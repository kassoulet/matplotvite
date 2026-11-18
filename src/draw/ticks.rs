//! Manual tick marks, tick labels and colored axis labels.

use super::polyline::draw_dashed;
use super::text::rotated_style;
use super::*;
use crate::scale::{asinh_inverse, asinh_scale, logit, symlog};

/// One label style for every tick on an axis. Using the widest precision in
/// the tick set keeps whole numbers aligned with fractional neighbours
/// (`0.5, 1.0, 1.5`) instead of mixing `0.5` with `1`.
#[derive(Clone, Copy)]
pub(super) struct TickFormat {
    pub(super) decimals: usize,
    pub(super) scientific: bool,
}

/// Minor tick positions: four intervals per major tick, excluding majors.
pub(super) fn minor_grid_values(major: &[f64], lo: f64, hi: f64) -> Vec<f64> {
    if major.len() < 2 {
        return Vec::new();
    }
    let step = (major[1] - major[0]).abs() / 4.0;
    if !step.is_finite() || step <= 0.0 || !lo.is_finite() || !hi.is_finite() {
        return Vec::new();
    }
    let mut values = Vec::new();
    let mut value = (lo / step).ceil() * step;
    while value <= hi && values.len() < 256 {
        if !major
            .iter()
            .any(|major| (major - value).abs() <= step * 1.0e-6)
        {
            values.push(value);
        }
        value += step;
    }
    values
}

/// Decimal places needed to write every value in `values` without float noise.
fn tick_decimals(values: &[f64]) -> usize {
    values
        .iter()
        .map(|&v| {
            let mut a = v.abs();
            if !a.is_finite() {
                return 0;
            }
            let mut decimals = 0;
            while decimals < 4 && (a - a.round()).abs() > 1e-9 {
                a *= 10.0;
                decimals += 1;
            }
            decimals
        })
        .max()
        .unwrap_or(0)
}

pub(super) fn tick_format(values: &[f64]) -> TickFormat {
    // A single out-of-range magnitude makes the whole axis scientific; mixing
    // plain and scientific labels on one axis is the same inconsistency.
    let scientific = values
        .iter()
        .any(|&v| v != 0.0 && !(1e-3..1e5).contains(&v.abs()));
    TickFormat {
        decimals: tick_decimals(values),
        scientific,
    }
}

/// Tick label for a linear axis: short, without float noise.
pub(super) fn tick_label(v: f64, format: TickFormat) -> String {
    let v = if v == 0.0 { 0.0 } else { v };
    let label = if format.scientific {
        format!("{v:.2e}")
    } else {
        format!("{v:.prec$}", prec = format.decimals)
    };
    label
        .strip_prefix('-')
        .map(|rest| format!("−{rest}"))
        .unwrap_or(label)
}

