use ndarray::{Array1, Array2, ArrayD, ArrayView1, ArrayView2, ArrayViewD};
use plotters::prelude::RGBAColor;

use crate::color::{Cmap, Color};
#[cfg(feature = "python")]
use pyo3::FromPyObject;

/// Array data copied out of NumPy while the GIL is held. Owning the buffer
/// makes every panel `Send + Sync`, so rendering can run on Rayon threads (or
/// under `allow_threads`) without borrowing Python memory.
pub(crate) struct OwnedArray1(Array1<f64>);

impl OwnedArray1 {
    pub(crate) fn from_array(array: Array1<f64>) -> Self {
        Self(array)
    }
}

impl OwnedArray1 {
    pub(crate) fn as_array(&self) -> ArrayView1<'_, f64> {
        self.0.view()
    }
}

impl std::ops::Deref for OwnedArray1 {
    type Target = Array1<f64>;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

impl Default for OwnedArray1 {
    fn default() -> Self {
        Self(Array1::from_vec(Vec::new()))
    }
}

impl From<Vec<f64>> for OwnedArray1 {
    fn from(values: Vec<f64>) -> Self {
        Self(Array1::from_vec(values))
    }
}

pub(crate) struct OwnedArray2(Array2<f64>);

impl OwnedArray2 {
    pub(crate) fn from_array(array: Array2<f64>) -> Self {
        Self(array)
    }
}

impl OwnedArray2 {
    pub(crate) fn as_array(&self) -> ArrayView2<'_, f64> {
        self.0.view()
    }
}

impl std::ops::Deref for OwnedArray2 {
    type Target = Array2<f64>;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

pub(crate) struct OwnedArrayD(ArrayD<f64>);

impl OwnedArrayD {
    pub(crate) fn from_array(array: ArrayD<f64>) -> Self {
        Self(array)
    }
}

impl OwnedArrayD {
    pub(crate) fn as_array(&self) -> ArrayViewD<'_, f64> {
        self.0.view()
    }
}

impl std::ops::Deref for OwnedArrayD {
    type Target = ArrayD<f64>;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

/// How the figure should be rendered. Passed as one object so the PyO3
/// boundary keeps a short signature.
#[derive(Default)]
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct RenderOptions {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) format: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) transparent: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) tight: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) dpi: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) facecolor: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) edgecolor: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) compression: Option<String>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) suptitle: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) suptitle_family: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) suptitle_size: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) suptitle_x: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) suptitle_y: f64,
    /// Figure-fraction text, drawn after the panels so it is never clipped.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) figure_texts: Vec<TextItem>,
    /// Images placed directly in figure pixel space, under every panel.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) figure_images: Vec<FigureImage>,
}

/// Figure-level title drawn above the panel grid.
pub(crate) struct Suptitle<'a> {
    pub(crate) text: &'a str,
    pub(crate) family: &'a str,
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
            Self::Default => png::Compression::Balanced,
            Self::Best => png::Compression::High,
        }
    }
}

/// How a line connects consecutive data points.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) enum DrawStyle {
    #[default]
    Normal,
    StepsPre,
    StepsMid,
    StepsPost,
}

impl DrawStyle {
    pub(crate) fn parse(value: &str) -> Option<Self> {
        match value {
            "default" => Some(Self::Normal),
            "steps-pre" => Some(Self::StepsPre),
            "steps-mid" => Some(Self::StepsMid),
            "steps-post" => Some(Self::StepsPost),
            _ => None,
        }
    }

    pub(crate) fn is_step(self) -> bool {
        !matches!(self, Self::Normal)
    }
}

/// The stroke pattern used by a line or gridline.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) enum LineStyle {
    #[default]
    Solid,
    Dashed,
    Dotted,
    DashDot,
    Hidden,
}

impl LineStyle {
    pub(crate) fn parse(value: &str) -> Option<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "-" | "solid" => Some(Self::Solid),
            "--" | "dashed" => Some(Self::Dashed),
            ":" | "dotted" => Some(Self::Dotted),
            "-." | "dashdot" => Some(Self::DashDot),
            "none" => Some(Self::Hidden),
            _ => None,
        }
    }

    pub(crate) fn is_hidden(self) -> bool {
        matches!(self, Self::Hidden)
    }

    pub(crate) fn is_dashed(self) -> bool {
        matches!(self, Self::Dashed | Self::Dotted | Self::DashDot)
    }

    /// Dash and gap lengths in multiples of the line width.
    pub(crate) fn dash_pattern(self) -> Option<(f64, f64)> {
        match self {
            Self::Dashed => Some((3.7, 1.6)),
            Self::Dotted => Some((1.0, 1.65)),
            Self::DashDot => Some((6.4, 1.6)),
            Self::Solid | Self::Hidden => None,
        }
    }
}

