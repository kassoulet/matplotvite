"""Minimal axes_grid1 compatibility package for matplotvite."""

from . import axes_size as Size
from .axes_divider import (
    Divider,
    HBoxDivider,
    SubplotDivider,
    VBoxDivider,
    make_axes_area_auto_adjustable,
    make_axes_locatable,
)
from .axes_grid import ImageGrid
from .axes_rgb import RGBAxes, make_rgb_axes
from .inset_locator import inset_axes, mark_inset, zoomed_inset_axes

__all__ = (
    "Divider",
    "HBoxDivider",
    "ImageGrid",
    "Size",
    "SubplotDivider",
    "VBoxDivider",
    "inset_axes",
    "make_axes_area_auto_adjustable",
    "make_axes_locatable",
    "make_rgb_axes",
    "mark_inset",
    "RGBAxes",
    "zoomed_inset_axes",
)
