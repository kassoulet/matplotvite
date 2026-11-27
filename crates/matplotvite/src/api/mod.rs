//! Native Rust plotting API.
//!
//! This is the first crate-level slice of the matplotlib-style builder. It
//! covers the priority methods from `TRACE.md` and renders through the same
//! panel pipeline as the Python facade. The API takes slices and copies them
//! into the renderer's owned panel records, keeping the render path independent
//! of caller lifetimes.

use std::fmt;
use std::path::Path;

mod axis;
mod field;
mod plot;

use ndarray::{Array2, ArrayView2};

use matplotvite_core::color::{Cmap, Color};
use matplotvite_core::fonts::SANS_FAMILY;
use matplotvite_core::model::{
    Arrow, ArtistCollection, ArtistPatch, AxisSpec, Band, Bar, Grid, Legend, Marker, OwnedArray1,
    OwnedArray2, OwnedArrayD, Panel, QuiverUnits, RenderOptions, Scatter, Series, TickStyle,
};
use matplotvite_core::render::render_figure;
use matplotvite_core::stats as stats_core;

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

    /// Append a line series and remember it as the last artist.
    fn push_series(&mut self, series: Series) -> &mut Self {
        self.panel.series.push(series);
        self.record(LastArtist::Series(self.panel.series.len() - 1))
    }

    /// Append a filled band and remember it as the last artist.
    fn push_band(&mut self, band: Band) -> &mut Self {
        self.panel.bands.push(band);
        self.record(LastArtist::Band(self.panel.bands.len() - 1))
    }

    /// Remember a freshly pushed artist so `color()`/`label()`/`alpha()` reach it.
    fn record(&mut self, artist: LastArtist) -> &mut Self {
        self.last = Some(artist);
        self.sequence.push(artist);
        self
    }

    fn next_color(&mut self) -> Color {
        let value = COLORS[self.color % COLORS.len()];
        self.color += 1;
        Color::parse(value)
    }
}

/// An owned array copied from a slice.
fn owned(values: &[f64]) -> OwnedArray1 {
    OwnedArray1::from(values.to_vec())
}

/// A default-styled line series through `x`/`y`.
fn line_series(x: &[f64], y: &[f64], color: Color) -> Series {
    Series {
        x: owned(x),
        y: owned(y),
        color,
        linewidth: 1.5,
        markersize: 6.0,
        mew: 1.0,
        ..Default::default()
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
        panel.x.log = false;
        panel.x.symlog = false;
        panel.x.logit = false;
        panel.x.asinh = false;
    } else {
        panel.y.log = false;
        panel.y.symlog = false;
        panel.y.logit = false;
        panel.y.asinh = false;
    }
    match scale {
        Scale::Linear => {}
        Scale::Log { base } => {
            if x {
                panel.x.log = true;
            } else {
                panel.y.log = true;
            }
            panel.log_base = if base > 1.0 { base } else { 10.0 };
        }
        Scale::Symlog { linthresh } => {
            let linthresh = linthresh.abs().max(f64::MIN_POSITIVE);
            if x {
                panel.x.symlog = true;
                panel.x.symlog_linthresh = linthresh;
            } else {
                panel.y.symlog = true;
                panel.y.symlog_linthresh = linthresh;
            }
        }
        Scale::Logit => {
            if x {
                panel.x.logit = true;
            } else {
                panel.y.logit = true;
            }
        }
        Scale::Asinh { linear_width } => {
            let width = linear_width.abs().max(f64::MIN_POSITIVE);
            if x {
                panel.x.asinh = true;
                panel.x.asinh_linear_width = width;
            } else {
                panel.y.asinh = true;
                panel.y.asinh_linear_width = width;
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
        x: AxisSpec {
            symlog_linthresh: 1.0,
            asinh_linear_width: 1.0,
            ..Default::default()
        },
        y: AxisSpec {
            symlog_linthresh: 1.0,
            asinh_linear_width: 1.0,
            ..Default::default()
        },
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
