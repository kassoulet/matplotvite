use numpy::{PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArrayDyn};
use plotters::prelude::RGBAColor;
use pyo3::prelude::*;

/// How the figure should be rendered. Passed as one object so the PyO3
/// boundary keeps a short signature.
#[derive(FromPyObject)]
pub(crate) struct RenderOptions {
    #[pyo3(item)]
    pub(crate) format: String,
    #[pyo3(item)]
    pub(crate) transparent: bool,
    #[pyo3(item)]
    pub(crate) tight: bool,
    #[pyo3(item)]
    pub(crate) dpi: f64,
    #[pyo3(item)]
    pub(crate) facecolor: Option<String>,
    #[pyo3(item)]
    pub(crate) edgecolor: Option<String>,
    #[pyo3(item)]
    pub(crate) compression: Option<String>,
    #[pyo3(item)]
    pub(crate) suptitle: String,
    #[pyo3(item)]
    pub(crate) suptitle_size: f64,
    #[pyo3(item)]
    pub(crate) suptitle_x: f64,
    #[pyo3(item)]
    pub(crate) suptitle_y: f64,
}

/// Figure-level title drawn above the panel grid.
pub(crate) struct Suptitle<'a> {
    pub(crate) text: &'a str,
    pub(crate) size: f64,
    pub(crate) x: f64,
    pub(crate) y: f64,
}

/// PNG compression level selectable through `savefig(compression=...)`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum PngCompression {
    Fast,
    Default,
    Best,
}

impl PngCompression {
    pub(crate) fn parse(value: &str) -> Option<Self> {
        match value.to_ascii_lowercase().as_str() {
            "fast" => Some(Self::Fast),
            "default" => Some(Self::Default),
            "best" => Some(Self::Best),
            _ => None,
        }
    }

    pub(crate) fn to_png(self) -> png::Compression {
        match self {
            Self::Fast => png::Compression::Fast,
            Self::Default => png::Compression::Default,
            Self::Best => png::Compression::Best,
        }
    }
}

/// One `plot` call, including its styling keywords.
#[derive(FromPyObject)]
pub(crate) struct Series<'py> {
    #[pyo3(item)]
    pub(crate) x: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) y: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) label: String,
    #[pyo3(item)]
    pub(crate) color: String,
    #[pyo3(item)]
    pub(crate) linestyle: String,
    #[pyo3(item)]
    pub(crate) linewidth: f64,
    #[pyo3(item)]
    pub(crate) marker: String,
    #[pyo3(item)]
    pub(crate) markersize: f64,
    #[pyo3(item)]
    pub(crate) mfc: Option<String>,
    #[pyo3(item)]
    pub(crate) mec: Option<String>,
    #[pyo3(item)]
    pub(crate) mew: f64,
    #[pyo3(item)]
    pub(crate) alpha: Option<f64>,
    #[pyo3(item)]
    pub(crate) drawstyle: String,
}

/// (x, y, text, color, font size, horizontal align, vertical align).
pub(crate) type TextItem = (f64, f64, String, String, f64, String, String);

/// (data, colormap, vmin, vmax, (left, right, bottom, top), origin-is-upper).
pub(crate) type ImageItem<'py> = (
    PyReadonlyArrayDyn<'py, f64>,
    String,
    Option<f64>,
    Option<f64>,
    (f64, f64, f64, f64),
    bool,
);

/// (text, xy, xytext, color, font size).
pub(crate) type Annotation = (String, (f64, f64), Option<(f64, f64)>, String, f64);

/// (x, y, yerr-lo, yerr-hi, xerr-lo, xerr-hi, color, cap half-width in px).
pub(crate) type ErrorItem<'py> = (
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    String,
    f64,
);

/// (colormap, vmin, vmax, label): a stand-alone gradient strip panel.
pub(crate) type ColorbarItem = (String, f64, f64, String);

/// One `scatter` call: per-point sizes and either per-point colours or values
/// mapped through `cmap`.
#[derive(FromPyObject)]
pub(crate) struct Scatter<'py> {
    #[pyo3(item)]
    pub(crate) x: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) y: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) sizes: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) values: Option<PyReadonlyArray1<'py, f64>>,
    #[pyo3(item)]
    pub(crate) cmap: String,
    #[pyo3(item)]
    pub(crate) clim: Option<(f64, f64)>,
    #[pyo3(item)]
    pub(crate) colors: Vec<String>,
    #[pyo3(item)]
    pub(crate) marker: String,
    #[pyo3(item)]
    pub(crate) alpha: f64,
    #[pyo3(item)]
    pub(crate) label: String,
}

/// One `quiver` call: arrow tails, vector components and styling.
#[derive(FromPyObject)]
pub(crate) struct Arrow<'py> {
    #[pyo3(item)]
    pub(crate) x: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) y: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) u: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) v: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) colors: Vec<String>,
    #[pyo3(item)]
    pub(crate) linewidth: f64,
    #[pyo3(item)]
    pub(crate) headwidth: f64,
    #[pyo3(item)]
    pub(crate) headlength: f64,
}

