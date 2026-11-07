use plotters::coord::types::RangedCoordf64;
use plotters::prelude::*;
use plotters::style::text_anchor::{HPos, Pos, VPos};
use plotters::style::IntoFont;

use crate::color::{color, colormap};
use crate::image::{base64, image_png};
use crate::layout::{auto_ticks, panel_ranges, range};
use crate::model::{Legend, LegendEntry, LegendSwatch, Panel};

/// Draw one label. Alignment is approximated: the backend only has a top-left
/// anchor, so the text width is estimated from the glyph count.
#[allow(clippy::too_many_arguments)]
fn draw_label<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    pos: (i32, i32),
    s: &str,
    col: RGBAColor,
    size: f64,
    ha: &str,
    va: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let fs = size.max(1.0);
    let w = s.chars().count() as f64 * fs * 0.55;
    let dx = match ha {
        "center" => -w / 2.0,
        "right" => -w,
        _ => 0.0,
    };
    let dy = match va {
        "top" => 0.0,
        "center" => -fs / 2.0,
        "bottom" => -fs,
        _ => -fs * 0.8, // baseline
    };
    let style = ("sans-serif", fs.round() as u32).into_font().color(&col);
    area.draw(&Text::new(
        s,
        (pos.0 - base.0 + dx as i32, pos.1 - base.1 + dy as i32),
        style,
    ))?;
    Ok(())
}

/// Straight arrow with a triangular head, in canvas pixels.
fn draw_arrow<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    from: (i32, i32),
    to: (i32, i32),
    col: RGBAColor,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (sx, sy) = (from.0 - base.0, from.1 - base.1);
    let (ax, ay) = (to.0 - base.0, to.1 - base.1);
    area.draw(&PathElement::new(
        vec![(sx, sy), (ax, ay)],
        col.stroke_width(2),
    ))?;
    let (dx, dy) = ((ax - sx) as f64, (ay - sy) as f64);
    let len = (dx * dx + dy * dy).sqrt().max(1.0);
    let (ux, uy) = (dx / len, dy / len);
    let (hl, hw) = (10.0, 4.5);
    let (px, py) = (ax as f64 - ux * hl, ay as f64 - uy * hl);
    area.draw(&Polygon::new(
        vec![
            (ax, ay),
            ((px - uy * hw) as i32, (py + ux * hw) as i32),
            ((px + uy * hw) as i32, (py - ux * hw) as i32),
        ],
        col.filled(),
    ))?;
    Ok(())
}

fn rotated_style(size: f64, col: RGBAColor, rotation: f64) -> TextStyle<'static> {
    let style = ("sans-serif", size.max(6.0).round() as u32)
        .into_font()
        .color(&col);
    let deg = rotation.rem_euclid(360.0);
    if (45.0..135.0).contains(&deg) {
        style.transform(FontTransform::Rotate90)
    } else if (135.0..225.0).contains(&deg) {
        style.transform(FontTransform::Rotate180)
    } else if (225.0..315.0).contains(&deg) {
        style.transform(FontTransform::Rotate270)
    } else {
        style
    }
}

