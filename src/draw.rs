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
    DrawStyle, LegendEntry, LegendSwatch, Marker, OwnedArray1, Panel, PngCompression, QuiverUnits,
    TextBBox,
};

mod axes;
mod colorbar;
mod contour;
mod image;
mod legend;
mod markers;
mod series;
mod ticks;

/// Plotters' SVG backend divides text sizes by 1.24; matplotlib sizes are
/// points at `dpi`. Convert once so both land on the same pixel size.
pub(crate) fn text_px(size: f64, dpi: f64) -> f64 {
    size * dpi.max(1.0) / 72.0 * 1.24
}

/// Draw one label. Alignment is approximated: the backend only has a top-left
/// anchor, so the text width is estimated from the glyph count.
#[allow(clippy::too_many_arguments)]
pub(crate) fn draw_label<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    pos: (i32, i32),
    s: &str,
    col: RGBAColor,
    size: f64,
    ha: &str,
    va: &str,
    bbox: Option<&TextBBox>,
    rotation: f64,
    line_scale: f64,
    family: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let fs = size.max(1.0);
    // SVG collapses runs of ordinary spaces. Text blocks with indentation or
    // tabs use non-breaking spaces so their columns survive resvg and PDF.
    let keep_spacing = s
        .lines()
        .any(|line| line.starts_with(' ') || line.starts_with('\t'))
        || s.contains('\t');
    let expanded: String;
    let text = if keep_spacing {
        expanded = s.replace('\t', "    ").replace(' ', "\u{00A0}");
        expanded.as_str()
    } else {
        s
    };
    let lines: Vec<&str> = text
        .split('\n')
        .map(|line| line.trim_end_matches('\r'))
        .collect();
    let w = lines
        .iter()
        .map(|line| crate::fonts::text_width(line, fs))
        .fold(0.0, f64::max);
    let dx = match ha {
        "center" => -w / 2.0,
        "right" => -w,
        _ => 0.0,
    };
    let line_h = fs * 1.2 * line_scale.clamp(0.1, 4.0);
    let dy = if lines.len() == 1 {
        match va {
            "top" => 0.0,
            "center" => -fs / 2.0,
            "bottom" => -fs,
            _ => -fs * 0.8, // baseline
        }
    } else {
        match va {
            "top" => 0.0,
            "center" => -line_h * lines.len() as f64 / 2.0,
            "bottom" => -line_h * lines.len() as f64,
            _ => -fs * 0.8,
        }
    };
    if let Some(bb) = bbox {
        let pad = bb.pad.max(0.0) * fs;
        let left = pos.0 as f64 - base.0 as f64 + dx - pad;
        let top = pos.1 as f64 - base.1 as f64 + dy - fs * 0.8 - pad;
        let right = pos.0 as f64 - base.0 as f64 + dx + w + pad;
        let bottom = pos.1 as f64 - base.1 as f64
            + dy
            + lines.len().saturating_sub(1) as f64 * line_h
            + fs * 0.2
            + pad;
        let face = bb
            .facecolor
            .map(|c| c.rgba())
            .unwrap_or(RGBAColor(0, 0, 0, 0.0));
        let edge = bb
            .edgecolor
            .map(|c| c.rgba())
            .unwrap_or(RGBAColor(0, 0, 0, 0.0));
        let alpha = bb.alpha.clamp(0.0, 1.0);
        let fill = RGBAColor(face.0, face.1, face.2, face.3 * alpha);
        let border = RGBAColor(edge.0, edge.1, edge.2, edge.3 * alpha);
        let radius = if bb.rounded {
            legend::legend_corner_radius(fs)
        } else {
            0.0
        };
        legend::draw_rounded_frame(
            area,
            (left, top, right - left, bottom - top),
            fill,
            border,
            radius,
        )?;
    }
    let deg = rotation.rem_euclid(360.0);
    let mut style = (family, fs.round() as u32).into_font().color(&col);
    if (45.0..135.0).contains(&deg) {
        style = style.transform(FontTransform::Rotate90);
    } else if (135.0..225.0).contains(&deg) {
        style = style.transform(FontTransform::Rotate180);
    } else if (225.0..315.0).contains(&deg) {
        style = style.transform(FontTransform::Rotate270);
    }
    for (index, line) in lines.iter().enumerate() {
        if line.is_empty() {
            continue;
        }
        area.draw(&Text::new(
            *line,
            (
                pos.0 - base.0 + dx as i32,
                pos.1 - base.1 + (dy + index as f64 * line_h) as i32,
            ),
            style.clone(),
        ))?;
    }
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

