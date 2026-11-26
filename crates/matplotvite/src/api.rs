//! Native Rust plotting API.
//!
//! This is the first crate-level slice of the matplotlib-style builder. It
//! covers the priority methods from `TRACE.md` and renders through the same
//! panel pipeline as the Python facade. The API takes slices and copies them
//! into the renderer's owned panel records, keeping the render path independent
//! of caller lifetimes.

use std::fmt;
use std::path::Path;

use ndarray::{Array2, ArrayView2};

use matplotvite_core::color::{Cmap, Color};
use matplotvite_core::fonts::SANS_FAMILY;
use matplotvite_core::model::{
    Arrow, ArtistCollection, ArtistPatch, Band, Bar, Grid, Legend, Marker, OwnedArray1,
    OwnedArray2, OwnedArrayD, Panel, QuiverUnits, RenderOptions, Scatter, Series, TickStyle,
};
use matplotvite_core::render::render_figure;

const COLORS: [&str; 10] = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf",
];

/// Axis scale accepted by [`Axes::xscale`] and [`Axes::yscale`].
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Scale {
    /// Evenly spaced data values.
    Linear,
    /// Logarithmic axis with the given base (Matplotlib's default is 10).
    Log { base: f64 },
    /// Linear inside `+-linthresh`, logarithmic outside it.
    Symlog { linthresh: f64 },
    /// Probabilities mapped through `ln(p / (1 - p))`.
    Logit,
    /// Smooth log-like axis that is linear within `+-linear_width`.
    Asinh { linear_width: f64 },
}

impl Scale {
    /// Matplotlib's base-10 log scale.
    pub fn log() -> Self {
        Self::Log { base: 10.0 }
    }
}

/// Tick label and tick-mark styling, passed to [`Axes::tick_params`].
#[derive(Clone, Debug)]
pub struct TickParams {
    pub labelsize: f64,
    pub length: f64,
    pub width: f64,
    pub rotation: f64,
    pub color: Option<String>,
    pub labelcolor: Option<String>,
}

impl Default for TickParams {
    fn default() -> Self {
        Self {
            labelsize: 10.0,
            length: 3.5,
            width: 1.0,
            rotation: 0.0,
            color: None,
            labelcolor: None,
        }
    }
}

/// Legend placement and styling, passed to [`Axes::legend_options`].
#[derive(Clone, Debug)]
pub struct LegendOptions {
    pub loc: String,
    pub ncol: usize,
    pub frameon: bool,
    pub fontsize: f64,
    pub title: String,
    pub title_fontsize: Option<f64>,
    pub anchor: Option<(f64, f64)>,
}

impl Default for LegendOptions {
    fn default() -> Self {
        Self {
            loc: "best".to_string(),
            ncol: 1,
            frameon: true,
            fontsize: 10.0,
            title: String::new(),
            title_fontsize: None,
            anchor: None,
        }
    }
}

/// Grid styling, passed to [`Axes::grid_options`].
#[derive(Clone, Debug)]
pub struct GridOptions {
    pub show: bool,
    /// `"both"`, `"x"` or `"y"`.
    pub axis: String,
    pub color: Option<String>,
    pub linewidth: Option<f64>,
    pub linestyle: Option<String>,
    pub alpha: Option<f64>,
    pub minor_show: bool,
    pub minor_color: Option<String>,
    pub minor_linewidth: Option<f64>,
    pub minor_alpha: Option<f64>,
}

impl Default for GridOptions {
    fn default() -> Self {
        Self {
            show: true,
            axis: "both".to_string(),
            color: None,
            linewidth: None,
            linestyle: None,
            alpha: None,
            minor_show: false,
            minor_color: None,
            minor_linewidth: None,
            minor_alpha: None,
        }
    }
}

/// A native plotting failure.
#[derive(Debug)]
pub enum ApiError {
    /// A caller supplied data or layout argument was invalid.
    InvalidArgument(String),
    /// The renderer could not draw or encode the figure.
    Render(String),
    /// The output path could not be written.
    Io(String),
}

impl fmt::Display for ApiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidArgument(message) | Self::Render(message) | Self::Io(message) => {
                f.write_str(message)
            }
        }
    }
}

impl std::error::Error for ApiError {}

/// A figure canvas containing one or more axes.
pub struct Figure {
    size: (u32, u32),
    dpi: f64,
    grid: (usize, usize),
    panels: Vec<Panel>,
}

impl Figure {
    /// Create a figure with the given pixel dimensions at 100 dpi.
    pub fn new(width: u32, height: u32) -> Self {
        Self {
            size: (width, height),
            dpi: 100.0,
            grid: (1, 1),
            panels: Vec::new(),
        }
    }

    /// Set the output resolution used when a panel is created.
    pub fn with_dpi(mut self, dpi: f64) -> Self {
        self.dpi = dpi;
        self
    }

