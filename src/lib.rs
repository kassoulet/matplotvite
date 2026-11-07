use numpy::{PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArrayDyn};
use plotters::prelude::*;
use plotters::style::IntoFont;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

// Geist (OFL, see assets/fonts/LICENSE_GEIST_OFL.txt)
static FONT_SANS: &[u8] = include_bytes!("../assets/fonts/Geist-Regular.ttf");
static FONT_SERIF: &[u8] = include_bytes!("../assets/fonts/GeistSerif-Regular.ttf");
static FONT_MONO: &[u8] = include_bytes!("../assets/fonts/GeistMono-Regular.ttf");

/// Register fonts into plotters (for SVG text element names) — called once.
fn register_plotters_fonts() {
    static ONCE: std::sync::Once = std::sync::Once::new();
    ONCE.call_once(|| {
        let fonts: &[(&str, &[u8])] = &[
            ("sans-serif", FONT_SANS),
            ("serif", FONT_SERIF),
            ("monospace", FONT_MONO),
        ];
        for (name, bytes) in fonts {
            let _ = plotters::style::register_font(name, FontStyle::Normal, bytes);
        }
    });
}

/// Build a fontdb loaded with our embedded Geist faces (for resvg rasterisation).
fn build_fontdb() -> usvg::fontdb::Database {
    let mut db = usvg::fontdb::Database::new();
    db.load_font_data(FONT_SANS.to_vec());
    db.load_font_data(FONT_SERIF.to_vec());
    db.load_font_data(FONT_MONO.to_vec());
    // Map CSS generic families to Geist variants
    db.set_sans_serif_family("Geist");
    db.set_serif_family("Geist Serif");
    db.set_monospace_family("Geist Mono");
    db
}

/// One `plot` call, including its styling keywords.
#[derive(FromPyObject)]
struct Series<'py> {
    #[pyo3(item)]
    x: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    y: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    label: String,
    #[pyo3(item)]
    color: String,
    #[pyo3(item)]
    linestyle: String,
    #[pyo3(item)]
    linewidth: f64,
    #[pyo3(item)]
    marker: String,
    #[pyo3(item)]
    markersize: f64,
    #[pyo3(item)]
    mfc: Option<String>,
    #[pyo3(item)]
    mec: Option<String>,
    #[pyo3(item)]
    mew: f64,
    #[pyo3(item)]
    alpha: Option<f64>,
    #[pyo3(item)]
    drawstyle: String,
}

/// (x, y, text, color, font size, horizontal align, vertical align).
type TextItem = (f64, f64, String, String, f64, String, String);

/// (data, colormap, vmin, vmax, (left, right, bottom, top), origin-is-upper).
type ImageItem<'py> = (
    PyReadonlyArrayDyn<'py, f64>,
    String,
    Option<f64>,
    Option<f64>,
    (f64, f64, f64, f64),
    bool,
);

/// (text, xy, xytext, color, font size).
type Annotation = (String, (f64, f64), Option<(f64, f64)>, String, f64);

/// (x, y, yerr-lo, yerr-hi, xerr-lo, xerr-hi, color, cap half-width in px).
type ErrorItem<'py> = (
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
type ColorbarItem = (String, f64, f64, String);

/// One `scatter` call: per-point sizes and either per-point colours or values
/// mapped through `cmap`.
#[derive(FromPyObject)]
struct Scatter<'py> {
    #[pyo3(item)]
    x: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    y: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    sizes: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    values: Option<PyReadonlyArray1<'py, f64>>,
    #[pyo3(item)]
    cmap: String,
    #[pyo3(item)]
    clim: Option<(f64, f64)>,
    #[pyo3(item)]
    colors: Vec<String>,
    #[pyo3(item)]
    marker: String,
    #[pyo3(item)]
    alpha: f64,
    #[pyo3(item)]
    label: String,
}

/// (x, y, z, levels, colors, colormap, filled).
type ContourItem<'py> = (
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray2<'py, f64>,
    Vec<f64>,
    Vec<String>,
    String,
    bool,
);

fn color(s: &str) -> RGBColor {
    let h = match s {
        "red" | "r" => "d62728",
        "green" | "g" => "2ca02c",
        "blue" | "b" => "1f77b4",
        "orange" => "ff7f0e",
        "black" | "k" => "000000",
        o => o.trim_start_matches('#'),
    };
    let n = u32::from_str_radix(h, 16).unwrap_or(0x1f77b4);
    RGBColor((n >> 16) as u8, (n >> 8) as u8, n as u8)
}

fn range(it: impl Iterator<Item = f64>) -> (f64, f64) {
    let (lo, hi) = it.fold((f64::MAX, f64::MIN), |(l, h), v| (l.min(v), h.max(v)));
    if lo < hi {
        (lo, hi)
    } else {
        (lo - 1.0, lo + 1.0)
    }
}

/// Data ranges for a panel: series values plus image extents, unless pinned.
fn panel_ranges(p: &Panel<'_>) -> (f64, f64, f64, f64) {
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

/// Draw one label. Alignment is approximated: the backend only has a top-left
/// anchor, so the text width is estimated from the glyph count.
#[allow(clippy::too_many_arguments)]
fn draw_label<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    pos: (i32, i32),
    s: &str,
    col: RGBColor,
    size: f64,
    ha: &str,
    va: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let fs = size.max(1.0);
    let w = s.chars().count() as f64 * fs * 0.55;
    let dx = match ha {
        "center" => -w / 2.0,
        "right" => -w,
        _ => 0.0,
    };
    let dy = match va {
        "top" => 0.0,
        "center" => -fs / 2.0,
        "bottom" => -fs,
        _ => -fs * 0.8, // baseline
    };
    let style = ("sans-serif", fs.round() as u32).into_font().color(&col);
    area.draw(&Text::new(
        s,
        (pos.0 - base.0 + dx as i32, pos.1 - base.1 + dy as i32),
        style,
    ))?;
    Ok(())
}