/// Draw ticks, tick labels and styled gridlines for panels whose tick layout is
/// controlled from Python. The plotters mesh still provides the axis frame and
/// descriptions; this only replaces its ticks and grid.
fn draw_manual_ticks<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &ChartContext<DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    ranges: (f64, f64, f64, f64),
    log_base: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (x0, x1, y0, y1) = ranges;
    let pa = chart.plotting_area();
    let origin = area.get_base_pixel();
    let tl = pa.map_coordinate(&(x0, y1));
    let br = pa.map_coordinate(&(x1, y0));
    let (left, top) = (tl.0 - origin.0, tl.1 - origin.1);
    let (right, bottom) = (br.0 - origin.0, br.1 - origin.1);
    let grid_col = color(p.grid.color.as_deref().unwrap_or("#b0b0b0"));
    let grid_alpha = p.grid.alpha.unwrap_or(1.0).clamp(0.0, 1.0);
    let grid_w = p.grid.linewidth.unwrap_or(1.0).max(1.0).round() as u32;
    let grid_style = grid_col.mix(grid_alpha).stroke_width(grid_w);
    let grid_dash = p.grid.linestyle.as_deref().and_then(dash_pattern);

    let to_chart_x = |v: f64| {
        if p.x_log {
            v.max(f64::MIN_POSITIVE).log(log_base)
        } else {
            v
        }
    };
    let to_chart_y = |v: f64| {
        if p.y_log {
            v.max(f64::MIN_POSITIVE).log(log_base)
        } else {
            v
        }
    };
    let xs: Vec<f64> = match &p.ticks.xticks {
        Some(v) => v.iter().map(|&v| to_chart_x(v)).collect(),
        None => auto_ticks(x0, x1, p.x_log),
    };
    let ys: Vec<f64> = match &p.ticks.yticks {
        Some(v) => v.iter().map(|&v| to_chart_y(v)).collect(),
        None => auto_ticks(y0, y1, p.y_log),
    };
    let xlabels: Vec<String> = match (&p.ticks.xticklabels, &p.ticks.xticks) {
        (Some(labels), Some(_)) => (0..xs.len())
            .map(|i| labels.get(i).cloned().unwrap_or_default())
            .collect(),
        _ => xs
            .iter()
            .map(|v| {
                if p.x_log {
                    log_label(*v, log_base)
                } else {
                    tick_label(*v)
                }
            })
            .collect(),
    };
    let ylabels: Vec<String> = match (&p.ticks.yticklabels, &p.ticks.yticks) {
        (Some(labels), Some(_)) => (0..ys.len())
            .map(|i| labels.get(i).cloned().unwrap_or_default())
            .collect(),
        _ => ys
            .iter()
            .map(|v| {
                if p.y_log {
                    log_label(*v, log_base)
                } else {
                    tick_label(*v)
                }
            })
            .collect(),
    };

    if p.grid.show && p.grid.axis != "y" {
        for v in &xs {
            let (px, _) = pa.map_coordinate(&(*v, y0));
            let px = px - origin.0;
            if let Some((dash, gap)) = grid_dash {
                draw_dashed(
                    area,
                    &[(px, top), (px, bottom)],
                    grid_col.mix(grid_alpha),
                    grid_w,
                    dash,
                    gap,
                )?;
            } else {
                area.draw(&PathElement::new(vec![(px, top), (px, bottom)], grid_style))?;
            }
        }
    }
    if p.grid.show && p.grid.axis != "x" {
        for v in &ys {
            let (_, py) = pa.map_coordinate(&(x0, *v));
            let py = py - origin.1;
            if let Some((dash, gap)) = grid_dash {
                draw_dashed(
                    area,
                    &[(left, py), (right, py)],
                    grid_col.mix(grid_alpha),
                    grid_w,
                    dash,
                    gap,
                )?;
            } else {
                area.draw(&PathElement::new(vec![(left, py), (right, py)], grid_style))?;
            }
        }
    }

    let default_tick = p.foreground.as_deref().unwrap_or("#000000");
    let xstyle = &p.ticks.xstyle;
    let xtick_col = color(xstyle.color.as_deref().unwrap_or(default_tick));
    let xlabel_col = color(xstyle.labelcolor.as_deref().unwrap_or(default_tick));
    let xtick_w = xstyle.width.max(1.0).round() as u32;
    let xtick_len = xstyle.length.max(0.0);
    for (v, label) in xs.iter().zip(xlabels.iter()) {
        let (px, _) = pa.map_coordinate(&(*v, y0));
        let px = px - origin.0;
        area.draw(&PathElement::new(
            vec![(px, bottom), (px, bottom + xtick_len as i32)],
            xtick_col.stroke_width(xtick_w),
        ))?;
        if !label.is_empty() && !p.ticks.hide_xlabels {
            let style = rotated_style(xstyle.labelsize, xlabel_col, xstyle.rotation)
                .pos(Pos::new(HPos::Center, VPos::Top));
            area.draw(&Text::new(
                label.clone(),
                (px, bottom + xtick_len as i32 + 4),
                style,
            ))?;
        }
    }
    let ystyle = &p.ticks.ystyle;
    let ytick_col = color(ystyle.color.as_deref().unwrap_or(default_tick));
    let ylabel_col = color(ystyle.labelcolor.as_deref().unwrap_or(default_tick));
    let ytick_w = ystyle.width.max(1.0).round() as u32;
    let ytick_len = ystyle.length.max(0.0);
    for (v, label) in ys.iter().zip(ylabels.iter()) {
        let (_, py) = pa.map_coordinate(&(x0, *v));
        let py = py - origin.1;
        area.draw(&PathElement::new(
            vec![(left - ytick_len as i32, py), (left, py)],
            ytick_col.stroke_width(ytick_w),
        ))?;
        if !label.is_empty() && !p.ticks.hide_ylabels {
            let style = rotated_style(ystyle.labelsize, ylabel_col, ystyle.rotation)
                .pos(Pos::new(HPos::Right, VPos::Center));
            area.draw(&Text::new(
                label.clone(),
                (left - ytick_len as i32 - 4, py),
                style,
            ))?;
        }
    }
    Ok(())
}

