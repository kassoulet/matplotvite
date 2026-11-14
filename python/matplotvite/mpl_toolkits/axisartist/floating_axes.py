"""Floating axes compatibility classes."""

from .axislines import Axes
from .grid_helper_curvelinear import GridHelperCurveLinear

__all__ = ("FloatingAxes", "FloatingSubplot", "GridHelperCurveLinear")


class FloatingAxes(Axes):
    """Axes whose grid helper describes a transformed coordinate system."""


class FloatingSubplot:
    def __init__(self, fig, rect, axes_class=FloatingAxes, grid_helper=None, **kwargs):
        self._axes = fig.add_subplot(
            rect, axes_class=axes_class, grid_helper=grid_helper, **kwargs)

    def get_aux_axes(self, *args, **kwargs):
        return self._axes.get_aux_axes(*args, **kwargs)


def floating_axes(ax, *args, **kwargs):
    return ax
