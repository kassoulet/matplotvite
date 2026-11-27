"""Axes mixin for box, violin and other summary plots."""
import datetime as _datetime
from typing import TYPE_CHECKING

import numpy as np

from ._axes_plot import _AxesMixinBase
from ._containers import _LineHandle, _number, _single_color, _ViolinBody
from ._core import violin_outline as _violin_outline_core
from ._helpers import _CYCLE, _date_to_num, _datetime_to_num, _looks_like_dates


class _StatsAxes(_AxesMixinBase):
    """Statistical plots: box, whisker and violin summaries."""

    def boxplot(self, x, notch=None, sym=None, vert=None, whis=None, positions=None,
                widths=None, patch_artist=None, labels=None, orientation=None,
                showmeans=False, showcaps=None, showbox=None, showfliers=None,
                meanline=False, capwidths=None, boxprops=None, medianprops=None,
                whiskerprops=None, capprops=None, flierprops=None, meanprops=None,
                manage_ticks=True, autorange=False, label=None, tick_labels=None,
                **kwargs):
        """Box-and-whisker plot for one dataset or a sequence of datasets.

        Returns a dict with `boxes`, `medians`, `whiskers`, `caps`, `fliers`
        and `means` lists, matching matplotlib's `boxplot` result."""
        groups = _box_datasets(x)
        if not groups:
            raise ValueError("boxplot needs at least one dataset")
        if orientation is None:
            orientation = "vertical" if (vert is None or vert) else "horizontal"
        if orientation not in ("vertical", "horizontal"):
            raise ValueError(f"unsupported orientation: {orientation!r}")
        n = len(groups)
        pos = np.arange(1.0, n + 1.0) if positions is None else _fill(positions, n)
        wid = _fill(0.5 if widths is None else widths, n)
        # Matplotlib's caps are half the box width unless `capwidths` says otherwise.
        cap = _fill([0.5 * v for v in wid] if capwidths is None else capwidths, n)
        (box_color, box_edge, box_width, box_alpha, median_color, median_width,
         whisker_color, whisker_width, cap_color, cap_width, mean_color, flier_format,
         flier_marker, flier_face, flier_edge, flier_width, flier_size) = _box_style(
            boxprops, medianprops, whiskerprops, capprops, flierprops, meanprops, sym)
        draw_caps = True if showcaps is None else bool(showcaps)
        draw_box = True if showbox is None else bool(showbox)
        draw_fliers = True if showfliers is None else bool(showfliers)
        if labels is None:
            labels = tick_labels
        out = dict(boxes=[], medians=[], whiskers=[], caps=[], fliers=[], means=[])  # type: ignore[var-annotated]
        for i, raw in enumerate(groups):
            vals = _as_f64(raw)
            vals = vals[np.isfinite(vals)]
            if vals.size == 0:
                raise ValueError("boxplot datasets must not be empty")
            q1, med, q3, lo, hi, fliers, mean, iqr = _box_stats(vals, whis, autorange)
            loc, half = float(pos[i]), float(wid[i]) / 2.0
            if draw_box:
                if notch:
                    depth = 1.57 * iqr / np.sqrt(vals.size)
                    nlo, nhi = med - depth, med + depth
                    inner = half / 2.0
                    if orientation == "vertical":
                        xs = [loc - half, loc - half, loc - inner, loc - inner,
                              loc - half, loc - half, loc + half, loc + half,
                              loc + inner, loc + inner, loc + half, loc + half, loc - half]
                        ys = [q1, nlo, nlo, nhi, nhi, q3, q3, nhi, nhi, nlo, nlo, q1, q1]
                    else:
                        ys = [loc - half, loc - half, loc - inner, loc - inner,
                              loc - half, loc - half, loc + half, loc + half,
                              loc + inner, loc + inner, loc + half, loc + half, loc - half]
                        xs = [q1, nlo, nlo, nhi, nhi, q3, q3, nhi, nhi, nlo, nlo, q1, q1]
                    if patch_artist:
                        self._append_band(_band(xs, ys, box_color, box_alpha))
                    entry = _series(xs, ys, "", box_edge, linewidth=box_width)
                    self._append_series(entry)
                    out["boxes"].append(_LineHandle(entry, box_color if patch_artist else "none"))
                elif orientation == "vertical":
                    bars = self.bar([loc], [q3 - q1], width=wid[i], bottom=q1,
                                    color=box_color if patch_artist else "none",
                                    edgecolor=box_edge, label=str(label or "") if i == 0 else "")
                    out["boxes"].append(bars[0])
                else:
                    bars = self.barh([loc], [q3 - q1], height=wid[i], left=q1,
                                     color=box_color if patch_artist else "none",
                                     edgecolor=box_edge, label=str(label or "") if i == 0 else "")
                    out["boxes"].append(bars[0])
            if orientation == "vertical":
                med_entry = self._stats_line([loc - half, loc + half], [med, med],
                                             median_color, median_width)
                out["medians"].append(med_entry)
                for y0, y1 in ((q3, hi), (q1, lo)):
                    out["whiskers"].append(self._stats_line(
                        [loc, loc], [y0, y1], whisker_color, whisker_width))
                    if draw_caps:
                        out["caps"].append(self._stats_line(
                            [loc - cap[i] / 2.0, loc + cap[i] / 2.0], [y1, y1],
                            cap_color, cap_width))
            else:
                med_entry = self._stats_line([med, med], [loc - half, loc + half],
                                             median_color, median_width)
                out["medians"].append(med_entry)
                for x0, x1 in ((q3, hi), (q1, lo)):
                    out["whiskers"].append(self._stats_line(
                        [x0, x1], [loc, loc], whisker_color, whisker_width))
                    if draw_caps:
                        out["caps"].append(self._stats_line(
                            [x1, x1], [loc - cap[i] / 2.0, loc + cap[i] / 2.0],
                            cap_color, cap_width))
            if showmeans:
                if orientation == "vertical":
                    out["means"].append(self._stats_line(
                        [loc - half, loc + half], [mean, mean], mean_color))
                else:
                    out["means"].append(self._stats_line(
                        [mean, mean], [loc - half, loc + half], mean_color))
            if draw_fliers and fliers.size and flier_format != "":
                style = dict(linestyle="none", marker=flier_marker,
                             markersize=flier_size, mfc=flier_face, mec=flier_edge,
                             mew=flier_width)
                if orientation == "vertical":
                    entry = self.plot(np.full(fliers.size, loc), fliers, **style)
                else:
                    entry = self.plot(fliers, np.full(fliers.size, loc), **style)
                out["fliers"].append(entry[0])
            else:
                out["fliers"].append(None)
        if manage_ticks:
            shown = ([str(v) for v in labels] if labels is not None
                     else [f"{v:g}" for v in pos])
            if orientation == "vertical":
                self.set_xticks(pos, labels=shown)
            else:
                self.set_yticks(pos, labels=shown)
        return out

    def bxp(self, bxpstats, positions=None, widths=None, vert=None, orientation=None,
            patch_artist=False, shownotches=False, showmeans=False, showcaps=True,
            showbox=True, showfliers=True, boxprops=None, whiskerprops=None,
            flierprops=None, medianprops=None, meanprops=None, meanline=False,
            manage_ticks=True, zorder=2, **kwargs):
        """Draw precomputed boxplot statistics, as returned by `cbook.boxplot_stats`."""
        stats = list(bxpstats)
        if not stats:
            raise ValueError("bxp needs at least one statistics entry")
        if orientation is None:
            orientation = "vertical" if (vert is None or vert) else "horizontal"
        if orientation not in ("vertical", "horizontal"):
            raise ValueError(f"unsupported orientation: {orientation!r}")
        n = len(stats)
        pos = np.arange(1.0, n + 1.0) if positions is None else _fill(positions, n)
        wid = _fill(0.5 if widths is None else widths, n)
        box_style = dict(boxprops or {})
        median_style = dict(medianprops or {})
        whisker_style = dict(whiskerprops or {})
        flier_style = dict(flierprops or {})
        mean_style = dict(meanprops or {})
        box_color = _single_color(box_style.get("color", box_style.get("c")), _CYCLE[0])
        box_edge = _single_color(box_style.get("edgecolor", box_style.get("ec")), "black")
        median_color = _single_color(median_style.get("color", median_style.get("c")), _CYCLE[1])
        median_width = _number(median_style.get("linewidth", median_style.get("lw")), 1.5)
        whisker_color = _single_color(whisker_style.get("color", whisker_style.get("c")), "black")
        whisker_width = _number(whisker_style.get("linewidth", whisker_style.get("lw")), 1.0)
        mean_color = _single_color(mean_style.get("color", mean_style.get("c")), _CYCLE[2])
        flier_color = _single_color(
            flier_style.get("markerfacecolor", flier_style.get("mfc",
                             flier_style.get("color", flier_style.get("c")))),
            "black")
        flier_marker = str(flier_style.get("marker", "o"))
        out = dict(boxes=[], medians=[], whiskers=[], caps=[], fliers=[], means=[])  # type: ignore[var-annotated]
        for i, stat in enumerate(stats):
            q1, q3, med, lo, hi = _bxp_fields(stat)
            loc, half = float(pos[i]), float(wid[i]) / 2.0
            cap_half = half / 2.0
            if showbox:
                if orientation == "vertical":
                    bars = self.bar([loc], [q3 - q1], width=wid[i], bottom=q1,
                                    color=box_color if patch_artist else "none",
                                    edgecolor=box_edge, label=str(stat.get("label", "")) if i == 0 else "")
                else:
                    bars = self.barh([loc], [q3 - q1], height=wid[i], left=q1,
                                     color=box_color if patch_artist else "none",
                                     edgecolor=box_edge, label=str(stat.get("label", "")) if i == 0 else "")
                out["boxes"].append(bars[0])
            if orientation == "vertical":
                out["medians"].append(self._stats_line(
                    [loc - half, loc + half], [med, med], median_color, median_width))
                for y0, y1 in ((q3, hi), (q1, lo)):
                    out["whiskers"].append(self._stats_line(
                        [loc, loc], [y0, y1], whisker_color, whisker_width))
                    if showcaps:
                        out["caps"].append(self._stats_line(
                            [loc - cap_half, loc + cap_half], [y1, y1],
                            whisker_color, whisker_width))
            else:
                out["medians"].append(self._stats_line(
                    [med, med], [loc - half, loc + half], median_color, median_width))
                for x0, x1 in ((q3, hi), (q1, lo)):
                    out["whiskers"].append(self._stats_line(
                        [x0, x1], [loc, loc], whisker_color, whisker_width))
                    if showcaps:
                        out["caps"].append(self._stats_line(
                            [x1, x1], [loc - cap_half, loc + cap_half],
                            whisker_color, whisker_width))
            if showmeans and stat.get("mean") is not None:
                mean = float(stat["mean"])
                if orientation == "vertical":
                    out["means"].append(self._stats_line(
                        [loc - half, loc + half], [mean, mean], mean_color))
                else:
                    out["means"].append(self._stats_line(
                        [mean, mean], [loc - half, loc + half], mean_color))
            fliers = _as_f64(stat.get("fliers", []))
            if showfliers and fliers.size:
                if orientation == "vertical":
                    self.scatter(np.full(fliers.size, loc), fliers, s=36,
                                 c=flier_color, marker=flier_marker)
                else:
                    self.scatter(fliers, np.full(fliers.size, loc), s=36,
                                 c=flier_color, marker=flier_marker)
                out["fliers"].append(self.scatter_pts[-1])
            else:
                out["fliers"].append(None)
        if manage_ticks:
            labels = [str(stat.get("label", "")) for stat in stats]
            shown = labels if any(labels) else [f"{v:g}" for v in pos]
            if orientation == "vertical":
                self.set_xticks(pos, labels=shown)
            else:
                self.set_yticks(pos, labels=shown)
        return out

    def _stats_line(self, x, y, color, linewidth=1.5, linestyle="-"):
        """Append one statistics line and return its mutable handle."""
        entry = _series(x, y, "", color, linestyle=linestyle, linewidth=linewidth)
        self._append_series(entry)
        return _LineHandle(entry)

    def violinplot(self, dataset, positions=None, vert=None, widths=0.5,
                   showmeans=False, showextrema=True, showmedians=False,
                   quantiles=None, points=100, bw_method=None, orientation=None,
                   side="both", **kwargs):
        """Violin plot: a Gaussian KDE per dataset drawn as a filled violin.

        Returns a dict with `bodies`, `cmeans`, `cmaxes`, `cmins` and `cbars`
        (plus `cquantiles` when `quantiles` is given)."""
        groups = _box_datasets(dataset)
        if not groups:
            raise ValueError("violinplot needs at least one dataset")
        if orientation is None:
            orientation = "vertical" if (vert is None or vert) else "horizontal"
        if orientation not in ("vertical", "horizontal"):
            raise ValueError(f"unsupported orientation: {orientation!r}")
        if side not in ("both", "left", "right", "low", "high"):
            raise ValueError(f"unsupported side: {side!r}")
        n = len(groups)
        pos = np.arange(1.0, n + 1.0) if positions is None else _fill(positions, n)
        wid = _fill(widths, n)
        colors = _colors(kwargs.get("facecolor", kwargs.get("facecolors")))
        if not colors:
            # Matplotlib 3.11 uses one cycle colour for every body in the call,
            # not a new colour per violin.
            colors = [self._next_color()]
        alpha = kwargs.get("alpha")
        body_alpha = 0.3 if alpha is None else float(alpha)
        # Extrema, means, medians and quantiles use the body colour. Bodies are
        # plain translucent fills with no outline, like Matplotlib's
        # fill_between path; an explicit edge colour is the only thing drawn.
        edge = kwargs.get("linecolor", kwargs.get("edgecolor"))
        line_color = _single_color(edge, colors[0])
        out = dict(bodies=[], cmeans=[], cmaxes=[], cmins=[], cbars=[])  # type: ignore[var-annotated]
        if quantiles is not None:
            out["cquantiles"] = []
        per_group_quantiles = None
        if (isinstance(quantiles, (list, tuple)) and len(quantiles) == n and any(
                isinstance(q, (list, tuple, np.ndarray)) for q in quantiles)):
            per_group_quantiles = [
                np.atleast_1d(np.asarray(q, dtype=np.float64)).ravel()
                for q in quantiles
            ]
        for i, raw in enumerate(groups):
            vals = _as_f64(raw)
            vals = vals[np.isfinite(vals)]
            if vals.size == 0:
                raise ValueError("violinplot datasets must not be empty")
            grid, density = _kde(vals, points, bw_method)
            loc, half = float(pos[i]), float(wid[i]) / 2.0
            xs, ys = _violinplot_outline(grid, density, loc, half, orientation, side)
            color = colors[i] if i < len(colors) else colors[0]
            entry = _band(xs, ys, color, body_alpha)
            self._append_band(entry)
            out["bodies"].append(_ViolinBody(entry, color))
            if edge is not None:
                outline = np.append(xs, xs[0])
                outline_y = np.append(ys, ys[0])
                self._stats_line(outline, outline_y, line_color)
            vmin, vmax = float(vals.min()), float(vals.max())
            horizontal = orientation == "horizontal"
            if showextrema:
                out["cmins"].append(self._stats_line(
                    [loc - half, loc + half], [vmin, vmin], line_color)
                    if not horizontal else self._stats_line(
                    [vmin, vmin], [loc - half, loc + half], line_color))
                out["cmaxes"].append(self._stats_line(
                    [loc - half, loc + half], [vmax, vmax], line_color)
                    if not horizontal else self._stats_line(
                    [vmax, vmax], [loc - half, loc + half], line_color))
                out["cbars"].append(self._stats_line(
                    [loc, loc], [vmin, vmax], line_color)
                    if not horizontal else self._stats_line(
                    [vmin, vmax], [loc, loc], line_color))
            if showmeans:
                mean = float(vals.mean())
                out["cmeans"].append(self._stats_line(
                    [loc - half, loc + half], [mean, mean], line_color)
                    if not horizontal else self._stats_line(
                    [mean, mean], [loc - half, loc + half], line_color))
            if showmedians:
                median = float(np.median(vals))
                self._stats_line(
                    [loc - half, loc + half], [median, median], line_color)
            if quantiles is not None:
                q_values = (per_group_quantiles[i] if per_group_quantiles is not None
                            else np.atleast_1d(
                                np.asarray(quantiles, dtype=np.float64)).ravel())
                for q in q_values:
                    value = float(np.percentile(vals, q))
                    out["cquantiles"].append(self._stats_line(
                        [value, value], [loc - half, loc + half], line_color)
                        if horizontal else self._stats_line(
                        [loc - half, loc + half], [value, value], line_color))
        return out

    def violin(self, vpstats, positions=None, vert=None, orientation="vertical",
               widths=0.5, showmeans=False, showextrema=True, showmedians=False,
               side="both", facecolor=None, linecolor=None):
        """Draw violins from pre-computed statistics, as `Axes.violin`.

        Each entry in `vpstats` carries `coords` and `vals` for the density
        outline plus `mean`, `median`, `min`, `max` and optional `quantiles`.
        Returns the same artist dictionary as Matplotlib (`bodies`, `cmeans`,
        `cmaxes`, `cmins`, `cbars`, plus `cmedians`/`cquantiles`)."""
        if vert is not None:
            orientation = "vertical" if vert else "horizontal"
        if orientation not in ("vertical", "horizontal"):
            raise ValueError(f"unsupported orientation: {orientation!r}")
        if side not in ("both", "low", "high"):
            raise ValueError(f"unsupported side: {side!r}")
        stats = list(vpstats)
        pos_num, width_num = _violin_axes(stats, positions, widths)

        facecolors = _colors(facecolor) if facecolor is not None else [self._next_color()]
        body_alpha = None if facecolor is not None else 0.3
        linecolors = _colors(linecolor) if linecolor is not None else list(facecolors)
        line_ends = _violin_line_ends(pos_num, width_num, side)
        horizontal = orientation == "horizontal"

        def number(value):
            if isinstance(value, (np.datetime64, _datetime.datetime, _datetime.date)):
                return float(_datetime_to_num(value))
            return float(value)

        out = {"bodies": []}  # type: ignore[var-annotated]
        if showmeans:
            out["cmeans"] = []
        if showextrema:
            out["cmaxes"], out["cmins"], out["cbars"] = [], [], []
        if showmedians:
            out["cmedians"] = []
        quantile_lines: list[_LineHandle] = []
        for i, stat in enumerate(stats):
            coords = np.asarray(stat["coords"])
            if _looks_like_dates(coords):
                coords = np.atleast_1d(_date_to_num(coords)).astype(float)
            else:
                coords = _as_f64(coords)
            vals = _as_f64(stat["vals"])
            pos = float(pos_num[i])
            color = facecolors[i] if i < len(facecolors) else facecolors[0]
            line_color = linecolors[i] if i < len(linecolors) else linecolors[0]
            if coords.size or vals.size:
                xs, ys = _violin_outline_core(
                    np.atleast_1d(coords), np.atleast_1d(vals), pos,
                    float(width_num[i]), horizontal, side)
                entry = _band(xs, ys, color, body_alpha)
                self._append_band(entry)
                out["bodies"].append(_ViolinBody(entry, color))
            lo_end, hi_end = float(line_ends[0, i]), float(line_ends[1, i])

            def perp(value, lo=lo_end, hi=hi_end, color=line_color):
                if horizontal:
                    return self._stats_line([value, value], [lo, hi], color)
                return self._stats_line([lo, hi], [value, value], color)

            if showmeans:
                out["cmeans"].append(perp(number(stat["mean"])))
            if showextrema:
                out["cmaxes"].append(perp(number(stat["max"])))
                out["cmins"].append(perp(number(stat["min"])))
                minimum, maximum = number(stat["min"]), number(stat["max"])
                out["cbars"].append(
                    self._stats_line([minimum, maximum], [pos, pos], line_color)
                    if horizontal else
                    self._stats_line([pos, pos], [minimum, maximum], line_color))
            if showmedians:
                out["cmedians"].append(perp(number(stat["median"])))
            quantile_lines.extend(perp(number(q)) for q in stat.get("quantiles") or ())
        if quantile_lines:
            out["cquantiles"] = quantile_lines
        return out