/// Straight arrow with a triangular head, in canvas pixels.
fn draw_arrow<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    from: (i32, i32),
    to: (i32, i32),
    col: RGBColor,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (sx, sy) = (from.0 - base.0, from.1 - base.1);
    let (ax, ay) = (to.0 - base.0, to.1 - base.1);
    area.draw(&PathElement::new(
        vec![(sx, sy), (ax, ay)],
        col.stroke_width(2),
    ))?;
    let (dx, dy) = ((ax - sx) as f64, (ay - sy) as f64);
    let len = (dx * dx + dy * dy).sqrt().max(1.0);
    let (ux, uy) = (dx / len, dy / len);
    let (hl, hw) = (10.0, 4.5);
    let (px, py) = (ax as f64 - ux * hl, ay as f64 - uy * hl);
    area.draw(&Polygon::new(
        vec![
            (ax, ay),
            ((px - uy * hw) as i32, (py + ux * hw) as i32),
            ((px + uy * hw) as i32, (py - ux * hw) as i32),
        ],
        col.filled(),
    ))?;
    Ok(())
}

/// Minimal colormaps; unknown names fall back to viridis.
fn colormap(name: &str, t: f64) -> [u8; 4] {
    let t = if t.is_finite() {
        t.clamp(0.0, 1.0)
    } else {
        0.0
    };
    if name.eq_ignore_ascii_case("gray") || name.eq_ignore_ascii_case("grey") {
        let v = (t * 255.0).round() as u8;
        return [v, v, v, 255];
    }
    const VIRIDIS: [[u8; 3]; 9] = [
        [68, 1, 84],
        [72, 40, 120],
        [62, 74, 137],
        [49, 104, 142],
        [38, 130, 142],
        [31, 158, 137],
        [53, 183, 121],
        [109, 205, 89],
        [253, 231, 37],
    ];
    let pos = t * (VIRIDIS.len() - 1) as f64;
    let i = (pos.floor() as usize).min(VIRIDIS.len() - 2);
    let f = pos - i as f64;
    let (a, b) = (VIRIDIS[i], VIRIDIS[i + 1]);
    let mix = |k: usize| (a[k] as f64 + (b[k] as f64 - a[k] as f64) * f).round() as u8;
    [mix(0), mix(1), mix(2), 255]
}

fn base64(data: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(data.len().div_ceil(3) * 4);
    for chunk in data.chunks(3) {
        let b = [
            chunk[0],
            *chunk.get(1).unwrap_or(&0),
            *chunk.get(2).unwrap_or(&0),
        ];
        let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
        out.push(T[(n >> 18) as usize & 63] as char);
        out.push(T[(n >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 {
            T[(n >> 6) as usize & 63] as char
        } else {
            '='
        });
        out.push(if chunk.len() > 2 {
            T[n as usize & 63] as char
        } else {
            '='
        });
    }
    out
}

/// Encode an `imshow` array as a PNG: 2-D through the colormap, 3-D as RGB(A).
fn image_png(item: &ImageItem<'_>) -> Result<Vec<u8>, String> {
    let (arr, cmap, vmin, vmax, _, _) = item;
    let a = arr.as_array();
    let shape = a.shape();
    let (h, w) = match shape {
        [h, w] => (*h, *w),
        [h, w, c] if *c == 3 || *c == 4 => (*h, *w),
        _ => return Err("imshow expects a 2-D array or an (H, W, 3|4) RGB(A) array".into()),
    };
    if h == 0 || w == 0 {
        return Err("imshow got an empty array".into());
    }
    let rgb = shape.len() == 3;
    let (lo, hi) = if rgb {
        (0.0, 1.0)
    } else {
        let mut lo = f64::MAX;
        let mut hi = f64::MIN;
        for v in a.iter().copied().filter(|v| v.is_finite()) {
            lo = lo.min(v);
            hi = hi.max(v);
        }
        if lo > hi {
            (0.0, 1.0)
        } else {
            (vmin.unwrap_or(lo), vmax.unwrap_or(hi))
        }
    };
    let span = if hi > lo { hi - lo } else { 1.0 };
    let mut pm = tiny_skia::Pixmap::new(w as u32, h as u32).ok_or("failed to allocate image")?;
    for y in 0..h {
        for x in 0..w {
            let c = if rgb {
                let ch = |i: usize| (a[[y, x, i]].clamp(0.0, 1.0) * 255.0).round() as u8;
                let alpha = if shape[2] == 4 { ch(3) } else { 255 };
                [ch(0), ch(1), ch(2), alpha]
            } else {
                colormap(cmap, (a[[y, x]] - lo) / span)
            };
            pm.pixels_mut()[y * w + x] =
                tiny_skia::ColorU8::from_rgba(c[0], c[1], c[2], c[3]).premultiply();
        }
    }
    pm.encode_png().map_err(|e| e.to_string())
}

/// Insert an element right after the SVG's background rect (or the root tag),
/// so embedded images sit behind the axes and series.
fn insert_overlay(svg: &str, tag: &str) -> String {
    let Some(start) = svg.find("<svg") else {
        return svg.to_string();
    };
    let Some(mut at) = svg[start..].find('>').map(|i| start + i + 1) else {
        return svg.to_string();
    };
    let rest = svg[at..].trim_start();
    if rest.starts_with("<rect") {
        if let Some(i) = rest.find("/>") {
            at += (svg[at..].len() - rest.len()) + i + 2;
        }
    }
    format!("{}\n{}{}", &svg[..at], tag, &svg[at..])
}

#[derive(FromPyObject)]
struct Panel<'py> {
    #[pyo3(item)]
    pos: usize, // row-major cell index
    #[pyo3(item)]
    series: Vec<Series<'py>>,
    #[pyo3(item)]
    title: String,
    #[pyo3(item)]
    xlabel: String,
    #[pyo3(item)]
    ylabel: String,
    #[pyo3(item)]
    legend: bool,
    #[pyo3(item)]
    xlim: Option<(f64, f64)>,
    #[pyo3(item)]
    ylim: Option<(f64, f64)>,
    #[pyo3(item)]
    texts: Vec<TextItem>,
    #[pyo3(item)]
    images: Vec<ImageItem<'py>>,
    #[pyo3(item)]
    annotations: Vec<Annotation>,
    /// `None` is matplotlib's "auto"; a number is the y-unit/x-unit scale
    /// (1.0 == "equal").
    #[pyo3(item)]
    aspect: Option<f64>,
    #[pyo3(item)]
    contours: Vec<ContourItem<'py>>,
    #[pyo3(item)]
    errors: Vec<ErrorItem<'py>>,
    #[pyo3(item)]
    scatter: Vec<Scatter<'py>>,
    #[pyo3(item)]
    bars: Vec<Bar<'py>>,
    #[pyo3(item)]
    bands: Vec<Band<'py>>,
    #[pyo3(item)]
    grid: bool,
    #[pyo3(item)]
    x_log: bool,
    #[pyo3(item)]
    y_log: bool,
    #[pyo3(item)]
    log_base: f64,
    #[pyo3(item)]
    colorbar: Option<ColorbarItem>,
    /// `axis("off")`: keep the data, drop axes, ticks and tick labels.
    #[pyo3(item)]
    axis_off: bool,
}

/// Stroke a polyline as dashes, in panel-local pixels.
fn draw_dashed<DB: DrawingBackend, C: Color>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    pts: &[(i32, i32)],
    col: C,
    width: u32,
    dash: f64,
    gap: f64,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let mut on = true;
    let mut left = dash;
    for pair in pts.windows(2) {
        let (x0, y0) = (pair[0].0 as f64, pair[0].1 as f64);
        let (x1, y1) = (pair[1].0 as f64, pair[1].1 as f64);
        let (dx, dy) = (x1 - x0, y1 - y0);
        let len = (dx * dx + dy * dy).sqrt();
        if len <= 0.0 {
            continue;
        }
        let (ux, uy) = (dx / len, dy / len);
        let mut t = 0.0;
        while t < len {
            let seg = left.min(len - t);
            if on {
                let a = (x0 + ux * t, y0 + uy * t);
                let b = (x0 + ux * (t + seg), y0 + uy * (t + seg));
                area.draw(&PathElement::new(
                    vec![
                        (a.0.round() as i32, a.1.round() as i32),
                        (b.0.round() as i32, b.1.round() as i32),
                    ],
                    col.stroke_width(width),
                ))?;
            }
            t += seg;
            left -= seg;
            if left <= f64::EPSILON {
                on = !on;
                left = if on { dash } else { gap };
            }
        }
    }
    Ok(())
}

