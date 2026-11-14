//! Line series, error bars and scatter markers.

use super::*;

/// Draw line series, their raster marker layer, error bars and scatter points.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_series_section<'a, DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &mut ChartContext<'a, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    tx: &FX,
    ty: &FY,
    entries: &mut Vec<LegendEntry>,
    raster_scatter: bool,
    custom_legend: bool,
    overlays: &mut Vec<String>,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend + 'a,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
{
    let marker_total = p
        .series
        .iter()
        .filter(|s| !s.marker.is_empty() && s.markersize > 0.0)
        .map(|s| s.x.as_array().len().min(s.y.as_array().len()))
        .sum::<usize>();
    let series_base = area.get_base_pixel();
    let mut series_marker_layer = if raster_scatter && marker_total >= 4096 {
        let (w, h) = area.dim_in_pixel();
        tiny_skia::Pixmap::new(w.max(1), h.max(1))
    } else {
        None
    };
    for s in &p.series {
        let base = area.get_base_pixel();
        let xs = s.x.as_array();
        let ys = s.y.as_array();
        let n = xs.len().min(ys.len());
        // Step drawstyles insert the corner points instead of a diagonal.
        let mut pts: Vec<(f64, f64)> = Vec::with_capacity(n * 2);
        for i in 0..n {
            pts.push((tx(xs[i]), ty(ys[i])));
            if i + 1 < n {
                match s.drawstyle.as_str() {
                    "steps-post" => pts.push((tx(xs[i + 1]), ty(ys[i]))),
                    "steps-pre" => pts.push((tx(xs[i]), ty(ys[i + 1]))),
                    _ => {}
                }
            }
        }
        if n > 2000 && s.drawstyle != "steps-pre" && s.drawstyle != "steps-post" {
            // Pixel-space simplification leaves the drawn path visually
            // unchanged while cutting the SVG path (and rasteriser work) by
            // orders of magnitude for dense series.
            let kept = {
                let chart_area = chart.plotting_area();
                simplify_polyline(&pts, 0.5, |p| {
                    let (x, y) = chart_area.map_coordinate(p);
                    (x as f64, y as f64)
                })
            };
            if kept.len() < pts.len() {
                pts = kept;
            }
        }
        let width = s.linewidth.max(1.0).round() as u32;
        let col = match s.alpha {
            Some(a) => color(&s.color).mix(a.clamp(0.0, 1.0)),
            None => color(&s.color).mix(1.0),
        };
        if s.linestyle == "None" {
            if !s.label.is_empty() && !s.marker.is_empty() {
                entries.push(LegendEntry {
                    label: s.label.clone(),
                    swatch: LegendSwatch::Marker(col, s.marker.clone()),
                });
            }
        } else if matches!(s.linestyle.as_str(), ":" | "--" | "-.") {
            let lw = s.linewidth.max(1.0);
            // Matplotlib scales its dash sequences by line width.
            let (dash, gap) = match s.linestyle.as_str() {
                ":" => (lw, lw * 1.65),
                "--" => (lw * 3.7, lw * 1.6),
                _ => (lw * 6.4, lw * 1.6),
            };
            let (px, clip) = {
                let chart_area = chart.plotting_area();
                let (xr, yr) = chart_area.get_pixel_range();
                let px: Vec<(i32, i32)> = pts
                    .iter()
                    .map(|p| {
                        let (x, y) = chart_area.map_coordinate(p);
                        (x - base.0, y - base.1)
                    })
                    .collect();
                (
                    px,
                    (
                        (xr.start - base.0) as f64,
                        (xr.end - base.0) as f64,
                        (yr.start - base.1) as f64,
                        (yr.end - base.1) as f64,
                    ),
                )
            };
            for run in clip_polyline(&px, clip) {
                draw_dashed(area, &run, col, width, dash, gap)?;
            }
            if !s.label.is_empty() {
                entries.push(LegendEntry {
                    label: s.label.clone(),
                    swatch: if s.marker.is_empty() {
                        LegendSwatch::Line(col, width)
                    } else {
                        LegendSwatch::LineMarker(col, width, s.marker.clone())
                    },
                });
                if !custom_legend {
                    chart
                        .draw_series(LineSeries::new(
                            Vec::<(f64, f64)>::new(),
                            col.stroke_width(width),
                        ))?
                        .label(s.label.as_str())
                        .legend(move |(x, y)| {
                            PathElement::new(vec![(x, y), (x + 20, y)], col.stroke_width(width))
                        });
                }
            }
        } else {
            let (px, clip) = {
                let chart_area = chart.plotting_area();
                let (xr, yr) = chart_area.get_pixel_range();
                let px: Vec<(i32, i32)> = pts
                    .iter()
                    .map(|p| {
                        let (x, y) = chart_area.map_coordinate(p);
                        (x - base.0, y - base.1)
                    })
                    .collect();
                (
                    px,
                    (
                        (xr.start - base.0) as f64,
                        (xr.end - base.0) as f64,
                        (yr.start - base.1) as f64,
                        (yr.end - base.1) as f64,
                    ),
                )
            };
            // Caps belong to the data ends only: a run cut by the axes must stop
            // flush at the spine rather than growing half a line width past it.
            for run in clip_polyline(&px, clip) {
                let caps = (
                    px.first() == Some(&run[0]),
                    px.last() == Some(&run[run.len() - 1]),
                );
                if has_sharp_join(&run, width) {
                    draw_solid_polyline(area, &run, col, width)?;
                } else {
                    area.draw(&PathElement::new(run.clone(), col.stroke_width(width)))?;
                }
                draw_projected_caps(area, &run, col, width, caps)?;
            }
            if !s.label.is_empty() {
                entries.push(LegendEntry {
                    label: s.label.clone(),
                    swatch: if s.marker.is_empty() {
                        LegendSwatch::Line(col, width)
                    } else {
                        LegendSwatch::LineMarker(col, width, s.marker.clone())
                    },
                });
            }
        }
        if !s.marker.is_empty() && s.markersize > 0.0 {
            let stroked = matches!(s.marker.as_str(), "x" | "+");
            let (fill_name, edge_name) = if stroked {
                (
                    s.mec.as_deref().unwrap_or(&s.color),
                    s.mec.as_deref().unwrap_or(&s.color),
                )
            } else {
                (
                    s.mfc.as_deref().unwrap_or(&s.color),
                    s.mec.as_deref().unwrap_or(&s.color),
                )
            };
            let shade = |name: &str| match s.alpha {
                Some(a) => color(name).mix(a.clamp(0.0, 1.0)),
                None => color(name).mix(1.0),
            };
            let (fill, edge) = (shade(fill_name), shade(edge_name));
            let r = marker_radius(s.markersize * s.markersize);
            let stroke = s.mew.max(1.0).round() as u32;
            let chart_area = chart.plotting_area();
            let (clip_x, clip_y) = chart_area.get_pixel_range();
            for (xv, yv) in xs.iter().zip(ys.iter()) {
                let (px, py) = chart_area.map_coordinate(&(tx(*xv), ty(*yv)));
                // Markers outside the axes are clipped away like the line is.
                if !clip_x.contains(&px) || !clip_y.contains(&py) {
                    continue;
                }
                if let Some(layer) = series_marker_layer.as_mut() {
                    draw_marker_raster(
                        layer,
                        series_base,
                        (px, py),
                        r,
                        fill,
                        edge,
                        stroke,
                        &s.marker,
                    );
                } else {
                    draw_marker(area, base, (px, py), r, fill, edge, stroke, &s.marker)?;
                }
            }
        }
    }
    if let Some(layer) = series_marker_layer {
        let (w, h) = area.dim_in_pixel();
        let png = crate::export::encode_png(&layer, PngCompression::Fast, false)
            .map_err(|e| e.to_string())?;
        overlays.push(format!(
            "<image x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" \
         preserveAspectRatio=\"none\" href=\"data:image/png;base64,{}\"/>",
            series_base.0,
            series_base.1,
            w,
            h,
            base64(&png)
        ));
    }
    // Error bars: one segment per point plus optional caps, in canvas pixels.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, ylo, yhi, xlo, xhi, c, cap) in &p.errors {
            let col = color(c);
            let cap = cap.round().max(0.0) as i32;
            let (ya, yb) = (ylo.as_array(), yhi.as_array());
            let (xa, xb) = (xlo.as_array(), xhi.as_array());
            let (xs_v, ys_v) = (x.as_array(), y.as_array());
            let yz = ya.iter().zip(yb.iter());
            let xz = xa.iter().zip(xb.iter());
            let it = xs_v.iter().zip(ys_v.iter());
            for ((xv, yv), ((lo, hi), (xl, xh))) in it.zip(yz.zip(xz)) {
                let (cx, cy) = chart_area.map_coordinate(&(tx(*xv), ty(*yv)));
                let (cx, cy) = (cx - base.0, cy - base.1);
                if *lo > 0.0 || *hi > 0.0 {
                    let (_, yt) = chart_area.map_coordinate(&(tx(*xv), ty(*yv + *hi)));
                    let (_, yb) = chart_area.map_coordinate(&(tx(*xv), ty(*yv - *lo)));
                    let (yt, yb) = (yt - base.1, yb - base.1);
                    area.draw(&PathElement::new(
                        vec![(cx, yt), (cx, yb)],
                        col.stroke_width(1),
                    ))?;
                    if cap > 0 {
                        for yc in [yt, yb] {
                            area.draw(&PathElement::new(
                                vec![(cx - cap, yc), (cx + cap, yc)],
                                col.stroke_width(1),
                            ))?;
                        }
                    }
                }
                if *xl > 0.0 || *xh > 0.0 {
                    let (xl_px, _) = chart_area.map_coordinate(&(tx(*xv - *xl), ty(*yv)));
                    let (xr_px, _) = chart_area.map_coordinate(&(tx(*xv + *xh), ty(*yv)));
                    let (xl_px, xr_px) = (xl_px - base.0, xr_px - base.0);
                    area.draw(&PathElement::new(
                        vec![(xl_px, cy), (xr_px, cy)],
                        col.stroke_width(1),
                    ))?;
                    if cap > 0 {
                        for xc in [xl_px, xr_px] {
                            area.draw(&PathElement::new(
                                vec![(xc, cy - cap), (xc, cy + cap)],
                                col.stroke_width(1),
                            ))?;
                        }
                    }
                }
            }
        }
    }
    // Scatter markers: per-point size and colour, so they bypass PointSeries.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        let mut legend_scatter: Vec<(String, RGBAColor)> = Vec::new();
        // Any raster scatter benefits from the layer: tiny_skia keeps the
        // fractional radius and anti-aliases the marker edge, which the
        // integer plotters circles cannot do.
        let mut marker_layer = if raster_scatter {
            let (w, h) = area.dim_in_pixel();
            // Falling back to per-point elements is better than failing a save.
            tiny_skia::Pixmap::new(w.max(1), h.max(1))
        } else {
            None
        };
        for sc in &p.scatter {
            let xs = sc.x.as_array();
            let ys = sc.y.as_array();
            let sizes = sc.sizes.as_array();
            let values = sc.values.as_ref().map(|v| v.as_array());
            let (cmin, cmax) = sc.clim.unwrap_or_else(|| match &values {
                Some(v) => range(v.iter().copied()),
                None => (0.0, 1.0),
            });
            let alpha = sc.alpha.clamp(0.0, 1.0);
            for i in 0..xs.len().min(ys.len()) {
                let (cx, cy) = chart_area.map_coordinate(&(tx(xs[i]), ty(ys[i])));
                // matplotlib's `s` is an area in points^2; ~1.39 px/pt at 100 dpi.
                let sz = sizes.get(i).copied().unwrap_or(36.0).max(0.0);
                let r = marker_radius(sz);
                let col = if !sc.colors.is_empty() {
                    color(&sc.colors[i % sc.colors.len()])
                } else if let Some(v) = &values {
                    let t = if cmax > cmin {
                        ((v[i] - cmin) / (cmax - cmin)).clamp(0.0, 1.0)
                    } else {
                        0.5
                    };
                    let c = colormap(&sc.cmap, t);
                    RGBAColor(c[0], c[1], c[2], 1.0)
                } else {
                    RGBAColor(31, 119, 180, 1.0)
                };
                let col = col.mix(alpha);
                if let Some(layer) = marker_layer.as_mut() {
                    draw_marker_raster(layer, base, (cx, cy), r, col, col, 2, &sc.marker);
                } else {
                    draw_marker(area, base, (cx, cy), r, col, col, 2, &sc.marker)?;
                }
            }
            if !sc.label.is_empty() {
                let icon = if sc.colors.is_empty() {
                    RGBAColor(31, 119, 180, 1.0)
                } else {
                    color(&sc.colors[0])
                };
                legend_scatter.push((sc.label.clone(), icon.mix(alpha)));
            }
        }
        if let Some(layer) = marker_layer {
            let (w, h) = area.dim_in_pixel();
            let png = crate::export::encode_png(&layer, PngCompression::Fast, false)
                .map_err(|e| e.to_string())?;
            overlays.push(format!(
                "<image x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" \
             preserveAspectRatio=\"none\" href=\"data:image/png;base64,{}\"/>",
                base.0,
                base.1,
                w,
                h,
                base64(&png)
            ));
        }
        // Registered once the plotting-area borrow is released.
        for (label, col) in legend_scatter {
            entries.push(LegendEntry {
                label: label.clone(),
                swatch: LegendSwatch::Circle(col),
            });
            if !custom_legend {
                let series = chart.draw_series(std::iter::once(Rectangle::new(
                    [(0.0f64, 0.0f64), (0.0f64, 0.0f64)],
                    RGBColor(0, 0, 0).mix(0.0).filled(),
                )))?;
                series
                    .label(label.as_str())
                    .legend(move |(x, y)| Circle::new((x + 10, y + 4), 4, col.filled()));
            }
        }
    }
    Ok(())
}
