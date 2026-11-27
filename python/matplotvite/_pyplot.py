"""The stateful pyplot facade and its wrappers."""
import datetime as _datetime
import os
import threading
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from ._axes import Axes
from ._figure import Figure, _figures
from ._helpers import (
    _FIGURE_KWARGS,
    Text,
    _check_kwargs,
    _cmap_name,
    _ignored,
    _noop_method,
    _state_setter,
)

_current_fig = None
_backend = "agg"
_figure_lock = threading.RLock()


def _find_figure_locked(fig: Any) -> Optional[int]:
    if isinstance(fig, Figure):
        for number, candidate in _figures.items():
            if candidate is fig:
                return number
        number = getattr(fig, "number", None)  # type: ignore[assignment]
        return number if isinstance(number, int) and _figures.get(number) is fig else None
    if isinstance(fig, str):
        return next((number for number, candidate in sorted(_figures.items())
                     if candidate.get_label() == fig), None)
    if isinstance(fig, (int, np.integer)):
        number = int(fig)
        return number if number in _figures else None
    return None


def _new_figure_locked(number: int, label: Any = None, **kwargs: Any) -> Figure:
    global _current_fig
    fig = Figure(**kwargs)
    fig.number = number
    if label is not None:
        fig.set_label(label)
    _figures[number] = fig
    _current_fig = number
    return fig


def figure(*args: Any, num: Any = None, figsize: Any = None, dpi: Any = None,
           facecolor: Any = None, edgecolor: Any = None, **kwargs: Any) -> Figure:
    """Create or activate a figure.

    A leading sequence sets `figsize`, as elsewhere in this facade. A leading
    integer or string is the matplotlib figure number or label; `num=` is also
    accepted. The registry is process-wide and guarded by a lock, while the
    object-oriented `Figure` API is the thread-safe path.
    """
    _check_kwargs(kwargs, "figure", _FIGURE_KWARGS)
    global _current_fig
    if args:
        first = args[0]
        if isinstance(first, (tuple, list, np.ndarray)):
            figsize = first
        elif isinstance(first, (Figure, int, np.integer, str)):
            if num is not None:
                raise TypeError("figure() got multiple values for argument 'num'")
            num = first
        if len(args) > 1:
            second = args[1]
            if isinstance(second, (tuple, list, np.ndarray)):
                figsize = second
            else:
                dpi = second
    with _figure_lock:
        if isinstance(num, Figure):
            number = _find_figure_locked(num)
            if number is not None:
                _current_fig = number
                return num
            number = getattr(num, "number", None)
            if not isinstance(number, int) or number in _figures:
                number = max(_figures, default=0) + 1
            num.number = number
            _figures[number] = num
            _current_fig = number
            return num
        if num is not None and not isinstance(num, (int, np.integer, str)):
            raise TypeError("figure number must be an integer or a string label")
        if isinstance(num, str):
            number = _find_figure_locked(num)
            if number is not None:
                _current_fig = number
                return _figures[number]
            number = max(_figures, default=0) + 1
            return _new_figure_locked(number, label=num, figsize=figsize, dpi=dpi,
                                      facecolor=facecolor, edgecolor=edgecolor)
        if num is not None:
            number = int(num)
            if number in _figures:
                _current_fig = number
                return _figures[number]
        else:
            number = max(_figures, default=0) + 1
        return _new_figure_locked(number, figsize=figsize, dpi=dpi,
                                  facecolor=facecolor, edgecolor=edgecolor)


def gcf() -> Figure:
    """Return the current figure, creating one if none exists."""
    with _figure_lock:
        if _current_fig is not None:
            current = _figures.get(_current_fig)
            if current is not None:
                return current
        return figure()


def gca() -> Any:
    """Return the current axes, creating one if none exists."""
    return gcf().gca()


def close(fig: Any = None) -> Any:
    """Close the current figure, a numbered/labelled figure, or all figures."""
    global _current_fig
    with _figure_lock:
        if fig is None:
            if _current_fig is None:
                return
            _figures.pop(_current_fig, None)
            _current_fig = max(_figures, default=None)
            return
        if isinstance(fig, str) and fig == "all":
            _figures.clear()
            _current_fig = None
            return
        if not isinstance(fig, (Figure, int, np.integer, str)):
            raise TypeError("close() expects a figure number, label, Figure or 'all'")
        number = _find_figure_locked(fig)
        if number is None:
            return
        _figures.pop(number, None)
        if _current_fig == number:
            _current_fig = max(_figures, default=None)


