//! Python bindings. Compiled only with the `python` feature.

use numpy::{PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArrayDyn};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::{Borrowed, FromPyObject};

use crate::cmap_data;
use crate::export::render_pdf_pages;
use crate::model::{
    DrawStyle, LineStyle, Marker, OwnedArray1, OwnedArray2, OwnedArrayD, Panel, QuiverUnits,
    RenderOptions,
};
use crate::render::render_figure;

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
    py.detach(move || render_figure(size, grid, panels, options))
        .map_err(|err| {
            if err.is_value_error() {
                PyValueError::new_err(err.into_message())
            } else {
                PyRuntimeError::new_err(err.into_message())
            }
        })
}

/// Colormap tables as `{name: bytes}` (packed RGB triples).
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

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(colormaps, m)?)?;
    m.add_function(wrap_pyfunction!(render_figure_py, m)?)?;
    m.add_function(wrap_pyfunction!(render_pdf_pages_py, m)?)
}