/// One `bar`/`barh` call: axis-aligned rectangles in data coordinates.
#[derive(FromPyObject)]
struct Bar<'py> {
    #[pyo3(item)]
    left: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    bottom: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    width: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    height: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    colors: Vec<String>,
    #[pyo3(item)]
    edgecolor: Option<String>,
    #[pyo3(item)]
    alpha: Option<f64>,
    #[pyo3(item)]
    label: String,
}

/// One closed filled area (`fill_between`/`fill`) in data coordinates.
#[derive(FromPyObject)]
struct Band<'py> {
    #[pyo3(item)]
    x: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    y: PyReadonlyArray1<'py, f64>,
    #[pyo3(item)]
    color: String,
    #[pyo3(item)]
    alpha: Option<f64>,
    #[pyo3(item)]
    label: String,
}

/// One scatter marker centred on canvas pixel `pos`, with pixel radius `r`.
fn draw_marker<DB: DrawingBackend, C: Color>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    base: (i32, i32),
    pos: (i32, i32),
    r: f64,
    col: C,
    stroke: u32,
    marker: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (x, y) = (pos.0 - base.0, pos.1 - base.1);
    let ri = r.round().max(1.0) as i32;
    match marker {
        "s" => area.draw(&Rectangle::new(
            [(x - ri, y - ri), (x + ri, y + ri)],
            col.filled(),
        ))?,
        "^" => area.draw(&Polygon::new(
            vec![(x, y - ri), (x + ri, y + ri), (x - ri, y + ri)],
            col.filled(),
        ))?,
        "v" => area.draw(&Polygon::new(
            vec![(x, y + ri), (x + ri, y - ri), (x - ri, y - ri)],
            col.filled(),
        ))?,
        "<" => area.draw(&Polygon::new(
            vec![(x - ri, y), (x + ri, y + ri), (x + ri, y - ri)],
            col.filled(),
        ))?,
        ">" => area.draw(&Polygon::new(
            vec![(x + ri, y), (x - ri, y + ri), (x - ri, y - ri)],
            col.filled(),
        ))?,
        "D" => area.draw(&Polygon::new(
            vec![(x, y - ri), (x + ri, y), (x, y + ri), (x - ri, y)],
            col.filled(),
        ))?,
        "x" => {
            area.draw(&PathElement::new(
                vec![(x - ri, y - ri), (x + ri, y + ri)],
                col.stroke_width(stroke),
            ))?;
            area.draw(&PathElement::new(
                vec![(x - ri, y + ri), (x + ri, y - ri)],
                col.stroke_width(stroke),
            ))?;
        }
        "+" => {
            area.draw(&PathElement::new(
                vec![(x - ri, y), (x + ri, y)],
                col.stroke_width(stroke),
            ))?;
            area.draw(&PathElement::new(
                vec![(x, y - ri), (x, y + ri)],
                col.stroke_width(stroke),
            ))?;
        }
        "." => area.draw(&Circle::new((x, y), (ri / 2).max(1) as u32, col.filled()))?,
        _ => area.draw(&Circle::new((x, y), ri as u32, col.filled()))?,
    }
    Ok(())
}

fn num(v: f64) -> String {
    let s = format!("{v:.4}");
    let s = s.trim_end_matches('0').trim_end_matches('.').to_string();
    if s.is_empty() || s == "-0" {
        "0".to_string()
    } else {
        s
    }
}

