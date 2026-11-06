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
fn render_svg(size: (u32, u32), grid: (usize, usize), panels: &[Panel]) -> Result<String, String> {
    let (w, h) = size;
    let mut svg = String::new();
    {
        let root = SVGBackend::with_string(&mut svg, (w, h)).into_drawing_area();
        root.fill(&WHITE).map_err(|e| e.to_string())?;
        let cells = root.split_evenly(grid);
        for p in panels {
            draw_panel(cells.get(p.pos).ok_or("subplot index out of range")?, p)
                .map_err(|e| e.to_string())?;
        }
        root.present().map_err(|e| e.to_string())?;
    }
    Ok(svg)
}

/// Rasterise an SVG string to PNG bytes via resvg + tiny-skia.
/// Fonts embedded in `build_fontdb()` are used — no system fonts needed.
fn svg_to_png(svg: &str, w: u32, h: u32) -> Result<Vec<u8>, String> {
    let fontdb = std::sync::Arc::new(build_fontdb());
    let opts = usvg::Options {
        fontdb: fontdb.clone(),
        ..Default::default()
    };
    let tree = usvg::Tree::from_str(svg, &opts).map_err(|e| e.to_string())?;
    let mut pixmap = tiny_skia::Pixmap::new(w, h).ok_or("failed to allocate pixmap")?;
    pixmap.fill(tiny_skia::Color::WHITE);
    resvg::render(
        &tree,
        tiny_skia::Transform::identity(),
        &mut pixmap.as_mut(),
    );
    pixmap.encode_png().map_err(|e| e.to_string())
}

/// Render series and write to `path`: SVG if it ends in ".svg", else anti-aliased PNG.
#[pyfunction]
fn save(path: &str, size: (u32, u32), grid: (usize, usize), panels: Vec<Panel>) -> PyResult<()> {
    let err = |e: &str| PyRuntimeError::new_err(e.to_string());
    register_plotters_fonts();
    if panels.iter().all(|p| p.series.is_empty()) {
        return Err(PyRuntimeError::new_err("nothing to plot"));
    }
    let (w, h) = size;
    let svg = render_svg(size, grid, &panels).map_err(|e| err(&e))?;
    let bytes: Vec<u8> = if path.to_lowercase().ends_with(".svg") {
        svg.into_bytes()
    } else {
        svg_to_png(&svg, w, h).map_err(|e| err(&e))?
    };
    std::fs::write(path, bytes).map_err(|e| err(&e.to_string()))
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(save, m)?)
}
