//! Normalisation curves behind the Python colour norms.
//!
//! The Python classes are thin wrappers around these Rust implementations, so
//! the mapping used by images and scatters has a single implementation.

/// Matplotlib's logarithmic mapping, clamped at the lower end.
pub(crate) fn log_norm(value: f64, lo: f64, hi: f64, base: f64) -> f64 {
    let base = if base > 0.0 && base != 1.0 {
        base
    } else {
        10.0
    };
    let log = |v: f64| v.max(1e-300).ln() / base.ln();
    let span = log(hi) - log(lo);
    (log(value) - log(lo)) / if span == 0.0 { 1.0 } else { span }
}

/// Matplotlib's `Normalize`: a plain linear mapping.
pub(crate) fn linear_norm(value: f64, lo: f64, hi: f64) -> f64 {
    let span = if hi != lo { hi - lo } else { 1.0 };
    (value - lo) / span
}

/// Matplotlib's `TwoSlopeNorm`: two linear spans meeting at `center`.
pub(crate) fn two_slope(value: f64, center: f64, lo: f64, hi: f64) -> f64 {
    if value <= center {
        0.5 * (value - lo) / (center - lo)
    } else {
        0.5 + 0.5 * (value - center) / (hi - center)
    }
}

/// Matplotlib's `PowerNorm`: a clipped linear ramp raised to `gamma`.
pub(crate) fn power_norm(value: f64, gamma: f64, lo: f64, hi: f64) -> f64 {
    let span = if hi != lo { hi - lo } else { 1.0 };
    ((value - lo) / span).clamp(0.0, 1.0).powf(gamma)
}

/// Matplotlib's `SymLogNorm` transform (`log1p` inside and outside the threshold).
pub(crate) fn symlog_norm(value: f64, linthresh: f64, lo: f64, hi: f64) -> f64 {
    let l = linthresh.max(1e-300);
    let transform = |v: f64| v.signum() * (1.0 + v.abs() / l).ln();
    let span = transform(hi) - transform(lo);
    (transform(value) - transform(lo)) / if span == 0.0 { 1.0 } else { span }
}

/// Matplotlib's `AsinhNorm` transform.
pub(crate) fn asinh_norm(value: f64, width: f64, lo: f64, hi: f64) -> f64 {
    let w = if width > 0.0 { width } else { 1.0 };
    let low = (lo / w).asinh();
    let high = (hi / w).asinh();
    ((value / w).asinh() - low) / if high > low { high - low } else { 1.0 }
}

/// `np.digitize(value, boundaries) - 1`, clamped to the palette.
pub(crate) fn boundary_norm(value: f64, boundaries: &[f64], ncolors: usize) -> i64 {
    let index = boundaries.partition_point(|boundary| *boundary <= value) as i64 - 1;
    let last = ncolors.saturating_sub(1) as i64;
    index.clamp(0, last.max(0))
}

#[cfg(feature = "python")]
mod py {
    use numpy::ndarray::{ArrayD, IxDyn};
    use numpy::{PyArray1, PyArrayDyn, PyReadonlyArray1, PyReadonlyArrayDyn};
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;
    use pyo3::IntoPyObjectExt;

    use super::{
        asinh_norm, boundary_norm, linear_norm, log_norm, power_norm, symlog_norm, two_slope,
    };

