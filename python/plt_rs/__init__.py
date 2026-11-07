"""plt_rs: minimal matplotlib-like API, rendered entirely in Rust."""
import numpy as np
from ._core import save

_CYCLE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
# Only the one-letter colors plt_rs can render are honoured in fmt strings.
_FMT_COLORS = {"b": "blue", "g": "green", "r": "red", "k": "black"}
DPI = 100
_FORMATS = ("png", "svg")


class Axes:
    def __init__(self, pos):
        self.pos, self.lines, self.texts = pos, [], []
        self.images, self.annotations = [], []
        self.contours = []
        self.errors = []
        self.scatter_pts = []
        self.aspect = None
        self.title = self.xlabel = self.ylabel = ""
        self.show_legend, self.xlim, self.ylim = False, None, None

    def plot(self, x, y=None, label="", color=None):
        if y is None:
            x, y = np.arange(len(x)), x
        c = color or _CYCLE[len(self.lines) % len(_CYCLE)]
        self.lines.append((np.ascontiguousarray(x, dtype=np.float64),
                           np.ascontiguousarray(y, dtype=np.float64), label, c))

    def set_aspect(self, aspect, adjustable=None, anchor=None, share=False):
        self.aspect = _norm_aspect(aspect)

    def get_aspect(self): return self.aspect

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
            self.lines.append((np.ascontiguousarray(x), np.ascontiguousarray(y), label, c))
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

    def _panel(self):
        return dict(pos=self.pos, series=self.lines, texts=self.texts, title=self.title,
                    xlabel=self.xlabel, ylabel=self.ylabel, legend=self.show_legend,
                    xlim=self.xlim, ylim=self.ylim, annotations=self.annotations,
                    aspect=self.aspect,
                    contours=[(c["x"], c["y"], c["z"], c["levels"], c["colors"], c["cmap"],
                               c["filled"]) for c in self.contours],
                    errors=self.errors,
                    scatter=[dict(x=e["x"], y=e["y"], sizes=e["sizes"], values=e["values"],
                                  cmap=e["cmap"], clim=e["clim"], colors=e["colors"],
                                  marker=e["marker"], alpha=e["alpha"])
                             for e in self.scatter_pts],
                    colorbar=None,
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
        self._cur = ax
        return ax

    def subplots(self, nrows=1, ncols=1):
        axs = [self.add_subplot(nrows, ncols, i + 1) for i in range(nrows * ncols)]
        return axs[0] if len(axs) == 1 else np.array(axs, dtype=object).reshape(nrows, ncols).squeeze()

    def gca(self):
        return self._cur or self.add_subplot()

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
                    contours=[], errors=[], scatter=[], aspect=None,
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
        panels = [a._panel() for a in self.axes]
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
def plot(x, y=None, label="", color=None): gca().plot(x, y, label, color)
def xlabel(text): gca().set_xlabel(text)
def ylabel(text): gca().set_ylabel(text)
def title(text): gca().set_title(text)
def text(x, y, s, color="black", fontsize=12, ha="left", va="baseline"):
    gca().text(x, y, s, color=color, fontsize=fontsize, ha=ha, va=va)
def imshow(X, cmap=None, vmin=None, vmax=None, extent=None, origin="upper",
           interpolation=None, aspect=None, alpha=None):
    return gca().imshow(X, cmap=cmap, vmin=vmin, vmax=vmax, extent=extent, origin=origin,
                        interpolation=interpolation, aspect=aspect, alpha=alpha)


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
def savefig(filepath, format=None, dpi=None, bbox_inches=None, transparent=False):
    gcf().savefig(filepath, format=format, dpi=dpi, bbox_inches=bbox_inches, transparent=transparent)
