"""Size objects for `mpl_toolkits.axes_grid1.axes_divider`."""

__all__ = ("AxesX", "AxesY", "Fixed", "Fraction", "MaxExtent", "Scaled")


class Fixed:
    """An absolute size in inches."""

    def __init__(self, size):
        self._size = float(size)

    def get_size(self, renderer=None):
        return self._size

    def __repr__(self):
        return f"Fixed({self._size:g})"


class Scaled:
    """A size that shares the remaining space in proportion to its weight."""

    def __init__(self, size):
        self._size = float(size)

    def get_size(self, renderer=None):
        return self._size

    def __repr__(self):
        return f"Scaled({self._size:g})"


class Fraction:
    """A size expressed as a fraction of the available span."""

    def __init__(self, fraction, percent=False):
        value = float(fraction)
        self._fraction = value / 100.0 if percent else value

    def get_size(self, renderer=None):
        return self._fraction

    def __repr__(self):
        return f"Fraction({self._fraction:g})"


class _AxesExtent:
    _axis = "x"

    def __init__(self, ax):
        self._ax = ax

    def get_size(self, renderer=None):
        fig = getattr(self._ax, "_fig", None)
        if fig is None:
            return 0.0
        width, height = (float(v) for v in fig.get_size_inches())
        box = self._ax.get_position()
        return (box.width * width) if self._axis == "x" else (box.height * height)

    def __repr__(self):
        return f"{type(self).__name__}({self._ax!r})"


class AxesX(_AxesExtent):
    """The current width of an axes, in inches."""

    _axis = "x"


class AxesY(_AxesExtent):
    """The current height of an axes, in inches."""

    _axis = "y"


class MaxExtent:
    """The largest of the wrapped size objects."""

    def __init__(self, *sizes):
        self._sizes = sizes

    def get_size(self, renderer=None):
        return max((float(size.get_size(renderer)) if hasattr(size, "get_size")
                    else float(size) for size in self._sizes), default=0.0)