    /// Convert any array-like input through `numpy.asarray`.
    fn as_array<'py>(
        py: Python<'py>,
        value: &Bound<'py, PyAny>,
    ) -> PyResult<PyReadonlyArrayDyn<'py, f64>> {
        let numpy = py.import("numpy")?;
        let array = numpy.getattr("asarray")?.call1((value,))?;
        array.extract()
    }

    /// Apply a scalar function elementwise, preserving Python's scalar shape.
    fn map_f64<'py, F>(py: Python<'py>, value: &Bound<'py, PyAny>, f: F) -> PyResult<Py<PyAny>>
    where
        F: Fn(f64) -> f64,
    {
        if let Ok(scalar) = value.extract::<f64>() {
            return f(scalar).into_py_any(py);
        }
        let array = as_array(py, value)?;
        let out = array.as_array().mapv(f);
        Ok(PyArrayDyn::from_owned_array(py, out).into_any().unbind())
    }

    fn map_i64<'py, F>(py: Python<'py>, value: &Bound<'py, PyAny>, f: F) -> PyResult<Py<PyAny>>
    where
        F: Fn(f64) -> i64,
    {
        if let Ok(scalar) = value.extract::<f64>() {
            return f(scalar).into_py_any(py);
        }
        let array = as_array(py, value)?;
        let out: ArrayD<i64> = array.as_array().mapv(f);
        Ok(PyArrayDyn::from_owned_array(py, out).into_any().unbind())
    }

    fn bounds(vmin: Option<f64>, vmax: Option<f64>, defaults: (f64, f64)) -> (f64, f64) {
        (vmin.unwrap_or(defaults.0), vmax.unwrap_or(defaults.1))
    }

    fn clipped(value: f64, clip: bool) -> f64 {
        if clip {
            value.clamp(0.0, 1.0)
        } else {
            value
        }
    }

    #[pyclass(module = "matplotvite._core")]
    #[derive(Default)]
    pub(crate) struct Normalize {
        #[pyo3(get, set)]
        vmin: Option<f64>,
        #[pyo3(get, set)]
        vmax: Option<f64>,
        #[pyo3(get, set)]
        clip: bool,
    }

    #[pymethods]
    impl Normalize {
        #[new]
        #[pyo3(signature = (vmin=None, vmax=None, clip=false))]
        fn new(vmin: Option<f64>, vmax: Option<f64>, clip: bool) -> Self {
            Self { vmin, vmax, clip }
        }

        #[pyo3(signature = (value, clip=None))]
        fn __call__<'py>(
            &self,
            py: Python<'py>,
            value: &Bound<'py, PyAny>,
            clip: Option<bool>,
        ) -> PyResult<Py<PyAny>> {
            let (lo, hi) = bounds(self.vmin, self.vmax, (0.0, 1.0));
            let clip = clip.unwrap_or(self.clip);
            map_f64(py, value, move |v| clipped(linear_norm(v, lo, hi), clip))
        }

        fn autoscale(&self, _values: &Bound<'_, PyAny>) {}

        #[pyo3(name = "autoscale_None")]
        fn autoscale_none(&self, _values: &Bound<'_, PyAny>) {}

        #[pyo3(signature = (value))]
        fn inverse<'py>(&self, py: Python<'py>, value: &Bound<'py, PyAny>) -> PyResult<Py<PyAny>> {
            let (lo, hi) = bounds(self.vmin, self.vmax, (0.0, 1.0));
            map_f64(py, value, move |v| v * (hi - lo) + lo)
        }
    }

    #[pyclass(module = "matplotvite._core")]
    pub(crate) struct LogNorm {
        #[pyo3(get, set)]
        vmin: Option<f64>,
        #[pyo3(get, set)]
        vmax: Option<f64>,
        #[pyo3(get, set)]
        clip: bool,
        #[pyo3(get, set)]
        base: f64,
    }

    #[pymethods]
    impl LogNorm {
        #[new]
        #[pyo3(signature = (vmin=None, vmax=None, clip=false, base=10.0))]
        fn new(vmin: Option<f64>, vmax: Option<f64>, clip: bool, base: f64) -> Self {
            Self {
                vmin,
                vmax,
                clip,
                base,
            }
        }

        #[pyo3(signature = (value, clip=None))]
        fn __call__<'py>(
            &self,
            py: Python<'py>,
            value: &Bound<'py, PyAny>,
            clip: Option<bool>,
        ) -> PyResult<Py<PyAny>> {
            let (lo, hi) = bounds(self.vmin, self.vmax, (1e-300, 1.0));
            let clip = clip.unwrap_or(self.clip);
            let base = self.base;
            map_f64(py, value, move |v| clipped(log_norm(v, lo, hi, base), clip))
        }

        #[pyo3(signature = (value))]
        fn inverse<'py>(&self, py: Python<'py>, value: &Bound<'py, PyAny>) -> PyResult<Py<PyAny>> {
            let (lo, hi) = bounds(self.vmin, self.vmax, (1e-300, 1.0));
            let (log_lo, log_hi) = (lo.ln(), hi.ln());
            map_f64(py, value, move |v| (log_lo + v * (log_hi - log_lo)).exp())
        }
    }

    #[pyclass(module = "matplotvite._core")]
    pub(crate) struct PowerNorm {
        #[pyo3(get, set)]
        vmin: Option<f64>,
        #[pyo3(get, set)]
        vmax: Option<f64>,
        #[pyo3(get, set)]
        clip: bool,
        #[pyo3(get, set)]
        gamma: f64,
    }

    #[pymethods]
    impl PowerNorm {
        #[new]
        #[pyo3(signature = (gamma, vmin=None, vmax=None, clip=false))]
        fn new(gamma: f64, vmin: Option<f64>, vmax: Option<f64>, clip: bool) -> Self {
            Self {
                vmin,
                vmax,
                clip,
                gamma,
            }
        }

        #[pyo3(signature = (value, clip=None))]
        fn __call__<'py>(
            &self,
            py: Python<'py>,
            value: &Bound<'py, PyAny>,
            clip: Option<bool>,
        ) -> PyResult<Py<PyAny>> {
            let _ = clip;
            let (lo, hi) = bounds(self.vmin, self.vmax, (0.0, 1.0));
            let gamma = self.gamma;
            map_f64(py, value, move |v| power_norm(v, gamma, lo, hi))
        }
    }

    #[pyclass(module = "matplotvite._core")]
    pub(crate) struct SymLogNorm {
        #[pyo3(get, set)]
        vmin: Option<f64>,
        #[pyo3(get, set)]
        vmax: Option<f64>,
        #[pyo3(get, set)]
        clip: bool,
        #[pyo3(get, set)]
        linthresh: f64,
        #[pyo3(get, set)]
        linscale: f64,
        #[pyo3(get, set)]
        base: f64,
    }

    #[pymethods]
    impl SymLogNorm {
        #[new]
        #[pyo3(signature = (linthresh, linscale=1.0, vmin=None, vmax=None, clip=false, *, base=10.0))]
        fn new(
            linthresh: f64,
            linscale: f64,
            vmin: Option<f64>,
            vmax: Option<f64>,
            clip: bool,
            base: f64,
        ) -> Self {
            Self {
                vmin,
                vmax,
                clip,
                linthresh: linthresh.max(1e-300),
                linscale,
                base,
            }
        }

        #[pyo3(signature = (value, clip=None))]
        fn __call__<'py>(
            &self,
            py: Python<'py>,
            value: &Bound<'py, PyAny>,
            clip: Option<bool>,
        ) -> PyResult<Py<PyAny>> {
            let (lo, hi) = bounds(self.vmin, self.vmax, (-1.0, 1.0));
            let clip = clip.unwrap_or(self.clip);
            let linthresh = self.linthresh;
            map_f64(py, value, move |v| {
                clipped(symlog_norm(v, linthresh, lo, hi), clip)
            })
        }
    }

    #[pyclass(module = "matplotvite._core")]
    pub(crate) struct AsinhNorm {
        #[pyo3(get, set)]
        vmin: Option<f64>,
        #[pyo3(get, set)]
        vmax: Option<f64>,
        #[pyo3(get, set)]
        clip: bool,
        #[pyo3(get, set)]
        linear_width: f64,
    }

    #[pymethods]
    impl AsinhNorm {
        #[new]
        #[pyo3(signature = (linear_width=1.0, vmin=None, vmax=None, clip=false))]
        fn new(linear_width: f64, vmin: Option<f64>, vmax: Option<f64>, clip: bool) -> Self {
            Self {
                vmin,
                vmax,
                clip,
                linear_width,
            }
        }

        #[pyo3(signature = (value, clip=None))]
        fn __call__<'py>(
            &self,
            py: Python<'py>,
            value: &Bound<'py, PyAny>,
            clip: Option<bool>,
        ) -> PyResult<Py<PyAny>> {
            let clip = clip.unwrap_or(self.clip);
            let width = self.linear_width;
            let vmin = self.vmin;
            let vmax = self.vmax;
            if let Ok(scalar) = value.extract::<f64>() {
                let default = if scalar.is_finite() { scalar } else { 0.0 };
                let (lo, hi) = bounds(vmin, vmax, (default, default));
                return clipped(asinh_norm(scalar, width, lo, hi), clip).into_py_any(py);
            }
            let array = as_array(py, value)?;
            let view = array.as_array();
            let mut min = f64::INFINITY;
            let mut max = f64::NEG_INFINITY;
            for &v in view.iter().filter(|v| v.is_finite()) {
                min = min.min(v);
                max = max.max(v);
            }
            if !min.is_finite() || !max.is_finite() {
                (min, max) = (0.0, 1.0);
            }
            let (lo, hi) = bounds(vmin, vmax, (min, max));
            let out = view.mapv(|v| clipped(asinh_norm(v, width, lo, hi), clip));
            let out = ArrayD::from_shape_vec(IxDyn(out.shape()), out.iter().copied().collect())
                .map_err(|err| PyValueError::new_err(err.to_string()))?;
            Ok(PyArrayDyn::from_owned_array(py, out).into_any().unbind())
        }
    }

    #[pyclass(module = "matplotvite._core")]
    pub(crate) struct TwoSlopeNorm {
        #[pyo3(get, set)]
        vmin: Option<f64>,
        #[pyo3(get, set)]
        vmax: Option<f64>,
        #[pyo3(get, set)]
        clip: bool,
        #[pyo3(get, set)]
        vcenter: f64,
    }

    #[pymethods]
    impl TwoSlopeNorm {
        #[new]
        #[pyo3(signature = (vcenter, vmin=None, vmax=None, clip=false))]
        fn new(vcenter: f64, vmin: Option<f64>, vmax: Option<f64>, clip: bool) -> Self {
            Self {
                vmin,
                vmax,
                clip,
                vcenter,
            }
        }

        #[pyo3(signature = (value, clip=None))]
        fn __call__<'py>(
            &self,
            py: Python<'py>,
            value: &Bound<'py, PyAny>,
            clip: Option<bool>,
        ) -> PyResult<Py<PyAny>> {
            let (lo, hi) = bounds(self.vmin, self.vmax, (0.0, 1.0));
            let center = self.vcenter;
            let clip = clip.unwrap_or(self.clip);
            map_f64(py, value, move |v| {
                clipped(two_slope(v, center, lo, hi), clip)
            })
        }
    }

    #[pyclass(module = "matplotvite._core")]
    pub(crate) struct BoundaryNorm {
        boundaries: Vec<f64>,
        ncolors: usize,
        #[pyo3(get, set)]
        vmin: Option<f64>,
        #[pyo3(get, set)]
        vmax: Option<f64>,
        #[pyo3(get, set)]
        clip: bool,
        #[pyo3(get, set)]
        extend: Option<String>,
    }

    #[pymethods]
    impl BoundaryNorm {
        #[new]
        #[pyo3(signature = (boundaries, ncolors, clip=false, extend=None))]
        fn new(
            boundaries: &Bound<'_, PyAny>,
            ncolors: usize,
            clip: bool,
            extend: Option<String>,
        ) -> PyResult<Self> {
            let values = if let Ok(values) = boundaries.extract::<Vec<f64>>() {
                values
            } else {
                let array: PyReadonlyArray1<f64> = boundaries.extract()?;
                array.as_array().to_vec()
            };
            Ok(Self {
                boundaries: values,
                ncolors,
                vmin: None,
                vmax: None,
                clip,
                extend,
            })
        }

        #[getter]
        fn boundaries<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray1<f64>> {
            PyArray1::from_vec(py, self.boundaries.clone())
        }

        #[getter]
        fn ncolors(&self) -> usize {
            self.ncolors
        }

        #[pyo3(signature = (value, clip=None))]
        fn __call__<'py>(
            &self,
            py: Python<'py>,
            value: &Bound<'py, PyAny>,
            clip: Option<bool>,
        ) -> PyResult<Py<PyAny>> {
            let _ = clip;
            let boundaries = self.boundaries.clone();
            let ncolors = self.ncolors;
            map_i64(py, value, move |v| boundary_norm(v, &boundaries, ncolors))
        }
    }
}