/// (x, y, z, levels, colors, colormap, filled).
pub(crate) type ContourItem<'py> = (
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    Vec<f64>,
    Vec<String>,
    String,
    bool,
);

#[derive(FromPyObject)]
pub(crate) struct TickStyle {
    #[pyo3(item)]
    pub(crate) labelsize: f64,
    #[pyo3(item)]
    pub(crate) length: f64,
    #[pyo3(item)]
    pub(crate) width: f64,
    #[pyo3(item)]
    pub(crate) color: Option<String>,
    #[pyo3(item)]
    pub(crate) labelcolor: Option<String>,
    #[pyo3(item)]
    pub(crate) rotation: f64,
}

impl TickStyle {
    pub(crate) fn is_custom(&self) -> bool {
        self.rotation != 0.0
            || self.length != 3.5
            || self.width != 1.0
            || self.color.is_some()
            || self.labelcolor.is_some()
            || (self.labelsize - 10.0).abs() > 0.01
    }
}

#[derive(FromPyObject)]
pub(crate) struct Ticks {
    #[pyo3(item)]
    pub(crate) xticks: Option<Vec<f64>>,
    #[pyo3(item)]
    pub(crate) xticklabels: Option<Vec<String>>,
    #[pyo3(item)]
    pub(crate) yticks: Option<Vec<f64>>,
    #[pyo3(item)]
    pub(crate) yticklabels: Option<Vec<String>>,
    #[pyo3(item)]
    pub(crate) xstyle: TickStyle,
    #[pyo3(item)]
    pub(crate) ystyle: TickStyle,
    /// Shared axes hide the inner tick labels, matching matplotlib.
    #[pyo3(item)]
    pub(crate) hide_xlabels: bool,
    #[pyo3(item)]
    pub(crate) hide_ylabels: bool,
}

/// One collected legend row; icons match the artist that registered it.
pub(crate) enum LegendSwatch {
    Line(RGBAColor, u32),
    Rect(RGBAColor),
    Circle(RGBAColor),
}

pub(crate) struct LegendEntry {
    pub(crate) label: String,
    pub(crate) swatch: LegendSwatch,
}

#[derive(FromPyObject)]
pub(crate) struct Legend {
    #[pyo3(item)]
    pub(crate) show: bool,
    #[pyo3(item)]
    pub(crate) loc: String,
    #[pyo3(item)]
    pub(crate) ncol: usize,
    #[pyo3(item)]
    pub(crate) frameon: bool,
    #[pyo3(item)]
    pub(crate) fontsize: f64,
    #[pyo3(item)]
    pub(crate) title: String,
    #[pyo3(item)]
    pub(crate) title_fontsize: f64,
    #[pyo3(item)]
    pub(crate) anchor: Option<(f64, f64)>,
}

impl Legend {
    /// The plotters legend only covers the default layout; every placement or
    /// typographic option goes through the manual renderer.
    pub(crate) fn is_custom(&self) -> bool {
        self.loc != "best"
            || self.ncol > 1
            || !self.frameon
            || !self.title.is_empty()
            || self.anchor.is_some()
            || (self.fontsize - 10.0).abs() > 0.01
    }
}

#[derive(FromPyObject)]
pub(crate) struct Grid {
    #[pyo3(item)]
    pub(crate) show: bool,
    #[pyo3(item)]
    pub(crate) color: Option<String>,
    #[pyo3(item)]
    pub(crate) linewidth: Option<f64>,
    #[pyo3(item)]
    pub(crate) alpha: Option<f64>,
    #[pyo3(item)]
    pub(crate) linestyle: Option<String>,
    #[pyo3(item)]
    pub(crate) axis: String,
}

