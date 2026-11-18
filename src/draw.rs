use plotters::coord::types::RangedCoordf64;
use plotters::prelude::*;
use plotters::style::text_anchor::{HPos, Pos, VPos};
use plotters::style::IntoFont;

use crate::color::color;
use crate::image::{base64, image_png_for_size, image_rgb};
use crate::layout::{
    aspect_datalim, auto_ticks, auto_ticks_for, axis_bounds, panel_ranges, range, tick_target,
};
use crate::model::{
    DrawStyle, LegendEntry, LegendSwatch, Marker, OwnedArray1, Panel, PngCompression,
};

use crate::scale::{asinh_scale, logit, symlog};

mod axes;
mod bars;
mod collection;
mod colorbar;
mod contour;
mod image;
mod legend;
mod markers;
mod polyline;
mod quiver;
mod series;
mod text;
pub(crate) use text::draw_label;
mod ticks;

/// Plotters' SVG backend divides text sizes by 1.24; matplotlib sizes are
/// points at `dpi`. Convert once so both land on the same pixel size.
pub(crate) fn text_px(size: f64, dpi: f64) -> f64 {
    size * dpi.max(1.0) / 72.0 * 1.24
}

#[allow(clippy::too_many_arguments)]
fn hex_encode(text: &str) -> String {
    use std::fmt::Write as _;
    let mut out = String::with_capacity(text.len() * 2);
    for byte in text.bytes() {
        let _ = write!(out, "{byte:02x}");
    }
    out
}

