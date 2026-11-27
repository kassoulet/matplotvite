//! Line, bar, histogram, error-bar, fill and violin artists.

use super::*;

impl Axes<'_> {
    /// Draw a line series. `x` and `y` must be non-empty and the same length.
    pub fn plot(&mut self, x: &[f64], y: &[f64]) -> Result<&mut Self, ApiError> {
        check_xy(x, y)?;
        let color = self.next_color();
        self.push_series(line_series(x, y, color));
        Ok(self)
    }

    /// Draw a scatter series. `x` and `y` must be non-empty and the same length.
    pub fn scatter(&mut self, x: &[f64], y: &[f64]) -> Result<&mut Self, ApiError> {
        check_xy(x, y)?;
        let color = self.next_color();
        self.panel.scatter.push(Scatter {
            x: OwnedArray1::from(x.to_vec()),
            y: OwnedArray1::from(y.to_vec()),
            sizes: OwnedArray1::from(vec![36.0; x.len()]),
            values: None,
            cmap: Cmap::parse("viridis"),
            clim: None,
            colors: vec![color],
            marker: Marker::Circle,
            alpha: 1.0,
            label: String::new(),
        });
        self.last = Some(LastArtist::Scatter(self.panel.scatter.len() - 1));
        self.sequence
            .push(LastArtist::Scatter(self.panel.scatter.len() - 1));
        Ok(self)
    }

    /// Draw vertical bars centred on `x`, with heights from `height`.
    pub fn bar(&mut self, x: &[f64], height: &[f64]) -> Result<&mut Self, ApiError> {
        check_xy(x, height)?;
        let color = self.next_color();
        self.panel.bars.push(Bar {
            left: OwnedArray1::from(x.iter().map(|value| value - 0.4).collect::<Vec<_>>()),
            bottom: OwnedArray1::from(vec![0.0; x.len()]),
            width: OwnedArray1::from(vec![0.8; x.len()]),
            height: OwnedArray1::from(height.to_vec()),
            colors: vec![color],
            edgecolor: None,
            alpha: None,
            label: String::new(),
        });
        self.last = Some(LastArtist::Bar(self.panel.bars.len() - 1));
        self.sequence
            .push(LastArtist::Bar(self.panel.bars.len() - 1));
        Ok(self)
    }

    /// Bin `values` into `bins` equal-width bars.
    pub fn hist(&mut self, values: &[f64], bins: usize) -> Result<&mut Self, ApiError> {
        if values.is_empty() || bins == 0 {
            return Err(ApiError::InvalidArgument(
                "hist needs at least one value and one bin".into(),
            ));
        }
        if values.iter().any(|value| !value.is_finite()) {
            return Err(ApiError::InvalidArgument(
                "hist values must be finite".into(),
            ));
        }
        let mut lo = f64::INFINITY;
        let mut hi = f64::NEG_INFINITY;
        for &value in values {
            lo = lo.min(value);
            hi = hi.max(value);
        }
        if lo == hi {
            lo -= 0.5;
            hi += 0.5;
        }
        let width = (hi - lo) / bins as f64;
        let mut counts = vec![0.0; bins];
        for &value in values {
            let index = ((value - lo) / width).floor() as isize;
            counts[index.clamp(0, bins as isize - 1) as usize] += 1.0;
        }
        let left: Vec<f64> = (0..bins).map(|index| lo + index as f64 * width).collect();
        let color = self.next_color();
        self.panel.bars.push(Bar {
            left: OwnedArray1::from(left),
            bottom: OwnedArray1::from(vec![0.0; bins]),
            width: OwnedArray1::from(vec![width; bins]),
            height: OwnedArray1::from(counts),
            colors: vec![color],
            edgecolor: None,
            alpha: None,
            label: String::new(),
        });
        self.last = Some(LastArtist::Bar(self.panel.bars.len() - 1));
        self.sequence
            .push(LastArtist::Bar(self.panel.bars.len() - 1));
        Ok(self)
    }

    /// Fill between two curves sharing the same x coordinates.
    pub fn fill_between(
        &mut self,
        x: &[f64],
        lower: &[f64],
        upper: &[f64],
    ) -> Result<&mut Self, ApiError> {
        check_xy(x, lower)?;
        check_xy(x, upper)?;
        let color = self.next_color();
        let mut xs = Vec::with_capacity(x.len() * 2 + 1);
        let mut ys = Vec::with_capacity(x.len() * 2 + 1);
        xs.extend_from_slice(x);
        xs.extend(x.iter().rev().copied());
        ys.extend_from_slice(lower);
        ys.extend(upper.iter().rev().copied());
        xs.push(x[0]);
        ys.push(lower[0]);
        self.push_band(Band {
            x: OwnedArray1::from(xs),
            y: OwnedArray1::from(ys),
            color,
            alpha: Some(0.3),
            label: String::new(),
            cells: 0,
            cell_colors: String::new(),
            gid: String::new(),
        });
        Ok(self)
    }

    /// Draw violins from precomputed statistics, as `Axes.violin`.
    ///
    /// Each body spans half its width in density units, mirrors the outline
    /// around `position`, and draws the min/max/centre extrema bars. All
    /// bodies in one call share the next cycle colour, like Matplotlib.
    pub fn violin(&mut self, stats: &[ViolinStat]) -> Result<&mut Self, ApiError> {
        for stat in stats {
            if stat.coords.is_empty() {
                return Err(ApiError::InvalidArgument(
                    "violin coords and vals must be non-empty".into(),
                ));
            }
            stats_core::validate_violin(&stat.coords, &stat.vals, stat.position, stat.width)
                .map_err(|err| ApiError::InvalidArgument(err.message().into()))?;
            if !(stat.min.is_finite() && stat.max.is_finite()) {
                return Err(ApiError::InvalidArgument(
                    "violin min and max must be finite".into(),
                ));
            }
        }
        let color = self.next_color();
        for stat in stats {
            let outline = stats_core::violin_outline(
                &stat.coords,
                &stat.vals,
                stat.position,
                stat.width,
                false,
                stats_core::ViolinSide::Both,
            )
            .map_err(|err| ApiError::InvalidArgument(err.message().into()))?;
            self.push_band(Band {
                x: OwnedArray1::from(outline.xs),
                y: OwnedArray1::from(outline.ys),
                color,
                alpha: Some(0.3),
                label: String::new(),
                cells: 0,
                cell_colors: String::new(),
                gid: String::new(),
            });
            let half = 0.25 * stat.width;
            let span = [stat.position - half, stat.position + half];
            self.stat_line(&span, &[stat.max, stat.max], color);
            self.stat_line(&span, &[stat.min, stat.min], color);
            self.stat_line(
                &[stat.position, stat.position],
                &[stat.min, stat.max],
                color,
            );
        }
        self.last = None;
        Ok(self)
    }

    /// Expand the autoscaled limits by a fraction of the data span.
    ///
    /// Applies to the artists added so far; call it after plotting, like the
    /// view limits `savefig` renders.
    pub fn margins(&mut self, x: f64, y: f64) -> &mut Self {
        let (x0, x1, y0, y1) = matplotvite_core::layout::panel_ranges(self.panel);
        if !(x0.is_finite() && x1.is_finite() && y0.is_finite() && y1.is_finite()) {
            return self;
        }
        self.panel.x.lim = Some(stats_core::expand_limits(x0, x1, x));
        self.panel.y.lim = Some(stats_core::expand_limits(y0, y1, y));
        self
    }

    fn stat_line(&mut self, x: &[f64], y: &[f64], color: Color) {
        self.push_series(line_series(x, y, color));
    }

    /// Draw horizontal bars centred on `y`, with lengths from `width`.
    pub fn barh(&mut self, y: &[f64], width: &[f64]) -> Result<&mut Self, ApiError> {
        check_xy(y, width)?;
        let color = self.next_color();
        self.panel.bars.push(Bar {
            left: OwnedArray1::from(vec![0.0; y.len()]),
            bottom: OwnedArray1::from(y.iter().map(|value| value - 0.4).collect::<Vec<_>>()),
            width: OwnedArray1::from(width.to_vec()),
            height: OwnedArray1::from(vec![0.8; y.len()]),
            colors: vec![color],
            edgecolor: None,
            alpha: None,
            label: String::new(),
        });
        self.last = Some(LastArtist::Bar(self.panel.bars.len() - 1));
        self.sequence
            .push(LastArtist::Bar(self.panel.bars.len() - 1));
        Ok(self)
    }

    /// Draw symmetric error bars around `x`/`y`.
    pub fn errorbar(&mut self, x: &[f64], y: &[f64], yerr: &[f64]) -> Result<&mut Self, ApiError> {
        check_xy(x, y)?;
        check_xy(x, yerr)?;
        let color = self.next_color();
        self.panel.errors.push((
            OwnedArray1::from(x.to_vec()),
            OwnedArray1::from(y.to_vec()),
            OwnedArray1::from(yerr.to_vec()),
            OwnedArray1::from(yerr.to_vec()),
            OwnedArray1::from(vec![0.0; x.len()]),
            OwnedArray1::from(vec![0.0; x.len()]),
            color,
            3.5,
        ));
        self.last = None;
        Ok(self)
    }
}