/// A vertical gradient strip with min/mid/max ticks and an optional axis label.
fn draw_colorbar<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    cmap: &str,
    vmin: f64,
    vmax: f64,
    label: &str,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (w, h) = area.dim_in_pixel();
    let (x0, x1) = (14i32, 44i32);
    let (y0, y1) = (12i32, h as i32 - 26);
    if x1 >= w as i32 || y1 - y0 < 4 {
        return Ok(());
    }
    let steps = y1 - y0;
    for i in 0..steps {
        let t = 1.0 - (i as f64 + 0.5) / steps as f64;
        let c = colormap(cmap, t);
        area.draw(&Rectangle::new(
            [(x0, y0 + i), (x1, y0 + i + 1)],
            RGBColor(c[0], c[1], c[2]).filled(),
        ))?;
    }
    let frame = RGBColor(90, 90, 90);
    area.draw(&Rectangle::new([(x0, y0), (x1, y1)], frame.stroke_width(1)))?;
    let mid = (vmin + vmax) / 2.0;
    for (t, v) in [(0.0, vmin), (0.5, mid), (1.0, vmax)] {
        let y = (y0 as f64 + (1.0 - t) * (y1 - y0) as f64).round() as i32;
        area.draw(&PathElement::new(
            vec![(x0 - 4, y), (x0, y)],
            frame.stroke_width(1),
        ))?;
        draw_label(
            area,
            (0, 0),
            (x1 + 6, y),
            &num(v),
            RGBColor(0, 0, 0),
            13.0,
            "left",
            "center",
        )?;
    }
    if !label.is_empty() {
        draw_label(
            area,
            (0, 0),
            (x1 + 6, h as i32 - 6),
            label,
            RGBColor(0, 0, 0),
            14.0,
            "left",
            "bottom",
        )?;
    }
    Ok(())
}