/// Marker symbols understood by the raster and vector renderers.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) enum Marker {
    #[default]
    None,
    Circle,
    Square,
    TriangleUp,
    TriangleDown,
    TriangleLeft,
    TriangleRight,
    Diamond,
    ThinDiamond,
    Cross,
    Plus,
    Point,
    Star,
    Hexagon1,
    Hexagon2,
    Pentagon,
    PlusFilled,
    X,
    Vline,
    Hline,
    Tick1,
    Tick2,
    Tick3,
    Tick4,
    Octagon,
}

impl Marker {
    pub(crate) fn parse(value: &str) -> Option<Self> {
        match value.trim() {
            "" | "none" | "None" => Some(Self::None),
            "o" => Some(Self::Circle),
            "s" => Some(Self::Square),
            "^" => Some(Self::TriangleUp),
            "v" => Some(Self::TriangleDown),
            "<" => Some(Self::TriangleLeft),
            ">" => Some(Self::TriangleRight),
            "D" => Some(Self::Diamond),
            "d" => Some(Self::ThinDiamond),
            "x" => Some(Self::Cross),
            "+" => Some(Self::Plus),
            "." => Some(Self::Point),
            "*" => Some(Self::Star),
            "h" => Some(Self::Hexagon1),
            "H" => Some(Self::Hexagon2),
            "p" => Some(Self::Pentagon),
            "P" => Some(Self::PlusFilled),
            "X" => Some(Self::X),
            "|" => Some(Self::Vline),
            "_" => Some(Self::Hline),
            "1" => Some(Self::Tick1),
            "2" => Some(Self::Tick2),
            "3" => Some(Self::Tick3),
            "4" => Some(Self::Tick4),
            "8" => Some(Self::Octagon),
            _ => None,
        }
    }

    pub(crate) fn is_none(self) -> bool {
        matches!(self, Self::None)
    }

    pub(crate) fn is_stroked(self) -> bool {
        matches!(self, Self::Cross | Self::Plus)
    }
}

/// One `plot` call, including its styling keywords.
#[derive(Default)]
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct Series {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) label: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) color: Color,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) linestyle: LineStyle,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) linewidth: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) marker: Marker,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) markersize: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) mfc: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) mec: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) mew: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) alpha: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) drawstyle: DrawStyle,
    /// SVG element id, emitted as a group around this artist's output.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) gid: String,
}

#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct TextBBox {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) facecolor: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) edgecolor: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) alpha: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) pad: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) rounded: bool,
}

/// (x, y, text, color, font size, horizontal align, vertical align, bbox,
/// rotation in degrees, font family, offset in points).
pub(crate) type TextItem = (
    f64,
    f64,
    String,
    Color,
    f64,
    String,
    String,
    Option<TextBBox>,
    f64,
    String,
    (f64, f64),
);

/// (data, colormap, vmin, vmax, (left, right, bottom, top), origin-is-upper,
/// opacity, interpolation).
pub(crate) type ImageItem = (
    OwnedArrayD,
    Cmap,
    Option<f64>,
    Option<f64>,
    (f64, f64, f64, f64),
    bool,
    f64,
    String,
);

/// A `Figure.figimage`: its pixel array, colormap, opacity, origin and pixel
/// offsets from the lower-left corner of the figure.
pub(crate) type FigureImage = (
    OwnedArrayD,
    Cmap,
    Option<f64>,
    Option<f64>,
    f64,
    bool,
    i64,
    i64,
);

/// (text, xy, xytext, color, font size, font family).
pub(crate) type Annotation = (String, (f64, f64), Option<(f64, f64)>, Color, f64, String);

/// (x, y, yerr-lo, yerr-hi, xerr-lo, xerr-hi, color, cap half-width in px).
pub(crate) type ErrorItem = (
    OwnedArray1,
    OwnedArray1,
    OwnedArray1,
    OwnedArray1,
    OwnedArray1,
    OwnedArray1,
    Color,
    f64,
);