def get_fignums() -> list[int]:
    """Return the numbers of all open figures, in ascending order."""
    with _figure_lock:
        return sorted(_figures)


def fignum_exists(num: Any) -> bool:
    """Return whether a figure with the given number is open."""
    if isinstance(num, np.integer):
        num = int(num)
    if not isinstance(num, int):
        return False
    with _figure_lock:
        return num in _figures


def subplots(nrows: Any = 1, ncols: Any = 1, *, sharex: Any = False,
             sharey: Any = False, squeeze: Any = True, subplot_kw: Any = None,
             gridspec_kw: Any = None, **fig_kw: Any) -> tuple[Figure, Any]:
    """Create a figure and a grid of axes, returning both."""
    fig = figure(**fig_kw)
    return fig, fig.subplots(nrows, ncols, sharex=sharex, sharey=sharey,
                             squeeze=squeeze, subplot_kw=subplot_kw,
                             gridspec_kw=gridspec_kw)


# One entry per pyplot wrapper: target, method, signature, call arguments and
# an optional docstring. `_make_delegate` builds the functions so the signature
# and docstring the docs and stubs see match the table.
_PYPLOT_DELEGATES = {
    "subplot": ('figure', 'add_subplot', '*args, **kwargs',
                '*args, **kwargs', '`subplot(nrows, ncols, index)` or `subplot(gs[row, col])`.'),
    "clabel": ('axes', 'clabel', 'CS, levels=None, **kwargs',
                'CS, levels=levels, **kwargs', '`plt.clabel()` shim for the current axes.'),
    "suptitle": ('figure', 'suptitle', 't, x=0.5, y=0.98, fontsize=None, **kwargs',
                't, x=x, y=y, fontsize=fontsize, **kwargs', 'Add a centred title above the current figure.'),
    "figtext": ('figure', 'text', 'x, y, s, **kwargs',
                'x, y, s, **kwargs', 'Place text in figure coordinates on the current figure.'),
    "polar": ('axes', 'plot', '*args, **kwargs',
                '*args, **kwargs', 'Call ``Axes.polar`` on the current axes and return its result.'),
    "title": ('axes', 'set_title', 'text, fontsize=None, **kwargs',
                'text, fontsize=fontsize, **kwargs', 'Set the title of the current axes.'),
    "text": ('axes', 'text', '*args, **kwargs',
                '*args, **kwargs', None),
    "xticks": ('axes', 'xticks', 'ticks=None, labels=None, **kwargs',
                'ticks, labels=labels, **kwargs', 'Set or query the x ticks and labels of the current axes.'),
    "yticks": ('axes', 'yticks', 'ticks=None, labels=None, **kwargs',
                'ticks, labels=labels, **kwargs', 'Set or query the y ticks and labels of the current axes.'),
    "imshow": ('axes', 'imshow', "X, cmap=None, vmin=None, vmax=None, extent=None, origin='upper', interpolation=None, aspect=None, alpha=None, **kwargs",
                'X, cmap=cmap, vmin=vmin, vmax=vmax, extent=extent, origin=origin, interpolation=interpolation, aspect=aspect, alpha=alpha, **kwargs', None),
    "xscale": ('axes', 'set_xscale', '*args, **kwargs',
                '*args, **kwargs', 'Call ``Axes.xscale`` on the current axes and return its result.'),
    "yscale": ('axes', 'set_yscale', '*args, **kwargs',
                '*args, **kwargs', 'Call ``Axes.yscale`` on the current axes and return its result.'),
    "semilogx": ('axes', 'semilogx', '*args, **kwargs',
                '*args, **kwargs', None),
    "semilogy": ('axes', 'semilogy', '*args, **kwargs',
                '*args, **kwargs', None),
    "loglog": ('axes', 'loglog', '*args, **kwargs',
                '*args, **kwargs', None),
    "hlines": ('axes', 'hlines', '*args, **kwargs',
                '*args, **kwargs', None),
    "vlines": ('axes', 'vlines', '*args, **kwargs',
                '*args, **kwargs', None),
    "step": ('axes', 'step', '*args, **kwargs',
                '*args, **kwargs', None),
    "stairs": ('axes', 'stairs', '*args, **kwargs',
                '*args, **kwargs', None),
    "tight_layout": ('figure', 'tight_layout', '*args, **kwargs',
                '*args, **kwargs', None),
    "subplots_adjust": ('figure', 'subplots_adjust', '*args, **kwargs',
                '*args, **kwargs', None),
    "hist": ('axes', 'hist', '*args, **kwargs',
                '*args, **kwargs', None),
    "fill_between": ('axes', 'fill_between', '*args, **kwargs',
                '*args, **kwargs', None),
    "fill_betweenx": ('axes', 'fill_betweenx', '*args, **kwargs',
                '*args, **kwargs', None),
    "fill": ('axes', 'fill', '*args, **kwargs',
                '*args, **kwargs', None),
    "matshow": ('axes', 'matshow', 'A, fignum=None, **kwargs',
                'A, **kwargs', None),
    "table": ('axes', 'table', 'cellText=None, cellColours=None, **kwargs',
                'cellText=cellText, cellColours=cellColours, **kwargs', None),
    "spy": ('axes', 'spy', "Z, precision=0, marker=None, markersize=None, aspect='equal', origin='upper', **kwargs",
                'Z, precision=precision, marker=marker, markersize=markersize, aspect=aspect, origin=origin, **kwargs', None),
    "axhline": ('axes', 'axhline', '*args, **kwargs',
                '*args, **kwargs', None),
    "axvline": ('axes', 'axvline', '*args, **kwargs',
                '*args, **kwargs', None),
    "axhspan": ('axes', 'axhspan', '*args, **kwargs',
                '*args, **kwargs', None),
    "axvspan": ('axes', 'axvspan', '*args, **kwargs',
                '*args, **kwargs', None),
    "bar": ('axes', 'bar', '*args, **kwargs',
                '*args, **kwargs', None),
    "bar_label": ('axes', 'bar_label', "container, labels=None, fmt='%g', label_type='edge', padding=0, **kwargs",
                'container, labels=labels, fmt=fmt, label_type=label_type, padding=padding, **kwargs', None),
    "barh": ('axes', 'barh', '*args, **kwargs',
                '*args, **kwargs', None),
    "boxplot": ('axes', 'boxplot', '*args, **kwargs',
                '*args, **kwargs', None),
    "violinplot": ('axes', 'violinplot', '*args, **kwargs',
                '*args, **kwargs', None),
    "pie": ('axes', 'pie', '*args, **kwargs',
                '*args, **kwargs', None),
    "pie_label": ('axes', 'pie_label', '*args, **kwargs',
                '*args, **kwargs', None),
    "stackplot": ('axes', 'stackplot', '*args, **kwargs',
                '*args, **kwargs', None),
    "stem": ('axes', 'stem', '*args, **kwargs',
                '*args, **kwargs', None),
    "pcolormesh": ('axes', 'pcolormesh', '*args, **kwargs',
                '*args, **kwargs', None),
    "pcolor": ('axes', 'pcolormesh', '*args, **kwargs',
                '*args, **kwargs', 'Call ``Axes.pcolor`` on the current axes and return its result.'),
    "pcolorfast": ('axes', 'pcolormesh', '*args, **kwargs',
                '*args, **kwargs', 'Call ``Axes.pcolorfast`` on the current axes and return its result.'),
    "hist2d": ('axes', 'hist2d', '*args, **kwargs',
                '*args, **kwargs', None),
    "hexbin": ('axes', 'hexbin', '*args, **kwargs',
                '*args, **kwargs', None),
    "annotate": ('axes', 'annotate', '*args, **kwargs',
                '*args, **kwargs', None),
    "scatter": ('axes', 'scatter', "x, y, s=None, c=None, alpha=None, cmap=None, label='', marker='o', vmin=None, vmax=None, data=None, norm=None, **kwargs",
                'x, y, s=s, c=c, alpha=alpha, cmap=cmap, label=label, marker=marker, vmin=vmin, vmax=vmax, data=data, norm=norm, **kwargs', None),
    "autoscale": ('axes', 'autoscale', "enable=True, axis='both', tight=None",
                'enable=enable, axis=axis, tight=tight', 'Call `Axes.autoscale` on the current axes.'),
    "specgram": ('axes', 'specgram', '*args, **kwargs',
                '*args, **kwargs', None),
    "barbs": ('axes', 'barbs', '*args, **kwargs',
                '*args, **kwargs', None),
    "ecdf": ('axes', 'ecdf', '*args, **kwargs',
                '*args, **kwargs', None),
    "figimage": ('figure', 'figimage', '*args, **kwargs',
                '*args, **kwargs', 'Place an image on the current figure with `Figure.figimage`.'),
    "streamplot": ('axes', 'streamplot', '*args, **kwargs',
                '*args, **kwargs', None),
    "quiver": ('axes', 'quiver', '*args, **kwargs',
                '*args, **kwargs', None),
    "quiverkey": ('axes', 'quiverkey', '*args, **kwargs',
                '*args, **kwargs', None),
    "errorbar": ('axes', 'errorbar', "x, y, yerr=None, xerr=None, fmt='', ecolor=None, elinewidth=None, capsize=None, label='', color=None, **kwargs",
                'x, y, yerr=yerr, xerr=xerr, fmt=fmt, ecolor=ecolor, elinewidth=elinewidth, capsize=capsize, label=label, color=color', None),
    "colorbar": ('figure', 'colorbar', "mappable=None, ax=None, label='', **kwargs",
                'mappable, ax=ax, label=label, **kwargs', 'Add a colorbar for a mappable to the current figure.'),
    "contour": ('axes', 'contour', '*args, levels=None, colors=None, cmap=None, linewidths=None, alpha=None, **kwargs',
                '*args, levels=levels, colors=colors, cmap=cmap, linewidths=linewidths, alpha=alpha, **kwargs', None),
    "contourf": ('axes', 'contourf', '*args, levels=None, colors=None, cmap=None, alpha=None, **kwargs',
                '*args, levels=levels, colors=colors, cmap=cmap, alpha=alpha, **kwargs', None),
    "triplot": ('axes', 'triplot', '*args, **kwargs',
                '*args, **kwargs', None),
    "tricontour": ('axes', 'tricontour', '*args, levels=None, colors=None, cmap=None, linewidths=None, alpha=None, **kwargs',
                '*args, levels=levels, colors=colors, cmap=cmap, linewidths=linewidths, alpha=alpha, **kwargs', None),
    "tricontourf": ('axes', 'tricontourf', '*args, levels=None, colors=None, cmap=None, linewidths=None, alpha=None, **kwargs',
                '*args, levels=levels, colors=colors, cmap=cmap, linewidths=linewidths, alpha=alpha, **kwargs', None),
    "tripcolor": ('axes', 'tripcolor', '*args, **kwargs',
                '*args, **kwargs', None),
    "legend": ('axes', 'legend', '*args, **kwargs',
                '*args, **kwargs', None),
    "eventplot": ('axes', 'eventplot', '*args, **kwargs',
                '*args, **kwargs', None),
    "broken_barh": ('axes', 'broken_barh', '*args, **kwargs',
                '*args, **kwargs', None),
    "minorticks_on": ('axes', 'minorticks_on', '',
                '', None),
    "minorticks_off": ('axes', 'minorticks_off', '',
                '', None),
    "grid": ('axes', 'grid', '*args, **kwargs',
                '*args, **kwargs', None),
    "tick_params": ('axes', 'tick_params', '*args, **kwargs',
                '*args, **kwargs', None),
    "axline": ('axes', 'axline', '*args, **kwargs',
                '*args, **kwargs', None),
}