/// Filled quiver arrow in canvas pixels: a shaft of `width_px` plus a
/// triangular head, following Matplotlib's `_h_arrows` geometry.
#[allow(clippy::too_many_arguments)]
fn draw_quiver_arrow<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    from: (f64, f64),
    to: (f64, f64),
    col: RGBAColor,
    width_px: f64,
    headwidth: f64,
    headlength: f64,
    headaxislength: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (sx, sy) = (from.0 - base.0 as f64, from.1 - base.1 as f64);
    let (ex, ey) = (to.0 - base.0 as f64, to.1 - base.1 as f64);
    let (dx, dy) = (ex - sx, ey - sy);
    let len = dx.hypot(dy);
    let w = width_px.max(1.0);
    if len < 1.0 {
        area.draw(&Circle::new(
            (sx as i32, sy as i32),
            (w * 0.5).max(1.0) as u32,
            col.filled(),
        ))?;
        return Ok(());
    }
    let (ux, uy) = (dx / len, dy / len);
    let (px, py) = (-uy, ux);
    let half = (w * 0.5).max(0.5);
    let hl = (headlength * w).clamp(1.0, len);
    let hal = (headaxislength * w).clamp(0.0, len);
    let hw = (0.5 * headwidth * w).max(half);
    let at = |t: f64, off: f64| {
        (
            (sx + ux * t + px * off).round() as i32,
            (sy + uy * t + py * off).round() as i32,
        )
    };
    area.draw(&Polygon::new(
        vec![
            at(0.0, half),
            at(len - hal, half),
            at(len - hl, hw),
            at(len, 0.0),
            at(len - hl, -hw),
            at(len - hal, -half),
            at(0.0, -half),
        ],
        col.filled(),
    ))?;
    Ok(())
}

/// Symmetric-log transform used by `symlog` axes: linear near zero, then
/// logarithmic on both sides of `±linthresh`.
fn symlog(value: f64, linthresh: f64) -> f64 {
    let l = if linthresh > 0.0 { linthresh } else { 1.0 };
    value.signum() * l * (1.0 + value.abs() / l).ln()
}

/// Logit transform for probability axes; values are clamped away from the
/// singular endpoints so zero and one remain drawable.
fn logit(value: f64) -> f64 {
    let p = value.clamp(1e-10, 1.0 - 1e-10);
    (p / (1.0 - p)).ln()
}

/// Asinh transform: linear near zero and logarithmic for large magnitudes.
fn asinh_scale(value: f64, linear_width: f64) -> f64 {
    let w = if linear_width > 0.0 {
        linear_width
    } else {
        1.0
    };
    w * (value / w).asinh()
}

fn asinh_inverse(value: f64, linear_width: f64) -> f64 {
    let w = if linear_width > 0.0 {
        linear_width
    } else {
        1.0
    };
    w * (value / w).sinh()
}

fn rotated_style<'a>(
    size: f64,
    col: RGBAColor,
    rotation: f64,
    dpi: f64,
    family: &'a str,
) -> TextStyle<'a> {
    let style = (family, text_px(size.max(6.0), dpi).round() as u32)
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