/// Mark the start or end of an artist carrying an SVG `gid`. The exporter
/// turns these text elements into `<g id="...">` / `</g>` after drawing, since
/// plotters' SVG backend has no hook for raw attributes.
pub(crate) fn draw_gid_marker<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    gid: &str,
    opening: bool,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let marker = format!(
        "__matplotvite_gid_{}_{}__",
        if opening { 'o' } else { 'c' },
        hex_encode(gid)
    );
    area.draw(&Text::new(marker, (0, 0), ("sans-serif", 1u32).into_font()))?;
    Ok(())
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn draw_panel<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    p: &Panel,
    overlays: &mut Vec<String>,
    twin_gap_px: i32,
    raster_scatter: bool,
    draw_images: bool,
    dpi: f64,
    line_scale: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let colorbar = p.colorbar.as_ref();
    let colorbar_horizontal = colorbar.map(|item| item.7 == "horizontal").unwrap_or(false);
    let fg = p
        .foreground
        .map(|c| c.rgba())
        .unwrap_or_else(|| color("#000000"));
    let twin_reserve = p.twin_reserve.as_str();
    let (mut x0, mut x1, mut y0, mut y1) = panel_ranges(p);
    // Log axes are laid out in log10 space: the ranges and every mapped point are
    // transformed, and the tick labels are converted back to powers of ten.
    let base = if p.log_base > 1.0 { p.log_base } else { 10.0 };
    let tx = |v: f64| {
        if p.x_log {
            v.max(f64::MIN_POSITIVE).log(base)
        } else if p.x_symlog {
            symlog(v, p.x_symlog_linthresh)
        } else if p.x_logit {
            logit(v)
        } else if p.x_asinh {
            asinh_scale(v, p.x_asinh_linear_width)
        } else {
            v
        }
    };
    let ty = |v: f64| {
        if p.y_log {
            v.max(f64::MIN_POSITIVE).log(base)
        } else if p.y_symlog {
            symlog(v, p.y_symlog_linthresh)
        } else if p.y_logit {
            logit(v)
        } else if p.y_asinh {
            asinh_scale(v, p.y_asinh_linear_width)
        } else {
            v
        }
    };
    if p.x_log || p.x_symlog || p.x_logit || p.x_asinh {
        (x0, x1) = (tx(x0), tx(x1));
        if x1 <= x0 {
            x1 = x0 + 1.0;
        }
    }
    if p.y_log || p.y_symlog || p.y_logit || p.y_asinh {
        (y0, y1) = (ty(y0), ty(y1));
        if y1 <= y0 {
            y1 = y0 + 1.0;
        }
    }
    // Apply matplotlib's default 5% autoscale margin in the (possibly
    // log-transformed) coordinate space. Explicit limits bypass it unchanged.
    (x0, x1) = axis_bounds((x0, x1), p.xlim.map(|(lo, hi)| (tx(lo), tx(hi))));
    (y0, y1) = axis_bounds((y0, y1), p.ylim.map(|(lo, hi)| (ty(lo), ty(hi))));
    // A fixed aspect either shrinks the plotting box (matplotlib's
    // adjustable="box", the set_aspect/imshow default) or bends the data
    // limits so the box keeps its size (adjustable="datalim", chosen by
    // axis("equal")).
    let title_size = text_px(p.title_size.unwrap_or(12.0).max(6.0), dpi)
        .max(6.0)
        .round() as u32;
    let custom_legend = p.legend.show && p.legend.is_custom();
    let mut entries: Vec<LegendEntry> = Vec::new();
    let exact_axes = p.axes_bounds;
    // Fixed margins at 25 px + 45 px label bands only fit tall panels. On a
    // short subplot row they consume the whole cell, leaving a few pixels for
    // the data (Matplotlib budgets these margins as a fraction of the axes).
    let panel_h = area.dim_in_pixel().1 as f64;
    let margin = (panel_h / 10.0).clamp(4.0, 25.0).round() as u32;
    let xs_for_grid: Vec<f64> = match &p.ticks.xticks {
        Some(values) => values.iter().map(|&v| tx(v)).collect(),
        None => auto_ticks(x0, x1, p.x_log),
    };
    let ys_for_grid: Vec<f64> = match &p.ticks.yticks {
        Some(values) => values.iter().map(|&v| ty(v)).collect(),
        None => auto_ticks(y0, y1, p.y_log),
    };
    let ys_for_labels = &ys_for_grid;
    let ylabels: Vec<String> = match (&p.ticks.yticklabels, &p.ticks.yticks) {
        (Some(labels), Some(_)) => (0..ys_for_labels.len())
            .map(|i| labels.get(i).cloned().unwrap_or_default())
            .collect(),
        _ => {
            let format = ticks::tick_format(ys_for_labels);
            ys_for_labels
                .iter()
                .map(|v| {
                    if p.y_log {
                        ticks::log_label(*v, base)
                    } else {
                        ticks::tick_label(*v, format)
                    }
                })
                .collect()
        }
    };
    let label_size = text_px(p.ticks.xstyle.labelsize.max(6.0), dpi).round() as u32;
    let desc_size = text_px(
        p.xlabel_size
            .unwrap_or(10.0)
            .max(p.ylabel_size.unwrap_or(10.0))
            .max(6.0),
        dpi,
    )
    .round() as u32;
    // The tick-label band and the axis description share `label_area`. Measure
    // the actual tick strings so a large `labelsize` reserves room for both
    // instead of drawing the axis label on top of the tick labels.
    let tick_px = text_px(
        p.ticks
            .xstyle
            .labelsize
            .max(p.ticks.ystyle.labelsize)
            .max(6.0),
        dpi,
    );
    let y_tick_width = ylabels
        .iter()
        .map(|label| crate::fonts::text_width(label, tick_px))
        .fold(0.0, f64::max);
    let x_desc_pad = if p.xlabel.is_empty() {
        0.0
    } else {
        desc_size as f64 + 6.0
    };
    let y_desc_pad = if p.ylabel.is_empty() {
        0.0
    } else {
        desc_size as f64 + 6.0
    };
    let max_label_w = (area.dim_in_pixel().0 as f64 * 0.45).max(40.0);
    let max_label_h = (panel_h * 0.45).max(30.0);
    let y_label_area = (y_tick_width + y_desc_pad + 6.0)
        .max(40.0)
        .min(max_label_w)
        .round() as u32;
    let x_label_area = if exact_axes {
        30
    } else {
        (tick_px * 1.15 + x_desc_pad + 6.0)
            .max(30.0)
            .min(max_label_h)
            .round() as u32
    };
    let y_label_area = if exact_axes { 40 } else { y_label_area };
    let shrunk_area;
    let mut builder = ChartBuilder::on(area);
    if exact_axes {
        // `add_axes`/insets already include their label margins in `bounds`.
        // Keep the chart plotting area on the requested rectangle instead of
        // adding the normal panel margin a second time.
        builder.margin(0);
        builder.margin_right(25);
        builder.margin_top(25);
        if colorbar_horizontal {
            builder.margin_bottom(110);
        }
    } else {
        builder.margin(margin);
        if colorbar.is_some() {
            if colorbar_horizontal {
                builder.margin_bottom(110);
            } else {
                builder.margin_right(125);
            }
        } else if twin_reserve == "y" {
            builder.margin_right(10 + twin_gap_px);
        } else if twin_reserve == "x" {
            builder.margin_top(10 + twin_gap_px);
        }
    }
    // An equal-aspect panel may rebuild its chart after measuring the plotting
    // area. Leave the caption empty for that probe so it cannot be drawn twice.
    // An empty caption still reserves a title band in plotters, which shifts
    // untitled panels down and breaks axes-rectangle placement.
    if p.aspect.is_none() && !p.title.is_empty() && !exact_axes {
        builder.caption(
            &p.title,
            (
                p.title_family.as_deref().unwrap_or(&p.font_family),
                title_size,
            )
                .into_font()
                .color(&fg),
        );
    }
    let mut chart = builder
        .x_label_area_size(x_label_area)
        .y_label_area_size(y_label_area)
        .build_cartesian_2d(x0..x1, y0..y1)?;
    if let Some(scale) = p.aspect {
        let (pw, ph) = chart.plotting_area().dim_in_pixel();
        let mut target: Option<DrawingArea<DB, plotters::coord::Shift>> = None;
        if pw > 8 && ph > 8 {
            if p.aspect_datalim {
                ((x0, x1), (y0, y1)) =
                    aspect_datalim((x0, x1), (y0, y1), scale, (pw as f64, ph as f64));
            } else {
                let ratio = (x1 - x0).abs() / (y1 - y0).abs() / scale;
                if ratio.is_finite() && ratio > 0.0 {
                    let mut dw = 0i32;
                    let mut dh = 0i32;
                    if pw as f64 / ph as f64 > ratio {
                        dw = (pw as f64 - ratio * ph as f64).round() as i32;
                    } else {
                        dh = (ph as f64 - pw as f64 / ratio).round() as i32;
                    }
                    if dw > 0 || dh > 0 {
                        shrunk_area = area.margin(dh / 2, dh - dh / 2, dw / 2, dw - dw / 2);
                        target = Some(shrunk_area);
                    }
                }
            }
        }
        let mut rb = match &target {
            Some(a) => ChartBuilder::on(a),
            None => ChartBuilder::on(area),
        };
        rb.margin(margin);
        if colorbar.is_some() {
            if colorbar_horizontal {
                rb.margin_bottom(110);
            } else {
                rb.margin_right(125);
            }
        } else if twin_reserve == "y" {
            rb.margin_right(10 + twin_gap_px);
        } else if twin_reserve == "x" {
            rb.margin_top(10 + twin_gap_px);
        }
        if !p.title.is_empty() {
            rb.caption(
                &p.title,
                (
                    p.title_family.as_deref().unwrap_or(&p.font_family),
                    title_size,
                )
                    .into_font()
                    .color(&fg),
            );
        }
        chart = rb
            .x_label_area_size(x_label_area)
            .y_label_area_size(y_label_area)
            .build_cartesian_2d(x0..x1, y0..y1)?;
    }
    if let Some(fc) = p.facecolor {
        chart.plotting_area().fill(&fc.rgba())?;
    }
    axes::draw_axes(
        area,
        &mut chart,
        p,
        (x0, x1, y0, y1),
        label_size,
        desc_size,
        &xs_for_grid,
        &ys_for_grid,
        base,
        twin_gap_px,
        dpi,
        fg,
    )?;
    if exact_axes && !p.title.is_empty() {
        // `add_axes` titles sit above the requested axes box rather than
        // taking a caption band out of it.
        let base = area.get_base_pixel();
        let pa = chart.plotting_area();
        let tl = pa.map_coordinate(&(x0, y1));
        let br = pa.map_coordinate(&(x1, y0));
        draw_label(
            area,
            base,
            ((tl.0 + br.0) / 2 - base.0, tl.1 - base.1 - 6),
            &p.title,
            fg,
            title_size as f64,
            "center",
            "bottom",
            None,
            0.0,
            line_scale,
            p.title_family.as_deref().unwrap_or(&p.font_family),
        )?;
    }
    // Filled contours sit on the image layer, under the line series.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, z, levels, _linewidths, colors, cmap, filled, alpha) in &p.contours {
            if !*filled || levels.len() < 2 {
                continue;
            }
            let opacity = alpha.clamp(0.0, 1.0);
            let xs: Vec<f64> = x.as_array().iter().copied().collect();
            let ys: Vec<f64> = y.as_array().iter().copied().collect();
            let zs: Vec<f64> = z.as_array().iter().copied().collect();
            let (rows, cols) = (ys.len(), xs.len());
            if rows < 2 || cols < 2 || rows.checked_mul(cols) != Some(zs.len()) {
                continue;
            }
            let bands = levels.len() - 1;
            for band in 0..bands {
                let (lo, hi) = (levels[band], levels[band + 1]);
                let col = (if colors.is_empty() {
                    let c = cmap.sample((band as f64 + 0.5) / bands as f64);
                    RGBAColor(c[0], c[1], c[2], 1.0)
                } else {
                    colors[band % colors.len()].rgba()
                })
                .mix(opacity);
                let map = |px: f64, py: f64| {
                    let (ax, ay) = chart_area.map_coordinate(&(tx(px), ty(py)));
                    (ax - base.0, ay - base.1)
                };
                for i in 0..rows - 1 {
                    let (y0, y1) = (ys[i], ys[i + 1]);
                    let row = &zs[i * cols..i * cols + cols];
                    let next = &zs[(i + 1) * cols..(i + 1) * cols + cols];
                    let mut j = 0;
                    while j + 1 < cols {
                        let (z00, z01) = (row[j], row[j + 1]);
                        let (z10, z11) = (next[j], next[j + 1]);
                        let zmin = z00.min(z01).min(z10).min(z11);
                        let zmax = z00.max(z01).max(z10).max(z11);
                        if zmin > hi || zmax < lo {
                            j += 1;
                            continue;
                        }
                        if zmin >= lo && zmax <= hi {
                            // Cells entirely inside a band tile it exactly, so a
                            // horizontal run collapses into one rectangle. This
                            // is what keeps the rasteriser from walking tens of
                            // thousands of tiny triangle sub-paths.
                            let j0 = j;
                            while j + 1 < cols - 1 {
                                let (a, b) = (row[j + 1], row[j + 2]);
                                let (c, d) = (next[j + 1], next[j + 2]);
                                if a >= lo
                                    && a <= hi
                                    && b >= lo
                                    && b <= hi
                                    && c >= lo
                                    && c <= hi
                                    && d >= lo
                                    && d <= hi
                                {
                                    j += 1;
                                } else {
                                    break;
                                }
                            }
                            // Runs are axis-aligned rectangles; `<rect>` is
                            // considerably cheaper for resvg than a 4-point path.
                            let (xa, ya) = map(xs[j0], y0);
                            let (xb, yb) = map(xs[j + 1], y1);
                            let (xl, xr) = (xa.min(xb), xa.max(xb));
                            let (yt, yb) = (ya.min(yb), ya.max(yb));
                            if xr > xl && yb > yt {
                                area.draw(&Rectangle::new([(xl, yt), (xr, yb)], col.filled()))?;
                            }
                            j += 1;
                            continue;
                        }
                        let p00 = (xs[j], y0, z00);
                        let p01 = (xs[j + 1], y0, z01);
                        let p10 = (xs[j], y1, z10);
                        let p11 = (xs[j + 1], y1, z11);
                        // Split each partial cell into two triangles: a band cut
                        // through a triangle is an exact polygon for piecewise-
                        // linear interpolation.
                        for tri in [[p00, p01, p11], [p00, p11, p10]] {
                            let poly = contour::clip_band(&tri, lo, hi);
                            if poly.len() < 3 {
                                continue;
                            }
                            let pts: Vec<(i32, i32)> =
                                poly.iter().map(|&(px, py, _)| map(px, py)).collect();
                            area.draw(&Polygon::new(pts, col.filled()))?;
                        }
                        j += 1;
                    }
                }
            }
        }
    }
    // Filled areas (`fill_between`/`fill`): closed data-space polygons.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        let mut legend_bands: Vec<(String, RGBAColor)> = Vec::new();
        for band in &p.bands {
            if !band.gid.is_empty() {
                draw_gid_marker(area, &band.gid, true)?;
            }
            'band: {
                let (xs, ys) = (band.x.as_array(), band.y.as_array());
                if xs.len() < 3 || xs.len() != ys.len() {
                    break 'band;
                }
                let alpha = band.alpha.unwrap_or(1.0).clamp(0.0, 1.0);
                let map = |x: f64, y: f64| {
                    let (px, py) = chart_area.map_coordinate(&(tx(x), ty(y)));
                    (px - base.0, py - base.1)
                };
                // Batched bands carry one closed ring and one RGB triple per cell;
                // hexbin uses this to avoid one Python dict per hexagon.
                if band.cells > 0
                    && band.cell_colors.len() == band.cells * 6
                    && xs.len() % band.cells == 0
                {
                    let per_cell = xs.len() / band.cells;
                    let parse = |h: &str| u8::from_str_radix(h, 16).unwrap_or(0);
                    for k in 0..band.cells {
                        let start = k * per_cell;
                        let pts: Vec<(i32, i32)> = (0..per_cell)
                            .map(|i| map(xs[start + i], ys[start + i]))
                            .collect();
                        let hex = &band.cell_colors[k * 6..k * 6 + 6];
                        let col =
                            RGBAColor(parse(&hex[0..2]), parse(&hex[2..4]), parse(&hex[4..6]), 1.0)
                                .mix(alpha);
                        // Matplotlib's hexbin uses edgecolors="face". Plotters'
                        // polygon ignores strokes, so grow each cell about its
                        // centre instead: adjacent fills overlap and the white
                        // antialiased seam between them disappears.
                        let n = pts.len() as f64;
                        let cx = pts.iter().map(|p| p.0 as f64).sum::<f64>() / n;
                        let cy = pts.iter().map(|p| p.1 as f64).sum::<f64>() / n;
                        let grown: Vec<(i32, i32)> = pts
                            .iter()
                            .map(|&(x, y)| {
                                let (dx, dy) = (x as f64 - cx, y as f64 - cy);
                                let len = (dx * dx + dy * dy).sqrt().max(1.0);
                                (
                                    (x as f64 + dx / len).round() as i32,
                                    (y as f64 + dy / len).round() as i32,
                                )
                            })
                            .collect();
                        area.draw(&Polygon::new(grown, col.filled()))?;
                    }
                    if !band.label.is_empty() {
                        let hex = &band.cell_colors[..6];
                        legend_bands.push((
                            band.label.clone(),
                            RGBAColor(parse(&hex[0..2]), parse(&hex[2..4]), parse(&hex[4..6]), 1.0)
                                .mix(alpha),
                        ));
                    }
                    break 'band;
                }
                let pts: Vec<(i32, i32)> =
                    xs.iter().zip(ys.iter()).map(|(x, y)| map(*x, *y)).collect();
                let col = band.color.rgba().mix(alpha);
                area.draw(&Polygon::new(pts, col.filled()))?;
                if !band.label.is_empty() {
                    legend_bands.push((band.label.clone(), col));
                }
            }
            if !band.gid.is_empty() {
                draw_gid_marker(area, &band.gid, false)?;
            }
        }
        for (label, col) in legend_bands {
            entries.push(LegendEntry {
                label: label.clone(),
                swatch: LegendSwatch::Collection(col),
            });
        }
    }
    bars::draw_bars_section(area, &chart, p, &tx, &ty, &mut entries)?;
    collection::draw_collection_section(
        area,
        &chart,
        p,
        &tx,
        &ty,
        &mut entries,
        raster_scatter,
        overlays,
    )?;
    series::draw_series_section(
        area,
        &mut chart,
        p,
        &tx,
        &ty,
        &mut entries,
        raster_scatter,
        overlays,
    )?;
    // Iso-lines are stroked above the series, one segment per marching-squares cell.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, z, levels, linewidths, colors, cmap, filled, alpha) in &p.contours {
            if *filled || levels.is_empty() {
                continue;
            }
            let opacity = alpha.clamp(0.0, 1.0);
            let xs: Vec<f64> = x.as_array().iter().copied().collect();
            let ys: Vec<f64> = y.as_array().iter().copied().collect();
            let zs: Vec<f64> = z.as_array().iter().copied().collect();
            let (rows, cols) = (ys.len(), xs.len());
            if rows < 2 || cols < 2 || rows.checked_mul(cols) != Some(zs.len()) {
                continue;
            }
            let n = levels.len() as f64;
            for (li, level) in levels.iter().enumerate() {
                let col = (if colors.is_empty() {
                    let t = if n > 1.0 { li as f64 / (n - 1.0) } else { 0.5 };
                    let c = cmap.sample(t);
                    RGBAColor(c[0], c[1], c[2], 1.0)
                } else {
                    colors[li % colors.len()].rgba()
                })
                .mix(opacity);
                let width = linewidths
                    .get(li)
                    .or_else(|| linewidths.first())
                    .copied()
                    .unwrap_or(2.0)
                    .clamp(0.25, 64.0);
                for line in
                    contour::contour_polylines(contour::contour_segments(&xs, &ys, &zs, *level))
                {
                    let points: Vec<(i32, i32)> = line
                        .iter()
                        .map(|(x, y)| {
                            let (px, py) = chart_area.map_coordinate(&(tx(*x), ty(*y)));
                            (px - base.0, py - base.1)
                        })
                        .collect();
                    area.draw(&PathElement::new(
                        points,
                        col.stroke_width(width.round().max(1.0) as u32),
                    ))?;
                }
            }
        }
    }
    quiver::draw_quiver_section(area, &chart, p, &tx, &ty, x0, x1, y0, y1, dpi)?;
    text::draw_text_section(area, &chart, p, &tx, &ty, line_scale, dpi)?;
    image::draw_panel_images(
        area,
        &chart,
        p,
        tx,
        ty,
        area.get_base_pixel(),
        draw_images,
        overlays,
    )?;
    legend::draw_legend_section(
        area,
        &mut chart,
        p,
        &mut entries,
        &tx,
        &ty,
        x0,
        x1,
        y0,
        y1,
        fg,
        dpi,
        custom_legend,
    )?;
    if let Some((
        cmap,
        vmin,
        vmax,
        label,
        log,
        limits,
        base,
        orientation,
        extend,
        extendrect,
        extendfrac,
    )) = colorbar
    {
        let origin = area.get_base_pixel();
        let pa = chart.plotting_area();
        let tl = pa.map_coordinate(&(x0, y1));
        let br = pa.map_coordinate(&(x1, y0));
        colorbar::draw_colorbar(
            area,
            (
                tl.0 - origin.0,
                tl.1 - origin.1,
                br.0 - origin.0,
                br.1 - origin.1,
            ),
            *cmap,
            *vmin,
            *vmax,
            label,
            *log,
            *limits,
            *base,
            orientation,
            extend,
            *extendrect,
            *extendfrac,
            line_scale,
            p.font_family.as_str(),
        )?;
    }
    Ok(())
}
