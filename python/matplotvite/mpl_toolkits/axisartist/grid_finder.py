"""Small locator and formatter stand-ins for `axisartist` grids."""

import numpy as np


class MaxNLocator:
    def __init__(self, nbins=10, steps=None, **kwargs):
        self.nbins = int(nbins)

    def __call__(self, vmin, vmax):
        if not np.isfinite([vmin, vmax]).all() or vmin == vmax:
            return [float(vmin)]
        return list(np.linspace(vmin, vmax, max(2, self.nbins + 1)))

    def set_params(self, **kwargs):
        if "nbins" in kwargs:
            self.nbins = int(kwargs["nbins"])
        return self

    def set_nbins(self, nbins):
        self.nbins = int(nbins)


class FixedLocator:
    def __init__(self, locs, nbins=None, **kwargs):
        self.locs = list(locs)

    def __call__(self, vmin=None, vmax=None):
        return list(self.locs)


class DictFormatter:
    def __init__(self, formatter_dict, formatter=None, **kwargs):
        self.formatter_dict = dict(formatter_dict)

    def __call__(self, values, num_to_format=None):
        return [self.formatter_dict.get(value, str(value)) for value in values]


class FormatterPrettyPrint:
    def __call__(self, values, num_to_format=None):
        return [f"{value:g}" for value in values]


class ExtremeFinderSimple:
    def __init__(self, nx=100, ny=100):
        self.nx, self.ny = int(nx), int(ny)

    def __call__(self, transform_xy, x1, y1, x2, y2):
        return x1, x2, y1, y2