/// One level of a marching-squares pass: iso-line segments in data coordinates.
fn contour_segments(x: &[f64], y: &[f64], z: &[f64], level: f64) -> Vec<((f64, f64), (f64, f64))> {
    let (rows, cols) = (y.len(), x.len());
    let mut out = Vec::new();
    if rows < 2 || cols < 2 || z.len() != rows * cols {
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

/// Clip a triangle (x, y, value) to `lo <= value <= hi`.
fn clip_band(tri: &[(f64, f64, f64); 3], lo: f64, hi: f64) -> Vec<(f64, f64, f64)> {
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

/// Tick label for a linear axis: short, without float noise.
fn tick_label(v: f64) -> String {
    if v == 0.0 {
        return "0".to_string();
    }
    let a = v.abs();
    if a >= 1e5 || a < 1e-3 {
        format!("{v:.2e}")
    } else {
        format!("{v:.4}")
            .trim_end_matches('0')
            .trim_end_matches('.')
            .to_string()
    }
}

/// Tick label for a log coordinate: base^v written as a plain number.
fn log_label(v: f64, base: f64) -> String {
    let value = base.powf(v);
    if value >= 1e5 || value < 1e-4 {
        format!("{value:.0e}")
    } else {
        format!("{value:.4}")
            .trim_end_matches('0')
            .trim_end_matches('.')
            .to_string()
    }
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

fn draw_panel<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    p: &Panel,
    overlays: &mut Vec<String>,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    if let Some((cmap, vmin, vmax, label)) = &p.colorbar {
        return draw_colorbar(area, cmap, *vmin, *vmax, label);
    }
    let (mut x0, mut x1, mut y0, mut y1) = panel_ranges(p);
    // Log axes are laid out in log10 space: the ranges and every mapped point are
    // transformed, and the tick labels are converted back to powers of ten.
    let base = if p.log_base > 1.0 { p.log_base } else { 10.0 };
    let tx = |v: f64| {
        if p.x_log {
            v.max(f64::MIN_POSITIVE).log(base)
        } else {
            v
        }
    };
    let ty = |v: f64| {
        if p.y_log {
            v.max(f64::MIN_POSITIVE).log(base)
        } else {
            v
        }
    };
    if p.x_log {
        (x0, x1) = (tx(x0), tx(x1));
        if x1 <= x0 {
            x1 = x0 + 1.0;
        }
    }
    if p.y_log {
        (y0, y1) = (ty(y0), ty(y1));
        if y1 <= y0 {
            y1 = y0 + 1.0;
        }
    }
    // A fixed aspect shrinks the plotting box instead of bending the data limits,
    // like matplotlib's adjustable="box".
    let shrunk_area;
    let mut chart = ChartBuilder::on(area)
        .caption(&p.title, ("sans-serif", 24))
        .margin(10)
        .x_label_area_size(40)
        .y_label_area_size(55)
        .build_cartesian_2d(x0..x1, y0..y1)?;
    if let Some(scale) = p.aspect {
        let (pw, ph) = chart.plotting_area().dim_in_pixel();
        let ratio = (x1 - x0) / (y1 - y0) / scale;
        if pw > 8 && ph > 8 && ratio.is_finite() && ratio > 0.0 {
            let mut dw = 0i32;
            let mut dh = 0i32;
            if pw as f64 / ph as f64 > ratio {
                dw = (pw as f64 - ratio * ph as f64).round() as i32;
            } else {
                dh = (ph as f64 - pw as f64 / ratio).round() as i32;
            }
            if dw > 0 || dh > 0 {
                shrunk_area = area.margin(dh / 2, dh - dh / 2, dw / 2, dw - dw / 2);
                chart = ChartBuilder::on(&shrunk_area)
                    .caption(&p.title, ("sans-serif", 24))
                    .margin(10)
                    .x_label_area_size(40)
                    .y_label_area_size(55)
                    .build_cartesian_2d(x0..x1, y0..y1)?;
            }
        }
    }
    if !p.axis_off {
        let x_fmt = move |v: &f64| {
            if p.x_log {
                log_label(*v, base)
            } else {
                tick_label(*v)
            }
        };
        let y_fmt = move |v: &f64| {
            if p.y_log {
                log_label(*v, base)
            } else {
                tick_label(*v)
            }
        };
        let mut mesh = chart.configure_mesh();
        if !p.grid {
            mesh.disable_mesh();
        }
        mesh.x_desc(&p.xlabel)
            .y_desc(&p.ylabel)
            .x_label_formatter(&x_fmt)
            .y_label_formatter(&y_fmt)
            .draw()?;
    }
    // Filled contours sit on the image layer, under the line series.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, z, levels, colors, cmap, filled) in &p.contours {
            if !*filled || levels.len() < 2 {
                continue;
            }
            let xs: Vec<f64> = x.as_array().iter().copied().collect();
            let ys: Vec<f64> = y.as_array().iter().copied().collect();
            let zs: Vec<f64> = z.as_array().iter().copied().collect();
            let (rows, cols) = (ys.len(), xs.len());
            if rows < 2 || cols < 2 || zs.len() != rows * cols {
                continue;
            }
            let bands = levels.len() - 1;
            for band in 0..bands {
                let (lo, hi) = (levels[band], levels[band + 1]);
                let col = if colors.is_empty() {
                    let c = colormap(cmap, (band as f64 + 0.5) / bands as f64);
                    RGBColor(c[0], c[1], c[2])
                } else {
                    color(&colors[band % colors.len()])
                };
                for i in 0..rows - 1 {
                    for j in 0..cols - 1 {
                        let p00 = (xs[j], ys[i], zs[i * cols + j]);
                        let p01 = (xs[j + 1], ys[i], zs[i * cols + j + 1]);
                        let p10 = (xs[j], ys[i + 1], zs[(i + 1) * cols + j]);
                        let p11 = (xs[j + 1], ys[i + 1], zs[(i + 1) * cols + j + 1]);
                        // Split each cell into two triangles: a band cut through a triangle
                        // is an exact polygon for piecewise-linear interpolation.
                        for tri in [[p00, p01, p11], [p00, p11, p10]] {
                            let poly = clip_band(&tri, lo, hi);
                            if poly.len() < 3 {
                                continue;
                            }
                            let pts: Vec<(i32, i32)> = poly
                                .iter()
                                .map(|&(px, py, _)| {
                                    let (ax, ay) = chart_area.map_coordinate(&(tx(px), ty(py)));
                                    (ax - base.0, ay - base.1)
                                })
                                .collect();
                            area.draw(&Polygon::new(pts, col.filled()))?;
                        }
                    }
                }
            }
        }
    }
    // Filled areas (`fill_between`/`fill`): closed data-space polygons.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        let mut legend_bands: Vec<(String, RGBAColor)> = Vec::new();
        for band in &p.bands {
            let (xs, ys) = (band.x.as_array(), band.y.as_array());
            if xs.len() < 3 || xs.len() != ys.len() {
                continue;
            }
            let pts: Vec<(i32, i32)> = xs
                .iter()
                .zip(ys.iter())
                .map(|(x, y)| {
                    let (px, py) = chart_area.map_coordinate(&(tx(*x), ty(*y)));
                    (px - base.0, py - base.1)
                })
                .collect();
            let col = match band.alpha {
                Some(a) => color(&band.color).mix(a.clamp(0.0, 1.0)),
                None => color(&band.color).mix(1.0),
            };
            area.draw(&Polygon::new(pts, col.filled()))?;
            if !band.label.is_empty() {
                legend_bands.push((band.label.clone(), col));
            }
        }
        // Registered once the plotting-area borrow is released.
        for (label, col) in legend_bands {
            let series = chart.draw_series(std::iter::once(Rectangle::new(
                [(0.0f64, 0.0f64), (0.0f64, 0.0f64)],
                RGBColor(0, 0, 0).mix(0.0).filled(),
            )))?;
            series
                .label(label.as_str())
                .legend(move |(x, y)| Rectangle::new([(x, y - 3), (x + 20, y + 7)], col.filled()));
        }
    }
    // Bars: axis-aligned rectangles, above the filled contours and below lines.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        let mut legend_bars: Vec<(String, RGBAColor)> = Vec::new();
        for bars in &p.bars {
            let (l, b) = (bars.left.as_array(), bars.bottom.as_array());
            let (w, h) = (bars.width.as_array(), bars.height.as_array());
            let mut swatch: Option<RGBAColor> = None;
            for i in 0..l.len().min(b.len()).min(w.len()).min(h.len()) {
                let col = if bars.colors.is_empty() {
                    RGBColor(31, 119, 180)
                } else {
                    color(&bars.colors[i % bars.colors.len()])
                };
                let col = match bars.alpha {
                    Some(a) => col.mix(a.clamp(0.0, 1.0)),
                    None => col.mix(1.0),
                };
                if swatch.is_none() {
                    swatch = Some(col);
                }
                let (x0, y0) = chart_area.map_coordinate(&(tx(l[i]), ty(b[i])));
                let (x1, y1) = chart_area.map_coordinate(&(tx(l[i] + w[i]), ty(b[i] + h[i])));
                let (xl, xr) = (x0.min(x1) - base.0, x0.max(x1) - base.0);
                let (yt, yb) = (y0.min(y1) - base.1, y0.max(y1) - base.1);
                if xr <= xl || yb <= yt {
                    continue;
                }
                area.draw(&Rectangle::new([(xl, yt), (xr, yb)], col.filled()))?;
                if let Some(ec) = &bars.edgecolor {
                    let ecol = color(ec).stroke_width(1);
                    area.draw(&Rectangle::new([(xl, yt), (xr, yb)], ecol))?;
                }
            }
            if !bars.label.is_empty() {
                let cs = swatch.unwrap_or_else(|| RGBColor(31, 119, 180).mix(1.0));
                legend_bars.push((bars.label.clone(), cs));
            }
        }
        // Registered after the loop so the plotting-area borrow on `chart` has ended.
        for (label, cs) in legend_bars {
            // A transparent zero-size rectangle only carries the legend entry; the
            // closure paints a filled swatch instead of a line.
            let series = chart.draw_series(std::iter::once(Rectangle::new(
                [(0.0f64, 0.0f64), (0.0f64, 0.0f64)],
                RGBColor(0, 0, 0).mix(0.0).filled(),
            )))?;
            series
                .label(label.as_str())
                .legend(move |(x, y)| Rectangle::new([(x, y - 3), (x + 20, y + 7)], cs.filled()));
        }
    }
    for s in &p.series {
        let base = area.get_base_pixel();
        let xs = s.x.as_array();
        let ys = s.y.as_array();
        let n = xs.len().min(ys.len());
        // Step drawstyles insert the corner points instead of a diagonal.
        let mut pts: Vec<(f64, f64)> = Vec::with_capacity(n * 2);
        for i in 0..n {
            pts.push((tx(xs[i]), ty(ys[i])));
            if i + 1 < n {
                match s.drawstyle.as_str() {
                    "steps-post" => pts.push((tx(xs[i + 1]), ty(ys[i]))),
                    "steps-pre" => pts.push((tx(xs[i]), ty(ys[i + 1]))),
                    _ => {}
                }
            }
        }
        let width = s.linewidth.max(1.0).round() as u32;
        let col = match s.alpha {
            Some(a) => color(&s.color).mix(a.clamp(0.0, 1.0)),
            None => color(&s.color).mix(1.0),
        };
        if matches!(s.linestyle.as_str(), ":" | "--" | "-.") {
            let (dash, gap) = match s.linestyle.as_str() {
                ":" => (2.0, 4.0),
                "--" => (9.0, 5.0),
                _ => (7.0, 3.0),
            };
            let px: Vec<(i32, i32)> = {
                let chart_area = chart.plotting_area();
                pts.iter()
                    .map(|p| {
                        let (x, y) = chart_area.map_coordinate(p);
                        (x - base.0, y - base.1)
                    })
                    .collect()
            };
            draw_dashed(area, &px, col, width, dash, gap)?;
            if !s.label.is_empty() {
                chart
                    .draw_series(LineSeries::new(
                        Vec::<(f64, f64)>::new(),
                        col.stroke_width(width),
                    ))?
                    .label(s.label.as_str())
                    .legend(move |(x, y)| {
                        PathElement::new(vec![(x, y), (x + 20, y)], col.stroke_width(width))
                    });
            }
        } else {
            let series = chart.draw_series(LineSeries::new(pts, col.stroke_width(width)))?;
            if !s.label.is_empty() {
                series.label(s.label.as_str()).legend(move |(x, y)| {
                    PathElement::new(vec![(x, y), (x + 20, y)], col.stroke_width(width))
                });
            }
        }
        if !s.marker.is_empty() && s.markersize > 0.0 {
            let stroked = matches!(s.marker.as_str(), "x" | "+");
            let name = if stroked {
                s.mec.as_deref().unwrap_or(&s.color)
            } else {
                s.mfc.as_deref().unwrap_or(&s.color)
            };
            let mc = match s.alpha {
                Some(a) => color(name).mix(a.clamp(0.0, 1.0)),
                None => color(name).mix(1.0),
            };
            let r = (s.markersize / 2.0 * 1.39).max(1.0);
            let stroke = s.mew.max(1.0).round() as u32;
            let chart_area = chart.plotting_area();
            for (xv, yv) in xs.iter().zip(ys.iter()) {
                let (px, py) = chart_area.map_coordinate(&(tx(*xv), ty(*yv)));
                draw_marker(area, base, (px, py), r, mc, stroke, &s.marker)?;
            }
        }
    }
    // Error bars: one segment per point plus optional caps, in canvas pixels.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, ylo, yhi, xlo, xhi, c, cap) in &p.errors {
            let col = color(c);
            let cap = cap.round().max(0.0) as i32;
            let (ya, yb) = (ylo.as_array(), yhi.as_array());
            let (xa, xb) = (xlo.as_array(), xhi.as_array());
            let (xs_v, ys_v) = (x.as_array(), y.as_array());
            let yz = ya.iter().zip(yb.iter());
            let xz = xa.iter().zip(xb.iter());
            let it = xs_v.iter().zip(ys_v.iter());
            for ((xv, yv), ((lo, hi), (xl, xh))) in it.zip(yz.zip(xz)) {
                let (cx, cy) = chart_area.map_coordinate(&(tx(*xv), ty(*yv)));
                let (cx, cy) = (cx - base.0, cy - base.1);
                if *lo > 0.0 || *hi > 0.0 {
                    let (_, yt) = chart_area.map_coordinate(&(tx(*xv), ty(*yv + *hi)));
                    let (_, yb) = chart_area.map_coordinate(&(tx(*xv), ty(*yv - *lo)));
                    let (yt, yb) = (yt - base.1, yb - base.1);
                    area.draw(&PathElement::new(
                        vec![(cx, yt), (cx, yb)],
                        col.stroke_width(1),
                    ))?;
                    if cap > 0 {
                        for yc in [yt, yb] {
                            area.draw(&PathElement::new(
                                vec![(cx - cap, yc), (cx + cap, yc)],
                                col.stroke_width(1),
                            ))?;
                        }
                    }
                }
                if *xl > 0.0 || *xh > 0.0 {
                    let (xl_px, _) = chart_area.map_coordinate(&(tx(*xv - *xl), ty(*yv)));
                    let (xr_px, _) = chart_area.map_coordinate(&(tx(*xv + *xh), ty(*yv)));
                    let (xl_px, xr_px) = (xl_px - base.0, xr_px - base.0);
                    area.draw(&PathElement::new(
                        vec![(xl_px, cy), (xr_px, cy)],
                        col.stroke_width(1),
                    ))?;
                    if cap > 0 {
                        for xc in [xl_px, xr_px] {
                            area.draw(&PathElement::new(
                                vec![(xc, cy - cap), (xc, cy + cap)],
                                col.stroke_width(1),
                            ))?;
                        }
                    }
                }
            }
        }
    }
    // Scatter markers: per-point size and colour, so they bypass PointSeries.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        let mut legend_scatter: Vec<(String, RGBAColor)> = Vec::new();
        for sc in &p.scatter {
            let xs = sc.x.as_array();
            let ys = sc.y.as_array();
            let sizes = sc.sizes.as_array();
            let values = sc.values.as_ref().map(|v| v.as_array());
            let (cmin, cmax) = sc.clim.unwrap_or_else(|| match &values {
                Some(v) => range(v.iter().copied()),
                None => (0.0, 1.0),
            });
            let alpha = sc.alpha.clamp(0.0, 1.0);
            for i in 0..xs.len().min(ys.len()) {
                let (cx, cy) = chart_area.map_coordinate(&(tx(xs[i]), ty(ys[i])));
                // matplotlib's `s` is an area in points^2; ~1.39 px/pt at 100 dpi.
                let sz = sizes.get(i).copied().unwrap_or(36.0).max(0.0);
                let r = (sz.sqrt() / 2.0 * 1.39).max(1.0);
                let col = if !sc.colors.is_empty() {
                    color(&sc.colors[i % sc.colors.len()])
                } else if let Some(v) = &values {
                    let t = if cmax > cmin {
                        ((v[i] - cmin) / (cmax - cmin)).clamp(0.0, 1.0)
                    } else {
                        0.5
                    };
                    let c = colormap(&sc.cmap, t);
                    RGBColor(c[0], c[1], c[2])
                } else {
                    RGBColor(31, 119, 180)
                };
                draw_marker(area, base, (cx, cy), r, col.mix(alpha), 2, &sc.marker)?;
            }
            if !sc.label.is_empty() {
                let icon = if sc.colors.is_empty() {
                    RGBColor(31, 119, 180)
                } else {
                    color(&sc.colors[0])
                };
                legend_scatter.push((sc.label.clone(), icon.mix(alpha)));
            }
        }
        // Registered once the plotting-area borrow is released.
        for (label, col) in legend_scatter {
            let series = chart.draw_series(std::iter::once(Rectangle::new(
                [(0.0f64, 0.0f64), (0.0f64, 0.0f64)],
                RGBColor(0, 0, 0).mix(0.0).filled(),
            )))?;
            series
                .label(label.as_str())
                .legend(move |(x, y)| Circle::new((x + 10, y + 4), 4, col.filled()));
        }
    }
    // Iso-lines are stroked above the series, one segment per marching-squares cell.
    {
        let chart_area = chart.plotting_area();
        let base = area.get_base_pixel();
        for (x, y, z, levels, colors, cmap, filled) in &p.contours {
            if *filled || levels.is_empty() {
                continue;
            }
            let xs: Vec<f64> = x.as_array().iter().copied().collect();
            let ys: Vec<f64> = y.as_array().iter().copied().collect();
            let zs: Vec<f64> = z.as_array().iter().copied().collect();
            let (rows, cols) = (ys.len(), xs.len());
            if rows < 2 || cols < 2 || zs.len() != rows * cols {
                continue;
            }
            let n = levels.len() as f64;
            for (li, level) in levels.iter().enumerate() {
                let col = if colors.is_empty() {
                    let t = if n > 1.0 { li as f64 / (n - 1.0) } else { 0.5 };
                    let c = colormap(cmap, t);
                    RGBColor(c[0], c[1], c[2])
                } else {
                    color(&colors[li % colors.len()])
                };
                for (a, b) in contour_segments(&xs, &ys, &zs, *level) {
                    let (ax, ay) = chart_area.map_coordinate(&(tx(a.0), ty(a.1)));
                    let (bx, by) = chart_area.map_coordinate(&(tx(b.0), ty(b.1)));
                    area.draw(&PathElement::new(
                        vec![(ax - base.0, ay - base.1), (bx - base.0, by - base.1)],
                        col.stroke_width(2),
                    ))?;
                }
            }
        }
    }
    {
        let chart_area = chart.plotting_area();
        // map_coordinate yields canvas-absolute pixels; the panel's own area re-applies
        // its origin, so anything drawn on it shifts back to cell-local pixels.
        let base = area.get_base_pixel();
        for (x, y, s, c, size, ha, va) in &p.texts {
            let pos = chart_area.map_coordinate(&(tx(*x), ty(*y)));
            draw_label(area, base, pos, s, color(c), *size, ha, va)?;
        }
        for (text, xy, xytext, c, size) in &p.annotations {
            let target = chart_area.map_coordinate(&(tx(xy.0), ty(xy.1)));
            let anchor = match xytext {
                Some(t) => chart_area.map_coordinate(&(tx(t.0), ty(t.1))),
                None => target,
            };
            if xytext.is_some() {
                draw_arrow(area, base, anchor, target, color(c))?;
            }
            draw_label(
                area,
                base,
                anchor,
                text,
                color(c),
                *size,
                "left",
                "baseline",
            )?;
        }
        for item in &p.images {
            let (l, r, b, t) = item.4;
            let (ax, ay) = chart_area.map_coordinate(&(tx(l), ty(t)));
            let (zx, zy) = chart_area.map_coordinate(&(tx(r), ty(b)));
            let (iw, ih) = ((ax - zx).abs(), (ay - zy).abs());
            if iw == 0 || ih == 0 {
                continue;
            }
            // Embedded into the root SVG, so this stays in canvas pixels.
            overlays.push(format!(
                "<image x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" \
                 preserveAspectRatio=\"none\" href=\"data:image/png;base64,{}\"/>",
                ax.min(zx),
                ay.min(zy),
                iw,
                ih,
                base64(&image_png(item)?)
            ));
        }
    }
    if p.legend {
        chart
            .configure_series_labels()
            .background_style(WHITE.mix(0.8))
            .border_style(BLACK)
            .draw()?;
    }
    Ok(())
}

