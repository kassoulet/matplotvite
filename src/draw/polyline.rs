//! Polyline clipping, joins, caps, dashes and point simplification.

use super::*;

/// A corner where matplotlib's round join is visibly different from the
/// backend's union of butt-ended segments. Pixel-quantised dense data has many
/// apparent corners of a pixel or two; those are covered by the stroke itself
/// and must not split the path, or smooth series cost a path per sample.
fn sharp_corner(a: (i32, i32), b: (i32, i32), c: (i32, i32), width: u32) -> bool {
    let half = width as f64 / 2.0;
    if half < 2.0 {
        // Below a few pixels the join geometry is sub-pixel either way.
        return false;
    }
    let d1 = ((b.0 - a.0) as f64, (b.1 - a.1) as f64);
    let d2 = ((c.0 - b.0) as f64, (c.1 - b.1) as f64);
    let (l1, l2) = (
        (d1.0 * d1.0 + d1.1 * d1.1).sqrt(),
        (d2.0 * d2.0 + d2.1 * d2.1).sqrt(),
    );
    if l1 < half || l2 < half {
        return false;
    }
    let cross = d1.0 * d2.1 - d1.1 * d2.0;
    cross.abs() / (l1 * l2) >= 0.2
}

pub(super) fn has_sharp_join(pts: &[(i32, i32)], width: u32) -> bool {
    pts.windows(3)
        .any(|w| sharp_corner(w[0], w[1], w[2], width))
}

/// matplotlib's default `solid_capstyle` is `projecting`: the stroke runs half a
/// line width past each endpoint. The backends end paths with a butt cap, so add
/// the missing half-square at the two ends of the line.
pub(super) fn draw_projected_caps<DB: DrawingBackend, C: Color + Copy>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    pts: &[(i32, i32)],
    col: C,
    width: u32,
    caps: (bool, bool),
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    if pts.len() < 2 || width == 0 {
        return Ok(());
    }
    let half = width as f64 / 2.0;
    let last = pts.len() - 1;
    let ends = [(pts[0], pts[1]), (pts[last], pts[last - 1])];
    for ((end, inward), wanted) in ends.into_iter().zip([caps.0, caps.1]) {
        if !wanted {
            continue;
        }
        let (dx, dy) = ((end.0 - inward.0) as f64, (end.1 - inward.1) as f64);
        let len = (dx * dx + dy * dy).sqrt();
        if !len.is_finite() || len <= 0.0 {
            continue;
        }
        let tip = (
            (end.0 as f64 + dx / len * half).round() as i32,
            (end.1 as f64 + dy / len * half).round() as i32,
        );
        area.draw(&PathElement::new(vec![end, tip], col.stroke_width(width)))?;
    }
    Ok(())
}

/// Clip one pixel-space segment to `(xmin, xmax, ymin, ymax)` with Liang–Barsky,
/// so a line that leaves the axes is cut at the spine instead of drawn over the
/// labels and the neighbouring panels.
fn clip_segment(
    a: (i32, i32),
    b: (i32, i32),
    rect: (f64, f64, f64, f64),
) -> Option<((i32, i32), (i32, i32))> {
    let (xmin, xmax, ymin, ymax) = rect;
    let (ax, ay) = (a.0 as f64, a.1 as f64);
    let (dx, dy) = (b.0 as f64 - ax, b.1 as f64 - ay);
    let (mut t0, mut t1) = (0.0_f64, 1.0_f64);
    for (p, q) in [
        (-dx, ax - xmin),
        (dx, xmax - ax),
        (-dy, ay - ymin),
        (dy, ymax - ay),
    ] {
        if p == 0.0 {
            if q < 0.0 {
                return None;
            }
            continue;
        }
        let r = q / p;
        if p < 0.0 {
            if r > t1 {
                return None;
            }
            t0 = t0.max(r);
        } else {
            if r < t0 {
                return None;
            }
            t1 = t1.min(r);
        }
    }
    let at = |t: f64| {
        let x = (ax + dx * t).round() as i32;
        let y = (ay + dy * t).round() as i32;
        (
            x.clamp(xmin.round() as i32, xmax.round() as i32),
            y.clamp(ymin.round() as i32, ymax.round() as i32),
        )
    };
    Some((at(t0), at(t1)))
}

