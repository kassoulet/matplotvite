use std::collections::HashMap;

use plotters::coord::types::RangedCoordf64;
use plotters::prelude::*;
use plotters::style::text_anchor::{HPos, Pos, VPos};
use plotters::style::IntoFont;

use crate::color::{color, colormap};
use crate::image::{base64, image_png, image_rgb};
use crate::layout::{aspect_datalim, auto_ticks, axis_bounds, panel_ranges, range};
use crate::model::{
    Legend, LegendEntry, LegendSwatch, OwnedArray1, Panel, PngCompression, TextBBox,
};

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
            .as_deref()
            .map(color)
            .unwrap_or(RGBAColor(0, 0, 0, 0.0));
        let edge = bb
            .edgecolor
            .as_deref()
            .map(color)
            .unwrap_or(RGBAColor(0, 0, 0, 0.0));
        let alpha = bb.alpha.clamp(0.0, 1.0);
        let fill = RGBAColor(face.0, face.1, face.2, face.3 * alpha);
        let border = RGBAColor(edge.0, edge.1, edge.2, edge.3 * alpha);
        let radius = if bb.rounded {
            legend_corner_radius(fs)
        } else {
            0.0
        };
        draw_rounded_frame(
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

/// Draw ticks, tick labels and styled gridlines for panels whose tick layout is
/// controlled from Python. The plotters mesh still provides the axis frame and
/// descriptions; this only replaces its ticks and grid.
#[allow(clippy::too_many_arguments)]
fn draw_manual_ticks<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &ChartContext<DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    ranges: (f64, f64, f64, f64),
    log_base: f64,
    side: &str,
    gap: i32,
    dpi: f64,
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
        } else if p.x_symlog {
            symlog(v, p.x_symlog_linthresh)
        } else {
            v
        }
    };
    let to_chart_y = |v: f64| {
        if p.y_log {
            v.max(f64::MIN_POSITIVE).log(log_base)
        } else if p.y_symlog {
            symlog(v, p.y_symlog_linthresh)
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

    if side.is_empty() && p.grid.show && p.grid.axis != "y" {
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
    if side.is_empty() && p.grid.show && p.grid.axis != "x" {
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
    if side != "right" {
        for (v, label) in xs.iter().zip(xlabels.iter()) {
            let (px, _) = pa.map_coordinate(&(*v, y0));
            let px = px - origin.0;
            let (base_y, tick_y, label_y, vpos) = if side == "top" {
                (
                    top,
                    top - xtick_len as i32,
                    top - xtick_len as i32 - 4,
                    VPos::Bottom,
                )
            } else {
                (
                    bottom,
                    bottom + xtick_len as i32,
                    bottom + xtick_len as i32 + 4,
                    VPos::Top,
                )
            };
            area.draw(&PathElement::new(
                vec![(px, base_y), (px, tick_y)],
                xtick_col.stroke_width(xtick_w),
            ))?;
            if !label.is_empty() && !p.ticks.hide_xlabels {
                let style = rotated_style(
                    xstyle.labelsize,
                    xlabel_col,
                    xstyle.rotation,
                    dpi,
                    &p.font_family,
                )
                .pos(Pos::new(HPos::Center, vpos));
                area.draw(&Text::new(label.clone(), (px, label_y), style))?;
            }
        }
    }
    let ystyle = &p.ticks.ystyle;
    let ytick_col = color(ystyle.color.as_deref().unwrap_or(default_tick));
    let ylabel_col = color(ystyle.labelcolor.as_deref().unwrap_or(default_tick));
    let ytick_w = ystyle.width.max(1.0).round() as u32;
    let ytick_len = ystyle.length.max(0.0);
    if side != "top" {
        for (v, label) in ys.iter().zip(ylabels.iter()) {
            let (_, py) = pa.map_coordinate(&(x0, *v));
            let py = py - origin.1;
            let (tick_x, edge_x, label_x, hpos) = if side == "right" {
                (
                    right + ytick_len as i32,
                    right,
                    right + ytick_len as i32 + 4,
                    HPos::Left,
                )
            } else {
                (
                    left - ytick_len as i32,
                    left,
                    left - ytick_len as i32 - 4,
                    HPos::Right,
                )
            };
            area.draw(&PathElement::new(
                vec![(tick_x, py), (edge_x, py)],
                ytick_col.stroke_width(ytick_w),
            ))?;
            if !label.is_empty() && !p.ticks.hide_ylabels {
                let style = rotated_style(
                    ystyle.labelsize,
                    ylabel_col,
                    ystyle.rotation,
                    dpi,
                    &p.font_family,
                )
                .pos(Pos::new(hpos, VPos::Center));
                area.draw(&Text::new(label.clone(), (label_x, py), style))?;
            }
        }
    }
    let fg = color(default_tick);
    let ylabel_col = p.ylabel_color.as_deref().map(color).unwrap_or(fg);
    let xlabel_col = p.xlabel_color.as_deref().map(color).unwrap_or(fg);
    if side == "right" && !p.ylabel.is_empty() {
        let size = p.ylabel_size.unwrap_or(10.0).max(6.0);
        let family = p.ylabel_family.as_deref().unwrap_or(&p.font_family);
        let style = rotated_style(size, ylabel_col, 270.0, dpi, family)
            .pos(Pos::new(HPos::Center, VPos::Center));
        // Sit just past the widest right-hand tick label (matplotlib's
        // labelpad of 4 pt) instead of at a fixed offset in the reserved gap.
        let label_px = text_px(ystyle.labelsize.max(6.0), dpi);
        let widest = ylabels
            .iter()
            .map(|l| crate::fonts::text_width(l, label_px))
            .fold(0.0, f64::max);
        let x = (right as f64 + ytick_len + 4.0 + widest + 10.0).min((right + gap - 8) as f64);
        area.draw(&Text::new(
            p.ylabel.clone(),
            (x.round() as i32, (top + bottom) / 2),
            style,
        ))?;
    } else if side == "top" && !p.xlabel.is_empty() {
        let size = p.xlabel_size.unwrap_or(10.0).max(6.0);
        let style = rotated_style(
            size,
            xlabel_col,
            0.0,
            dpi,
            p.xlabel_family.as_deref().unwrap_or(&p.font_family),
        )
        .pos(Pos::new(HPos::Center, VPos::Center));
        area.draw(&Text::new(
            p.xlabel.clone(),
            ((left + right) / 2, top - gap + 10),
            style,
        ))?;
    } else if side.is_empty() {
        if p.ylabel_color.is_some() && !p.ylabel.is_empty() {
            let size = p.ylabel_size.unwrap_or(10.0).max(6.0);
            let style = rotated_style(
                size,
                ylabel_col,
                270.0,
                dpi,
                p.ylabel_family.as_deref().unwrap_or(&p.font_family),
            )
            .pos(Pos::new(HPos::Center, VPos::Center));
            // Sit just left of the widest tick label instead of 52 px out,
            // which left a visible hole between the label and its ticks.
            let label_px = text_px(ystyle.labelsize.max(6.0), dpi);
            let widest = ylabels
                .iter()
                .map(|l| crate::fonts::text_width(l, label_px))
                .fold(0.0, f64::max);
            let x = (left as f64 - ytick_len - 4.0 - widest - 8.0).max(2.0);
            area.draw(&Text::new(
                p.ylabel.clone(),
                (x.round() as i32, (top + bottom) / 2),
                style,
            ))?;
        }
        if p.xlabel_color.is_some() && !p.xlabel.is_empty() {
            let size = p.xlabel_size.unwrap_or(10.0).max(6.0);
            let style = rotated_style(
                size,
                xlabel_col,
                0.0,
                dpi,
                p.xlabel_family.as_deref().unwrap_or(&p.font_family),
            )
            .pos(Pos::new(HPos::Center, VPos::Center));
            area.draw(&Text::new(
                p.xlabel.clone(),
                ((left + right) / 2, bottom + 34),
                style,
            ))?;
        }
    }
    Ok(())
}

/// Candidate axes-fraction placements for `loc="best"`, in matplotlib's
/// preference order (`AnchoredOffsetbox.codes`). Ties keep the earlier entry.
const BEST_LOCS: [&str; 10] = [
    "upper right",
    "upper left",
    "lower left",
    "lower right",
    "right",
    "center left",
    "center right",
    "lower center",
    "upper center",
    "center",
];

/// Per-artist vertex cap for the `"best"` scorer: the score only needs a
/// representative sample, and dense series should not be copied per candidate.
const LEGEND_SCORE_VERTICES: usize = 1024;

/// Pixel-space geometry of the drawn artists, mirroring matplotlib's
/// `Legend._auto_legend_data`: line paths, collection offsets and patch boxes.
#[derive(Default)]
struct LegendObstacles {
    lines: Vec<Vec<(f64, f64)>>,
    offsets: Vec<(f64, f64)>,
    boxes: Vec<(f64, f64, f64, f64)>,
}

impl LegendObstacles {
    fn push_line(&mut self, mut pts: Vec<(f64, f64)>) {
        // Bound the work for artists that emit thousands of small paths.
        if pts.len() < 2 || self.lines.len() >= 4096 {
            return;
        }
        if pts.len() > LEGEND_SCORE_VERTICES {
            let stride = pts.len().div_ceil(LEGEND_SCORE_VERTICES);
            let last = *pts.last().expect("non-empty polyline");
            let mut thinned = Vec::with_capacity(LEGEND_SCORE_VERTICES + 1);
            thinned.extend(pts.iter().step_by(stride).copied());
            thinned.push(last);
            pts = thinned;
        }
        self.lines.push(pts);
    }

    fn push_point(&mut self, (x, y): (f64, f64)) {
        if x.is_finite() && y.is_finite() && self.offsets.len() < 8192 {
            self.offsets.push((x, y));
        }
    }

    /// matplotlib's badness: containment counts for line vertices and point
    /// offsets, box overlaps for filled patches, plus one per line that touches
    /// the candidate box.
    fn badness(&self, x: f64, y: f64, w: f64, h: f64) -> usize {
        let (x0, y0, x1, y1) = (x, y, x + w, y + h);
        let inside = |p: (f64, f64)| p.0 >= x0 && p.0 <= x1 && p.1 >= y0 && p.1 <= y1;
        let mut badness = self.offsets.iter().filter(|p| inside(**p)).count();
        for line in &self.lines {
            badness += line.iter().filter(|p| inside(**p)).count();
            if line.iter().any(|p| inside(*p)) || polyline_crosses_box(line, x0, y0, x1, y1) {
                badness += 1;
            }
        }
        badness
            + self
                .boxes
                .iter()
                .filter(|b| box_overlaps(b, x0, y0, x1, y1))
                .count()
    }
}

fn segments_cross(a: (f64, f64), b: (f64, f64), c: (f64, f64), d: (f64, f64)) -> bool {
    let cross = |p: (f64, f64), q: (f64, f64), r: (f64, f64)| {
        (q.0 - p.0) * (r.1 - p.1) - (q.1 - p.1) * (r.0 - p.0)
    };
    let (d1, d2) = (cross(c, d, a), cross(c, d, b));
    let (d3, d4) = (cross(a, b, c), cross(a, b, d));
    ((d1 > 0.0) != (d2 > 0.0)) && ((d3 > 0.0) != (d4 > 0.0))
}

fn polyline_crosses_box(line: &[(f64, f64)], x0: f64, y0: f64, x1: f64, y1: f64) -> bool {
    let corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)];
    line.windows(2)
        .any(|seg| (0..4).any(|i| segments_cross(seg[0], seg[1], corners[i], corners[(i + 1) % 4])))
}

fn box_overlaps(b: &(f64, f64, f64, f64), x0: f64, y0: f64, x1: f64, y1: f64) -> bool {
    b.0 < x1 && x0 < b.2 && b.1 < y1 && y0 < b.3
}

fn legend_anchor(loc: &str) -> (f64, f64) {
    match loc {
        "upper left" => (0.0, 1.0),
        "lower left" => (0.0, 0.0),
        "lower right" => (1.0, 0.0),
        "center" => (0.5, 0.5),
        "center left" => (0.0, 0.5),
        "center right" | "right" => (1.0, 0.5),
        "upper center" => (0.5, 1.0),
        "lower center" => (0.5, 0.0),
        _ => (1.0, 1.0),
    }
}

fn anchored_legend_pos(
    ax: f64,
    ay: f64,
    loc: &str,
    box_w: f64,
    box_h: f64,
    rect: (i32, i32, i32, i32),
) -> (f64, f64) {
    let (left, top, right, bottom) = rect;
    let px = left as f64 + ax * (right - left) as f64;
    let py = bottom as f64 - ay * (bottom - top) as f64;
    let x = if loc.contains("right") {
        px - box_w
    } else if loc.contains("left") {
        px
    } else {
        px - box_w / 2.0
    };
    let y = if loc.contains("upper") {
        py
    } else if loc.contains("lower") {
        py - box_h
    } else {
        py - box_h / 2.0
    };
    (
        x.clamp(left as f64, (right as f64 - box_w).max(left as f64)),
        y.clamp(top as f64, (bottom as f64 - box_h).max(top as f64)),
    )
}

/// Score every candidate placement and keep the least-overlapping one, stopping
/// at the first zero-badness candidate like matplotlib.
fn best_legend_pos(
    obstacles: &LegendObstacles,
    box_w: f64,
    box_h: f64,
    rect: (i32, i32, i32, i32),
) -> (f64, f64) {
    let mut best = anchored_legend_pos(1.0, 1.0, "upper right", box_w, box_h, rect);
    let mut best_badness = usize::MAX;
    for loc in BEST_LOCS {
        let (ax, ay) = legend_anchor(loc);
        let pos = anchored_legend_pos(ax, ay, loc, box_w, box_h, rect);
        let badness = obstacles.badness(pos.0, pos.1, box_w, box_h);
        if badness < best_badness {
            best_badness = badness;
            best = pos;
        }
        if badness == 0 {
            break;
        }
    }
    best
}

fn legend_corner_radius(font_size: f64) -> f64 {
    // Matplotlib's rounded legend box scales with the text, not the canvas.
    (font_size * 0.5).clamp(3.0, 12.0)
}

fn draw_rounded_frame<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    rect: (f64, f64, f64, f64),
    fill: RGBAColor,
    border: RGBAColor,
    radius: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (x, y, w, h) = rect;
    let r = radius.min(w / 2.0).min(h / 2.0);
    let mut pts = Vec::with_capacity(20);
    let corners = [
        (
            x + r,
            y + r,
            std::f64::consts::PI,
            1.5 * std::f64::consts::PI,
        ),
        (
            x + w - r,
            y + r,
            1.5 * std::f64::consts::PI,
            2.0 * std::f64::consts::PI,
        ),
        (x + w - r, y + h - r, 0.0, 0.5 * std::f64::consts::PI),
        (
            x + r,
            y + h - r,
            0.5 * std::f64::consts::PI,
            std::f64::consts::PI,
        ),
    ];
    for (cx, cy, start, end) in corners {
        for i in 0..=4 {
            let angle = start + (end - start) * i as f64 / 4.0;
            pts.push(((cx + r * angle.cos()) as i32, (cy + r * angle.sin()) as i32));
        }
    }
    area.draw(&Polygon::new(pts.clone(), fill.filled()))?;
    let mut outline = pts;
    if let Some(first) = outline.first().copied() {
        outline.push(first);
    }
    area.draw(&PathElement::new(outline, border.stroke_width(1)))?;
    Ok(())
}