/// Render all panels to an SVG string via plotters.
fn render_svg(
    size: (u32, u32),
    grid: (usize, usize),
    panels: &[Panel],
    transparent: bool,
) -> Result<String, String> {
    let (w, h) = size;
    let mut svg = String::new();
    let mut overlays: Vec<String> = Vec::new();
    {
        let root = SVGBackend::with_string(&mut svg, (w, h)).into_drawing_area();
        // A transparent figure gets no background rect at all, so the SVG (and the
        // PNG rasterised from it) keeps alpha where nothing was drawn.
        if !transparent {
            root.fill(&WHITE).map_err(|e| e.to_string())?;
        }
        let cells = root.split_evenly(grid);
        for p in panels {
            draw_panel(
                cells.get(p.pos).ok_or("subplot index out of range")?,
                p,
                &mut overlays,
            )
            .map_err(|e| e.to_string())?;
        }
        root.present().map_err(|e| e.to_string())?;
    }
    for tag in &overlays {
        svg = insert_overlay(&svg, tag);
    }
    Ok(svg)
}

/// Rasterise an SVG string via resvg + tiny-skia.
/// Fonts embedded in `build_fontdb()` are used — no system fonts needed.
fn rasterize(svg: &str, w: u32, h: u32, transparent: bool) -> Result<tiny_skia::Pixmap, String> {
    let fontdb = std::sync::Arc::new(build_fontdb());
    let opts = usvg::Options {
        fontdb: fontdb.clone(),
        ..Default::default()
    };
    let tree = usvg::Tree::from_str(svg, &opts).map_err(|e| e.to_string())?;
    let mut pixmap = tiny_skia::Pixmap::new(w, h).ok_or("failed to allocate pixmap")?;
    if !transparent {
        pixmap.fill(tiny_skia::Color::WHITE);
    }
    resvg::render(
        &tree,
        tiny_skia::Transform::identity(),
        &mut pixmap.as_mut(),
    );
    Ok(pixmap)
}

