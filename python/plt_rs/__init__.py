"""plt_rs: minimal matplotlib-like API, rendered entirely in Rust."""
from contextlib import contextmanager

import numpy as np

from ._core import save

_CYCLE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
# Only the one-letter colors plt_rs can render are honoured in fmt strings.
_FMT_COLORS = {"b": "blue", "g": "green", "r": "red", "k": "black"}


class _Bbox:
    """Minimal Bbox with the attribute names matplotlib tests reach for."""

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = float(x0), float(y0), float(x1), float(y1)

    @property
    def width(self): return self.x1 - self.x0

    @property
    def height(self): return self.y1 - self.y0

    @property
    def bounds(self): return (self.x0, self.y0, self.width, self.height)

    @property
    def p0(self): return (self.x0, self.y0)

    @property
    def p1(self): return (self.x1, self.y1)

    def get_points(self): return [[self.x0, self.y0], [self.x1, self.y1]]

    def __repr__(self):
        return f"Bbox({self.x0:g}, {self.y0:g}, {self.x1:g}, {self.y1:g})"


class _Transform:
    """Stand-in for a matplotlib transform: data coordinates pass through."""

    def transform(self, points): return np.asarray(points, dtype=np.float64)

    def inverted(self): return self


class _TextLabel:
    """Minimal tick-label stand-in for code that pokes at Text objects."""

    def __init__(self, text=""):
        self._text, self._visible, self._fontsize = str(text), True, 12.0

    def get_text(self): return self._text
    def set_text(self, text): self._text = str(text)
    def get_visible(self): return self._visible
    def set_visible(self, visible): self._visible = bool(visible)
    def get_fontsize(self): return self._fontsize
    def set_fontsize(self, size): self._fontsize = float(size)


def _span(values):
    """Same padding rule as the Rust renderer: a flat series gets a unit window."""
    vals = [float(v) for v in values]
    if not vals:
        return (0.0, 1.0)
    lo, hi = min(vals), max(vals)
    return (lo, hi) if lo < hi else (lo - 1.0, lo + 1.0)
DPI = 100
_FORMATS = ("png", "svg")


class _BarHandle:
    """One bar, mirroring the mutable part of matplotlib's `Rectangle`."""

    def __init__(self, axes, group, index):
        self._axes = axes
        self._group = group
        self._index = index

    def _get(self, key):
        return float(self._axes.bars[self._group][key][self._index])

    def _set(self, key, value):
        self._axes.bars[self._group][key] = value

    def get_x(self): return self._get("left")
    def get_y(self): return self._get("bottom")
    def get_width(self): return self._get("width")
    def get_height(self): return self._get("height")

    def set_facecolor(self, c):
        self._set("colors", [str(c)])
        return self

    def set_color(self, c):
        return self.set_facecolor(c)

    def set_edgecolor(self, c):
        self._set("edgecolor", str(c))
        return self

    def set_alpha(self, a):
        self._set("alpha", float(a))
        return self

    def remove(self):
        self._axes.bars[self._group]["height"][self._index] = 0.0
        self._axes.bars[self._group]["width"][self._index] = 0.0


class _BarContainer(list):
    """List of `_BarHandle`, matching matplotlib's `BarContainer`."""

    def __init__(self, handles, label=""):
        super().__init__(handles)
        self.label = label

    @property
    def patches(self):
        return list(self)