/// Draw the legend myself so placement, columns, title and frame options all
/// work; plotters' built-in legend only supports a single column.
fn draw_legend<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    rect: (i32, i32, i32, i32),
    entries: &[LegendEntry],
    opts: &Legend,
    text: RGBAColor,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    if entries.is_empty() {
        return Ok(());
    }
    let fs = opts.fontsize.max(6.0);
    let title_fs = opts.title_fontsize.max(6.0);
    let cols = opts.ncol.max(1);
    let rows = entries.len().div_ceil(cols);
    let col_w = entries
        .iter()
        .map(|e| e.label.chars().count())
        .max()
        .unwrap_or(0) as f64
        * fs
        * 0.58
        + 36.0;
    let row_h = fs * 1.6;
    let title_h = if opts.title.is_empty() {
        0.0
    } else {
        title_fs * 1.5
    };
    let box_w = col_w * cols as f64 + 8.0;
    let box_h = rows as f64 * row_h + title_h + 8.0;
    let (left, top, right, bottom) = rect;
    let (ax, ay) = opts.anchor.unwrap_or(match opts.loc.as_str() {
        "upper left" => (0.0, 1.0),
        "lower left" => (0.0, 0.0),
        "lower right" => (1.0, 0.0),
        "center" => (0.5, 0.5),
        "center left" => (0.0, 0.5),
        "center right" | "right" => (1.0, 0.5),
        "upper center" => (0.5, 1.0),
        "lower center" => (0.5, 0.0),
        _ => (1.0, 1.0),
    });
    let px = left as f64 + ax * (right - left) as f64;
    let py = bottom as f64 - ay * (bottom - top) as f64;
    let loc = opts.loc.as_str();
    let mut x = if loc.contains("right") {
        px - box_w
    } else if loc.contains("left") {
        px
    } else {
        px - box_w / 2.0
    };
    let mut y = if loc.contains("upper") {
        py
    } else if loc.contains("lower") {
        py - box_h
    } else {
        py - box_h / 2.0
    };
    x = x.clamp(left as f64, (right as f64 - box_w).max(left as f64));
    y = y.clamp(top as f64, (bottom as f64 - box_h).max(top as f64));
    if opts.frameon {
        area.draw(&Rectangle::new(
            [
                (x as i32, y as i32),
                ((x + box_w) as i32, (y + box_h) as i32),
            ],
            WHITE.filled(),
        ))?;
        area.draw(&Rectangle::new(
            [
                (x as i32, y as i32),
                ((x + box_w) as i32, (y + box_h) as i32),
            ],
            BLACK.stroke_width(1),
        ))?;
    }
    if !opts.title.is_empty() {
        let style = ("sans-serif", title_fs.round() as u32)
            .into_font()
            .color(&text);
        area.draw(&Text::new(
            opts.title.clone(),
            ((x + box_w / 2.0) as i32, (y + title_h / 2.0) as i32),
            style.pos(Pos::new(HPos::Center, VPos::Center)),
        ))?;
    }
    for (i, entry) in entries.iter().enumerate() {
        let col = i / rows.max(1);
        let row = i % rows.max(1);
        let cx = x + 6.0 + col as f64 * col_w;
        let cy = y + title_h + 4.0 + row as f64 * row_h + row_h / 2.0;
        match &entry.swatch {
            LegendSwatch::Line(c, w) => area.draw(&PathElement::new(
                vec![(cx as i32, cy as i32), ((cx + 20.0) as i32, cy as i32)],
                c.stroke_width(*w),
            ))?,
            LegendSwatch::Rect(c) => area.draw(&Rectangle::new(
                [
                    ((cx + 2.0) as i32, (cy - 5.0) as i32),
                    ((cx + 22.0) as i32, (cy + 5.0) as i32),
                ],
                c.filled(),
            ))?,
            LegendSwatch::Circle(c) => {
                area.draw(&Circle::new(((cx + 10.0) as i32, cy as i32), 5, c.filled()))?
            }
        }
        let style = ("sans-serif", fs.round() as u32).into_font().color(&text);
        area.draw(&Text::new(
            entry.label.clone(),
            ((cx + 28.0) as i32, cy as i32),
            style.pos(Pos::new(HPos::Left, VPos::Center)),
        ))?;
    }
    Ok(())
}

/// Map a matplotlib linestyle name onto a dash/gap length in pixels.
fn dash_pattern(linestyle: &str) -> Option<(f64, f64)> {
    match linestyle {
        "--" | "dashed" => Some((6.0, 4.0)),
        ":" | "dotted" => Some((1.0, 3.0)),
        "-." | "dashdot" => Some((6.0, 3.0)),
        _ => None,
    }
}

/// Stroke a polyline as dashes, in panel-local pixels.
fn draw_dashed<DB: DrawingBackend, C: Color>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    pts: &[(i32, i32)],
    col: C,
    width: u32,
    dash: f64,
    gap: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let mut on = true;
    let mut left = dash;
    for pair in pts.windows(2) {
        let (x0, y0) = (pair[0].0 as f64, pair[0].1 as f64);
        let (x1, y1) = (pair[1].0 as f64, pair[1].1 as f64);
        let (dx, dy) = (x1 - x0, y1 - y0);
        let len = (dx * dx + dy * dy).sqrt();
        if len <= 0.0 {
            continue;
        }
        let (ux, uy) = (dx / len, dy / len);
        let mut t = 0.0;
        while t < len {
            let seg = left.min(len - t);
            if on {
                let a = (x0 + ux * t, y0 + uy * t);
                let b = (x0 + ux * (t + seg), y0 + uy * (t + seg));
                area.draw(&PathElement::new(
                    vec![
                        (a.0.round() as i32, a.1.round() as i32),
                        (b.0.round() as i32, b.1.round() as i32),
                    ],
                    col.stroke_width(width),
                ))?;
            }
            t += seg;
            left -= seg;
            if left <= f64::EPSILON {
                on = !on;
                left = if on { dash } else { gap };
            }
        }
    }
    Ok(())
}

