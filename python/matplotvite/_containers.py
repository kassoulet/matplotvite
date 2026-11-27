"""Artist handles and containers returned by the plotting calls."""
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

from ._helpers import (
    _is_rgb,
    _noop_method,
    _norm_color,
    _state_setter,
    _TextLabel,
    get_cmap,
)


class _Wedge:
    """Placeholder wedge returned by `pie`."""

    def __init__(self, color=None, center=(0.0, 0.0), r=1.0,
                 theta1=0.0, theta2=360.0, band=None, label=""):
        self._color = color
        self._band = band
        self._label = str(label or "")
        self._gid = None
        self._zorder = 1
        self.center = (float(center[0]), float(center[1]))
        self.r = float(r)
        self.theta1, self.theta2 = float(theta1), float(theta2)

    def set_facecolor(self, c):
        self._color = str(c)
        return self

    def set_edgecolor(self, c): return self
    def set_color(self, c): return self.set_facecolor(c)
    def get_facecolor(self): return self._color
    def set_gid(self, gid):
        self._gid = "" if gid is None else str(gid)
        if self._band is not None:
            self._band["gid"] = self._gid
        return self
    def get_gid(self): return self._gid
    def get_label(self): return self._label
    def get_zorder(self): return self._zorder
    set_zorder = _state_setter(
        "_zorder", 'zorder', 'zorder')
    def set_agg_filter(self, value): return self
    def set_rasterized(self, value): return self
    def set(self, **kwargs):
        if "ec" in kwargs or "edgecolor" in kwargs:
            self.set_edgecolor(kwargs.get("ec", kwargs.get("edgecolor")))
        return self


class HandlerTuple:
    """Legend handler that packs tuple entries into one row; drawing is a no-op."""

    def __init__(self, ndivide=None, pad=None, **kwargs):
        self.ndivide, self.pad, self.kwargs = ndivide, pad, kwargs


class HandlerLineCollection:
    """Legend handler that draws a line-collection sample."""
    def __init__(self, **kwargs): self.kwargs = kwargs


class _PieResult:
    """Matplotlib's PieResult: unpackable and attribute-accessible."""

    def __init__(self, wedges, texts, autotexts, values=None, fracs=None):
        self.wedges, self.texts, self.autotexts = wedges, texts, autotexts
        self.values = np.asarray([] if values is None else values, dtype=float)
        self.fracs = np.asarray([] if fracs is None else fracs, dtype=float)

    def __iter__(self): return iter((self.wedges, self.texts, self.autotexts))

    def add_texts(self, texts):
        """Append label `.Text` instances to the container."""
        self.texts.extend(texts)
        return None


class _LegendHandle:
    """Return value of `legend`, with the mutable frame patch."""

    def __init__(self):
        self.legendPatch = Rectangle((0, 0), 1, 1)
        self._zorder = 5

    def get_zorder(self): return self._zorder
    def set_zorder(self, zorder): self._zorder = int(zorder)
    def get_frame(self): return self.legendPatch
    def get_title(self): return _TextLabel()
    def get_lines(self): return []
    def set_draggable(self, value=True, **kwargs): return self


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

    def get_xdata(self):
        """The rectangle's four corners and closing vertex, as Matplotlib's box."""
        x, w = self.get_x(), self.get_width()
        return np.asarray([x, x, x + w, x + w, x], dtype=float)

    def get_ydata(self):
        y, h = self.get_y(), self.get_height()
        return np.asarray([y, y + h, y + h, y, y], dtype=float)

    def get_facecolor(self):
        return self._axes.bars[self._group]["colors"][:1] or ["#1f77b4"]

    def get_edgecolor(self):
        edges = self._axes.bars[self._group].get("edgecolor")
        return edges[0] if edges and len(edges) == 1 else edges

    def get_color(self):
        return self.get_facecolor()[0]

    def get_zorder(self): return 1
    def set_zorder(self, zorder): return self
    def set_agg_filter(self, value): return self
    def set_rasterized(self, value): return self

    def set_x(self, x):
        self._axes.bars[self._group]["left"][self._index] = float(x)
        return self

    def set_y(self, y):
        self._axes.bars[self._group]["bottom"][self._index] = float(y)
        return self

    def set_width(self, w):
        self._axes.bars[self._group]["width"][self._index] = float(w)
        return self

    def set_height(self, h):
        self._axes.bars[self._group]["height"][self._index] = float(h)
        return self

    def set_facecolor(self, c):
        self._set("colors", [c if isinstance(c, str) else _norm_color(c)])
        return self

    def set_color(self, c):
        return self.set_facecolor(c)

    def set_edgecolor(self, c):
        group = self._axes.bars[self._group]
        count = len(group["left"])
        current = group.get("edgecolor")
        if isinstance(current, str):
            current = [current] * count
        elif current is None:
            current = ["none"] * count
        else:
            current = list(current)
            if len(current) != count:
                current = [current[0] if current else "none"] * count
        current[self._index] = c if isinstance(c, str) else _norm_color(c)
        group["edgecolor"] = current
        return self

    def set_alpha(self, a):
        self._set("alpha", float(a))
        return self

    def set_hatch(self, hatch):
        # Keep hatch styling on the handle; the Rust panel record has no bar
        # hatch field, and adding one would make panel extraction reject it.
        self._hatch = hatch
        return self

    def remove(self):
        self._axes.bars[self._group]["height"][self._index] = 0.0
        self._axes.bars[self._group]["width"][self._index] = 0.0