class Axes:
    def __init__(self, pos):
        self.pos, self.lines, self.texts = pos, [], []
        self.images, self.annotations = [], []
        self.contours = []
        self.errors = []
        self.scatter_pts = []
        self.bars = []
        self.bands = []
        self._hline_refs = []
        self._vline_refs = []
        self.hspans = []
        self.vspans = []
        self.aspect = None
        self.title = self.xlabel = self.ylabel = ""
        self.show_legend, self.xlim, self.ylim = False, None, None
        self.visible, self._removed, self._axis_off = True, False, False
        self.artists, self.label, self.zorder = [], "", 0
        self.facecolor, self.alpha = "white", None
        self.xscale = self.yscale = "linear"
        self.show_grid = False
        self.tick_params_box = {}
        self._axlines = []
        self._xticks = self._yticks = None
        self._xticklabels = self._yticklabels = None
        self._inverted = [False, False]
        self._pos_override = None
        self._fig = None

    def plot(self, *args, label="", color=None, c=None, linestyle=None, ls=None,
             linewidth=None, lw=None, marker=None, markersize=None, ms=None,
             markerfacecolor=None, mfc=None, markeredgecolor=None, mec=None,
             markeredgewidth=None, mew=None, alpha=None, drawstyle="default", fmt=None,
             **kwargs):
        """Line plot with matplotlib's styling keywords (`lw`, `ls`, `marker`, `ms`,
        `mfc`/`mec`, `alpha`, `drawstyle`) and fmt-string shorthand (`"r--o"`)."""
        x, y, fmt = _plot_args(args, fmt)
        if y is None:
            x, y = np.arange(len(x)), x
        style = linestyle or ls or "-"
        if fmt:
            f_color, f_style, f_marker = _parse_fmt(fmt)
            color = color or c or f_color
            if linestyle is None and ls is None:
                style = f_style or style
            if not marker:
                marker = f_marker
        line_color = color or c or _CYCLE[len(self.lines) % len(_CYCLE)]
        if drawstyle not in ("default", "steps-pre", "steps-post"):
            raise ValueError(f"unsupported drawstyle: {drawstyle!r}")
        edge = markeredgecolor or mec
        self.lines.append(_series(
            x, y, label, line_color, linestyle=style,
            linewidth=linewidth if linewidth is not None else (lw if lw is not None else 2.0),
            marker=marker or "",
            markersize=markersize if markersize is not None else (ms if ms is not None else 6.0),
            mfc=markerfacecolor or mfc, mec=edge,
            mew=markeredgewidth if markeredgewidth is not None else (mew if mew is not None else 1.0),
            alpha=alpha, drawstyle=drawstyle))

    def set_aspect(self, aspect, adjustable=None, anchor=None, share=False):
        self.aspect = _norm_aspect(aspect)

    def get_aspect(self): return self.aspect

    # -- introspection / compatibility surface --------------------------------
    def draw(self, *args, **kwargs): return None

    def get_position(self):
        """Figure-fraction box: the grid cell, or whatever `set_position` stored."""
        if self._pos_override is not None:
            x, y, w, h = self._pos_override
            return _Bbox(x, y, x + w, y + h)
        rows, cols = self._fig.grid if self._fig is not None else (1, 1)
        r, c = divmod(self.pos, cols)
        return _Bbox(c / cols, 1.0 - (r + 1) / rows, (c + 1) / cols, 1.0 - r / rows)

    def set_position(self, pos):
        self._pos_override = tuple(float(v) for v in pos)

    def _extent_x(self):
        xs = []
        for entry in self.lines:
            xs.extend(np.asarray(entry["x"]).ravel())
        for im in self.images:
            xs.extend([im["extent"][0], im["extent"][1]])
        for c in self.contours:
            xs.extend([float(c["x"][0]), float(c["x"][-1])])
        for sc in self.scatter_pts:
            xs.extend(sc["x"])
        for bars in self.bars:
            xs.extend(bars["left"])
            xs.extend(bars["left"] + bars["width"])
        for band in self.bands:
            xs.extend(band["x"])
        for e in self.errors:
            xs.extend(e[0] - e[4])
            xs.extend(e[0] + e[5])
        return _span(xs)

    def _extent_y(self):
        ys = []
        for entry in self.lines:
            ys.extend(np.asarray(entry["y"]).ravel())
        for im in self.images:
            ys.extend([im["extent"][2], im["extent"][3]])
        for c in self.contours:
            ys.extend([float(c["y"][0]), float(c["y"][-1])])
        for sc in self.scatter_pts:
            ys.extend(sc["y"])
        for bars in self.bars:
            ys.extend(bars["bottom"])
            ys.extend(bars["bottom"] + bars["height"])
        for band in self.bands:
            ys.extend(band["y"])
        for e in self.errors:
            ys.extend(e[1] - e[2])
            ys.extend(e[1] + e[3])
        return _span(ys)

    def get_xlim(self):
        lo, hi = self.xlim or self._extent_x()
        return _log_bounds(lo, hi, self.xscale, self._extent_x())

    def get_ylim(self):
        lo, hi = self.ylim or self._extent_y()
        return _log_bounds(lo, hi, self.yscale, self._extent_y())
    def get_xbound(self): return self.get_xlim()
    def get_ybound(self): return self.get_ylim()

    def invert_xaxis(self): self._inverted[0] = not self._inverted[0]
    def invert_yaxis(self): self._inverted[1] = not self._inverted[1]
    def xaxis_inverted(self): return self._inverted[0]
    def yaxis_inverted(self): return self._inverted[1]

    def _limits(self):
        (x0, x1), (y0, y1) = self.get_xlim(), self.get_ylim()
        if self._inverted[0]:
            x0, x1 = x1, x0
        if self._inverted[1]:
            y0, y1 = y1, y0
        return (x0, x1), (y0, y1)

    def get_visible(self): return self.visible
    def set_visible(self, visible): self.visible = bool(visible)
    def set_axis_off(self): self._axis_off = True
    def set_axis_on(self): self._axis_off = False

    def axis(self, arg=None, **kwargs):
        if arg is None:
            return (self.get_xlim(), self.get_ylim())
        if isinstance(arg, str):
            key = arg.lower()
            if key in ("off", "false", "tight"):
                self._axis_off = True
            elif key in ("on", "true", "image"):
                self._axis_off = False
            elif key in ("equal", "scaled"):
                self.set_aspect("equal")
            elif key == "auto":
                self.set_aspect("auto")
            else:
                raise ValueError(f"unsupported axis mode: {arg!r}")
            return None
        vals = list(arg)
        if len(vals) != 4:
            raise ValueError("axis expects 'off'/'equal' or four limits")
        self.set_xlim(vals[0], vals[1])
        self.set_ylim(vals[2], vals[3])

    def remove(self): self._removed = True

    def get_facecolor(self): return self.facecolor
    def set_facecolor(self, color): self.facecolor = str(color)
    def get_alpha(self): return self.alpha
    def set_alpha(self, alpha): self.alpha = None if alpha is None else float(alpha)

    def get_transform(self): return _Transform()

    def get_window_extent(self, renderer=None):
        b = self.get_position()
        w, h = self._fig.figsize if self._fig is not None else (6.4, 4.8)
        return _Bbox(b.x0 * w * DPI, b.y0 * h * DPI, b.x1 * w * DPI, b.y1 * h * DPI)

    def get_tightbbox(self, renderer=None): return self.get_window_extent(renderer)
    def get_figure(self): return self._fig

    def add_artist(self, artist): self.artists.append(artist); return artist
    def add_patch(self, patch): self.artists.append(patch); return patch
    def add_collection(self, collection, autolim=True):
        self.artists.append(collection)
        return collection
    def add_line(self, line): self.artists.append(line); return line
    def get_children(self): return list(self.artists) + [self]
    def update(self, *args, **kwargs): return None

    def get_label(self): return self.label
    def set_label(self, label): self.label = str(label)
    def get_zorder(self): return self.zorder
    def set_zorder(self, zorder): self.zorder = int(zorder)

    # Accepted for compatibility; custom artists are not rendered yet.
    def set_clip_path(self, path, transform=None): return None
    def set_clip_on(self, clip): return None
    def set_path_effects(self, effects): return None
    def margins(self, *args, **kwargs): return None
    def relim(self, visible_only=True): return None
    def autoscale(self, enable=True, axis="both", tight=None): return None
    def autoscale_view(self, tight=None, scalex=True, scaley=True): return None

    def clear(self):
        self.lines.clear()
        self.texts.clear()
        self.images.clear()
        self.annotations.clear()
        self.contours.clear()
        self.errors.clear()
        self.scatter_pts.clear()
        self.bars.clear()
        self.bands.clear()
        self._hline_refs.clear()
        self._vline_refs.clear()
        self.hspans.clear()
        self.vspans.clear()
        self.artists.clear()
        self.title = self.xlabel = self.ylabel = ""
        self.show_legend, self.xlim, self.ylim = False, None, None
        self._xticks = self._yticks = None
        self._xticklabels = self._yticklabels = None
        self.show_grid = False
        self._axlines.clear()

    cla = clear

    def set_xticks(self, ticks, labels=None, **kwargs):
        self._xticks = [float(t) for t in np.asarray(ticks).ravel()]
        if labels is not None:
            self._xticklabels = [str(v) for v in np.asarray(labels).ravel()]

    def set_yticks(self, ticks, labels=None, **kwargs):
        self._yticks = [float(t) for t in np.asarray(ticks).ravel()]
        if labels is not None:
            self._yticklabels = [str(v) for v in np.asarray(labels).ravel()]

    def get_xticks(self, minor=False):
        if self._xticks is not None:
            return np.asarray(self._xticks)
        return np.linspace(*self.get_xlim(), 6)

    def get_yticks(self, minor=False):
        if self._yticks is not None:
            return np.asarray(self._yticks)
        return np.linspace(*self.get_ylim(), 6)

    def set_xticklabels(self, labels, **kwargs):
        self._xticklabels = [str(v) for v in np.asarray(labels).ravel()]

    def set_yticklabels(self, labels, **kwargs):
        self._yticklabels = [str(v) for v in np.asarray(labels).ravel()]

    def get_xticklabels(self, minor=False, which=None):
        labels = self._xticklabels
        if labels is None:
            labels = [f"{v:g}" for v in self.get_xticks()]
        return [_TextLabel(t) for t in labels]

    def get_yticklabels(self, minor=False, which=None):
        labels = self._yticklabels
        if labels is None:
            labels = [f"{v:g}" for v in self.get_yticks()]
        return [_TextLabel(t) for t in labels]

    def set_xscale(self, value, base=10, **kwargs):
        name = str(value)
        if name == "linear":
            self.xscale = "linear"
        elif name == "log":
            self.xscale, self.log_base = "log", float(base)
        else:
            raise NotImplementedError(f"unsupported x scale: {value!r}")

    def set_yscale(self, value, base=10, **kwargs):
        name = str(value)
        if name == "linear":
            self.yscale = "linear"
        elif name == "log":
            self.yscale, self.log_base = "log", float(base)
        else:
            raise NotImplementedError(f"unsupported y scale: {value!r}")

    def semilogx(self, *args, **kwargs):
        self.set_xscale("log")
        return self.plot(*args, **kwargs)

    def semilogy(self, *args, **kwargs):
        self.set_yscale("log")
        return self.plot(*args, **kwargs)

    def loglog(self, *args, **kwargs):
        self.set_xscale("log")
        self.set_yscale("log")
        return self.plot(*args, **kwargs)

    def get_xscale(self): return self.xscale
    def get_yscale(self): return self.yscale
    def get_title(self): return self.title
    def get_xlabel(self): return self.xlabel
    def get_ylabel(self): return self.ylabel

    def set(self, **kwargs):
        """`ax.set(xlim=, ylim=, xlabel=, title=, xticks=, aspect=, ...)` shorthand."""
        for key, value in kwargs.items():
            if key in ("xlim", "ylim", "xticks", "yticks"):
                if key.endswith("ticks"):
                    getattr(self, f"set_{key}")(value)
                else:
                    getattr(self, f"set_{key}")(*value)
            elif key in ("xlabel", "ylabel", "title", "xticklabels", "yticklabels",
                         "xscale", "yscale"):
                getattr(self, f"set_{key}")(value)
            elif key == "aspect":
                self.set_aspect(value)
            else:
                setter = getattr(self, f"set_{key}", None)
                if setter is None:
                    raise AttributeError(f"Axes.set() does not support {key!r}")
                setter(value)

    def text(self, x, y, s, color="black", fontsize=12, ha="left", va="baseline"):
        """Place text at data coordinates (x, y)."""
        if ha not in ("left", "center", "right"):
            raise ValueError(f"unsupported ha: {ha!r}")
        if va not in ("baseline", "bottom", "center", "top"):
            raise ValueError(f"unsupported va: {va!r}")
        self.texts.append((float(x), float(y), str(s), color, float(fontsize), ha, va))

    def imshow(self, X, cmap=None, vmin=None, vmax=None, extent=None, origin="upper",
               interpolation=None, aspect=None, alpha=None):
        """Draw an array as an image. `X` is 2-D (mapped through `cmap`) or
        (H, W, 3|4) RGB(A) floats in 0-1."""
        a = _as_image(X)
        h, w = a.shape[:2]
        if origin == "lower":
            a = a[::-1]
        elif origin != "upper":
            raise ValueError(f"unsupported origin: {origin!r}")
        if extent is None:
            extent = (0.0, float(w), 0.0, float(h))
        elif len(extent) != 4:
            raise ValueError("extent must be (left, right, bottom, top)")
        entry = dict(data=a, cmap=cmap or "viridis", vmin=vmin, vmax=vmax,
                     extent=tuple(float(v) for v in extent))
        self.images.append(entry)
        # matplotlib's image.aspect default is "equal".
        self.set_aspect("equal" if aspect is None else aspect)
        return AxesImage(entry)

    def hist(self, x, bins=10, range=None, density=False, weights=None, cumulative=False,
             bottom=None, histtype="bar", align="mid", orientation="vertical", color=None,
             label=None, alpha=None, edgecolor=None, stacked=False, **kwargs):
        """Histogram of `x`, drawn as bars; returns `(counts, edges, handles)`."""
        if histtype != "bar":
            raise NotImplementedError(f"histtype={histtype!r} is not supported yet")
        data = np.asarray(x, dtype=np.float64).ravel()
        counts, edges = np.histogram(data, bins=bins, range=range, weights=weights,
                                     density=bool(density))
        if cumulative:
            counts = np.cumsum(counts)
        widths = np.diff(edges)
        bar_align = "edge" if align in ("left", "edge") else "center"
        if bar_align == "edge":
            centers = edges[:-1]
        else:
            centers = (edges[:-1] + edges[1:]) / 2.0
        lab = "" if label is None else str(label)
        if orientation == "horizontal":
            handles = self.barh(centers, counts, height=widths, align=bar_align, color=color,
                                edgecolor=edgecolor, alpha=alpha, label=lab)
        elif orientation == "vertical":
            handles = self.bar(centers, counts, width=widths, align=bar_align, color=color,
                               edgecolor=edgecolor, alpha=alpha, label=lab)
        else:
            raise ValueError(f"unsupported orientation: {orientation!r}")
        return np.asarray(counts, dtype=np.float64), edges, handles

    def bar(self, x, height, width=0.8, bottom=0.0, color=None, edgecolor=None, label="",
            align="center", alpha=None, linewidth=None, yerr=None, **kwargs):
        """Vertical bars; `color` may be a single colour or one per bar."""
        x = np.asarray(x, dtype=np.float64).ravel()
        n = x.size
        h, w, b = _fill(height, n), _fill(width, n), _fill(bottom, n)
        if align not in ("center", "edge"):
            raise ValueError(f"unsupported align: {align!r}")
        left = x - w / 2.0 if align == "center" else x
        colors = _bar_colors(color, n)
        self.bars.append(dict(left=np.ascontiguousarray(left), bottom=b, width=w, height=h,
                              colors=colors,
                              edgecolor=None if edgecolor is None else str(edgecolor),
                              alpha=None if alpha is None else float(alpha), label=str(label),
                              vertical=True))
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
                    y, va = anchor + length + float(padding), "bottom"
                else:
                    y, va = anchor + length / 2.0, "center"
                ha = "center"
            else:
                length = float(group["width"][index])
                y = float(group["bottom"][index] + group["height"][index] / 2.0)
                anchor = float(group["left"][index])
                if label_type == "edge":
                    x, ha = anchor + length + float(padding), "left"
                else:
                    x, ha = anchor + length / 2.0, "center"
                va = "center"
            text = texts[i] if texts is not None else fmt % length
            self.text(x, y, text, color=kwargs.get("color", "black"),
                      fontsize=kwargs.get("fontsize", 10), ha=ha, va=va)
            out.append(text)
        return out

    def barh(self, y, width, height=0.8, left=0.0, color=None, edgecolor=None, label="",
             align="center", alpha=None, linewidth=None, **kwargs):
        """Horizontal bars, stored as the same rectangles as `bar`."""
        y = np.asarray(y, dtype=np.float64).ravel()
        n = y.size
        w, h, l = _fill(width, n), _fill(height, n), _fill(left, n)
        if align not in ("center", "edge"):
            raise ValueError(f"unsupported align: {align!r}")
        bottom = y - h / 2.0 if align == "center" else y
        self.bars.append(dict(left=l, bottom=np.ascontiguousarray(bottom), width=w, height=h,
                              colors=_bar_colors(color, n),
                              edgecolor=None if edgecolor is None else str(edgecolor),
                              alpha=None if alpha is None else float(alpha), label=str(label),
                              vertical=False))
        return _BarContainer([_BarHandle(self, len(self.bars) - 1, i) for i in range(n)],
                             str(label))

    def fill_between(self, x, y1, y2=0.0, where=None, interpolate=False, color=None,
                     alpha=None, label="", step=None, **kwargs):
        """Fill between two curves; `where` masks split the area into runs."""
        x = np.asarray(x, dtype=np.float64).ravel()
        a, b = _fill(y1, x.size), _fill(y2, x.size)
        c = color or _CYCLE[len(self.bands) % len(_CYCLE)]
        for xs, ya, yb in _runs(x, a, b, where):
            self.bands.append(_band(np.concatenate([xs, xs[::-1]]),
                                    np.concatenate([ya, yb[::-1]]), c, alpha))

    def fill_betweenx(self, y, x1, x2=0.0, where=None, color=None, alpha=None, label="",
                      **kwargs):
        y = np.asarray(y, dtype=np.float64).ravel()
        a, b = _fill(x1, y.size), _fill(x2, y.size)
        c = color or _CYCLE[len(self.bands) % len(_CYCLE)]
        for ys, xa, xb in _runs(y, a, b, where):
            self.bands.append(_band(np.concatenate([xa, xb[::-1]]),
                                    np.concatenate([ys, ys[::-1]]), c, alpha))

    def fill(self, *args, color=None, alpha=None, label="", **kwargs):
        """Closed polygon: `fill(x, y)` or `fill(x1, y1, x2, y2)`."""
        c = color or _CYCLE[len(self.bands) % len(_CYCLE)]
        if len(args) == 2:
            self.bands.append(_band(_as_f64(args[0]), _as_f64(args[1]), c, alpha))
        elif len(args) == 4:
            x1, y1, x2, y2 = (_as_f64(a) for a in args)
            self.bands.append(_band(np.concatenate([x1, x2[::-1]]),
                                    np.concatenate([y1, y2[::-1]]), c, alpha))
        else:
            raise TypeError("fill expects (x, y) or (x1, y1, x2, y2)")

    def axhline(self, y=0.0, xmin=0.0, xmax=1.0, color=None, linestyle=None, linewidth=None,
                alpha=None, label="", **kwargs):
        """Horizontal line at data `y`, spanning an axes-fraction x range."""
        self._hline_refs.append(dict(y=float(y), xmin=float(xmin), xmax=float(xmax), color=color,
                                linestyle=linestyle, linewidth=linewidth, alpha=alpha,
                                label=str(label)))

    def axvline(self, x=0.0, ymin=0.0, ymax=1.0, color=None, linestyle=None, linewidth=None,
                alpha=None, label="", **kwargs):
        """Vertical line at data `x`, spanning an axes-fraction y range."""
        self._vline_refs.append(dict(x=float(x), ymin=float(ymin), ymax=float(ymax), color=color,
                                linestyle=linestyle, linewidth=linewidth, alpha=alpha,
                                label=str(label)))

    def axhspan(self, ymin, ymax, xmin=0.0, xmax=1.0, color=None, alpha=None, label="",
                **kwargs):
        """Horizontal band between two data y values, over an axes-fraction x range."""
        self.hspans.append(dict(ymin=float(ymin), ymax=float(ymax), xmin=float(xmin),
                                xmax=float(xmax), color=color, alpha=alpha, label=str(label)))

    def axvspan(self, xmin, xmax, ymin=0.0, ymax=1.0, color=None, alpha=None, label="",
                **kwargs):
        """Vertical band between two data x values, over an axes-fraction y range."""
        self.vspans.append(dict(xmin=float(xmin), xmax=float(xmax), ymin=float(ymin),
                                ymax=float(ymax), color=color, alpha=alpha, label=str(label)))

    def pcolormesh(self, *args, cmap=None, vmin=None, vmax=None, shading="auto",
                   alpha=None, norm=None, **kwargs):
        """Quad mesh: each Z cell is filled through `cmap` via the image path.

        `X`/`Y` may be cell edges (one longer than Z's axis) or cell centres.
        """
        x, y, z, edges = _mesh_args(args)
        rows, cols = z.shape
        if edges:
            extent = (float(x[0]), float(x[-1]), float(y[0]), float(y[-1]))
        else:
            dx = float(x[1] - x[0]) if x.size > 1 else 1.0
            dy = float(y[1] - y[0]) if y.size > 1 else 1.0
            extent = (float(x[0]) - dx / 2, float(x[-1]) + dx / 2,
                      float(y[0]) - dy / 2, float(y[-1]) + dy / 2)
        return self.imshow(z, cmap=cmap or "viridis", vmin=vmin, vmax=vmax,
                           extent=extent, origin="lower", alpha=alpha)

    def pcolor(self, *args, **kwargs):
        return self.pcolormesh(*args, **kwargs)

    def pcolorfast(self, *args, **kwargs):
        return self.pcolormesh(*args, **kwargs)

    def annotate(self, text, xy, xytext=None, arrowprops=None, color="black", fontsize=12):
        """Text at `xytext` with an arrow pointing at `xy`."""
        self.annotations.append((str(text), (float(xy[0]), float(xy[1])),
                                 None if xytext is None else (float(xytext[0]), float(xytext[1])),
                                 color, float(fontsize)))

    def scatter(self, x, y, s=None, c=None, alpha=None, cmap=None, label="", marker="o",
                vmin=None, vmax=None, **kwargs):
        """Scatter markers; `s` is an area in points^2 and `c` a colour, a list of
        colours, or numeric values mapped through `cmap`."""
        x = np.asarray(x, dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        n = y.size
        values, colors = _scatter_colors(c, n)
        self.scatter_pts.append(dict(
            x=np.ascontiguousarray(x), y=np.ascontiguousarray(y), sizes=_sizes(s, n),
            values=values, cmap=cmap or "viridis",
            clim=None if vmin is None and vmax is None else (vmin, vmax), colors=colors,
            marker=str(marker), alpha=1.0 if alpha is None else float(alpha)))

    def errorbar(self, x, y, yerr=None, xerr=None, fmt="", ecolor=None, elinewidth=None,
                 capsize=None, label="", color=None, **kwargs):
        """Plot `y` against `x` with vertical (`yerr`) and/or horizontal (`xerr`)
        error bars; each error may be a scalar, a length-N array, or (2, N) lo/hi."""
        x = np.asarray(x, dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        n = y.size
        ylo, yhi = _err_pair(yerr, n, "yerr")
        xlo, xhi = _err_pair(xerr, n, "xerr")
        c = (color or ecolor or _FMT_COLORS.get(fmt[:1])
             or _CYCLE[len(self.errors) % len(_CYCLE)])
        # matplotlib's default fmt='' still draws a solid line; marker-only formats
        # ('o', 's', ...) get bars only since markers are not rendered yet.
        if fmt != "none" and (fmt == "" or "-" in fmt):
            self.lines.append(_series(x, y, label, c))
        self.errors.append((np.ascontiguousarray(x), np.ascontiguousarray(y), ylo, yhi,
                            xlo, xhi, c, float(capsize or 0.0) * 1.4))

    def contour(self, *args, levels=None, colors=None, cmap=None, linewidths=None, alpha=None):
        """Iso-lines of a 2-D array: `contour(Z)` or `contour(X, Y, Z)`, optionally
        followed by `levels`."""
        return self._add_contour(args, levels, colors, cmap, False)

    def contourf(self, *args, levels=None, colors=None, cmap=None, alpha=None):
        """Filled iso-bands of a 2-D array; takes the same forms as `contour`."""
        return self._add_contour(args, levels, colors, cmap, True)

    def _add_contour(self, args, levels, colors, cmap, filled):
        x, y, z, levels = _contour_args(args, levels)
        entry = dict(x=x, y=y, z=z, levels=_levels(z, levels),
                     colors=_colors(colors), cmap=cmap or "viridis", filled=filled)
        self.contours.append(entry)
        return ContourSet(entry)

    def set_title(self, t): self.title = t
    def set_xlabel(self, t): self.xlabel = t
    def set_ylabel(self, t): self.ylabel = t
    def set_xlim(self, lo, hi): self.xlim = (float(lo), float(hi))
    def set_ylim(self, lo, hi): self.ylim = (float(lo), float(hi))
    def legend(self): self.show_legend = True

    def grid(self, visible=None, which="major", axis="both", **kwargs):
        """Toggle gridlines; `visible=None` flips the current state."""
        self.show_grid = (not self.show_grid) if visible is None else bool(visible)
        return None

    def tick_params(self, axis="both", **kwargs):
        """Tick styling is recorded but not rendered."""
        self.tick_params_box.update(kwargs)
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

    def hlines(self, y, xmin, xmax, colors=None, linestyles=None, label="", **kwargs):
        """Horizontal segments from `xmin` to `xmax` at every `y`."""
        ys = np.asarray(y, dtype=np.float64).ravel()
        lo, hi = _fill(xmin, ys.size), _fill(xmax, ys.size)
        cols, styles = _line_colors(colors, ys.size), _line_styles(linestyles, ys.size)
        for i in range(ys.size):
            self.lines.append(_series([lo[i], hi[i]], [ys[i], ys[i]], label, cols[i],
                                      linestyle=styles[i]))

    def vlines(self, x, ymin, ymax, colors=None, linestyles=None, label="", **kwargs):
        """Vertical segments from `ymin` to `ymax` at every `x`."""
        xs = np.asarray(x, dtype=np.float64).ravel()
        lo, hi = _fill(ymin, xs.size), _fill(ymax, xs.size)
        cols, styles = _line_colors(colors, xs.size), _line_styles(linestyles, xs.size)
        for i in range(xs.size):
            self.lines.append(_series([xs[i], xs[i]], [lo[i], hi[i]], label, cols[i],
                                      linestyle=styles[i]))

    def step(self, x, y, fmt="", where="pre", label="", color=None, **kwargs):
        """Staircase line through `x`/`y`; `where` picks the corner placement."""
        if where in ("pre", "post"):
            style = "steps-pre" if where == "pre" else "steps-post"
        elif where == "mid":
            raise NotImplementedError("step(where='mid') is not supported yet")
        else:
            raise ValueError(f"unsupported where: {where!r}")
        return self.plot(x, y, fmt, label=label, color=color, drawstyle=style, **kwargs)

    def stairs(self, values, edges=None, baseline=0.0, orientation="vertical", fill=False,
               color=None, label="", **kwargs):
        """Step chart from bin `values` and `edges` (one longer than `values`)."""
        v = np.asarray(values, dtype=np.float64).ravel()
        if edges is None:
            e = np.arange(v.size + 1.0)
        else:
            e = np.asarray(edges, dtype=np.float64).ravel()
            if e.size != v.size + 1:
                raise ValueError("edges must have len(values) + 1 entries")
        if orientation != "vertical":
            raise NotImplementedError(f"orientation={orientation!r} is not supported yet")
        xs = np.empty(2 * v.size)
        ys = np.empty(2 * v.size)
        xs[0::2] = e[:-1]
        xs[1::2] = e[1:]
        ys[0::2] = v
        ys[1::2] = v
        if fill:
            self.fill_between(xs, ys, baseline, color=color)
        return self.plot(xs, ys, color=color, label=label, **kwargs)

    # Layout requests are accepted but ignored: every panel is drawn at its fixed
    # gridspec cell, so there is nothing to negotiate.
    def tight_layout(self, **kwargs): return None
    def subplots_adjust(self, **kwargs): return None
    def set_layout_engine(self, engine=None, **kwargs): self.layout_engine = engine
    def get_layout_engine(self): return getattr(self, "layout_engine", None)
    def set_in_layout(self, b): self.in_layout = bool(b)
    def get_in_layout(self): return getattr(self, "in_layout", True)

    def _panel(self):
        (x0, x1), (y0, y1) = self._limits()
        dx, dy = x1 - x0, y1 - y0
        # Reference lines and bands are axes-fraction based, so they are resolved
        # here, once the drawing limits are known.
        series = list(self.lines)
        for h in self._hline_refs:
            series.append(_series([x0 + h["xmin"] * dx, x0 + h["xmax"] * dx],
                                  [h["y"], h["y"]], h["label"], h["color"] or "black",
                                  linestyle=h["linestyle"] or "-",
                                  linewidth=1.5 if h["linewidth"] is None else float(h["linewidth"]),
                                  alpha=h["alpha"]))
        for a in self._axlines:
            (px, py) = a["p"]
            if a["slope"] is None:
                (qx, qy) = a["xy2"]
                m = np.inf if qx == px else (qy - py) / (qx - px)
            else:
                m = a["slope"]
            if not np.isfinite(m):
                xs, ys = [px, px], [y0, y1]
            else:
                xs = [x0, x1]
                ys = [py + m * (x0 - px), py + m * (x1 - px)]
            series.append(_series(xs, ys, a["label"], a["color"] or "black",
                                  linestyle=a["linestyle"], linewidth=a["linewidth"],
                                  alpha=a["alpha"]))
        for v in self._vline_refs:
            series.append(_series([v["x"], v["x"]],
                                  [y0 + v["ymin"] * dy, y0 + v["ymax"] * dy],
                                  v["label"], v["color"] or "black",
                                  linestyle=v["linestyle"] or "-",
                                  linewidth=1.5 if v["linewidth"] is None else float(v["linewidth"]),
                                  alpha=v["alpha"]))
        bars = list(self.bars)
        for s in self.hspans:
            lo, hi = min(s["ymin"], s["ymax"]), max(s["ymin"], s["ymax"])
            bars.append(dict(left=np.array([x0 + s["xmin"] * dx]), bottom=np.array([lo]),
                             width=np.array([(s["xmax"] - s["xmin"]) * dx]),
                             height=np.array([hi - lo]), colors=[s["color"] or "0.5"],
                             edgecolor=None, alpha=s["alpha"], label="", vertical=True))
        for s in self.vspans:
            lo, hi = min(s["xmin"], s["xmax"]), max(s["xmin"], s["xmax"])
            bars.append(dict(left=np.array([lo]), bottom=np.array([y0 + s["ymin"] * dy]),
                             width=np.array([hi - lo]),
                             height=np.array([(s["ymax"] - s["ymin"]) * dy]),
                             colors=[s["color"] or "0.5"], edgecolor=None, alpha=s["alpha"],
                             label="", vertical=True))
        return dict(pos=self.pos, series=series, texts=self.texts, title=self.title,
                    xlabel=self.xlabel, ylabel=self.ylabel, legend=self.show_legend,
                    xlim=(x0, x1), ylim=(y0, y1), annotations=self.annotations,
                    aspect=self.aspect,
                    contours=[(c["x"], c["y"], c["z"], c["levels"], c["colors"], c["cmap"],
                               c["filled"]) for c in self.contours],
                    errors=self.errors,
                    bars=bars,
                    bands=self.bands,
                    x_log=self.xscale == "log", y_log=self.yscale == "log",
                    grid=self.show_grid,
                    scatter=[dict(x=e["x"], y=e["y"], sizes=e["sizes"], values=e["values"],
                                  cmap=e["cmap"], clim=e["clim"], colors=e["colors"],
                                  marker=e["marker"], alpha=e["alpha"])
                             for e in self.scatter_pts],
                    colorbar=None,
                    axis_off=self._axis_off,
                    images=[(e["data"], e["cmap"], e["vmin"], e["vmax"], e["extent"], True)
                            for e in self.images])


def _norm_aspect(a):
    if isinstance(a, str):
        if a == "auto": return None
        if a == "equal": return 1.0
        raise ValueError(f"unsupported aspect: {a!r} (use 'auto', 'equal' or a number)")
    a = float(a)
    if not a > 0:
        raise ValueError(f"aspect must be positive, got {a!r}")
    return a


def _as_image(X):
    a = np.asarray(X, dtype=np.float64)
    if a.ndim == 3 and a.shape[2] in (3, 4):
        return a
    if a.ndim == 2:
        return a
    raise ValueError("imshow expects a 2-D array or an (H, W, 3|4) RGB(A) array")


def _series(x, y, label, color, linestyle="-", linewidth=2.0, marker="", markersize=6.0,
            mfc=None, mec=None, mew=1.0, alpha=None, drawstyle="default"):
    return dict(x=np.ascontiguousarray(x, dtype=np.float64),
                y=np.ascontiguousarray(y, dtype=np.float64),
                label=str(label), color=str(color), linestyle=str(linestyle),
                linewidth=float(linewidth), marker=str(marker), markersize=float(markersize),
                mfc=None if mfc is None else str(mfc),
                mec=None if mec is None else str(mec), mew=float(mew),
                alpha=None if alpha is None else float(alpha), drawstyle=str(drawstyle))


def _plot_args(args, fmt):
    if len(args) == 1:
        return args[0], None, fmt
    if len(args) == 2:
        return args[0], args[1], fmt
    if len(args) == 3:
        return args[0], args[1], fmt or args[2]
    raise TypeError("plot expects y, (x, y) or (x, y, fmt)")


def _parse_fmt(fmt):
    """Split a matplotlib fmt string into (colour, linestyle, marker)."""
    color_map = {"b": "blue", "g": "green", "r": "red", "c": "cyan",
                 "m": "magenta", "y": "yellow", "k": "black", "w": "white"}
    markers = set("os^v<>Dx+.*hpH")
    color, style, mark = None, "", ""
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch in color_map and color is None:
            color = color_map[ch]
            i += 1
        elif ch == "-" and i + 1 < len(fmt) and fmt[i + 1] in "-.":
            style = "--" if fmt[i + 1] == "-" else "-."
            i += 2
        elif ch == "-":
            style, i = "-", i + 1
        elif ch in ":.":
            style, i = ":", i + 1
        elif ch in markers:
            mark, i = ch, i + 1
        else:
            i += 1
    return color, style, mark


def _log_bounds(lo, hi, scale, extent):
    """Log axes can only cover positive data; the lower bound climbs to the
    smallest positive sample when the data crosses zero."""
    lo, hi = float(lo), float(hi)
    if scale != "log":
        return (lo, hi)
    positive = [float(v) for v in extent if v > 0]
    lo = max(lo, min(positive)) if positive else 1e-10
    if hi <= lo:
        hi = lo * 10.0
    return (lo, hi)


def _line_colors(colors, n):
    if colors is None:
        return [_CYCLE[0]] * n
    if isinstance(colors, str):
        return [colors] * n
    vals = [str(c) for c in np.asarray(colors, dtype=object).ravel()]
    if len(vals) != n:
        raise ValueError("colors must be a single colour or one per segment")
    return vals


def _line_styles(styles, n):
    if styles is None:
        return ["-"] * n
    if isinstance(styles, str):
        return [styles] * n
    vals = [str(s) for s in np.asarray(styles, dtype=object).ravel()]
    if len(vals) != n:
        raise ValueError("linestyles must be a single style or one per segment")
    return vals


def _as_f64(v):
    return np.ascontiguousarray(np.asarray(v, dtype=np.float64).ravel())


def _band(xs, ys, color, alpha):
    return dict(x=_as_f64(xs), y=_as_f64(ys), color=str(color),
                alpha=None if alpha is None else float(alpha))


def _runs(x, y1, y2, where):
    """Split the curve into contiguous runs where `where` is true."""
    if where is None:
        mask = np.ones(x.size, dtype=bool)
    else:
        mask = np.asarray(where, dtype=bool).ravel()
        if mask.size != x.size:
            raise ValueError("where must have one entry per point")
    runs = []
    start = None
    for i, on in enumerate(mask):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append((x[start:i], y1[start:i], y2[start:i]))
            start = None
    if start is not None:
        runs.append((x[start:], y1[start:], y2[start:]))
    return runs


def _fill(values, n):
    a = np.asarray(values, dtype=np.float64).ravel()
    if a.size == 1:
        return np.full(n, float(a[0]))
    if a.size != n:
        raise ValueError(f"expected a scalar or {n} values, got {a.size}")
    return np.ascontiguousarray(a)


def _bar_colors(color, n):
    if color is None:
        return []
    if isinstance(color, str):
        return [color]
    return [str(v) for v in np.asarray(color, dtype=object).ravel()]


def _sizes(s, n):
    if s is None:
        return np.full(n, 36.0)
    a = np.asarray(s, dtype=np.float64)
    if a.ndim == 0:
        return np.full(n, max(float(a), 0.0))
    a = a.ravel()
    if a.size != n:
        raise ValueError("s must be a scalar or have one value per point")
    return np.ascontiguousarray(np.clip(a, 0.0, None))


def _scatter_colors(c, n):
    """Split `c` into (numeric values for cmap, explicit colour strings)."""
    if c is None:
        return None, []
    if isinstance(c, str):
        return None, [c]
    a = np.asarray(c)
    if a.dtype.kind in "fiu":
        v = np.asarray(a, dtype=np.float64).ravel()
        if v.size == 1:
            v = np.full(n, float(v[0]))
        if v.size != n:
            raise ValueError("c must be a single value or have one value per point")
        return np.ascontiguousarray(v), []
    seq = list(a.ravel())
    if len(seq) == 1:
        seq = seq * n
    if len(seq) != n:
        raise ValueError("c must be a single colour or one colour per point")
    return None, [str(v) for v in seq]


def _mesh_args(args):
    if len(args) == 1:
        x = y = None
        z = args[0]
    elif len(args) == 3:
        x, y, z = args
    else:
        raise TypeError("pcolormesh expects Z or X, Y, Z")
    z = np.asarray(z, dtype=np.float64)
    if z.ndim != 2:
        raise ValueError("pcolormesh expects a 2-D Z array")
    rows, cols = z.shape
    if x is None:
        return np.arange(cols + 1.0), np.arange(rows + 1.0), z, True
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    edges = x.size == cols + 1 and y.size == rows + 1
    if not edges and (x.size != cols or y.size != rows):
        raise ValueError("expected len(X) == Z.shape[1] and len(Y) == Z.shape[0], "
                         "or one extra edge per axis")
    if not edges and (x.size < 2 or y.size < 2):
        raise ValueError("pcolormesh needs at least two cells")
    return x, y, z, edges


def _err_pair(err, n, name):
    if err is None:
        z = np.zeros(n)
        return z, z.copy()
    a = np.asarray(err, dtype=np.float64)
    if a.ndim == 0:
        v = np.full(n, abs(float(a)))
        return v, v.copy()
    if a.shape == (n,):
        v = np.ascontiguousarray(np.abs(a))
        return v, v.copy()
    if a.shape == (2, n):
        return (np.ascontiguousarray(np.abs(a[0])),
                np.ascontiguousarray(np.abs(a[1])))
    raise ValueError(f"{name} must be a scalar, a length-{n} array, or shape (2, {n})")


def _levels(z, levels):
    lo, hi = float(np.nanmin(z)), float(np.nanmax(z))
    if not hi > lo:
        hi = lo + 1.0
    if levels is None:
        return [float(v) for v in np.linspace(lo, hi, 7)]
    if isinstance(levels, (int, np.integer)):
        if levels < 2:
            raise ValueError("levels must be at least 2")
        return [float(v) for v in np.linspace(lo, hi, int(levels))]
    lv = np.atleast_1d(np.asarray(levels, dtype=np.float64)).ravel()
    if lv.size < 2:
        raise ValueError("levels needs at least two entries")
    return [float(v) for v in np.sort(lv)]


def _colors(colors):
    if colors is None:
        return []
    if isinstance(colors, str):
        return [colors]
    return [str(c) for c in colors]


def _contour_args(args, levels):
    if len(args) == 1:
        (z,) = args
        x = y = None
    elif len(args) == 2:
        z, levels = args
        x = y = None
    elif len(args) == 3:
        x, y, z = args
    elif len(args) == 4:
        x, y, z, levels = args
    else:
        raise TypeError("contour expects Z or X, Y, Z, optionally followed by levels")
    z = np.asarray(z, dtype=np.float64)
    if z.ndim != 2:
        raise ValueError("contour expects a 2-D Z array")
    rows, cols = z.shape
    if x is None:
        x, y = np.arange(cols, dtype=np.float64), np.arange(rows, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim == 2 or y.ndim == 2:
        if x.shape != z.shape or y.shape != z.shape:
            raise ValueError("2-D X and Y must match Z's shape")
        # meshgrid output: keep the 1-D coordinates when the grid is rectilinear.
        if not (np.allclose(x, x[0:1, :]) and np.allclose(y, y[:, 0:1])):
            raise NotImplementedError("only rectilinear X/Y grids are supported")
        x, y = x[0, :], y[:, 0]
    x, y = x.ravel(), y.ravel()
    if x.size != cols or y.size != rows:
        raise ValueError("expected len(X) == Z.shape[1] and len(Y) == Z.shape[0]")
    return (np.ascontiguousarray(x), np.ascontiguousarray(y),
            np.ascontiguousarray(z), levels)


class ContourSet:
    """Handle returned by `Axes.contour` / `Axes.contourf`."""

    def __init__(self, entry): self._e = entry

    @property
    def levels(self): return list(self._e["levels"])

    def get_cmap(self): return self._e["cmap"]
    def set_cmap(self, cmap): self._e["cmap"] = cmap
    def set_clim(self, vmin=None, vmax=None): pass

    def _colorbar_spec(self):
        lv = self._e["levels"]
        return dict(cmap=self._e["cmap"], vmin=lv[0], vmax=lv[-1])


class AxesImage:
    """Handle returned by `Axes.imshow`, for later tweaks."""

    def __init__(self, entry): self._e = entry

    def get_array(self): return self._e["data"]
    def set_data(self, X): self._e["data"] = _as_image(X)
    def get_cmap(self): return self._e["cmap"]
    def set_cmap(self, cmap): self._e["cmap"] = cmap
    def set_extent(self, extent): self._e["extent"] = tuple(float(v) for v in extent)

    def set_clim(self, vmin=None, vmax=None):
        self._e["vmin"], self._e["vmax"] = vmin, vmax

    def _colorbar_spec(self):
        data = self._e["data"]
        lo = self._e["vmin"] if self._e["vmin"] is not None else float(np.nanmin(data))
        hi = self._e["vmax"] if self._e["vmax"] is not None else float(np.nanmax(data))
        return dict(cmap=self._e["cmap"], vmin=lo, vmax=hi)


class Colorbar:
    """Handle returned by `Figure.colorbar`."""

    def __init__(self, entry): self._e = entry

    def set_label(self, label): self._e["label"] = str(label)
    def get_label(self): return self._e["label"]


class Figure:
    def __init__(self, figsize=(6.4, 4.8)):
        self.figsize, self.grid, self.axes, self._cur = figsize, (1, 1), [], None
        self._colorbar = None

    def add_subplot(self, nrows=1, ncols=1, index=1):
        """index is 1-based, row-major (matplotlib convention)."""
        if (nrows, ncols) != self.grid:
            if self.axes:
                raise ValueError("mixed subplot grids are not supported yet")
            self.grid = (nrows, ncols)
        ax = next((a for a in self.axes if a.pos == index - 1), None) or Axes(index - 1)
        if ax not in self.axes:
            self.axes.append(ax)
        ax._fig = self
        self._cur = ax
        return ax

    def subplots(self, nrows=1, ncols=1):
        axs = [self.add_subplot(nrows, ncols, i + 1) for i in range(nrows * ncols)]
        return axs[0] if len(axs) == 1 else np.array(axs, dtype=object).reshape(nrows, ncols).squeeze()

    def gca(self):
        return self._cur or self.add_subplot()

    def add_axes(self, rect=None, **kwargs):
        """Compatibility shim: `rect` is stored but layout stays on the grid."""
        rows, cols = self.grid
        ax = self.add_subplot(rows, cols, len(self.axes) + 1)
        ax.set_position(rect if rect is not None else (0.0, 0.0, 1.0, 1.0))
        return ax

    def draw_without_rendering(self): return None
    def draw(self, *args, **kwargs): return None

    # Layout requests are accepted but ignored: panels always fill their gridspec
    # cells, so there are no margins to negotiate.
    def tight_layout(self, **kwargs): return None
    def subplots_adjust(self, **kwargs): return None
    def set_layout_engine(self, engine=None, **kwargs): self.layout_engine = engine
    def get_layout_engine(self): return getattr(self, "layout_engine", None)
    def get_axes(self): return list(self.axes)
    def get_dpi(self): return DPI
    def get_size_inches(self): return self.figsize

    def set_size_inches(self, width, height=None):
        if height is None:
            width, height = width
        self.figsize = (float(width), float(height))

    def colorbar(self, mappable=None, ax=None, label=""):
        """Reserve a strip beside the single axes showing `mappable`'s scale."""
        if self.grid != (1, 1) or len(self.axes) != 1:
            raise NotImplementedError("colorbar needs a figure with a single axes")
        axes = ax or self.axes[0]
        if mappable is not None:
            spec = mappable._colorbar_spec()
        elif axes.contours:
            spec = ContourSet(axes.contours[-1])._colorbar_spec()
        elif axes.images:
            spec = AxesImage(axes.images[-1])._colorbar_spec()
        else:
            raise ValueError("colorbar needs an image or contour to describe")
        self.grid = (1, 2)
        self._colorbar = dict(cmap=str(spec["cmap"]), vmin=float(spec["vmin"]),
                              vmax=float(spec["vmax"]), label=str(label))
        return Colorbar(self._colorbar)

    def _colorbar_panel(self):
        cb = self._colorbar
        return dict(pos=1, series=[], texts=[], title="", xlabel="", ylabel="",
                    legend=False, xlim=None, ylim=None, annotations=[], images=[],
                    contours=[], errors=[], scatter=[], bars=[], bands=[],
                    x_log=False, y_log=False, grid=False, aspect=None, axis_off=False,
                    colorbar=(cb["cmap"], cb["vmin"], cb["vmax"], cb["label"]))

    def savefig(self, filepath, format=None, dpi=None, bbox_inches=None, transparent=False):
        """Write this figure. `format` overrides the file extension; `dpi` scales
        the pixel size; `bbox_inches="tight"` crops to the drawn content."""
        w, h = (round(v * (dpi or DPI)) for v in self.figsize)
        fmt = format.lower().lstrip(".") if format else None
        if fmt is not None and fmt not in _FORMATS:
            raise ValueError(f"unsupported format: {format!r} (use 'png' or 'svg')")
        if bbox_inches not in (None, "tight"):
            raise ValueError(f"unsupported bbox_inches: {bbox_inches!r} (use 'tight')")
        panels = [a._panel() for a in self.axes if a.visible and not a._removed]
        if self._colorbar is not None:
            panels.append(self._colorbar_panel())
        save(str(filepath), (w, h), self.grid, panels,
             format=fmt, transparent=bool(transparent), bbox_inches=bbox_inches)


_fig = None


def figure(figsize=(6.4, 4.8)):
    global _fig
    _fig = Figure(figsize)
    return _fig


def gcf(): return _fig or figure()
def gca(): return gcf().gca()
def close(*_): global _fig; _fig = None


def subplots(nrows=1, ncols=1, figsize=(6.4, 4.8)):
    fig = figure(figsize)
    return fig, fig.subplots(nrows, ncols)


def subplot(nrows, ncols, index): return gcf().add_subplot(nrows, ncols, index)
def plot(*args, **kwargs): return gca().plot(*args, **kwargs)
def xlabel(text): gca().set_xlabel(text)
def ylabel(text): gca().set_ylabel(text)
def title(text): gca().set_title(text)
def text(x, y, s, color="black", fontsize=12, ha="left", va="baseline"):
    gca().text(x, y, s, color=color, fontsize=fontsize, ha=ha, va=va)
def imshow(X, cmap=None, vmin=None, vmax=None, extent=None, origin="upper",
           interpolation=None, aspect=None, alpha=None):
    return gca().imshow(X, cmap=cmap, vmin=vmin, vmax=vmax, extent=extent, origin=origin,
                        interpolation=interpolation, aspect=aspect, alpha=alpha)


def xscale(*args, **kwargs): return gca().set_xscale(*args, **kwargs)
def yscale(*args, **kwargs): return gca().set_yscale(*args, **kwargs)
def semilogx(*args, **kwargs): return gca().semilogx(*args, **kwargs)
def semilogy(*args, **kwargs): return gca().semilogy(*args, **kwargs)
def loglog(*args, **kwargs): return gca().loglog(*args, **kwargs)
def hlines(*args, **kwargs): return gca().hlines(*args, **kwargs)
def vlines(*args, **kwargs): return gca().vlines(*args, **kwargs)
def step(*args, **kwargs): return gca().step(*args, **kwargs)
def stairs(*args, **kwargs): return gca().stairs(*args, **kwargs)
def tight_layout(*args, **kwargs): return gcf().tight_layout(*args, **kwargs)
def subplots_adjust(*args, **kwargs): return gcf().subplots_adjust(*args, **kwargs)
def hist(*args, **kwargs): return gca().hist(*args, **kwargs)
def fill_between(*args, **kwargs): return gca().fill_between(*args, **kwargs)
def fill_betweenx(*args, **kwargs): return gca().fill_betweenx(*args, **kwargs)
def fill(*args, **kwargs): return gca().fill(*args, **kwargs)
def axhline(*args, **kwargs): return gca().axhline(*args, **kwargs)
def axvline(*args, **kwargs): return gca().axvline(*args, **kwargs)
def axhspan(*args, **kwargs): return gca().axhspan(*args, **kwargs)
def axvspan(*args, **kwargs): return gca().axvspan(*args, **kwargs)
def bar(*args, **kwargs): return gca().bar(*args, **kwargs)
def barh(*args, **kwargs): return gca().barh(*args, **kwargs)
def pcolormesh(*args, **kwargs): return gca().pcolormesh(*args, **kwargs)
def pcolor(*args, **kwargs): return gca().pcolormesh(*args, **kwargs)
def pcolorfast(*args, **kwargs): return gca().pcolormesh(*args, **kwargs)


def annotate(text, xy, xytext=None, arrowprops=None, color="black", fontsize=12):
    gca().annotate(text, xy, xytext=xytext, arrowprops=arrowprops, color=color,
                   fontsize=fontsize)


def scatter(x, y, s=None, c=None, alpha=None, cmap=None, label="", marker="o", vmin=None,
            vmax=None, **kwargs):
    return gca().scatter(x, y, s=s, c=c, alpha=alpha, cmap=cmap, label=label, marker=marker,
                         vmin=vmin, vmax=vmax)


def axes(*args, **kwargs):
    """Compatibility shim: plt_rs lays out subplots on a grid, so this returns the
    current axes (creating one if needed)."""
    return gca()


def show(*args, **kwargs): pass

def draw(*args, **kwargs): pass

def pause(*args, **kwargs): pass

def ion(*args, **kwargs): pass

def ioff(*args, **kwargs): pass


def errorbar(x, y, yerr=None, xerr=None, fmt="", ecolor=None, elinewidth=None, capsize=None,
             label="", color=None, **kwargs):
    return gca().errorbar(x, y, yerr=yerr, xerr=xerr, fmt=fmt, ecolor=ecolor,
                          elinewidth=elinewidth, capsize=capsize, label=label, color=color)


def colorbar(mappable=None, ax=None, label=""):
    return gcf().colorbar(mappable, ax=ax, label=label)


def contour(*args, levels=None, colors=None, cmap=None, linewidths=None, alpha=None):
    return gca().contour(*args, levels=levels, colors=colors, cmap=cmap,
                         linewidths=linewidths, alpha=alpha)


def contourf(*args, levels=None, colors=None, cmap=None, alpha=None):
    return gca().contourf(*args, levels=levels, colors=colors, cmap=cmap, alpha=alpha)


def xlim(lo, hi): gca().set_xlim(lo, hi)
def ylim(lo, hi): gca().set_ylim(lo, hi)
def legend(): gca().legend()
def grid(*args, **kwargs): return gca().grid(*args, **kwargs)
def tick_params(*args, **kwargs): return gca().tick_params(*args, **kwargs)
def axline(*args, **kwargs): return gca().axline(*args, **kwargs)
rcParams = {
    "figure.figsize": (6.4, 4.8),
    "figure.dpi": 100.0,
    "lines.linewidth": 1.5,
    "lines.markersize": 6.0,
    "font.size": 10.0,
    "axes.labelsize": 10.0,
    "axes.titlesize": 12.0,
    "legend.fontsize": 10.0,
}
_RC_DEFAULTS = dict(rcParams)


def rc(group=None, **kwargs):
    """Record rc settings. `rc("lines", linewidth=2)` maps to `lines.linewidth`."""
    if group is None or isinstance(group, dict):
        rcParams.update(group or kwargs)
        return None
    for key, value in kwargs.items():
        rcParams[f"{group}.{key}"] = value
    return None


@contextmanager
def rc_context(rc=None, fname=None):
    """Apply rc overrides for the duration of the block, then restore them."""
    saved = dict(rcParams)
    if rc is not None:
        rcParams.update(rc)
    try:
        yield rcParams
    finally:
        rcParams.clear()
        rcParams.update(saved)


def rcdefaults():
    rcParams.clear()
    rcParams.update(_RC_DEFAULTS)


def savefig(filepath, format=None, dpi=None, bbox_inches=None, transparent=False):
    gcf().savefig(filepath, format=format, dpi=dpi, bbox_inches=bbox_inches, transparent=transparent)