type Bbox = (u32, u32, u32, u32); // x, y, width, height

/// Smallest rectangle containing drawn pixels, or `None` if the figure is blank.
fn content_bbox(pixmap: &tiny_skia::Pixmap, transparent: bool) -> Option<Bbox> {
    let (w, h) = (pixmap.width(), pixmap.height());
    let data = pixmap.data();
    let (mut x0, mut y0, mut x1, mut y1) = (w, h, 0u32, 0u32);
    let mut found = false;
    for y in 0..h {
        for x in 0..w {
            let i = ((y * w + x) * 4) as usize;
            let px = &data[i..i + 4];
            let drawn = if transparent {
                px[3] != 0
            } else {
                !(px[0] == 255 && px[1] == 255 && px[2] == 255)
            };
            if drawn {
                found = true;
                x0 = x0.min(x);
                y0 = y0.min(y);
                x1 = x1.max(x);
                y1 = y1.max(y);
            }
        }
    }
    found.then(|| (x0, y0, x1 - x0 + 1, y1 - y0 + 1))
}

/// Copy `bbox` out of a pixmap — used for `bbox_inches="tight"` PNGs.
fn crop_pixmap(
    pixmap: &tiny_skia::Pixmap,
    (bx, by, bw, bh): Bbox,
) -> Result<tiny_skia::Pixmap, String> {
    let mut out = tiny_skia::Pixmap::new(bw, bh).ok_or("failed to allocate pixmap")?;
    let (src, sw) = (pixmap.data(), pixmap.width());
    for y in 0..bh {
        for x in 0..bw {
            let s = (((by + y) * sw + (bx + x)) * 4) as usize;
            let d = ((y * bw + x) * 4) as usize;
            out.data_mut()[d..d + 4].copy_from_slice(&src[s..s + 4]);
        }
    }
    Ok(out)
}

