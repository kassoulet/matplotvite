//! Manual tick marks, tick labels and colored axis labels.

use super::*;

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
            // Clear the tick labels, whose height grows with `labelsize`.
            let tick_height = text_px(xstyle.labelsize.max(6.0), dpi) * 1.2;
            let y = bottom + (tick_height + 10.0 + size * dpi / 72.0 * 0.5).round() as i32;
            area.draw(&Text::new(p.xlabel.clone(), ((left + right) / 2, y), style))?;
        }
    }
    Ok(())
}