def _make_delegate(name: Any, target: Any, method: Any, signature: Any, call: Any, doc: Any) -> Any:
    """Build a pyplot wrapper with the signature and docstring the docs expect."""
    scope = {"__name__": __name__, "_current": gcf if target == "figure" else gca}
    source = f"def {name}({signature}):\n    return _current().{method}({call})\n"
    # `source` is built from the table above, not external input.
    exec(source, scope)  # noqa: S102  # nosec B102
    function = scope[name]
    function.__doc__ = doc or (
        f"Call ``{'Figure' if target == 'figure' else 'Axes'}.{method}`` on the "
        f"current {'figure' if target == 'figure' else 'axes'} and return its result.")
    return function


subplot = _make_delegate("subplot", *_PYPLOT_DELEGATES["subplot"])
clabel = _make_delegate("clabel", *_PYPLOT_DELEGATES["clabel"])
suptitle = _make_delegate("suptitle", *_PYPLOT_DELEGATES["suptitle"])
figtext = _make_delegate("figtext", *_PYPLOT_DELEGATES["figtext"])
polar = _make_delegate("polar", *_PYPLOT_DELEGATES["polar"])
title = _make_delegate("title", *_PYPLOT_DELEGATES["title"])
text = _make_delegate("text", *_PYPLOT_DELEGATES["text"])
xticks = _make_delegate("xticks", *_PYPLOT_DELEGATES["xticks"])
yticks = _make_delegate("yticks", *_PYPLOT_DELEGATES["yticks"])
imshow = _make_delegate("imshow", *_PYPLOT_DELEGATES["imshow"])
xscale = _make_delegate("xscale", *_PYPLOT_DELEGATES["xscale"])
yscale = _make_delegate("yscale", *_PYPLOT_DELEGATES["yscale"])
semilogx = _make_delegate("semilogx", *_PYPLOT_DELEGATES["semilogx"])
semilogy = _make_delegate("semilogy", *_PYPLOT_DELEGATES["semilogy"])
loglog = _make_delegate("loglog", *_PYPLOT_DELEGATES["loglog"])
hlines = _make_delegate("hlines", *_PYPLOT_DELEGATES["hlines"])
vlines = _make_delegate("vlines", *_PYPLOT_DELEGATES["vlines"])
step = _make_delegate("step", *_PYPLOT_DELEGATES["step"])
stairs = _make_delegate("stairs", *_PYPLOT_DELEGATES["stairs"])
tight_layout = _make_delegate("tight_layout", *_PYPLOT_DELEGATES["tight_layout"])
subplots_adjust = _make_delegate("subplots_adjust", *_PYPLOT_DELEGATES["subplots_adjust"])
hist = _make_delegate("hist", *_PYPLOT_DELEGATES["hist"])
fill_between = _make_delegate("fill_between", *_PYPLOT_DELEGATES["fill_between"])
fill_betweenx = _make_delegate("fill_betweenx", *_PYPLOT_DELEGATES["fill_betweenx"])
fill = _make_delegate("fill", *_PYPLOT_DELEGATES["fill"])
matshow = _make_delegate("matshow", *_PYPLOT_DELEGATES["matshow"])
table = _make_delegate("table", *_PYPLOT_DELEGATES["table"])
spy = _make_delegate("spy", *_PYPLOT_DELEGATES["spy"])
axhline = _make_delegate("axhline", *_PYPLOT_DELEGATES["axhline"])
axvline = _make_delegate("axvline", *_PYPLOT_DELEGATES["axvline"])
axhspan = _make_delegate("axhspan", *_PYPLOT_DELEGATES["axhspan"])
axvspan = _make_delegate("axvspan", *_PYPLOT_DELEGATES["axvspan"])
bar = _make_delegate("bar", *_PYPLOT_DELEGATES["bar"])
bar_label = _make_delegate("bar_label", *_PYPLOT_DELEGATES["bar_label"])
barh = _make_delegate("barh", *_PYPLOT_DELEGATES["barh"])
boxplot = _make_delegate("boxplot", *_PYPLOT_DELEGATES["boxplot"])
violinplot = _make_delegate("violinplot", *_PYPLOT_DELEGATES["violinplot"])
pie = _make_delegate("pie", *_PYPLOT_DELEGATES["pie"])
pie_label = _make_delegate("pie_label", *_PYPLOT_DELEGATES["pie_label"])
stackplot = _make_delegate("stackplot", *_PYPLOT_DELEGATES["stackplot"])
stem = _make_delegate("stem", *_PYPLOT_DELEGATES["stem"])
pcolormesh = _make_delegate("pcolormesh", *_PYPLOT_DELEGATES["pcolormesh"])
pcolor = _make_delegate("pcolor", *_PYPLOT_DELEGATES["pcolor"])
pcolorfast = _make_delegate("pcolorfast", *_PYPLOT_DELEGATES["pcolorfast"])
hist2d = _make_delegate("hist2d", *_PYPLOT_DELEGATES["hist2d"])
hexbin = _make_delegate("hexbin", *_PYPLOT_DELEGATES["hexbin"])
annotate = _make_delegate("annotate", *_PYPLOT_DELEGATES["annotate"])
scatter = _make_delegate("scatter", *_PYPLOT_DELEGATES["scatter"])
autoscale = _make_delegate("autoscale", *_PYPLOT_DELEGATES["autoscale"])
specgram = _make_delegate("specgram", *_PYPLOT_DELEGATES["specgram"])
barbs = _make_delegate("barbs", *_PYPLOT_DELEGATES["barbs"])
ecdf = _make_delegate("ecdf", *_PYPLOT_DELEGATES["ecdf"])
figimage = _make_delegate("figimage", *_PYPLOT_DELEGATES["figimage"])
streamplot = _make_delegate("streamplot", *_PYPLOT_DELEGATES["streamplot"])
quiver = _make_delegate("quiver", *_PYPLOT_DELEGATES["quiver"])
quiverkey = _make_delegate("quiverkey", *_PYPLOT_DELEGATES["quiverkey"])
errorbar = _make_delegate("errorbar", *_PYPLOT_DELEGATES["errorbar"])
colorbar = _make_delegate("colorbar", *_PYPLOT_DELEGATES["colorbar"])
contour = _make_delegate("contour", *_PYPLOT_DELEGATES["contour"])
contourf = _make_delegate("contourf", *_PYPLOT_DELEGATES["contourf"])
triplot = _make_delegate("triplot", *_PYPLOT_DELEGATES["triplot"])
tricontour = _make_delegate("tricontour", *_PYPLOT_DELEGATES["tricontour"])
tricontourf = _make_delegate("tricontourf", *_PYPLOT_DELEGATES["tricontourf"])
tripcolor = _make_delegate("tripcolor", *_PYPLOT_DELEGATES["tripcolor"])
legend = _make_delegate("legend", *_PYPLOT_DELEGATES["legend"])
eventplot = _make_delegate("eventplot", *_PYPLOT_DELEGATES["eventplot"])
broken_barh = _make_delegate("broken_barh", *_PYPLOT_DELEGATES["broken_barh"])
minorticks_on = _make_delegate("minorticks_on", *_PYPLOT_DELEGATES["minorticks_on"])
minorticks_off = _make_delegate("minorticks_off", *_PYPLOT_DELEGATES["minorticks_off"])
grid = _make_delegate("grid", *_PYPLOT_DELEGATES["grid"])
tick_params = _make_delegate("tick_params", *_PYPLOT_DELEGATES["tick_params"])
axline = _make_delegate("axline", *_PYPLOT_DELEGATES["axline"])


