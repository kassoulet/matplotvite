"""Compatibility shims for Matplotlib's `mpl_toolkits.axisartist`."""

from . import angle_helper, grid_finder
from .axislines import Axes, AxesZero
from .floating_axes import FloatingAxes, FloatingSubplot
from .grid_helper_curvelinear import GridHelperCurveLinear
from .parasite_axes import HostAxes, ParasiteAxes

__all__ = (
    "Axes",
    "AxesZero",
    "FloatingAxes",
    "FloatingSubplot",
    "GridHelperCurveLinear",
    "HostAxes",
    "ParasiteAxes",
    "angle_helper",
    "grid_finder",
)