class _LineGroupHandle(list[Any]):
    """A group of line handles that applies a setter to every member."""

    def set_linewidth(self, width):
        for handle in self:
            handle.set_linewidth(width)
        return self

    def set_color(self, color):
        for handle in self:
            handle.set_color(color)
        return self

    def set_linestyle(self, linestyle):
        for handle in self:
            handle.set_linestyle(linestyle)
        return self

    def set_visible(self, visible): return self


class _StemContainer:
    """`markerline`, `stemlines` and `baseline`, unpackable as Matplotlib's."""

    def __init__(self, markerline, stemlines, baseline):
        self.markerline, self.stemlines, self.baseline = markerline, stemlines, baseline

    def __iter__(self):
        return iter((self.markerline, self.stemlines, self.baseline))


class _BarContainer(list[object]):
    """List of `_BarHandle`, matching matplotlib's `BarContainer`."""

    # `list` is unhashable; Matplotlib's container is not, so restore the
    # identity hash while keeping the list behaviour.
    __hash__: ClassVar[Any] = object.__hash__

    def __init__(self, handles, label=""):
        super().__init__(handles)
        self.label = label

    def get_label(self): return str(self.label)
    def set_label(self, label): self.label = str(label)

    @property
    def patches(self):
        return list(self)


class _StreamplotSet:
    """Lines and arrows returned by `Axes.streamplot`."""

    def __init__(self, lines, arrows):
        self.lines = lines
        self.arrows = arrows


class _QuiverHandle:
    """Handle for one `quiver` collection."""

    def __init__(self, entry): self._e = entry

    def get_offsets(self):
        return np.column_stack([self._e["x"], self._e["y"]])

    def get_U(self): return self._e["u"]
    def get_V(self): return self._e["v"]
    def get_facecolor(self): return list(self._e["colors"])


class _ScatterHandle:
    """Handle for one scatter collection, including its color scale."""

    def __init__(self, entry, axes=None):
        self._e = entry
        self.axes = axes

    def get_offsets(self):
        return np.column_stack([self._e["x"], self._e["y"]])

    def get_sizes(self): return self._e["sizes"]

    def set_sizes(self, sizes):
        self._e["sizes"] = np.ascontiguousarray(_as_f64(sizes))
        return self

    def set_markerfacecolor(self, color):
        self._e["colors"] = [_norm_color(color)]
        return self

    set_facecolor = set_markerfacecolor

    set_markeredgecolor = _noop_method(
        "set_markeredgecolor", 'self, color', warn='PathCollection.set_markeredgecolor', returns_self=True)

    def set_markersize(self, size):
        self._e["sizes"] = np.full(np.asarray(self._e["x"]).size, float(size) ** 2)
        return self

    def set_alpha(self, alpha):
        self._e["alpha"] = float(alpha)
        return self

    @property
    def cmap(self): return get_cmap(self._e["cmap"])

    def set_urls(self, urls): self._urls = list(urls)
    def get_urls(self): return getattr(self, "_urls", None)

    def legend_elements(self, prop="colors", num="auto", alpha=None, **kwargs):
        """Proxy handles and labels for a numeric color or size scale."""
        values = self._e["values"] if prop == "colors" else self._e["sizes"]
        if values is None:
            values = np.arange(np.asarray(self._e["x"]).size)
        vals = _as_f64(values)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            return [], []
        count = min(5, vals.size) if num == "auto" else max(1, int(num))
        picks = vals[np.linspace(0, vals.size - 1, count).astype(int)]
        return [self] * picks.size, [f"{value:g}" for value in picks]

    def get_array(self): return self._e["values"]
    def get_cmap(self): return self._e["cmap"]

    def get_clim(self):
        clim = self._e["clim"]
        return tuple(clim) if clim is not None else (None, None)

    def set_clim(self, vmin=None, vmax=None):
        if vmin is not None or vmax is not None:
            self._e["clim"] = (vmin, vmax)
        return self

    def _colorbar_spec(self):
        values = self._e["values"]
        if values is None:
            raise ValueError("scatter needs numeric c values for a colorbar")
        vals = _as_f64(values)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            raise ValueError("scatter has no finite c values for a colorbar")
        clim = self._e["clim"]
        lo, hi = (float(vals.min()), float(vals.max())) if clim is None else clim
        lo = float(vals.min()) if lo is None else float(lo)
        hi = float(vals.max()) if hi is None else float(hi)
        if not hi > lo:
            lo, hi = lo - 0.5, lo + 0.5
        return dict(cmap=self._e["cmap"] or rcParams.get("image.cmap", "viridis"),
                    vmin=lo, vmax=hi)


