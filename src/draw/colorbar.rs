use super::ticks::{log_label, tick_format, tick_label, TickFormat};
use super::*;
use crate::color::Cmap;

/// A gradient strip with min/mid/max ticks and an optional axis label.
/// `plot` is the main chart's plotting rectangle in panel-local pixels; a
/// vertical strip occupies its right margin and a horizontal strip its bottom
/// margin.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_colorbar<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    plot: (i32, i32, i32, i32),
    cmap: Cmap,
    vmin: f64,
    vmax: f64,
    label: &str,
    log_scale: bool,
    limits: Option<(f64, f64)>,
    base: f64,
    orientation: &str,
    extend: &str,
    extendrect: bool,
    extendfrac: f64,
    line_scale: f64,
    family: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (w, h) = area.dim_in_pixel();
    let (left, top, right, bottom) = plot;
    let horizontal = orientation == "horizontal";
    let (x0, x1, y0, y1) = if horizontal {
        (left, right, bottom + 18, bottom + 48)
    } else {
        (right + 18, right + 48, top, bottom)
    };
    if x0 < 0 || y0 < 0 || x1 > w as i32 || y1 > h as i32 || x1 - x0 < 4 || y1 - y0 < 4 {
        return Ok(());
    }
    let (lo, hi) = limits
        .map(|(a, b)| (a.min(b), a.max(b)))
        .unwrap_or((vmin.min(vmax), vmax.max(vmin)));
    let base = if base > 1.0 { base } else { 10.0 };
    let log = log_scale && lo > 0.0 && hi > 0.0;
    let (scale_lo, scale_hi) = if log {
        (lo.log(base), hi.log(base))
    } else {
        (lo, hi)
    };
    let scale_span = scale_hi - scale_lo;
    let safe_span = if scale_span.abs() > f64::EPSILON {
        scale_span
    } else {
        1.0
    };
    let (norm_lo, norm_hi) = (vmin.min(vmax), vmax.max(vmin));
    let steps = if horizontal { x1 - x0 } else { y1 - y0 };
    for i in 0..steps {
        let f = if horizontal {
            (i as f64 + 0.5) / steps as f64
        } else {
            1.0 - (i as f64 + 0.5) / steps as f64
        };
        let value = if log {
            base.powf(scale_lo + f * scale_span)
        } else {
            lo + f * scale_span
        };
        let t = if norm_hi > norm_lo {
            ((value - norm_lo) / (norm_hi - norm_lo)).clamp(0.0, 1.0)
        } else {
            f
        };
        let c = cmap.sample(t);
        let rect = if horizontal {
            [(x0 + i, y0), (x0 + i + 1, y1)]
        } else {
            [(x0, y0 + i), (x1, y0 + i + 1)]
        };
        area.draw(&Rectangle::new(
            rect,
            RGBAColor(c[0], c[1], c[2], 1.0).filled(),
        ))?;
    }
    let frame = RGBColor(90, 90, 90);
    let span = if horizontal { x1 - x0 } else { y1 - y0 };
    let tri = (span as f64 * extendfrac.max(0.0)).round() as i32;
    let low_color = cmap.sample(0.0);
    let high_color = cmap.sample(1.0);
    if extend == "min" || extend == "both" {
        let fill = RGBAColor(low_color[0], low_color[1], low_color[2], 1.0).filled();
        if extendrect {
            let rect = if horizontal {
                [(x0 - tri, y0), (x0, y1)]
            } else {
                [(x0, y1), (x1, y1 + tri)]
            };
            area.draw(&Rectangle::new(rect, fill))?;
            area.draw(&Rectangle::new(rect, frame.stroke_width(1)))?;
        } else {
            let pts = if horizontal {
                vec![(x0, y0), (x0, y1), (x0 - tri, (y0 + y1) / 2)]
            } else {
                vec![(x0, y1), (x1, y1), ((x0 + x1) / 2, y1 + tri)]
            };
            area.draw(&Polygon::new(pts.clone(), fill))?;
            area.draw(&Polygon::new(pts, frame.stroke_width(1)))?;
        }
    }
    if extend == "max" || extend == "both" {
        let fill = RGBAColor(high_color[0], high_color[1], high_color[2], 1.0).filled();
        if extendrect {
            let rect = if horizontal {
                [(x1, y0), (x1 + tri, y1)]
            } else {
                [(x0, y0 - tri), (x1, y0)]
            };
            area.draw(&Rectangle::new(rect, fill))?;
            area.draw(&Rectangle::new(rect, frame.stroke_width(1)))?;
        } else {
            let pts = if horizontal {
                vec![(x1, y0), (x1, y1), (x1 + tri, (y0 + y1) / 2)]
            } else {
                vec![(x0, y0), (x1, y0), ((x0 + x1) / 2, y0 - tri)]
            };
            area.draw(&Polygon::new(pts.clone(), fill))?;
            area.draw(&Polygon::new(pts, frame.stroke_width(1)))?;
        }
    }
    area.draw(&Rectangle::new([(x0, y0), (x1, y1)], frame.stroke_width(1)))?;
    let tick_positions = if scale_span > 0.0 {
        auto_ticks(scale_lo, scale_hi, log)
    } else {
        Vec::new()
    };
    let format = if log {
        TickFormat {
            decimals: 0,
            scientific: false,
        }
    } else {
        tick_format(&tick_positions)
    };
    let mut widest_tick = 0.0_f64;
    for &v in &tick_positions {
        let text = if log {
            log_label(v, base)
        } else {
            tick_label(v, format)
        };
        widest_tick = widest_tick.max(crate::fonts::text_width(&text, 13.0));
        let t = (v - scale_lo) / safe_span;
        if horizontal {
            let x = (x0 as f64 + t * (x1 - x0) as f64).round() as i32;
            area.draw(&PathElement::new(
                vec![(x, y1), (x, y1 + 4)],
                frame.stroke_width(1),
            ))?;
            draw_label(
                area,
                (0, 0),
                (x, y1 + 8),
                &text,
                RGBAColor(0, 0, 0, 1.0),
                13.0,
                "center",
                "top",
                None,
                0.0,
                line_scale,
                family,
            )?;
        } else {
            let y = (y0 as f64 + (1.0 - t) * (y1 - y0) as f64).round() as i32;
            area.draw(&PathElement::new(
                vec![(x0 - 4, y), (x0, y)],
                frame.stroke_width(1),
            ))?;
            draw_label(
                area,
                (0, 0),
                (x1 + 6, y),
                &text,
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
        if horizontal {
            draw_label(
                area,
                (0, 0),
                ((x0 + x1) / 2, y1 + 30),
                label,
                RGBAColor(0, 0, 0, 1.0),
                14.0,
                "center",
                "top",
                None,
                0.0,
                line_scale,
                family,
            )?;
        } else {
            // Matplotlib puts the colorbar label on the right of its tick text,
            // rotated a quarter turn and centred on the strip.
            let label_x = (x1 + 6 + widest_tick.ceil() as i32 + 16).min(w as i32 - 4);
            draw_label(
                area,
                (0, 0),
                (label_x, (y0 + y1) / 2),
                label,
                RGBAColor(0, 0, 0, 1.0),
                14.0,
                "center",
                "center",
                None,
                90.0,
                line_scale,
                family,
            )?;
        }
    }
    Ok(())
}
