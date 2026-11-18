"""ScaleBase-compatible shims for ``matplotlib.scale``.

The renderer implements the built-in scales directly; these classes give
gallery and test code the Matplotlib objects and transforms it expects, and
``Axes.set_xscale``/``set_yscale`` already accept their names.
"""

import math

import numpy as np

from . import _core

__all__ = (
    "AsinhScale", "FuncScale", "FuncScaleLog", "LinearScale", "LogScale",
    "LogitScale", "ScaleBase", "SymmetricalLogScale", "get_scale_names",
    "register_scale",
)


class _ScaleTransform:
    """A pair of forward/inverse callables with Matplotlib's transform API."""

    def __init__(self, forward, inverse):
        self._forward = forward
        self._inverse = inverse

    def transform(self, values):
        return self._forward(np.asarray(values, dtype=float))

    transform_non_affine = transform

    def inverted(self):
        return _ScaleTransform(self._inverse, self._forward)


def _identity(values):
    return values


class ScaleBase:
    """Base class carrying the axis and default scale behaviour."""

    name = "function"

    def __init__(self, axis, **kwargs):
        self.axis = axis
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_transform(self):
        return _ScaleTransform(_identity, _identity)

    def set_default_locators_and_formatters(self, axis):
        return None

    def limit_range_for_scale(self, vmin, vmax, minpos):
        return vmin, vmax

    def __str__(self):
        return self.name


class LinearScale(ScaleBase):
    name = "linear"


class LogScale(ScaleBase):
    name = "log"

    def __init__(self, axis, **kwargs):
        super().__init__(axis, **kwargs)
        self.base = float(kwargs.get("base", 10.0))

    def get_transform(self):
        base = self.base
        return _ScaleTransform(
            lambda values: np.log(values) / math.log(base),
            lambda values: np.power(base, values),
        )

    def limit_range_for_scale(self, vmin, vmax, minpos):
        return (max(vmin, minpos), vmax) if minpos > 0 else (vmin, vmax)


class SymmetricalLogScale(ScaleBase):
    name = "symlog"

    def __init__(self, axis, **kwargs):
        super().__init__(axis, **kwargs)
        self.base = float(kwargs.get("base", 10.0))
        self.linthresh = float(kwargs.get("linthresh", 2.0))
        self.linscale = float(kwargs.get("linscale", 1.0))

    def get_transform(self):
        base, linthresh, linscale = self.base, self.linthresh, self.linscale
        return _ScaleTransform(
            lambda values: _core.symlog(
                np.asarray(values, dtype=float), linthresh, base, linscale),
            lambda values: _core.symlog_inverse(
                np.asarray(values, dtype=float), linthresh, base, linscale),
        )


class LogitScale(ScaleBase):
    name = "logit"

    def get_transform(self):
        return _ScaleTransform(_core.logit, _core.logit_inverse)


class AsinhScale(ScaleBase):
    name = "asinh"

    def __init__(self, axis, **kwargs):
        super().__init__(axis, **kwargs)
        self.linear_width = float(kwargs.get("linear_width", 1.0))

    def get_transform(self):
        width = self.linear_width
        return _ScaleTransform(
            lambda values: _core.asinh(np.asarray(values, dtype=float), width),
            lambda values: _core.asinh_inverse(np.asarray(values, dtype=float), width),
        )


class FuncScale(ScaleBase):
    name = "function"

    def __init__(self, axis, functions, **kwargs):
        super().__init__(axis, **kwargs)
        self._forward, self._inverse = functions

    def get_transform(self):
        return _ScaleTransform(self._forward, self._inverse)


class FuncScaleLog(FuncScale):
    name = "functionlog"

    def __init__(self, axis, functions, base=10, **kwargs):
        super().__init__(axis, functions, **kwargs)
        self.base = float(base)

    def get_transform(self):
        log_base = math.log(self.base)
        forward, inverse = self._forward, self._inverse
        return _ScaleTransform(
            lambda values: np.log(forward(values)) / log_base,
            lambda values: inverse(np.power(self.base, values)),
        )


_SCALES = {}


def register_scale(scale_class):
    """Register a scale class under its ``name``, like Matplotlib."""
    _SCALES[scale_class.name] = scale_class
    return scale_class


def get_scale_names():
    """Names of the scales Matplotlib exposes."""
    return ["asinh", "function", "functionlog", "linear", "log", "logit", "symlog"]


for _scale in (
    AsinhScale, FuncScale, FuncScaleLog, LinearScale, LogScale, LogitScale,
    SymmetricalLogScale,
):
    register_scale(_scale)
