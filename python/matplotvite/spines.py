"""Lightweight spine objects used by custom projections.

The renderer draws the standard four spines itself, so these objects only
carry the geometry and axis registration that projection code inspects.
"""
import numpy as np

from . import _Spine


class _SpinePath:
    def __init__(self, vertices):
        self.vertices = np.asarray(vertices, dtype=float)
        self.codes = None


class Spine(_Spine):
    """A single axes spine, compatible with custom projection subclasses."""

    def __init__(self):
        super().__init__()
        self.axes = None
        self.spine_type = ""
        self._path = _SpinePath(((0.0, 0.0), (0.0, 0.0)))
        self._axis = None
        self._patch = None

    @classmethod
    def linear_spine(cls, axes, spine_type, path=None):
        spine = cls()
        spine.axes = axes
        spine.spine_type = spine_type
        if path is None:
            spine._path = _SpinePath(((0.0, 0.0), (0.0, 0.0)))
        elif hasattr(path, "vertices"):
            spine._path = _SpinePath(path.vertices)
        else:
            spine._path = _SpinePath(path)
        return spine

    @classmethod
    def circular_spine(cls, axes, center, radius):
        spine = cls()
        spine.axes = axes
        spine.spine_type = "circle"
        angles = np.linspace(0.0, 2.0 * np.pi, 65)
        spine._path = _SpinePath(
            np.column_stack((center[0] + radius * np.cos(angles),
                             center[1] + radius * np.sin(angles)))
        )
        return spine

    def register_axis(self, axis):
        self._axis = axis

    def get_path(self):
        return self._path

    def get_spine_transform(self, *args, **kwargs):
        return None

    def set_patch(self, patch):
        self._patch = patch

    def get_patch(self):
        return self._patch

    def _adjust_location(self):
        return None


__all__ = ("Spine",)
