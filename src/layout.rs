use crate::model::Panel;

fn raw_range(it: impl Iterator<Item = f64>) -> (f64, f64) {
    let mut lo = f64::INFINITY;
    let mut hi = f64::NEG_INFINITY;
    for v in it.filter(|v| v.is_finite()) {
        lo = lo.min(v);
        hi = hi.max(v);
    }
    if !lo.is_finite() || !hi.is_finite() {
        (0.0, 1.0)
    } else {
        (lo, hi)
    }
}

pub(crate) fn range(it: impl Iterator<Item = f64>) -> (f64, f64) {
    let (lo, hi) = raw_range(it);
    if lo < hi {
        (lo, hi)
    } else {
        (lo - 1.0, lo + 1.0)
    }
}

/// Matplotlib's default 5% autoscale margin on each side of the data range.
///
/// Mirrors `matplotlib.transforms.nonsingular` followed by the margin
/// expansion in `Axes.autoscale_view`: a degenerate range is first widened by
/// 5% of its magnitude (or to `[-0.05, 0.05]` at zero), then the usual 5%
/// margin is applied to the resulting span.
pub(crate) fn padded_range(lo: f64, hi: f64) -> (f64, f64) {
    const MARGIN: f64 = 0.05;
    if !lo.is_finite() || !hi.is_finite() {
        return (0.0, 1.0);
    }
    let (lo, hi) = if lo == hi {
        let pad = if lo == 0.0 { MARGIN } else { lo.abs() * MARGIN };
        (lo - pad, hi + pad)
    } else {
        (lo, hi)
    };
    let pad = (hi - lo) * MARGIN;
    (lo - pad, hi + pad)
}

/// Final bounds for one axis.
///
/// Explicit limits are used verbatim; otherwise the raw data extent gets
/// matplotlib's default 5% autoscale margin.
pub(crate) fn axis_bounds(extent: (f64, f64), explicit: Option<(f64, f64)>) -> (f64, f64) {
    explicit.unwrap_or_else(|| padded_range(extent.0, extent.1))
}

/// Raw data ranges for a panel: series values plus image extents. Explicit
/// limits are applied later by [`axis_bounds`], after any log transform.
pub(crate) fn panel_ranges(p: &Panel) -> (f64, f64, f64, f64) {
    let mut xs: Vec<f64> = Vec::new();
    let mut ys: Vec<f64> = Vec::new();
    for s in &p.series {
        xs.extend(s.x.as_array().iter().copied());
        ys.extend(s.y.as_array().iter().copied());
    }
    for im in &p.images {
        let (l, r, b, t) = im.4;
        xs.extend([l, r]);
        ys.extend([b, t]);
    }
    for sc in &p.scatter {
        xs.extend(sc.x.as_array().iter().copied());
        ys.extend(sc.y.as_array().iter().copied());
    }
    // Matplotlib autoscales quiver on the arrow tails only; the arrows may
    // extend past the data limits.
    for arrow in &p.arrows {
        xs.extend(arrow.x.as_array().iter().copied());
        ys.extend(arrow.y.as_array().iter().copied());
    }
    for bars in &p.bars {
        let (l, w) = (bars.left.as_array(), bars.width.as_array());
        let (b, h) = (bars.bottom.as_array(), bars.height.as_array());
        for i in 0..l.len().min(w.len()) {
            xs.extend([l[i], l[i] + w[i]]);
        }
        for i in 0..b.len().min(h.len()) {
            ys.extend([b[i], b[i] + h[i]]);
        }
    }
    for band in &p.bands {
        xs.extend(band.x.as_array().iter().copied());
        ys.extend(band.y.as_array().iter().copied());
    }
    for (x, y, ylo, yhi, xlo, xhi, _, _) in &p.errors {
        let (ya, yb) = (ylo.as_array(), yhi.as_array());
        let (xa, xb) = (xlo.as_array(), xhi.as_array());
        let (xs_v, ys_v) = (x.as_array(), y.as_array());
        let yz = ya.iter().zip(yb.iter());
        let xz = xa.iter().zip(xb.iter());
        let it = xs_v.iter().zip(ys_v.iter());
        for ((xv, yv), ((lo, hi), (xl, xh))) in it.zip(yz.zip(xz)) {
            xs.extend([*xv - *xl, *xv + *xh]);
            ys.extend([*yv - *lo, *yv + *hi]);
        }
    }
    for c in &p.contours {
        let (x, y) = (c.0.as_array(), c.1.as_array());
        if let (Some(a), Some(b)) = (x.first(), x.last()) {
            xs.extend([*a, *b]);
        }
        if let (Some(a), Some(b)) = (y.first(), y.last()) {
            ys.extend([*a, *b]);
        }
    }
    for patch in &p.patches {
        match patch.kind.as_str() {
            "rect" => {
                xs.extend([patch.x, patch.x + patch.width]);
                ys.extend([patch.y, patch.y + patch.height]);
            }
            "circle" => {
                xs.extend([patch.x - patch.width, patch.x + patch.width]);
                ys.extend([patch.y - patch.width, patch.y + patch.width]);
            }
            _ => {
                for pair in patch.points.as_chunks::<2>().0 {
                    xs.push(pair[0]);
                    ys.push(pair[1]);
                }
            }
        }
    }
    for coll in &p.collections {
        for pair in coll.points.as_chunks::<2>().0 {
            xs.push(pair[0]);
            ys.push(pair[1]);
        }
        for seg in &coll.segments {
            for pair in seg.as_chunks::<2>().0 {
                xs.push(pair[0]);
                ys.push(pair[1]);
            }
        }
    }
    if xs.is_empty() {
        xs = vec![0.0, 1.0];
    }
    if ys.is_empty() {
        ys = vec![0.0, 1.0];
    }
    let (x0, x1) = raw_range(xs.into_iter());
    let (y0, y1) = raw_range(ys.into_iter());
    (x0, x1, y0, y1)
}