/// Map a matplotlib linestyle name onto a dash/gap length in pixels.
/// Stroke a polyline as dashes, in panel-local pixels.
/// A corner where matplotlib's round join is visibly different from the
/// backend's union of butt-ended segments. Pixel-quantised dense data has many
/// apparent corners of a pixel or two; those are covered by the stroke itself
/// and must not split the path, or smooth series cost a path per sample.
fn sharp_corner(a: (i32, i32), b: (i32, i32), c: (i32, i32), width: u32) -> bool {
    let half = width as f64 / 2.0;
    if half < 2.0 {
        // Below a few pixels the join geometry is sub-pixel either way.
        return false;
    }
    let d1 = ((b.0 - a.0) as f64, (b.1 - a.1) as f64);
    let d2 = ((c.0 - b.0) as f64, (c.1 - b.1) as f64);
    let (l1, l2) = (
        (d1.0 * d1.0 + d1.1 * d1.1).sqrt(),
        (d2.0 * d2.0 + d2.1 * d2.1).sqrt(),
    );
    if l1 < half || l2 < half {
        return false;
    }
    let cross = d1.0 * d2.1 - d1.1 * d2.0;
    cross.abs() / (l1 * l2) >= 0.2
}

fn has_sharp_join(pts: &[(i32, i32)], width: u32) -> bool {
    pts.windows(3)
        .any(|w| sharp_corner(w[0], w[1], w[2], width))
}

/// matplotlib's default `solid_capstyle` is `projecting`: the stroke runs half a
/// line width past each endpoint. The backends end paths with a butt cap, so add
/// the missing half-square at the two ends of the line.
fn draw_projected_caps<DB: DrawingBackend, C: Color + Copy>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    pts: &[(i32, i32)],
    col: C,
    width: u32,
    caps: (bool, bool),
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    if pts.len() < 2 || width == 0 {
        return Ok(());
    }
    let half = width as f64 / 2.0;
    let last = pts.len() - 1;
    let ends = [(pts[0], pts[1]), (pts[last], pts[last - 1])];
    for ((end, inward), wanted) in ends.into_iter().zip([caps.0, caps.1]) {
        if !wanted {
            continue;
        }
        let (dx, dy) = ((end.0 - inward.0) as f64, (end.1 - inward.1) as f64);
        let len = (dx * dx + dy * dy).sqrt();
        if !len.is_finite() || len <= 0.0 {
            continue;
        }
        let tip = (
            (end.0 as f64 + dx / len * half).round() as i32,
            (end.1 as f64 + dy / len * half).round() as i32,
        );
        area.draw(&PathElement::new(vec![end, tip], col.stroke_width(width)))?;
    }
    Ok(())
}

/// Clip one pixel-space segment to `(xmin, xmax, ymin, ymax)` with Liang–Barsky,
/// so a line that leaves the axes is cut at the spine instead of drawn over the
/// labels and the neighbouring panels.
fn clip_segment(
    a: (i32, i32),
    b: (i32, i32),
    rect: (f64, f64, f64, f64),
) -> Option<((i32, i32), (i32, i32))> {
    let (xmin, xmax, ymin, ymax) = rect;
    let (ax, ay) = (a.0 as f64, a.1 as f64);
    let (dx, dy) = (b.0 as f64 - ax, b.1 as f64 - ay);
    let (mut t0, mut t1) = (0.0_f64, 1.0_f64);
    for (p, q) in [
        (-dx, ax - xmin),
        (dx, xmax - ax),
        (-dy, ay - ymin),
        (dy, ymax - ay),
    ] {
        if p == 0.0 {
            if q < 0.0 {
                return None;
            }
            continue;
        }
        let r = q / p;
        if p < 0.0 {
            if r > t1 {
                return None;
            }
            t0 = t0.max(r);
        } else {
            if r < t0 {
                return None;
            }
            t1 = t1.min(r);
        }
    }
    let at = |t: f64| {
        let x = (ax + dx * t).round() as i32;
        let y = (ay + dy * t).round() as i32;
        (
            x.clamp(xmin.round() as i32, xmax.round() as i32),
            y.clamp(ymin.round() as i32, ymax.round() as i32),
        )
    };
    Some((at(t0), at(t1)))
}

