//! Patch and collection drawing, including the dense marker overlay.

use super::*;

#[allow(clippy::too_many_arguments)]
pub(super) fn draw_collection_section<DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &ChartContext<'_, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    tx: &FX,
    ty: &FY,
    entries: &mut Vec<LegendEntry>,
    raster_scatter: bool,
    overlays: &mut Vec<String>,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
{
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
    Ok(())
}
