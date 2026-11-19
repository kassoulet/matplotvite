//! Marching-squares contours and filled-band clipping.

use super::*;

use std::collections::HashMap;

/// One level of a marching-squares pass: iso-line segments in data coordinates.
pub(super) fn contour_segments(
    x: &[f64],
    y: &[f64],
    z: &[f64],
    level: f64,
) -> Vec<((f64, f64), (f64, f64))> {
    let (rows, cols) = (y.len(), x.len());
    let mut out = Vec::new();
    if rows < 2 || cols < 2 || rows.checked_mul(cols) != Some(z.len()) {
        return out;
    }
    let at = |i: usize, j: usize| z[i * cols + j];
    let lerp = |a: f64, b: f64, va: f64, vb: f64| {
        let d = vb - va;
        if d.abs() < f64::EPSILON {
            a
        } else {
            a + (b - a) * ((level - va) / d)
        }
    };
    for i in 0..rows - 1 {
        for j in 0..cols - 1 {
            let (z00, z01, z11, z10) = (at(i, j), at(i, j + 1), at(i + 1, j + 1), at(i + 1, j));
            let idx = (z00 > level) as u8
                | ((z01 > level) as u8) << 1
                | ((z11 > level) as u8) << 2
                | ((z10 > level) as u8) << 3;
            if idx == 0 || idx == 15 {
                continue;
            }
            let top = (lerp(x[j], x[j + 1], z00, z01), y[i]);
            let right = (x[j + 1], lerp(y[i], y[i + 1], z01, z11));
            let bottom = (lerp(x[j], x[j + 1], z10, z11), y[i + 1]);
            let left = (x[j], lerp(y[i], y[i + 1], z00, z10));
            let (a, b) = match idx {
                1 | 14 => (left, top),
                2 | 13 => (top, right),
                3 | 12 => (left, right),
                4 | 11 => (right, bottom),
                5 => (left, top),
                6 | 9 => (top, bottom),
                7 | 8 => (left, bottom),
                10 => (top, right),
                _ => continue,
            };
            out.push((a, b));
            // Saddle cells get a second leg; either diagonal split is valid.
            if idx == 5 {
                out.push((right, bottom));
            } else if idx == 10 {
                out.push((left, bottom));
            }
        }
    }
    out
}

/// Join marching-squares segments that share an endpoint into polylines.
pub(super) fn contour_polylines(segments: Vec<((f64, f64), (f64, f64))>) -> Vec<Vec<(f64, f64)>> {
    if segments.is_empty() {
        return Vec::new();
    }
    let key = |p: (f64, f64)| (p.0.to_bits(), p.1.to_bits());
    let mut incident: HashMap<(u64, u64), Vec<usize>> = HashMap::new();
    for (i, (a, b)) in segments.iter().enumerate() {
        incident.entry(key(*a)).or_default().push(i);
        incident.entry(key(*b)).or_default().push(i);
    }
    let mut used = vec![false; segments.len()];
    let mut lines = Vec::new();
    for i in 0..segments.len() {
        if used[i] {
            continue;
        }
        used[i] = true;
        let (a, b) = segments[i];
        let mut line = vec![a, b];
        // Extend forward from the current tail.
        while let Some(tail_point) = line.last() {
            let tail = key(*tail_point);
            let Some(next) = incident
                .get(&tail)
                .and_then(|ids| ids.iter().copied().find(|&j| !used[j]))
            else {
                break;
            };
            used[next] = true;
            let (c, d) = segments[next];
            let far = if key(c) == tail { d } else { c };
            line.push(far);
        }
        // Extend backward from the current head. Collect the prefix first so
        // long open contours do not pay Vec::insert(0, ..) on every segment.
        let mut prefix = Vec::new();
        while let Some(head_point) = line.first() {
            let head = key(*head_point);
            let Some(previous) = incident
                .get(&head)
                .and_then(|ids| ids.iter().copied().find(|&j| !used[j]))
            else {
                break;
            };
            used[previous] = true;
            let (c, d) = segments[previous];
            let far = if key(c) == head { d } else { c };
            prefix.push(far);
        }
        if !prefix.is_empty() {
            prefix.reverse();
            prefix.extend(line);
            line = prefix;
        }
        if line.len() > 1 {
            lines.push(line);
        }
    }
    lines
}

