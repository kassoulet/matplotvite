"""Angle locators used by the axisartist gallery examples."""

import numpy as np

from . import grid_finder


def _degree_parts(value, scale):
    """Format a coordinate as degrees/minutes/seconds for tick labels."""
    sign = "-" if value < 0 else ""
    value = abs(float(value))
    degrees = int(value)
    minutes = int((value - degrees) * 60)
    seconds = (value - degrees - minutes / 60) * 3600
    if scale == "HMS":
        hours = degrees
        minutes = int((value - hours) * 60)
        seconds = (value - hours - minutes / 60) * 3600
        return f"{sign}{hours:d}h{minutes:02d}m{seconds:04.1f}s"
    if seconds >= 0.05:
        return f"{sign}{degrees:d}°{minutes:02d}′{seconds:04.1f}″"
    return f"{sign}{degrees:d}°{minutes:02d}′"


class LocatorDMS:
    def __init__(self, nbins=10, **kwargs):
        self.nbins = int(nbins)

    def __call__(self, v1, v2):
        return list(np.linspace(v1, v2, max(2, self.nbins + 1)))


class FormatterDMS:
    def __call__(self, values, num_to_format=None):
        return [_degree_parts(v, "DMS") for v in values]


class LocatorHMS:
    def __init__(self, nbins=10, **kwargs):
        self.nbins = int(nbins)

    def __call__(self, v1, v2):
        return list(np.linspace(v1, v2, max(2, self.nbins + 1)))


class FormatterHMS:
    def __call__(self, values, num_to_format=None):
        return [_degree_parts(v, "HMS") for v in values]


class ExtremeFinderCycle(grid_finder.ExtremeFinderSimple):
    def __init__(self, nx=100, ny=100, lon_cycle=360, lat_cycle=180,
                 lon_minmax=None, lat_minmax=None, **kwargs):
        super().__init__(nx, ny)
        self.lon_cycle = lon_cycle
        self.lat_cycle = lat_cycle
        self.lon_minmax = lon_minmax
        self.lat_minmax = lat_minmax