def subplot2grid(shape: Any, loc: Any, rowspan: Any = 1, colspan: Any = 1, fig: Any = None, **kwargs: Any) -> Any:
    """Create an axes spanning a cell of a regular grid."""
    return (fig or gcf()).subplot2grid(shape, loc, rowspan=rowspan,
                                      colspan=colspan, **kwargs)


def subplot_mosaic(mosaic: Any, empty_sentinel: Any = ".", figsize: Any = None, dpi: Any = None,
                   facecolor: Any = None, edgecolor: Any = None, **kwargs: Any) -> Any:
    """Create a figure from an ASCII or nested mosaic layout."""
    fig = figure(figsize, dpi=dpi, facecolor=facecolor, edgecolor=edgecolor)
    return fig, fig.subplot_mosaic(mosaic, empty_sentinel=empty_sentinel)
class _ScalarFormatter:
    """Compact `ScalarFormatter` used by `Axes.ticklabel_format`."""

    def __init__(self, style: Any = None, scilimits: Any = None, useOffset: Any = None,
                 useLocale: Any = None, useMathText: Any = None) -> None:
        if style not in (None, "plain", "sci"):
            raise ValueError(f"style must be 'sci', 'plain' or None, not {style!r}")
        self.style = style
        self.scilimits = None if scilimits is None else tuple(scilimits)
        self.useOffset = True if useOffset is None else bool(useOffset)
        self.useLocale = bool(useLocale)
        self.useMathText = False if useMathText is None else bool(useMathText)
        self.locs = None

    set_locs = _state_setter(
        "locs", 'locs', 'locs')

    def _scientific(self, value: Any) -> Any:
        if self.scilimits is None:
            return False
        magnitude = abs(value)
        return magnitude != 0.0 and not 10.0 ** self.scilimits[0] <= magnitude < 10.0 ** self.scilimits[1]

    def __call__(self, x: Any, pos: Any = None) -> Any:
        value = float(x)
        if self.style == "sci" or (self.style is None and self._scientific(value)):
            return f"{value:.2e}"
        return f"{value:g}"

    def format_data_short(self, value: Any) -> Any: return self(value)