/// Roughly `target` evenly spaced values on a 1/2/2.5/5/10 x 10^k step.
///
/// The step is the candidate whose ratio to `span / target` is closest, so a
/// span of 17.6 with eight requested ticks uses 2 rather than 5 and a 1.96
/// span uses 0.25 rather than 0.2, as Matplotlib's `MaxNLocator` does. Only
/// steps whose labels fit the budget are considered.
pub(crate) fn nice_ticks(lo: f64, hi: f64, target: usize) -> Vec<f64> {
    if hi <= lo || !lo.is_finite() || !hi.is_finite() {
        return Vec::new();
    }
    let raw = (hi - lo) / target.max(1) as f64;
    let mag = 10f64.powf(raw.log10().floor());
    let mut step = 10.0 * mag;
    let mut best = f64::INFINITY;
    // Matplotlib's AutoLocator steps: 1, 2, 2.5, 5, 10 per decade.
    for norm in [1.0, 2.0, 2.5, 5.0, 10.0] {
        let candidate = norm * mag;
        let count =
            ((hi / candidate + 1e-9).floor() - (lo / candidate - 1e-9).ceil() + 1.0) as usize;
        if count <= target + 1 {
            let score = (candidate / raw).ln().abs();
            if score < best {
                best = score;
                step = candidate;
            }
        }
    }
    // Multiply an integer index by the step rather than adding it repeatedly:
    // accumulation left values like -5.55e-17 where Matplotlib prints 0.
    let mut index = (lo / step).ceil();
    let mut out = Vec::new();
    while index * step <= hi + step * 1e-9 && out.len() < 50 {
        out.push(index * step);
        index += 1.0;
    }
    out
}

/// Tick positions in chart space (log axes already transformed).
pub(crate) fn auto_ticks(lo: f64, hi: f64, log: bool) -> Vec<f64> {
    if log {
        let (start, end) = (lo.ceil(), hi.floor());
        if end >= start && end - start <= 12.0 {
            let mut out = Vec::new();
            let mut k = start as i64;
            while (k as f64) <= end {
                out.push(k as f64);
                k += 1;
            }
            if !out.is_empty() {
                return out;
            }
        }
    }
    nice_ticks(lo, hi, 8)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn padded_range_adds_five_percent_on_each_side() {
        assert_eq!(padded_range(0.0, 10.0), (-0.5, 10.5));
    }

    #[test]
    fn axis_bounds_honors_explicit_limits_without_padding() {
        assert_eq!(axis_bounds((0.0, 10.0), Some((2.0, 6.0))), (2.0, 6.0));
        assert_eq!(axis_bounds((5.0, 5.0), Some((1.0, 2.0))), (1.0, 2.0));
    }

    #[test]
    fn nice_ticks_uses_the_densest_step_within_the_budget() {
        // A 17.6 span with eight ticks fits 2s (nine labels); 5s would leave
        // three, which is what the twin sample used to show.
        assert_eq!(
            nice_ticks(11.2, 28.8, 8),
            vec![12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0]
        );
    }

    #[test]
    fn nice_ticks_uses_quarter_steps_for_a_two_unit_span() {
        assert_eq!(
            nice_ticks(-0.1, 2.1, 8),
            vec![0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
        );
    }

    #[test]
    fn auto_ticks_uses_eight_ticks_for_a_wide_range() {
        assert_eq!(
            auto_ticks(0.0, 3500.0, false),
            vec![0.0, 500.0, 1000.0, 1500.0, 2000.0, 2500.0, 3000.0, 3500.0]
        );
    }

    #[test]
    fn axis_bounds_pads_automatic_limits() {
        assert_eq!(axis_bounds((0.0, 10.0), None), (-0.5, 10.5));
        assert_eq!(axis_bounds((5.0, 5.0), None), (4.725, 5.275));
    }

    #[test]
    fn padded_range_expands_flat_data_symmetrically() {
        // Matplotlib widens the degenerate interval first, then adds the margin.
        let (lo, hi) = padded_range(0.0, 0.0);
        assert!((lo + 0.055).abs() < 1e-12 && (hi - 0.055).abs() < 1e-12);
        let (lo, hi) = padded_range(5.0, 5.0);
        assert!((lo - 4.725).abs() < 1e-12 && (hi - 5.275).abs() < 1e-12);
        let (lo, hi) = padded_range(-5.0, -5.0);
        assert!((lo + 5.275).abs() < 1e-12 && (hi + 4.725).abs() < 1e-12);
    }
}
