//! Text layout, rotated labels and annotations.

use crate::model::TextBBox;

use super::*;

/// Draw one label. Alignment is approximated: the backend only has a top-left
/// anchor, so the text width is estimated from the glyph count.
#[allow(clippy::too_many_arguments)]
pub fn draw_label<DB: DrawingBackend>(
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

pub(super) fn rotated_style<'a>(
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

/// Draw panel text and annotations above the data layers.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_text_section<DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &ChartContext<'_, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    tx: &FX,
    ty: &FY,
    line_scale: f64,
    dpi: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
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
    Ok(())
}