/// Draw the legend myself so placement, columns, title and frame options all
/// work; plotters' built-in legend only supports a single column.
fn draw_legend<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    rect: (i32, i32, i32, i32),
    entries: &[LegendEntry],
    opts: &Legend,
    obstacles: &LegendObstacles,
    text: RGBAColor,
    dpi: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    if entries.is_empty() {
        return Ok(());
    }
    let fs = text_px(opts.fontsize.max(6.0), dpi);
    let title_fs = text_px(opts.title_fontsize.max(6.0), dpi);
    let cols = opts.ncol.max(1);
    let rows = entries.len().div_ceil(cols);
    let col_w = entries
        .iter()
        .map(|e| crate::fonts::text_width(&e.label, fs))
        .fold(0.0, f64::max)
        + 36.0;
    let row_h = fs * 1.6;
    let title_h = if opts.title.is_empty() {
        0.0
    } else {
        title_fs * 1.5
    };
    let box_w = col_w * cols as f64 + 8.0;
    let box_h = rows as f64 * row_h + title_h + 8.0;
    let loc = opts.loc.as_str();
    let (x, y) = if let Some((ax, ay)) = opts.anchor {
        anchored_legend_pos(ax, ay, loc, box_w, box_h, rect)
    } else if loc == "best" {
        best_legend_pos(obstacles, box_w, box_h, rect)
    } else {
        let (ax, ay) = legend_anchor(loc);
        anchored_legend_pos(ax, ay, loc, box_w, box_h, rect)
    };
    if opts.frameon {
        draw_rounded_frame(
            area,
            (x, y, box_w, box_h),
            RGBAColor(255, 255, 255, 0.8),
            RGBAColor(204, 204, 204, 1.0),
            legend_corner_radius(fs),
        )?;
    }
    if !opts.title.is_empty() {
        let style = (opts.family.as_str(), title_fs.round() as u32)
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
            LegendSwatch::LineMarker(c, w, marker) => {
                area.draw(&PathElement::new(
                    vec![(cx as i32, cy as i32), ((cx + 20.0) as i32, cy as i32)],
                    c.stroke_width(*w),
                ))?;
                draw_marker(
                    area,
                    (0, 0),
                    ((cx + 10.0) as i32, cy as i32),
                    4.0,
                    *c,
                    *c,
                    1,
                    marker,
                )?;
            }
            LegendSwatch::Marker(c, marker) => draw_marker(
                area,
                (0, 0),
                ((cx + 10.0) as i32, cy as i32),
                4.0,
                *c,
                *c,
                1,
                marker,
            )?,
            LegendSwatch::Rect(c) | LegendSwatch::Collection(c) => area.draw(&Rectangle::new(
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
        let style = (opts.family.as_str(), fs.round() as u32)
            .into_font()
            .color(&text);
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
        "--" | "dashed" => Some((3.7, 1.6)),
        ":" | "dotted" => Some((1.0, 1.65)),
        "-." | "dashdot" => Some((6.4, 1.6)),
        _ => None,
    }
}

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

/// Largest marker radius drawn; a bad `s` value should not ask the backend
/// to build an arbitrarily large path.
const MAX_MARKER_RADIUS: f64 = 4096.0;

fn marker_radius(area: f64) -> f64 {
    (area.max(0.0).sqrt() / 2.0 * 1.39).clamp(1.0, MAX_MARKER_RADIUS)
}

/// Marker geometry in matplotlib's normalized unit square (y up): filled
/// outlines as polygons, stroked markers as line subpaths, circles by radius.
enum MarkerShape {
    Polygon(Vec<(f64, f64)>),
    Strokes(Vec<((f64, f64), (f64, f64))>),
    Circle(f64),
}

/// matplotlib's marker paths, so markers we draw match its shapes exactly.
fn marker_shape(marker: &str) -> MarkerShape {
    let poly = |pts: &[(f64, f64)]| MarkerShape::Polygon(pts.to_vec());
    match marker {
        "s" => poly(&[(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]),
        "D" => poly(&[(0.0, -0.5), (0.5, 0.0), (0.0, 0.5), (-0.5, 0.0)]),
        "d" => poly(&[(0.0, -0.707), (0.424, 0.0), (0.0, 0.707), (-0.424, 0.0)]),
        "p" => poly(&[
            (0.0, 0.5),
            (-0.476, 0.155),
            (-0.294, -0.405),
            (0.294, -0.405),
            (0.476, 0.155),
        ]),
        "P" => poly(&[
            (-0.167, -0.5),
            (0.167, -0.5),
            (0.167, -0.167),
            (0.5, -0.167),
            (0.5, 0.167),
            (0.167, 0.167),
            (0.167, 0.5),
            (-0.167, 0.5),
            (-0.167, 0.167),
            (-0.5, 0.167),
            (-0.5, -0.167),
            (-0.167, -0.167),
        ]),
        "h" => poly(&[
            (0.0, 0.5),
            (-0.433, 0.25),
            (-0.433, -0.25),
            (0.0, -0.5),
            (0.433, -0.25),
            (0.433, 0.25),
        ]),
        "H" => poly(&[
            (-0.25, 0.433),
            (-0.5, 0.0),
            (-0.25, -0.433),
            (0.25, -0.433),
            (0.5, 0.0),
            (0.25, 0.433),
        ]),
        "8" => poly(&[
            (-0.191, 0.462),
            (-0.462, 0.191),
            (-0.462, -0.191),
            (-0.191, -0.462),
            (0.191, -0.462),
            (0.462, -0.191),
            (0.462, 0.191),
            (0.191, 0.462),
        ]),
        "*" => poly(&[
            (0.0, 0.5),
            (-0.112, 0.155),
            (-0.476, 0.155),
            (-0.182, -0.059),
            (-0.294, -0.405),
            (0.0, -0.191),
            (0.294, -0.405),
            (0.182, -0.059),
            (0.476, 0.155),
            (0.112, 0.155),
        ]),
        "X" => poly(&[
            (-0.25, -0.5),
            (0.0, -0.25),
            (0.25, -0.5),
            (0.5, -0.25),
            (0.25, 0.0),
            (0.5, 0.25),
            (0.25, 0.5),
            (0.0, 0.25),
            (-0.25, 0.5),
            (-0.5, 0.25),
            (-0.25, 0.0),
            (-0.5, -0.25),
        ]),
        "^" => poly(&[(0.0, 0.5), (-0.5, -0.5), (0.5, -0.5)]),
        "v" => poly(&[(0.0, -0.5), (0.5, 0.5), (-0.5, 0.5)]),
        "<" => poly(&[(-0.5, 0.0), (0.5, -0.5), (0.5, 0.5)]),
        ">" => poly(&[(0.5, 0.0), (-0.5, 0.5), (-0.5, -0.5)]),
        "1" | "2" | "3" | "4" => {
            let (stem, arm_a, arm_b) = match marker {
                "1" => ((0.0, -0.5), (0.4, 0.25), (-0.4, 0.25)),
                "2" => ((0.0, 0.5), (-0.4, -0.25), (0.4, -0.25)),
                "3" => ((-0.5, 0.0), (0.25, -0.4), (0.25, 0.4)),
                _ => ((0.5, 0.0), (-0.25, 0.4), (-0.25, -0.4)),
            };
            MarkerShape::Strokes(vec![
                ((0.0, 0.0), stem),
                ((0.0, 0.0), arm_a),
                ((0.0, 0.0), arm_b),
            ])
        }
        "x" => MarkerShape::Strokes(vec![((-0.5, -0.5), (0.5, 0.5)), ((-0.5, 0.5), (0.5, -0.5))]),
        "+" => MarkerShape::Strokes(vec![((-0.5, 0.0), (0.5, 0.0)), ((0.0, -0.5), (0.0, 0.5))]),
        "|" => MarkerShape::Strokes(vec![((0.0, -0.5), (0.0, 0.5))]),
        "_" => MarkerShape::Strokes(vec![((-0.5, 0.0), (0.5, 0.0))]),
        "." => MarkerShape::Circle(0.5),
        _ => MarkerShape::Circle(1.0),
    }
}

/// One scatter marker centred on canvas pixel `pos`, with pixel radius `r`.
/// `fill` paints the interior and `edge` the outline; a fully transparent
/// `fill` draws the outline only (Matplotlib's `markerfacecolor="none"`).
#[allow(clippy::too_many_arguments)]
fn draw_marker<DB: DrawingBackend, C: Color>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    pos: (i32, i32),
    r: f64,
    fill: C,
    edge: C,
    stroke: u32,
    marker: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (x, y) = (pos.0 - base.0, pos.1 - base.1);
    let ri = r.round().max(1.0);
    let span = 2.0 * ri;
    let hollow = fill.to_rgba().3 == 0.0;
    let map = |(vx, vy): (f64, f64)| {
        (
            (x as f64 + vx * span).round() as i32,
            (y as f64 - vy * span).round() as i32,
        )
    };
    match marker_shape(marker) {
        MarkerShape::Polygon(verts) => {
            if marker == "s" {
                let corners = [
                    (x - ri as i32, y - ri as i32),
                    (x + ri as i32, y + ri as i32),
                ];
                if hollow {
                    // Keep a square marker as an SVG `<rect>`; the raster backends
                    // produce the same pixels either way.
                    area.draw(&Rectangle::new(corners, edge.stroke_width(stroke.max(1))))?;
                } else {
                    area.draw(&Rectangle::new(corners, fill.filled()))?;
                }
            } else {
                let pts: Vec<(i32, i32)> = verts.iter().map(|v| map(*v)).collect();
                if hollow {
                    area.draw(&Polygon::new(pts, edge.stroke_width(stroke.max(1))))?;
                } else {
                    area.draw(&Polygon::new(pts, fill.filled()))?;
                }
            }
        }
        MarkerShape::Strokes(segs) => {
            for (a, b) in segs {
                area.draw(&PathElement::new(
                    vec![map(a), map(b)],
                    edge.stroke_width(stroke),
                ))?;
            }
        }
        MarkerShape::Circle(frac) => {
            // Matplotlib strokes markers with their edge width even when the
            // edge colour is the face, so the visible radius includes half of
            // it (scatter's default linewidths is 1 pt).
            let radius = (ri * frac + stroke as f64 / 2.0).round().max(1.0) as u32;
            if hollow {
                area.draw(&Circle::new(
                    (x, y),
                    radius,
                    edge.stroke_width(stroke.max(1)),
                ))?;
            } else {
                area.draw(&Circle::new((x, y), radius, fill.filled()))?;
            }
        }
    }
    Ok(())
}

/// A vertical gradient strip with min/mid/max ticks and an optional axis label.
/// `plot` is the main chart's plotting rectangle in panel-local pixels; the
/// strip spans exactly that vertical range, like a matplotlib colorbar.
#[allow(clippy::too_many_arguments)]
fn draw_colorbar<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    plot: (i32, i32, i32, i32),
    cmap: &str,
    vmin: f64,
    vmax: f64,
    label: &str,
    line_scale: f64,
    family: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (w, h) = area.dim_in_pixel();
    let (_, top, right, bottom) = plot;
    let (x0, x1) = (right + 18, right + 48);
    let (y0, y1) = (top, bottom);
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
    if vmax > vmin {
        for v in auto_ticks(vmin, vmax, false) {
            let t = (v - vmin) / (vmax - vmin);
            let y = (y0 as f64 + (1.0 - t) * (y1 - y0) as f64).round() as i32;
            area.draw(&PathElement::new(
                vec![(x0 - 4, y), (x0, y)],
                frame.stroke_width(1),
            ))?;
            draw_label(
                area,
                (0, 0),
                (x1 + 6, y),
                &tick_label(v),
                RGBAColor(0, 0, 0, 1.0),
                13.0,
                "left",
                "center",
                None,
                0.0,
                line_scale,
                family,
            )?;
        }
    }
    if !label.is_empty() {
        draw_label(
            area,
            (0, 0),
            (x1 + 6, (y1 + 8).min(h as i32 - 2)),
            label,
            RGBAColor(0, 0, 0, 1.0),
            14.0,
            "left",
            "top",
            None,
            0.0,
            line_scale,
            family,
        )?;
    }
    Ok(())
}

