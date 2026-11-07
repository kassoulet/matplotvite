use numpy::PyReadonlyArray1;
use plotters::prelude::*;
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
}

fn draw_panel<DB: DrawingBackend>(
    area: &DrawingArea<DB, plotters::coord::Shift>,
    p: &Panel,
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    let auto = |f: fn(&Series) -> Vec<f64>| {
        if p.series.is_empty() {
            (0.0, 1.0)
        } else {
            range(p.series.iter().flat_map(f))
        }
    };
    let (x0, x1) = p.xlim.unwrap_or_else(|| auto(|s| s.0.as_array().to_vec()));
    let (y0, y1) = p.ylim.unwrap_or_else(|| auto(|s| s.1.as_array().to_vec()));
    let mut chart = ChartBuilder::on(area)
        .caption(&p.title, ("sans-serif", 24))
        .margin(10)
        .x_label_area_size(40)
        .y_label_area_size(55)
        .build_cartesian_2d(x0..x1, y0..y1)?;
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
        use plotters::style::IntoFont;
        let chart_area = chart.plotting_area();
        // map_coordinate yields canvas-absolute pixels, but drawing on the panel's own
        // area re-applies that panel's origin, so shift back to cell-local pixels.
        let (bx, by) = area.get_base_pixel();
        for (x, y, s, c, size, ha, va) in &p.texts {
            let (px, py) = chart_area.map_coordinate(&(*x, *y));
            let fs = size.max(1.0);
            // Text width has to be estimated to honour alignment: the backend only
            // exposes the top-left anchor.
            let w = s.chars().count() as f64 * fs * 0.55;
            let dx = match ha.as_str() {
                "center" => -w / 2.0,
                "right" => -w,
                _ => 0.0,
            };
            let dy = match va.as_str() {
                "top" => 0.0,
                "center" => -fs / 2.0,
                "bottom" => -fs,
                _ => -fs * 0.8, // baseline
            };
            let style = ("sans-serif", fs.round() as u32)
                .into_font()
                .color(&color(c));
            area.draw(&Text::new(
                s.as_str(),
                (px - bx + dx as i32, py - by + dy as i32),
                style,
            ))?;
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
    {
        let root = SVGBackend::with_string(&mut svg, (w, h)).into_drawing_area();
        // A transparent figure gets no background rect at all, so the SVG (and the
        // PNG rasterised from it) keeps alpha where nothing was drawn.
        if !transparent {
            root.fill(&WHITE).map_err(|e| e.to_string())?;
        }
        let cells = root.split_evenly(grid);
        for p in panels {
            draw_panel(cells.get(p.pos).ok_or("subplot index out of range")?, p)
                .map_err(|e| e.to_string())?;
        }
        root.present().map_err(|e| e.to_string())?;
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
    if panels
        .iter()
        .all(|p| p.series.is_empty() && p.texts.is_empty())
    {
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