/// (colormap, vmin, vmax, label, log scale, display limits, log base,
/// orientation, extend, rectangular extensions, extension fraction): a
/// gradient strip panel.
pub(crate) type ColorbarItem = (
    Cmap,
    f64,
    f64,
    String,
    bool,
    Option<(f64, f64)>,
    f64,
    String,
    String,
    bool,
    f64,
);

/// One `scatter` call: per-point sizes and either per-point colours or values
/// mapped through `cmap`.
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct Scatter {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) sizes: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) values: Option<OwnedArray1>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) cmap: Cmap,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) clim: Option<(f64, f64)>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) colors: Vec<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) marker: Marker,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) alpha: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) label: String,
}

/// The axes measurement used to turn quiver vector lengths into pixels.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) enum QuiverUnits {
    #[default]
    Width,
    Height,
    Dots,
    Inches,
    X,
    Y,
    Xy,
}

impl QuiverUnits {
    pub(crate) fn parse(value: &str) -> Option<Self> {
        match value {
            "width" => Some(Self::Width),
            "height" => Some(Self::Height),
            "dots" => Some(Self::Dots),
            "inches" => Some(Self::Inches),
            "x" => Some(Self::X),
            "y" => Some(Self::Y),
            "xy" => Some(Self::Xy),
            _ => None,
        }
    }
}

/// One `quiver` call: arrow tails, vector components and styling.
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct Arrow {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) u: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) v: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) colors: Vec<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) scale: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) units: QuiverUnits,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) scale_units: Option<QuiverUnits>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) angles: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) width: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) headwidth: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) headlength: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) headaxislength: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) pivot: String,
}

/// (x, y, z, levels, linewidths, colors, colormap, filled, opacity).
pub(crate) type ContourItem = (
    OwnedArray1,
    OwnedArray1,
    OwnedArray2,
    Vec<f64>,
    Vec<f64>,
    Vec<Color>,
    Cmap,
    bool,
    f64,
);

#[derive(Default)]
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct TickStyle {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) labelsize: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) length: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) width: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) color: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) labelcolor: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
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

#[derive(Default)]
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct Ticks {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) xticks: Option<Vec<f64>>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) xticklabels: Option<Vec<String>>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) yticks: Option<Vec<f64>>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) yticklabels: Option<Vec<String>>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) xstyle: TickStyle,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) ystyle: TickStyle,
    /// Shared axes hide the inner tick labels, matching matplotlib.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) hide_xlabels: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) hide_ylabels: bool,
    /// `"left"` or `"right"` forces the y tick side; empty keeps the default.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) yside: String,
}

/// One collected legend row; icons match the artist that registered it.
#[derive(Clone)]
pub(crate) enum LegendSwatch {
    Line(RGBAColor, u32),
    LineMarker(RGBAColor, u32, Marker),
    Marker(RGBAColor, Marker),
    Rect(RGBAColor),
    Collection(RGBAColor),
    Circle(RGBAColor),
}

pub(crate) struct LegendEntry {
    pub(crate) label: String,
    pub(crate) swatch: LegendSwatch,
}

#[derive(Default)]
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct Legend {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) family: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) show: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) loc: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) ncol: usize,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) frameon: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) fontsize: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) title: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) title_fontsize: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) anchor: Option<(f64, f64)>,
    /// Labels supplied directly to `legend(labels)`; they replace artist labels.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) labels: Vec<String>,
    /// Labels of the drawn artists in creation order, as Matplotlib lists them.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) order: Vec<String>,
}

impl Legend {
    /// The plotters legend only covers the upper-right layout; every placement
    /// (including the scored `"best"` one) goes through the manual renderer.
    pub(crate) fn is_custom(&self) -> bool {
        self.loc == "best"
            || self.ncol > 1
            || !self.frameon
            || !self.title.is_empty()
            || self.anchor.is_some()
            || (self.fontsize - 10.0).abs() > 0.01
    }
}

#[derive(Default)]
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct Grid {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) show: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) color: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) linewidth: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) alpha: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) linestyle: Option<LineStyle>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) axis: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) minor_show: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) minor_color: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) minor_linewidth: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) minor_alpha: Option<f64>,
}