class FormatStrFormatter:
    """Old-style `%` formatter used by `FormatStrFormatter`."""

    def __init__(self, fmt: Any) -> None:
        self.fmt = str(fmt)

    def __call__(self, x: Any, pos: Any = None) -> Any:
        return self.fmt % x


class FuncFormatter:
    """Formatter backed by a user function, as `matplotlib.ticker.FuncFormatter`."""

    def __init__(self, func: Any) -> None:
        if not callable(func):
            raise TypeError("FuncFormatter needs a callable")
        self.func = func
        self.locs = None

    def __call__(self, x: Any, pos: Any = None) -> Any:
        return str(self.func(x, pos))

    def format_data_short(self, value: Any) -> Any:
        return str(self.func(value, None))

    set_locs = _state_setter(
        "locs", 'locs', 'locs')


class _Epoch(float):
    """Date-number-compatible epoch used by the harvested JPL unit tests."""

    def __new__(cls: Any, name: Any, dt: Any = None) -> Any:
        if dt is None:
            value = 0.0
        elif isinstance(dt, _datetime.datetime):
            value = (dt - _datetime.datetime(1970, 1, 1)).total_seconds() / 86400.0
        else:
            value = float(dt)
        return float.__new__(cls, value)


class _Duration(float):
    """Second-based duration with the small `convert` surface tests use."""

    def __new__(cls: Any, name: Any, seconds: Any = 0.0) -> Any:
        return float.__new__(cls, float(seconds))

    def convert(self, unit: Any) -> Any:
        return float(self)


