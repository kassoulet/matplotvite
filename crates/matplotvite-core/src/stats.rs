//! Shared statistics geometry: violin bodies and autoscale margins.
//!
//! The Python facade and the native builder draw the same violins and expand
//! the same autoscaled limits, so both call into this module instead of
//! keeping two copies of the arithmetic.

/// Failure modes shared by the violin geometry and its front ends.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StatsError {
    /// `coords` and `vals` must be the same length.
    LengthMismatch,
    /// Positions, widths and coordinates must be finite.
    NonFinite,
    /// Densities must be finite and non-negative.
    NegativeDensity,
}

impl StatsError {
    /// Stable message used by the Python and Rust front ends.
    pub fn message(self) -> &'static str {
        match self {
            Self::LengthMismatch => "violin `coords` and `vals` must have the same length",
            Self::NonFinite => "violin `coords`, `position` and `width` must be finite",
            Self::NegativeDensity => "violin `vals` must be finite and non-negative",
        }
    }
}

impl std::fmt::Display for StatsError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.message())
    }
}

impl std::error::Error for StatsError {}

/// Which half of the body a violin draws.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ViolinSide {
    /// Mirror the density around the position.
    Both,
    /// Only the low side (`left`/`low` in Matplotlib).
    Low,
    /// Only the high side (`right`/`high` in Matplotlib).
    High,
}

impl ViolinSide {
    /// Parse Matplotlib's `side` spellings.
    pub fn parse(name: &str) -> Option<Self> {
        match name {
            "both" => Some(Self::Both),
            "left" | "low" => Some(Self::Low),
            "right" | "high" => Some(Self::High),
            _ => None,
        }
    }
}

/// A violin body in data coordinates, ready to append as a filled band.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct ViolinOutline {
    /// X coordinates of the closed outline.
    pub xs: Vec<f64>,
    /// Y coordinates of the closed outline.
    pub ys: Vec<f64>,
}

/// Check the inputs both front ends require for a violin body.
pub fn validate_violin(
    coords: &[f64],
    vals: &[f64],
    position: f64,
    width: f64,
) -> Result<(), StatsError> {
    if coords.len() != vals.len() {
        return Err(StatsError::LengthMismatch);
    }
    if !(position.is_finite() && width.is_finite()) || !coords.iter().all(|c| c.is_finite()) {
        return Err(StatsError::NonFinite);
    }
    if !vals.iter().all(|v| v.is_finite() && *v >= 0.0) {
        return Err(StatsError::NegativeDensity);
    }
    Ok(())
}

/// Build the mirrored (or one-sided) outline for one violin body.
///
/// `vals` are raw densities; the outline is normalised to the body's peak and
/// scaled to half of `width`, matching Matplotlib's `Axes.violin`.
pub fn violin_outline(
    coords: &[f64],
    vals: &[f64],
    position: f64,
    width: f64,
    horizontal: bool,
    side: ViolinSide,
) -> Result<ViolinOutline, StatsError> {
    validate_violin(coords, vals, position, width)?;
    let outline = if coords.is_empty() {
        ViolinOutline::default()
    } else {
        let peak = vals.iter().copied().fold(0.0_f64, f64::max);
        let half_width = 0.5 * width;
        let density: Vec<f64> = if peak > 0.0 {
            vals.iter().map(|v| half_width * v / peak).collect()
        } else {
            vec![0.0; vals.len()]
        };
        let first = coords[0];
        let last = coords[coords.len() - 1];
        let mut xs = Vec::with_capacity(coords.len() * 2 + 2);
        let mut ys = Vec::with_capacity(coords.len() * 2 + 2);
        match (horizontal, side) {
            (false, ViolinSide::Both) => {
                xs.extend(density.iter().map(|d| position - d));
                xs.extend(density.iter().rev().map(|d| position + d));
                ys.extend_from_slice(coords);
                ys.extend(coords.iter().rev());
            }
            (true, ViolinSide::Both) => {
                xs.extend_from_slice(coords);
                xs.extend(coords.iter().rev());
                ys.extend(density.iter().map(|d| position - d));
                ys.extend(density.iter().rev().map(|d| position + d));
            }
            (false, ViolinSide::Low) => {
                xs.push(position);
                xs.extend(density.iter().map(|d| position - d));
                xs.push(position);
                ys.push(first);
                ys.extend_from_slice(coords);
                ys.push(last);
            }
            (false, ViolinSide::High) => {
                xs.push(position);
                xs.extend(density.iter().map(|d| position + d));
                xs.push(position);
                ys.push(first);
                ys.extend_from_slice(coords);
                ys.push(last);
            }
            (true, ViolinSide::Low) => {
                xs.push(first);
                xs.extend_from_slice(coords);
                xs.push(last);
                ys.push(position);
                ys.extend(density.iter().map(|d| position - d));
                ys.push(position);
            }
            (true, ViolinSide::High) => {
                xs.push(first);
                xs.extend_from_slice(coords);
                xs.push(last);
                ys.push(position);
                ys.extend(density.iter().map(|d| position + d));
                ys.push(position);
            }
        }
        ViolinOutline { xs, ys }
    };
    Ok(outline)
}

/// Padding for one autoscaled axis: a fraction of the data span.
pub fn margin_pad(lo: f64, hi: f64, fraction: f64) -> f64 {
    (hi - lo) * fraction
}

/// Expand the data span by its margin on both ends.
///
/// The span is ordered first, so the result is always `(low - pad, high + pad)`.
pub fn expand_limits(lo: f64, hi: f64, fraction: f64) -> (f64, f64) {
    let (lo, hi) = (lo.min(hi), lo.max(hi));
    let pad = margin_pad(lo, hi, fraction);
    (lo - pad, hi + pad)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn margin_pad_is_a_fraction_of_the_span() {
        assert_eq!(margin_pad(0.0, 10.0, 0.05), 0.5);
        assert_eq!(expand_limits(0.0, 10.0, 0.05), (-0.5, 10.5));
        assert_eq!(expand_limits(10.0, 0.0, 0.05), (-0.5, 10.5));
    }

    #[test]
    fn violin_outline_mirrors_the_density() {
        let outline =
            violin_outline(&[0.0, 1.0], &[1.0, 0.0], 2.0, 0.4, false, ViolinSide::Both).unwrap();
        assert_eq!(outline.xs, vec![1.8, 2.0, 2.0, 2.2]);
        assert_eq!(outline.ys, vec![0.0, 1.0, 1.0, 0.0]);
    }

    #[test]
    fn violin_outline_closes_one_sided_bodies() {
        let outline =
            violin_outline(&[0.0, 1.0], &[1.0, 0.0], 2.0, 0.4, true, ViolinSide::Low).unwrap();
        assert_eq!(outline.xs, vec![0.0, 0.0, 1.0, 1.0]);
        assert_eq!(outline.ys, vec![2.0, 1.8, 2.0, 2.0]);
    }

    #[test]
    fn violin_validation_rejects_bad_input() {
        assert_eq!(
            violin_outline(&[0.0], &[1.0, 2.0], 0.0, 1.0, false, ViolinSide::Both).unwrap_err(),
            StatsError::LengthMismatch
        );
        assert_eq!(
            violin_outline(&[0.0], &[-1.0], 0.0, 1.0, false, ViolinSide::Both).unwrap_err(),
            StatsError::NegativeDensity
        );
        assert_eq!(
            violin_outline(&[f64::NAN], &[1.0], 0.0, 1.0, false, ViolinSide::Both).unwrap_err(),
            StatsError::NonFinite
        );
    }
}