#[derive(Default)]
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct Panel {
    /// Fingerprint from the Python layer; empty disables the fragment cache.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) cache_key: String,
    /// Font family for this panel's text, resolved from `rcParams["font.family"]`.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) font_family: String,
    /// Per-artist overrides; `None` follows `font_family`.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) title_family: Option<String>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) xlabel_family: Option<String>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) ylabel_family: Option<String>,
    /// Effective output resolution, used to convert point sizes to pixels.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) dpi: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) pos: usize, // row-major cell index
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) series: Vec<Series>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) title: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) xlabel: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) ylabel: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) title_size: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) xlabel_size: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) ylabel_size: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) legend: Legend,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) xlim: Option<(f64, f64)>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) ylim: Option<(f64, f64)>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) texts: Vec<TextItem>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) images: Vec<ImageItem>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) annotations: Vec<Annotation>,
    /// `None` is matplotlib's "auto"; a number is the y-unit/x-unit scale
    /// (1.0 == "equal").
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) aspect: Option<f64>,
    /// `set_adjustable("datalim")`: widen the data limits instead of
    /// shrinking the plot area to reach `aspect`.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) aspect_datalim: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) contours: Vec<ContourItem>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) errors: Vec<ErrorItem>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) scatter: Vec<Scatter>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) arrows: Vec<Arrow>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) bars: Vec<Bar>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) bands: Vec<Band>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) grid: Grid,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) ticks: Ticks,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x_log: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y_log: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) log_base: f64,
    /// Symmetric-log axes: linear inside `±linthresh`, logarithmic outside.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x_symlog: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y_symlog: bool,
    /// Logit axes: probabilities mapped through log(p / (1 - p)).
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x_logit: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y_logit: bool,
    /// Asinh axes: smooth log-like scaling with a linear width around zero.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x_asinh: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y_asinh: bool,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x_symlog_linthresh: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y_symlog_linthresh: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x_asinh_linear_width: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y_asinh_linear_width: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) colorbar: Option<ColorbarItem>,
    /// `axis("off")`: keep the data, drop axes, ticks and tick labels.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) axis_off: bool,
    /// Axes background and the colour used for titles, labels and ticks.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) facecolor: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) foreground: Option<Color>,
    /// Figure-fraction `(x, y, width, height)`; `None` uses the grid cell.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) bounds: Option<(f64, f64, f64, f64)>,
    /// The bounds are a precise plotting rectangle (`add_axes`/inset), not a
    /// panel that still needs the roomier label margins.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) axes_bounds: bool,
    /// Empty for a normal axes, `"y"` for `twinx`, `"x"` for `twiny`.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) twin: String,
    /// Gap reserved for the twin axis labels, as a figure-width fraction.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) twin_gap: f64,
    /// Side that reserves label room for a twin axis, on both panels.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) twin_reserve: String,
    /// Explicit axis-label colours; `None` follows the axes foreground.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) xlabel_color: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) ylabel_color: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) patches: Vec<ArtistPatch>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) collections: Vec<ArtistCollection>,
}

// Panels own their array data, so `Send + Sync` is derived automatically and
// rendering can safely leave the GIL.

/// A patch added through `add_patch`, reduced to simple data-space geometry.
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct ArtistPatch {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) kind: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) width: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) height: f64,
    /// Flattened xy pairs for `kind == "polygon"`.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) points: Vec<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) facecolor: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) edgecolor: Option<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) linewidth: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) alpha: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) gid: String,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) label: String,
}

/// A collection added through `add_collection`: point offsets and/or polylines.
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct ArtistCollection {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) points: Vec<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) segments: Vec<Vec<f64>>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) sizes: Vec<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) colors: Vec<Color>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) marker: Marker,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) alpha: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) linewidth: f64,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) label: String,
}

/// One `bar`/`barh` call: axis-aligned rectangles in data coordinates.
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct Bar {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) left: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) bottom: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) width: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) height: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) colors: Vec<Color>,
    /// One edge colour per bar; a shorter list cycles.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) edgecolor: Option<Vec<Color>>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) alpha: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) label: String,
}

/// One closed filled area (`fill_between`/`fill`) in data coordinates.
#[cfg_attr(feature = "python", derive(FromPyObject))]
pub(crate) struct Band {
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) x: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) y: OwnedArray1,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) color: Color,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) alpha: Option<f64>,
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) label: String,
    /// Number of closed rings packed into `x`/`y`; zero means one polygon.
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) cells: usize,
    /// Six hex digits per cell when `cells > 0` (hexbin's per-cell colours).
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) cell_colors: String,
    /// SVG element id for the filled area (pie wedges use this).
    #[cfg_attr(feature = "python", pyo3(item))]
    pub(crate) gid: String,
}