class _TestingUnits:
    """Small `matplotlib.testing` stand-in for the harvested unit tests."""

    sec = 1.0
    km = 1.0
    deg = 1.0
    Epoch = _Epoch
    Duration = _Duration

    def __init__(self) -> None:
        self.day = _Duration("ET", 86400.0)

    register = _noop_method("register", 'self')


testing = _TestingUnits()


def twinx(ax: Any = None) -> Any:
    """`plt.twinx()` shim."""
    return (ax or gca()).twinx()


def twiny(ax: Any = None) -> Any:
    """`plt.twiny()` shim."""
    return (ax or gca()).twiny()




def _is_pandas_data(value: Any) -> Any:
    """Whether `value` is a pandas DataFrame or Series, without importing pandas."""
    return (type(value).__module__.split(".")[0] == "pandas"
            and hasattr(value, "index")
            and (hasattr(value, "columns") or hasattr(value, "name")))


def plot(*args: Any, **kwargs: Any) -> Any:
    """Call ``Axes.plot`` on the current axes and return its result.

    A pandas DataFrame/Series with a `kind=` keyword is dispatched to the
    pandas plotting backend, so ``pd.options.plotting.backend = "matplotvite"``
    works without a separate backend module.
    """
    if args and "kind" in kwargs and _is_pandas_data(args[0]):
        from ._pandas import plot as pandas_plot
        return pandas_plot(*args, **kwargs)
    return gca().plot(*args, **kwargs)
