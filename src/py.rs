//! Python bindings. Compiled only with the `python` feature.

use numpy::{PyArray1, PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArrayDyn};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::{Borrowed, FromPyObject};

use crate::cmap_data;
use crate::cmap_py;
use crate::cmap_py::Colormap;
use crate::color::{Cmap, Color};
use crate::export::render_pdf_pages;
use crate::layout;
use crate::model::{
    DrawStyle, LineStyle, Marker, OwnedArray1, OwnedArray2, OwnedArrayD, Panel, QuiverUnits,
    RenderOptions,
};
use crate::render::render_figure;
use crate::scale as scales;

impl<'a, 'py> FromPyObject<'a, 'py> for OwnedArray1 {
    type Error = PyErr;

    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        let array: PyReadonlyArray1<'py, f64> = obj.extract()?;
        Ok(OwnedArray1::from_array(array.as_array().to_owned()))
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for OwnedArray2 {
    type Error = PyErr;

    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        let array: PyReadonlyArray2<'py, f64> = obj.extract()?;
        Ok(OwnedArray2::from_array(array.as_array().to_owned()))
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for OwnedArrayD {
    type Error = PyErr;

    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        let array: PyReadonlyArrayDyn<'py, f64> = obj.extract()?;
        Ok(OwnedArrayD::from_array(array.as_array().to_owned()))
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for LineStyle {
    type Error = PyErr;

    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        let value: String = obj.extract()?;
        // Custom dash tuples become their string repr in Python and have always
        // rendered solid; keep that fallback while typing the common styles.
        Ok(LineStyle::parse(&value).unwrap_or(LineStyle::Solid))
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for Marker {
    type Error = PyErr;

    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        let value: Option<String> = obj.extract()?;
        // Unknown markers have always rendered as circles; keep that fallback
        // while validating the supported symbols at the boundary.
        Ok(value
            .as_deref()
            .and_then(Marker::parse)
            .unwrap_or(Marker::Circle))
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for Color {
    type Error = PyErr;

    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        let value: String = obj.extract()?;
        Ok(Color::parse(&value))
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for Cmap {
    type Error = PyErr;

    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        let value: String = obj.extract()?;
        Ok(Cmap::parse(&value))
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for QuiverUnits {
    type Error = PyErr;

    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        let value: String = obj.extract()?;
        QuiverUnits::parse(&value).ok_or_else(|| {
            PyValueError::new_err(format!(
                "unsupported quiver units: {value:?} (use 'width', 'height', 'dots', 'inches', 'x', 'y', or 'xy')"
            ))
        })
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for DrawStyle {
    type Error = PyErr;

    fn extract(obj: Borrowed<'a, 'py, PyAny>) -> Result<Self, Self::Error> {
        let value: String = obj.extract()?;
        DrawStyle::parse(&value).ok_or_else(|| {
            PyValueError::new_err(format!(
                "unsupported drawstyle: {value:?} (use 'default', 'steps-pre', 'steps-mid', or 'steps-post')"
            ))
        })
    }
}

/// Render a figure and return its encoded bytes. All drawing and validation
/// happen off the GIL; only the Python exception mapping runs with it held.
#[pyfunction]
#[pyo3(name = "render", signature = (size, grid, panels, options))]
fn render_figure_py(
    py: Python<'_>,
    size: (u32, u32),
    grid: (usize, usize),
    panels: Vec<Panel>,
    options: RenderOptions,
) -> PyResult<Vec<u8>> {
    py.detach(move || render_figure(size, grid, &panels, options))
        .map_err(|err| {
            if err.is_value_error() {
                PyValueError::new_err(err.into_message())
            } else {
                PyRuntimeError::new_err(err.into_message())
            }
        })
}

/// Colormap tables as `{name: bytes}` (packed RGB triples).
/// Canonical registry name, including the `_r` reversal suffix.
#[pyfunction]
#[pyo3(name = "cmap_name")]
fn cmap_name_py(name: &str) -> PyResult<String> {
    let text = name.trim();
    let (base, reversed) = match text.strip_suffix("_r") {
        Some(base) => (base, true),
        None => (text, false),
    };
    let canonical = if cmap_py::has_custom(base) {
        base.to_string()
    } else {
        cmap_data::lookup(base)
            .ok_or_else(|| PyValueError::new_err(format!("unsupported colormap: {name:?}")))?
            .name
            .to_string()
    };
    Ok(format!("{}{}", canonical, if reversed { "_r" } else { "" }))
}

/// Add a Python-built colormap table to the native registry.
#[pyfunction]
#[pyo3(name = "register_colormap")]
fn register_colormap_py(name: &str, colors: &[u8]) -> PyResult<()> {
    cmap_py::register(name, colors)
}

#[pyfunction]
fn colormaps<'py>(py: Python<'py>) -> PyResult<Bound<'py, pyo3::types::PyDict>> {
    let d = pyo3::types::PyDict::new(py);
    for c in cmap_data::cmaps() {
        d.set_item(
            c.name,
            pyo3::types::PyBytes::new(py, c.colors.as_flattened()),
        )?;
    }
    Ok(d)
}

#[pyfunction]
#[pyo3(name = "render_pdf_pages")]
fn render_pdf_pages_py(py: Python<'_>, svgs: Vec<Vec<u8>>, dpis: Vec<f64>) -> PyResult<Vec<u8>> {
    py.detach(move || render_pdf_pages(&svgs, &dpis))
        .map_err(PyRuntimeError::new_err)
}

#[pyfunction]
#[pyo3(name = "auto_ticks")]
#[pyo3(signature = (lo, hi, log=false, base=10.0, target=8))]
fn auto_ticks_py(lo: f64, hi: f64, log: bool, base: f64, target: usize) -> Vec<f64> {
    layout::data_ticks(lo, hi, log, base, target)
}

#[pyfunction]
#[pyo3(name = "tick_target")]
fn tick_target_py(pixels: f64, pixels_per_label: f64) -> usize {
    layout::tick_target(pixels, pixels_per_label)
}

#[pyfunction]
#[pyo3(name = "symlog")]
fn symlog_py<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    linthresh: f64,
    base: f64,
    linscale: f64,
) -> Bound<'py, PyArray1<f64>> {
    let out: Vec<f64> = values
        .as_array()
        .iter()
        .map(|&value| scales::symlog(value, linthresh, base, linscale))
        .collect();
    PyArray1::from_vec(py, out)
}

#[pyfunction]
#[pyo3(name = "symlog_inverse")]
fn symlog_inverse_py<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    linthresh: f64,
    base: f64,
    linscale: f64,
) -> Bound<'py, PyArray1<f64>> {
    let out: Vec<f64> = values
        .as_array()
        .iter()
        .map(|&value| scales::symlog_inverse(value, linthresh, base, linscale))
        .collect();
    PyArray1::from_vec(py, out)
}

#[pyfunction]
#[pyo3(name = "logit")]
fn logit_py<'py>(py: Python<'py>, values: PyReadonlyArray1<'py, f64>) -> Bound<'py, PyArray1<f64>> {
    let out: Vec<f64> = values
        .as_array()
        .iter()
        .map(|&value| scales::logit(value))
        .collect();
    PyArray1::from_vec(py, out)
}

#[pyfunction]
#[pyo3(name = "logit_inverse")]
fn logit_inverse_py<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
) -> Bound<'py, PyArray1<f64>> {
    let out: Vec<f64> = values
        .as_array()
        .iter()
        .map(|&value| scales::logit_inverse(value))
        .collect();
    PyArray1::from_vec(py, out)
}

