"""Pandas plotting backend for the Matplotlib-style pyplot facade.

Pandas imports the module named by ``pd.options.plotting.backend`` and calls its
``plot(data, kind=..., **kwargs)`` function. The public ``matplotvite.plot``
dispatches DataFrame/Series calls here, so setting the backend to
``"matplotvite"`` is enough.

Supported kinds are line, bar, barh, hist, box, area, scatter and pie. Unknown
kinds raise ``ValueError`` instead of drawing a different chart.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from . import _plotting

SUPPORTED_KINDS = ("line", "bar", "barh", "hist", "box", "area", "scatter", "pie")

_LAYOUT_KWARGS = {
    "backend", "layout", "sharex", "sharey", "table", "secondary_y",
    "mark_right", "include_bool", "sort_columns",
}
_LINE_KWARGS = ("alpha", "linewidth", "lw", "linestyle", "ls", "marker",
                "markersize", "ms", "zorder")
_BAR_KWARGS = ("alpha", "edgecolor", "linewidth", "yerr", "zorder")
_HIST_KWARGS = ("alpha", "cumulative", "edgecolor", "histtype", "linewidth",
                "zorder")
_SCATTER_KWARGS = ("alpha", "cmap", "marker", "s", "vmin", "vmax", "zorder")


def _is_series(data: Any) -> bool:
    return hasattr(data, "index") and not hasattr(data, "columns")


def _label(value: Any) -> str:
    if isinstance(value, tuple):
        return " / ".join(str(part) for part in value)
    return str(value)


def _index_label(index: Any) -> str:
    names = [str(name) for name in getattr(index, "names", ()) if name is not None]
    if names:
        return " / ".join(names)
    name = getattr(index, "name", None)
    return "" if name is None else str(name)


def _column_labels(data: Any, selected: Any) -> list[str]:
    if _is_series(data):
        name = getattr(data, "name", None)
        return ["" if name is None else str(name)]
    return [_label(column) for column in selected]


def _values(data: Any, column: Any) -> np.ndarray:
    values = data.to_numpy() if column is None else data[column].to_numpy()
    return np.asarray(values, dtype=float)


def _selected_columns(data: Any, y: Any, kind: str) -> list[Any]:
    if _is_series(data):
        return [None]
    columns = list(data.columns)
    if y is not None:
        return list(y) if isinstance(y, list) else [y]
    numeric = [column for column in columns
               if np.issubdtype(np.asarray(data[column]).dtype, np.number)]
    candidates = numeric or columns
    if kind == "pie":
        return candidates[:1]
    return candidates


def _axis_values(data: Any, x: Any, use_index: Any) -> tuple[Any, Any, str]:
    """Return (x values, categorical labels or None, default x label)."""
    if x is None:
        if not use_index:
            return np.arange(len(data.index), dtype=float), None, ""
        raw = data.index
        xlabel = _index_label(data.index)
    else:
        try:
            raw = data[x]
        except (KeyError, TypeError):
            raw = x
        xlabel = _label(x)
    array = np.asarray(raw)
    if array.dtype.kind in "Mm":
        # Preserve pandas' DatetimeIndex/Series so the date locator and
        # formatter see the original calendar values, not raw int64 ticks.
        return raw, None, xlabel
    if array.dtype.kind in "iufb":
        return array.astype(float), None, xlabel
    labels = [_label(value) for value in raw]
    return np.arange(len(labels), dtype=float), labels, xlabel


def _categorical_axis(data: Any, x: Any, use_index: Any) -> tuple[Any, Any, str]:
    """Force labels for bar/barh, including datetime and MultiIndex axes."""
    positions, labels, xlabel = _axis_values(data, x, use_index)
    if labels is None:
        if x is None and not use_index:
            labels = [str(index) for index in range(len(positions))]
        else:
            raw = data.index if x is None else data[x]
            labels = [np.datetime_as_string(np.datetime64(value), unit="D")
                      if isinstance(value, np.datetime64)
                      else _label(value)
                      for value in raw]
    return positions, labels, xlabel


def _color_for(colors: Any, index: int) -> Any:
    if isinstance(colors, list) and len(colors) > index:
        return colors[index]
    return colors


def _take(kwargs: dict[str, Any], names: Any) -> dict[str, Any]:
    return {name: kwargs[name] for name in names if name in kwargs}


def _finish(axes: Any, *, title: Any = None, xlabel: Any = None, ylabel: Any = None,
            legend: Any = False, grid: Any = None, rot: Any = None,
            logx: Any = False, logy: Any = False, xlim: Any = None,
            ylim: Any = None, fontsize: Any = None) -> None:
    if title:
        axes.set_title(str(title))
    if xlabel not in (None, ""):
        axes.set_xlabel(str(xlabel), fontsize=fontsize)
    if ylabel not in (None, ""):
        axes.set_ylabel(str(ylabel), fontsize=fontsize)
    if grid:
        axes.grid(True)
    if rot is not None:
        axes.tick_params(axis="x", rotation=float(rot))
    if fontsize is not None:
        axes.tick_params(axis="both", labelsize=float(fontsize))
    if logx:
        axes.set_xscale("log")
    if logy:
        axes.set_yscale("log")
    if xlim is not None:
        axes.set_xlim(*xlim)
    if ylim is not None:
        axes.set_ylim(*ylim)
    if legend:
        axes.legend()


def _line_plot(data: Any, axes: Any, columns: Any, x: Any, use_index: Any,
               kwargs: dict[str, Any], colors: Any) -> tuple[Any, str, bool]:
    positions, labels, xlabel = _axis_values(data, x, use_index)
    arrays = [_values(data, column) for column in columns]
    stacked = bool(kwargs.pop("stacked", False))
    bottoms = np.zeros(len(positions))
    for index, (name, values) in enumerate(zip(_column_labels(data, columns), arrays)):
        style = _take(kwargs, _LINE_KWARGS)
        colour = _color_for(colors, index)
        if colour is not None:
            style["color"] = colour
        if stacked:
            axes.plot(positions, bottoms + values, label=name, **style)
            bottoms = bottoms + values
        else:
            axes.plot(positions, values, label=name, **style)
    if labels is not None:
        axes.set_xticks(positions, labels)
    return xlabel, "", labels is not None


def _bar_plot(data: Any, axes: Any, columns: Any, x: Any, use_index: Any,
              kwargs: dict[str, Any], colors: Any,
              horizontal: bool = False) -> tuple[Any, str, bool]:
    positions, labels, xlabel = _categorical_axis(data, x, use_index)
    arrays = [_values(data, column) for column in columns]
    stacked = bool(kwargs.pop("stacked", False))
    width = float(kwargs.pop("width", 0.8))
    bottoms = np.zeros(len(positions))
    count = max(len(arrays), 1)
    for index, (name, values) in enumerate(zip(_column_labels(data, columns), arrays)):
        style = _take(kwargs, _BAR_KWARGS)
        colour = _color_for(colors, index)
        if colour is not None:
            style["color"] = colour
        if stacked:
            offset, bar_width = 0.0, width
        else:
            bar_width = width / count
            offset = (index - (count - 1) / 2.0) * bar_width
        yerr = style.pop("yerr", None)
        if horizontal:
            style.pop("yerr", None)
            axes.barh(positions + offset, values, height=bar_width,
                      left=bottoms, label=name, **style)
        else:
            axes.bar(positions + offset, values, width=bar_width,
                     bottom=bottoms, label=name, yerr=yerr, **style)
        if stacked:
            bottoms = bottoms + values
    if labels is not None:
        if horizontal:
            axes.set_yticks(positions, labels)
        else:
            axes.set_xticks(positions, labels)
    return xlabel, "", labels is not None


def _hist_plot(data: Any, axes: Any, columns: Any, x: Any,
               kwargs: dict[str, Any], colors: Any) -> tuple[str, str]:
    bins = kwargs.pop("bins", 10)
    density = bool(kwargs.pop("density", False))
    stacked = bool(kwargs.pop("stacked", False))
    arrays = [_values(data, column) for column in columns]
    labels = _column_labels(data, columns)
    for index, (name, values) in enumerate(zip(labels, arrays)):
        style = _take(kwargs, _HIST_KWARGS)
        colour = _color_for(colors, index)
        if colour is not None:
            style["color"] = colour
        axes.hist(values, bins=bins, density=density, stacked=stacked,
                  label=name, **style)
    return "", "Frequency"


def _box_plot(data: Any, axes: Any, columns: Any, kwargs: dict[str, Any],
              colors: Any) -> tuple[str, str]:
    arrays = [_values(data, column) for column in columns]
    labels = _column_labels(data, columns)
    orientation = "horizontal" if kwargs.pop("vert", True) is False else "vertical"
    style = {
        "patch_artist": True,
        "showmeans": True,
        "tick_labels": labels,
        "orientation": orientation,
    }
    if colors:
        style["boxprops"] = {"facecolor": _color_for(colors, 0)}
    axes.boxplot(arrays, **style)
    return "", ""


def _area_plot(data: Any, axes: Any, columns: Any, x: Any, use_index: Any,
               kwargs: dict[str, Any], colors: Any) -> tuple[Any, str, bool]:
    positions, labels, xlabel = _axis_values(data, x, use_index)
    arrays = [_values(data, column) for column in columns]
    labels_for_series = _column_labels(data, columns)
    stacked = kwargs.pop("stacked", True)
    alpha = kwargs.pop("alpha", None)
    bottoms = np.zeros(len(positions))
    for index, (name, values) in enumerate(zip(labels_for_series, arrays)):
        colour = _color_for(colors, index)
        lower = bottoms if stacked else np.zeros(len(values))
        axes.fill_between(positions, lower, lower + values, color=colour,
                          alpha=alpha, label=name)
        if stacked:
            bottoms = bottoms + values
    if labels is not None:
        axes.set_xticks(positions, labels)
    return xlabel, "", labels is not None


def _scatter_plot(data: Any, axes: Any, x: Any, y: Any,
                  kwargs: dict[str, Any], colors: Any) -> tuple[Any, Any]:
    if x is None or y is None:
        raise ValueError("scatter requires both x= and y=")
    xvalues, xlabels, xlabel = _axis_values(data, x, False)
    yvalues, ylabels, ylabel = _axis_values(data, y, False)
    style = _take(kwargs, _SCATTER_KWARGS)
    if isinstance(kwargs.get("c"), (str, tuple, list)):
        style["c"] = kwargs["c"]
    elif colors is not None:
        style["c"] = colors
    if "c" not in style:
        style["c"] = "#1f77b4"
    axes.scatter(xvalues, yvalues, **style)
    if xlabels is not None:
        axes.set_xticks(xvalues, xlabels)
    if ylabels is not None:
        axes.set_yticks(yvalues, ylabels)
    return xlabel, ylabel


def _pie_plot(data: Any, axes: Any, columns: Any, kwargs: dict[str, Any],
              colors: Any) -> tuple[str, str]:
    values = _values(data, columns[0])
    labels = [_label(value) for value in data.index]
    if colors is None:
        colors = kwargs.pop("colors", None)
    style = {
        "labels": labels,
        "colors": colors,
        "autopct": kwargs.pop("autopct", None),
        "startangle": kwargs.pop("startangle", 0),
        "explode": kwargs.pop("explode", None),
        "normalize": kwargs.pop("normalize", True),
    }
    axes.pie(values, **style)
    return "", ""


def plot(data: Any, kind: Any = "line", **kwargs: Any) -> Any:
    """Pandas backend entry point; return the axes (or list for subplots)."""
    kind = "line" if kind is None else str(kind).lower()
    if kind not in SUPPORTED_KINDS:
        raise ValueError(
            f"kind={kind!r} is not supported by the matplotvite pandas backend; "
            f"choose one of: {', '.join(SUPPORTED_KINDS)}")
    if kwargs.pop("subplots", False):
        raise NotImplementedError("matplotvite's pandas backend does not implement subplots=True")

    axes = kwargs.pop("ax", None)
    figsize = kwargs.pop("figsize", None)
    if axes is None:
        figure_kwargs = {}
        if figsize is not None:
            figure_kwargs["figsize"] = figsize
        for name in ("dpi", "facecolor", "edgecolor"):
            if name in kwargs:
                figure_kwargs[name] = kwargs.pop(name)
        _figure, axes = _plotting.subplots(1, 1, **figure_kwargs)

    x = kwargs.pop("x", None)
    y = kwargs.pop("y", None)
    title = kwargs.pop("title", None)
    xlabel = kwargs.pop("xlabel", None)
    ylabel = kwargs.pop("ylabel", None)
    legend = kwargs.pop("legend", None)
    grid = kwargs.pop("grid", None)
    rot = kwargs.pop("rot", None)
    use_index = bool(kwargs.pop("use_index", True))
    logx = bool(kwargs.pop("logx", False))
    logy = bool(kwargs.pop("logy", False))
    xlim = kwargs.pop("xlim", None)
    ylim = kwargs.pop("ylim", None)
    fontsize = kwargs.pop("fontsize", None)
    colors = kwargs.pop("color", None)
    for name in _LAYOUT_KWARGS:
        kwargs.pop(name, None)

    columns = _selected_columns(data, y, kind)
    default_legend = (not _is_series(data) and kind not in ("scatter", "box"))
    if kind == "pie":
        default_legend = True
    show_legend = default_legend if legend is None else bool(legend)

    if kind == "line":
        xlabel, ylabel, _ = _line_plot(data, axes, columns, x, use_index,
                                       kwargs, colors)
    elif kind in ("bar", "barh"):
        xlabel, ylabel, _ = _bar_plot(
            data, axes, columns, x, use_index, kwargs, colors,
            horizontal=kind == "barh")
        if kind == "barh":
            # Pandas puts the index label on the categorical (y) axis.
            xlabel, ylabel = "", xlabel
    elif kind == "hist":
        xlabel, ylabel = _hist_plot(data, axes, columns, x, kwargs, colors)
        show_legend = bool(legend) if legend is not None else not _is_series(data)
    elif kind == "box":
        xlabel, ylabel = _box_plot(data, axes, columns, kwargs, colors)
        show_legend = bool(legend) if legend is not None else False
    elif kind == "area":
        xlabel, ylabel, _ = _area_plot(data, axes, columns, x, use_index,
                                       kwargs, colors)
    elif kind == "scatter":
        xlabel, ylabel = _scatter_plot(data, axes, x, y, kwargs, colors)
        show_legend = bool(legend) if legend is not None else False
    else:
        xlabel, ylabel = _pie_plot(data, axes, columns, kwargs, colors)
        show_legend = bool(legend) if legend is not None else True

    _finish(axes, title=title, xlabel=xlabel, ylabel=ylabel,
            legend=show_legend, grid=grid, rot=rot, logx=logx, logy=logy,
            xlim=xlim, ylim=ylim, fontsize=fontsize)
    return axes