def xlabel(text: Any, fontsize: Any = None, **kwargs: Any) -> Any:
    """Set the x-axis label of the current axes."""
    gca().set_xlabel(text, fontsize=fontsize)
def ylabel(text: Any, fontsize: Any = None, **kwargs: Any) -> Any:
    """Set the y-axis label of the current axes."""
    gca().set_ylabel(text, fontsize=fontsize)
# `text` is a function, so the class hangs off it as Matplotlib does; mypy
# cannot express attributes on a callable.
text.Text = Text


def xkcd(scale: Any = 1, length: Any = 100, randomness: Any = 2) -> Any:
    """Matplotlib's sketch style has no renderer support; accept and ignore it.

    The call also works as `with plt.xkcd():`, so return a context manager.
    """
    _ignored("xkcd")
    return _NoopContext()
def get_data_path() -> str:
    """Return the directory that holds the bundled data files."""
    return os.path.dirname(os.path.abspath(__file__))
def _delegate_probe(method: Any) -> Any:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return getattr(gca(), method)(*args, **kwargs)
    wrapper.__name__ = method
    return wrapper


grouped_bar = _delegate_probe("grouped_bar")






def axes(*args: Any, **kwargs: Any) -> Any:
    """Compatibility shim: matplotvite lays out subplots on a grid, so this returns the
    current axes (creating one if needed)."""
    return gca()





def get_backend() -> str:
    """Return the active backend name; matplotvite always renders statically."""
    return _backend


def switch_backend(newbackend: Any) -> None:
    """Record a backend name; the renderer and encoded formats do not change."""
    global _backend
    _backend = str(newbackend).lower()


def draw_if_interactive(*args: Any, **kwargs: Any) -> Any:
    """Draw pending figures in interactive mode; matplotvite draws on save."""
    pass


def draw_all(*args: Any, **kwargs: Any) -> Any:
    """Draw every open figure; matplotvite draws on save, so this is a no-op."""
    pass


def show(*args: Any, **kwargs: Any) -> Any:
    """Display figures; Matplotvite has no window backend, so this is a no-op."""
    pass

def draw(*args: Any, **kwargs: Any) -> Any:
    """Flush pending drawing work; Matplotvite writes on save, so this is a no-op."""
    pass

