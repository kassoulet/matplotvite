"""rcParams defaults and the style registry."""
from typing import Any

from ._helpers import _CYCLE, _CycleList

rcParams = {
    "figure.figsize": (6.4, 4.8),
    "figure.dpi": 100.0,
    "lines.linewidth": 1.5,
    "lines.markersize": 6.0,
    "font.size": 10.0,
    "axes.labelsize": 10.0,
    "axes.titlesize": 12.0,
    "xtick.labelsize": 10.0,
    "ytick.labelsize": 10.0,
    "figure.titlesize": 12.0,
    "legend.fontsize": 10.0,
    "axes.prop_cycle": _CycleList(_CYCLE),
    "image.cmap": "viridis",
    "image.interpolation": "nearest",
    "figure.facecolor": "#ffffff",
    "axes.facecolor": "#ffffff",
    "axes.edgecolor": "#000000",
    "axes.grid": False,
    "axes.xmargin": 0.05,
    "axes.ymargin": 0.05,
    "axes.labelcolor": "#000000",
    "xtick.color": "#000000",
    "ytick.color": "#000000",
    "text.color": "#000000",
    "text.parse_math": True,
    "text.usetex": False,
    "grid.color": "#b0b0b0",
    "font.family": ["sans-serif"],
    "font.sans-serif": ["DejaVu Sans", "Bitstream Vera Sans", "Arial"],
    "font.serif": ["DejaVu Serif", "Times New Roman"],
    "font.monospace": ["DejaVu Sans Mono", "Courier New"],
    "savefig.transparent": False,
}
_RC_DEFAULTS = dict(rcParams)


class _Namespace:
    """Namespace whose members come from keyword arguments at construction."""

    def __init__(self, **values: object) -> None: self.__dict__.update(values)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)