/// One scatter marker centred on canvas pixel `pos`, with pixel radius `r`.
fn draw_marker<DB: DrawingBackend, C: Color>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    pos: (i32, i32),
    r: f64,
    col: C,
    stroke: u32,
    marker: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (x, y) = (pos.0 - base.0, pos.1 - base.1);
    let ri = r.round().max(1.0) as i32;
    match marker {
        "s" => area.draw(&Rectangle::new(
            [(x - ri, y - ri), (x + ri, y + ri)],
            col.filled(),
        ))?,
        "^" => area.draw(&Polygon::new(
            vec![(x, y - ri), (x + ri, y + ri), (x - ri, y + ri)],
            col.filled(),
        ))?,
        "v" => area.draw(&Polygon::new(
            vec![(x, y + ri), (x + ri, y - ri), (x - ri, y - ri)],
            col.filled(),
        ))?,
        "<" => area.draw(&Polygon::new(
            vec![(x - ri, y), (x + ri, y + ri), (x + ri, y - ri)],
            col.filled(),
        ))?,
        ">" => area.draw(&Polygon::new(
            vec![(x + ri, y), (x - ri, y + ri), (x - ri, y - ri)],
            col.filled(),
        ))?,
        "D" => area.draw(&Polygon::new(
            vec![(x, y - ri), (x + ri, y), (x, y + ri), (x - ri, y)],
            col.filled(),
        ))?,
        "x" => {
            area.draw(&PathElement::new(
                vec![(x - ri, y - ri), (x + ri, y + ri)],
                col.stroke_width(stroke),
            ))?;
            area.draw(&PathElement::new(
                vec![(x - ri, y + ri), (x + ri, y - ri)],
                col.stroke_width(stroke),
            ))?;
        }
        "+" => {
            area.draw(&PathElement::new(
                vec![(x - ri, y), (x + ri, y)],
                col.stroke_width(stroke),
            ))?;
            area.draw(&PathElement::new(
                vec![(x, y - ri), (x, y + ri)],
                col.stroke_width(stroke),
            ))?;
        }
        "." => area.draw(&Circle::new((x, y), (ri / 2).max(1) as u32, col.filled()))?,
        _ => area.draw(&Circle::new((x, y), ri as u32, col.filled()))?,
    }
    Ok(())
}

fn num(v: f64) -> String {
    let s = format!("{v:.4}");
    let s = s.trim_end_matches('0').trim_end_matches('.').to_string();
    if s.is_empty() || s == "-0" {
        "0".to_string()
    } else {
        s
    }
}

/// A vertical gradient strip with min/mid/max ticks and an optional axis label.
fn draw_colorbar<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    cmap: &str,
    vmin: f64,
    vmax: f64,
    label: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (w, h) = area.dim_in_pixel();
    let (x0, x1) = (14i32, 44i32);
    let (y0, y1) = (12i32, h as i32 - 26);
    if x1 >= w as i32 || y1 - y0 < 4 {
        return Ok(());
    }
    let steps = y1 - y0;
    for i in 0..steps {
        let t = 1.0 - (i as f64 + 0.5) / steps as f64;
        let c = colormap(cmap, t);
        area.draw(&Rectangle::new(
            [(x0, y0 + i), (x1, y0 + i + 1)],
            RGBAColor(c[0], c[1], c[2], 1.0).filled(),
        ))?;
    }
    let frame = RGBColor(90, 90, 90);
    area.draw(&Rectangle::new([(x0, y0), (x1, y1)], frame.stroke_width(1)))?;
    let mid = (vmin + vmax) / 2.0;
    for (t, v) in [(0.0, vmin), (0.5, mid), (1.0, vmax)] {
        let y = (y0 as f64 + (1.0 - t) * (y1 - y0) as f64).round() as i32;
        area.draw(&PathElement::new(
            vec![(x0 - 4, y), (x0, y)],
            frame.stroke_width(1),
        ))?;
        draw_label(
            area,
            (0, 0),
            (x1 + 6, y),
            &num(v),
            RGBAColor(0, 0, 0, 1.0),
            13.0,
            "left",
            "center",
        )?;
    }
    if !label.is_empty() {
        draw_label(
            area,
            (0, 0),
            (x1 + 6, h as i32 - 6),
            label,
            RGBAColor(0, 0, 0, 1.0),
            14.0,
            "left",
            "bottom",
        )?;
    }
    Ok(())
}

/// One level of a marching-squares pass: iso-line segments in data coordinates.
fn contour_segments(x: &[f64], y: &[f64], z: &[f64], level: f64) -> Vec<((f64, f64), (f64, f64))> {
    let (rows, cols) = (y.len(), x.len());
    let mut out = Vec::new();
    if rows < 2 || cols < 2 || z.len() != rows * cols {
        return out;
    }
    let at = |i: usize, j: usize| z[i * cols + j];
    let lerp = |a: f64, b: f64, va: f64, vb: f64| {
        let d = vb - va;
        if d.abs() < f64::EPSILON {
            a
        } else {
            a + (b - a) * ((level - va) / d)
        }
    };
    for i in 0..rows - 1 {
        for j in 0..cols - 1 {
            let (z00, z01, z11, z10) = (at(i, j), at(i, j + 1), at(i + 1, j + 1), at(i + 1, j));
            let idx = (z00 > level) as u8
                | ((z01 > level) as u8) << 1
                | ((z11 > level) as u8) << 2
                | ((z10 > level) as u8) << 3;
            if idx == 0 || idx == 15 {
                continue;
            }
            let top = (lerp(x[j], x[j + 1], z00, z01), y[i]);
            let right = (x[j + 1], lerp(y[i], y[i + 1], z01, z11));
            let bottom = (lerp(x[j], x[j + 1], z10, z11), y[i + 1]);
            let left = (x[j], lerp(y[i], y[i + 1], z00, z10));
            let (a, b) = match idx {
                1 | 14 => (left, top),
                2 | 13 => (top, right),
                3 | 12 => (left, right),
                4 | 11 => (right, bottom),
                5 => (left, top),
                6 | 9 => (top, bottom),
                7 | 8 => (left, bottom),
                10 => (top, right),
                _ => continue,
            };
            out.push((a, b));
            // Saddle cells get a second leg; either diagonal split is valid.
            if idx == 5 {
                out.push((right, bottom));
            } else if idx == 10 {
                out.push((left, bottom));
            }
        }
    }
    out
}

