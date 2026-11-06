use numpy::PyReadonlyArray1;
use plotters::prelude::*;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

// Geist (OFL, see assets/fonts/LICENSE_GEIST_OFL.txt)
static FONTS: [(&str, &[u8]); 3] = [
    (
        "sans-serif",
        include_bytes!("../assets/fonts/Geist-Regular.ttf"),
    ),
    (
        "serif",
        include_bytes!("../assets/fonts/GeistSerif-Regular.ttf"),
    ),
    (
        "monospace",
        include_bytes!("../assets/fonts/GeistMono-Regular.ttf"),
    ),
];

fn register_font() {
    static ONCE: std::sync::Once = std::sync::Once::new();
    ONCE.call_once(|| {
        for (name, bytes) in FONTS {
            let _ = plotters::style::register_font(name, FontStyle::Normal, bytes);
        }
    });
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

fn draw<DB: DrawingBackend>(
    root: DrawingArea<DB, plotters::coord::Shift>,
    grid: (usize, usize),
    panels: &[Panel],
) -> Result<(), Box<dyn std::error::Error>>
where
    DB::ErrorType: 'static,
{
    root.fill(&WHITE)?;
    let cells = root.split_evenly(grid);
    for p in panels {
        draw_panel(cells.get(p.pos).ok_or("subplot index out of range")?, p)?;
    }
    root.present()?;
    Ok(())
}

/// Render series and write to `path`: SVG if it ends in ".svg", else PNG (all in Rust).
#[pyfunction]
fn save(path: &str, size: (u32, u32), grid: (usize, usize), panels: Vec<Panel>) -> PyResult<()> {
    let err = |e: &dyn std::fmt::Display| PyRuntimeError::new_err(e.to_string());
    register_font();
    let (w, h) = size;
    if panels.iter().all(|p| p.series.is_empty()) {
        return Err(PyRuntimeError::new_err("nothing to plot"));
    }
    let out: Vec<u8> = if path.to_lowercase().ends_with(".svg") {
        let mut svg = String::new();
        draw(
            SVGBackend::with_string(&mut svg, (w, h)).into_drawing_area(),
            grid,
            &panels,
        )
        .map_err(|e| err(&e))?;
        svg.into_bytes()
    } else {
        let mut buf = vec![255u8; (w * h * 3) as usize];
        draw(
            BitMapBackend::with_buffer(&mut buf, (w, h)).into_drawing_area(),
            grid,
            &panels,
        )
        .map_err(|e| err(&e))?;
        let mut out = Vec::new();
        let mut enc = png::Encoder::new(&mut out, w, h);
        enc.set_color(png::ColorType::Rgb);
        enc.set_depth(png::BitDepth::Eight);
        enc.write_header()
            .and_then(|mut wr| wr.write_image_data(&buf))
            .map_err(|e| err(&e))?;
        out
    };
    std::fs::write(path, out).map_err(|e| err(&e))
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(save, m)?)
}