class _HexbinHandle:
    """Handle for the hexagonal cells drawn by `hexbin`."""

    def __init__(self, values, offsets, colors, cmap):
        self._values = np.asarray(values, dtype=np.float64)
        self._offsets = np.asarray(offsets, dtype=np.float64).reshape(-1, 2)
        self._colors = list(colors)
        self._cmap = cmap

    def get_array(self): return self._values
    def get_offsets(self): return self._offsets
    def get_facecolor(self): return list(self._colors)
    def get_cmap(self): return self._cmap

    set_clim = _noop_method("set_clim", 'self, vmin=None, vmax=None')

    def _colorbar_spec(self):
        vals = self._values[np.isfinite(self._values)]
        lo = float(vals.min()) if vals.size else 0.0
        hi = float(vals.max()) if vals.size else 1.0
        return dict(cmap=self._cmap, vmin=lo, vmax=hi)


class _ViolinBody:
    """Handle for one filled violin polygon."""

    def __init__(self, entry, facecolor=None):
        self._e = entry
        self._facecolor = facecolor

    def get_facecolor(self): return self._facecolor or self._e["color"]

    def set_facecolor(self, color):
        self._facecolor = _norm_color(color)
        self._e["color"] = self._facecolor
        return self

    def get_alpha(self): return self._e["alpha"]

    def set_alpha(self, alpha):
        self._e["alpha"] = None if alpha is None else float(alpha)
        return self

    set_edgecolor = _noop_method(
        "set_edgecolor", 'self, color', warn='ViolinBody.set_edgecolor', returns_self=True)

    set_linewidth = _noop_method(
        "set_linewidth", 'self, width', warn='ViolinBody.set_linewidth', returns_self=True)

    def get_paths(self): return [self._e]


class _GridLine:
    """One axis gridline handle, backed by the axes' grid state."""

    def __init__(self, axes, axis, which):
        self.axes = axes
        self._axis = axis
        self._which = which

    def _prefix(self):
        return "grid_" if self._which == "major" else "grid_minor_"

    def _visible_attr(self):
        return "show_grid" if self._which == "major" else "grid_minor_show"

    def get_visible(self):
        return bool(getattr(self.axes, self._visible_attr(), False))

    def set_visible(self, visible):
        setattr(self.axes, self._visible_attr(), bool(visible))
        return self

    def get_color(self):
        return getattr(self.axes, f"{self._prefix()}color", None)

    def set_color(self, color):
        setattr(self.axes, f"{self._prefix()}color", _norm_color(color))
        return self

    def get_linewidth(self):
        return getattr(self.axes, f"{self._prefix()}linewidth", None)

    def set_linewidth(self, width):
        setattr(self.axes, f"{self._prefix()}linewidth", float(width))
        return self

    def get_alpha(self):
        return getattr(self.axes, f"{self._prefix()}alpha", None)

    def set_alpha(self, alpha):
        setattr(self.axes, f"{self._prefix()}alpha",
                None if alpha is None else float(alpha))
        return self


class _LineHandle:
    """Mutable handle around one stored `_series` entry."""

    def __init__(self, entry, facecolor=None):
        self._e = entry
        self._facecolor = facecolor

    def get_xdata(self): return self._e["x"]
    def get_ydata(self): return self._e["y"]
    def get_color(self): return self._e["color"]

    def set_color(self, color):
        self._e["color"] = _norm_color(color)
        return self

    def get_facecolor(self): return self._facecolor

    def set_facecolor(self, color):
        self._facecolor = _norm_color(color)
        return self

    def get_linewidth(self): return self._e["linewidth"]

    def set_linewidth(self, width):
        self._e["linewidth"] = float(width)
        return self

    def get_linestyle(self): return self._e["linestyle"]

    def set_linestyle(self, linestyle):
        self._e["linestyle"] = str(linestyle)
        return self

    def get_label(self): return self._e["label"]

    def set_label(self, label):
        self._e["label"] = str(label)
        return self

    def set_marker(self, marker):
        self._e["marker"] = str(marker)
        return self

    def set_markersize(self, size):
        self._e["markersize"] = float(size)
        return self

    def set_markerfacecolor(self, color):
        self._e["mfc"] = _norm_color(color)
        return self

    def set_markeredgecolor(self, color):
        self._e["mec"] = _norm_color(color)
        return self

    def set_markeredgewidth(self, width):
        self._e["mew"] = float(width)
        return self

    def set_alpha(self, alpha):
        self._e["alpha"] = None if alpha is None else float(alpha)
        return self

    def set_drawstyle(self, drawstyle):
        self._e["drawstyle"] = str(drawstyle)
        return self

    def set_gid(self, gid):
        self._e["gid"] = "" if gid is None else str(gid)
        return self

    def get_gid(self): return self._e.get("gid", "")
    def set_zorder(self, zorder): self._e["zorder"] = int(zorder); return self
    def get_zorder(self): return self._e.get("zorder", 2)
    def set_visible(self, visible): return self
    def set_path_effects(self, effects): return self
    def set_rasterized(self, value): return self
    def set_clip_on(self, value): return self


