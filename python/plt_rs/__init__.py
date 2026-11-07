"""plt_rs: minimal matplotlib-like API, rendered entirely in Rust."""
import numpy as np
from ._core import save

_CYCLE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
DPI = 100
_FORMATS = ("png", "svg")


class Axes:
    def __init__(self, pos):
        self.pos, self.lines, self.texts = pos, [], []
        self.images, self.annotations = [], []
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


class Figure:
    def __init__(self, figsize=(6.4, 4.8)):
        self.figsize, self.grid, self.axes, self._cur = figsize, (1, 1), [], None

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

    def savefig(self, filepath, format=None, dpi=None, bbox_inches=None, transparent=False):
        """Write this figure. `format` overrides the file extension; `dpi` scales
        the pixel size; `bbox_inches="tight"` crops to the drawn content."""
        w, h = (round(v * (dpi or DPI)) for v in self.figsize)
        fmt = format.lower().lstrip(".") if format else None
        if fmt is not None and fmt not in _FORMATS:
            raise ValueError(f"unsupported format: {format!r} (use 'png' or 'svg')")
        if bbox_inches not in (None, "tight"):
            raise ValueError(f"unsupported bbox_inches: {bbox_inches!r} (use 'tight')")
        save(str(filepath), (w, h), self.grid, [a._panel() for a in self.axes],
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


def xlim(lo, hi): gca().set_xlim(lo, hi)
def ylim(lo, hi): gca().set_ylim(lo, hi)
def legend(): gca().legend()
def savefig(filepath, format=None, dpi=None, bbox_inches=None, transparent=False):
    gcf().savefig(filepath, format=format, dpi=dpi, bbox_inches=bbox_inches, transparent=transparent)
