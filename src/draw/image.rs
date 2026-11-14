//! Panel image placement, split from the main drawing pipeline.

use super::*;

/// Place the panel's embedded images, either as bitmap elements in the direct
/// raster path or as data-URI PNG overlays in the SVG path.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_panel_images<DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &ChartContext<'_, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    tx: FX,
    ty: FY,
    base: (i32, i32),
    draw_images: bool,
    overlays: &mut Vec<String>,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
{
    let chart_area = chart.plotting_area();
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
    Ok(())
}
