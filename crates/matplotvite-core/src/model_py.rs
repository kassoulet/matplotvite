//! PyO3 extraction traits for the core model types.
//!
//! These implementations must live in the defining crate because both
//! `FromPyObject` and the model types are foreign to the extension crate.

use numpy::{PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArrayDyn};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::{Borrowed, FromPyObject};

use crate::color::{Cmap, Color};
use crate::model::{
    DrawStyle, LineStyle, Marker, OwnedArray1, OwnedArray2, OwnedArrayD, QuiverUnits,
};

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
