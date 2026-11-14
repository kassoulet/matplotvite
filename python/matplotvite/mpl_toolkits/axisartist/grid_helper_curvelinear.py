"""Grid-helper data holder used by the axisartist examples."""

from . import grid_finder


class GridHelperCurveLinear:
    def __init__(self, aux_trans, extreme_finder=None,
                 grid_locator1=None, grid_locator2=None,
                 tick_formatter1=None, tick_formatter2=None,
                 extremes=None, **kwargs):
        self.aux_trans = aux_trans
        self.extreme_finder = extreme_finder or grid_finder.ExtremeFinderSimple()
        self.grid_locator1 = grid_locator1
        self.grid_locator2 = grid_locator2
        self.tick_formatter1 = tick_formatter1
        self.tick_formatter2 = tick_formatter2
        self.extremes = extremes

    def apply(self, axes):
        axes.grid_helper = self
        return self

    def update_lim(self, axes):
        return None

    def get_grid_lines(self, *args, **kwargs):
        return []