/// Split a polyline into the runs that stay inside the axes rectangle. An
/// unclipped polyline comes back as one run, unchanged.
pub(super) fn clip_polyline(
    pts: &[(i32, i32)],
    rect: (f64, f64, f64, f64),
) -> Vec<Vec<(i32, i32)>> {
    let mut runs: Vec<Vec<(i32, i32)>> = Vec::new();
    let mut run: Vec<(i32, i32)> = Vec::new();
    for pair in pts.windows(2) {
        match clip_segment(pair[0], pair[1], rect) {
            Some((start, end)) => {
                if run.last() != Some(&start) {
                    if run.len() >= 2 {
                        runs.push(std::mem::take(&mut run));
                    } else {
                        run.clear();
                    }
                    run.push(start);
                }
                run.push(end);
            }
            None => {
                if run.len() >= 2 {
                    runs.push(std::mem::take(&mut run));
                } else {
                    run.clear();
                }
            }
        }
    }
    if run.len() >= 2 {
        runs.push(run);
    }
    runs
}

/// Finish and draw one run of a polyline. The backend already gives every path
/// matplotlib's default `projecting` cap (half a line width past the end), so a
/// run trimmed by that much stops exactly at the point it was trimmed to.
fn stroke_run<DB: DrawingBackend, C: Color + Copy>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    run: &mut Vec<(i32, i32)>,
    col: C,
    width: u32,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let path = std::mem::take(run);
    if path.len() >= 2 {
        area.draw(&PathElement::new(path, col.stroke_width(width)))?;
    }
    Ok(())
}

/// Draw a solid polyline with matplotlib's `solid_joinstyle="round"`: split the
/// path at sharp corners, fill each corner with a disc of the line radius, and
/// trim the split ends so no backend cap overshoots the corner.
pub(super) fn draw_solid_polyline<DB: DrawingBackend, C: Color + Copy>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    pts: &[(i32, i32)],
    col: C,
    width: u32,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let radius = ((width as f64 / 2.0).max(1.0)) as u32;
    let mut run: Vec<(i32, i32)> = vec![pts[0]];
    for i in 1..pts.len() {
        let at_end = i == pts.len() - 1;
        if !at_end && sharp_corner(pts[i - 1], pts[i], pts[i + 1], width) {
            if run.last() != Some(&pts[i]) {
                run.push(pts[i]);
            }
            stroke_run(area, &mut run, col, width)?;
            area.draw(&Circle::new(pts[i], radius, col.filled()))?;
            run.push(pts[i]);
        } else {
            run.push(pts[i]);
        }
    }
    stroke_run(area, &mut run, col, width)
}

/// Stroke a polyline as dashes, in panel-local pixels.
pub(super) fn draw_dashed<DB: DrawingBackend, C: Color>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    pts: &[(i32, i32)],
    col: C,
    width: u32,
    dash: f64,
    gap: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let mut on = true;
    let mut left = dash;
    for pair in pts.windows(2) {
        let (x0, y0) = (pair[0].0 as f64, pair[0].1 as f64);
        let (x1, y1) = (pair[1].0 as f64, pair[1].1 as f64);
        let (dx, dy) = (x1 - x0, y1 - y0);
        let len = (dx * dx + dy * dy).sqrt();
        if len <= 0.0 {
            continue;
        }
        let (ux, uy) = (dx / len, dy / len);
        let mut t = 0.0;
        while t < len {
            let seg = left.min(len - t);
            if on {
                let a = (x0 + ux * t, y0 + uy * t);
                let b = (x0 + ux * (t + seg), y0 + uy * (t + seg));
                area.draw(&PathElement::new(
                    vec![
                        (a.0.round() as i32, a.1.round() as i32),
                        (b.0.round() as i32, b.1.round() as i32),
                    ],
                    col.stroke_width(width),
                ))?;
                // matplotlib's dash join is round: a dash that runs through a
                // polyline vertex gets a disc there.
                if seg >= len - t - 1e-9 && left - seg > 1e-9 {
                    let vertex = (x1.round() as i32, y1.round() as i32);
                    let radius = ((width as f64 / 2.0).max(1.0)) as u32;
                    area.draw(&Circle::new(vertex, radius, col.filled()))?;
                }
            }
            t += seg;
            left -= seg;
            if left <= f64::EPSILON {
                on = !on;
                left = if on { dash } else { gap };
            }
        }
    }
    Ok(())
}