def _box_stats(vals, whis, autorange):
    """Quartiles, whisker ends, outliers and mean of one boxplot dataset."""
    q1, med, q3 = (float(v) for v in np.percentile(vals, [25.0, 50.0, 75.0]))
    iqr = q3 - q1
    if autorange:
        lo, hi = float(vals.min()), float(vals.max())
    elif isinstance(whis, (tuple, list)):
        lo = float(np.percentile(vals, float(whis[0])))
        hi = float(np.percentile(vals, float(whis[1])))
    else:
        bound = 1.5 if whis is None else float(whis)
        low_bound, high_bound = q1 - bound * iqr, q3 + bound * iqr
        inside = vals[(vals >= low_bound) & (vals <= high_bound)]
        lo, hi = (float(inside.min()), float(inside.max())) if inside.size else (q1, q3)
    fliers = vals[(vals < lo) | (vals > hi)]
    return q1, med, q3, lo, hi, fliers, float(vals.mean()), iqr


def _bxp_fields(stat):
    """Quartiles and whisker ends from one `cbook.boxplot_stats` entry."""
    q1 = float(stat.get("q1", 0.0))
    q3 = float(stat.get("q3", q1))
    med = float(stat.get("med", 0.5 * (q1 + q3)))
    lo = float(stat.get("whislo", q1))
    hi = float(stat.get("whishi", q3))
    return q1, q3, med, lo, hi


