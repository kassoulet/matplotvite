"""Axes mixin for lines, bars, fills and categorical plots."""
from typing import TYPE_CHECKING, Any

import numpy as np

from ._artists import Line2D, _GroupedBarResult, _spectral_estimates
from ._containers import (
    _BarContainer,
    _BarHandle,
    _LineGroupHandle,
    _LineHandle,
    _PieResult,
    _ScatterHandle,
    _StemContainer,
    _Wedge,
)
from ._helpers import (
    _BAR_KWARGS,
    _CYCLE,
    _FMT_COLORS,
    _HIST_KWARGS,
    _LINE2D_KWARGS,
    _SCATTER_KWARGS,
    _as_list,
    _check_kwargs,
    _cmap_name,
    _looks_like_categories,
    _TextLabel,
    _validate_bins,
    _validate_linestyle,
)

_AXES_ARTIST_PROPS = frozenset(
    ["agg_filter", "alpha", "animated", "clip_box", "clip_on", "clip_path", "gid", "in_layout", "label", "path_effects", "picker", "rasterized", "sketch_params", "snap", "url", "visible", "zorder"]
)


class _AxesMixinBase:
    """The `Axes` surface the plotting mixins share.

    The state below is created by `Axes.__init__` and updated by the plot
    families; the methods are implemented by `Axes` or by one of the mixins.
    Declaring them here gives the mixins a real contract instead of a blanket
    `__getattr__` that made every member `Any`.
    """

    # Artist and label state filled in by `Axes.__init__` and the plot calls.
    annotations: list[Any]
    arrows: list[Any]
    bars: list[Any]
    contours: list[Any]
    errors: list[Any]
    hspans: list[Any]
    images: list[Any]
    lines: list[Any]
    scatter_pts: list[Any]
    texts: list[Any]
    vspans: list[Any]
    _axlines: list[Any]
    _hline_refs: list[Any]
    _vline_refs: list[Any]
    legend_labels: list[Any]
    # Axis, grid and legend configuration.
    _inverted: list[bool]
    _sticky_x: list[Any]
    _sticky_y: list[Any]
    _yside: str
    grid_axis: str
    grid_minor_show: bool
    show_grid: bool
    show_legend: bool
    tick_params_box: dict[str, Any]
    ylim: Any
    legend_anchor: Any
    legend_family: Any
    legend_fontsize: Any
    legend_frameon: Any
    legend_loc: Any
    legend_ncol: Any
    legend_title: Any
    legend_title_fontsize: Any
    title: Any
    title_family: Any
    title_size: Any
    xaxis: Any
    xlabel: Any
    xlabel_color: Any
    xlabel_family: Any
    xlabel_size: Any
    yaxis: Any
    ylabel: Any
    ylabel_color: Any
    ylabel_family: Any
    ylabel_size: Any

    # Plot families the mixins call on each other.
    def plot(self, *args: Any, **kwargs: Any) -> Any: ...
    def bar(self, *args: Any, **kwargs: Any) -> Any: ...
    def barh(self, *args: Any, **kwargs: Any) -> Any: ...
    def hist(self, *args: Any, **kwargs: Any) -> Any: ...
    def step(self, *args: Any, **kwargs: Any) -> Any: ...
    def hlines(self, *args: Any, **kwargs: Any) -> Any: ...
    def vlines(self, *args: Any, **kwargs: Any) -> Any: ...
    def axhline(self, *args: Any, **kwargs: Any) -> Any: ...
    def fill_between(self, *args: Any, **kwargs: Any) -> Any: ...
    def fill_betweenx(self, *args: Any, **kwargs: Any) -> Any: ...
    def text(self, *args: Any, **kwargs: Any) -> Any: ...
    def imshow(self, *args: Any, **kwargs: Any) -> Any: ...
    def pcolormesh(self, *args: Any, **kwargs: Any) -> Any: ...
    def contour(self, *args: Any, **kwargs: Any) -> Any: ...
    def contourf(self, *args: Any, **kwargs: Any) -> Any: ...
    def triplot(self, *args: Any, **kwargs: Any) -> Any: ...
    def quiver(self, *args: Any, **kwargs: Any) -> Any: ...
    def scatter(self, *args: Any, **kwargs: Any) -> Any: ...
    def add_patch(self, *args: Any, **kwargs: Any) -> Any: ...
    def add_collection(self, *args: Any, **kwargs: Any) -> Any: ...
    def set_aspect(self, *args: Any, **kwargs: Any) -> Any: ...
    def set_axis_off(self, *args: Any, **kwargs: Any) -> Any: ...
    def set_xlim(self, *args: Any, **kwargs: Any) -> Any: ...
    def set_ylim(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_xlim(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_ylim(self, *args: Any, **kwargs: Any) -> Any: ...
    def set_xticks(self, *args: Any, **kwargs: Any) -> Any: ...
    def set_yticks(self, *args: Any, **kwargs: Any) -> Any: ...
    # Private plumbing shared by the mixins.
    def _next_color(self, patch: bool = False) -> Any: ...
    # Projection subclasses (polar, 3D, geographic) provide these.
    def _polar_xy(self, *args: Any, **kwargs: Any) -> Any: ...
    def _polar_segments(self, *args: Any, **kwargs: Any) -> Any: ...
    def _polar_grid(self, *args: Any, **kwargs: Any) -> Any: ...
    def _xdate(self, *args: Any, **kwargs: Any) -> Any: ...
    def _ydate(self, *args: Any, **kwargs: Any) -> Any: ...
    def _append_series(self, *args: Any, **kwargs: Any) -> Any: ...
    def _append_band(self, *args: Any, **kwargs: Any) -> Any: ...
    def _append_bar(self, *args: Any, **kwargs: Any) -> Any: ...
    def _append_scatter(self, *args: Any, **kwargs: Any) -> Any: ...
    def _add_contour(self, *args: Any, **kwargs: Any) -> Any: ...
    def _category_positions(self, *args: Any, **kwargs: Any) -> Any: ...
    def _size_or(self, *args: Any, **kwargs: Any) -> Any: ...
    def _stats_line(self, *args: Any, **kwargs: Any) -> Any: ...
    def _tick_style(self, *args: Any, **kwargs: Any) -> Any: ...


class _PlotAxes(_AxesMixinBase):
    """Plot families: lines, points, bars, fills and categorical plots."""

    def plot(self, *args, label="", color=None, c=None, linestyle=None, ls=None,
             linewidth=None, lw=None, marker=None, markersize=None, ms=None,
             markerfacecolor=None, mfc=None, markeredgecolor=None, mec=None,
             markeredgewidth=None, mew=None, alpha=None, drawstyle="default", fmt=None,
             data=None, x=None, y=None, **kwargs):
        """Line plot with matplotlib's styling keywords (`lw`, `ls`, `marker`, `ms`,
        `mfc`/`mec`, `alpha`, `drawstyle`) and fmt-string shorthand (`"r--o"`).
        `data=` accepts a DataFrame/Series and `x=`/`y=` may name its columns."""
        args = _resolve_data_args(args, data, x, y)
        gid = str(kwargs.pop("gid", "") or "")
        xunits = kwargs.pop("xunits", None)
        yunits = kwargs.pop("yunits", None)
        _check_kwargs(kwargs, "plot", _LINE2D_KWARGS)
        if drawstyle is None:
            drawstyle = "default"
        if drawstyle == "steps":
            drawstyle = "steps-pre"
        if drawstyle not in ("default", "steps-pre", "steps-mid", "steps-post"):
            raise ValueError(f"unsupported drawstyle: {drawstyle!r}")
        handles = []
        for index, (gx, gy, gfmt) in enumerate(_plot_args(args, fmt)):
            if gx is None:
                gx = np.arange(np.asarray(gy).size)
            elif gy is None:
                gx, gy = np.arange(np.asarray(gx).size), gx
            gfmt = gfmt or (fmt if index == 0 else None)
            if not label and getattr(gy, "name", None) is not None:
                glabel = str(gy.name)
            else:
                glabel = label if index == 0 else ""
            style = linestyle if linestyle is not None else (ls if ls is not None else "-")
            gcolor = color if color is not None else c
            gmarker = marker
            if gfmt:
                f_color, f_style, f_marker = _parse_fmt(gfmt)
                gcolor = gcolor if gcolor is not None else f_color
                if linestyle is None and ls is None:
                    style = f_style or style
                if not gmarker:
                    gmarker = f_marker
            style = _validate_linestyle(style)
            line_color = self._next_color() if gcolor is None else gcolor
            edge = markeredgecolor if markeredgecolor is not None else mec
            gx = _convert_units(gx, self.xaxis, xunits)
            gy = _convert_units(gy, self.yaxis, yunits)
            xvals = self._xdate(gx)
            gy = self._ydate(gy)
            xshape, yshape = np.asarray(xvals).shape, np.asarray(gy).shape
            if xshape != yshape:
                raise ValueError(
                    "x and y must have same first dimension, but have shapes "
                    f"{xshape} and {yshape}")
            series_style = drawstyle
            if drawstyle == "steps-mid":
                xvals, gy = _mid_steps(xvals, gy)
                series_style = "steps-post"
            handle = _series(
                xvals, gy, glabel, line_color, linestyle=style,
                linewidth=linewidth if linewidth is not None else (lw if lw is not None else rcParams.get("lines.linewidth", 2.0)),
                marker=gmarker or "",
                markersize=markersize if markersize is not None else (ms if ms is not None else rcParams.get("lines.markersize", 6.0)),
                mfc=(markerfacecolor if markerfacecolor is not None else mfc), mec=edge,
                mew=markeredgewidth if markeredgewidth is not None else (mew if mew is not None else rcParams.get("lines.markerlinewidth", 1.0)),
                alpha=alpha, drawstyle=series_style, gid=gid)
            self._append_series(handle)
            handles.append(Line2D(handle))
        return handles

    def specgram(self, x, NFFT=256, Fs=2, Fc=0, detrend=None, window=None,
                 noverlap=None, cmap=None, xextent=None, pad_to=None, sides=None,
                 scale_by_freq=None, mode=None, scale=None, vmin=None, vmax=None,
                 **kwargs):
        """Windowed FFT magnitude, drawn as an image; returns (Pxx, freqs, bins, image)."""
        data = _as_f64(x)
        fs = 2.0 if Fs is None else float(Fs)
        nfft = max(int(NFFT), 2)
        step = nfft - (nfft // 2 if noverlap is None else int(noverlap))
        if step <= 0:
            raise ValueError("noverlap must be smaller than NFFT")
        if data.size < nfft:
            raise ValueError("specgram needs at least NFFT samples")
        taper = np.hanning(nfft) if window is None or window is np.hanning else np.asarray(window)
        frames = np.stack([data[i:i + nfft] * taper
                           for i in range(0, data.size - nfft + 1, step)])
        spectrum = np.abs(np.fft.rfft(frames, n=nfft, axis=1)) ** 2
        pxx = spectrum.T / max(fs, 1e-12)
        freqs = np.fft.rfftfreq(nfft, d=1.0 / fs) + float(Fc)
        bins = np.arange(frames.shape[0]) * step / fs
        decibels = 10.0 * np.log10(np.maximum(pxx, 1e-20))
        image = self.imshow(decibels, aspect="auto", origin="lower", cmap=cmap,
                            vmin=vmin, vmax=vmax,
                            extent=(float(bins[0]), float(bins[-1]),
                                    float(freqs[0]), float(freqs[-1])), **kwargs)
        return pxx, freqs, bins, image

    def psd(self, x, NFFT=256, Fs=2, Fc=0, detrend=None, window=None,
            noverlap=None, pad_to=None, sides="default", scale_by_freq=None,
            return_line=False, **kwargs):
        """Plot a one-sided power spectral density estimate."""
        pxx, freqs = _spectral_estimates(
            x, NFFT=NFFT, Fs=Fs, Fc=Fc, window=window, noverlap=noverlap,
            pad_to=pad_to)
        line = self.plot(freqs, 10.0 * np.log10(np.maximum(pxx, 1e-20)), **kwargs)
        return (line if return_line else (pxx, freqs))

    def csd(self, x, y, NFFT=256, Fs=2, Fc=0, detrend=None, window=None,
            noverlap=None, pad_to=None, sides="default", scale_by_freq=None,
            return_line=False, **kwargs):
        """Plot the cross spectral density of two signals."""
        _, _, pxy, freqs = _spectral_estimates(
            x, y, NFFT=NFFT, Fs=Fs, Fc=Fc, window=window, noverlap=noverlap,
            pad_to=pad_to)
        line = self.plot(freqs, 10.0 * np.log10(np.maximum(np.abs(pxy), 1e-20)),
                         **kwargs)
        return (line if return_line else (pxy, freqs))

    def cohere(self, x, y, NFFT=256, Fs=2, Fc=0, detrend=None, window=None,
               noverlap=None, pad_to=None, sides="default", scale_by_freq=None,
               **kwargs):
        """Plot the magnitude-squared coherence of two signals."""
        pxx, pyy, pxy, freqs = _spectral_estimates(
            x, y, NFFT=NFFT, Fs=Fs, Fc=Fc, window=window, noverlap=noverlap,
            pad_to=pad_to)
        coh = np.clip(np.abs(pxy) ** 2 / np.maximum(pxx * pyy, 1e-20), 0.0, 1.0)
        self.plot(freqs, coh, **kwargs)
        return coh, freqs

    def magnitude_spectrum(self, x, Fs=2, Fc=0, window=None, pad_to=None,
                           sides="default", scale="linear", **kwargs):
        """Plot the single-sided magnitude spectrum of a signal."""
        pxx, freqs = _spectral_estimates(
            x, NFFT=min(max(len(np.asarray(x).ravel()), 2), 256), Fs=Fs, Fc=Fc,
            window=window, pad_to=pad_to)
        magnitude = np.sqrt(pxx)
        if scale == "dB":
            magnitude = 20.0 * np.log10(np.maximum(magnitude, 1e-20))
        line = self.plot(freqs, magnitude, **kwargs)
        return magnitude, freqs, line[0]

    def angle_spectrum(self, x, Fs=2, Fc=0, window=None, pad_to=None,
                       sides="default", **kwargs):
        """Plot the wrapped phase spectrum of a signal."""
        x = _as_f64(x)
        taper = np.ones(x.size) if window is None else np.asarray(window(np.ones(x.size)))
        spectrum = np.fft.rfft(x * taper, n=max(int(pad_to or x.size), x.size))
        freqs = np.fft.rfftfreq(spectrum.size * 2 - 1, d=1.0 / float(Fs)) + float(Fc)
        angle = np.angle(spectrum)
        line = self.plot(freqs[:angle.size], angle, **kwargs)
        return angle, freqs[:angle.size], line[0]

    def phase_spectrum(self, x, Fs=2, Fc=0, window=None, pad_to=None,
                       sides="default", **kwargs):
        """Plot the unwrapped phase spectrum of a signal."""
        x = _as_f64(x)
        taper = np.ones(x.size) if window is None else np.asarray(window(np.ones(x.size)))
        spectrum = np.fft.rfft(x * taper, n=max(int(pad_to or x.size), x.size))
        freqs = np.fft.rfftfreq(spectrum.size * 2 - 1, d=1.0 / float(Fs)) + float(Fc)
        phase = np.unwrap(np.angle(spectrum))
        line = self.plot(freqs[:phase.size], phase, **kwargs)
        return phase, freqs[:phase.size], line[0]

    def xcorr(self, x, y, normed=False, maxlags=10, usevlines=True, **kwargs):
        """Plot the cross-correlation of two signals."""
        x = _as_f64(x)
        y = _as_f64(y)
        _check_same_length(x, y)
        maxlags = x.size - 1 if maxlags is None else max(int(maxlags), 0)
        corr = np.correlate(x, y, mode="full")[x.size - 1 - maxlags:
                                                x.size + maxlags]
        if normed:
            corr = corr / max(np.sqrt(np.sum(x ** 2) * np.sum(y ** 2)), 1e-20)
        lags = np.arange(-maxlags, maxlags + 1)
        line = self.vlines(lags, 0, corr, **kwargs) if usevlines else self.plot(
            lags, corr, **kwargs)
        if usevlines:
            self.axhline(0, color="black", linewidth=0.8)
        return lags, corr, line, None

    def acorr(self, x, normed=False, maxlags=10, usevlines=True, **kwargs):
        """Plot the autocorrelation of a signal."""
        return self.xcorr(x, x, normed=normed, maxlags=maxlags,
                          usevlines=usevlines, **kwargs)

    def ecdf(self, x, weights=None, complementary=False, orientation="vertical",
             **kwargs):
        """Plot the empirical cumulative distribution function of a sample."""
        x = np.sort(_as_f64(x))
        if weights is None:
            y = np.arange(1, x.size + 1) / max(x.size, 1)
        else:
            w = _as_f64(weights)
            if w.size != x.size:
                raise ValueError("weights must match the sample size")
            y = np.cumsum(w) / max(w.sum(), 1e-20)
        if complementary:
            y = 1.0 - y
        if orientation == "horizontal":
            line = self.step(y, x, where="post", **kwargs)
        else:
            line = self.step(x, y, where="post", **kwargs)
        return x, y, line

    def barbs(self, *args, **kwargs):
        pivot = kwargs.get("pivot")
        if isinstance(pivot, (int, float, np.number)):
            kwargs["pivot"] = "middle"
        return self.quiver(*args, **kwargs)

    def hist(self, x, bins=10, range=None, density=False, weights=None, cumulative=False,
             bottom=None, histtype="bar", align="mid", orientation="vertical", color=None,
             label=None, alpha=None, edgecolor=None, stacked=False, data=None, **kwargs):
        """Histogram of `x`, drawn as bars; returns `(counts, edges, handles)`."""
        _check_kwargs(kwargs, "hist", _HIST_KWARGS)
        if histtype == "barstacked":
            histtype, stacked = "bar", True
        if histtype not in ("bar", "step", "stepfilled"):
            raise ValueError(
                f"{histtype!r} is not a valid value for histtype. "
                "Supported values are 'bar', 'barstacked', 'step', 'stepfilled'")

        if data is not None and isinstance(x, str):
            x = data[x]
        bins = _validate_bins(bins)
        datasets = None
        if isinstance(x, (list, tuple)) and x:
            try:
                candidate = np.asarray(x, dtype=np.float64)
                if candidate.ndim == 2:
                    datasets = list(candidate)
                elif candidate.ndim == 1:
                    datasets = [candidate]
            except (TypeError, ValueError):
                # Ragged sample sizes are the usual multi-histogram input.
                datasets = [_as_f64(item) for item in x]
        elif isinstance(x, np.ndarray) and x.ndim == 2:
            datasets = list(x)
        if datasets is not None and len(datasets) > 1 and not stacked:
            # Overlaid histograms: one pass per data set, as Matplotlib draws them.
            counts_list, handles = [], []
            edges = None
            for i, dataset in enumerate(datasets):
                colour = (color[i] if isinstance(color, (list, tuple)) and i < len(color)
                          else color)
                label_i = (label[i] if isinstance(label, (list, tuple)) and i < len(label)
                           else label)
                counts, edges, handle = self.hist(
                    dataset, bins=bins, range=range, density=density, weights=weights,
                    cumulative=cumulative, bottom=bottom, histtype=histtype, align=align,
                    orientation=orientation, color=colour, label=label_i, alpha=alpha,
                    edgecolor=edgecolor, **kwargs)
                counts_list.append(counts)
                handles.append(handle)
            return counts_list, edges, handles
        if datasets is not None and len(datasets) > 1 and stacked:
            edges = np.histogram_bin_edges(np.concatenate(datasets), bins=bins, range=range)
            counts_list = []
            for dataset in datasets:
                count, _ = np.histogram(dataset, bins=edges, density=bool(density))
                if cumulative:
                    count = np.cumsum(count)
                counts_list.append(np.asarray(count, dtype=np.float64))
            widths = np.diff(edges)
            bar_align = "edge" if align in ("left", "edge") else "center"
            centers = edges[:-1] if bar_align == "edge" else (edges[:-1] + edges[1:]) / 2.0
            handles = []
            running = np.zeros(counts_list[0].size)
            for i, count in enumerate(counts_list):
                colour = (color[i] if isinstance(color, (list, tuple)) and i < len(color)
                          else color)
                label_i = (label[i] if isinstance(label, (list, tuple)) and i < len(label)
                           else label)
                text = "" if label_i is None else str(label_i)
                if histtype == "bar":
                    if orientation == "horizontal":
                        raise NotImplementedError("stacked hist bars need orientation='vertical'")
                    handles.append(self.bar(centers, count, width=widths, bottom=running,
                                            align=bar_align, color=colour,
                                            edgecolor=edgecolor, alpha=alpha, label=text, _hist=True))
                elif orientation != "vertical":
                    raise NotImplementedError("stacked hist steps need orientation='vertical'")
                else:
                    sx = np.empty(2 * count.size)
                    sx[0::2], sx[1::2] = edges[:-1], edges[1:]
                    if histtype == "stepfilled":
                        self.fill_between(sx, np.repeat(running, 2),
                                          np.repeat(running + count, 2),
                                          color=colour, alpha=alpha)
                    handles.append(self.plot(sx, np.repeat(running + count, 2),
                                             color=colour, label=text)[0])
                running = running + count
            return counts_list, edges, handles
        data = (datasets[0] if datasets is not None and len(datasets) == 1
                else _as_f64(x))
        counts, edges = np.histogram(data, bins=bins, range=range, weights=weights,
                                     density=bool(density))
        if cumulative:
            counts = np.cumsum(counts)
        widths = np.diff(edges)
        base = np.zeros(counts.size) if bottom is None else _fill(bottom, counts.size)
        bar_align = "edge" if align in ("left", "edge") else "center"
        if bar_align == "edge":
            centers = edges[:-1]
        else:
            centers = (edges[:-1] + edges[1:]) / 2.0
        lab = "" if label is None else str(label)
        if histtype == "bar":
            if orientation == "horizontal":
                handles = self.barh(centers, counts, height=widths, left=base,
                                    align=bar_align, color=color, edgecolor=edgecolor,
                                    alpha=alpha, label=lab, _hist=True)
            elif orientation == "vertical":
                handles = self.bar(centers, counts, width=widths, bottom=base,
                                   align=bar_align, color=color, edgecolor=edgecolor,
                                   alpha=alpha, label=lab, _hist=True)
            else:
                raise ValueError(f"unsupported orientation: {orientation!r}")
            return np.asarray(counts, dtype=np.float64), edges, handles
        if orientation == "horizontal":
            sx = np.repeat(counts, 2)
            sy = np.empty(2 * counts.size)
            sy[0::2], sy[1::2] = edges[:-1], edges[1:]
            if histtype == "stepfilled":
                self.fill_betweenx(sy, np.repeat(base, 2), sx,
                                   color=color, alpha=alpha)
            handles = self.plot(sx, sy, color=color, label=lab)
            return np.asarray(counts, dtype=np.float64), edges, handles
        if orientation != "vertical":
            raise ValueError(f"unsupported orientation: {orientation!r}")
        sx = np.empty(2 * counts.size)
        sy = np.empty(2 * counts.size)
        sx[0::2], sx[1::2] = edges[:-1], edges[1:]
        sy[0::2], sy[1::2] = counts, counts
        if histtype == "stepfilled":
            self.fill_between(sx, sy, np.repeat(base, 2), color=color, alpha=alpha)
        handles = self.plot(sx, sy, color=color, label=lab)
        return np.asarray(counts, dtype=np.float64), edges, handles

    def bar(self, x, height, width=0.8, bottom=0.0, color=None, edgecolor=None, label="",
            align="center", alpha=None, linewidth=None, yerr=None, **kwargs):
        """Vertical bars; `color` may be a single colour or one per bar."""
        hist = kwargs.pop("_hist", False)
        _check_kwargs(kwargs, "bar", _BAR_KWARGS)
        x = _as_f64(self._xdate(x))
        n = x.size
        h, w, b = _fill(height, n), _fill(width, n), _fill(bottom, n)
        if align not in ("center", "edge"):
            raise ValueError(f"unsupported align: {align!r}")
        left = x - w / 2.0 if align == "center" else x
        # Matplotlib pins each bar's baseline so autoscaling keeps it on the axis.
        self._sticky_y += [float(v) for v in np.asarray(b).ravel()]
        colors = _bar_colors(color if color is not None else self._next_color(patch=True), n)
        self._append_bar(dict(
            left=np.ascontiguousarray(left), bottom=b, width=w, height=h,
            colors=colors,
            edgecolor=(_bar_colors(edgecolor, n) if edgecolor is not None else None),
            alpha=None if alpha is None else float(alpha), label=str(label),
            vertical=True), container=not hist)
        if yerr is not None:
            lo, hi = _err_pair(yerr, n, "yerr")
            ecolor = edgecolor or (colors[0] if colors else "#1f77b4")
            self.errors.append((np.ascontiguousarray(left + w / 2.0),
                                np.ascontiguousarray(b + h), lo, hi,
                                np.zeros(n), np.zeros(n), str(ecolor), 0.0))
        return _BarContainer([_BarHandle(self, len(self.bars) - 1, i) for i in range(n)],
                             str(label))

    def bar_label(self, container, labels=None, fmt="%g", label_type="edge", padding=0,
                  **kwargs):
        """Annotate each bar with its length, at the bar end or centred."""
        if label_type not in ("edge", "center"):
            raise ValueError(f"unsupported label_type: {label_type!r}")
        handles = list(container) if isinstance(container, (list, tuple)) else [container]
        texts = None if labels is None else [str(v) for v in np.asarray(labels, dtype=object).ravel()]
        if texts is not None and len(texts) != len(handles):
            raise ValueError("labels must have one entry per bar")
        out = []
        for i, handle in enumerate(handles):
            group = self.bars[handle._group]
            index = handle._index
            if group.get("vertical", True):
                length = float(group["height"][index])
                x = float(group["left"][index] + group["width"][index] / 2.0)
                anchor = float(group["bottom"][index])
                if label_type == "edge":
                    y, va, shift = anchor + length, "bottom", (0.0, float(padding))
                else:
                    y, va, shift = anchor + length / 2.0, "center", (0.0, 0.0)
                ha = "center"
            else:
                length = float(group["width"][index])
                y = float(group["bottom"][index] + group["height"][index] / 2.0)
                anchor = float(group["left"][index])
                if label_type == "edge":
                    x, ha, shift = anchor + length, "left", (float(padding), 0.0)
                else:
                    x, ha, shift = anchor + length / 2.0, "center", (0.0, 0.0)
                va = "center"
            if texts is not None:
                text = texts[i]
            elif callable(fmt):
                text = str(fmt(length))
            elif "%" in str(fmt):
                text = str(fmt) % length
            else:
                text = str(fmt).format(length)
            self.text(x, y, text, color=kwargs.get("color", "black"),
                      fontsize=kwargs.get("fontsize", 10), ha=ha, va=va,
                      offset=shift)
            out.append(text)
        return out

    def barh(self, y, width, height=0.8, left=0.0, color=None, edgecolor=None, label="",
             align="center", alpha=None, linewidth=None, **kwargs):
        """Horizontal bars, stored as the same rectangles as `bar`."""
        hist = kwargs.pop("_hist", False)
        _check_kwargs(kwargs, "barh", _BAR_KWARGS)
        y = (self._category_positions(y) if _looks_like_categories(y)
             else _as_f64(y))
        n = y.size
        w, h, l = _fill(width, n), _fill(height, n), _fill(left, n)
        if align not in ("center", "edge"):
            raise ValueError(f"unsupported align: {align!r}")
        bottom = y - h / 2.0 if align == "center" else y
        self._sticky_x += [float(v) for v in np.asarray(l).ravel()]
        self._append_bar(dict(
            left=l, bottom=np.ascontiguousarray(bottom), width=w, height=h,
            colors=_bar_colors(color if color is not None else self._next_color(patch=True), n),
            edgecolor=(_bar_colors(edgecolor, n) if edgecolor is not None else None),
            alpha=None if alpha is None else float(alpha), label=str(label),
            vertical=False), container=not hist)
        return _BarContainer([_BarHandle(self, len(self.bars) - 1, i) for i in range(n)],
                             str(label))

    def grouped_bar(self, data, tick_labels=None, labels=None, bottom=None,
                    group_spacing=None, colors=None, edgecolor=None, **kwargs):
        """Side-by-side bars for several series, one `BarContainer` per series."""
        if isinstance(data, dict):
            series = [str(v) for v in (labels if labels is not None else data.keys())]
            values = np.asarray(list(data.values()), dtype=np.float64).T
        else:
            values = np.asarray(data, dtype=np.float64)
            series = [str(v) for v in (labels or [])]
        if values.ndim != 2:
            raise ValueError("grouped_bar expects a mapping or a 2-D array")
        n, m = values.shape
        if len(series) != m:
            series = [f"series {i + 1}" for i in range(m)]
        bar_width = 0.8 / m
        gap = 0.0 if group_spacing is None else float(group_spacing) * bar_width
        centers = np.arange(n, dtype=np.float64) * (m * bar_width + gap)
        palette = _colors(colors) if colors is not None else []
        containers = []
        for i in range(m):
            colour = palette[i % len(palette)] if palette else self._next_color()
            containers.append(self.bar(
                centers + (i - (m - 1) / 2.0) * bar_width, values[:, i],
                width=bar_width, bottom=0.0 if bottom is None else bottom,
                color=colour, edgecolor=edgecolor, label=series[i], **kwargs))
        if tick_labels is not None:
            self.set_xticks(centers, labels=list(tick_labels))
        return _GroupedBarResult(containers)

    def fill_between(self, x, y1, y2=0.0, where=None, interpolate=False, color=None,
                     alpha=None, label="", step=None, **kwargs):
        """Fill between two curves; `where` masks split the area into runs."""
        x = _as_f64(self._xdate(x))
        a, b = _fill(y1, x.size), _fill(y2, x.size)
        c = color if color is not None else self._next_color(patch=True)
        for xs, ya, yb in _runs(x, a, b, where):
            self._append_band(_band(np.concatenate([xs, xs[::-1]]),
                                    np.concatenate([ya, yb[::-1]]), c, alpha, label))

    def fill_betweenx(self, y, x1, x2=0.0, where=None, color=None, alpha=None, label="",
                      **kwargs):
        y = _as_f64(y)
        a, b = _fill(self._xdate(x1), y.size), _fill(self._xdate(x2), y.size)
        c = color if color is not None else self._next_color(patch=True)
        for ys, xa, xb in _runs(y, a, b, where):
            self._append_band(_band(np.concatenate([xa, xb[::-1]]),
                                    np.concatenate([ys, ys[::-1]]), c, alpha, label))

    def fill(self, *args, color=None, alpha=None, label="", **kwargs):
        """Filled polygons: every `x, y` pair is one polygon, optionally
        followed by its own colour, as in Matplotlib (`fill(x, y, x2, y2)`
        draws two polygons, not one polygon through both)."""
        groups, pair = [], []  # type: ignore[var-annotated]
        for arg in args:
            if isinstance(arg, str):
                if not groups or groups[-1][1] is not None:
                    raise TypeError("fill expects x, y pairs, optionally followed by a colour")
                groups[-1] = (groups[-1][0], arg)  # type: ignore[assignment]
                continue
            pair.append(arg)
            if len(pair) == 2:
                groups.append((pair, None))
                pair = []
        if pair:
            raise TypeError("fill expects x, y pairs, optionally followed by a colour")
        for (x, y), spec in groups:
            c = spec or color or self._next_color(patch=True)
            self._append_band(_band(_as_f64(self._xdate(x)), _as_f64(y), c, alpha, label))

    def axhline(self, y=0.0, xmin=0.0, xmax=1.0, color=None, linestyle=None, linewidth=None,
                alpha=None, label="", **kwargs):
        """Horizontal line at data `y`, spanning an axes-fraction x range."""
        y = _as_f64(y)[0]
        self._hline_refs.append(dict(y=float(y), xmin=float(xmin), xmax=float(xmax), color=color,
                                linestyle=linestyle, linewidth=linewidth, alpha=alpha,
                                label=str(label)))

    def axvline(self, x=0.0, ymin=0.0, ymax=1.0, color=None, linestyle=None, linewidth=None,
                alpha=None, label="", **kwargs):
        """Vertical line at data `x`, spanning an axes-fraction y range."""
        x = _as_f64(self._xdate(x))[0]
        self._vline_refs.append(dict(x=float(x), ymin=float(ymin), ymax=float(ymax), color=color,
                                linestyle=linestyle, linewidth=linewidth, alpha=alpha,
                                label=str(label)))

    def axhspan(self, ymin, ymax, xmin=0.0, xmax=1.0, color=None, alpha=None, label="",
                **kwargs):
        """Horizontal band between two data y values, over an axes-fraction x range."""
        ymin, ymax = _as_f64((ymin, ymax))
        self.hspans.append(dict(ymin=float(ymin), ymax=float(ymax), xmin=float(xmin),
                                xmax=float(xmax), color=color, alpha=alpha, label=str(label)))

    def axvspan(self, xmin, xmax, ymin=0.0, ymax=1.0, color=None, alpha=None, label="",
                **kwargs):
        """Vertical band between two data x values, over an axes-fraction y range."""
        values = _as_f64(self._xdate((xmin, xmax)))
        self.vspans.append(dict(xmin=float(values[0]), xmax=float(values[1]), ymin=float(ymin),
                                ymax=float(ymax), color=color, alpha=alpha, label=str(label)))

    def scatter(self, x, y, s=None, c=None, alpha=None, cmap=None, label="", marker="o",
                vmin=None, vmax=None, data=None, norm=None, **kwargs):
        """Scatter markers; `s` is an area in points^2 and `c` a colour, a list of
        colours, or numeric values mapped through `cmap`. `data=` may supply columns."""
        _check_kwargs(kwargs, "scatter", _SCATTER_KWARGS)
        if data is not None:
            def column(value):
                return data[value] if isinstance(value, str) and value in data else value
            x, y, s, c = column(x), column(y), column(s), column(c)
        x = _as_f64(self._xdate(x))
        y = _as_f64(self._ydate(y))
        _check_same_length(x, y)
        n = y.size
        values, colors = _scatter_colors(c if c is not None else self._next_color(patch=True), n)
        if norm is not None and values is not None:
            values, vmin, vmax = _norm_values(norm, values)
        entry = dict(
            x=np.ascontiguousarray(x), y=np.ascontiguousarray(y), sizes=_sizes(s, n),
            values=values, cmap=_cmap_name(cmap),
            clim=None if vmin is None and vmax is None else (vmin, vmax), colors=colors,
            marker=str(marker), alpha=1.0 if alpha is None else float(alpha),
            label=str(label))
        self._append_scatter(entry)
        return _ScatterHandle(entry, self)

    def errorbar(self, x, y, yerr=None, xerr=None, fmt="", ecolor=None, elinewidth=None,
                 capsize=None, label="", color=None, **kwargs):
        """Plot `y` against `x` with vertical (`yerr`) and/or horizontal (`xerr`)
        error bars; each error may be a scalar, a length-N array, or (2, N) lo/hi."""
        x = _as_f64(self._xdate(x))
        y = _as_f64(y)
        _check_same_length(x, y)
        n = y.size
        ylo, yhi = _err_pair(yerr, n, "yerr")
        xlo, xhi = _err_pair(xerr, n, "xerr")
        c = (color or ecolor or _FMT_COLORS.get(fmt[:1])
             or self._next_color())
        # matplotlib's default fmt='' still draws a solid line; marker-only formats
        # ('o', 's', ...) get bars only since markers are not rendered yet.
        elw = elinewidth if elinewidth is not None else rcParams.get("lines.linewidth", 1.5)
        if fmt != "none" and (fmt == "" or "-" in fmt):
            self._append_series(_series(x, y, label, c, linewidth=elw))
        self.errors.append((np.ascontiguousarray(x), np.ascontiguousarray(y), ylo, yhi,
                            xlo, xhi, c, float(capsize or 0.0) * 1.4))
        _, _, marker = _stem_fmt(fmt, "")
        if marker:
            self.scatter(x, y, s=36, c=c, marker=marker)

    def eventplot(self, positions, orientation="horizontal", lineoffsets=0.0, linelengths=1.0,
                  colors=None, linestyles=None, linewidths=None, **kwargs):
        """One short line per event position, one row per positions array."""
        data = kwargs.pop("data", None)
        if data is not None:
            positions = data[positions] if isinstance(positions, str) else positions
            colors = data[colors] if isinstance(colors, str) else colors
            lineoffsets = data[lineoffsets] if isinstance(lineoffsets, str) else lineoffsets
            linelengths = data[linelengths] if isinstance(linelengths, str) else linelengths
            linestyles = data[linestyles] if isinstance(linestyles, str) else linestyles
        rows = positions
        if isinstance(rows, np.ndarray) and rows.ndim == 2:
            rows = list(rows)
        elif not isinstance(rows, (list, tuple)) or (len(rows) and np.isscalar(rows[0])):
            rows = [rows]
        rows = [_as_f64(r) for r in rows]
        if not rows:
            return None
        n = len(rows)
        if np.isscalar(lineoffsets):
            offsets = np.full(n, float(lineoffsets)) + np.arange(n)
        else:
            offsets = _fill(lineoffsets, n)
        lengths = _fill(linelengths, n)
        cols = _line_colors(colors, n)
        styles = _line_styles(linestyles, n)
        collections = []
        for i, row in enumerate(rows):
            half = float(lengths[i]) / 2.0
            if orientation == "horizontal":
                collections.append(self.vlines(
                    row, offsets[i] - half, offsets[i] + half,
                    colors=cols[i], linestyles=styles[i], linewidths=linewidths))
            elif orientation == "vertical":
                collections.append(self.hlines(
                    row, offsets[i] - half, offsets[i] + half,
                    colors=cols[i], linestyles=styles[i], linewidths=linewidths))
            else:
                raise ValueError(f"unsupported orientation: {orientation!r}")
        return collections

    def broken_barh(self, xranges, yrange, colors=None, edgecolor=None, alpha=None,
                    linewidth=None, **kwargs):
        """Horizontal bars from `(xstart, width)` pairs over a shared y range."""
        colors = kwargs.get("facecolors", colors)
        pairs = [(float(a), float(b)) for a, b in xranges]
        if not pairs:
            return None
        n = len(pairs)
        position, height = yrange
        if isinstance(position, str):
            # A categorical y position labels the axis and sits at index 0.
            offset = self._category_positions([position])[0]
            step = float(height) / 2.0 if kwargs.get("align", "center") == "center" else 0.0
            position = offset - step
        self._append_bar(dict(left=np.array([a for a, _ in pairs]),
                              bottom=np.full(n, float(position)),
                              width=np.array([b for _, b in pairs]),
                              height=np.full(n, float(height)),
                              colors=_bar_colors(colors, n),
                              edgecolor=(_bar_colors(edgecolor, n)
                                         if edgecolor is not None else None),
                              alpha=None if alpha is None else float(alpha),
                              label="", vertical=True))
        return None

    def axline(self, xy1, xy2=None, slope=None, **kwargs):
        """Infinite line through `xy1`/`xy2` (or `xy1` with `slope`), clipped to
        the axes. It never contributes to the data limits."""
        if (xy2 is None) == (slope is None):
            raise ValueError("axline needs exactly one of xy2 or slope")
        self._axlines.append(dict(
            p=(float(xy1[0]), float(xy1[1])),
            xy2=None if xy2 is None else (float(xy2[0]), float(xy2[1])),
            slope=None if slope is None else float(slope),
            color=kwargs.get("color") or kwargs.get("c"),
            linestyle=kwargs.get("linestyle") or kwargs.get("ls") or "-",
            linewidth=float(kwargs.get("linewidth") or kwargs.get("lw") or 1.5),
            alpha=kwargs.get("alpha"), label=str(kwargs.get("label", ""))))
        return None

    def hlines(self, y, xmin, xmax, colors=None, linestyles=None, linewidths=None,
               label="", **kwargs):
        """Horizontal segments from `xmin` to `xmax` at every `y`."""
        ys = _as_f64(y)
        lo, hi = _fill(self._xdate(xmin), ys.size), _fill(self._xdate(xmax), ys.size)
        cols, styles = _line_colors(colors, ys.size), _line_styles(linestyles, ys.size)
        widths = _fill(linewidths, ys.size) if linewidths is not None else None
        handles = []
        for i in range(ys.size):
            self._append_series(_series(
                [lo[i], hi[i]], [ys[i], ys[i]], label, cols[i], linestyle=styles[i],
                linewidth=2.0 if widths is None else float(widths[i])))
            handles.append(_LineHandle(self.lines[-1]))
        return handles

    def vlines(self, x, ymin, ymax, colors=None, linestyles=None, linewidths=None,
               label="", **kwargs):
        """Vertical segments from `ymin` to `ymax` at every `x`."""
        xs = _as_f64(self._xdate(x))
        lo, hi = _fill(ymin, xs.size), _fill(ymax, xs.size)
        cols, styles = _line_colors(colors, xs.size), _line_styles(linestyles, xs.size)
        widths = _fill(linewidths, xs.size) if linewidths is not None else None
        handles = []
        for i in range(xs.size):
            self._append_series(_series(
                [xs[i], xs[i]], [lo[i], hi[i]], label, cols[i], linestyle=styles[i],
                linewidth=2.0 if widths is None else float(widths[i])))
            handles.append(_LineHandle(self.lines[-1]))
        return handles

    def stem(self, *args, linefmt=None, markerfmt=None, basefmt=None, bottom=0.0, label="",
             orientation="vertical", **kwargs):
        """Stem plot: one segment per point plus a marker at the tip."""
        if len(args) == 1:
            y = _as_f64(args[0])
            x = np.arange(y.size, dtype=np.float64)
        elif len(args) == 2:
            x = _as_f64(self._xdate(args[0]))
            y = _as_f64(args[1])
        else:
            raise TypeError("stem expects y or x, y")
        _check_same_length(x, y)
        if orientation not in ("vertical", "horizontal"):
            raise ValueError(f"unsupported orientation: {orientation!r}")
        colour, style, _ = _stem_fmt(linefmt)
        colour = kwargs.get("color") or colour or _CYCLE[len(self.lines) % len(_CYCLE)]
        marker = baseline = None
        stemlines = _LineGroupHandle()
        if x.size:
            if orientation == "vertical":
                stemlines = _LineGroupHandle(self.vlines(
                    x, bottom, y, colors=colour, linestyles=style,
                    linewidths=rcParams.get("lines.linewidth", 1.5)))
            else:
                stemlines = _LineGroupHandle(self.hlines(
                    y, bottom, x, colors=colour, linestyles=style,
                    linewidths=rcParams.get("lines.linewidth", 1.5)))
            marker_colour, _, marker_fmt = _stem_fmt(markerfmt, "o")
            marker = self.scatter(x, y, s=36, c=marker_colour or colour,
                                  marker=marker_fmt)
            if basefmt != "none":
                if orientation == "vertical":
                    base_lines = self.hlines(
                        [float(bottom)], float(x.min()), float(x.max()),
                        colors=colour, linewidths=rcParams.get("lines.linewidth", 1.5))
                else:
                    base_lines = self.vlines(
                        [float(bottom)], float(y.min()), float(y.max()),
                        colors=colour, linewidths=rcParams.get("lines.linewidth", 1.5))
                baseline = _LineGroupHandle(base_lines)[0] if base_lines else None
        return _StemContainer(marker, stemlines, baseline)

    def pie(self, x, labels=None, colors=None, autopct=None, explode=None, startangle=0,
            normalize=True, shadow=False, **kwargs):
        """Pie chart drawn as filled wedges; returns `(wedges, texts, autotexts)`."""
        values = _as_f64(x)
        if values.size == 0 or np.any(values < 0):
            raise ValueError("pie values must be non-negative")
        total = float(values.sum())
        if total <= 0.0:
            raise ValueError("pie values must sum to a positive number")
        if not normalize and total > 1.0:
            raise ValueError("pie values must sum to <= 1 when normalize=False")
        fracs = values / total
        angles = np.concatenate([[0.0], np.cumsum(fracs) * 360.0]) + float(startangle)
        offsets = np.zeros(values.size) if explode is None else _fill(explode, values.size)
        cols = _colors(colors) or list(_CYCLE)
        self.set_aspect("equal")
        self.set_xlim(-1.25, 1.25)
        self.set_ylim(-1.25, 1.25)
        texts, autotexts, wedges = [], [], []
        for i in range(values.size):
            a0, a1 = np.radians(angles[i]), np.radians(angles[i + 1])
            mid = (a0 + a1) / 2.0
            ex, ey = float(offsets[i]) * np.cos(mid), float(offsets[i]) * np.sin(mid)
            arc = np.linspace(a0, a1, 48)
            band = _band(np.concatenate([[ex], ex + np.cos(arc)]),
                         np.concatenate([[ey], ey + np.sin(arc)]),
                         cols[i % len(cols)], None)
            self._append_band(band)
            wedges.append(_Wedge(cols[i % len(cols)], center=(ex, ey),
                                 theta1=float(np.degrees(a0)),
                                 theta2=float(np.degrees(a1)), band=band,
                                 label=labels[i] if labels is not None else ""))
            if labels is not None:
                self.text(ex + 1.1 * np.cos(mid), ey + 1.1 * np.sin(mid), labels[i],
                          ha="center", va="center")
                texts.append(_TextLabel(labels[i]))
            if autopct is not None:
                pct = float(fracs[i]) * 100.0
                shown = autopct(pct) if callable(autopct) else str(autopct) % pct
                self.text(ex + 0.6 * np.cos(mid), ey + 0.6 * np.sin(mid), shown,
                          ha="center", va="center")
                autotexts.append(_TextLabel(shown))
        self.set_axis_off()
        return _PieResult(wedges, texts, autotexts, values=values, fracs=fracs)

    def stackplot(self, x, *ys, labels=(), colors=None, alpha=None, baseline="zero",
                  **kwargs):
        """Stacked areas: each layer fills between the running total and itself."""
        if baseline not in ("zero", "sym", "wiggle", "weighted_wiggle"):
            raise NotImplementedError(f"baseline={baseline!r} is not supported yet")
        wiggle = baseline in ("wiggle", "weighted_wiggle")
        x = _as_f64(x)
        layers = []  # type: ignore[var-annotated]
        for y in ys:
            a = np.asarray(_as_list(y), dtype=np.float64)
            if a.ndim == 2 and a.shape[0] == x.size:
                layers.extend(a[:, i] for i in range(a.shape[1]))
            elif a.ndim == 2 and a.shape[1] == x.size:
                layers.extend(a[i] for i in range(a.shape[0]))
            else:
                layers.append(a.ravel())
        if not layers:
            raise ValueError("stackplot needs at least one y array")
        labels = list(_as_list(labels)) if labels else []
        cols = _colors(colors)
        if baseline == "sym":
            cum = -np.sum(np.stack(layers), axis=0) / 2.0
        elif baseline == "weighted_wiggle":
            stacked = np.stack(layers)
            total = stacked.sum(axis=0)
            weights = stacked.shape[0] - np.arange(1, stacked.shape[0] + 1)
            center = np.divide((stacked * weights[:, None]).sum(axis=0), total,
                               out=np.zeros_like(total), where=total != 0)
            cum = -center
        elif baseline == "wiggle":
            cum = -np.sum(np.stack(layers), axis=0) / 2.0
        else:
            cum = np.zeros(x.size)
        data_lo = data_hi = 0.0
        for i, layer in enumerate(layers):
            _check_same_length(layer, x)
            colour = cols[i % len(cols)] if cols else _CYCLE[i % len(_CYCLE)]
            lab = str(labels[i]) if i < len(labels) else ""
            self.fill_between(x, cum, cum + layer, color=colour, alpha=alpha, label=lab)
            data_lo = min(data_lo, float(cum.min()), float((cum + layer).min()))
            data_hi = max(data_hi, float(cum.max()), float((cum + layer).max()))
            cum = cum + layer
        # Like bars, a stack that stays on one side of zero meets the axis at
        # y=0 instead of autoscaling a margin below it.
        if (baseline == "zero" or wiggle) and self.ylim is None:
            lo, hi = self.get_ylim()
            if wiggle:
                reach = max(abs(data_lo), abs(data_hi))
                lo, hi = -reach, reach
            elif data_lo >= 0.0:
                lo = 0.0
            elif data_hi <= 0.0:
                hi = 0.0
            self.set_ylim(lo, hi)

    def step(self, x, y, fmt="", where="pre", label="", color=None, **kwargs):
        """Staircase line through `x`/`y`; `where` picks the corner placement."""
        if where in ("pre", "post"):
            return self.plot(x, y, fmt, label=label, color=color,
                             drawstyle=f"steps-{where}", **kwargs)
        elif where == "mid":
            x_out, y_out = _mid_steps(x, y)
            return self.plot(x_out, y_out, fmt, label=label, color=color, drawstyle="steps-post", **kwargs)
        else:
            raise ValueError(f"unsupported where: {where!r}")

    def stairs(self, values, edges=None, baseline=0.0, orientation="vertical", fill=False,
               color=None, label="", **kwargs):
        """Step chart from bin `values` and `edges` (one longer than `values`)."""
        v = _as_f64(values)
        if edges is None:
            e = np.arange(v.size + 1.0)
        else:
            e = _as_f64(edges)
            if e.size != v.size + 1:
                raise ValueError("edges must have len(values) + 1 entries")
        if orientation not in ("vertical", "horizontal"):
            raise ValueError(f"unsupported orientation: {orientation!r}")
        first = np.empty(2 * v.size)
        second = np.empty(2 * v.size)
        first[0::2] = e[:-1]
        first[1::2] = e[1:]
        second[0::2] = v
        second[1::2] = v
        xs, ys = ((first, second) if orientation == "vertical"
                  else (second, first))
        if not fill:
            return self.plot(xs, ys, color=color, label=label, **kwargs)
        # A filled `stairs` is one StepPatch: `color` fills it, `alpha` applies to
        # the whole patch, and no edge is drawn unless one is asked for.
        alpha = kwargs.pop("alpha", None)
        edge = kwargs.pop("edgecolor", kwargs.pop("ec", None))
        linewidth = kwargs.pop("linewidth", kwargs.pop("lw", None))
        face = kwargs.pop("facecolor", kwargs.pop("fc", None)) or color
        base = baseline
        if not np.isscalar(baseline):
            base = np.repeat(_as_f64(baseline), 2)
        if orientation == "vertical":
            self.fill_between(xs, ys, base, color=face, alpha=alpha, label=label)
        else:
            self.fill_betweenx(ys, xs, base, color=face, alpha=alpha, label=label)
        if edge is not None:
            self.plot(xs, ys, color=edge, alpha=alpha, label="",
                      linewidth=linewidth if linewidth is not None else 1.0)
        return None


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._cm import _norm_values
    from ._config import rcParams
    from ._plot_helpers import (
        _as_f64,
        _band,
        _bar_colors,
        _check_same_length,
        _colors,
        _convert_units,
        _err_pair,
        _fill,
        _line_colors,
        _line_styles,
        _mid_steps,
        _parse_fmt,
        _plot_args,
        _resolve_data_args,
        _runs,
        _scatter_colors,
        _series,
        _sizes,
        _stem_fmt,
    )