/// Split a polyline into the runs that stay inside the axes rectangle. An
/// unclipped polyline comes back as one run, unchanged.
fn clip_polyline(pts: &[(i32, i32)], rect: (f64, f64, f64, f64)) -> Vec<Vec<(i32, i32)>> {
    let mut runs: Vec<Vec<(i32, i32)>> = Vec::new();
    let mut run: Vec<(i32, i32)> = Vec::new();
    for pair in pts.windows(2) {
        match clip_segment(pair[0], pair[1], rect) {
            Some((start, end)) => {
                if run.last() != Some(&start) {
                    if run.len() >= 2 {
                        runs.push(std::mem::take(&mut run));
                    } else {
                        run.clear();
                    }
                    run.push(start);
                }
                run.push(end);
            }
            None => {
                if run.len() >= 2 {
                    runs.push(std::mem::take(&mut run));
                } else {
                    run.clear();
                }
            }
        }
    }
    if run.len() >= 2 {
        runs.push(run);
    }
    runs
}

/// Finish and draw one run of a polyline. The backend already gives every path
/// matplotlib's default `projecting` cap (half a line width past the end), so a
/// run trimmed by that much stops exactly at the point it was trimmed to.
fn stroke_run<DB: DrawingBackend, C: Color + Copy>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    run: &mut Vec<(i32, i32)>,
    col: C,
    width: u32,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let path = std::mem::take(run);
    if path.len() >= 2 {
        area.draw(&PathElement::new(path, col.stroke_width(width)))?;
    }
    Ok(())
}

/// Draw a solid polyline with matplotlib's `solid_joinstyle="round"`: split the
/// path at sharp corners, fill each corner with a disc of the line radius, and
/// trim the split ends so no backend cap overshoots the corner.
fn draw_solid_polyline<DB: DrawingBackend, C: Color + Copy>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    pts: &[(i32, i32)],
    col: C,
    width: u32,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let radius = ((width as f64 / 2.0).max(1.0)) as u32;
    let mut run: Vec<(i32, i32)> = vec![pts[0]];
    for i in 1..pts.len() {
        let at_end = i == pts.len() - 1;
        if !at_end && sharp_corner(pts[i - 1], pts[i], pts[i + 1], width) {
            if run.last() != Some(&pts[i]) {
                run.push(pts[i]);
            }
            stroke_run(area, &mut run, col, width)?;
            area.draw(&Circle::new(pts[i], radius, col.filled()))?;
            run.push(pts[i]);
        } else {
            run.push(pts[i]);
        }
    }
    stroke_run(area, &mut run, col, width)
}

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
                // matplotlib's dash join is round: a dash that runs through a
                // polyline vertex gets a disc there.
                if seg >= len - t - 1e-9 && left - seg > 1e-9 {
                    let vertex = (x1.round() as i32, y1.round() as i32);
                    let radius = ((width as f64 / 2.0).max(1.0)) as u32;
                    area.draw(&Circle::new(vertex, radius, col.filled()))?;
                }
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