/// One level of a marching-squares pass: iso-line segments in data coordinates.
fn contour_segments(x: &[f64], y: &[f64], z: &[f64], level: f64) -> Vec<((f64, f64), (f64, f64))> {
    let (rows, cols) = (y.len(), x.len());
    let mut out = Vec::new();
    if rows < 2 || cols < 2 || rows.checked_mul(cols) != Some(z.len()) {
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

/// Join marching-squares segments that share an endpoint into polylines.
fn contour_polylines(segments: Vec<((f64, f64), (f64, f64))>) -> Vec<Vec<(f64, f64)>> {
    if segments.is_empty() {
        return Vec::new();
    }
    let key = |p: (f64, f64)| (p.0.to_bits(), p.1.to_bits());
    let mut incident: HashMap<(u64, u64), Vec<usize>> = HashMap::new();
    for (i, (a, b)) in segments.iter().enumerate() {
        incident.entry(key(*a)).or_default().push(i);
        incident.entry(key(*b)).or_default().push(i);
    }
    let mut used = vec![false; segments.len()];
    let mut lines = Vec::new();
    for i in 0..segments.len() {
        if used[i] {
            continue;
        }
        used[i] = true;
        let (a, b) = segments[i];
        let mut line = vec![a, b];
        // Extend forward from the current tail.
        while let Some(tail_point) = line.last() {
            let tail = key(*tail_point);
            let Some(next) = incident
                .get(&tail)
                .and_then(|ids| ids.iter().copied().find(|&j| !used[j]))
            else {
                break;
            };
            used[next] = true;
            let (c, d) = segments[next];
            let far = if key(c) == tail { d } else { c };
            line.push(far);
        }
        // Extend backward from the current head. Collect the prefix first so
        // long open contours do not pay Vec::insert(0, ..) on every segment.
        let mut prefix = Vec::new();
        while let Some(head_point) = line.first() {
            let head = key(*head_point);
            let Some(previous) = incident
                .get(&head)
                .and_then(|ids| ids.iter().copied().find(|&j| !used[j]))
            else {
                break;
            };
            used[previous] = true;
            let (c, d) = segments[previous];
            let far = if key(c) == head { d } else { c };
            prefix.push(far);
        }
        if !prefix.is_empty() {
            prefix.reverse();
            prefix.extend(line);
            line = prefix;
        }
        if line.len() > 1 {
            lines.push(line);
        }
    }
    lines
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

/// Greedily drop points closer than `tolerance` pixels to the last kept point.
/// Matplotlib simplifies dense paths before drawing; without this a 100k-point
/// line becomes a 0.8 MB SVG path and swamps the render time.
fn simplify_polyline(
    pts: &[(f64, f64)],
    tolerance: f64,
    map: impl Fn(&(f64, f64)) -> (f64, f64),
) -> Vec<(f64, f64)> {
    let mut out = Vec::new();
    if pts.len() < 3 {
        return pts.to_vec();
    }
    out.push(pts[0]);
    let mut last = map(&pts[0]);
    for p in &pts[1..pts.len().saturating_sub(1)] {
        let (x, y) = map(p);
        if !x.is_finite() || !y.is_finite() {
            // Keep non-finite points and stop simplifying the rest so the
            // undrawn gaps in the series stay where they were.
            out.push(*p);
            last = (x, y);
            continue;
        }
        let (dx, dy) = (x - last.0, y - last.1);
        if dx * dx + dy * dy >= tolerance * tolerance {
            out.push(*p);
            last = (x, y);
        }
    }
    if let Some(last_pt) = pts.last() {
        if out.last() != Some(last_pt) {
            out.push(*last_pt);
        }
    }
    out
}

/// Paint one marker into a transparent raster layer. Dense raster scatters use
/// this instead of one SVG element per point, which keeps resvg's per-element
/// work out of the save path.
#[allow(clippy::too_many_arguments)]
fn draw_marker_raster(
    pixmap: &mut tiny_skia::Pixmap,
    base: (i32, i32),
    pos: (i32, i32),
    r: f64,
    fill: RGBAColor,
    edge: RGBAColor,
    stroke: u32,
    marker: &str,
) {
    let (x, y) = ((pos.0 - base.0) as f64, (pos.1 - base.1) as f64);
    // Keep the fractional radius on the dense raster path: rounding it down
    // shrank every small marker (s=4 is 1.39 px) to a hard two-pixel block
    // instead of an anti-aliased disc.
    let r = r.clamp(1.0, MAX_MARKER_RADIUS);
    let span = 2.0 * r;
    let hollow = fill.3 == 0.0;
    let map = |(vx, vy): (f64, f64)| ((x + vx * span) as f32, (y - vy * span) as f32);
    let paint_of = |col: RGBAColor| {
        let alpha = (col.3.clamp(0.0, 1.0) * 255.0).round() as u8;
        tiny_skia::Paint {
            shader: tiny_skia::Shader::SolidColor(tiny_skia::Color::from_rgba8(
                col.0, col.1, col.2, alpha,
            )),
            anti_alias: true,
            ..Default::default()
        }
    };
    let paint = paint_of(if hollow { edge } else { fill });
    match marker_shape(marker) {
        MarkerShape::Strokes(segs) => {
            let mut pb = tiny_skia::PathBuilder::new();
            for (a, b) in segs {
                let (ax, ay) = map(a);
                let (bx, by) = map(b);
                pb.move_to(ax, ay);
                pb.line_to(bx, by);
            }
            if let Some(path) = pb.finish() {
                let stroke = tiny_skia::Stroke {
                    width: stroke.max(1) as f32,
                    ..Default::default()
                };
                pixmap.stroke_path(
                    &path,
                    &paint_of(edge),
                    &stroke,
                    tiny_skia::Transform::identity(),
                    None,
                );
            }
        }
        MarkerShape::Circle(frac) => {
            let mut pb = tiny_skia::PathBuilder::new();
            pb.push_circle(x as f32, y as f32, (r * frac).max(1.0) as f32);
            if let Some(path) = pb.finish() {
                if hollow {
                    if stroke > 0 {
                        let outline = tiny_skia::Stroke {
                            width: stroke as f32,
                            ..Default::default()
                        };
                        pixmap.stroke_path(
                            &path,
                            &paint_of(edge),
                            &outline,
                            tiny_skia::Transform::identity(),
                            None,
                        );
                    }
                } else {
                    pixmap.fill_path(
                        &path,
                        &paint,
                        tiny_skia::FillRule::Winding,
                        tiny_skia::Transform::identity(),
                        None,
                    );
                    // A face-coloured edge like Matplotlib's marker linewidth.
                    if stroke > 0 {
                        let outline = tiny_skia::Stroke {
                            width: stroke as f32,
                            ..Default::default()
                        };
                        pixmap.stroke_path(
                            &path,
                            &paint,
                            &outline,
                            tiny_skia::Transform::identity(),
                            None,
                        );
                    }
                }
            }
        }
        MarkerShape::Polygon(verts) => {
            let mut pb = tiny_skia::PathBuilder::new();
            if let Some((vx, vy)) = verts.first() {
                let (px, py) = map((*vx, *vy));
                pb.move_to(px, py);
                for v in &verts[1..] {
                    let (px, py) = map(*v);
                    pb.line_to(px, py);
                }
                pb.close();
            }
            if let Some(path) = pb.finish() {
                pixmap.fill_path(
                    &path,
                    &paint,
                    tiny_skia::FillRule::Winding,
                    tiny_skia::Transform::identity(),
                    None,
                );
            }
        }
    }
}

/// Tick label for a linear axis: short, without float noise.
fn tick_label(v: f64) -> String {
    if v == 0.0 {
        return "0".to_string();
    }
    let a = v.abs();
    let label = if !(1e-3..1e5).contains(&a) {
        format!("{v:.2e}")
    } else {
        format!("{v:.4}")
            .trim_end_matches('0')
            .trim_end_matches('.')
            .to_string()
    };
    label
        .strip_prefix('-')
        .map(|rest| format!("−{rest}"))
        .unwrap_or(label)
}

/// Tick label for a log coordinate: base^v written as a plain number.
fn log_label(v: f64, base: f64) -> String {
    let value = base.powf(v);
    if !(1e-4..1e5).contains(&value) {
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
    let fg = color(p.foreground.as_deref().unwrap_or("#000000"));
    let twin_side = p.twin.as_str();
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
        } else {
            v
        }
    };
    let ty = |v: f64| {
        if p.y_log {
            v.max(f64::MIN_POSITIVE).log(base)
        } else if p.y_symlog {
            symlog(v, p.y_symlog_linthresh)
        } else {
            v
        }
    };
    if p.x_log || p.x_symlog {
        (x0, x1) = (tx(x0), tx(x1));
        if x1 <= x0 {
            x1 = x0 + 1.0;
        }
    }
    if p.y_log || p.y_symlog {
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
    let manual = p.ticks.xticks.is_some()
        || p.ticks.yticks.is_some()
        || p.ticks.xstyle.is_custom()
        || p.ticks.ystyle.is_custom()
        || !twin_side.is_empty()
        || p.xlabel_color.is_some()
        || p.ylabel_color.is_some()
        || (p.grid.show
            && (p.grid.color.is_some()
                || p.grid.linewidth.is_some()
                || p.grid.alpha.is_some()
                || p.grid.linestyle.is_some()));
    let exact_axes = p.axes_bounds;
    // Fixed margins at 25 px + 45 px label bands only fit tall panels. On a
    // short subplot row they consume the whole cell, leaving a few pixels for
    // the data (Matplotlib budgets these margins as a fraction of the axes).
    let panel_h = area.dim_in_pixel().1 as f64;
    let margin = (panel_h / 10.0).clamp(4.0, 25.0).round() as u32;
    let label_area = (panel_h / 5.0).clamp(8.0, 45.0).round() as u32;
    let shrunk_area;
    let mut builder = ChartBuilder::on(area);
    if exact_axes {
        // `add_axes`/insets already include their label margins in `bounds`.
        // Keep the chart plotting area on the requested rectangle instead of
        // adding the normal panel margin a second time.
        builder.margin(0);
        builder.margin_right(25);
        builder.margin_top(25);
    } else {
        builder.margin(margin);
        if colorbar.is_some() {
            builder.margin_right(125);
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
    if p.aspect.is_none() && !p.title.is_empty() {
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
        .x_label_area_size(if exact_axes { 30 } else { label_area })
        .y_label_area_size(if exact_axes { 40 } else { label_area })
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
            rb.margin_right(125);
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
            .x_label_area_size(label_area)
            .y_label_area_size(label_area)
            .build_cartesian_2d(x0..x1, y0..y1)?;
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
        let label_size = text_px(p.ticks.xstyle.labelsize.max(6.0), dpi).round() as u32;
        let desc_size = text_px(
            p.xlabel_size
                .unwrap_or(10.0)
                .max(p.ylabel_size.unwrap_or(10.0))
                .max(6.0),
            dpi,
        )
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
        let x_desc =
            if twin_side.is_empty() && p.xlabel_color.is_none() && p.xlabel_family.is_none() {
                p.xlabel.as_str()
            } else {
                ""
            };
        let y_desc =
            if twin_side.is_empty() && p.ylabel_color.is_none() && p.ylabel_family.is_none() {
                p.ylabel.as_str()
            } else {
                ""
            };
        mesh.label_style((p.font_family.as_str(), label_size).into_font().color(&fg))
            .axis_desc_style((p.font_family.as_str(), desc_size).into_font().color(&fg))
            .axis_style(fg.stroke_width(1))
            .x_labels(8)
            .y_labels(8)
            .x_desc(x_desc)
            .y_desc(y_desc)
            .x_label_formatter(&x_fmt)
            .y_label_formatter(&y_fmt)
            .draw()?;
        // Plotters strokes the left/bottom axes; add only the missing top and
        // right spines so no edge is painted twice and looks thicker.
        {
            let base = area.get_base_pixel();
            let pa = chart.plotting_area();
            let tl = pa.map_coordinate(&(x0, y1));
            let br = pa.map_coordinate(&(x1, y0));
            let (left, top) = (tl.0 - base.0, tl.1 - base.1);
            let (right, bottom) = (br.0 - base.0, br.1 - base.1);
            area.draw(&PathElement::new(
                vec![(left, top), (right, top)],
                fg.stroke_width(1),
            ))?;
            area.draw(&PathElement::new(
                vec![(right, top), (right, bottom)],
                fg.stroke_width(1),
            ))?;
        }
        if manual {
            let axis_side = match twin_side {
                "y" => "right",
                "x" => "top",
                _ => "",
            };
            draw_manual_ticks(
                area,
                &chart,
                p,
                (x0, x1, y0, y1),
                base,
                axis_side,
                twin_gap_px,
                dpi,
            )?;
        }
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
                    let c = colormap(cmap, (band as f64 + 0.5) / bands as f64);
                    RGBAColor(c[0], c[1], c[2], 1.0)
                } else {
                    color(&colors[band % colors.len()])
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
                            let poly = clip_band(&tri, lo, hi);
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
            let (xs, ys) = (band.x.as_array(), band.y.as_array());
            if xs.len() < 3 || xs.len() != ys.len() {
                continue;
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
                continue;
            }
            let pts: Vec<(i32, i32)> = xs.iter().zip(ys.iter()).map(|(x, y)| map(*x, *y)).collect();
            let col = color(&band.color).mix(alpha);
            area.draw(&Polygon::new(pts, col.filled()))?;
            if !band.label.is_empty() {
                legend_bands.push((band.label.clone(), col));
            }
        }
        for (label, col) in legend_bands {
            entries.push(LegendEntry {
                label: label.clone(),
                swatch: LegendSwatch::Collection(col),
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
                if let Some(edges) = &bars.edgecolor {
                    if let Some(ec) = edges.get(i % edges.len().max(1)) {
                        let ecol = color(ec).stroke_width(1);
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
            let face = patch.facecolor.as_deref().map(color).filter(|c| c.3 > 0.0);
            let fill = face.map(|c| c.mix(alpha));
            let stroke = patch
                .edgecolor
                .as_deref()
                .map(color)
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
            match patch.kind.as_str() {
                "rect" => {
                    let (ax0, ay0) = map(patch.x, patch.y);
                    let (ax1, ay1) = map(patch.x + patch.width, patch.y + patch.height);
                    let (xl, xr) = (ax0.min(ax1), ax0.max(ax1));
                    let (yt, yb) = (ay0.min(ay1), ay0.max(ay1));
                    if xr <= xl || yb <= yt {
                        continue;
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
                        continue;
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
        for coll in &p.collections {
            let alpha = coll.alpha.clamp(0.0, 1.0);
            let marker = if coll.marker.is_empty() {
                "o"
            } else {
                coll.marker.as_str()
            };
            if !coll.label.is_empty() {
                let icon = coll
                    .colors
                    .first()
                    .map(|c| color(c))
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
                let r = marker_radius(size);
                let col = if coll.colors.is_empty() {
                    RGBAColor(31, 119, 180, 1.0)
                } else {
                    color(&coll.colors[i % coll.colors.len()])
                };
                if let Some(layer) = collection_layer.as_mut() {
                    draw_marker_raster(
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
                    draw_marker(
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
                    color(&coll.colors[i % coll.colors.len()])
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
                    let c = colormap(cmap, t);
                    RGBAColor(c[0], c[1], c[2], 1.0)
                } else {
                    color(&colors[li % colors.len()])
                })
                .mix(opacity);
                let width = linewidths
                    .get(li)
                    .or_else(|| linewidths.first())
                    .copied()
                    .unwrap_or(2.0)
                    .clamp(0.25, 64.0);
                for line in contour_polylines(contour_segments(&xs, &ys, &zs, *level)) {
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
            let dots_per_unit = |unit: &str| -> f64 {
                match unit {
                    "height" => ph,
                    "dots" => 1.0,
                    "inches" => dpi,
                    "x" => pw / x_span,
                    "y" => ph / y_span,
                    "xy" => pw.hypot(ph) / x_span.hypot(y_span),
                    _ => pw,
                }
            };
            let dx_trans = dots_per_unit(&arrow.units).max(f64::MIN_POSITIVE);
            let span = pw / dx_trans;
            let width_units = arrow.width.unwrap_or(0.06 * span / sn);
            let widthu_per_lenu = match arrow.scale_units.as_deref() {
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
                    color(&arrow.colors[i % arrow.colors.len()])
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
                color(c),
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
                draw_arrow(area, base, anchor, target, color(c))?;
            }
            draw_label(
                area,
                base,
                anchor,
                text,
                color(c),
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
        for item in &p.images {
            let (l, r, b, t) = item.4;
            let (ax, ay) = chart_area.map_coordinate(&(tx(l), ty(t)));
            let (zx, zy) = chart_area.map_coordinate(&(tx(r), ty(b)));
            let (iw, ih) = ((ax - zx).abs(), (ay - zy).abs());
            if iw == 0 || ih == 0 {
                continue;
            }
            if draw_images {
                let bg = p
                    .facecolor
                    .as_deref()
                    .map(color)
                    .map(|c| [c.0, c.1, c.2])
                    .unwrap_or([255, 255, 255]);
                let (x, y) = (ax.min(zx) - base.0, ay.min(zy) - base.1);
                let rgb = image_rgb(item, iw as u32, ih as u32, bg)?;
                if let Some(elem) = plotters::element::BitMapElement::with_owned_buffer(
                    (x, y),
                    (iw as u32, ih as u32),
                    rgb,
                ) {
                    area.draw(&elem)?;
                }
                continue;
            }
            let hint = if matches!(item.7.as_str(), "none" | "nearest") {
                " style=\"image-rendering:pixelated\""
            } else {
                ""
            };
            // Embedded into the root SVG, so this stays in canvas pixels.
            overlays.push(format!(
                "<image x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" \
                 preserveAspectRatio=\"none\"{hint} href=\"data:image/png;base64,{}\"/>",
                ax.min(zx),
                ay.min(zy),
                iw,
                ih,
                base64(&image_png(item)?)
            ));
        }
    }
    // `loc="best"` scores candidate corners against the drawn artists, so collect
    // their pixel geometry once, mirroring matplotlib's `Legend._auto_legend_data`.
    let legend_obstacles = if custom_legend && p.legend.loc == "best" {
        let pa = chart.plotting_area();
        let base = area.get_base_pixel();
        let mut obstacles = LegendObstacles::default();
        let to_px = |x: f64, y: f64| {
            let (px, py) = pa.map_coordinate(&(tx(x), ty(y)));
            (px as f64 - base.0 as f64, py as f64 - base.1 as f64)
        };
        let sample = |xs: &OwnedArray1, ys: &OwnedArray1| -> Vec<(f64, f64)> {
            let (xs, ys) = (xs.as_array(), ys.as_array());
            let n = xs.len().min(ys.len());
            let stride = n.div_ceil(LEGEND_SCORE_VERTICES).max(1);
            (0..n)
                .step_by(stride)
                .map(|i| to_px(xs[i], ys[i]))
                .collect()
        };
        for s in &p.series {
            obstacles.push_line(sample(&s.x, &s.y));
        }
        for bar in &p.bars {
            let (left, bottom) = (bar.left.as_array(), bar.bottom.as_array());
            let (width, height) = (bar.width.as_array(), bar.height.as_array());
            for i in 0..left
                .len()
                .min(bottom.len())
                .min(width.len())
                .min(height.len())
            {
                let (ax0, ay0) = to_px(left[i], bottom[i]);
                let (ax1, ay1) = to_px(left[i] + width[i], bottom[i] + height[i]);
                obstacles
                    .boxes
                    .push((ax0.min(ax1), ay0.min(ay1), ax0.max(ax1), ay0.max(ay1)));
            }
        }
        for band in &p.bands {
            obstacles.push_line(sample(&band.x, &band.y));
        }
        for sc in &p.scatter {
            let (xs, ys) = (sc.x.as_array(), sc.y.as_array());
            let n = xs.len().min(ys.len());
            let stride = n.div_ceil(LEGEND_SCORE_VERTICES).max(1);
            for i in (0..n).step_by(stride) {
                obstacles.push_point(to_px(xs[i], ys[i]));
            }
        }
        for err in &p.errors {
            let (xs, ys) = (err.0.as_array(), err.1.as_array());
            let n = xs.len().min(ys.len());
            let stride = n.div_ceil(LEGEND_SCORE_VERTICES).max(1);
            for i in (0..n).step_by(stride) {
                obstacles.push_point(to_px(xs[i], ys[i]));
            }
        }
        for patch in &p.patches {
            match patch.kind.as_str() {
                "rect" => {
                    let (ax0, ay0) = to_px(patch.x, patch.y);
                    let (ax1, ay1) = to_px(patch.x + patch.width, patch.y + patch.height);
                    obstacles
                        .boxes
                        .push((ax0.min(ax1), ay0.min(ay1), ax0.max(ax1), ay0.max(ay1)));
                }
                "circle" => {
                    let (cx, cy) = to_px(patch.x, patch.y);
                    let (rx, _) = to_px(patch.x + patch.width, patch.y);
                    let (_, ry) = to_px(patch.x, patch.y + patch.width);
                    let (rx, ry) = ((rx - cx).abs(), (ry - cy).abs());
                    let ring = (0..16)
                        .map(|i| {
                            let t = i as f64 / 16.0 * std::f64::consts::TAU;
                            (cx + rx * t.cos(), cy + ry * t.sin())
                        })
                        .collect();
                    obstacles.push_line(ring);
                }
                _ => {
                    let pts = patch
                        .points
                        .as_chunks::<2>()
                        .0
                        .iter()
                        .map(|pair| to_px(pair[0], pair[1]))
                        .collect();
                    obstacles.push_line(pts);
                }
            }
        }
        for coll in &p.collections {
            let n = coll.points.len() / 2;
            let stride = n.div_ceil(LEGEND_SCORE_VERTICES).max(1);
            for i in (0..n).step_by(stride) {
                obstacles.push_point(to_px(coll.points[i * 2], coll.points[i * 2 + 1]));
            }
            for seg in &coll.segments {
                let pts = seg
                    .as_chunks::<2>()
                    .0
                    .iter()
                    .map(|pair| to_px(pair[0], pair[1]))
                    .collect();
                obstacles.push_line(pts);
            }
        }
        obstacles
    } else {
        LegendObstacles::default()
    };
    if p.legend.show {
        // Matplotlib collects line handles before patches and collections.
        entries.sort_by_key(|entry| match &entry.swatch {
            LegendSwatch::Line(..) | LegendSwatch::LineMarker(..) | LegendSwatch::Marker(..) => 0,
            LegendSwatch::Rect(_) => 1,
            LegendSwatch::Collection(_) | LegendSwatch::Circle(_) => 2,
        });
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
            &legend_obstacles,
            fg,
            dpi,
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
        labels.position(position).label_font((
            p.legend.family.as_str(),
            text_px(p.legend.fontsize.max(6.0), dpi).round() as u32,
        ));
        if p.legend.frameon {
            labels
                .background_style(RGBAColor(255, 255, 255, 0.92))
                .border_style(RGBColor(200, 200, 200))
                .margin(12)
                .legend_area_size(24);
        } else {
            labels
                .background_style(TRANSPARENT)
                .border_style(TRANSPARENT);
        }
        labels.draw()?;
    }
    if let Some((cmap, vmin, vmax, label)) = colorbar {
        let base = area.get_base_pixel();
        let pa = chart.plotting_area();
        let tl = pa.map_coordinate(&(x0, y1));
        let br = pa.map_coordinate(&(x1, y0));
        draw_colorbar(
            area,
            (tl.0 - base.0, tl.1 - base.1, br.0 - base.0, br.1 - base.1),
            cmap,
            *vmin,
            *vmax,
            label,
            line_scale,
            p.font_family.as_str(),
        )?;
    }
    Ok(())
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