def _box_style(boxprops, medianprops, whiskerprops, capprops, flierprops,
               meanprops, sym):
    """Parsed box, median, whisker, cap, flier and mean styles."""
    box_style = dict(boxprops or {})
    median_style = dict(medianprops or {})
    whisker_style = dict(whiskerprops or {})
    cap_style = dict(capprops or {})
    flier_style = dict(flierprops or {})
    mean_style = dict(meanprops or {})
    box_color = _single_color(box_style.get("color", box_style.get("c")), _CYCLE[0])
    box_edge = _single_color(box_style.get("edgecolor", box_style.get("ec")), "black")
    box_width = _number(box_style.get("linewidth", box_style.get("lw")), 1.0)
    median_color = _single_color(median_style.get("color", median_style.get("c")), _CYCLE[1])
    median_width = _number(median_style.get("linewidth", median_style.get("lw")), 1.5)
    whisker_color = _single_color(whisker_style.get("color", whisker_style.get("c")), "black")
    whisker_width = _number(whisker_style.get("linewidth", whisker_style.get("lw")), 1.0)
    cap_color = _single_color(cap_style.get("color", cap_style.get("c")), "black")
    cap_width = _number(cap_style.get("linewidth", cap_style.get("lw")), 1.0)
    mean_color = _single_color(mean_style.get("color", mean_style.get("c")), _CYCLE[2])
    # `sym=None` means matplotlib's default flier (`o`); only an explicit
    # empty string (`sym=""`) hides the outliers.
    flier_format = "o" if sym is None else str(sym)
    parsed_color, _, parsed_marker = _stem_fmt(flier_format, None)
    flier_edge = _single_color(
        flier_style.get("markeredgecolor", flier_style.get("mec",
                         flier_style.get("color", flier_style.get("c")))),
        parsed_color or "black")
    flier_face = _single_color(
        flier_style.get("markerfacecolor", flier_style.get("mfc")),
        parsed_color or "none")
    flier_marker = str(flier_style.get("marker", parsed_marker or "o"))
    flier_width = _number(
        flier_style.get("markeredgewidth", flier_style.get("mew")), 1.0)
    flier_size = _number(flier_style.get("markersize", flier_style.get("ms")), 8.0)
    return (box_color, box_edge, box_width, box_style.get("alpha"), median_color,
            median_width, whisker_color, whisker_width, cap_color, cap_width,
            mean_color, flier_format, flier_marker, flier_face, flier_edge,
            flier_width, flier_size)