#[cfg(feature = "python")]
pub(crate) use py::{
    AsinhNorm, BoundaryNorm, LogNorm, Normalize, PowerNorm, SymLogNorm, TwoSlopeNorm,
};

#[cfg(test)]
mod tests {
    use super::{
        asinh_norm, boundary_norm, linear_norm, log_norm, power_norm, symlog_norm, two_slope,
    };

    #[test]
    fn linear_norm_maps_the_bounds() {
        assert!((linear_norm(1.0, 0.0, 2.0) - 0.5).abs() < 1e-12);
        assert!((linear_norm(0.0, 0.0, 2.0)).abs() < 1e-12);
        assert!((linear_norm(2.0, 0.0, 2.0) - 1.0).abs() < 1e-12);
    }

    #[test]
    fn log_norm_matches_hand_values() {
        assert!((log_norm(10.0, 1.0, 1000.0, 10.0) - 1.0 / 3.0).abs() < 1e-12);
        assert!((log_norm(1000.0, 1.0, 1000.0, 10.0) - 1.0).abs() < 1e-12);
    }

    #[test]
    fn two_slope_meets_at_the_centre() {
        assert!((two_slope(0.0, 0.0, -2.0, 2.0) - 0.5).abs() < 1e-12);
        assert!((two_slope(-2.0, 0.0, -2.0, 2.0)).abs() < 1e-12);
        assert!((two_slope(2.0, 0.0, -2.0, 2.0) - 1.0).abs() < 1e-12);
    }

    #[test]
    fn power_symlog_and_asinh_cover_their_ramps() {
        assert!((power_norm(1.0, 2.0, 0.0, 2.0) - 0.25).abs() < 1e-12);
        assert!((symlog_norm(0.0, 1.0, -100.0, 100.0) - 0.5).abs() < 1e-12);
        assert!((asinh_norm(0.0, 1.0, -1.0, 1.0) - 0.5).abs() < 1e-12);
    }

    #[test]
    fn boundary_norm_is_left_inclusive_and_clamped() {
        let boundaries = [0.0, 1.0, 2.0, 3.0];
        assert_eq!(boundary_norm(0.5, &boundaries, 4), 0);
        assert_eq!(boundary_norm(1.5, &boundaries, 4), 1);
        assert_eq!(boundary_norm(2.5, &boundaries, 4), 2);
        assert_eq!(boundary_norm(-5.0, &boundaries, 4), 0);
        assert_eq!(boundary_norm(50.0, &boundaries, 4), 3);
    }
}
