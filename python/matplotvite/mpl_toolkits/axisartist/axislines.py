"""Constructors shared by the axisartist compatibility modules."""

from matplotvite import Axes as _Axes


class Axes(_Axes):
    """Axes with the axisartist subscriptable axis accessor."""


class AxesZero(_Axes):
    """Axes that also exposes hidden xzero/yzero axis artists."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.axis["xzero"].set_visible(False)
        self.axis["yzero"].set_visible(False)
