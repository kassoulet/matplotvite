use crate::model::Panel;

pub(crate) fn range(it: impl Iterator<Item = f64>) -> (f64, f64) {
    let mut lo = f64::INFINITY;
    let mut hi = f64::NEG_INFINITY;
    for v in it.filter(|v| v.is_finite()) {
        lo = lo.min(v);
        hi = hi.max(v);
    }
    if !lo.is_finite() || !hi.is_finite() {
        (0.0, 1.0)
    } else if lo < hi {
        (lo, hi)
    } else {
        (lo - 1.0, lo + 1.0)
    }
}

/// Data ranges for a panel: series values plus image extents, unless pinned.
pub(crate) fn panel_ranges(p: &Panel<'_>) -> (f64, f64, f64, f64) {
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
    let (x0, x1) = p.xlim.unwrap_or_else(|| range(xs.into_iter()));
    let (y0, y1) = p.ylim.unwrap_or_else(|| range(ys.into_iter()));
    (x0, x1, y0, y1)
}

/// Roughly `target` evenly spaced values on a 1/2/5 x 10^k step.
pub(crate) fn nice_ticks(lo: f64, hi: f64, target: usize) -> Vec<f64> {
    if hi <= lo || !lo.is_finite() || !hi.is_finite() {
        return Vec::new();
    }
    let raw = (hi - lo) / target.max(1) as f64;
    let mag = 10f64.powf(raw.log10().floor());
    let norm = raw / mag;
    let step = if norm <= 1.0 {
        1.0
    } else if norm <= 2.0 {
        2.0
    } else if norm <= 5.0 {
        5.0
    } else {
        10.0
    } * mag;
    let mut value = (lo / step).ceil() * step;
    let mut out = Vec::new();
    while value <= hi + step * 1e-9 && out.len() < 50 {
        out.push(value);
        value += step;
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
    nice_ticks(lo, hi, 6)
}
