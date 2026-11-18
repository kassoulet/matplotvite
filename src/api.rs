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

use crate::color::{Cmap, Color};
use crate::fonts::SANS_FAMILY;
use crate::model::{
    Band, Bar, Legend, Marker, OwnedArray1, OwnedArrayD, Panel, RenderOptions, Scatter, Series,
};
use crate::render::render_figure;

const COLORS: [&str; 10] = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf",
];

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
        let panel = self.panels.last_mut().expect("just pushed a panel");
        Ok(Axes {
            panel,
            last: None,
            color: 0,
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
}

#[derive(Clone, Copy)]
enum LastArtist {
    Series(usize),
    Scatter(usize),
    Bar(usize),
    Band(usize),
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
                    .expect("shape and length agree")
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
        let order = self
            .panel
            .series
            .iter()
            .map(|artist| &artist.label)
            .chain(self.panel.scatter.iter().map(|artist| &artist.label))
            .chain(self.panel.bars.iter().map(|artist| &artist.label))
            .chain(self.panel.bands.iter().map(|artist| &artist.label))
            .filter(|label| !label.is_empty())
            .cloned()
            .collect();
        self.panel.legend = Legend {
            show: true,
            loc: "best".to_string(),
            order,
            ..Default::default()
        };
        self
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

fn new_panel(pos: usize, dpi: f64) -> Panel {
    Panel {
        dpi,
        pos,
        font_family: SANS_FAMILY.to_string(),
        log_base: 10.0,
        x_symlog_linthresh: 1.0,
        y_symlog_linthresh: 1.0,
        x_asinh_linear_width: 1.0,
        y_asinh_linear_width: 1.0,
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
    fn mismatched_series_are_rejected() {
        let mut figure = Figure::new(320, 240);
        let mut axes = figure.subplot(1, 1, 0).unwrap();
        assert!(matches!(
            axes.plot(&[0.0, 1.0], &[0.0]),
            Err(ApiError::InvalidArgument(_))
        ));
    }
}