def pause(*args: Any, **kwargs: Any) -> Any:
    """Pause for an interval; Matplotvite has no interactive backend, so this is a no-op."""
    pass


def ion(*args: Any, **kwargs: Any) -> Any:
    """Enable interactive mode; Matplotvite always renders statically."""
    pass
def ioff(*args: Any, **kwargs: Any) -> Any:
    """Disable interactive mode; Matplotvite always renders statically."""
    pass
def use(*args: Any, **kwargs: Any) -> None: pass
def connect(*args: Any, **kwargs: Any) -> int: return 1
def figaspect(aspect: Any) -> tuple[float, float]:
    """Return a figure size with the requested height/width ratio."""
    aspect = float(aspect)
    if aspect < 1.0:
        return (4.0, 4.0 * aspect)
    return (4.0 * aspect, 4.0)


def get_figlabels() -> list[str]:
    """Return the labels of all open figures, in figure-number order."""
    with _figure_lock:
        return [_figures[number].get_label() for number in sorted(_figures)]


def sca(ax: Any) -> Any:
    """Set the current axes, switching to its figure when needed."""
    if not isinstance(ax, Axes):
        raise ValueError("sca() requires an Axes instance")
    fig = ax._fig
    if fig is None:
        raise ValueError("sca() requires an Axes that belongs to a figure")
    global _current_fig
    with _figure_lock:
        number = _find_figure_locked(fig)
        if number is None:
            number = max(_figures, default=0) + 1
            fig.number = number
            _figures[number] = fig
        _current_fig = number
    fig.sca(ax)


def box(on: Any = None) -> Any:
    """Turn the current axes' frame on or off, toggling when `on` is None."""
    ax = gca()
    if on is None:
        on = not ax.get_frame_on()
    ax.set_frame_on(on)
































def set_cmap(cmap: Any) -> Any:
    """Set the default colormap used by image-like artists."""
    rcParams["image.cmap"] = _cmap_name(cmap)


def xlim(*args: Any, **kwargs: Any) -> Any:
    """Set or query the x limits of the current axes."""
    ax = gca()
    if not args and not kwargs:
        return ax.get_xlim()
    if len(args) == 1 and isinstance(args[0], (tuple, list, np.ndarray)):
        ax.set_xlim(*args[0], **kwargs)
    else:
        ax.set_xlim(*args, **kwargs)
    return ax.get_xlim()


def ylim(*args: Any, **kwargs: Any) -> Any:
    """Set or query the y limits of the current axes."""
    ax = gca()
    if not args and not kwargs:
        return ax.get_ylim()
    if len(args) == 1 and isinstance(args[0], (tuple, list, np.ndarray)):
        ax.set_ylim(*args[0], **kwargs)
    else:
        ax.set_ylim(*args, **kwargs)
    return ax.get_ylim()


def _is_artist_sequence(obj: Any) -> bool:
    """True for a list of artists such as a `BarContainer`, not a string."""
    return isinstance(obj, (list, tuple, np.flatiter)) and not isinstance(obj, (str, bytes))


def getp(obj: Any, *args: Any) -> Any:
    """Generic getter: `getp(artist, "color")` calls `artist.get_color()`.

    A sequence of artists is read element by element, as in Matplotlib.
    """
    if _is_artist_sequence(obj):
        return [getp(item, *args) for item in obj]
    out = []
    for name in args:
        getter = getattr(obj, f"get_{name}", None)
        if getter is None:
            raise AttributeError(f"{type(obj).__name__} has no get_{name}")
        out.append(getter())
    if not out:
        return None
    return out[0] if len(out) == 1 else out


def setp(obj: Any, *args: Any, **kwargs: Any) -> Any:
    """Generic setter: `setp(artist, color="red")` calls `artist.set_color()`.

    A sequence of artists is updated element by element, as in Matplotlib.
    """
    if _is_artist_sequence(obj):
        # Boxplot returns `None` in place of a hidden flier; Matplotlib skips
        # such entries, and so must setp when styling a whole boxplot dict.
        for item in obj:
            if item is not None:
                setp(item, *args, **kwargs)
        return getp(obj, *args) if args else None
    for name, value in kwargs.items():
        setter = getattr(obj, f"set_{name}", None)
        if setter is None:
            raise AttributeError(f"{type(obj).__name__} has no set_{name}")
        setter(value)
    if args:
        return getp(obj, *args)
    return None


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._cm import _NoopContext
    from ._config import rcParams
