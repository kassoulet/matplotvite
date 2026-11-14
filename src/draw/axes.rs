//! Axis, grid and spine drawing for one panel.

use super::*;

/// Draw the mesh, tick labels, gridlines, spines and manual ticks.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_axes<'a, DB>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &mut ChartContext<'a, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    (x0, x1, y0, y1): (f64, f64, f64, f64),
    label_size: u32,
    desc_size: u32,
    xs_for_grid: &[f64],
    ys_for_grid: &[f64],
    base: f64,
    twin_gap_px: i32,
    dpi: f64,
    fg: RGBAColor,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend + 'a,
    DB::ErrorType: 'static,
{
    let manual = p.ticks.xticks.is_some()
        || p.ticks.yticks.is_some()
        || p.ticks.xstyle.is_custom()
        || p.ticks.ystyle.is_custom()
        || !p.twin.is_empty()
        || p.xlabel_color.is_some()
        || p.ylabel_color.is_some()
        || (p.grid.show
            && (p.grid.color.is_some()
                || p.grid.linewidth.is_some()
                || p.grid.alpha.is_some()
                || p.grid.linestyle.is_some()));
    let twin_side = p.twin.as_str();
    if !p.axis_off {
        // Plotters asks the formatter for one value at a time, so fix the
        // axis-wide precision up front from the ticks it will use.
        let xformat = tick_format(&auto_ticks(x0, x1, p.x_log));
        let yformat = tick_format(&auto_ticks(y0, y1, p.y_log));
        let x_fmt = move |v: &f64| {
            if manual || p.ticks.hide_xlabels {
                String::new()
            } else if p.x_log {
                log_label(*v, base)
            } else {
                tick_label(*v, xformat)
            }
        };
        let y_fmt = move |v: &f64| {
            if manual || p.ticks.hide_ylabels {
                String::new()
            } else if p.y_log {
                log_label(*v, base)
            } else {
                tick_label(*v, yformat)
            }
        };
        let mut mesh = chart.configure_mesh();
        if !p.grid.show {
            mesh.disable_mesh();
        } else if p.grid.color.is_some() || p.grid.linewidth.is_some() || p.grid.alpha.is_some() {
            let gc = color(p.grid.color.as_deref().unwrap_or("#b0b0b0"));
            let alpha = p.grid.alpha.unwrap_or(1.0).clamp(0.0, 1.0);
            // `grid.linewidth` is in points; a 0.8 pt default is 1 px at
            // 100 dpi and 2 px at 200 dpi.
            let width = (p.grid.linewidth.unwrap_or(0.8) * dpi / 72.0)
                .round()
                .max(1.0) as u32;
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
        let spine_width = (0.8 * dpi / 72.0).round().max(1.0) as u32;
        mesh.label_style((p.font_family.as_str(), label_size).into_font().color(&fg))
            .axis_desc_style((p.font_family.as_str(), desc_size).into_font().color(&fg))
            .axis_style(fg.stroke_width(spine_width))
            .x_labels(8)
            .y_labels(8)
            .x_desc(x_desc)
            .y_desc(y_desc)
            .x_label_formatter(&x_fmt)
            .y_label_formatter(&y_fmt)
            .draw()?;
        if p.grid.minor_show && !p.x_log && !p.y_log {
            // Plotters only draws major gridlines, so add the minor ones in
            // the same style. They sit under the series, like the mesh.
            let base = area.get_base_pixel();
            let pa = chart.plotting_area();
            let tl = pa.map_coordinate(&(x0, y1));
            let br = pa.map_coordinate(&(x1, y0));
            let (left, top) = (tl.0 - base.0, tl.1 - base.1);
            let (right, bottom) = (br.0 - base.0, br.1 - base.1);
            let gc = color(p.grid.minor_color.as_deref().unwrap_or("#b0b0b0"));
            let alpha = p.grid.minor_alpha.unwrap_or(1.0).clamp(0.0, 1.0);
            let width = (p.grid.minor_linewidth.unwrap_or(0.8) * dpi / 72.0)
                .round()
                .max(1.0) as u32;
            let style = gc.mix(alpha).stroke_width(width);
            if p.grid.axis != "y" {
                for value in minor_grid_values(xs_for_grid, x0, x1) {
                    let (px, _) = pa.map_coordinate(&(value, y0));
                    area.draw(&PathElement::new(
                        vec![(px - base.0, top), (px - base.0, bottom)],
                        style,
                    ))?;
                }
            }
            if p.grid.axis != "x" {
                for value in minor_grid_values(ys_for_grid, y0, y1) {
                    let (_, py) = pa.map_coordinate(&(x0, value));
                    area.draw(&PathElement::new(
                        vec![(left, py - base.1), (right, py - base.1)],
                        style,
                    ))?;
                }
            }
            // Minor tick marks outside the axes, matching the grid spacing.
            let tick = fg.stroke_width(width);
            if p.grid.axis != "y" {
                for value in minor_grid_values(xs_for_grid, x0, x1) {
                    let (px, _) = pa.map_coordinate(&(value, y0));
                    let px = px - base.0;
                    area.draw(&PathElement::new(
                        vec![(px, bottom), (px, bottom + 3)],
                        tick,
                    ))?;
                }
            }
            if p.grid.axis != "x" {
                for value in minor_grid_values(ys_for_grid, y0, y1) {
                    let (_, py) = pa.map_coordinate(&(x0, value));
                    let py = py - base.1;
                    area.draw(&PathElement::new(vec![(left - 3, py), (left, py)], tick))?;
                }
            }
        }
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
                fg.stroke_width(spine_width),
            ))?;
            area.draw(&PathElement::new(
                vec![(right, top), (right, bottom)],
                fg.stroke_width(spine_width),
            ))?;
        }
        if manual {
            let axis_side = match twin_side {
                "y" => "right",
                "x" => "top",
                _ => "",
            };
            super::ticks::draw_manual_ticks(
                area,
                chart,
                p,
                (x0, x1, y0, y1),
                base,
                axis_side,
                twin_gap_px,
                dpi,
            )?;
        }
    }
    Ok(())
}