#[pyfunction]
#[pyo3(name = "asinh")]
fn asinh_py<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    linear_width: f64,
) -> Bound<'py, PyArray1<f64>> {
    let out: Vec<f64> = values
        .as_array()
        .iter()
        .map(|&value| scales::asinh_scale(value, linear_width))
        .collect();
    PyArray1::from_vec(py, out)
}

#[pyfunction]
#[pyo3(name = "asinh_inverse")]
fn asinh_inverse_py<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<'py, f64>,
    linear_width: f64,
) -> Bound<'py, PyArray1<f64>> {
    let out: Vec<f64> = values
        .as_array()
        .iter()
        .map(|&value| scales::asinh_inverse(value, linear_width))
        .collect();
    PyArray1::from_vec(py, out)
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(colormaps, m)?)?;
    m.add_function(wrap_pyfunction!(cmap_name_py, m)?)?;
    m.add_function(wrap_pyfunction!(register_colormap_py, m)?)?;
    m.add_function(wrap_pyfunction!(render_figure_py, m)?)?;
    m.add_function(wrap_pyfunction!(render_pdf_pages_py, m)?)?;
    m.add_function(wrap_pyfunction!(auto_ticks_py, m)?)?;
    m.add_function(wrap_pyfunction!(tick_target_py, m)?)?;
    m.add_function(wrap_pyfunction!(symlog_py, m)?)?;
    m.add_function(wrap_pyfunction!(symlog_inverse_py, m)?)?;
    m.add_function(wrap_pyfunction!(logit_py, m)?)?;
    m.add_function(wrap_pyfunction!(logit_inverse_py, m)?)?;
    m.add_function(wrap_pyfunction!(asinh_py, m)?)?;
    m.add_function(wrap_pyfunction!(asinh_inverse_py, m)?)?;
    m.add_class::<Colormap>()?;
    m.add_class::<crate::norms::Normalize>()?;
    m.add_class::<crate::norms::LogNorm>()?;
    m.add_class::<crate::norms::PowerNorm>()?;
    m.add_class::<crate::norms::SymLogNorm>()?;
    m.add_class::<crate::norms::AsinhNorm>()?;
    m.add_class::<crate::norms::TwoSlopeNorm>()?;
    m.add_class::<crate::norms::BoundaryNorm>()
}