/// Collapse runs of points that share one pixel column to their first, lowest,
/// highest and last points, in path order. The stroke inside a column spans
/// [min, max] and enters and leaves at first/last, so the drawn path is
/// visually unchanged while dense series shrink to at most four points per
/// column, whatever their noise. Cost is O(n); the `tolerance` argument of the
/// old greedy scheme is gone because it kept every point of a noisy series.
pub(super) fn simplify_polyline(
    n: usize,
    point: impl Fn(usize) -> (f64, f64),
    map: impl Fn(&(f64, f64)) -> (f64, f64),
) -> Vec<(f64, f64)> {
    if n < 3 {
        return (0..n).map(point).collect();
    }
    let mut out = Vec::new();
    // Indices of the current column's first, min-y, max-y and last points.
    let mut col: Option<(f64, [usize; 4], f64, f64)> = None;
    fn flush(out: &mut Vec<(f64, f64)>, point: &impl Fn(usize) -> (f64, f64), idx: [usize; 4]) {
        let mut idx = idx;
        idx.sort_unstable();
        let mut prev = usize::MAX;
        for i in idx {
            if i != prev {
                out.push(point(i));
                prev = i;
            }
        }
    }
    for i in 0..n {
        let p = point(i);
        let (x, y) = map(&p);
        if !x.is_finite() || !y.is_finite() {
            // Keep non-finite points so the undrawn gaps stay where they were.
            if let Some((_, idx, _, _)) = col.take() {
                flush(&mut out, &point, idx);
            }
            out.push(p);
            continue;
        }
        let column = x.floor();
        match &mut col {
            Some((c, idx, lo, hi)) if *c == column => {
                if y < *lo {
                    *lo = y;
                    idx[1] = i;
                }
                if y > *hi {
                    *hi = y;
                    idx[2] = i;
                }
                idx[3] = i;
            }
            _ => {
                if let Some((_, idx, _, _)) = col.take() {
                    flush(&mut out, &point, idx);
                }
                col = Some((column, [i; 4], y, y));
            }
        }
    }
    if let Some((_, idx, _, _)) = col {
        flush(&mut out, &point, idx);
    }
    out
}

#[cfg(test)]
mod clip_tests {
    use super::{clip_polyline, clip_segment, simplify_polyline};
    use proptest::prelude::*;

    const RECT: (f64, f64, f64, f64) = (0.0, 100.0, 0.0, 50.0);

    #[test]
    fn inside_segments_are_untouched() {
        assert_eq!(
            clip_segment((10, 10), (90, 40), RECT),
            Some(((10, 10), (90, 40)))
        );
    }

    #[test]
    fn segments_are_cut_at_the_axes_edge() {
        assert_eq!(
            clip_segment((-10, 25), (110, 25), RECT),
            Some(((0, 25), (100, 25)))
        );
        assert_eq!(
            clip_segment((50, -10), (50, 60), RECT),
            Some(((50, 0), (50, 50)))
        );
    }

    #[test]
    fn fully_outside_segments_are_dropped() {
        assert_eq!(clip_segment((-10, -10), (-5, 60), RECT), None);
    }

    #[test]
    fn a_polyline_is_split_around_an_outside_gap() {
        let runs = clip_polyline(&[(50, 25), (50, 60), (60, 60), (60, 25)], RECT);
        assert_eq!(runs.len(), 2);
        assert_eq!(runs[0], vec![(50, 25), (50, 50)]);
        assert_eq!(runs[1], vec![(60, 50), (60, 25)]);
    }

    proptest! {
        #[test]
        fn simplification_keeps_endpoints_and_order(
            points in prop::collection::vec((-1000i32..1000, -1000i32..1000), 0..400)
        ) {
            let points: Vec<(f64, f64)> = points
                .iter()
                .map(|(x, y)| (*x as f64, *y as f64))
                .collect();
            let out = simplify_polyline(points.len(), |index| points[index], |point| *point);
            if points.is_empty() {
                prop_assert!(out.is_empty());
            } else {
                prop_assert_eq!(out.first(), points.first());
                prop_assert_eq!(out.last(), points.last());
                let mut cursor = 0usize;
                for expected in &out {
                    while cursor < points.len() && points[cursor] != *expected {
                        cursor += 1;
                    }
                    prop_assert!(cursor < points.len());
                    cursor += 1;
                }
                let mut columns: Vec<i32> = points.iter().map(|(x, _)| *x as i32).collect();
                columns.sort_unstable();
                columns.dedup();
                prop_assert!(out.len() <= columns.len() * 4);
            }
        }
    }
}
