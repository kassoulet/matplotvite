"""Small locator and formatter stand-ins for `axisartist` grids."""

from typing import Any

import numpy as np


class MaxNLocator:
    def __init__(self, nbins: Any = 10, steps: Any = None, **kwargs: Any) -> None:
        self.nbins = int(nbins)

    def __call__(self, vmin: Any, vmax: Any) -> Any:
        if not np.isfinite([vmin, vmax]).all() or vmin == vmax:
            return [float(vmin)]
        return list(np.linspace(vmin, vmax, max(2, self.nbins + 1)))

    def set_params(self, **kwargs: Any) -> Any:
        if "nbins" in kwargs:
            self.nbins = int(kwargs["nbins"])
        return self

    def set_nbins(self, nbins: Any) -> Any:
        self.nbins = int(nbins)


class FixedLocator:
    def __init__(self, locs: Any, nbins: Any = None, **kwargs: Any) -> None:
        self.locs = list(locs)

    def __call__(self, vmin: Any = None, vmax: Any = None) -> Any:
        return list(self.locs)


class DictFormatter:
    def __init__(self, formatter_dict: Any, formatter: Any = None, **kwargs: Any) -> None:
        self.formatter_dict = dict(formatter_dict)

    def __call__(self, values: Any, num_to_format: Any = None) -> Any:
        return [self.formatter_dict.get(value, str(value)) for value in values]


class FormatterPrettyPrint:
    def __call__(self, values: Any, num_to_format: Any = None) -> Any:
        return [f"{value:g}" for value in values]


class ExtremeFinderSimple:
    def __init__(self, nx: Any = 100, ny: Any = 100) -> None:
        self.nx, self.ny = int(nx), int(ny)

    def __call__(self, transform_xy: Any, x1: Any, y1: Any, x2: Any, y2: Any) -> Any:
        return x1, x2, y1, y2
