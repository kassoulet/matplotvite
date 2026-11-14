"""Minimal axes_grid1 compatibility package for matplotvite."""

from .axes_divider import (
    Divider,
    make_axes_area_auto_adjustable,
    make_axes_locatable,
)
from .axes_grid import ImageGrid
from .inset_locator import inset_axes, mark_inset, zoomed_inset_axes

__all__ = (
    "Divider",
    "ImageGrid",
    "inset_axes",
    "make_axes_area_auto_adjustable",
    "make_axes_locatable",
    "mark_inset",
    "zoomed_inset_axes",
)