/// Tick label for a log coordinate: base^v written as a plain number.
pub(super) fn log_label(v: f64, base: f64) -> String {
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

/// Draw ticks, tick labels and styled gridlines for panels whose tick layout is
/// controlled from Python. The plotters mesh still provides the axis frame and
/// descriptions; this only replaces its ticks and grid.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_manual_ticks<DB: DrawingBackend>(
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
    let grid_col = p
        .grid
        .color
        .map(|c| c.rgba())
        .unwrap_or_else(|| color("#b0b0b0"));
    let grid_alpha = p.grid.alpha.unwrap_or(1.0).clamp(0.0, 1.0);
    let grid_w = p.grid.linewidth.unwrap_or(1.0).max(1.0).round() as u32;
    let grid_style = grid_col.mix(grid_alpha).stroke_width(grid_w);
    let grid_dash = p.grid.linestyle.and_then(|style| style.dash_pattern());

    let to_chart_x = |v: f64| {
        if p.x_log {
            v.max(f64::MIN_POSITIVE).log(log_base)
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
    let to_chart_y = |v: f64| {
        if p.y_log {
            v.max(f64::MIN_POSITIVE).log(log_base)
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
    let x_labels = tick_target((right - left).abs() as f64, 55.0);
    let y_labels = tick_target((bottom - top).abs() as f64, 45.0);
    let xs: Vec<f64> = match &p.ticks.xticks {
        Some(v) => v.iter().map(|&v| to_chart_x(v)).collect(),
        None => auto_ticks_for(x0, x1, p.x_log, x_labels),
    };
    let ys: Vec<f64> = match &p.ticks.yticks {
        Some(v) => v.iter().map(|&v| to_chart_y(v)).collect(),
        None => auto_ticks_for(y0, y1, p.y_log, y_labels),
    };
    let xformat = tick_format(&xs);
    let yformat = tick_format(&ys);
    let xlabels: Vec<String> = match (&p.ticks.xticklabels, &p.ticks.xticks) {
        (Some(labels), Some(_)) => (0..xs.len())
            .map(|i| labels.get(i).cloned().unwrap_or_default())
            .collect(),
        _ => xs
            .iter()
            .map(|v| {
                if p.x_log {
                    log_label(*v, log_base)
                } else if p.x_asinh {
                    tick_label(asinh_inverse(*v, p.x_asinh_linear_width), xformat)
                } else {
                    tick_label(*v, xformat)
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
                } else if p.y_asinh {
                    tick_label(asinh_inverse(*v, p.y_asinh_linear_width), yformat)
                } else {
                    tick_label(*v, yformat)
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

    let default_tick = p
        .foreground
        .map(|c| c.rgba())
        .unwrap_or_else(|| color("#000000"));
    let xstyle = &p.ticks.xstyle;
    let xtick_col = xstyle.color.map(|c| c.rgba()).unwrap_or(default_tick);
    let xlabel_col = xstyle.labelcolor.map(|c| c.rgba()).unwrap_or(default_tick);
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
    let ytick_col = ystyle.color.map(|c| c.rgba()).unwrap_or(default_tick);
    let ylabel_col = ystyle.labelcolor.map(|c| c.rgba()).unwrap_or(default_tick);
    let ytick_w = ystyle.width.max(1.0).round() as u32;
    let ytick_len = ystyle.length.max(0.0);
    if side != "top" {
        for (v, label) in ys.iter().zip(ylabels.iter()) {
            let (_, py) = pa.map_coordinate(&(x0, *v));
            let py = py - origin.1;
            let on_right = match p.ticks.yside.as_str() {
                "right" => true,
                "left" => false,
                _ => side == "right",
            };
            let (tick_x, edge_x, label_x, hpos) = if on_right {
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
    let fg = default_tick;
    let ylabel_col = p.ylabel_color.map(|c| c.rgba()).unwrap_or(fg);
    let xlabel_col = p.xlabel_color.map(|c| c.rgba()).unwrap_or(fg);
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
        if (p.ylabel_color.is_some() || p.axes_bounds) && !p.ylabel.is_empty() {
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
            // Clear the tick labels, whose height grows with `labelsize`.
            let tick_height = text_px(xstyle.labelsize.max(6.0), dpi) * 1.2;
            let y = bottom + (tick_height + 10.0 + size * dpi / 72.0 * 0.5).round() as i32;
            area.draw(&Text::new(p.xlabel.clone(), ((left + right) / 2, y), style))?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{tick_format, tick_label};

    #[test]
    fn whole_ticks_keep_the_precision_of_their_fractional_neighbours() {
        let format = tick_format(&[0.5, 1.0, 1.5]);
        assert_eq!(
            [0.5, 1.0, 1.5].map(|v| tick_label(v, format)),
            ["0.5", "1.0", "1.5"]
        );
    }

    #[test]
    fn quarter_ticks_pad_to_two_decimals() {
        let format = tick_format(&[0.0, 0.25, 0.5, 0.75, 1.0]);
        assert_eq!(
            [0.0, 0.25, 0.5, 1.0].map(|v| tick_label(v, format)),
            ["0.00", "0.25", "0.50", "1.00"]
        );
    }

    #[test]
    fn integer_axes_gain_no_decimal_point() {
        let format = tick_format(&[0.0, 500.0, 1000.0, 3500.0]);
        assert_eq!(tick_label(3500.0, format), "3500");
    }

    #[test]
    fn float_noise_does_not_inflate_the_precision() {
        let format = tick_format(&[0.0, 0.1, 0.2, 0.30000000000000004]);
        assert_eq!(tick_label(0.30000000000000004, format), "0.3");
    }

    #[test]
    fn an_axis_uses_scientific_notation_for_every_tick_or_none() {
        let format = tick_format(&[0.0, 200000.0]);
        assert!(format.scientific);
        assert_eq!(tick_label(0.0, format), "0.00e0");
        assert_eq!(tick_label(200000.0, format), "2.00e5");
    }

    #[test]
    fn colorbar_scale_labels_stay_plain_thousands() {
        let format = tick_format(&[0.0, 4000.0, 8000.0]);
        assert!(!format.scientific);
        assert_eq!(tick_label(8000.0, format), "8000");
    }

    #[test]
    fn negative_labels_keep_the_unicode_minus() {
        let format = tick_format(&[-1.0, -0.5, 0.0]);
        assert_eq!(tick_label(-1.0, format), "−1.0");
    }
}
