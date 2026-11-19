//! Quiver vector fields and their filled arrow geometry.

use crate::model::QuiverUnits;

use super::*;

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

/// Draw quiver arrows after the data layers and before text.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_quiver_section<DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &ChartContext<'_, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    tx: &FX,
    ty: &FY,
    x0: f64,
    x1: f64,
    y0: f64,
    y1: f64,
    dpi: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
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
    Ok(())
}