def _call(obj, name):
    """Call an optional getter, treating broken or missing members as absent."""
    fn = getattr(obj, name, None)
    if fn is None:
        return None
    try:
        return fn()
    except Exception:
        return None


def _number(value, default):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


_FONT_SCALINGS = {
    "xx-small": 0.579, "x-small": 0.694, "small": 0.833, "medium": 1.0,
    "large": 1.2, "x-large": 1.44, "xx-large": 1.728,
    "larger": 1.2, "smaller": 0.833,
}


def _font_size(value, default=10.0):
    """Resolve numeric and named font sizes relative to `font.size`."""
    base = float(rcParams.get("font.size", 10.0))  # type: ignore[arg-type]
    if value is None:
        value = default
    if isinstance(value, str):
        scale = _FONT_SCALINGS.get(value.lower())
        if scale is not None:
            return base * scale
        value = default
    try:
        return float(value)
    except (TypeError, ValueError):
        if isinstance(default, str):
            return base * _FONT_SCALINGS.get(default.lower(), 1.0)
        return float(default)


_FONT_FAMILY_ALIASES = {
    "sans-serif": "DejaVu Sans, sans-serif",
    "sans": "DejaVu Sans, sans-serif",
    "dejavu sans": "DejaVu Sans, sans-serif",
    "dejavusans": "DejaVu Sans, sans-serif",
    "serif": "Geist Serif",
    "geist serif": "Geist Serif",
    "monospace": "Geist Mono",
    "mono": "Geist Mono",
    "geist mono": "Geist Mono",
}


def _font_family(value=None):
    """Resolve a Matplotlib font family to one of the embedded faces.

    `font.family` may be a string or a preference list; unknown names fall back
    to DejaVu Sans, the same way Matplotlib falls back when a font is missing.
    """
    if value is None:
        value = rcParams.get("font.family", ["sans-serif"])
    families = [value] if isinstance(value, str) else list(value or [])
    for family in families:
        resolved = _FONT_FAMILY_ALIASES.get(str(family).strip().lower())
        if resolved:
            return resolved
    return _FONT_FAMILY_ALIASES["sans-serif"]


def _family_override(kwargs):
    """Explicit `fontfamily=`/`family=` on an artist, or None to follow rcParams."""
    value = kwargs.get("fontfamily", kwargs.get("family", kwargs.get("fontname")))
    return None if value is None else _font_family(value)


def _numbers(value):
    if value is None:
        return []
    if isinstance(value, (int, float, np.number)):
        return [float(value)]
    try:
        return [float(v) for v in _as_f64(value)]
    except (TypeError, ValueError):
        return []


def _single_color(value, fallback=None):
    """Pick one colour from a matplotlib colour, list or colour array."""
    if value is None:
        return fallback
    try:
        if isinstance(value, np.ndarray):
            if value.ndim == 2:
                return fallback if value.shape[0] == 0 else _norm_color(value[0])
            if value.ndim == 1 and value.size in (3, 4):
                return _norm_color(value)
            return fallback if value.size == 0 else _single_color(value.ravel()[0], fallback)
        if isinstance(value, (list, tuple)):
            if not value:
                return fallback
            if len(value) in (3, 4) and all(isinstance(v, (int, float, np.number)) for v in value):
                return _norm_color(value)
            return _single_color(value[0], fallback)
        return _norm_color(value)
    except (TypeError, ValueError):
        return fallback


def _color_list(value):
    """Normalise a colour, a list of colours or an Nx4 colour array."""
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        if value.ndim == 2:
            return [_norm_color(row) for row in value]
        value = value.ravel().tolist()
    if isinstance(value, str) or _is_rgb(value):
        return [_norm_color(value)]
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_color_list(item))
        return out
    return []


class _StickyEdges:
    def __init__(self): self.x, self.y = [], []


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._artists import Rectangle
    from ._config import rcParams
    from ._plot_helpers import _as_f64
