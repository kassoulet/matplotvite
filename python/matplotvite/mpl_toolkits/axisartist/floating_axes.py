"""Floating axes compatibility classes."""

from typing import Any

from .axislines import Axes
from .grid_helper_curvelinear import GridHelperCurveLinear

__all__ = ("FloatingAxes", "FloatingSubplot", "GridHelperCurveLinear")


class FloatingAxes(Axes):
    """Axes whose grid helper describes a transformed coordinate system."""


class FloatingSubplot:
    def __init__(self, fig: Any, rect: Any, axes_class: Any = FloatingAxes, grid_helper: Any = None, **kwargs: Any) -> None:
        self._axes = fig.add_subplot(
            rect, axes_class=axes_class, grid_helper=grid_helper, **kwargs)

    def get_aux_axes(self, *args: Any, **kwargs: Any) -> Any:
        return self._axes.get_aux_axes(*args, **kwargs)


def floating_axes(ax: Any, *args: Any, **kwargs: Any) -> Any:
    return ax