def _violin_axes(stats, positions, widths):
    """Validated numeric `(positions, widths)` of one `Axes.violin` call."""
    n = len(stats)
    message = "List of violinplot statistics and `%s` values must have the same length"
    if positions is None:
        positions = list(range(1, n + 1))
    elif len(positions) != n:
        raise ValueError(message % "positions")
    if np.isscalar(widths):
        widths = [widths] * n
    elif len(widths) != n:
        raise ValueError(message % "widths")
    if n:
        pos0, width0 = positions[0], widths[0]
        if isinstance(pos0, np.datetime64):
            if not isinstance(width0, np.timedelta64):
                raise TypeError(
                    "np.datetime64 'position' values require np.timedelta64 'widths'")
        elif (isinstance(pos0, (_datetime.datetime, _datetime.date))
              and not isinstance(width0, _datetime.timedelta)):
            raise TypeError(
                "datetime/date 'position' values require timedelta 'widths'")
    if n and isinstance(positions[0], (np.datetime64, _datetime.datetime,
                                       _datetime.date)):
        pos_num = np.atleast_1d(_date_to_num(positions)).astype(float)
        width_num = np.asarray([
            (w / np.timedelta64(1, "D"))
            if isinstance(w, np.timedelta64) else w.total_seconds() / 86400.0
            for w in widths], dtype=float)
    else:
        pos_num = np.asarray(positions, dtype=float)
        width_num = np.asarray(widths, dtype=float)
    return pos_num, width_num