/// Remove `name="..."` from an SVG tag string.
fn drop_attr(tag: &str, name: &str) -> String {
    let pat = format!("{name}=\"");
    let Some(i) = tag.find(&pat) else {
        return tag.to_string();
    };
    let start = if i > 0 && tag.as_bytes()[i - 1] == b' ' {
        i - 1
    } else {
        i
    };
    let vstart = i + pat.len();
    let vend = tag[vstart..]
        .find('"')
        .map(|j| vstart + j + 1)
        .unwrap_or(tag.len());
    format!("{}{}", &tag[..start], &tag[vend..])
}

/// Crop an SVG by rewriting its root width/height/viewBox — stays vector.
fn svg_tight(svg: &str, (bx, by, bw, bh): Bbox) -> Option<String> {
    let start = svg.find("<svg")?;
    let end = start + svg[start..].find('>')?;
    let mut tag = svg[start..end].to_string();
    for attr in ["width", "height", "viewBox"] {
        tag = drop_attr(&tag, attr);
    }
    let tag = format!("{tag} width=\"{bw}\" height=\"{bh}\" viewBox=\"{bx} {by} {bw} {bh}\"");
    Some(format!("{}{}{}", &svg[..start], tag, &svg[end..]))
}

/// Render series and write to `path`.
///
/// `format` overrides the extension ("png" or "svg"); otherwise it is inferred
/// from `path`. `bbox_inches="tight"` crops to the drawn content.
#[pyfunction]
#[pyo3(signature = (path, size, grid, panels, format=None, transparent=false, bbox_inches=None))]
fn save(
    path: &str,
    size: (u32, u32),
    grid: (usize, usize),
    panels: Vec<Panel>,
    format: Option<String>,
    transparent: bool,
    bbox_inches: Option<String>,
) -> PyResult<()> {
    let err = |e: &str| PyRuntimeError::new_err(e.to_string());
    register_plotters_fonts();
    if panels.iter().all(|p| {
        p.series.is_empty()
            && p.texts.is_empty()
            && p.images.is_empty()
            && p.annotations.is_empty()
            && p.contours.is_empty()
            && p.errors.is_empty()
            && p.scatter.is_empty()
            && p.bars.is_empty()
            && p.bands.is_empty()
            && p.colorbar.is_none()
    }) {
        return Err(PyRuntimeError::new_err("nothing to plot"));
    }
    let fmt = match format {
        Some(f) => f.to_lowercase(),
        None if path.to_lowercase().ends_with(".svg") => "svg".to_string(),
        None => "png".to_string(),
    };
    if fmt != "png" && fmt != "svg" {
        return Err(err(&format!("unsupported format: {fmt}")));
    }
    let tight = match bbox_inches.as_deref() {
        None => false,
        Some("tight") => true,
        Some(other) => return Err(err(&format!("unsupported bbox_inches: {other}"))),
    };

    let (w, h) = size;
    let svg = render_svg(size, grid, &panels, transparent).map_err(|e| err(&e))?;
    let bytes: Vec<u8> = if fmt == "svg" {
        match (
            tight,
            rasterize(&svg, w, h, transparent)
                .ok()
                .and_then(|p| content_bbox(&p, transparent)),
        ) {
            (true, Some(bbox)) => svg_tight(&svg, bbox).unwrap_or(svg).into_bytes(),
            _ => svg.into_bytes(),
        }
    } else {
        let pixmap = rasterize(&svg, w, h, transparent).map_err(|e| err(&e))?;
        let pixmap = match if tight {
            content_bbox(&pixmap, transparent)
        } else {
            None
        } {
            Some(bbox) => crop_pixmap(&pixmap, bbox).map_err(|e| err(&e))?,
            None => pixmap,
        };
        pixmap.encode_png().map_err(|e| err(&e.to_string()))?
    };
    std::fs::write(path, bytes).map_err(|e| err(&e.to_string()))
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(save, m)?)
}