/// Clip a triangle (x, y, value) to `lo <= value <= hi`.
pub(super) fn clip_band(tri: &[(f64, f64, f64); 3], lo: f64, hi: f64) -> Vec<(f64, f64, f64)> {
    let poly = clip_value(tri.to_vec(), lo, true);
    clip_value(poly, hi, false)
}

/// One Sutherland-Hodgman pass against a level plane.
fn clip_value(poly: Vec<(f64, f64, f64)>, bound: f64, keep_above: bool) -> Vec<(f64, f64, f64)> {
    if poly.is_empty() {
        return poly;
    }
    let inside = |v: f64| if keep_above { v >= bound } else { v <= bound };
    let mut out = Vec::with_capacity(poly.len() + 2);
    for i in 0..poly.len() {
        let cur = poly[i];
        let prev = poly[(i + poly.len() - 1) % poly.len()];
        let (cin, pin) = (inside(cur.2), inside(prev.2));
        if cin != pin {
            out.push(mix_at(prev, cur, bound));
        }
        if cin {
            out.push(cur);
        }
    }
    out
}

fn mix_at(a: (f64, f64, f64), b: (f64, f64, f64), bound: f64) -> (f64, f64, f64) {
    let d = b.2 - a.2;
    let t = if d.abs() < f64::EPSILON {
        0.0
    } else {
        (bound - a.2) / d
    };
    (a.0 + (b.0 - a.0) * t, a.1 + (b.1 - a.1) * t, bound)
}

/// Draw filled contour bands beneath the line series.
pub(super) fn draw_filled_contours<DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &ChartContext<'_, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    tx: &FX,
    ty: &FY,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
{
    // Filled contours sit on the image layer, under the line series.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, z, levels, _linewidths, colors, cmap, filled, alpha) in &p.contours {
            if !*filled || levels.len() < 2 {
                continue;
            }
            let opacity = alpha.clamp(0.0, 1.0);
            let xs: Vec<f64> = x.as_array().iter().copied().collect();
            let ys: Vec<f64> = y.as_array().iter().copied().collect();
            let zs: Vec<f64> = z.as_array().iter().copied().collect();
            let (rows, cols) = (ys.len(), xs.len());
            if rows < 2 || cols < 2 || rows.checked_mul(cols) != Some(zs.len()) {
                continue;
            }
            let bands = levels.len() - 1;
            for band in 0..bands {
                let (lo, hi) = (levels[band], levels[band + 1]);
                let col = (if colors.is_empty() {
                    let c = cmap.sample((band as f64 + 0.5) / bands as f64);
                    RGBAColor(c[0], c[1], c[2], 1.0)
                } else {
                    colors[band % colors.len()].rgba()
                })
                .mix(opacity);
                let map = |px: f64, py: f64| {
                    let (ax, ay) = chart_area.map_coordinate(&(tx(px), ty(py)));
                    (ax - base.0, ay - base.1)
                };
                for i in 0..rows - 1 {
                    let (y0, y1) = (ys[i], ys[i + 1]);
                    let row = &zs[i * cols..i * cols + cols];
                    let next = &zs[(i + 1) * cols..(i + 1) * cols + cols];
                    let mut j = 0;
                    while j + 1 < cols {
                        let (z00, z01) = (row[j], row[j + 1]);
                        let (z10, z11) = (next[j], next[j + 1]);
                        let zmin = z00.min(z01).min(z10).min(z11);
                        let zmax = z00.max(z01).max(z10).max(z11);
                        if zmin > hi || zmax < lo {
                            j += 1;
                            continue;
                        }
                        if zmin >= lo && zmax <= hi {
                            // Cells entirely inside a band tile it exactly, so a
                            // horizontal run collapses into one rectangle. This
                            // is what keeps the rasteriser from walking tens of
                            // thousands of tiny triangle sub-paths.
                            let j0 = j;
                            while j + 1 < cols - 1 {
                                let (a, b) = (row[j + 1], row[j + 2]);
                                let (c, d) = (next[j + 1], next[j + 2]);
                                if a >= lo
                                    && a <= hi
                                    && b >= lo
                                    && b <= hi
                                    && c >= lo
                                    && c <= hi
                                    && d >= lo
                                    && d <= hi
                                {
                                    j += 1;
                                } else {
                                    break;
                                }
                            }
                            // Runs are axis-aligned rectangles; `<rect>` is
                            // considerably cheaper for resvg than a 4-point path.
                            let (xa, ya) = map(xs[j0], y0);
                            let (xb, yb) = map(xs[j + 1], y1);
                            let (xl, xr) = (xa.min(xb), xa.max(xb));
                            let (yt, yb) = (ya.min(yb), ya.max(yb));
                            if xr > xl && yb > yt {
                                area.draw(&Rectangle::new([(xl, yt), (xr, yb)], col.filled()))?;
                            }
                            j += 1;
                            continue;
                        }
                        let p00 = (xs[j], y0, z00);
                        let p01 = (xs[j + 1], y0, z01);
                        let p10 = (xs[j], y1, z10);
                        let p11 = (xs[j + 1], y1, z11);
                        // Split each partial cell into two triangles: a band cut
                        // through a triangle is an exact polygon for piecewise-
                        // linear interpolation.
                        for tri in [[p00, p01, p11], [p00, p11, p10]] {
                            let poly = clip_band(&tri, lo, hi);
                            if poly.len() < 3 {
                                continue;
                            }
                            let pts: Vec<(i32, i32)> =
                                poly.iter().map(|&(px, py, _)| map(px, py)).collect();
                            area.draw(&Polygon::new(pts, col.filled()))?;
                        }
                        j += 1;
                    }
                }
            }
        }
    }
    Ok(())
}