/// Collapse runs of points that share one pixel column to their first, lowest,
/// highest and last points, in path order. The stroke inside a column spans
/// [min, max] and enters and leaves at first/last, so the drawn path is
/// visually unchanged while dense series shrink to at most four points per
/// column, whatever their noise. Cost is O(n); the `tolerance` argument of the
/// old greedy scheme is gone because it kept every point of a noisy series.
fn simplify_polyline(
    n: usize,
    point: impl Fn(usize) -> (f64, f64),
    map: impl Fn(&(f64, f64)) -> (f64, f64),
) -> Vec<(f64, f64)> {
    if n < 3 {
        return (0..n).map(point).collect();
    }
    let mut out = Vec::new();
    // Indices of the current column's first, min-y, max-y and last points.
    let mut col: Option<(f64, [usize; 4], f64, f64)> = None;
    fn flush(out: &mut Vec<(f64, f64)>, point: &impl Fn(usize) -> (f64, f64), idx: [usize; 4]) {
        let mut idx = idx;
        idx.sort_unstable();
        let mut prev = usize::MAX;
        for i in idx {
            if i != prev {
                out.push(point(i));
                prev = i;
            }
        }
    }
    for i in 0..n {
        let p = point(i);
        let (x, y) = map(&p);
        if !x.is_finite() || !y.is_finite() {
            // Keep non-finite points so the undrawn gaps stay where they were.
            if let Some((_, idx, _, _)) = col.take() {
                flush(&mut out, &point, idx);
            }
            out.push(p);
            continue;
        }
        let column = x.floor();
        match &mut col {
            Some((c, idx, lo, hi)) if *c == column => {
                if y < *lo {
                    *lo = y;
                    idx[1] = i;
                }
                if y > *hi {
                    *hi = y;
                    idx[2] = i;
                }
                idx[3] = i;
            }
            _ => {
                if let Some((_, idx, _, _)) = col.take() {
                    flush(&mut out, &point, idx);
                }
                col = Some((column, [i; 4], y, y));
            }
        }
    }
    if let Some((_, idx, _, _)) = col {
        flush(&mut out, &point, idx);
    }
    out
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
                    bars.colors[i % bars.colors.len()].rgba()
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
                if let Some(edges) = &bars.edgecolor {
                    if let Some(ec) = edges.get(i % edges.len().max(1)) {
                        let ecol = ec.rgba().stroke_width(1);
                        area.draw(&Rectangle::new([(xl, yt), (xr, yb)], ecol))?;
                    }
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
        }
    }
    // Patches and collections registered through add_patch/add_collection.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        let dense_offsets = raster_scatter
            && p.collections
                .iter()
                .map(|coll| coll.points.len() / 2)
                .sum::<usize>()
                >= 4096;
        let mut collection_layer = if dense_offsets {
            let (w, h) = area.dim_in_pixel();
            tiny_skia::Pixmap::new(w.max(1), h.max(1))
        } else {
            None
        };
        for patch in &p.patches {
            let alpha = patch.alpha.clamp(0.0, 1.0);
            let face = patch.facecolor.map(|c| c.rgba()).filter(|c| c.3 > 0.0);
            let fill = face.map(|c| c.mix(alpha));
            let stroke = patch
                .edgecolor
                .map(|c| c.rgba())
                .filter(|c| c.3 > 0.0)
                .map(|c| {
                    c.mix(alpha)
                        .stroke_width(patch.linewidth.max(1.0).round() as u32)
                });
            if !patch.label.is_empty() {
                entries.push(LegendEntry {
                    label: patch.label.clone(),
                    swatch: LegendSwatch::Rect(face.unwrap_or(RGBAColor(31, 119, 180, 1.0))),
                });
            }
            let map = |x: f64, y: f64| {
                let (px, py) = chart_area.map_coordinate(&(tx(x), ty(y)));
                (px - base.0, py - base.1)
            };
            if !patch.gid.is_empty() {
                draw_gid_marker(area, &patch.gid, true)?;
            }
            'patch: {
                match patch.kind.as_str() {
                    "rect" => {
                        let (ax0, ay0) = map(patch.x, patch.y);
                        let (ax1, ay1) = map(patch.x + patch.width, patch.y + patch.height);
                        let (xl, xr) = (ax0.min(ax1), ax0.max(ax1));
                        let (yt, yb) = (ay0.min(ay1), ay0.max(ay1));
                        if xr <= xl || yb <= yt {
                            break 'patch;
                        }
                        let rect = [(xl, yt), (xr, yb)];
                        if let Some(c) = fill {
                            area.draw(&Rectangle::new(rect, c.filled()))?;
                        }
                        if let Some(c) = stroke {
                            area.draw(&Rectangle::new(rect, c))?;
                        }
                    }
                    "circle" => {
                        let (cx, cy) = map(patch.x, patch.y);
                        let (rxp, _) = map(patch.x + patch.width, patch.y);
                        let (_, ryp) = map(patch.x, patch.y + patch.width);
                        let (rx, ry) = ((rxp - cx).abs() as f64, (ryp - cy).abs() as f64);
                        let pts: Vec<(i32, i32)> = (0..48)
                            .map(|i| {
                                let t = i as f64 / 48.0 * std::f64::consts::TAU;
                                (
                                    cx + (rx * t.cos()).round() as i32,
                                    cy + (ry * t.sin()).round() as i32,
                                )
                            })
                            .collect();
                        if let Some(c) = fill {
                            area.draw(&Polygon::new(pts.clone(), c.filled()))?;
                        }
                        if let Some(c) = stroke {
                            let mut outline = pts.clone();
                            outline.push(pts[0]);
                            area.draw(&PathElement::new(outline, c))?;
                        }
                    }
                    _ => {
                        if patch.points.len() < 4 {
                            break 'patch;
                        }
                        let pts: Vec<(i32, i32)> = patch
                            .points
                            .as_chunks::<2>()
                            .0
                            .iter()
                            .map(|pair| map(pair[0], pair[1]))
                            .collect();
                        if let Some(c) = fill {
                            if pts.len() >= 3 {
                                area.draw(&Polygon::new(pts.clone(), c.filled()))?;
                            }
                        }
                        if let Some(c) = stroke {
                            let mut outline = pts.clone();
                            if let Some(&first) = pts.first() {
                                outline.push(first);
                            }
                            if outline.len() >= 2 {
                                area.draw(&PathElement::new(outline, c))?;
                            }
                        }
                    }
                }
            }
            if !patch.gid.is_empty() {
                draw_gid_marker(area, &patch.gid, false)?;
            }
        }
        for coll in &p.collections {
            let alpha = coll.alpha.clamp(0.0, 1.0);
            let marker = if coll.marker.is_none() {
                Marker::Circle
            } else {
                coll.marker
            };
            if !coll.label.is_empty() {
                let icon = coll
                    .colors
                    .first()
                    .map(|c| c.rgba())
                    .unwrap_or(RGBAColor(31, 119, 180, 1.0));
                entries.push(LegendEntry {
                    label: coll.label.clone(),
                    swatch: LegendSwatch::Circle(icon.mix(alpha)),
                });
            }
            for i in 0..coll.points.len() / 2 {
                let (x, y) = (coll.points[i * 2], coll.points[i * 2 + 1]);
                if !x.is_finite() || !y.is_finite() {
                    continue;
                }
                let (px, py) = chart_area.map_coordinate(&(tx(x), ty(y)));
                let size = coll
                    .sizes
                    .get(i)
                    .or_else(|| coll.sizes.first())
                    .copied()
                    .unwrap_or(36.0)
                    .max(0.0);
                let r = markers::marker_radius(size);
                let col = if coll.colors.is_empty() {
                    RGBAColor(31, 119, 180, 1.0)
                } else {
                    coll.colors[i % coll.colors.len()].rgba()
                };
                if let Some(layer) = collection_layer.as_mut() {
                    markers::draw_marker_raster(
                        layer,
                        base,
                        (px, py),
                        r,
                        col.mix(alpha),
                        col.mix(alpha),
                        1,
                        marker,
                    );
                } else {
                    markers::draw_marker(
                        area,
                        base,
                        (px, py),
                        r,
                        col.mix(alpha),
                        col.mix(alpha),
                        1,
                        marker,
                    )?;
                }
            }
            for (i, seg) in coll.segments.iter().enumerate() {
                if seg.len() < 4 {
                    continue;
                }
                let pts: Vec<(i32, i32)> = seg
                    .as_chunks::<2>()
                    .0
                    .iter()
                    .map(|pair| {
                        let (px, py) = chart_area.map_coordinate(&(tx(pair[0]), ty(pair[1])));
                        (px - base.0, py - base.1)
                    })
                    .collect();
                let col = if coll.colors.is_empty() {
                    RGBAColor(31, 119, 180, 1.0)
                } else {
                    coll.colors[i % coll.colors.len()].rgba()
                };
                area.draw(&PathElement::new(
                    pts,
                    col.mix(alpha)
                        .stroke_width(coll.linewidth.max(1.0).round() as u32),
                ))?;
            }
        }
        if let Some(layer) = collection_layer {
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
    }
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
    // Quiver arrows sit above the data and below the text layer. Matplotlib
    // sizes them from the finished axes box, so `scale` and `units` are applied
    // here, in pixels, rather than on the data values in Python.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        let (pw, ph) = chart_area.dim_in_pixel();
        let (pw, ph) = (pw as f64, ph as f64);
        let x_span = (x1 - x0).abs().max(f64::MIN_POSITIVE);
        let y_span = (y1 - y0).abs().max(f64::MIN_POSITIVE);
        for arrow in &p.arrows {
            let (axs, ays) = (arrow.x.as_array(), arrow.y.as_array());
            let (aus, avs) = (arrow.u.as_array(), arrow.v.as_array());
            let n = axs.len().min(ays.len()).min(aus.len()).min(avs.len());
            let amean = if n == 0 {
                0.0
            } else {
                (0..n).map(|i| aus[i].hypot(avs[i])).sum::<f64>() / n as f64
            };
            let sn = (n as f64).sqrt().clamp(8.0, 25.0);
            let dots_per_unit = |unit: QuiverUnits| -> f64 {
                match unit {
                    QuiverUnits::Height => ph,
                    QuiverUnits::Dots => 1.0,
                    QuiverUnits::Inches => dpi,
                    QuiverUnits::X => pw / x_span,
                    QuiverUnits::Y => ph / y_span,
                    QuiverUnits::Xy => pw.hypot(ph) / x_span.hypot(y_span),
                    QuiverUnits::Width => pw,
                }
            };
            let dx_trans = dots_per_unit(arrow.units).max(f64::MIN_POSITIVE);
            let span = pw / dx_trans;
            let width_units = arrow.width.unwrap_or(0.06 * span / sn);
            let widthu_per_lenu = match arrow.scale_units {
                Some(unit) => dots_per_unit(unit) / dx_trans,
                None => 1.0,
            };
            let scale = match arrow.scale {
                Some(s) => s,
                None => 1.8 * amean * sn / span * widthu_per_lenu,
            };
            let scale = if scale > 0.0 { scale } else { 1.0 };
            let width_px = (width_units * dx_trans).max(1.0);
            for i in 0..n {
                let (sx, sy) = chart_area.map_coordinate(&(tx(axs[i]), ty(ays[i])));
                let mag = aus[i].hypot(avs[i]);
                let px_len = mag * widthu_per_lenu * dx_trans / scale;
                let (dir_x, dir_y) = if arrow.angles == "uv" {
                    (aus[i], -avs[i])
                } else {
                    (aus[i] * pw / x_span, -avs[i] * ph / y_span)
                };
                let dir_len = dir_x.hypot(dir_y);
                let (ux, uy) = if dir_len > 1e-12 {
                    (dir_x / dir_len, dir_y / dir_len)
                } else {
                    (1.0, 0.0)
                };
                let shift = match arrow.pivot.as_str() {
                    "middle" => 0.5 * px_len,
                    "tip" => px_len,
                    _ => 0.0,
                };
                let start = (sx as f64 - ux * shift, sy as f64 - uy * shift);
                let end = (start.0 + ux * px_len, start.1 + uy * px_len);
                let col = if arrow.colors.is_empty() {
                    RGBAColor(31, 119, 180, 1.0)
                } else {
                    arrow.colors[i % arrow.colors.len()].rgba()
                };
                draw_quiver_arrow(
                    area,
                    base,
                    start,
                    end,
                    col,
                    width_px,
                    arrow.headwidth.max(1.0),
                    arrow.headlength.max(1.0),
                    arrow.headaxislength.max(0.0),
                )?;
            }
        }
    }
    {
        let chart_area = chart.plotting_area();
        // map_coordinate yields canvas-absolute pixels; the panel's own area re-applies
        // its origin, so anything drawn on it shifts back to cell-local pixels.
        let base = area.get_base_pixel();
        for (x, y, s, c, size, ha, va, bbox, rotation, family, offset) in &p.texts {
            let mapped = chart_area.map_coordinate(&(tx(*x), ty(*y)));
            // Offsets are points, positive up, like Matplotlib's text offsets.
            let pos = (
                mapped.0 + (offset.0 * dpi / 72.0).round() as i32,
                mapped.1 - (offset.1 * dpi / 72.0).round() as i32,
            );
            let font = if family.is_empty() {
                p.font_family.as_str()
            } else {
                family.as_str()
            };
            draw_label(
                area,
                base,
                pos,
                s,
                c.rgba(),
                text_px(*size, dpi),
                ha,
                va,
                bbox.as_ref(),
                *rotation,
                line_scale,
                font,
            )?;
        }
        for (text, xy, xytext, c, size, family) in &p.annotations {
            let target = chart_area.map_coordinate(&(tx(xy.0), ty(xy.1)));
            let anchor = match xytext {
                Some(t) => chart_area.map_coordinate(&(tx(t.0), ty(t.1))),
                None => target,
            };
            if xytext.is_some() {
                draw_arrow(area, base, anchor, target, c.rgba())?;
            }
            draw_label(
                area,
                base,
                anchor,
                text,
                c.rgba(),
                text_px(*size, dpi),
                "left",
                "baseline",
                None,
                0.0,
                line_scale,
                if family.is_empty() {
                    p.font_family.as_str()
                } else {
                    family.as_str()
                },
            )?;
        }
        image::draw_panel_images(area, &chart, p, tx, ty, base, draw_images, overlays)?;
    }
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

