"""Grid-helper data holder used by the axisartist examples."""

from typing import Any

from . import grid_finder


class GridHelperCurveLinear:
    def __init__(self, aux_trans: Any, extreme_finder: Any = None,
                 grid_locator1: Any = None, grid_locator2: Any = None,
                 tick_formatter1: Any = None, tick_formatter2: Any = None,
                 extremes: Any = None, **kwargs: Any) -> None:
        self.aux_trans = aux_trans
        self.extreme_finder = extreme_finder or grid_finder.ExtremeFinderSimple()
        self.grid_locator1 = grid_locator1
        self.grid_locator2 = grid_locator2
        self.tick_formatter1 = tick_formatter1
        self.tick_formatter2 = tick_formatter2
        self.extremes = extremes

    def apply(self, axes: Any) -> Any:
        axes.grid_helper = self
        return self

    def update_lim(self, axes: Any) -> Any:
        return None

    def get_grid_lines(self, *args: Any, **kwargs: Any) -> Any:
        return []