/// Clip a triangle (x, y, value) to `lo <= value <= hi`.
fn clip_band(tri: &[(f64, f64, f64); 3], lo: f64, hi: f64) -> Vec<(f64, f64, f64)> {
    let poly = clip_value(tri.to_vec(), lo, true);
    clip_value(poly, hi, false)
}

/// One Sutherland-Hodgman pass against a level plane.
fn clip_value(poly: Vec<(f64, f64, f64)>, bound: f64, keep_above: bool) -> Vec<(f64, f64, f64)> {
    if poly.is_empty() {
        return poly;
    }
    let inside = |v: f64| if keep_above { v >= bound } else { v <= bound };
    let mut out = Vec::with_capacity(poly.len() + 2);
    for i in 0..poly.len() {
        let cur = poly[i];
        let prev = poly[(i + poly.len() - 1) % poly.len()];
        let (cin, pin) = (inside(cur.2), inside(prev.2));
        if cin != pin {
            out.push(mix_at(prev, cur, bound));
        }
        if cin {
            out.push(cur);
        }
    }
    out
}

/// Tick label for a linear axis: short, without float noise.
fn tick_label(v: f64) -> String {
    if v == 0.0 {
        return "0".to_string();
    }
    let a = v.abs();
    if a >= 1e5 || a < 1e-3 {
        format!("{v:.2e}")
    } else {
        format!("{v:.4}")
            .trim_end_matches('0')
            .trim_end_matches('.')
            .to_string()
    }
}

/// Tick label for a log coordinate: base^v written as a plain number.
fn log_label(v: f64, base: f64) -> String {
    let value = base.powf(v);
    if value >= 1e5 || value < 1e-4 {
        format!("{value:.0e}")
    } else {
        format!("{value:.4}")
            .trim_end_matches('0')
            .trim_end_matches('.')
            .to_string()
    }
}

fn mix_at(a: (f64, f64, f64), b: (f64, f64, f64), bound: f64) -> (f64, f64, f64) {
    let d = b.2 - a.2;
    let t = if d.abs() < f64::EPSILON {
        0.0
    } else {
        (bound - a.2) / d
    };
    (a.0 + (b.0 - a.0) * t, a.1 + (b.1 - a.1) * t, bound)
}