    /// Create an axes at a precise figure-fraction rectangle, like
    /// `Figure.add_axes`. The rectangle is the plotting area, so it does not
    /// reserve extra room for labels.
    pub fn add_axes(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
    ) -> Result<Axes<'_>, ApiError> {
        if !(width > 0.0 && height > 0.0) || !(width.is_finite() && height.is_finite()) {
            return Err(ApiError::InvalidArgument(
                "add_axes width and height must be positive".into(),
            ));
        }
        if !(x.is_finite() && y.is_finite()) {
            return Err(ApiError::InvalidArgument(
                "add_axes bounds must be finite".into(),
            ));
        }
        let mut panel = new_panel(0, self.dpi);
        panel.bounds = Some((x, y, width, height));
        panel.axes_bounds = true;
        self.panels.push(panel);
        let index = self.panels.len() - 1;
        let panel = &mut self.panels[index];
        Ok(Axes {
            panel,
            last: None,
            color: 0,
            sequence: Vec::new(),
        })
    }

    /// Create an axes at a zero-based row-major position in a `rows` by `cols`
    /// grid.
    pub fn subplot(
        &mut self,
        rows: usize,
        cols: usize,
        index: usize,
    ) -> Result<Axes<'_>, ApiError> {
        if rows == 0 || cols == 0 {
            return Err(ApiError::InvalidArgument(
                "subplot rows and columns must be positive".into(),
            ));
        }
        let cells = rows
            .checked_mul(cols)
            .ok_or_else(|| ApiError::InvalidArgument("subplot grid is too large".into()))?;
        if index >= cells {
            return Err(ApiError::InvalidArgument(format!(
                "subplot index {index} is outside a {rows}x{cols} grid"
            )));
        }
        self.grid = (rows, cols);
        self.panels.push(new_panel(index, self.dpi));
        let slot = self.panels.len() - 1;
        let panel = &mut self.panels[slot];
        Ok(Axes {
            panel,
            last: None,
            color: 0,
            sequence: Vec::new(),
        })
    }

    /// Encode the figure as PNG, SVG, PDF, WebP, or EPS bytes.
    pub fn to_bytes(&self, format: &str) -> Result<Vec<u8>, ApiError> {
        let options = RenderOptions {
            format: format.to_string(),
            dpi: self.dpi,
            ..Default::default()
        };
        render_figure(self.size, self.grid, &self.panels, options)
            .map_err(|error| ApiError::Render(error.into_message()))
    }

    /// Encode the figure and write it to `path`.
    pub fn savefig(&self, path: impl AsRef<Path>) -> Result<(), ApiError> {
        let path = path.as_ref();
        let format = path
            .extension()
            .and_then(|extension| extension.to_str())
            .ok_or_else(|| {
                ApiError::InvalidArgument(format!(
                    "output path {} needs a png, svg, pdf, webp, or eps extension",
                    path.display()
                ))
            })?;
        let bytes = self.to_bytes(format)?;
        std::fs::write(path, bytes).map_err(|error| ApiError::Io(error.to_string()))
    }
}

/// A mutable handle to one panel while a figure is being built.
pub struct Axes<'a> {
    panel: &'a mut Panel,
    last: Option<LastArtist>,
    color: usize,
    /// Artist creation order, so the legend lists handles like matplotlib.
    sequence: Vec<LastArtist>,
}

#[derive(Clone, Copy)]
enum LastArtist {
    Series(usize),
    Scatter(usize),
    Bar(usize),
    Band(usize),
    Patch(usize),
    Collection(usize),
}

/// One violin body built from precomputed density statistics.
pub struct ViolinStat {
    /// Centre of the violin on the categorical axis.
    pub position: f64,
    /// Total width assigned to the body.
    pub width: f64,
    /// Coordinates of the density outline (the vertical axis).
    pub coords: Vec<f64>,
    /// Density at each `coords` entry, normalised to the body's peak.
    pub vals: Vec<f64>,
    /// Low end of the extrema bar.
    pub min: f64,
    /// High end of the extrema bar.
    pub max: f64,
}

