//! The Python colormap class. Sampling, reversal and LUT resampling live here
//! so the Python layer only resolves names and custom registrations.

#[cfg(feature = "python")]
mod py {
    use std::collections::HashMap;
    use std::sync::{Mutex, OnceLock};

    use numpy::ndarray::{Array2, ArrayD, IxDyn};
    use numpy::{PyArray2, PyArrayDyn, PyReadonlyArrayDyn, PyUntypedArrayMethods};
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;
    use pyo3::IntoPyObjectExt;

    use matplotvite_core::cmap_data;

    fn custom() -> &'static Mutex<HashMap<String, Vec<[u8; 3]>>> {
        static CUSTOM: OnceLock<Mutex<HashMap<String, Vec<[u8; 3]>>>> = OnceLock::new();
        CUSTOM.get_or_init(|| Mutex::new(HashMap::new()))
    }

    /// Register a colormap built in Python (a `ListedColormap` table).
    pub(crate) fn register(name: &str, rgb: &[u8]) -> PyResult<()> {
        if !rgb.len().is_multiple_of(3) {
            return Err(PyValueError::new_err("a colormap table needs RGB triples"));
        }
        let colors = rgb
            .as_chunks::<3>()
            .0
            .iter()
            .map(|pixel| [pixel[0], pixel[1], pixel[2]])
            .collect();
        custom()
            .lock()
            .map_err(|_| PyValueError::new_err("colormap registry is poisoned"))?
            .insert(name.to_string(), colors);
        Ok(())
    }

    pub(crate) fn has_custom(name: &str) -> bool {
        custom()
            .lock()
            .map(|registry| registry.contains_key(name))
            .unwrap_or(false)
    }

    fn custom_table(name: &str) -> Option<Vec<[u8; 3]>> {
        custom().lock().ok()?.get(name).cloned()
    }

    /// A named colormap that samples values to RGB(A) tuples.
    #[pyclass(module = "matplotvite._core")]
    #[derive(Clone)]
    pub(crate) struct Colormap {
        name: String,
        base: String,
        reversed: bool,
        rgb: Vec<[f64; 3]>,
        alpha: Option<f64>,
        bad: Option<String>,
        under: Option<String>,
        over: Option<String>,
    }

    impl Colormap {
        fn table(name: &str) -> PyResult<Self> {
            let (base, reversed) = match name.strip_suffix("_r") {
                Some(base) => (base, true),
                None => (name, false),
            };
            let (base_name, table) = match custom_table(base) {
                Some(colors) => (base.to_string(), colors),
                None => {
                    let def = cmap_data::lookup(base).ok_or_else(|| {
                        PyValueError::new_err(format!("unsupported colormap: {name:?}"))
                    })?;
                    (def.name.to_string(), def.colors.clone())
                }
            };
            let rgb = table
                .iter()
                .map(|c| {
                    [
                        c[0] as f64 / 255.0,
                        c[1] as f64 / 255.0,
                        c[2] as f64 / 255.0,
                    ]
                })
                .collect();
            Ok(Self {
                name: format!("{}{}", base_name, if reversed { "_r" } else { "" }),
                base: base_name,
                reversed,
                rgb,
                alpha: None,
                bad: None,
                under: None,
                over: None,
            })
        }

        fn sample(&self, value: f64) -> [f64; 3] {
            if !value.is_finite() || self.rgb.is_empty() {
                return [0.0; 3];
            }
            let n = self.rgb.len();
            let mut index = (value.clamp(0.0, 1.0) * n as f64) as usize;
            if index >= n {
                index = n - 1;
            }
            if self.reversed {
                index = n - 1 - index;
            }
            self.rgb[index]
        }

        fn alpha_at(&self, input: f64, alpha: Option<f64>) -> f64 {
            if input.is_finite() {
                alpha.unwrap_or(1.0) * self.alpha.unwrap_or(1.0)
            } else {
                0.0
            }
        }
    }

    #[pymethods]
    impl Colormap {
        #[new]
        fn new(name: &str) -> PyResult<Self> {
            Self::table(name)
        }

        #[getter]
        fn name(&self) -> &str {
            &self.name
        }

        #[getter]
        #[allow(non_snake_case)]
        fn N(&self) -> usize {
            self.rgb.len()
        }

        #[getter]
        fn colors(&self) -> Vec<(f64, f64, f64)> {
            self.rgb.iter().map(|c| (c[0], c[1], c[2])).collect()
        }

        #[getter]
        fn _rgb<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyArray2<f64>>> {
            let flat: Vec<f64> = self.rgb.iter().flatten().copied().collect();
            let array = Array2::from_shape_vec((self.rgb.len(), 3), flat)
                .map_err(|err| PyValueError::new_err(err.to_string()))?;
            Ok(PyArray2::from_owned_array(py, array))
        }

        #[getter]
        fn _reverse(&self) -> bool {
            self.reversed
        }

        #[getter]
        fn _bad(&self) -> Option<&str> {
            self.bad.as_deref()
        }

        #[getter]
        fn _under(&self) -> Option<&str> {
            self.under.as_deref()
        }

        #[getter]
        fn _over(&self) -> Option<&str> {
            self.over.as_deref()
        }

        #[getter]
        fn _alpha(&self) -> Option<f64> {
            self.alpha
        }

        #[setter]
        #[allow(non_snake_case)]
        fn set__alpha(&mut self, value: Option<f64>) {
            self.alpha = value;
        }

        #[pyo3(signature = (value, alpha=None, bytes=false))]
        fn __call__<'py>(
            &self,
            py: Python<'py>,
            value: &Bound<'py, PyAny>,
            alpha: Option<&Bound<'py, PyAny>>,
            bytes: bool,
        ) -> PyResult<Py<PyAny>> {
            let alpha_scalar = alpha.and_then(|a| a.extract::<f64>().ok());
            if let Ok(scalar) = value.extract::<f64>() {
                let [r, g, b] = self.sample(scalar);
                let a = self.alpha_at(scalar, alpha_scalar);
                if bytes {
                    return (to_byte(r), to_byte(g), to_byte(b), to_byte(a)).into_py_any(py);
                }
                return (r, g, b, a).into_py_any(py);
            }

            let numpy = py.import("numpy")?;
            let converted = numpy.getattr("asarray")?.call1((value,))?;
            let values: PyReadonlyArrayDyn<'py, f64> = converted.extract()?;
            let shape = values.shape().to_vec();
            let view = values.as_array();
            let alpha_array: Option<PyReadonlyArrayDyn<'py, f64>> = match alpha {
                Some(a) if alpha_scalar.is_none() => Some(a.extract()?),
                _ => None,
            };
            let broadcast = alpha_array
                .as_ref()
                .and_then(|a| a.as_array().broadcast(IxDyn(&shape)).map(|b| b.to_owned()));

            let mut flat = Vec::with_capacity(view.len() * 4);
            match &broadcast {
                Some(alpha_values) => {
                    for (&v, &a) in view.iter().zip(alpha_values.iter()) {
                        let [r, g, b] = self.sample(v);
                        flat.extend_from_slice(&[r, g, b, self.alpha_at(v, Some(a))]);
                    }
                }
                None => {
                    for &v in view.iter() {
                        let [r, g, b] = self.sample(v);
                        flat.extend_from_slice(&[r, g, b, self.alpha_at(v, alpha_scalar)]);
                    }
                }
            }

            let mut out_shape = shape;
            out_shape.push(4);
            if bytes {
                let out: Vec<u8> = flat.iter().map(|v| to_byte(*v)).collect();
                let array = ArrayD::from_shape_vec(IxDyn(&out_shape), out)
                    .map_err(|err| PyValueError::new_err(err.to_string()))?;
                return Ok(PyArrayDyn::from_owned_array(py, array).into_any().unbind());
            }
            let array = ArrayD::from_shape_vec(IxDyn(&out_shape), flat)
                .map_err(|err| PyValueError::new_err(err.to_string()))?;
            Ok(PyArrayDyn::from_owned_array(py, array).into_any().unbind())
        }

        #[pyo3(signature = (name=None))]
        fn reversed(&self, name: Option<&str>) -> PyResult<Self> {
            if let Some(name) = name {
                return Self::table(name);
            }
            let mut copy = self.clone();
            copy.reversed = !self.reversed;
            copy.name = if self.reversed {
                self.base.to_string()
            } else {
                format!("{}_r", self.base)
            };
            Ok(copy)
        }

        #[pyo3(signature = (lut))]
        fn resampled(&self, lut: usize) -> Self {
            let count = lut.max(1);
            let n = self.rgb.len();
            let mut rgb = Vec::with_capacity(count);
            for index in 0..count {
                let t = if count > 1 {
                    index as f64 / (count - 1) as f64
                } else {
                    0.0
                };
                let mut source = (t * n.saturating_sub(1) as f64).round() as usize;
                if self.reversed && n > 0 {
                    source = n - 1 - source.min(n - 1);
                }
                rgb.push(self.rgb.get(source).copied().unwrap_or([0.0; 3]));
            }
            let mut copy = self.clone();
            copy.rgb = rgb;
            copy
        }

        #[pyo3(signature = (bad=None, under=None, over=None))]
        fn with_extremes(
            &self,
            bad: Option<&str>,
            under: Option<&str>,
            over: Option<&str>,
        ) -> Self {
            let mut copy = self.clone();
            if let Some(color) = bad {
                copy.bad = Some(color.to_string());
            }
            if let Some(color) = under {
                copy.under = Some(color.to_string());
            }
            if let Some(color) = over {
                copy.over = Some(color.to_string());
            }
            copy
        }

        #[pyo3(signature = (alpha))]
        fn with_alpha(&self, alpha: Option<f64>) -> Self {
            let mut copy = self.clone();
            copy.alpha = alpha.map(|a| a.clamp(0.0, 1.0));
            copy
        }

        fn copy(&self) -> Self {
            self.clone()
        }

        #[pyo3(signature = (color="k", alpha=None))]
        fn set_bad(&mut self, color: &str, alpha: Option<f64>) {
            let _ = alpha;
            self.bad = Some(color.to_string());
        }

        #[pyo3(signature = (color="k", alpha=None))]
        fn set_under(&mut self, color: &str, alpha: Option<f64>) {
            let _ = alpha;
            self.under = Some(color.to_string());
        }

        #[pyo3(signature = (color="k", alpha=None))]
        fn set_over(&mut self, color: &str, alpha: Option<f64>) {
            let _ = alpha;
            self.over = Some(color.to_string());
        }

        fn __repr__(&self) -> String {
            format!("<Colormap {:?}>", self.name)
        }
    }

    fn to_byte(value: f64) -> u8 {
        (value * 255.0).round().clamp(0.0, 255.0) as u8
    }
}

#[cfg(feature = "python")]
pub(crate) use py::{has_custom, register, Colormap};
