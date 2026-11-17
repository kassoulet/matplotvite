//! Marching-squares contours and filled-band clipping.

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
