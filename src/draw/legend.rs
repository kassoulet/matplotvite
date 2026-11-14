//! Legend obstacle collection and placement.

use super::*;

/// Collect the pixel geometry of drawn artists, then place the custom or
/// plotters-managed legend. Keeping this together guarantees `loc="best"` sees
/// exactly the layers that were already drawn.
#[allow(clippy::too_many_arguments)]
pub(super) fn draw_legend_section<'a, DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &mut ChartContext<'a, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    entries: &mut [LegendEntry],
    tx: &FX,
    ty: &FY,
    x0: f64,
    x1: f64,
    y0: f64,
    y1: f64,
    fg: RGBAColor,
    dpi: f64,
    custom_legend: bool,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend + 'a,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
{
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
            entries,
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
    Ok(())
}