/// Draw contour iso-lines above the line series.
pub(super) fn draw_line_contours<DB, FX, FY>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    chart: &ChartContext<'_, DB, Cartesian2d<RangedCoordf64, RangedCoordf64>>,
    p: &Panel,
    tx: &FX,
    ty: &FY,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB: DrawingBackend,
    DB::ErrorType: 'static,
    FX: Fn(f64) -> f64,
    FY: Fn(f64) -> f64,
{
    // Iso-lines are stroked above the series, one segment per marching-squares cell.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, z, levels, linewidths, colors, cmap, filled, alpha) in &p.contours {
            if *filled || levels.is_empty() {
                continue;
            }
            let opacity = alpha.clamp(0.0, 1.0);
            let xs: Vec<f64> = x.as_array().iter().copied().collect();
            let ys: Vec<f64> = y.as_array().iter().copied().collect();
            let zs: Vec<f64> = z.as_array().iter().copied().collect();
            let (rows, cols) = (ys.len(), xs.len());
            if rows < 2 || cols < 2 || rows.checked_mul(cols) != Some(zs.len()) {
                continue;
            }
            let n = levels.len() as f64;
            for (li, level) in levels.iter().enumerate() {
                let col = (if colors.is_empty() {
                    let t = if n > 1.0 { li as f64 / (n - 1.0) } else { 0.5 };
                    let c = cmap.sample(t);
                    RGBAColor(c[0], c[1], c[2], 1.0)
                } else {
                    colors[li % colors.len()].rgba()
                })
                .mix(opacity);
                let width = linewidths
                    .get(li)
                    .or_else(|| linewidths.first())
                    .copied()
                    .unwrap_or(2.0)
                    .clamp(0.25, 64.0);
                for line in contour_polylines(contour_segments(&xs, &ys, &zs, *level)) {
                    let points: Vec<(i32, i32)> = line
                        .iter()
                        .map(|(x, y)| {
                            let (px, py) = chart_area.map_coordinate(&(tx(*x), ty(*y)));
                            (px - base.0, py - base.1)
                        })
                        .collect();
                    area.draw(&PathElement::new(
                        points,
                        col.stroke_width(width.round().max(1.0) as u32),
                    ))?;
                }
            }
        }
    }
    Ok(())
}
