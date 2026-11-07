use numpy::{PyReadonlyArray1, PyReadonlyArrayDyn};
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

type Series<'py> = (
    PyReadonlyArray1<'py, f64>,
    PyReadonlyArray1<'py, f64>,
    String,
    String,
);

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
        xs.extend(s.0.as_array().iter().copied());
        ys.extend(s.1.as_array().iter().copied());
    }
    for im in &p.images {
        let (l, r, b, t) = im.4;
        xs.extend([l, r]);
        ys.extend([b, t]);
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
}

fn draw_panel<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    p: &Panel,
    overlays: &mut Vec<String>,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let (x0, x1, y0, y1) = panel_ranges(p);
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
    chart
        .configure_mesh()
        .disable_mesh()
        .x_desc(&p.xlabel)
        .y_desc(&p.ylabel)
        .draw()?;
    for (x, y, label, c) in &p.series {
        let col = color(c);
        let pts = x
            .as_array()
            .iter()
            .zip(y.as_array().iter())
            .map(|(a, b)| (*a, *b))
            .collect::<Vec<_>>();
        let s = chart.draw_series(LineSeries::new(pts, col.stroke_width(2)))?;
        if !label.is_empty() {
            s.label(label.as_str()).legend(move |(x, y)| {
                PathElement::new(vec![(x, y), (x + 20, y)], col.stroke_width(2))
            });
        }
    }
    {
        let chart_area = chart.plotting_area();
        // map_coordinate yields canvas-absolute pixels; the panel's own area re-applies
        // its origin, so anything drawn on it shifts back to cell-local pixels.
        let base = area.get_base_pixel();
        for (x, y, s, c, size, ha, va) in &p.texts {
            let pos = chart_area.map_coordinate(&(*x, *y));
            draw_label(area, base, pos, s, color(c), *size, ha, va)?;
        }
        for (text, xy, xytext, c, size) in &p.annotations {
            let target = chart_area.map_coordinate(xy);
            let anchor = match xytext {
                Some(t) => chart_area.map_coordinate(t),
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
            let (ax, ay) = chart_area.map_coordinate(&(l, t));
            let (zx, zy) = chart_area.map_coordinate(&(r, b));
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
        p.series.is_empty() && p.texts.is_empty() && p.images.is_empty() && p.annotations.is_empty()
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