#[derive(FromPyObject)]
pub(crate) struct Panel<'py> {
    #[pyo3(item)]
    pub(crate) pos: usize, // row-major cell index
    #[pyo3(item)]
    pub(crate) series: Vec<Series<'py>>,
    #[pyo3(item)]
    pub(crate) title: String,
    #[pyo3(item)]
    pub(crate) xlabel: String,
    #[pyo3(item)]
    pub(crate) ylabel: String,
    #[pyo3(item)]
    pub(crate) title_size: Option<f64>,
    #[pyo3(item)]
    pub(crate) xlabel_size: Option<f64>,
    #[pyo3(item)]
    pub(crate) ylabel_size: Option<f64>,
    #[pyo3(item)]
    pub(crate) legend: Legend,
    #[pyo3(item)]
    pub(crate) xlim: Option<(f64, f64)>,
    #[pyo3(item)]
    pub(crate) ylim: Option<(f64, f64)>,
    #[pyo3(item)]
    pub(crate) texts: Vec<TextItem>,
    #[pyo3(item)]
    pub(crate) images: Vec<ImageItem<'py>>,
    #[pyo3(item)]
    pub(crate) annotations: Vec<Annotation>,
    /// `None` is matplotlib's "auto"; a number is the y-unit/x-unit scale
    /// (1.0 == "equal").
    #[pyo3(item)]
    pub(crate) aspect: Option<f64>,
    #[pyo3(item)]
    pub(crate) contours: Vec<ContourItem<'py>>,
    #[pyo3(item)]
    pub(crate) errors: Vec<ErrorItem<'py>>,
    #[pyo3(item)]
    pub(crate) scatter: Vec<Scatter<'py>>,
    #[pyo3(item)]
    pub(crate) arrows: Vec<Arrow<'py>>,
    #[pyo3(item)]
    pub(crate) bars: Vec<Bar<'py>>,
    #[pyo3(item)]
    pub(crate) bands: Vec<Band<'py>>,
    #[pyo3(item)]
    pub(crate) grid: Grid,
    #[pyo3(item)]
    pub(crate) ticks: Ticks,
    #[pyo3(item)]
    pub(crate) x_log: bool,
    #[pyo3(item)]
    pub(crate) y_log: bool,
    #[pyo3(item)]
    pub(crate) log_base: f64,
    #[pyo3(item)]
    pub(crate) colorbar: Option<ColorbarItem>,
    /// `axis("off")`: keep the data, drop axes, ticks and tick labels.
    #[pyo3(item)]
    pub(crate) axis_off: bool,
    /// Axes background and the colour used for titles, labels and ticks.
    #[pyo3(item)]
    pub(crate) facecolor: Option<String>,
    #[pyo3(item)]
    pub(crate) foreground: Option<String>,
    /// Figure-fraction `(x, y, width, height)`; `None` uses the grid cell.
    #[pyo3(item)]
    pub(crate) bounds: Option<(f64, f64, f64, f64)>,
    /// Empty for a normal axes, `"y"` for `twinx`, `"x"` for `twiny`.
    #[pyo3(item)]
    pub(crate) twin: String,
    /// Gap reserved for the twin axis labels, as a figure-width fraction.
    #[pyo3(item)]
    pub(crate) twin_gap: f64,
    #[pyo3(item)]
    pub(crate) patches: Vec<ArtistPatch>,
    #[pyo3(item)]
    pub(crate) collections: Vec<ArtistCollection>,
}

/// A patch added through `add_patch`, reduced to simple data-space geometry.
#[derive(FromPyObject)]
pub(crate) struct ArtistPatch {
    #[pyo3(item)]
    pub(crate) kind: String,
    #[pyo3(item)]
    pub(crate) x: f64,
    #[pyo3(item)]
    pub(crate) y: f64,
    #[pyo3(item)]
    pub(crate) width: f64,
    #[pyo3(item)]
    pub(crate) height: f64,
    /// Flattened xy pairs for `kind == "polygon"`.
    #[pyo3(item)]
    pub(crate) points: Vec<f64>,
    #[pyo3(item)]
    pub(crate) facecolor: Option<String>,
    #[pyo3(item)]
    pub(crate) edgecolor: Option<String>,
    #[pyo3(item)]
    pub(crate) linewidth: f64,
    #[pyo3(item)]
    pub(crate) alpha: f64,
    #[pyo3(item)]
    pub(crate) label: String,
}

/// A collection added through `add_collection`: point offsets and/or polylines.
#[derive(FromPyObject)]
pub(crate) struct ArtistCollection {
    #[pyo3(item)]
    pub(crate) points: Vec<f64>,
    #[pyo3(item)]
    pub(crate) segments: Vec<Vec<f64>>,
    #[pyo3(item)]
    pub(crate) sizes: Vec<f64>,
    #[pyo3(item)]
    pub(crate) colors: Vec<String>,
    #[pyo3(item)]
    pub(crate) marker: String,
    #[pyo3(item)]
    pub(crate) alpha: f64,
    #[pyo3(item)]
    pub(crate) linewidth: f64,
    #[pyo3(item)]
    pub(crate) label: String,
}

/// One `bar`/`barh` call: axis-aligned rectangles in data coordinates.
#[derive(FromPyObject)]
pub(crate) struct Bar<'py> {
    #[pyo3(item)]
    pub(crate) left: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) bottom: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) width: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) height: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) colors: Vec<String>,
    #[pyo3(item)]
    pub(crate) edgecolor: Option<String>,
    #[pyo3(item)]
    pub(crate) alpha: Option<f64>,
    #[pyo3(item)]
    pub(crate) label: String,
}

/// One closed filled area (`fill_between`/`fill`) in data coordinates.
#[derive(FromPyObject)]
pub(crate) struct Band<'py> {
    #[pyo3(item)]
    pub(crate) x: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) y: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    pub(crate) color: String,
    #[pyo3(item)]
    pub(crate) alpha: Option<f64>,
    #[pyo3(item)]
    pub(crate) label: String,
}