impl Axes<'_> {
    /// Draw a line series. `x` and `y` must be non-empty and the same length.
    pub fn plot(&mut self, x: &[f64], y: &[f64]) -> Result<&mut Self, ApiError> {
        check_xy(x, y)?;
        let color = self.next_color();
        self.panel.series.push(Series {
            x: OwnedArray1::from(x.to_vec()),
            y: OwnedArray1::from(y.to_vec()),
            color,
            linewidth: 1.5,
            markersize: 6.0,
            mew: 1.0,
            ..Default::default()
        });
        self.last = Some(LastArtist::Series(self.panel.series.len() - 1));
        self.sequence
            .push(LastArtist::Series(self.panel.series.len() - 1));
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

    /// Display a 2-D scalar array as an image with an equal aspect ratio.
    pub fn imshow(&mut self, values: ArrayView2<'_, f64>) -> Result<&mut Self, ApiError> {
        let (rows, cols) = (values.shape()[0], values.shape()[1]);
        if rows == 0 || cols == 0 {
            return Err(ApiError::InvalidArgument(
                "imshow needs a non-empty 2-D array".into(),
            ));
        }
        self.panel.images.push((
            OwnedArrayD::from_array(
                Array2::from_shape_vec((rows, cols), values.iter().copied().collect())
                    .map_err(|e| ApiError::InvalidArgument(e.to_string()))?
                    .into_dyn(),
            ),
            Cmap::parse("viridis"),
            None,
            None,
            (-0.5, cols as f64 - 0.5, rows as f64 - 0.5, -0.5),
            true,
            1.0,
            "nearest".to_string(),
        ));
        self.panel.aspect = Some(1.0);
        self.panel.xlim = Some((-0.5, cols as f64 - 0.5));
        self.panel.ylim = Some((rows as f64 - 0.5, -0.5));
        self.last = None;
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
        self.panel.bands.push(Band {
            x: OwnedArray1::from(xs),
            y: OwnedArray1::from(ys),
            color,
            alpha: Some(0.3),
            label: String::new(),
            cells: 0,
            cell_colors: String::new(),
            gid: String::new(),
        });
        self.last = Some(LastArtist::Band(self.panel.bands.len() - 1));
        self.sequence
            .push(LastArtist::Band(self.panel.bands.len() - 1));
        Ok(self)
    }

    /// Draw violins from precomputed statistics, as `Axes.violin`.
    ///
    /// Each body spans half its width in density units, mirrors the outline
    /// around `position`, and draws the min/max/centre extrema bars. All
    /// bodies in one call share the next cycle colour, like Matplotlib.
    pub fn violin(&mut self, stats: &[ViolinStat]) -> Result<&mut Self, ApiError> {
        for stat in stats {
            if stat.coords.is_empty() || stat.coords.len() != stat.vals.len() {
                return Err(ApiError::InvalidArgument(
                    "violin coords and vals must be non-empty and the same length".into(),
                ));
            }
            if !(stat.position.is_finite() && stat.width.is_finite()) {
                return Err(ApiError::InvalidArgument(
                    "violin position and width must be finite".into(),
                ));
            }
            if !(stat.min.is_finite() && stat.max.is_finite()) {
                return Err(ApiError::InvalidArgument(
                    "violin min and max must be finite".into(),
                ));
            }
            if !stat.coords.iter().all(|c| c.is_finite())
                || !stat.vals.iter().all(|v| v.is_finite() && *v >= 0.0)
            {
                return Err(ApiError::InvalidArgument(
                    "violin coords must be finite and vals finite and non-negative".into(),
                ));
            }
        }
        let color = self.next_color();
        for stat in stats {
            let peak = stat.vals.iter().copied().fold(0.0_f64, f64::max);
            let scale = if peak > 0.0 {
                0.5 * stat.width / peak
            } else {
                0.0
            };
            let mut xs = Vec::with_capacity(stat.coords.len() * 2);
            let mut ys = Vec::with_capacity(stat.coords.len() * 2);
            for (coord, value) in stat.coords.iter().zip(&stat.vals) {
                xs.push(stat.position - value * scale);
                ys.push(*coord);
            }
            for (coord, value) in stat.coords.iter().zip(&stat.vals).rev() {
                xs.push(stat.position + value * scale);
                ys.push(*coord);
            }
            self.panel.bands.push(Band {
                x: OwnedArray1::from(xs),
                y: OwnedArray1::from(ys),
                color,
                alpha: Some(0.3),
                label: String::new(),
                cells: 0,
                cell_colors: String::new(),
                gid: String::new(),
            });
            self.sequence
                .push(LastArtist::Band(self.panel.bands.len() - 1));
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
        let (x0, x1) = (x0.min(x1), x0.max(x1));
        let (y0, y1) = (y0.min(y1), y0.max(y1));
        if !(x0.is_finite() && x1.is_finite() && y0.is_finite() && y1.is_finite()) {
            return self;
        }
        let pad_x = (x1 - x0) * x;
        let pad_y = (y1 - y0) * y;
        self.panel.xlim = Some((x0 - pad_x, x1 + pad_x));
        self.panel.ylim = Some((y0 - pad_y, y1 + pad_y));
        self
    }

    fn stat_line(&mut self, x: &[f64], y: &[f64], color: Color) {
        self.panel.series.push(Series {
            x: OwnedArray1::from(x.to_vec()),
            y: OwnedArray1::from(y.to_vec()),
            color,
            linewidth: 1.5,
            markersize: 6.0,
            mew: 1.0,
            ..Default::default()
        });
        self.last = Some(LastArtist::Series(self.panel.series.len() - 1));
        self.sequence
            .push(LastArtist::Series(self.panel.series.len() - 1));
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

    /// Draw arrows whose tails are `(x, y)` and whose components are `(u, v)`.
    pub fn quiver(
        &mut self,
        x: &[f64],
        y: &[f64],
        u: &[f64],
        v: &[f64],
    ) -> Result<&mut Self, ApiError> {
        check_xy(x, y)?;
        check_xy(x, u)?;
        check_xy(x, v)?;
        let color = self.next_color();
        self.panel.arrows.push(Arrow {
            x: OwnedArray1::from(x.to_vec()),
            y: OwnedArray1::from(y.to_vec()),
            u: OwnedArray1::from(u.to_vec()),
            v: OwnedArray1::from(v.to_vec()),
            colors: vec![color],
            scale: None,
            units: QuiverUnits::Width,
            scale_units: None,
            angles: "uv".to_string(),
            width: None,
            headwidth: 3.0,
            headlength: 5.0,
            headaxislength: 4.5,
            pivot: "tail".to_string(),
        });
        self.last = None;
        Ok(self)
    }

    /// Draw contour lines through a 2-D value grid.
    pub fn contour(
        &mut self,
        x: &[f64],
        y: &[f64],
        z: ArrayView2<'_, f64>,
        levels: &[f64],
    ) -> Result<&mut Self, ApiError> {
        self.push_contour(x, y, z, levels, false)
    }

    /// Draw filled contours through a 2-D value grid.
    pub fn contourf(
        &mut self,
        x: &[f64],
        y: &[f64],
        z: ArrayView2<'_, f64>,
        levels: &[f64],
    ) -> Result<&mut Self, ApiError> {
        self.push_contour(x, y, z, levels, true)
    }

    fn push_contour(
        &mut self,
        x: &[f64],
        y: &[f64],
        z: ArrayView2<'_, f64>,
        levels: &[f64],
        filled: bool,
    ) -> Result<&mut Self, ApiError> {
        let (rows, cols) = (z.shape()[0], z.shape()[1]);
        if rows == 0 || cols == 0 {
            return Err(ApiError::InvalidArgument(
                "contour needs a non-empty 2-D array".into(),
            ));
        }
        if x.len() != cols || y.len() != rows {
            return Err(ApiError::InvalidArgument(format!(
                "contour grid is {cols}x{rows}, got {} x values and {} y values",
                x.len(),
                y.len()
            )));
        }
        let provided = levels.to_vec();
        let levels = if provided.is_empty() {
            let mut lo = f64::INFINITY;
            let mut hi = f64::NEG_INFINITY;
            for value in z.iter().copied().filter(|value| value.is_finite()) {
                lo = lo.min(value);
                hi = hi.max(value);
            }
            if lo >= hi {
                lo -= 0.5;
                hi += 0.5;
            }
            (0..7)
                .map(|index| lo + (hi - lo) * index as f64 / 6.0)
                .collect()
        } else {
            provided
        };
        self.panel.contours.push((
            OwnedArray1::from(x.to_vec()),
            OwnedArray1::from(y.to_vec()),
            OwnedArray2::from_array(
                Array2::from_shape_vec((rows, cols), z.iter().copied().collect())
                    .map_err(|e| ApiError::InvalidArgument(e.to_string()))?,
            ),
            levels.clone(),
            vec![1.5; levels.len()],
            Vec::new(),
            Cmap::parse("viridis"),
            filled,
            1.0,
        ));
        self.last = None;
        Ok(self)
    }

    /// Place data-space text with the default size, colour and alignment.
    pub fn text(&mut self, x: f64, y: f64, text: impl Into<String>) -> &mut Self {
        self.text_styled(x, y, text, 10.0, "black", ("left", "baseline"))
    }

    /// Place data-space text with an explicit size, colour and alignment.
    pub fn text_styled(
        &mut self,
        x: f64,
        y: f64,
        text: impl Into<String>,
        size: f64,
        color: &str,
        align: (&str, &str),
    ) -> &mut Self {
        let (ha, va) = align;
        let family = self.panel.font_family.clone();
        self.panel.texts.push((
            x,
            y,
            text.into(),
            Color::parse(color),
            size,
            ha.to_string(),
            va.to_string(),
            None,
            0.0,
            family,
            (0.0, 0.0),
        ));
        self
    }

    /// Annotate `xy`, optionally with the text placed at `xytext`.
    pub fn annotate(
        &mut self,
        text: impl Into<String>,
        xy: (f64, f64),
        xytext: Option<(f64, f64)>,
    ) -> &mut Self {
        let family = self.panel.font_family.clone();
        self.panel
            .annotations
            .push((text.into(), xy, xytext, Color::parse("black"), 10.0, family));
        self
    }

    /// Set explicit x tick positions, keeping the automatic labels.
    pub fn xticks(&mut self, ticks: &[f64]) -> &mut Self {
        self.panel.ticks.xticks = Some(ticks.to_vec());
        self
    }

    /// Set explicit x tick positions and labels.
    pub fn xticks_with_labels(
        &mut self,
        ticks: &[f64],
        labels: &[&str],
    ) -> Result<&mut Self, ApiError> {
        check_labels(ticks, labels)?;
        self.panel.ticks.xticks = Some(ticks.to_vec());
        self.panel.ticks.xticklabels = Some(labels.iter().map(|value| value.to_string()).collect());
        Ok(self)
    }

    /// Set explicit y tick positions, keeping the automatic labels.
    pub fn yticks(&mut self, ticks: &[f64]) -> &mut Self {
        self.panel.ticks.yticks = Some(ticks.to_vec());
        self
    }

    /// Set explicit y tick positions and labels.
    pub fn yticks_with_labels(
        &mut self,
        ticks: &[f64],
        labels: &[&str],
    ) -> Result<&mut Self, ApiError> {
        check_labels(ticks, labels)?;
        self.panel.ticks.yticks = Some(ticks.to_vec());
        self.panel.ticks.yticklabels = Some(labels.iter().map(|value| value.to_string()).collect());
        Ok(self)
    }

    /// Apply tick styling to both axes.
    pub fn tick_params(&mut self, params: &TickParams) -> &mut Self {
        apply_tick_style(&mut self.panel.ticks.xstyle, params);
        apply_tick_style(&mut self.panel.ticks.ystyle, params);
        self
    }

    /// Apply tick styling to the x axis only.
    pub fn xtick_params(&mut self, params: &TickParams) -> &mut Self {
        apply_tick_style(&mut self.panel.ticks.xstyle, params);
        self
    }

    /// Apply tick styling to the y axis only.
    pub fn ytick_params(&mut self, params: &TickParams) -> &mut Self {
        apply_tick_style(&mut self.panel.ticks.ystyle, params);
        self
    }

    /// Set the x-axis scale.
    pub fn xscale(&mut self, scale: Scale) -> &mut Self {
        set_scale(self.panel, scale, true);
        self
    }

    /// Set the y-axis scale.
    pub fn yscale(&mut self, scale: Scale) -> &mut Self {
        set_scale(self.panel, scale, false);
        self
    }

    /// Hide the axes frame, ticks and tick labels while keeping the data.
    pub fn axis_off(&mut self) -> &mut Self {
        self.panel.axis_off = true;
        self
    }

    /// Set the data-unit aspect ratio (`1.0` is `"equal"`).
    pub fn aspect(&mut self, aspect: f64) -> Result<&mut Self, ApiError> {
        if aspect <= 0.0 || !aspect.is_finite() {
            return Err(ApiError::InvalidArgument(
                "aspect must be a positive finite number".into(),
            ));
        }
        self.panel.aspect = Some(aspect);
        Ok(self)
    }

    /// Widen the data limits to reach the aspect ratio instead of shrinking the
    /// plotting rectangle (`set_adjustable("datalim")`).
    pub fn aspect_datalim(&mut self, enabled: bool) -> &mut Self {
        self.panel.aspect_datalim = enabled;
        self
    }

    /// Apply grid styling and visibility.
    pub fn grid_options(&mut self, options: &GridOptions) -> &mut Self {
        let grid = Grid {
            show: options.show,
            color: options.color.as_deref().map(Color::parse),
            linewidth: options.linewidth,
            alpha: options.alpha,
            linestyle: options
                .linestyle
                .as_deref()
                .and_then(matplotvite_core::model::LineStyle::parse),
            axis: options.axis.clone(),
            minor_show: options.minor_show,
            minor_color: options.minor_color.as_deref().map(Color::parse),
            minor_linewidth: options.minor_linewidth,
            minor_alpha: options.minor_alpha,
        };
        self.panel.grid = grid;
        self
    }

    /// Apply legend placement and styling to the labelled artists.
    pub fn legend_options(&mut self, options: &LegendOptions) -> &mut Self {
        let fontsize = options.fontsize;
        self.panel.legend = Legend {
            show: true,
            loc: options.loc.clone(),
            family: self.panel.font_family.clone(),
            ncol: options.ncol,
            frameon: options.frameon,
            fontsize,
            title: options.title.clone(),
            title_fontsize: options.title_fontsize.unwrap_or(fontsize * 1.1),
            anchor: options.anchor,
            order: self.artist_labels(),
            ..Default::default()
        };
        self
    }

    /// Set the title font size, in points.
    pub fn title_size(&mut self, size: f64) -> &mut Self {
        self.panel.title_size = Some(size);
        self
    }

    /// Set the x-axis label font size, in points.
    pub fn xlabel_size(&mut self, size: f64) -> &mut Self {
        self.panel.xlabel_size = Some(size);
        self
    }

    /// Set the y-axis label font size, in points.
    pub fn ylabel_size(&mut self, size: f64) -> &mut Self {
        self.panel.ylabel_size = Some(size);
        self
    }

    /// Set the axes background colour.
    pub fn facecolor(&mut self, color: &str) -> &mut Self {
        self.panel.facecolor = Some(Color::parse(color));
        self
    }

    /// Set the colour used for titles, labels and ticks.
    pub fn foreground(&mut self, color: &str) -> &mut Self {
        self.panel.foreground = Some(Color::parse(color));
        self
    }

    /// Set explicit x- and y-axis label colours.
    pub fn label_colors(&mut self, x: &str, y: &str) -> &mut Self {
        self.panel.xlabel_color = Some(Color::parse(x));
        self.panel.ylabel_color = Some(Color::parse(y));
        self
    }

    /// Add a vertical gradient strip for `cmap` over `vmin..vmax`.
    pub fn colorbar(&mut self, cmap: &str, vmin: f64, vmax: f64) -> &mut Self {
        let vmax = if vmax > vmin { vmax } else { vmin + 1.0 };
        self.panel.colorbar = Some((
            Cmap::parse(cmap),
            vmin,
            vmax,
            String::new(),
            false,
            None,
            10.0,
            "vertical".to_string(),
            "neither".to_string(),
            false,
            0.05,
        ));
        self
    }

    /// Add a data-space rectangle.
    pub fn rectangle(&mut self, x: f64, y: f64, width: f64, height: f64) -> &mut Self {
        self.push_patch("rect", x, y, width, height, Vec::new())
    }

    /// Add a data-space circle.
    pub fn circle(&mut self, x: f64, y: f64, radius: f64) -> &mut Self {
        self.push_patch("circle", x, y, radius, 0.0, Vec::new())
    }

    /// Add a closed polygon; `points` are data-space `(x, y)` vertices.
    pub fn polygon(&mut self, points: &[(f64, f64)]) -> &mut Self {
        let mut flat = Vec::with_capacity(points.len() * 2);
        for &(x, y) in points {
            flat.push(x);
            flat.push(y);
        }
        self.push_patch("polygon", 0.0, 0.0, 0.0, 0.0, flat)
    }

    fn push_patch(
        &mut self,
        kind: &str,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        points: Vec<f64>,
    ) -> &mut Self {
        let color = self.next_color();
        self.panel.patches.push(ArtistPatch {
            kind: kind.to_string(),
            x,
            y,
            width,
            height,
            points,
            facecolor: Some(color),
            edgecolor: None,
            linewidth: 1.0,
            alpha: 1.0,
            gid: String::new(),
            label: String::new(),
        });
        self.last = Some(LastArtist::Patch(self.panel.patches.len() - 1));
        self.sequence
            .push(LastArtist::Patch(self.panel.patches.len() - 1));
        self
    }

    /// Add a collection of unconnected polylines, each given as flat `x, y`
    /// pairs.
    pub fn line_collection(&mut self, segments: &[Vec<f64>]) -> &mut Self {
        let color = self.next_color();
        self.panel.collections.push(ArtistCollection {
            points: Vec::new(),
            segments: segments.to_vec(),
            sizes: Vec::new(),
            colors: vec![color],
            marker: Marker::None,
            alpha: 1.0,
            linewidth: 1.5,
            label: String::new(),
        });
        self.last = Some(LastArtist::Collection(self.panel.collections.len() - 1));
        self.sequence
            .push(LastArtist::Collection(self.panel.collections.len() - 1));
        self
    }

    /// Display a 2-D scalar array with an explicit colormap and value range.
    pub fn imshow_cmap(
        &mut self,
        values: ArrayView2<'_, f64>,
        cmap: &str,
        vmin: Option<f64>,
        vmax: Option<f64>,
    ) -> Result<&mut Self, ApiError> {
        let (rows, cols) = (values.shape()[0], values.shape()[1]);
        if rows == 0 || cols == 0 {
            return Err(ApiError::InvalidArgument(
                "imshow needs a non-empty 2-D array".into(),
            ));
        }
        self.panel.images.push((
            OwnedArrayD::from_array(
                Array2::from_shape_vec((rows, cols), values.iter().copied().collect())
                    .map_err(|e| ApiError::InvalidArgument(e.to_string()))?
                    .into_dyn(),
            ),
            Cmap::parse(cmap),
            vmin,
            vmax,
            (-0.5, cols as f64 - 0.5, rows as f64 - 0.5, -0.5),
            true,
            1.0,
            "nearest".to_string(),
        ));
        self.panel.aspect = Some(1.0);
        self.panel.xlim = Some((-0.5, cols as f64 - 0.5));
        self.panel.ylim = Some((rows as f64 - 0.5, -0.5));
        self.last = None;
        Ok(self)
    }

    /// Set the axes title.
    pub fn title(&mut self, title: impl Into<String>) -> &mut Self {
        self.panel.title = title.into();
        self
    }

    /// Set the x-axis label.
    pub fn xlabel(&mut self, label: impl Into<String>) -> &mut Self {
        self.panel.xlabel = label.into();
        self
    }

    /// Set the y-axis label.
    pub fn ylabel(&mut self, label: impl Into<String>) -> &mut Self {
        self.panel.ylabel = label.into();
        self
    }

    /// Set explicit x limits.
    pub fn xlim(&mut self, lo: f64, hi: f64) -> &mut Self {
        self.panel.xlim = Some((lo, hi));
        self
    }

    /// Set explicit y limits.
    pub fn ylim(&mut self, lo: f64, hi: f64) -> &mut Self {
        self.panel.ylim = Some((lo, hi));
        self
    }

    /// Show a legend for labelled artists.
    pub fn legend(&mut self) -> &mut Self {
        self.panel.legend = Legend {
            show: true,
            loc: "best".to_string(),
            family: self.panel.font_family.clone(),
            fontsize: 10.0,
            title_fontsize: 11.0,
            ncol: 1,
            frameon: true,
            order: self.artist_labels(),
            ..Default::default()
        };
        self
    }

    fn artist_labels(&self) -> Vec<String> {
        let mut entries: Vec<(bool, String)> = self
            .sequence
            .iter()
            .filter_map(|artist| match *artist {
                LastArtist::Series(index) => self
                    .panel
                    .series
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
                LastArtist::Scatter(index) => self
                    .panel
                    .scatter
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
                LastArtist::Bar(index) => self
                    .panel
                    .bars
                    .get(index)
                    .map(|artist| (true, artist.label.as_str())),
                LastArtist::Band(index) => self
                    .panel
                    .bands
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
                LastArtist::Patch(index) => self
                    .panel
                    .patches
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
                LastArtist::Collection(index) => self
                    .panel
                    .collections
                    .get(index)
                    .map(|artist| (false, artist.label.as_str())),
            })
            .filter(|(_, label)| !label.is_empty())
            .map(|(is_bar, label)| (is_bar, label.to_string()))
            .collect();
        // Matplotlib lists bar containers after the other artists, even when
        // the bars were added first.
        entries.sort_by_key(|(is_bar, _)| *is_bar);
        entries.into_iter().map(|(_, label)| label).collect()
    }

    /// Toggle the grid on both axes.
    pub fn grid(&mut self, show: bool) -> &mut Self {
        self.panel.grid.show = show;
        self.panel.grid.axis = "both".to_string();
        self
    }

    /// Set the colour of the most recently added artist.
    pub fn color(&mut self, color: &str) -> &mut Self {
        let color = Color::parse(color);
        match self.last {
            Some(LastArtist::Series(index)) => self.panel.series[index].color = color,
            Some(LastArtist::Scatter(index)) => self.panel.scatter[index].colors = vec![color],
            Some(LastArtist::Bar(index)) => self.panel.bars[index].colors = vec![color],
            Some(LastArtist::Band(index)) => self.panel.bands[index].color = color,
            Some(LastArtist::Patch(index)) => self.panel.patches[index].facecolor = Some(color),
            Some(LastArtist::Collection(index)) => {
                self.panel.collections[index].colors = vec![color]
            }
            None => {}
        }
        self
    }

    /// Set the label of the most recently added artist.
    pub fn label(&mut self, label: impl Into<String>) -> &mut Self {
        let label = label.into();
        match self.last {
            Some(LastArtist::Series(index)) => self.panel.series[index].label = label,
            Some(LastArtist::Scatter(index)) => self.panel.scatter[index].label = label,
            Some(LastArtist::Bar(index)) => self.panel.bars[index].label = label,
            Some(LastArtist::Band(index)) => self.panel.bands[index].label = label,
            Some(LastArtist::Patch(index)) => self.panel.patches[index].label = label,
            Some(LastArtist::Collection(index)) => self.panel.collections[index].label = label,
            None => {}
        }
        self
    }

    /// Set the line width of the most recently added line.
    pub fn linewidth(&mut self, width: f64) -> &mut Self {
        if let Some(LastArtist::Series(index)) = self.last {
            self.panel.series[index].linewidth = width.max(0.0);
        }
        self
    }

    /// Set the marker of the most recently added line or scatter series.
    pub fn marker(&mut self, marker: &str) -> &mut Self {
        let marker = Marker::parse(marker).unwrap_or(Marker::Circle);
        match self.last {
            Some(LastArtist::Series(index)) => self.panel.series[index].marker = marker,
            Some(LastArtist::Scatter(index)) => self.panel.scatter[index].marker = marker,
            _ => {}
        }
        self
    }

    /// Set the opacity of the most recently added artist where supported.
    pub fn alpha(&mut self, alpha: f64) -> &mut Self {
        let alpha = alpha.clamp(0.0, 1.0);
        match self.last {
            Some(LastArtist::Series(index)) => self.panel.series[index].alpha = Some(alpha),
            Some(LastArtist::Scatter(index)) => self.panel.scatter[index].alpha = alpha,
            Some(LastArtist::Bar(index)) => self.panel.bars[index].alpha = Some(alpha),
            Some(LastArtist::Band(index)) => self.panel.bands[index].alpha = Some(alpha),
            Some(LastArtist::Patch(index)) => self.panel.patches[index].alpha = alpha,
            Some(LastArtist::Collection(index)) => self.panel.collections[index].alpha = alpha,
            None => {}
        }
        self
    }

    fn next_color(&mut self) -> Color {
        let value = COLORS[self.color % COLORS.len()];
        self.color += 1;
        Color::parse(value)
    }
}

fn check_xy(x: &[f64], y: &[f64]) -> Result<(), ApiError> {
    if x.is_empty() || x.len() != y.len() {
        return Err(ApiError::InvalidArgument(format!(
            "x and y must be non-empty and the same length, got {} and {}",
            x.len(),
            y.len()
        )));
    }
    Ok(())
}

fn check_labels(ticks: &[f64], labels: &[&str]) -> Result<(), ApiError> {
    if ticks.len() != labels.len() {
        return Err(ApiError::InvalidArgument(format!(
            "ticks and labels must be the same length, got {} and {}",
            ticks.len(),
            labels.len()
        )));
    }
    Ok(())
}

fn apply_tick_style(style: &mut TickStyle, params: &TickParams) {
    style.labelsize = params.labelsize;
    style.length = params.length;
    style.width = params.width;
    style.rotation = params.rotation;
    style.color = params.color.as_deref().map(Color::parse);
    style.labelcolor = params.labelcolor.as_deref().map(Color::parse);
}

fn set_scale(panel: &mut Panel, scale: Scale, x: bool) {
    if x {
        panel.x_log = false;
        panel.x_symlog = false;
        panel.x_logit = false;
        panel.x_asinh = false;
    } else {
        panel.y_log = false;
        panel.y_symlog = false;
        panel.y_logit = false;
        panel.y_asinh = false;
    }
    match scale {
        Scale::Linear => {}
        Scale::Log { base } => {
            if x {
                panel.x_log = true;
            } else {
                panel.y_log = true;
            }
            panel.log_base = if base > 1.0 { base } else { 10.0 };
        }
        Scale::Symlog { linthresh } => {
            let linthresh = linthresh.abs().max(f64::MIN_POSITIVE);
            if x {
                panel.x_symlog = true;
                panel.x_symlog_linthresh = linthresh;
            } else {
                panel.y_symlog = true;
                panel.y_symlog_linthresh = linthresh;
            }
        }
        Scale::Logit => {
            if x {
                panel.x_logit = true;
            } else {
                panel.y_logit = true;
            }
        }
        Scale::Asinh { linear_width } => {
            let width = linear_width.abs().max(f64::MIN_POSITIVE);
            if x {
                panel.x_asinh = true;
                panel.x_asinh_linear_width = width;
            } else {
                panel.y_asinh = true;
                panel.y_asinh_linear_width = width;
            }
        }
    }
}

fn new_panel(pos: usize, dpi: f64) -> Panel {
    let tick_style = || TickStyle {
        labelsize: 10.0,
        length: 3.5,
        width: 1.0,
        ..Default::default()
    };
    Panel {
        dpi,
        pos,
        font_family: SANS_FAMILY.to_string(),
        log_base: 10.0,
        x_symlog_linthresh: 1.0,
        y_symlog_linthresh: 1.0,
        x_asinh_linear_width: 1.0,
        y_asinh_linear_width: 1.0,
        ticks: matplotvite_core::model::Ticks {
            xstyle: tick_style(),
            ystyle: tick_style(),
            ..Default::default()
        },
        legend: Legend {
            fontsize: 10.0,
            title_fontsize: 11.0,
            ..Default::default()
        },
        ..Default::default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::array;

    #[test]
    fn priority_methods_render_without_python() {
        let mut figure = Figure::new(640, 480);
        {
            let mut axes = figure.subplot(1, 2, 0).unwrap();
            axes.plot(&[0.0, 1.0, 2.0], &[0.0, 1.0, 0.0])
                .unwrap()
                .color("red")
                .label("line");
            axes.scatter(&[0.5, 1.5], &[0.2, 0.8]).unwrap();
            axes.bar(&[0.0, 1.0], &[1.0, 2.0]).unwrap();
            axes.fill_between(&[0.0, 1.0], &[0.0, 0.0], &[1.0, 1.0])
                .unwrap();
            axes.hist(&[0.0, 1.0, 1.0, 2.0], 4).unwrap();
            axes.title("native");
            axes.xlabel("x");
            axes.ylabel("y");
            axes.legend();
            axes.grid(true);
        }
        {
            let mut axes = figure.subplot(1, 2, 1).unwrap();
            axes.imshow(array![[0.0, 1.0], [1.0, 0.0]].view()).unwrap();
        }

        let png = figure.to_bytes("png").unwrap();
        assert!(png.starts_with(b"\x89PNG\r\n\x1a\n"));
        let svg = figure.to_bytes("svg").unwrap();
        let text = String::from_utf8(svg).unwrap();
        assert!(text.starts_with("<svg"));
        assert!(text.contains("native"));
    }

    #[test]
    fn builder_covers_the_panel_surface() {
        let mut figure = Figure::new(640, 480);
        {
            let mut axes = figure.add_axes(0.1, 0.1, 0.8, 0.8).unwrap();
            axes.plot(&[0.0, 1.0, 2.0], &[1.0, 4.0, 9.0])
                .unwrap()
                .label("square");
            axes.barh(&[0.0, 1.0], &[1.0, 2.0]).unwrap();
            axes.errorbar(&[0.5, 1.5], &[1.0, 2.0], &[0.1, 0.2])
                .unwrap();
            axes.quiver(&[0.0], &[0.0], &[1.0], &[0.5]).unwrap();
            axes.contour(
                &[0.0, 1.0],
                &[0.0, 1.0],
                array![[0.0, 1.0], [1.0, 0.0]].view(),
                &[0.25, 0.75],
            )
            .unwrap();
            axes.rectangle(0.1, 0.1, 0.5, 0.5).color("red").alpha(0.2);
            axes.circle(1.0, 1.0, 0.3);
            axes.polygon(&[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]);
            axes.line_collection(&[vec![0.0, 0.0, 1.0, 1.0]]);
            axes.text(0.2, 0.8, "native");
            axes.text_styled(0.2, 0.7, "styled", 12.0, "red", ("center", "top"));
            axes.annotate("point", (1.0, 1.0), Some((0.5, 1.5)));
            axes.xticks_with_labels(&[0.0, 1.0, 2.0], &["a", "b", "c"])
                .unwrap();
            axes.yticks_with_labels(&[0.0, 2.0], &["low", "high"])
                .unwrap();
            axes.tick_params(&TickParams {
                rotation: 45.0,
                ..Default::default()
            });
            axes.xscale(Scale::log())
                .yscale(Scale::Asinh { linear_width: 0.5 });
            axes.aspect(1.0).unwrap().aspect_datalim(false);
            axes.grid_options(&GridOptions {
                show: true,
                axis: "x".to_string(),
                linestyle: Some("dashed".to_string()),
                minor_show: true,
                ..Default::default()
            });
            axes.legend_options(&LegendOptions {
                loc: "upper left".to_string(),
                ncol: 2,
                title: "series".to_string(),
                ..Default::default()
            });
            axes.title("panel").title_size(14.0);
            axes.xlabel("x").xlabel_size(11.0);
            axes.ylabel("y").ylabel_size(11.0);
            axes.facecolor("#f4f4f4").foreground("#222222");
            axes.label_colors("#333333", "#444444");
        }
        {
            let mut axes = figure.subplot(1, 2, 0).unwrap();
            axes.imshow_cmap(
                array![[0.0, 1.0], [1.0, 0.0]].view(),
                "magma",
                Some(0.0),
                Some(1.0),
            )
            .unwrap();
            axes.colorbar("magma", 0.0, 1.0);
        }
        {
            let mut axes = figure.subplot(1, 2, 1).unwrap();
            axes.contourf(
                &[0.0, 1.0],
                &[0.0, 1.0],
                array![[0.0, 1.0], [1.0, 0.0]].view(),
                &[],
            )
            .unwrap();
            axes.axis_off();
        }

        let png = figure.to_bytes("png").unwrap();
        assert!(png.starts_with(b"\x89PNG\r\n\x1a\n"));
        let svg = String::from_utf8(figure.to_bytes("svg").unwrap()).unwrap();
        assert!(svg.contains("native"));
    }

    #[test]
    fn mismatched_series_are_rejected() {
        let mut figure = Figure::new(320, 240);
        let mut axes = figure.subplot(1, 1, 0).unwrap();
        assert!(matches!(
            axes.plot(&[0.0, 1.0], &[0.0]),
            Err(ApiError::InvalidArgument(_))
        ));
    }
}