pub(crate) fn draw_panel<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    p: &Panel,
    overlays: &mut Vec<String>,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    if let Some((cmap, vmin, vmax, label)) = &p.colorbar {
        return draw_colorbar(area, cmap, *vmin, *vmax, label);
    }
    let fg = color(p.foreground.as_deref().unwrap_or("#000000"));
    let (mut x0, mut x1, mut y0, mut y1) = panel_ranges(p);
    // Log axes are laid out in log10 space: the ranges and every mapped point are
    // transformed, and the tick labels are converted back to powers of ten.
    let base = if p.log_base > 1.0 { p.log_base } else { 10.0 };
    let tx = |v: f64| {
        if p.x_log {
            v.max(f64::MIN_POSITIVE).log(base)
        } else {
            v
        }
    };
    let ty = |v: f64| {
        if p.y_log {
            v.max(f64::MIN_POSITIVE).log(base)
        } else {
            v
        }
    };
    if p.x_log {
        (x0, x1) = (tx(x0), tx(x1));
        if x1 <= x0 {
            x1 = x0 + 1.0;
        }
    }
    if p.y_log {
        (y0, y1) = (ty(y0), ty(y1));
        if y1 <= y0 {
            y1 = y0 + 1.0;
        }
    }
    // A fixed aspect shrinks the plotting box instead of bending the data limits,
    // like matplotlib's adjustable="box".
    let title_size = p.title_size.unwrap_or(18.0).max(6.0).round() as u32;
    let custom_legend = p.legend.show && p.legend.is_custom();
    let mut entries: Vec<LegendEntry> = Vec::new();
    let manual = p.ticks.xticks.is_some()
        || p.ticks.yticks.is_some()
        || p.ticks.xstyle.is_custom()
        || p.ticks.ystyle.is_custom()
        || (p.grid.show
            && (p.grid.color.is_some()
                || p.grid.linewidth.is_some()
                || p.grid.alpha.is_some()
                || p.grid.linestyle.is_some()));
    let shrunk_area;
    let mut chart = ChartBuilder::on(area)
        .caption(&p.title, ("sans-serif", title_size).into_font().color(&fg))
        .margin(10)
        .x_label_area_size(40)
        .y_label_area_size(55)
        .build_cartesian_2d(x0..x1, y0..y1)?;
    if let Some(scale) = p.aspect {
        let (pw, ph) = chart.plotting_area().dim_in_pixel();
        let ratio = (x1 - x0) / (y1 - y0) / scale;
        if pw > 8 && ph > 8 && ratio.is_finite() && ratio > 0.0 {
            let mut dw = 0i32;
            let mut dh = 0i32;
            if pw as f64 / ph as f64 > ratio {
                dw = (pw as f64 - ratio * ph as f64).round() as i32;
            } else {
                dh = (ph as f64 - pw as f64 / ratio).round() as i32;
            }
            if dw > 0 || dh > 0 {
                shrunk_area = area.margin(dh / 2, dh - dh / 2, dw / 2, dw - dw / 2);
                chart = ChartBuilder::on(&shrunk_area)
                    .caption(&p.title, ("sans-serif", title_size).into_font().color(&fg))
                    .margin(10)
                    .x_label_area_size(40)
                    .y_label_area_size(55)
                    .build_cartesian_2d(x0..x1, y0..y1)?;
            }
        }
    }
    if let Some(fc) = &p.facecolor {
        chart.plotting_area().fill(&color(fc))?;
    }
    if !p.axis_off {
        let x_fmt = move |v: &f64| {
            if manual || p.ticks.hide_xlabels {
                String::new()
            } else if p.x_log {
                log_label(*v, base)
            } else {
                tick_label(*v)
            }
        };
        let y_fmt = move |v: &f64| {
            if manual || p.ticks.hide_ylabels {
                String::new()
            } else if p.y_log {
                log_label(*v, base)
            } else {
                tick_label(*v)
            }
        };
        let label_size = p.ticks.xstyle.labelsize.max(6.0).round() as u32;
        let desc_size = p
            .xlabel_size
            .unwrap_or(10.0)
            .max(p.ylabel_size.unwrap_or(10.0))
            .max(6.0)
            .round() as u32;
        let mut mesh = chart.configure_mesh();
        if !p.grid.show {
            mesh.disable_mesh();
        } else if p.grid.color.is_some() || p.grid.linewidth.is_some() || p.grid.alpha.is_some() {
            let gc = color(p.grid.color.as_deref().unwrap_or("#b0b0b0"));
            let alpha = p.grid.alpha.unwrap_or(1.0).clamp(0.0, 1.0);
            let width = p.grid.linewidth.unwrap_or(1.0).max(1.0).round() as u32;
            let style = gc.mix(alpha).stroke_width(width);
            mesh.light_line_style(style).bold_line_style(style);
        }
        if p.grid.show {
            match p.grid.axis.as_str() {
                "x" => {
                    mesh.disable_y_mesh();
                }
                "y" => {
                    mesh.disable_x_mesh();
                }
                _ => {}
            }
        }
        if manual {
            // Manual ticks own the tick marks and gridlines; the mesh only
            // contributes the axis spines and descriptions.
            mesh.disable_mesh().set_all_tick_mark_size(0);
        }
        mesh.label_style(("sans-serif", label_size).into_font().color(&fg))
            .axis_desc_style(("sans-serif", desc_size).into_font().color(&fg))
            .axis_style(fg.stroke_width(1))
            .x_desc(&p.xlabel)
            .y_desc(&p.ylabel)
            .x_label_formatter(&x_fmt)
            .y_label_formatter(&y_fmt)
            .draw()?;
        if manual {
            draw_manual_ticks(area, &chart, p, (x0, x1, y0, y1), base)?;
        }
    }
    // Filled contours sit on the image layer, under the line series.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, z, levels, colors, cmap, filled) in &p.contours {
            if !*filled || levels.len() < 2 {
                continue;
            }
            let xs: Vec<f64> = x.as_array().iter().copied().collect();
            let ys: Vec<f64> = y.as_array().iter().copied().collect();
            let zs: Vec<f64> = z.as_array().iter().copied().collect();
            let (rows, cols) = (ys.len(), xs.len());
            if rows < 2 || cols < 2 || zs.len() != rows * cols {
                continue;
            }
            let bands = levels.len() - 1;
            for band in 0..bands {
                let (lo, hi) = (levels[band], levels[band + 1]);
                let col = if colors.is_empty() {
                    let c = colormap(cmap, (band as f64 + 0.5) / bands as f64);
                    RGBAColor(c[0], c[1], c[2], 1.0)
                } else {
                    color(&colors[band % colors.len()])
                };
                for i in 0..rows - 1 {
                    for j in 0..cols - 1 {
                        let p00 = (xs[j], ys[i], zs[i * cols + j]);
                        let p01 = (xs[j + 1], ys[i], zs[i * cols + j + 1]);
                        let p10 = (xs[j], ys[i + 1], zs[(i + 1) * cols + j]);
                        let p11 = (xs[j + 1], ys[i + 1], zs[(i + 1) * cols + j + 1]);
                        // Split each cell into two triangles: a band cut through a triangle
                        // is an exact polygon for piecewise-linear interpolation.
                        for tri in [[p00, p01, p11], [p00, p11, p10]] {
                            let poly = clip_band(&tri, lo, hi);
                            if poly.len() < 3 {
                                continue;
                            }
                            let pts: Vec<(i32, i32)> = poly
                                .iter()
                                .map(|&(px, py, _)| {
                                    let (ax, ay) = chart_area.map_coordinate(&(tx(px), ty(py)));
                                    (ax - base.0, ay - base.1)
                                })
                                .collect();
                            area.draw(&Polygon::new(pts, col.filled()))?;
                        }
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
            let (xs, ys) = (band.x.as_array(), band.y.as_array());
            if xs.len() < 3 || xs.len() != ys.len() {
                continue;
            }
            let pts: Vec<(i32, i32)> = xs
                .iter()
                .zip(ys.iter())
                .map(|(x, y)| {
                    let (px, py) = chart_area.map_coordinate(&(tx(*x), ty(*y)));
                    (px - base.0, py - base.1)
                })
                .collect();
            let col = match band.alpha {
                Some(a) => color(&band.color).mix(a.clamp(0.0, 1.0)),
                None => color(&band.color).mix(1.0),
            };
            area.draw(&Polygon::new(pts, col.filled()))?;
            if !band.label.is_empty() {
                legend_bands.push((band.label.clone(), col));
            }
        }
        for (label, col) in legend_bands {
            entries.push(LegendEntry {
                label: label.clone(),
                swatch: LegendSwatch::Rect(col),
            });
            if !custom_legend {
                let series = chart.draw_series(std::iter::once(Rectangle::new(
                    [(0.0f64, 0.0f64), (0.0f64, 0.0f64)],
                    RGBColor(0, 0, 0).mix(0.0).filled(),
                )))?;
                series.label(label.as_str()).legend(move |(x, y)| {
                    Rectangle::new([(x, y - 3), (x + 20, y + 7)], col.filled())
                });
            }
        }
    }
    // Bars: axis-aligned rectangles, above the filled contours and below lines.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        let mut legend_bars: Vec<(String, RGBAColor)> = Vec::new();
        for bars in &p.bars {
            let (l, b) = (bars.left.as_array(), bars.bottom.as_array());
            let (w, h) = (bars.width.as_array(), bars.height.as_array());
            let mut swatch: Option<RGBAColor> = None;
            for i in 0..l.len().min(b.len()).min(w.len()).min(h.len()) {
                let col = if bars.colors.is_empty() {
                    RGBAColor(31, 119, 180, 1.0)
                } else {
                    color(&bars.colors[i % bars.colors.len()])
                };
                let col = match bars.alpha {
                    Some(a) => col.mix(a.clamp(0.0, 1.0)),
                    None => col.mix(1.0),
                };
                if swatch.is_none() {
                    swatch = Some(col);
                }
                let (x0, y0) = chart_area.map_coordinate(&(tx(l[i]), ty(b[i])));
                let (x1, y1) = chart_area.map_coordinate(&(tx(l[i] + w[i]), ty(b[i] + h[i])));
                let (xl, xr) = (x0.min(x1) - base.0, x0.max(x1) - base.0);
                let (yt, yb) = (y0.min(y1) - base.1, y0.max(y1) - base.1);
                if xr <= xl || yb <= yt {
                    continue;
                }
                area.draw(&Rectangle::new([(xl, yt), (xr, yb)], col.filled()))?;
                if let Some(ec) = &bars.edgecolor {
                    let ecol = color(ec).stroke_width(1);
                    area.draw(&Rectangle::new([(xl, yt), (xr, yb)], ecol))?;
                }
            }
            if !bars.label.is_empty() {
                let cs = swatch.unwrap_or_else(|| RGBColor(31, 119, 180).mix(1.0));
                legend_bars.push((bars.label.clone(), cs));
            }
        }
        for (label, cs) in legend_bars {
            entries.push(LegendEntry {
                label: label.clone(),
                swatch: LegendSwatch::Rect(cs),
            });
            if !custom_legend {
                let series = chart.draw_series(std::iter::once(Rectangle::new(
                    [(0.0f64, 0.0f64), (0.0f64, 0.0f64)],
                    RGBColor(0, 0, 0).mix(0.0).filled(),
                )))?;
                series.label(label.as_str()).legend(move |(x, y)| {
                    Rectangle::new([(x, y - 3), (x + 20, y + 7)], cs.filled())
                });
            }
        }
    }
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
        let width = s.linewidth.max(1.0).round() as u32;
        let col = match s.alpha {
            Some(a) => color(&s.color).mix(a.clamp(0.0, 1.0)),
            None => color(&s.color).mix(1.0),
        };
        if matches!(s.linestyle.as_str(), ":" | "--" | "-.") {
            let (dash, gap) = match s.linestyle.as_str() {
                ":" => (2.0, 4.0),
                "--" => (9.0, 5.0),
                _ => (7.0, 3.0),
            };
            let px: Vec<(i32, i32)> = {
                let chart_area = chart.plotting_area();
                pts.iter()
                    .map(|p| {
                        let (x, y) = chart_area.map_coordinate(p);
                        (x - base.0, y - base.1)
                    })
                    .collect()
            };
            draw_dashed(area, &px, col, width, dash, gap)?;
            if !s.label.is_empty() {
                entries.push(LegendEntry {
                    label: s.label.clone(),
                    swatch: LegendSwatch::Line(col, width),
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
            let series = chart.draw_series(LineSeries::new(pts, col.stroke_width(width)))?;
            if !s.label.is_empty() {
                entries.push(LegendEntry {
                    label: s.label.clone(),
                    swatch: LegendSwatch::Line(col, width),
                });
                if !custom_legend {
                    series.label(s.label.as_str()).legend(move |(x, y)| {
                        PathElement::new(vec![(x, y), (x + 20, y)], col.stroke_width(width))
                    });
                }
            }
        }
        if !s.marker.is_empty() && s.markersize > 0.0 {
            let stroked = matches!(s.marker.as_str(), "x" | "+");
            let name = if stroked {
                s.mec.as_deref().unwrap_or(&s.color)
            } else {
                s.mfc.as_deref().unwrap_or(&s.color)
            };
            let mc = match s.alpha {
                Some(a) => color(name).mix(a.clamp(0.0, 1.0)),
                None => color(name).mix(1.0),
            };
            let r = (s.markersize / 2.0 * 1.39).max(1.0);
            let stroke = s.mew.max(1.0).round() as u32;
            let chart_area = chart.plotting_area();
            for (xv, yv) in xs.iter().zip(ys.iter()) {
                let (px, py) = chart_area.map_coordinate(&(tx(*xv), ty(*yv)));
                draw_marker(area, base, (px, py), r, mc, stroke, &s.marker)?;
            }
        }
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
                let r = (sz.sqrt() / 2.0 * 1.39).max(1.0);
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
                draw_marker(area, base, (cx, cy), r, col.mix(alpha), 2, &sc.marker)?;
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
    // Iso-lines are stroked above the series, one segment per marching-squares cell.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, z, levels, colors, cmap, filled) in &p.contours {
            if *filled || levels.is_empty() {
                continue;
            }
            let xs: Vec<f64> = x.as_array().iter().copied().collect();
            let ys: Vec<f64> = y.as_array().iter().copied().collect();
            let zs: Vec<f64> = z.as_array().iter().copied().collect();
            let (rows, cols) = (ys.len(), xs.len());
            if rows < 2 || cols < 2 || zs.len() != rows * cols {
                continue;
            }
            let n = levels.len() as f64;
            for (li, level) in levels.iter().enumerate() {
                let col = if colors.is_empty() {
                    let t = if n > 1.0 { li as f64 / (n - 1.0) } else { 0.5 };
                    let c = colormap(cmap, t);
                    RGBAColor(c[0], c[1], c[2], 1.0)
                } else {
                    color(&colors[li % colors.len()])
                };
                for (a, b) in contour_segments(&xs, &ys, &zs, *level) {
                    let (ax, ay) = chart_area.map_coordinate(&(tx(a.0), ty(a.1)));
                    let (bx, by) = chart_area.map_coordinate(&(tx(b.0), ty(b.1)));
                    area.draw(&PathElement::new(
                        vec![(ax - base.0, ay - base.1), (bx - base.0, by - base.1)],
                        col.stroke_width(2),
                    ))?;
                }
            }
        }
    }
    {
        let chart_area = chart.plotting_area();
        // map_coordinate yields canvas-absolute pixels; the panel's own area re-applies
        // its origin, so anything drawn on it shifts back to cell-local pixels.
        let base = area.get_base_pixel();
        for (x, y, s, c, size, ha, va) in &p.texts {
            let pos = chart_area.map_coordinate(&(tx(*x), ty(*y)));
            draw_label(area, base, pos, s, color(c), *size, ha, va)?;
        }
        for (text, xy, xytext, c, size) in &p.annotations {
            let target = chart_area.map_coordinate(&(tx(xy.0), ty(xy.1)));
            let anchor = match xytext {
                Some(t) => chart_area.map_coordinate(&(tx(t.0), ty(t.1))),
                None => target,
            };
            if xytext.is_some() {
                draw_arrow(area, base, anchor, target, color(c))?;
            }
            draw_label(
                area,
                base,
                anchor,
                text,
                color(c),
                *size,
                "left",
                "baseline",
            )?;
        }
        for item in &p.images {
            let (l, r, b, t) = item.4;
            let (ax, ay) = chart_area.map_coordinate(&(tx(l), ty(t)));
            let (zx, zy) = chart_area.map_coordinate(&(tx(r), ty(b)));
            let (iw, ih) = ((ax - zx).abs(), (ay - zy).abs());
            if iw == 0 || ih == 0 {
                continue;
            }
            // Embedded into the root SVG, so this stays in canvas pixels.
            overlays.push(format!(
                "<image x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" \
                 preserveAspectRatio=\"none\" href=\"data:image/png;base64,{}\"/>",
                ax.min(zx),
                ay.min(zy),
                iw,
                ih,
                base64(&image_png(item)?)
            ));
        }
    }
    if p.legend.show && custom_legend {
        let base = area.get_base_pixel();
        let pa = chart.plotting_area();
        let tl = pa.map_coordinate(&(x0, y1));
        let br = pa.map_coordinate(&(x1, y0));
        draw_legend(
            area,
            (tl.0 - base.0, tl.1 - base.1, br.0 - base.0, br.1 - base.1),
            &entries,
            &p.legend,
            fg,
        )?;
    } else if p.legend.show {
        let loc = p.legend.loc.as_str();
        let position = match loc {
            "upper left" => SeriesLabelPosition::UpperLeft,
            "upper center" => SeriesLabelPosition::UpperMiddle,
            "lower left" => SeriesLabelPosition::LowerLeft,
            "lower center" => SeriesLabelPosition::LowerMiddle,
            "lower right" => SeriesLabelPosition::LowerRight,
            "center left" => SeriesLabelPosition::MiddleLeft,
            "center right" | "right" => SeriesLabelPosition::MiddleRight,
            "center" => SeriesLabelPosition::MiddleRight,
            _ => SeriesLabelPosition::UpperRight,
        };
        let mut labels = chart.configure_series_labels();
        labels
            .position(position)
            .label_font(("sans-serif", p.legend.fontsize.max(6.0).round() as u32));
        if p.legend.frameon {
            labels.background_style(WHITE.mix(0.8)).border_style(BLACK);
        } else {
            labels
                .background_style(TRANSPARENT)
                .border_style(TRANSPARENT);
        }
        labels.draw()?;
    }
    Ok(())
}
