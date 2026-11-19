//! Axis-aligned bar rectangles and their legend swatches.

use super::*;

/// Draw bars after filled areas and below line series.
pub(super) fn draw_bars_section<'a, DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &ChartContext<'a, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    tx: &FX,
    ty: &FY,
    entries: &mut Vec<LegendEntry>,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend + 'a,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
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
    Ok(())
}