#[cfg(test)]
mod scale_tests {
    use super::{asinh_inverse, asinh_scale, logit};

    #[test]
    fn asinh_is_linear_near_zero_and_inverts() {
        assert!((asinh_scale(0.0, 2.0)).abs() < 1e-12);
        assert!((asinh_scale(1.0, 1.0) - (1.0_f64).asinh()).abs() < 1e-12);
        assert!((asinh_inverse(asinh_scale(12.0, 0.5), 0.5) - 12.0).abs() < 1e-9);
    }

    #[test]
    fn logit_maps_probabilities_and_clamps_endpoints() {
        assert!((logit(0.5) - 0.0).abs() < 1e-12);
        assert!((logit(0.75) - 3.0_f64.ln()).abs() < 1e-12);
        assert!(logit(0.0).is_finite());
        assert!(logit(1.0).is_finite());
    }
}

#[cfg(test)]
mod clip_tests {
    use super::{clip_polyline, clip_segment};

    const RECT: (f64, f64, f64, f64) = (0.0, 100.0, 0.0, 50.0);

    #[test]
    fn inside_segments_are_untouched() {
        assert_eq!(
            clip_segment((10, 10), (90, 40), RECT),
            Some(((10, 10), (90, 40)))
        );
    }

    #[test]
    fn segments_are_cut_at_the_axes_edge() {
        assert_eq!(
            clip_segment((-10, 25), (110, 25), RECT),
            Some(((0, 25), (100, 25)))
        );
        assert_eq!(
            clip_segment((50, -10), (50, 60), RECT),
            Some(((50, 0), (50, 50)))
        );
    }

    #[test]
    fn fully_outside_segments_are_dropped() {
        assert_eq!(clip_segment((-10, -10), (-5, 60), RECT), None);
    }

    #[test]
    fn a_polyline_is_split_around_an_outside_gap() {
        let runs = clip_polyline(&[(50, 25), (50, 60), (60, 60), (60, 25)], RECT);
        assert_eq!(runs.len(), 2);
        assert_eq!(runs[0], vec![(50, 25), (50, 50)]);
        assert_eq!(runs[1], vec![(60, 50), (60, 25)]);
    }
}