def _violin_line_ends(pos_num, width_num, side):
    """Start and end of the extrema lines drawn across each violin."""
    return np.array([[-0.25 if side in ("both", "low") else 0.0],
                     [0.25 if side in ("both", "high") else 0.0]]) \
        * width_num + pos_num


def _violinplot_outline(grid, density, pos, half, orientation, side):
    """`(x, y)` outline of one KDE violin, scaled to `half` its width."""
    peak = float(density.max())
    if not np.isfinite(peak) or peak <= 0.0:
        peak = 1.0
    scale = half / peak
    if orientation == "vertical":
        if side == "both":
            xs = np.concatenate([pos + density * scale,
                                 (pos - density * scale)[::-1]])
            ys = np.concatenate([grid, grid[::-1]])
        else:
            sign = -1.0 if side in ("left", "low") else 1.0
            xs = np.concatenate([[pos], pos + sign * density * scale, [pos]])
            ys = np.concatenate([[grid[0]], grid, [grid[-1]]])
    else:
        if side == "both":
            ys = np.concatenate([pos + density * scale,
                                 (pos - density * scale)[::-1]])
            xs = np.concatenate([grid, grid[::-1]])
        else:
            sign = -1.0 if side in ("left", "low") else 1.0
            ys = np.concatenate([[pos], pos + sign * density * scale, [pos]])
            xs = np.concatenate([[grid[0]], grid, [grid[-1]]])
    return xs, ys


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._plot_helpers import (
        _as_f64,
        _band,
        _box_datasets,
        _colors,
        _fill,
        _kde,
        _series,
        _stem_fmt,
    )
