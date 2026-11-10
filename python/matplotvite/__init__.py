"""matplotvite: minimal matplotlib-like API, rendered entirely in Rust."""
import datetime as _datetime
import hashlib as _hashlib
import math as _math
import os
import re as _re
import warnings
from contextlib import contextmanager

import numpy as np

from ._cmaps import COLORMAPS as _CMAP_DATA
from ._colors import CSS_COLORS as _CSS_COLORS
from ._core import __version__, render as _render

__all__ = (
    "Axes", "AxesImage", "Colorbar", "Colormap", "ContourSet", "DPI", "Figure", "GridSpec",
    "SubplotSpec", "Patch", "Rectangle", "Circle", "Ellipse", "Polygon", "Arc", "Wedge",
    "RegularPolygon", "FancyArrow", "FancyArrowPatch", "FancyBboxPatch", "PathPatch",
    "Annulus", "Affine2D", "Path", "Bbox", "patches", "mpatches", "mpath",
    "mtransforms", "mcolors", "colors", "mticker", "ticker", "gridspec", "lines",
    "Collection", "LineCollection", "PolyCollection", "PatchCollection", "EventCollection",
    "mcollections", "ConnectionPatch",
    "patheffects", "path_effects", "color_sequences", "cm", "colormaps",
    "annotate", "axes", "axis", "axhline", "axhspan", "axline", "axvline", "axvspan",
    "bar", "bar_label", "barh", "boxplot", "broken_barh", "close", "colorbar", "contour", "contourf",
    "draw", "errorbar", "eventplot", "figure", "figtext", "fill", "fill_between", "violinplot",
    "fill_betweenx", "gca", "gcf", "get_cmap", "getp", "grid", "hexbin", "hist", "hist2d", "hlines", "imshow",
    "ioff", "ion", "legend", "loglog", "minorticks_off", "minorticks_on", "pause",
    "pcolor", "pcolorfast", "pcolormesh", "pie", "plot", "quiver", "rc", "rc_context", "rcdefaults",
    "rcParams", "savefig", "scatter", "semilogx", "semilogy", "set_cmap", "setp", "show", "style",
    "stackplot", "stairs", "stem", "step", "subplot", "subplot_mosaic", "subplots", "subplots_adjust", "suptitle", "text", "tick_params",
    "tight_layout", "title", "vlines", "xlabel", "xlim", "xscale", "xticks",
    "ylabel", "ylim", "yscale", "yticks", "__version__",
)

# matplotlib's tab10 cycle; also the targets of the C0-C9 shorthand.
_CYCLE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
          "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
# Only the one-letter colors matplotvite can render are honoured in fmt strings.
_FMT_COLORS = {"b": "blue", "g": "green", "r": "red", "k": "black"}
_SHORT_COLORS = {"b": "blue", "g": "green", "r": "red", "c": "cyan",
                 "m": "magenta", "y": "yellow", "k": "black", "w": "white"}
_TAB10 = {"tab:blue": "#1f77b4", "tab:orange": "#ff7f0e", "tab:green": "#2ca02c",
          "tab:red": "#d62728", "tab:purple": "#9467bd", "tab:brown": "#8c564b",
          "tab:pink": "#e377c2", "tab:gray": "#7f7f7f", "tab:grey": "#7f7f7f",
          "tab:olive": "#bcbd22", "tab:cyan": "#17becf"}

# Compatibility shims that cannot affect the renderer record their calls here.
# The gallery reads and resets this list per case; direct users get one warning
# per shim instead of a warning on every artist mutation.
_IGNORED_CALLS: list[str] = []
_IGNORED_WARNED: set[str] = set()


def _ignored(name):
    _IGNORED_CALLS.append(name)
    if name not in _IGNORED_WARNED:
        _IGNORED_WARNED.add(name)
        warnings.warn(f"{name} is accepted but ignored by matplotvite",
                      RuntimeWarning, stacklevel=3)


def _norm_color(c):
    """Normalise a matplotlib colour spec to `#rrggbb`, `#rrggbbaa` or "none".

    Accepts CSS4 names, single-letter shorthands, `C0`-`C9`, hex strings
    (3/6/8 digits), RGB(A) tuples in 0-1 and greyscale strings such as "0.5".
    """
    if c is None:
        return None
    if isinstance(c, (tuple, list, np.ndarray)):
        vals = [float(v) for v in np.asarray(c, dtype=float).ravel()]
        if len(vals) not in (3, 4):
            raise ValueError("a colour tuple needs 3 (RGB) or 4 (RGBA) values")
        if any(not 0.0 <= v <= 1.0 for v in vals):
            raise ValueError("colour tuple values must be between 0 and 1")
        return "#" + "".join(f"{round(v * 255):02x}" for v in vals)
    s = str(c).strip().lower()
    if s in ("none", "transparent"):
        return "none"
    if s in _SHORT_COLORS:
        return _CSS_COLORS[_SHORT_COLORS[s]].lower()
    if s in _TAB10:
        return _TAB10[s]
    if s in _CSS_COLORS:
        return _CSS_COLORS[s].lower()
    if len(s) == 2 and s[0] == "c" and s[1].isdigit():
        return _CYCLE[int(s[1]) % len(_CYCLE)]
    if s.startswith("#"):
        body = s[1:]
        if len(body) == 3:
            body = "".join(ch * 2 for ch in body)
        if len(body) not in (6, 8) or any(ch not in "0123456789abcdef" for ch in body):
            raise ValueError(f"invalid hex colour: {c!r}")
        return "#" + body
    try:
        grey = float(s)
    except ValueError:
        raise ValueError(f"unrecognized colour: {c!r}") from None
    if 0.0 <= grey <= 1.0:
        v = f"{round(grey * 255):02x}"
        return f"#{v}{v}{v}"
    raise ValueError(f"invalid colour: {c!r}")


def _is_rgb(c):
    """True for a tuple/list of 3 or 4 numeric channel values."""
    return (isinstance(c, (tuple, list)) and len(c) in (3, 4)
            and all(isinstance(v, (int, float, np.number)) for v in c))


_MATH_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "omicron": "ο", "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ",
    "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "φ",
    "varphi": "ϕ", "chi": "χ", "psi": "ψ", "omega": "ω", "Alpha": "Α",
    "Beta": "Β", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
_MATH_SYMBOLS = {
    "pm": "±", "mp": "∓", "times": "×", "div": "÷", "cdot": "·", "infty": "∞",
    "approx": "≈", "neq": "≠", "leq": "≤", "geq": "≥", "rightarrow": "→",
    "to": "→", "leftarrow": "←", "degree": "°", "circ": "°", "sum": "∑",
    "prod": "∏", "int": "∫", "partial": "∂", "nabla": "∇", "sqrt": "√",
    "propto": "∝", "sim": "∼", "ldots": "…", "dots": "…",
}
# Geist includes the Unicode superscript and subscript digits but not the
# modifier letters or subscript operators. Unsupported scripts fall back to
# parenthesized baseline notation instead of rendering missing-glyph boxes.
_SUPERSCRIPTS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _math_script(body, table, marker):
    """Translate a script that the bundled font can show, else keep it readable."""
    if all(ord(ch) in table for ch in body):
        return body.translate(table)
    return f"{marker}({body})"


# Text properties Matplotlib accepts that the renderer has no model for. They are
# accepted so Matplotlib code runs unchanged; size, colour, alignment and
# transform are the ones that actually change the output.
_IGNORED_TEXT_KWARGS = frozenset(
    "alpha antialiased antialiasing backgroundcolor bbox clip_box clip_on clip_path "
    "family figure font fontfamily fontname fontproperties font_properties "
    "fontstretch fontstyle fontvariant fontweight gid in_layout linespacing ma "
    "math_fontfamily multialignment parse_math path_effects picker rasterized "
    "rotation rotation_mode sketch_params snap style url usetex verticalalignment "
    "visible weight wrap zorder".split()
)


def _text_props(fontdict, kwargs):
    """Split text keywords into the honoured subset and the compatibility no-ops."""
    props = dict(fontdict or {})
    props.update(kwargs)
    transform = props.pop("transform", None)
    fontsize = props.pop("fontsize", props.pop("size", None))
    colour = props.pop("color", props.pop("c", None))
    ha = props.pop("horizontalalignment", props.pop("ha", "left"))
    va = props.pop("verticalalignment", props.pop("va", "baseline"))
    unexpected = [key for key in props if key not in _IGNORED_TEXT_KWARGS]
    if unexpected:
        raise TypeError(f"unexpected text keyword argument {unexpected[0]!r}")
    return transform, fontsize, colour, ha, va


def _mathtext(text):
    """Render a small `$...$` TeX subset as Unicode for the text renderer."""
    value = str(text)
    parts = value.split("$")
    if len(parts) % 2 == 0:
        return value

    def segment(body):
        body = _re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", body)
        body = _re.sub(
            r"\\([A-Za-z]+)",
            lambda m: _MATH_GREEK.get(m.group(1)) or _MATH_SYMBOLS.get(m.group(1), m.group(0)),
            body,
        )
        body = _re.sub(
            r"\^\{([^{}]*)\}|\^(\S)",
            lambda m: _math_script(
                m.group(1) if m.group(1) is not None else m.group(2),
                _SUPERSCRIPTS,
                "^",
            ),
            body,
        )
        body = _re.sub(
            r"_\{([^{}]*)\}|_(\S)",
            lambda m: _math_script(
                m.group(1) if m.group(1) is not None else m.group(2),
                _SUBSCRIPTS,
                "_",
            ),
            body,
        )
        return body.replace("{", "").replace("}", "").replace("\\", "")

    out = [parts[0]]
    for i in range(1, len(parts), 2):
        out.extend((segment(parts[i]), parts[i + 1]))
    return "".join(out)


def _cmap_lookup(name):
    """Resolve a colormap name to (canonical base, RGB table, reversed?)."""
    text = str(name).strip()
    reverse = text.endswith("_r")
    base = text[:-2] if reverse else text
    colors = _CMAP_DATA.get(base)
    if colors is None:
        canonical = next((key for key in _CMAP_DATA if key.lower() == base.lower()), None)
        if canonical is None:
            raise ValueError(f"unsupported colormap: {name!r}")
        base = canonical
        colors = _CMAP_DATA[base]
    return base, np.asarray(colors, dtype=np.uint8), reverse


def _cmap_name(cmap):
    """Canonical registry name; `None` picks up the `image.cmap` rcParam."""
    if isinstance(cmap, Colormap):
        return cmap.name
    if cmap is None:
        cmap = rcParams.get("image.cmap", "viridis")
    base, _, reverse = _cmap_lookup(cmap)
    return base + ("_r" if reverse else "")


class Colormap:
    """A registered matplotlib colormap sampled at its native resolution."""

    def __init__(self, name):
        base, colors, reverse = _cmap_lookup(name)
        self.name = base + ("_r" if reverse else "")
        self.N = int(colors.shape[0])
        self._rgb = colors.astype(np.float64) / 255.0
        self._reverse = reverse

    @property
    def colors(self):
        return [tuple(float(v) for v in row) for row in self._rgb]

    def __call__(self, X, alpha=None, bytes=False):
        arr = np.asarray(X, dtype=np.float64)
        scalar = arr.ndim == 0
        missing = ~np.isfinite(arr)
        t = np.clip(np.where(missing, 0.0, arr), 0.0, 1.0)
        index = np.minimum((t * self.N).astype(int), self.N - 1)
        if self._reverse:
            index = self.N - 1 - index
        rgb = self._rgb[index].copy()
        # Matplotlib maps non-finite samples to the fully transparent "bad"
        # colour rather than casting NaN to an out-of-range array index.
        if np.any(missing):
            rgb[missing] = 0.0
        if alpha is None:
            alpha_arr = np.where(missing, 0.0, 1.0)
        else:
            alpha_arr = np.broadcast_to(np.asarray(alpha, dtype=np.float64),
                                        rgb.shape[:-1]).copy()
            alpha_arr[missing] = 0.0
        rgba = np.concatenate([rgb, alpha_arr[..., None]], axis=-1)
        if bytes:
            rgba = np.round(rgba * 255.0).astype(np.uint8)
        if scalar:
            return tuple(rgba.tolist())
        return rgba

    def reversed(self, name=None):
        if name is not None:
            return get_cmap(name)
        if self.name.endswith("_r"):
            return get_cmap(self.name[:-2])
        return get_cmap(self.name + "_r")

    def __repr__(self):
        return f"<Colormap {self.name!r}>"


def get_cmap(name=None, lut=None):
    """Return a `Colormap` by registry name (or the `image.cmap` default)."""
    cmap = name if isinstance(name, Colormap) else Colormap(
        name if name is not None else rcParams.get("image.cmap", "viridis"))
    if lut is not None:
        count = max(int(lut), 1)
        index = np.round(np.linspace(0.0, cmap.N - 1, count)).astype(int)
        if cmap._reverse:
            index = cmap.N - 1 - index
        cmap._rgb = cmap._rgb[index]
        cmap.N = count
    return cmap


def colormaps():
    """Sorted names of every registered colormap, including `_r` variants."""
    return sorted([*_CMAP_DATA, *(f"{name}_r" for name in _CMAP_DATA)])


class _CmapNamespace:
    """The `plt.cm` namespace, exposing one attribute per colormap."""

    def get_cmap(self, name=None, lut=None):
        return get_cmap(name, lut)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        try:
            return get_cmap(name)
        except ValueError:
            raise AttributeError(name) from None


cm = _CmapNamespace()


class _Share:
    """Limit group behind `sharex`/`sharey`: explicit limits win, otherwise the
    union of every member's data extent."""

    def __init__(self):
        self.limits = None
        self.axes = []

    def union(self, axis):
        spans = [(a._extent_x() if axis == "x" else a._extent_y()) for a in self.axes]
        return (min(s[0] for s in spans), max(s[1] for s in spans))


def _share_axes(axs, shape, sharex, sharey):
    """Join axes into limit groups and hide duplicate inner tick labels."""
    rows, cols = shape
    grid = np.array(axs, dtype=object).reshape(rows, cols)

    def attach(kind, attr, key):
        if not kind:
            return
        if kind in (True, "all"):
            def key(_a):
                return 0
        groups = {}
        for ax in axs:
            group = groups.setdefault(key(ax), _Share())
            group.axes.append(ax)
            setattr(ax, attr, group)

    if sharex:
        attach(sharex, "_share_x",
               (lambda a: a.pos % cols) if sharex == "col" else (lambda a: a.pos // cols))
        for c in range(cols):
            column = [grid[r][c] for r in range(rows) if not grid[r][c]._removed]
            for ax in column[:-1]:
                ax.hide_xticklabels = True
    if sharey:
        attach(sharey, "_share_y",
               (lambda a: a.pos // cols) if sharey == "row" else (lambda a: a.pos % cols))
        for r in range(rows):
            row = [grid[r][c] for c in range(cols) if not grid[r][c]._removed]
            for ax in row[1:]:
                ax.hide_yticklabels = True


class _PropCycler:
    """Small stand-in for matplotlib's Cycler, enough for `get_prop_cycle`."""

    def __init__(self, colors):
        self._colors = list(colors)

    def by_key(self):
        return {"color": list(self._colors)}

    def __iter__(self):
        return iter(self._colors)

    def __len__(self):
        return len(self._colors)

    def __repr__(self):
        return f"Cycler(color={self._colors!r})"


class _CycleList(list):
    """A prop-cycle list that also supports matplotlib's `by_key()` API."""

    def by_key(self): return {"color": list(self)}


class _CoordTransform:
    """Marker for `text(transform=...)`: data, axes or figure coordinates."""

    def __init__(self, kind):
        self.kind = kind

    def transform(self, points): return np.asarray(points, dtype=np.float64)
    def inverted(self): return self
    def __add__(self, other): return self
    def __radd__(self, other): return self
    def translate(self, *args, **kwargs): return self
    def rotate_deg(self, *args, **kwargs): return self
    def scale(self, *args, **kwargs): return self
    def skew_deg(self, *args, **kwargs): return self


class Affine2D:
    """No-op affine transform accepted by annotation and locator helpers."""

    def __init__(self, *args, **kwargs): pass
    def transform(self, points): _ignored("Affine2D.transform"); return np.asarray(points, dtype=np.float64)
    def inverted(self): return self
    def __add__(self, other): return self
    def __radd__(self, other): return self
    def translate(self, *args, **kwargs): _ignored("Affine2D.translate"); return self
    def rotate_deg(self, *args, **kwargs): _ignored("Affine2D.rotate_deg"); return self
    def scale(self, *args, **kwargs): _ignored("Affine2D.scale"); return self
    def skew_deg(self, *args, **kwargs): _ignored("Affine2D.skew_deg"); return self
    def get_matrix(self): return np.eye(3)


class Path:
    """Minimal path container used by `PathPatch`."""

    def __init__(self, vertices, codes=None, **kwargs):
        self.vertices = np.asarray(vertices, dtype=float).reshape(-1, 2)
        self.codes = codes

    def get_vertices(self): return self.vertices
    def get_codes(self): return self.codes
    def transformed(self, transform): _ignored("Path.transformed"); return self
    def __iter__(self): return iter((self.vertices, self.codes))


class _Bbox:
    """Minimal Bbox with the attribute names matplotlib tests reach for."""

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = float(x0), float(y0), float(x1), float(y1)

    @classmethod
    def from_bounds(cls, x0, y0, width, height):
        return cls(x0, y0, x0 + width, y0 + height)

    @classmethod
    def from_extents(cls, *args):
        vals = [float(v) for v in args]
        return cls(min(vals[0::2]), min(vals[1::2]), max(vals[0::2]), max(vals[1::2]))

    @classmethod
    def union(cls, boxes):
        boxes = list(boxes)
        return cls(min(b.x0 for b in boxes), min(b.y0 for b in boxes),
                   max(b.x1 for b in boxes), max(b.y1 for b in boxes))

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

    @property
    def size(self): return (self.width, self.height)

    @property
    def intervalx(self): return (self.x0, self.x1)

    @property
    def intervaly(self): return (self.y0, self.y1)

    def get_points(self): return [[self.x0, self.y0], [self.x1, self.y1]]
    def get_extents(self): return (self.x0, self.y0, self.x1, self.y1)
    def expanded(self, sw, sh):
        return _Bbox(self.x0 - sw, self.y0 - sh, self.x1 + sw, self.y1 + sh)
    def transformed(self, transform): _ignored("Bbox.transformed"); return self
    def contains(self, x, y): return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1
    def containsx(self, x): return self.x0 <= x <= self.x1
    def containsy(self, y): return self.y0 <= y <= self.y1

    def __repr__(self):
        return f"Bbox({self.x0:g}, {self.y0:g}, {self.x1:g}, {self.y1:g})"


Bbox = _Bbox


class _Transform:
    """Stand-in for a matplotlib transform: data coordinates pass through."""

    def transform(self, points): return np.asarray(points, dtype=np.float64)

    def inverted(self): return self


class _TextLabel:
    """Minimal tick-label stand-in for code that pokes at Text objects."""

    def __init__(self, text=""):
        self._text, self._visible, self._fontsize = str(text), True, 12.0
        self._rotation = 0.0
        self._color = "black"

    def get_text(self): return self._text
    def set_text(self, text): self._text = str(text)
    def get_visible(self): return self._visible
    def set_visible(self, visible): self._visible = bool(visible)
    def get_fontsize(self): return self._fontsize
    def set_fontsize(self, size): self._fontsize = _font_size(size, self._fontsize)
    def get_rotation(self): return self._rotation
    def set_rotation(self, rotation): self._rotation = float(rotation)
    def get_color(self): return self._color
    def set_color(self, color): self._color = color
    def set_ha(self, value): _ignored("Text.set_ha")
    def set_va(self, value): _ignored("Text.set_va")
    def set_fontweight(self, value): _ignored("Text.set_fontweight")
    def set_fontstyle(self, value): _ignored("Text.set_fontstyle")
    def set_fontfamily(self, value): _ignored("Text.set_fontfamily")
    def set_fontname(self, value): _ignored("Text.set_fontname")
    def set_fontproperties(self, value): _ignored("Text.set_fontproperties")
    def set_multialignment(self, value): _ignored("Text.set_multialignment")
    def set_linespacing(self, value): _ignored("Text.set_linespacing")
    def set_wrap(self, value): _ignored("Text.set_wrap")
    def get_window_extent(self, renderer=None): return _Bbox(0, 0, 1, 1)


def _margin(lo, hi, scale, sticky=()):
    """Matplotlib's default 5% autoscale margin (in log space for log axes).

    `sticky` edges (images, hexbin) swallow the margin on their side, like
    Matplotlib's `sticky_edges`.
    """
    f = np.log10 if scale == "log" else float
    lo, hi = f(lo), f(hi)
    sticky = [f(e) for e in sticky if e > 0 or scale != "log"]
    pad = (hi - lo) * 0.05
    plo, phi = lo - pad, hi + pad
    below = [e for e in sticky if plo < e <= lo]
    above = [e for e in sticky if hi <= e < phi]
    lo, hi = max(below, default=plo), min(above, default=phi)
    return (10.0 ** lo, 10.0 ** hi) if scale == "log" else (lo, hi)


def _span(values):
    """A flat series is widened so its extent is never degenerate.

    `Axes.get_xlim`/`get_ylim` add Matplotlib's autoscale margin on top of this.
    """
    vals = np.asarray(values, dtype=float).ravel()
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return (0.0, 1.0)
    lo, hi = float(vals.min()), float(vals.max())
    return (lo, hi) if lo < hi else (lo - 1.0, lo + 1.0)


def _looks_like_categories(values):
    """True for string scalars or sequences, which matplotlib treats as categories."""
    if isinstance(values, str):
        return True
    try:
        array = np.asarray(values)
    except (TypeError, ValueError):
        return False
    if array.dtype.kind in ("U", "S"):
        return True
    return (array.dtype.kind == "O" and array.size
            and isinstance(array.ravel()[0], str))


def _looks_like_dates(values):
    """True for date/datetime/`datetime64` scalars or sequences of them."""
    if isinstance(values, (np.datetime64, _datetime.date)):
        return True
    try:
        array = np.asarray(values)
    except (TypeError, ValueError):
        return False
    if array.dtype.kind == "M":
        return True
    if array.dtype.kind == "O" and array.size:
        return isinstance(array.ravel()[0], (np.datetime64, _datetime.date))
    return False


def _datetime_to_num(value):
    """Matplotlib date number: proleptic Gregorian ordinal plus day fraction."""
    if isinstance(value, np.datetime64):
        if np.isnat(value):
            return np.nan
        delta = value - np.datetime64("1970-01-01T00:00:00")
        return 719163.0 + float(delta / np.timedelta64(1, "D"))
    if isinstance(value, _datetime.datetime):
        if value.tzinfo is not None:
            value = value.astimezone(_datetime.timezone.utc).replace(tzinfo=None)
        seconds = (value.hour * 3600.0 + value.minute * 60.0 + value.second
                   + value.microsecond / 1e6)
        return value.toordinal() + seconds / 86400.0
    return float(value.toordinal())


def _date_to_num(values):
    """Convert date-like input to a float array of matplotlib date numbers."""
    array = np.asarray(values)
    if array.dtype.kind == "M":
        result = np.asarray([_datetime_to_num(v) for v in array.ravel()],
                            dtype=np.float64)
        result = result.reshape(array.shape)
    else:
        result = np.asarray([_datetime_to_num(v) for v in array.ravel()],
                            dtype=np.float64).reshape(array.shape)
    return result.item() if result.ndim == 0 else result


def _date_from_num(value):
    ordinal = int(_math.floor(value))
    seconds = int(round(float(value - ordinal) * 86400.0))
    return (_datetime.datetime.fromordinal(ordinal)
            + _datetime.timedelta(seconds=seconds))


def _date_label(value):
    dt = _date_from_num(value)
    if abs(value - round(value)) < 1e-9:
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d %H:%M")


def _add_months(value, months):
    total = value.year * 12 + (value.month - 1) + int(months)
    year, month = divmod(total, 12)
    month += 1
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    last_day = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return value.replace(year=year, month=month, day=min(value.day, last_day))


def _nice_step(raw, steps):
    for step in steps:
        if step >= raw:
            return step
    return steps[-1] * max(1, int(_math.ceil(raw / steps[-1])))


def _date_ticks(lo, hi):
    """Calendar-aligned tick positions and labels for a date-number range."""
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
        return [float(lo)], [_date_label(lo)]
    span = float(hi - lo)
    if span >= 60.0:
        raw = span / 30.44 / 6.0
        step = _nice_step(raw, [1, 2, 3, 6, 12, 24, 48, 120, 240, 600])
        start = _date_from_num(lo).replace(day=1, hour=0, minute=0, second=0,
                                           microsecond=0)
        if _datetime_to_num(start) < lo:
            start = _add_months(start, 1)
        ticks, labels = [], []
        current = start
        while len(ticks) < 20:
            value = _datetime_to_num(current)
            if value > hi + 1e-9:
                break
            if value >= lo - 1e-9:
                ticks.append(value)
                labels.append(current.strftime("%Y-%m-%d"))
            current = _add_months(current, step)
        return ticks, labels
    if span >= 2.0:
        step = int(_nice_step(span / 6.0, [1, 2, 3, 5, 7, 10, 14, 21, 30]))
        tick = int(_math.ceil(lo - 1e-9))
        ticks, labels = [], []
        while tick <= hi + 1e-9 and len(ticks) < 20:
            if tick >= lo - 1e-9:
                ticks.append(float(tick))
                labels.append(_date_from_num(tick).strftime("%Y-%m-%d"))
            tick += step
        return ticks, labels
    step = _nice_step(span * 86400.0 / 6.0,
                      [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800,
                       3600, 7200, 10800, 21600, 43200])
    start = _math.ceil(lo * 86400.0 / step) * step
    ticks, labels = [], []
    while start <= hi * 86400.0 + 1e-6 and len(ticks) < 20:
        value = start / 86400.0
        if value >= lo - 1e-9:
            ticks.append(value)
            labels.append(_date_from_num(value).strftime("%Y-%m-%d %H:%M"))
        start += step
    return ticks, labels
DPI = 100
_FORMATS = ("png", "svg", "pdf", "webp")
_COMPRESSIONS = ("fast", "default", "best")
_MAX_CANVAS_DIM = 32768
_MAX_CANVAS_AREA = 67108864  # 2^26 pixels (~256 MiB RGBA raw buffer limit)
_MAX_BINS = 4096
_MAX_BIN_CELLS = 4_000_000
_MAX_EDGES = 100_000


def _validate_bins(bins, name="bins", max_cells=None):
    """Reject bin counts that would allocate unbounded arrays."""
    if isinstance(bins, (int, np.integer)) and not isinstance(bins, bool):
        n = int(bins)
        if n < 1:
            raise ValueError(f"{name} must be at least 1")
        if n > _MAX_BINS:
            raise ValueError(f"{name}={n} exceeds maximum allowed ({_MAX_BINS})")
        if max_cells is not None and n * n > max_cells:
            raise ValueError(f"{name}={n} creates too many bins ({n * n} > {max_cells})")
    elif isinstance(bins, (tuple, list, np.ndarray)):
        if isinstance(bins, (tuple, list)) and len(bins) == 2:
            try:
                edges = [np.asarray(edge) for edge in bins]
            except (TypeError, ValueError):
                edges = []
            if edges and all(edge.ndim == 1 for edge in edges):
                if any(edge.size > _MAX_EDGES for edge in edges):
                    raise ValueError(
                        f"{name} has too many edges "
                        f"({max(edge.size for edge in edges)} > {_MAX_EDGES})"
                    )
                return bins
        try:
            arr = np.asarray(bins)
        except (TypeError, ValueError):
            return bins
        if arr.ndim == 1 and arr.size in (1, 2) and np.issubdtype(arr.dtype, np.integer):
            ns = [int(v) for v in arr.ravel()]
            if any(n < 1 for n in ns):
                raise ValueError(f"{name} values must be at least 1")
            if any(n > _MAX_BINS for n in ns):
                raise ValueError(f"{name} values exceed maximum allowed ({_MAX_BINS})")
            if (max_cells is not None and len(ns) == 2
                    and ns[0] * ns[1] > max_cells):
                raise ValueError(
                    f"{name}={ns} creates too many bins "
                    f"({ns[0] * ns[1]} > {max_cells})"
                )
        elif arr.ndim == 1 and arr.size > _MAX_EDGES:
            raise ValueError(f"{name} has too many edges ({arr.size} > {_MAX_EDGES})")
    return bins


def _validate_dimension(val, name):
    try:
        v = float(val)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a real number, got {val!r}") from None
    if not _math.isfinite(v) or v <= 0.0:
        raise ValueError(f"{name} must be positive and finite, got {val!r}")
    return v


def _validate_figsize(figsize):
    if not isinstance(figsize, (tuple, list, np.ndarray)) or len(figsize) != 2:
        raise ValueError(f"figsize must be a sequence of 2 positive numbers, got {figsize!r}")
    w = _validate_dimension(figsize[0], "figsize width")
    h = _validate_dimension(figsize[1], "figsize height")
    return (w, h)


def _output_format(filepath, format):
    """Resolve the output format from an explicit value or the destination name."""
    if format is None:
        name = (filepath if isinstance(filepath, (str, bytes, os.PathLike))
                else getattr(filepath, "name", None))
        if not isinstance(name, (str, bytes, os.PathLike)):
            name = ""
        suffix = os.path.splitext(os.fsdecode(name))[1]
        fmt = suffix.lower().lstrip(".") or "png"
    else:
        fmt = str(format).lower().lstrip(".")
    if fmt not in _FORMATS:
        raise ValueError(f"unsupported format: {fmt!r} (use 'png', 'svg', 'pdf', or 'webp')")
    return fmt


class _Wedge:
    """Placeholder wedge returned by `pie`."""

    def __init__(self, color=None):
        self._color = color

    def set_facecolor(self, c):
        self._color = str(c)
        return self

    def set_color(self, c):
        return self.set_facecolor(c)

    def get_facecolor(self): return self._color


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

    def get_facecolor(self):
        return self._axes.bars[self._group]["colors"][:1] or ["#1f77b4"]

    def get_color(self):
        return self.get_facecolor()[0]

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
        self._set("edgecolor", c if isinstance(c, str) else _norm_color(c))
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


class _QuiverHandle:
    """Handle for one `quiver` collection."""

    def __init__(self, entry): self._e = entry

    def get_offsets(self):
        return np.column_stack([self._e["x"], self._e["y"]])

    def get_U(self): return self._e["u"]
    def get_V(self): return self._e["v"]
    def get_facecolor(self): return list(self._e["colors"])


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

    def set_clim(self, vmin=None, vmax=None):
        return None

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

    def get_paths(self): return [self._e]


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


_FONT_SIZE_NAMES = {
    "xx-small": 6.0, "x-small": 8.0, "small": 10.0, "medium": 12.0,
    "large": 14.0, "x-large": 18.0, "xx-large": 24.0,
    "larger": 14.0, "smaller": 8.0,
}


def _font_size(value, default=10.0):
    """Resolve numeric and named font sizes accepted by matplotlib."""
    if value is None:
        return float(default)
    if isinstance(value, str):
        return _FONT_SIZE_NAMES.get(value.lower(), float(default))
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _numbers(value):
    if value is None:
        return []
    if isinstance(value, (int, float, np.number)):
        return [float(value)]
    try:
        return [float(v) for v in np.asarray(value, dtype=float).ravel()]
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


class Patch:
    """Base class for matplotlib-style patches accepted by `add_patch`."""

    def __init__(self, **kwargs):
        fill = kwargs.pop("fill", True)
        color = kwargs.pop("color", None)
        self._facecolor = None if fill is False else (
            kwargs.pop("facecolor", kwargs.pop("fc", None))
            or color or _CYCLE[0])
        self._edgecolor = kwargs.pop("edgecolor", kwargs.pop("ec", None)) or color
        self._linewidth = float(kwargs.pop("linewidth", kwargs.pop("lw", 1.0)))
        self._alpha = kwargs.pop("alpha", None)
        self._label = str(kwargs.pop("label", ""))
        self._fill = bool(fill)
        self._visible = bool(kwargs.pop("visible", True))
        self._zorder = int(kwargs.pop("zorder", 1))
        self._linestyle = kwargs.pop("linestyle", kwargs.pop("ls", "-"))
        self._hatch = kwargs.pop("hatch", None)
        self._transform = kwargs.pop("transform", None)
        self._kwargs = kwargs

    def get_facecolor(self):
        return "none" if not self._fill or self._facecolor is None else _norm_color(self._facecolor)

    def get_edgecolor(self):
        return None if self._edgecolor is None else _norm_color(self._edgecolor)

    def get_color(self): return self.get_facecolor()
    def get_linewidth(self): return self._linewidth
    def get_lw(self): return self._linewidth
    def get_linestyle(self): return self._linestyle
    def get_alpha(self): return self._alpha
    def get_label(self): return self._label
    def get_visible(self): return self._visible
    def get_zorder(self): return self._zorder
    def get_fill(self): return self._fill
    def get_hatch(self): return self._hatch
    def get_transform(self): return self._transform or _Transform()
    def get_patch_transform(self): return self.get_transform()

    def set_facecolor(self, color):
        self._facecolor = color
        self._fill = color is not None and str(color).lower() != "none"
        return self

    def set_fc(self, color): return self.set_facecolor(color)

    def set_color(self, color):
        self._facecolor = color
        self._edgecolor = color
        self._fill = str(color).lower() != "none"
        return self

    def set_edgecolor(self, color):
        self._edgecolor = color
        return self

    def set_ec(self, color): return self.set_edgecolor(color)

    def set_linewidth(self, width):
        self._linewidth = float(width)
        return self

    def set_lw(self, width): return self.set_linewidth(width)

    def set_linestyle(self, style):
        self._linestyle = str(style)
        return self

    def set_alpha(self, alpha):
        self._alpha = None if alpha is None else float(alpha)
        return self

    def set_label(self, label):
        self._label = str(label)
        return self

    def set_visible(self, visible):
        self._visible = bool(visible)
        return self

    def set_zorder(self, zorder):
        self._zorder = int(zorder)
        return self

    def set_fill(self, fill):
        self._fill = bool(fill)
        return self

    def set_hatch(self, hatch):
        self._hatch = hatch
        return self

    def set_transform(self, transform): self._transform = transform
    def set_clip_on(self, clip): _ignored("Patch.set_clip_on")
    def set_clip_path(self, path, transform=None): _ignored("Patch.set_clip_path")
    def set_clip_box(self, box): _ignored("Patch.set_clip_box")
    def set_path_effects(self, effects): _ignored("Patch.set_path_effects")
    def set_antialiased(self, value): return None
    def set_antialiaseds(self, value): return None
    def set_joinstyle(self, value): return None
    def set_capstyle(self, value): return None
    def set_rasterized(self, value): return None
    def set_url(self, value): return None
    def set_gid(self, value): return None
    def set_sketch_params(self, *args, **kwargs): return None
    def set_snap(self, value): return None
    def set_in_layout(self, value): return None
    def remove(self): self._visible = False
    def get_window_extent(self, renderer=None): return _Bbox(0, 0, 1, 1)
    def contains(self, mouseevent=None): return False, {}

    def __repr__(self):
        return f"<{type(self).__name__} at {hex(id(self))}>"


class Rectangle(Patch):
    """Axis-aligned (or rotated) rectangle in data coordinates."""

    def __init__(self, xy, width, height, angle=0.0, **kwargs):
        super().__init__(**kwargs)
        self._x, self._y = float(xy[0]), float(xy[1])
        self._width, self._height = float(width), float(height)
        self.angle = float(angle)

    def get_x(self): return self._x
    def get_y(self): return self._y
    def get_width(self): return self._width
    def get_height(self): return self._height
    def get_angle(self): return self.angle
    def get_xy(self): return (self._x, self._y)
    def set_x(self, x): self._x = float(x)
    def set_y(self, y): self._y = float(y)
    def set_width(self, width): self._width = float(width)
    def set_height(self, height): self._height = float(height)
    def set_angle(self, angle): self.angle = float(angle)
    def set_xy(self, xy): self._x, self._y = float(xy[0]), float(xy[1])
    def get_bbox(self): return _Bbox(self._x, self._y, self._x + self._width, self._y + self._height)


class Circle(Patch):
    def __init__(self, xy, radius=5, **kwargs):
        super().__init__(**kwargs)
        self._center = (float(xy[0]), float(xy[1]))
        self._radius = float(radius)

    def get_center(self): return self._center
    def get_radius(self): return self._radius
    def set_center(self, xy): self._center = (float(xy[0]), float(xy[1]))
    def set_radius(self, radius): self._radius = float(radius)

    @property
    def center(self): return self._center

    @center.setter
    def center(self, value): self.set_center(value)


class Ellipse(Patch):
    def __init__(self, xy, width, height, angle=0.0, **kwargs):
        super().__init__(**kwargs)
        self._center = (float(xy[0]), float(xy[1]))
        self._width, self._height = float(width), float(height)
        self.angle = float(angle)

    def get_center(self): return self._center
    def get_width(self): return self._width
    def get_height(self): return self._height
    def get_angle(self): return self.angle
    def set_center(self, xy): self._center = (float(xy[0]), float(xy[1]))
    def set_width(self, width): self._width = float(width)
    def set_height(self, height): self._height = float(height)
    def set_angle(self, angle): self.angle = float(angle)

    def get_xy(self):
        t = np.linspace(0.0, 2.0 * np.pi, 73)
        x = 0.5 * self._width * np.cos(t)
        y = 0.5 * self._height * np.sin(t)
        a = np.deg2rad(self.angle)
        return np.column_stack([
            self._center[0] + x * np.cos(a) - y * np.sin(a),
            self._center[1] + x * np.sin(a) + y * np.cos(a),
        ])


class Polygon(Patch):
    def __init__(self, xy, closed=True, **kwargs):
        super().__init__(**kwargs)
        self._xy = np.asarray(xy, dtype=float).reshape(-1, 2)
        self._closed = bool(closed)

    def get_xy(self): return self._xy
    def get_closed(self): return self._closed
    def set_xy(self, xy): self._xy = np.asarray(xy, dtype=float).reshape(-1, 2)
    def set_closed(self, closed): self._closed = bool(closed)


class Arc(Patch):
    def __init__(self, xy, width, height, angle=0.0, theta1=0.0, theta2=360.0, **kwargs):
        kwargs.setdefault("fill", False)
        kwargs.setdefault("facecolor", "none")
        super().__init__(**kwargs)
        self._center = (float(xy[0]), float(xy[1]))
        self._width, self._height = float(width), float(height)
        self.angle = float(angle)
        self.theta1, self.theta2 = float(theta1), float(theta2)

    def get_center(self): return self._center
    def get_width(self): return self._width
    def get_height(self): return self._height
    def get_angle(self): return self.angle
    def get_theta1(self): return self.theta1
    def get_theta2(self): return self.theta2

    def get_xy(self):
        t = np.deg2rad(np.linspace(self.theta1, self.theta2, 73))
        x = 0.5 * self._width * np.cos(t)
        y = 0.5 * self._height * np.sin(t)
        a = np.deg2rad(self.angle)
        return np.column_stack([
            self._center[0] + x * np.cos(a) - y * np.sin(a),
            self._center[1] + x * np.sin(a) + y * np.cos(a),
        ])


class Wedge(Patch):
    def __init__(self, center, r, theta1, theta2, width=None, **kwargs):
        super().__init__(**kwargs)
        self._center = (float(center[0]), float(center[1]))
        self._r = float(r)
        self.theta1, self.theta2 = float(theta1), float(theta2)
        self._width = None if width is None else float(width)

    def get_center(self): return self._center
    def get_radius(self): return self._r
    def get_theta1(self): return self.theta1
    def get_theta2(self): return self.theta2

    def get_xy(self):
        t = np.deg2rad(np.linspace(self.theta1, self.theta2, 49))
        outer = np.column_stack([
            self._center[0] + self._r * np.cos(t),
            self._center[1] + self._r * np.sin(t),
        ])
        if self._width is None:
            return np.vstack([self._center, outer, self._center])
        inner = np.column_stack([
            self._center[0] + (self._r - self._width) * np.cos(t),
            self._center[1] + (self._r - self._width) * np.sin(t),
        ])
        return np.vstack([outer, inner[::-1]])


class RegularPolygon(Patch):
    def __init__(self, xy, numVertices, radius=5, orientation=0, **kwargs):
        super().__init__(**kwargs)
        self._center = (float(xy[0]), float(xy[1]))
        self.numvertices = int(numVertices)
        self._radius = float(radius)
        self.orientation = float(orientation)

    def get_center(self): return self._center
    def get_radius(self): return self._radius
    def get_numvertices(self): return self.numvertices

    def get_xy(self):
        t = (np.arange(self.numvertices) / self.numvertices * 2.0 * np.pi
             + np.deg2rad(self.orientation))
        return np.column_stack([
            self._center[0] + self._radius * np.cos(t),
            self._center[1] + self._radius * np.sin(t),
        ])


class FancyArrow(Patch):
    def __init__(self, x, y, dx, dy, width=0.001, length_includes_head=False,
                 head_width=None, head_length=None, **kwargs):
        super().__init__(**kwargs)
        self.x, self.y, self.dx, self.dy = map(float, (x, y, dx, dy))
        self.width = float(width)
        self.head_width = float(head_width if head_width is not None else 3.0 * width)
        self.head_length = float(head_length if head_length is not None else 3.0 * width)

    def get_xy(self):
        x0, y0, dx, dy = self.x, self.y, self.dx, self.dy
        length = _math.hypot(dx, dy)
        if length == 0.0:
            return np.array([[x0, y0]])
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        head = min(self.head_length, length * 0.5)
        hw = self.head_width * 0.5
        ww = self.width * 0.5
        return np.array([
            [x0 + px * ww, y0 + py * ww],
            [x0 + ux * (length - head) + px * ww, y0 + uy * (length - head) + py * ww],
            [x0 + ux * (length - head) + px * hw, y0 + uy * (length - head) + py * hw],
            [x0 + dx, y0 + dy],
            [x0 + ux * (length - head) - px * hw, y0 + uy * (length - head) - py * hw],
            [x0 + ux * (length - head) - px * ww, y0 + uy * (length - head) - py * ww],
            [x0 - px * ww, y0 - py * ww],
        ])


class FancyArrowPatch(Patch):
    def __init__(self, posA=None, posB=None, arrowstyle="-", mutation_scale=1.0, **kwargs):
        super().__init__(**kwargs)
        self.posA, self.posB = posA, posB
        self.arrowstyle = arrowstyle
        self.mutation_scale = float(mutation_scale)

    def get_xy(self):
        if self.posA is None or self.posB is None:
            return np.empty((0, 2))
        a = np.asarray(self.posA, dtype=float)
        b = np.asarray(self.posB, dtype=float)
        if "-" == str(self.arrowstyle):
            return np.vstack([a, b])
        return FancyArrow(a[0], a[1], b[0] - a[0], b[1] - a[1],
                          width=self.mutation_scale * 0.002,
                          head_width=self.mutation_scale * 0.02,
                          head_length=self.mutation_scale * 0.02).get_xy()

    def set_positions(self, posA, posB):
        self.posA, self.posB = posA, posB


class FancyBboxPatch(Patch):
    def __init__(self, xy, width, height, boxstyle="round", mutation_scale=1.0, **kwargs):
        super().__init__(**kwargs)
        self._x, self._y = float(xy[0]), float(xy[1])
        self._width, self._height = float(width), float(height)
        self.boxstyle = boxstyle
        self.mutation_scale = float(mutation_scale)

    def get_x(self): return self._x
    def get_y(self): return self._y
    def get_width(self): return self._width
    def get_height(self): return self._height
    def get_xy(self): return (self._x, self._y)
    def set_bounds(self, x, y, width, height):
        self._x, self._y = float(x), float(y)
        self._width, self._height = float(width), float(height)


class PathPatch(Patch):
    def __init__(self, path, **kwargs):
        super().__init__(**kwargs)
        self._path = path

    def get_path(self): return self._path
    def set_path(self, path): self._path = path

    def get_xy(self):
        vertices = getattr(self._path, "vertices", None)
        return np.empty((0, 2)) if vertices is None else np.asarray(vertices, dtype=float)


class Annulus(Patch):
    def __init__(self, xy, r, width, angle=0.0, **kwargs):
        super().__init__(**kwargs)
        self._center = (float(xy[0]), float(xy[1]))
        self._r, self._width = float(r), float(width)
        self.angle = float(angle)

    def get_xy(self):
        t = np.linspace(0.0, 2.0 * np.pi, 97)
        outer = np.column_stack([self._center[0] + self._r * np.cos(t),
                                 self._center[1] + self._r * np.sin(t)])
        inner = np.column_stack([self._center[0] + (self._r - self._width) * np.cos(t),
                                 self._center[1] + (self._r - self._width) * np.sin(t)])
        return np.vstack([outer, inner[::-1]])


class _PatchesNamespace:
    pass


patches = _PatchesNamespace()
for _patch_name in ("Patch", "Rectangle", "Circle", "Ellipse", "Polygon", "Arc",
                    "Wedge", "RegularPolygon", "FancyArrow", "FancyArrowPatch",
                    "FancyBboxPatch", "PathPatch", "Annulus"):
    setattr(patches, _patch_name, globals()[_patch_name])


class _FlexibleStyleNamespace:
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        _ignored(f"patches.{name}")
        return type(name, (), {"__init__": lambda self, *args, **kwargs: None})


patches.ArrowStyle = _FlexibleStyleNamespace()
patches.BoxStyle = _FlexibleStyleNamespace()
patches.ConnectionStyle = _FlexibleStyleNamespace()


def _patch_entry(artist):
    """Reduce a Rectangle/Circle/Polygon-like object, or return None."""
    kind = None
    x = y = w = h = 0.0
    points = []
    if not getattr(artist, "get_visible", lambda: True)():
        return None
    vals = [_call(artist, name) for name in
            ("get_x", "get_y", "get_width", "get_height")]
    if all(v is not None for v in vals):
        kind = "rect"
        x, y, w, h = (float(v) for v in vals)
    if kind is None and _call(artist, "get_radius") is not None:
        center = _call(artist, "get_center")
        if center is not None:
            kind, x, y = "circle", float(center[0]), float(center[1])
            w = float(_call(artist, "get_radius"))
    if kind is None:
        xy = _call(artist, "get_xy")
        if xy is not None:
            try:
                pts = np.asarray(xy, dtype=float)
                if pts.ndim == 2 and pts.shape[1] >= 2:
                    pts = pts[np.isfinite(pts[:, :2]).all(axis=1)]
                    if len(pts) >= 2:
                        kind, points = "polygon", pts[:, :2].ravel().tolist()
            except (TypeError, ValueError):
                points = []
    if kind is None:
        return None
    return dict(kind=kind, x=x, y=y, width=w, height=h, points=points,
                facecolor=_single_color(_call(artist, "get_facecolor")),
                edgecolor=_single_color(_call(artist, "get_edgecolor")),
                linewidth=_number(_call(artist, "get_linewidth"), 1.0),
                alpha=_number(_call(artist, "get_alpha"), 1.0),
                label=str(_call(artist, "get_label") or ""))


def _collection_entry(artist):
    """Reduce a scatter/line collection, or return None."""
    points, segments = [], []
    offsets = _call(artist, "get_offsets")
    if offsets is not None:
        try:
            a = np.asarray(offsets, dtype=float)
            if a.size:
                a = a.reshape(-1, 2)
                a = a[np.isfinite(a).all(axis=1)]
                points = a.ravel().tolist()
        except (TypeError, ValueError):
            points = []
    raw_segments = _call(artist, "get_segments")
    if raw_segments is not None:
        try:
            items = list(raw_segments)
        except TypeError:
            items = []
        for raw in items:
            try:
                seg = np.asarray(raw, dtype=float).reshape(-1, 2)
            except (TypeError, ValueError):
                continue
            seg = seg[np.isfinite(seg).all(axis=1)]
            if len(seg) >= 2:
                segments.append(seg.ravel().tolist())
    if not points and not segments:
        return None
    colors = _call(artist, "get_facecolor")
    if colors is None or (hasattr(colors, "__len__") and len(colors) == 0):
        colors = _call(artist, "get_colors") or _call(artist, "get_edgecolor")
    marker = _call(artist, "get_marker")
    alpha = _number(_call(artist, "get_alpha"), 1.0)
    return dict(points=points, segments=segments,
                sizes=_numbers(_call(artist, "get_sizes")),
                colors=_color_list(colors),
                marker="o" if marker is None else str(marker),
                alpha=1.0 if alpha is None else alpha,
                linewidth=_number(_call(artist, "get_linewidth"), 1.5),
                label=str(_call(artist, "get_label") or ""))


class Collection:
    """Base compatibility object for Matplotlib collection artists."""

    def __init__(self, colors=None, facecolor=None, edgecolor=None, linewidths=None,
                 alpha=None, label="", zorder=1, **kwargs):
        self._colors = colors
        self._facecolor = facecolor if facecolor is not None else colors
        self._edgecolor = edgecolor if edgecolor is not None else colors
        self._linewidth = linewidths if linewidths is not None else kwargs.get("lw", 1.5)
        self._alpha = alpha
        self._label = str(label)
        self._zorder = zorder
        self._visible = True
        self._array = None

    def get_facecolor(self): return self._facecolor
    def get_edgecolor(self): return self._edgecolor
    def get_colors(self): return self._colors
    def get_alpha(self): return self._alpha
    def get_linewidth(self):
        return float(np.asarray(self._linewidth).ravel()[0]) if self._linewidth is not None else 1.5
    def get_label(self): return self._label
    def get_zorder(self): return self._zorder
    def get_visible(self): return self._visible
    def set_color(self, color):
        self._colors = color
        self._facecolor = color
        return self
    def set_facecolor(self, color): self._facecolor = color; return self
    def set_edgecolor(self, color): self._edgecolor = color; return self
    def set_alpha(self, alpha): self._alpha = alpha; return self
    def set_linewidth(self, width): self._linewidth = width; return self
    def set_linewidths(self, width): self._linewidth = width; return self
    def set_label(self, label): self._label = str(label); return self
    def set_zorder(self, zorder): self._zorder = zorder; return self
    def set_visible(self, visible): self._visible = bool(visible); return self
    def set_array(self, values): self._array = values; return self
    def set_clim(self, *args, **kwargs): return self
    def set_norm(self, norm): return self
    def set_cmap(self, cmap): return self
    def set_sizes(self, sizes): return self
    def set_path_effects(self, effects): _ignored("Collection.set_path_effects")
    def set_clip_on(self, value): _ignored("Collection.set_clip_on")
    def set_clip_path(self, *args, **kwargs): _ignored("Collection.set_clip_path")
    def set_offset_transform(self, value): return self
    def set_transform(self, value): return self


class LineCollection(Collection):
    def __init__(self, segments, colors=None, linewidths=None, label="", **kwargs):
        super().__init__(colors=colors, linewidths=linewidths, label=label, **kwargs)
        self._segments = [np.asarray(seg, dtype=float).reshape(-1, 2) for seg in segments]

    def get_segments(self): return self._segments
    def set_segments(self, segments):
        self._segments = [np.asarray(seg, dtype=float).reshape(-1, 2) for seg in segments]
        return self
    def get_offsets(self): return None


class PolyCollection(LineCollection):
    def __init__(self, verts, colors=None, **kwargs):
        loops = []
        for vert in verts:
            points = np.asarray(vert, dtype=float).reshape(-1, 2)
            loops.append(np.vstack([points, points[:1]]) if len(points) else points)
        super().__init__(loops, colors=colors, **kwargs)

    def set_verts(self, verts, closed=True):
        self._segments = [np.vstack([np.asarray(v, dtype=float).reshape(-1, 2),
                                      np.asarray(v, dtype=float).reshape(-1, 2)[:1]])
                          for v in verts]
        return self


class PatchCollection(LineCollection):
    def __init__(self, patches, colors=None, **kwargs):
        self._patches = list(patches)
        super().__init__([], colors=colors, **kwargs)

    def get_segments(self):
        out = []
        for patch in self._patches:
            entry = _patch_entry(patch)
            if entry is None:
                continue
            if entry["kind"] == "rect":
                x, y, w, h = entry["x"], entry["y"], entry["width"], entry["height"]
                pts = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]])
                out.append(pts)
            elif entry["points"]:
                pts = np.asarray(entry["points"], dtype=float).reshape(-1, 2)
                out.append(np.vstack([pts, pts[:1]]))
        return out

    def set_paths(self, patches):
        self._patches = list(patches)
        return self


class EventCollection(LineCollection):
    def __init__(self, positions, orientation="horizontal", lineoffset=0, linelength=1, **kwargs):
        positions = np.asarray(positions, dtype=float).ravel()
        if orientation in ("horizontal", "vertical"):
            if orientation == "horizontal":
                segs = [[(p, lineoffset - linelength / 2), (p, lineoffset + linelength / 2)]
                        for p in positions]
            else:
                segs = [[(lineoffset - linelength / 2, p), (lineoffset + linelength / 2, p)]
                        for p in positions]
        else:
            raise ValueError(f"unsupported orientation: {orientation!r}")
        super().__init__(segs, **kwargs)


class ConnectionPatch(FancyArrowPatch):
    def __init__(self, xyA, xyB, coordsA="data", coordsB="data", axesA=None, axesB=None,
                 **kwargs):
        super().__init__(posA=xyA, posB=xyB, **kwargs)
        self.coordsA, self.coordsB = coordsA, coordsB
        self.axesA, self.axesB = axesA, axesB


patches.ConnectionPatch = ConnectionPatch


class Line2D:
    """Handle for a plotted series, mirroring Matplotlib's `Line2D` setters.

    It mutates the series the axes will draw, so `line, = plot(...)` followed by
    `line.set_color(...)` behaves like Matplotlib.
    """

    def __init__(self, series, ydata=None, **kwargs):
        if ydata is not None:
            series = _series(np.arange(len(series)), series,
                             kwargs.get("label", ""), kwargs.get("color", _CYCLE[0]),
                             linestyle=kwargs.get("linestyle", kwargs.get("ls", "-")),
                             linewidth=kwargs.get("linewidth", kwargs.get("lw", 1.5)))
        self._series = series

    def __getitem__(self, key):
        return self._series[key]

    def __setitem__(self, key, value):
        self._series[key] = value

    def __iter__(self): return iter(self._series)
    def __len__(self): return len(self._series)

    def update_from(self, other):
        if getattr(other, "_series", None) is not None:
            self._series.update(other._series)
        return self

    def get_xdata(self): return self._series["x"]
    def get_ydata(self): return self._series["y"]
    def set_xdata(self, x): self._series["x"] = _as_f64(x)
    def set_ydata(self, y): self._series["y"] = _as_f64(y)

    def set_data(self, x, y):
        self.set_xdata(x)
        self.set_ydata(y)

    def get_color(self): return self._series["color"]
    def set_color(self, color): self._series["color"] = _norm_color(color)
    def get_alpha(self): return self._series["alpha"]
    def set_alpha(self, alpha):
        self._series["alpha"] = None if alpha is None else float(alpha)
    def get_linewidth(self): return self._series["linewidth"]
    def set_linewidth(self, linewidth): self._series["linewidth"] = float(linewidth)
    def get_linestyle(self): return self._series["linestyle"]
    def set_linestyle(self, linestyle): self._series["linestyle"] = str(linestyle)
    def get_marker(self): return self._series["marker"]
    def set_marker(self, marker): self._series["marker"] = str(marker)
    def set_markersize(self, size): self._series["markersize"] = float(size)
    def set_markerfacecolor(self, color): self._series["mfc"] = _norm_color(color)
    def set_markeredgecolor(self, color): self._series["mec"] = _norm_color(color)
    def get_label(self): return self._series["label"]
    def set_label(self, label): self._series["label"] = str(label)
    def get_drawstyle(self): return self._series["drawstyle"]
    def set_drawstyle(self, drawstyle): self._series["drawstyle"] = str(drawstyle)
    def set_path_effects(self, effects): _ignored("Line2D.set_path_effects"); return self
    def set_zorder(self, zorder): self._series["zorder"] = int(zorder)
    def get_zorder(self): return self._series.get("zorder", 2)
    def set_visible(self, visible): _ignored("Line2D.set_visible")


class _Spine:
    """Compatibility stand-in for one axes spine."""

    def __init__(self):
        self._visible = True
        self._color = None
        self._linewidth = 1.0
        self._position = ""

    def set_visible(self, visible): self._visible = bool(visible)
    def get_visible(self): return self._visible
    def set_color(self, color): self._color = color
    def get_color(self): return self._color
    def get_edgecolor(self): return self._color
    def set_linewidth(self, width): self._linewidth = float(width)
    def get_linewidth(self): return self._linewidth
    def set_position(self, position): self._position = position
    def get_position(self): return self._position
    def set_bounds(self, *args): return None
    def set_smart_bounds(self, *args): return None
    def set_zorder(self, zorder): return None
    def set_path_effects(self, effects): return None


class _Spines:
    """The four axes spines, addressable as a mapping or as attributes."""

    def __init__(self):
        self.left = _Spine()
        self.right = _Spine()
        self.bottom = _Spine()
        self.top = _Spine()

    def __getitem__(self, name): return getattr(self, name)
    def __iter__(self): return iter(("left", "right", "bottom", "top"))
    def keys(self): return ("left", "right", "bottom", "top")
    def values(self): return (self.left, self.right, self.bottom, self.top)
    def items(self): return ((name, getattr(self, name)) for name in self)


class _Axis:
    """Stand-in for `ax.xaxis` / `ax.yaxis` with tick and label shims."""

    def __init__(self, parent, axis):
        self._parent, self._axis = parent, axis
        self.label = _TextLabel()
        self.offsetText = _TextLabel()
        self._visible = True
        self._locator = None
        self._formatter = None

    def _labels(self):
        return (self._parent.get_xticklabels() if self._axis == "x"
                else self._parent.get_yticklabels())

    def _ticks(self):
        return (self._parent.get_xticks() if self._axis == "x"
                else self._parent.get_yticks())

    def set_visible(self, visible): self._visible = bool(visible)
    def get_visible(self): return self._visible
    def get_label(self): return self.label
    def get_offset_text(self): return self.offsetText

    def set_label_text(self, label, fontdict=None, **kwargs):
        if self._axis == "x":
            self._parent.set_xlabel(label, fontsize=kwargs.get("fontsize", kwargs.get("size")))
        else:
            self._parent.set_ylabel(label, fontsize=kwargs.get("fontsize", kwargs.get("size")))
        self.label.set_text(label)
        return self.label

    def set_label_coords(self, x, y, transform=None): return None
    def set_label_position(self, position): return None
    def set_ticks_position(self, position): return None
    def tick_top(self): return None
    def tick_bottom(self): return None
    def tick_left(self): return None
    def tick_right(self): return None
    def set_tick_params(self, **kwargs): self._parent._tick_style(self._axis, **kwargs)
    def set_ticks(self, ticks, labels=None, **kwargs):
        if self._axis == "x": self._parent.set_xticks(ticks, labels=labels, **kwargs)
        else: self._parent.set_yticks(ticks, labels=labels, **kwargs)
    def get_ticklocs(self): return self._ticks()
    def get_ticklabels(self, *args, **kwargs): return self._labels()
    def get_majorticklabels(self): return self._labels()
    def get_minorticklabels(self): return []
    def get_major_ticks(self): return []
    def get_minor_ticks(self): return []
    def set_ticklabels(self, labels, **kwargs):
        if self._axis == "x": self._parent.set_xticklabels(labels, **kwargs)
        else: self._parent.set_yticklabels(labels, **kwargs)
    def set_major_locator(self, locator): self._locator = locator
    def set_minor_locator(self, locator): return None
    def set_major_formatter(self, formatter): self._formatter = formatter
    def set_minor_formatter(self, formatter): return None
    def get_major_locator(self): return self._locator
    def get_major_formatter(self): return self._formatter
    def set_units(self, units): return None
    def get_units(self): return None
    def update_units(self, data): return None
    def set_inverted(self, inverted):
        target = self._parent._inverted[0 if self._axis == "x" else 1]
        if bool(inverted) != target:
            if self._axis == "x": self._parent.invert_xaxis()
            else: self._parent.invert_yaxis()
    def get_inverted(self): return self._parent._inverted[0 if self._axis == "x" else 1]
    def get_transform(self): return _Transform()
    def get_scale(self): return self._parent.get_xscale() if self._axis == "x" else self._parent.get_yscale()
    def set_scale(self, value, **kwargs):
        if self._axis == "x": self._parent.set_xscale(value, **kwargs)
        else: self._parent.set_yscale(value, **kwargs)
    def grid(self, visible=None, **kwargs): self._parent.grid(visible, axis=self._axis, **kwargs)


class _Callbacks:
    def connect(self, *args, **kwargs): return 1
    def disconnect(self, *args, **kwargs): return None


class _Manager:
    def __init__(self, canvas): self.canvas = canvas
    def set_window_title(self, *args, **kwargs): return None
    def get_window_title(self): return ""
    def destroy(self): return None


class _Canvas:
    """Headless canvas stand-in for code that calls draw or print_figure."""

    def __init__(self, figure):
        self.figure = figure
        self.manager = _Manager(self)
    def draw(self, *args, **kwargs): return None
    def draw_idle(self, *args, **kwargs): return None
    def flush_events(self): return None
    def get_renderer(self, *args, **kwargs): return None
    def get_width_height(self):
        w, h = self.figure.get_size_inches()
        dpi = self.figure.get_dpi()
        return int(w * dpi), int(h * dpi)
    def print_figure(self, filename, **kwargs):
        return self.figure.savefig(filename, **kwargs)
    def mpl_connect(self, *args, **kwargs): return 1
    def mpl_disconnect(self, *args, **kwargs): return None
    def blit(self, *args, **kwargs): return None
    def restore_region(self, *args, **kwargs): return None
    def copy_from_bbox(self, *args, **kwargs): return None
    def new_timer(self, *args, **kwargs): return None
    def set_window_title(self, *args, **kwargs): return None
    def start_event_loop(self, *args, **kwargs): return None
    def stop_event_loop(self, *args, **kwargs): return None


class _SubplotPars:
    def __init__(self):
        self.left, self.right, self.bottom, self.top = 0.125, 0.9, 0.11, 0.88
        self.wspace, self.hspace = 0.2, 0.2

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self


class Axes:
    def __init__(self, pos):
        self.pos, self.lines, self.texts = pos, [], []
        self.images, self.annotations = [], []
        self.contours = []
        self.errors = []
        self.scatter_pts = []
        self.arrows = []
        self.bars = []
        self.bands = []
        self._hline_refs = []
        self._vline_refs = []
        self.hspans = []
        self.vspans = []
        self.aspect = None
        self.title = self.xlabel = self.ylabel = ""
        self.show_legend, self.xlim, self.ylim = False, None, None
        self._sticky_x, self._sticky_y = [], []
        self.visible, self._removed, self._axis_off = True, False, False
        self.artists, self.label, self.zorder = [], "", 0
        self.facecolor, self.alpha = None, None
        self.xscale = self.yscale = "linear"
        self.log_base = 10.0
        self.show_grid = False
        self.grid_color = self.grid_linewidth = self.grid_alpha = self.grid_linestyle = None
        self.grid_axis = "both"
        self.minor_ticks = False
        self.tick_params_box = {}
        self.tick_params_x = {}
        self.tick_params_y = {}
        self.legend_loc = "best"
        self.legend_ncol = 1
        self.legend_frameon = True
        self.legend_fontsize = None
        self.legend_title = ""
        self.legend_title_fontsize = None
        self.legend_anchor = None
        self.title_size = self.xlabel_size = self.ylabel_size = None
        self.transAxes = _CoordTransform("axes")
        self.transData = _CoordTransform("data")
        self.patch = Rectangle((0, 0), 1, 1, transform=self.transAxes,
                               facecolor=self.get_facecolor(), edgecolor="none")
        self._axlines = []
        self._xticks = self._yticks = None
        self._xticklabels = self._yticklabels = None
        self._x_date = False
        self._categories = []
        self._inverted = [False, False]
        self._pos_override = None
        self._share_x = self._share_y = None
        self.hide_xticklabels = self.hide_yticklabels = False
        self._prop_cycle = list(rcParams.get("axes.prop_cycle", _CYCLE))
        self._cycle_pos = 0
        self._twin, self._twin_gap, self._twin_of = "", 0.0, None
        self._fig = None
        self._colorbar = None
        self._bounds_are_axes = False
        self.xaxis = _Axis(self, "x")
        self.yaxis = _Axis(self, "y")
        self.spines = _Spines()
        self.patches = []
        self.collections = []
        self.callbacks = _Callbacks()
        self._box_aspect = None
        self._axes_locator = None

    def _next_color(self):
        cycle = self._prop_cycle or _CYCLE
        color = cycle[self._cycle_pos % len(cycle)]
        self._cycle_pos += 1
        return color

    def set_prop_cycle(self, *args, **kwargs):
        """Replace the colour cycle used by artists without an explicit colour."""
        colors = kwargs.get("color", kwargs.get("colors"))
        if colors is None and args:
            arg = args[0]
            if arg is None:
                colors = list(rcParams.get("axes.prop_cycle", _CYCLE))
            elif hasattr(arg, "by_key"):
                colors = arg.by_key().get("color")
            elif isinstance(arg, dict):
                colors = arg.get("color")
            elif isinstance(arg, str):
                colors = [arg]
            else:
                colors = arg
        if colors is None:
            raise ValueError("set_prop_cycle needs a color sequence")
        if isinstance(colors, str) or _is_rgb(colors):
            colors = [colors]
        self._prop_cycle = [_norm_color(c) for c in colors]
        self._cycle_pos = 0
        return self

    def get_prop_cycle(self):
        return _PropCycler(self._prop_cycle)

    def plot(self, *args, label="", color=None, c=None, linestyle=None, ls=None,
             linewidth=None, lw=None, marker=None, markersize=None, ms=None,
             markerfacecolor=None, mfc=None, markeredgecolor=None, mec=None,
             markeredgewidth=None, mew=None, alpha=None, drawstyle="default", fmt=None,
             data=None, x=None, y=None, **kwargs):
        """Line plot with matplotlib's styling keywords (`lw`, `ls`, `marker`, `ms`,
        `mfc`/`mec`, `alpha`, `drawstyle`) and fmt-string shorthand (`"r--o"`).
        `data=` accepts a DataFrame/Series and `x=`/`y=` may name its columns."""
        args = _resolve_data_args(args, data, x, y)
        if drawstyle == "steps":
            drawstyle = "steps-pre"
        if drawstyle not in ("default", "steps-pre", "steps-mid", "steps-post"):
            raise ValueError(f"unsupported drawstyle: {drawstyle!r}")
        handles = []
        for index, (gx, gy, gfmt) in enumerate(_plot_args(args, fmt)):
            if gy is None:
                gx, gy = np.arange(len(gx)), gx
            gfmt = gfmt or (fmt if index == 0 else None)
            if not label and getattr(gy, "name", None) is not None:
                glabel = str(gy.name)
            else:
                glabel = label if index == 0 else ""
            style = linestyle or ls or "-"
            gcolor, gmarker = color or c, marker
            if gfmt:
                f_color, f_style, f_marker = _parse_fmt(gfmt)
                gcolor = gcolor or f_color
                if linestyle is None and ls is None:
                    style = f_style or style
                if not gmarker:
                    gmarker = f_marker
            line_color = gcolor or self._next_color()
            edge = markeredgecolor or mec
            xvals = self._xdate(gx)
            series_style = drawstyle
            if drawstyle == "steps-mid":
                xvals, gy = _mid_steps(xvals, gy)
                series_style = "steps-post"
            handle = _series(
                xvals, gy, glabel, line_color, linestyle=style,
                linewidth=linewidth if linewidth is not None else (lw if lw is not None else rcParams.get("lines.linewidth", 2.0)),
                marker=gmarker or "",
                markersize=markersize if markersize is not None else (ms if ms is not None else rcParams.get("lines.markersize", 6.0)),
                mfc=markerfacecolor or mfc, mec=edge,
                mew=markeredgewidth if markeredgewidth is not None else (mew if mew is not None else rcParams.get("lines.markerlinewidth", 1.0)),
                alpha=alpha, drawstyle=series_style)
            self.lines.append(handle)
            handles.append(Line2D(handle))
        return handles

    def set_aspect(self, aspect, adjustable=None, anchor=None, share=False):
        self.aspect = _norm_aspect(aspect)

    def get_aspect(self): return self.aspect

    # -- introspection / compatibility surface --------------------------------
    def draw(self, *args, **kwargs): return None

    def get_position(self, original=False):
        """Figure-fraction box: the grid cell, or whatever `set_position` stored."""
        if self._pos_override is not None:
            x, y, w, h = self._pos_override
            return _Bbox(x, y, x + w, y + h)
        rows, cols = self._fig.grid if self._fig is not None else (1, 1)
        r, c = divmod(self.pos, cols)
        return _Bbox(c / cols, 1.0 - (r + 1) / rows, (c + 1) / cols, 1.0 - r / rows)

    def set_position(self, pos):
        self._pos_override = tuple(float(v) for v in pos)
        self._bounds_are_axes = True

    def _render_bounds(self, dpi=None):
        """Expand an axes rectangle by the renderer's label margins.

        Matplotlib's `add_axes`/`set_position` rectangle is the axes box, not
        the outer panel; the fixed tick, label and title margins live outside
        it. The renderer takes a panel rectangle, so add those margins back
        before drawing.
        """
        if self._pos_override is None:
            return None
        if not getattr(self, "_bounds_are_axes", False) or self._fig is None:
            return self._pos_override
        dpi = float(self._fig.get_dpi() if dpi is None else dpi)
        fw, fh = self._fig.get_size_inches()
        width, height = fw * dpi, fh * dpi
        if width <= 0.0 or height <= 0.0:
            return self._pos_override
        left, right, bottom = 70.0 / width, 25.0 / width, 60.0 / height
        title_pad = 0.0
        if self.title:
            title_size = float(self.title_size or rcParams.get("axes.titlesize", 12.0))
            title_pad = title_size * dpi / 72.0 * 1.24 * 1.45 + 4.0
        top = (25.0 + title_pad) / height
        x, y, w, h = self._pos_override
        x0, y0 = max(0.0, x - left), max(0.0, y - bottom)
        x1, y1 = min(1.0, x + w + right), min(1.0, y + h + top)
        return (x0, y0, max(x1 - x0, 0.01), max(y1 - y0, 0.01))

    def inset_axes(self, bounds, *, transform=None, zorder=5, **kwargs):
        """Place a child axes inside this one, in axes-fraction coordinates."""
        if self._fig is None:
            raise RuntimeError("inset_axes needs an axes attached to a figure")
        kind = getattr(transform, "kind", "axes") if transform is not None else "axes"
        if kind != "axes":
            raise NotImplementedError("inset_axes only supports axes-fraction bounds")
        if len(bounds) != 4:
            raise ValueError("inset_axes bounds must be (x, y, width, height)")
        x, y, w, h = (float(v) for v in bounds)
        box = self.get_position()
        child = Axes(len(self._fig.axes))
        child._fig = self._fig
        child._pos_override = (box.x0 + x * box.width, box.y0 + y * box.height,
                               w * box.width, h * box.height)
        child._bounds_are_axes = True
        child.zorder = int(zorder)
        self._fig.axes.append(child)
        self._fig._cur = child
        return child

    def twinx(self):
        """A second axes sharing the x axis, with its own y axis on the right."""
        return self._make_twin("y")

    def twiny(self):
        """A second axes sharing the y axis, with its own x axis on top."""
        return self._make_twin("x")

    def _make_twin(self, axis):
        if self._fig is None:
            raise RuntimeError("twinx/twiny needs an axes attached to a figure")
        fig = self._fig
        box = self.get_position()
        if axis == "y":
            gap = 60.0 / (fig.figsize[0] * fig.get_dpi())
            base = (box.x0, box.y0, max(box.width - gap, 0.05), box.height)
        else:
            gap = 50.0 / (fig.figsize[1] * fig.get_dpi())
            base = (box.x0, box.y0, box.width, max(box.height - gap, 0.05))
        self._pos_override = base
        self._bounds_are_axes = False
        twin = Axes(self.pos)
        twin._fig, twin._twin, twin._twin_gap = fig, axis, gap
        twin._twin_of = self
        twin._pos_override = box.bounds
        twin._bounds_are_axes = False
        twin.facecolor = "none"
        if axis == "y":
            group = self._share_x or _Share()
            if self._share_x is None:
                group.axes.append(self)
                self._share_x = group
                group.limits = self.xlim
            twin._share_x = group
        else:
            group = self._share_y or _Share()
            if self._share_y is None:
                group.axes.append(self)
                self._share_y = group
                group.limits = self.ylim
            twin._share_y = group
        group.axes.append(twin)
        fig.axes.append(twin)
        fig._cur = twin
        return twin

    def _artist_extents(self):
        """Data bounds of registered patches and collections."""
        xs, ys = [], []
        for artist in self.artists:
            patch = _patch_entry(artist)
            if patch is not None:
                if patch["kind"] == "rect":
                    xs += [patch["x"], patch["x"] + patch["width"]]
                    ys += [patch["y"], patch["y"] + patch["height"]]
                elif patch["kind"] == "circle":
                    xs += [patch["x"] - patch["width"], patch["x"] + patch["width"]]
                    ys += [patch["y"] - patch["width"], patch["y"] + patch["width"]]
                else:
                    pts = np.asarray(patch["points"], dtype=float).reshape(-1, 2)
                    xs += pts[:, 0].tolist()
                    ys += pts[:, 1].tolist()
                continue
            coll = _collection_entry(artist)
            if coll is not None:
                for flat in [coll["points"], *coll["segments"]]:
                    pts = np.asarray(flat, dtype=float)
                    if pts.size:
                        pts = pts.reshape(-1, 2)
                        xs += pts[:, 0].tolist()
                        ys += pts[:, 1].tolist()
        return xs, ys

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
        for a in self.arrows:
            xs.extend(a["x"])
            xs.extend(a["x"] + a["u"])
        for bars in self.bars:
            xs.extend(bars["left"])
            xs.extend(bars["left"] + bars["width"])
        for band in self.bands:
            xs.extend(band["x"])
        for e in self.errors:
            xs.extend(e[0] - e[4])
            xs.extend(e[0] + e[5])
        xs.extend(self._artist_extents()[0])
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
        for a in self.arrows:
            ys.extend(a["y"])
            ys.extend(a["y"] + a["v"])
        for bars in self.bars:
            ys.extend(bars["bottom"])
            ys.extend(bars["bottom"] + bars["height"])
        for band in self.bands:
            ys.extend(band["y"])
        for e in self.errors:
            ys.extend(e[1] - e[2])
            ys.extend(e[1] + e[3])
        ys.extend(self._artist_extents()[1])
        return _span(ys)

    def get_xlim(self):
        extent = self._extent_x()
        group = self._share_x
        explicit = group.limits if group is not None else self.xlim
        lo, hi = explicit or (group.union("x") if group is not None else extent)
        lo, hi = _log_bounds(lo, hi, self.xscale, extent)
        if explicit:
            return (lo, hi)
        sticky = [e for im in self.images for e in (im["extent"][0], im["extent"][1])]
        sticky += self._sticky_x + [float(c["x"][k]) for c in self.contours for k in (0, -1)]
        return _margin(lo, hi, self.xscale, sticky)

    def get_ylim(self):
        extent = self._extent_y()
        group = self._share_y
        explicit = group.limits if group is not None else self.ylim
        lo, hi = explicit or (group.union("y") if group is not None else extent)
        lo, hi = _log_bounds(lo, hi, self.yscale, extent)
        if explicit:
            return (lo, hi)
        sticky = [e for im in self.images for e in (im["extent"][2], im["extent"][3])]
        sticky += self._sticky_y + [float(c["y"][k]) for c in self.contours for k in (0, -1)]
        return _margin(lo, hi, self.yscale, sticky)
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

    def get_facecolor(self):
        return self.facecolor or rcParams.get("axes.facecolor", "white")

    def set_facecolor(self, color): self.facecolor = str(color)
    def get_alpha(self): return self.alpha
    def set_alpha(self, alpha): self.alpha = None if alpha is None else float(alpha)

    def get_transform(self): return _Transform()
    @property
    def bbox(self): return self.get_window_extent()
    def get_xticklines(self): return []
    def get_yticklines(self): return []
    def get_legend(self): return None
    def get_legend_handles_labels(self):
        handles, labels = [], []
        for entry in self.lines:
            if entry.get("label"):
                handles.append(Line2D(entry))
                labels.append(entry["label"])
        return handles, labels

    def specgram(self, *args, **kwargs): return None
    def psd(self, *args, **kwargs): return None
    def magnitude_spectrum(self, *args, **kwargs): return None
    def set_rorigin(self, value): return None
    def set_rlabel_position(self, value): return None
    def set_thetalim(self, *args, **kwargs): return None
    def pie_label(self, *args, **kwargs): return None

    def get_window_extent(self, renderer=None):
        """Pixel box covering the axes plus the space its labels and title use."""
        b = self.get_position()
        w, h = self._fig.figsize if self._fig is not None else (6.4, 4.8)
        dpi = self._fig.dpi if self._fig is not None else DPI
        scale = dpi / 100.0
        if self._axis_off:
            left_pad = bottom_pad = 10.0
        else:
            left_pad = 55.0 + (8.0 if self.ylabel else 0.0)
            bottom_pad = 40.0 + (8.0 if self.xlabel else 0.0)
        size = self.title_size or float(rcParams.get("axes.titlesize", 12.0))
        top_pad = 10.0 + (size * 1.6 if self.title else 0.0)
        return _Bbox(b.x0 * w * dpi - left_pad * scale,
                     b.y0 * h * dpi - bottom_pad * scale,
                     b.x1 * w * dpi + 10.0 * scale,
                     b.y1 * h * dpi + top_pad * scale)

    def get_tightbbox(self, renderer=None): return self.get_window_extent(renderer)
    def get_figure(self, root=None): return self._fig

    @property
    def figure(self): return self._fig

    @figure.setter
    def figure(self, value): self._fig = value

    def get_xaxis_transform(self, which="grid"): return _Transform()
    def get_yaxis_transform(self, which="grid"): return _Transform()
    def get_gridspec(self): return getattr(self._fig, "_gridspec", None)
    def set_box_aspect(self, aspect, **kwargs): self._box_aspect = aspect
    def get_box_aspect(self): return self._box_aspect
    def set_axes_locator(self, locator): self._axes_locator = locator
    def get_axes_locator(self): return self._axes_locator
    def set_autoscale_on(self, value): _ignored("Axes.set_autoscale_on")
    def set_autoscalex_on(self, value): _ignored("Axes.set_autoscalex_on")
    def set_autoscaley_on(self, value): _ignored("Axes.set_autoscaley_on")
    def set_axisbelow(self, value): _ignored("Axes.set_axisbelow")
    def set_frame_on(self, value): _ignored("Axes.set_frame_on")
    def set_xmargin(self, value): _ignored("Axes.set_xmargin")
    def set_ymargin(self, value): _ignored("Axes.set_ymargin")
    def get_frame_on(self): return True
    def label_outer(self, **kwargs): _ignored("Axes.label_outer")
    def locator_params(self, *args, **kwargs): _ignored("Axes.locator_params")
    def set_rmax(self, value): return None
    def set_rmin(self, value): return None
    def set_rlim(self, *args, **kwargs): return None
    def clabel(self, *args, **kwargs): return []
    def secondary_xaxis(self, *args, **kwargs): _ignored("Axes.secondary_xaxis"); return self
    def secondary_yaxis(self, *args, **kwargs): _ignored("Axes.secondary_yaxis"); return self
    def get_aux_axes(self, *args, **kwargs): return self
    def barbs(self, *args, **kwargs): return self.quiver(*args, **kwargs)

    def add_artist(self, artist): self.artists.append(artist); return artist
    def add_patch(self, patch):
        self.artists.append(patch)
        self.patches.append(patch)
        return patch
    def add_collection(self, collection, autolim=True):
        self.artists.append(collection)
        self.collections.append(collection)
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
        self._sticky_x, self._sticky_y = [], []
        self.annotations.clear()
        self.contours.clear()
        self.errors.clear()
        self.scatter_pts.clear()
        self.arrows.clear()
        self.bars.clear()
        self.bands.clear()
        self._hline_refs.clear()
        self._vline_refs.clear()
        self.hspans.clear()
        self.vspans.clear()
        self.artists.clear()
        self.patches.clear()
        self.collections.clear()
        self.title = self.xlabel = self.ylabel = ""
        self.title_size = self.xlabel_size = self.ylabel_size = None
        self.show_legend, self.xlim, self.ylim = False, None, None
        self._xticks = self._yticks = None
        self._xticklabels = self._yticklabels = None
        self._x_date = False
        self._categories = []
        self.show_grid = False
        self.grid_color = self.grid_linewidth = self.grid_alpha = self.grid_linestyle = None
        self.grid_axis = "both"
        self.tick_params_x.clear()
        self.tick_params_y.clear()
        self.tick_params_box.clear()
        self.legend_loc, self.legend_ncol = "best", 1
        self.legend_frameon, self.legend_fontsize = True, None
        self.legend_title, self.legend_title_fontsize = "", None
        self.legend_anchor = None
        self._axlines.clear()

    cla = clear

    def _xdate(self, values):
        """Convert date-like or categorical x values to numbers and mark the axis."""
        if _looks_like_dates(values):
            self._x_date = True
            return _date_to_num(values)
        if _looks_like_categories(values):
            array = np.asarray(values)
            labels = [str(v) for v in array.ravel()]
            for label in labels:
                if label not in self._categories:
                    self._categories.append(label)
            index = {label: i for i, label in enumerate(self._categories)}
            mapped = np.asarray([index[label] for label in labels], dtype=np.float64)
            return mapped.reshape(array.shape)
        return values

    def set_xticks(self, ticks, labels=None, rotation=None, fontsize=None,
                   color=None, **kwargs):
        self._xticks = [float(t) for t in np.asarray(self._xdate(ticks)).ravel()]
        if labels is not None:
            self._xticklabels = [str(v) for v in np.asarray(labels).ravel()]
        else:
            self._xticklabels = None
        self._tick_style("x", rotation=rotation, labelsize=fontsize, labelcolor=color)

    def set_yticks(self, ticks, labels=None, rotation=None, fontsize=None,
                   color=None, **kwargs):
        self._yticks = [float(t) for t in np.asarray(ticks).ravel()]
        if labels is not None:
            self._yticklabels = [str(v) for v in np.asarray(labels).ravel()]
        self._tick_style("y", rotation=rotation, labelsize=fontsize, labelcolor=color)

    def _tick_style(self, axis, **kwargs):
        """Merge tick styling into the per-axis settings (`axis` is x or y)."""
        target = self.tick_params_x if axis == "x" else self.tick_params_y
        aliases = {"labelsize": "labelsize", "fontsize": "labelsize",
                   "labelcolor": "labelcolor", "color": "labelcolor",
                   "rotation": "rotation", "length": "length",
                   "width": "width", "pad": "pad", "direction": "direction",
                   "tickcolor": "color"}
        for key, value in kwargs.items():
            if value is not None and key in aliases:
                target[aliases[key]] = value

    def xticks(self, ticks=None, labels=None, **kwargs):
        """`plt.xticks(...)` shim: set ticks/labels or return the current pair."""
        if ticks is None:
            return (self.get_xticks(), self.get_xticklabels())
        self.set_xticks(ticks, labels=labels, **kwargs)
        return (self.get_xticks(), self.get_xticklabels())

    def yticks(self, ticks=None, labels=None, **kwargs):
        """`plt.yticks(...)` shim, mirroring `xticks`."""
        if ticks is None:
            return (self.get_yticks(), self.get_yticklabels())
        self.set_yticks(ticks, labels=labels, **kwargs)
        return (self.get_yticks(), self.get_yticklabels())

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
                    if key in {"frame_on", "xmargin", "ymargin", "axisbelow",
                               "autoscale_on", "autoscalex_on", "autoscaley_on",
                               "xbound", "ybound"}:
                        continue
                    raise AttributeError(f"Axes.set() does not support {key!r}")
                setter(value)

    def text(self, x, y, s, fontdict=None, **kwargs):
        """Place text at (x, y); `transform` may be `ax.transAxes` or
        `fig.transFigure` to use axes- or figure-fraction coordinates. Other
        Matplotlib text properties are accepted but not drawn yet."""
        transform, fontsize, colour, ha, va = _text_props(fontdict, kwargs)
        if ha not in ("left", "center", "right"):
            raise ValueError(f"unsupported ha: {ha!r}")
        if va == "center_baseline":
            va = "center"
        if va not in ("baseline", "bottom", "center", "top"):
            raise ValueError(f"unsupported va: {va!r}")
        kind = getattr(transform, "kind", "data") if transform is not None else "data"
        if kind not in ("data", "axes", "figure"):
            raise ValueError(f"unsupported text transform: {transform!r}")
        size = _font_size(fontsize, rcParams.get("font.size", 10.0))
        colour = colour if colour is not None else rcParams.get("text.color", "black")
        if kind == "data":
            x = self._xdate(x)
        self.texts.append((float(x), float(y), _mathtext(s), _norm_color(colour), size, ha, va, kind))

    def imshow(self, X, cmap=None, vmin=None, vmax=None, extent=None, origin="upper",
               interpolation=None, aspect=None, alpha=None, clim=None, **kwargs):
        """Draw an array as an image. `X` is 2-D (mapped through `cmap`) or
        (H, W, 3|4) RGB(A) floats in 0-1. `interpolation` accepts `none`,
        `nearest`, `antialiased`, `bilinear` or `bicubic`; `alpha` scales the
        image's opacity. `clim` and Matplotlib's extra artist kwargs are accepted."""
        if clim is not None:
            vmin, vmax = clim
        if interpolation is not None:
            interpolation = {
                "spline16": "bicubic", "spline36": "bicubic", "hanning": "bilinear",
                "hamming": "bilinear", "hermite": "bicubic", "kaiser": "bicubic",
                "quadric": "bicubic", "catrom": "bicubic", "gaussian": "bicubic",
                "lanczos": "bicubic", "blackman": "bilinear", "sinc": "bicubic",
            }.get(str(interpolation).lower(), interpolation)
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
        # No resampling by default: pixels are drawn as-is.
        interp = "nearest" if interpolation is None else str(interpolation).lower()
        if interp == "auto":
            interp = "antialiased"
        if interp not in ("none", "nearest", "antialiased", "bilinear", "bicubic"):
            raise ValueError(f"unsupported interpolation: {interpolation!r}")
        opacity = 1.0 if alpha is None else float(alpha)
        if not np.isfinite(opacity):
            raise ValueError("alpha must be finite")
        entry = dict(data=a, cmap=_cmap_name(cmap), vmin=vmin, vmax=vmax,
                     extent=tuple(float(v) for v in extent),
                     alpha=float(np.clip(opacity, 0.0, 1.0)), interpolation=interp)
        self.images.append(entry)
        # matplotlib's image.aspect default is "equal".
        self.set_aspect("equal" if aspect is None else aspect)
        return AxesImage(entry, self)

    def hist(self, x, bins=10, range=None, density=False, weights=None, cumulative=False,
             bottom=None, histtype="bar", align="mid", orientation="vertical", color=None,
             label=None, alpha=None, edgecolor=None, stacked=False, **kwargs):
        """Histogram of `x`, drawn as bars; returns `(counts, edges, handles)`."""
        if histtype not in ("bar", "step", "stepfilled"):
            raise NotImplementedError(f"histtype={histtype!r} is not supported yet")
        data = np.asarray(x, dtype=np.float64).ravel()
        bins = _validate_bins(bins)
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
                                    alpha=alpha, label=lab)
            elif orientation == "vertical":
                handles = self.bar(centers, counts, width=widths, bottom=base,
                                   align=bar_align, color=color, edgecolor=edgecolor,
                                   alpha=alpha, label=lab)
            else:
                raise ValueError(f"unsupported orientation: {orientation!r}")
            return np.asarray(counts, dtype=np.float64), edges, handles
        if orientation != "vertical":
            raise NotImplementedError("histtype step needs orientation='vertical'")
        sx = np.empty(2 * counts.size)
        sy = np.empty(2 * counts.size)
        sx[0::2], sx[1::2] = edges[:-1], edges[1:]
        sy[0::2], sy[1::2] = counts, counts
        if histtype == "stepfilled":
            self.fill_between(sx, sy, np.repeat(base, 2), color=color, alpha=alpha)
        handles = self.plot(sx, sy, color=color, label=lab)
        return np.asarray(counts, dtype=np.float64), edges, handles

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
        cap = _fill(wid if capwidths is None else capwidths, n)
        box_style = dict(boxprops or {})
        median_style = dict(medianprops or {})
        whisker_style = dict(whiskerprops or {})
        cap_style = dict(capprops or {})
        flier_style = dict(flierprops or {})
        mean_style = dict(meanprops or {})
        box_color = _single_color(box_style.get("color", box_style.get("c")), _CYCLE[0])
        box_edge = _single_color(box_style.get("edgecolor", box_style.get("ec")), box_color)
        box_width = _number(box_style.get("linewidth", box_style.get("lw")), 1.5)
        median_color = _single_color(median_style.get("color", median_style.get("c")), _CYCLE[1])
        median_width = _number(median_style.get("linewidth", median_style.get("lw")), 1.5)
        whisker_color = _single_color(whisker_style.get("color", whisker_style.get("c")), box_color)
        whisker_width = _number(whisker_style.get("linewidth", whisker_style.get("lw")), 1.5)
        cap_color = _single_color(cap_style.get("color", cap_style.get("c")), whisker_color)
        cap_width = _number(cap_style.get("linewidth", cap_style.get("lw")), 1.5)
        mean_color = _single_color(mean_style.get("color", mean_style.get("c")), _CYCLE[2])
        parsed_color, _, parsed_marker = _stem_fmt(str(sym or ""), None)
        flier_color = _single_color(
            flier_style.get("markerfacecolor", flier_style.get("mfc",
                             flier_style.get("color", flier_style.get("c")))),
            parsed_color or "black")
        flier_marker = str(flier_style.get("marker", parsed_marker or "o"))
        draw_caps = True if showcaps is None else bool(showcaps)
        draw_box = True if showbox is None else bool(showbox)
        draw_fliers = True if showfliers is None else bool(showfliers)
        if labels is None:
            labels = tick_labels
        out = dict(boxes=[], medians=[], whiskers=[], caps=[], fliers=[], means=[])
        for i, raw in enumerate(groups):
            vals = np.asarray(raw, dtype=np.float64).ravel()
            vals = vals[np.isfinite(vals)]
            if vals.size == 0:
                raise ValueError("boxplot datasets must not be empty")
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
                        self.bands.append(_band(xs, ys, box_color, box_style.get("alpha")))
                    entry = _series(xs, ys, "", box_edge, linewidth=box_width)
                    self.lines.append(entry)
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
                mean = float(vals.mean())
                if orientation == "vertical":
                    out["means"].append(self._stats_line(
                        [loc - half, loc + half], [mean, mean], mean_color))
                else:
                    out["means"].append(self._stats_line(
                        [mean, mean], [loc - half, loc + half], mean_color))
            if draw_fliers and fliers.size and str(sym or "") != "":
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
            shown = ([str(v) for v in labels] if labels is not None
                     else [f"{v:g}" for v in pos])
            if orientation == "vertical":
                self.set_xticks(pos, labels=shown)
            else:
                self.set_yticks(pos, labels=shown)
        return out

    def _stats_line(self, x, y, color, linewidth=1.5, linestyle="-"):
        """Append one statistics line and return its mutable handle."""
        entry = _series(x, y, "", color, linestyle=linestyle, linewidth=linewidth)
        self.lines.append(entry)
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
        line_color = _single_color(kwargs.get("linecolor", kwargs.get("edgecolor")), None)
        out = dict(bodies=[], cmeans=[], cmaxes=[], cmins=[], cbars=[])
        if quantiles is not None:
            out["cquantiles"] = []
        per_group_quantiles = None
        if quantiles is not None and isinstance(quantiles, (list, tuple)):
            if len(quantiles) == n and any(
                    isinstance(q, (list, tuple, np.ndarray)) for q in quantiles):
                per_group_quantiles = [
                    np.atleast_1d(np.asarray(q, dtype=np.float64)).ravel()
                    for q in quantiles
                ]
        for i, raw in enumerate(groups):
            vals = np.asarray(raw, dtype=np.float64).ravel()
            vals = vals[np.isfinite(vals)]
            if vals.size == 0:
                raise ValueError("violinplot datasets must not be empty")
            grid, density = _kde(vals, points, bw_method)
            peak = float(density.max())
            if not np.isfinite(peak) or peak <= 0.0:
                peak = 1.0
            loc, half = float(pos[i]), float(wid[i]) / 2.0
            scale = half / peak
            if orientation == "vertical":
                if side == "both":
                    xs = np.concatenate([loc + density * scale,
                                         (loc - density * scale)[::-1]])
                    ys = np.concatenate([grid, grid[::-1]])
                else:
                    sign = -1.0 if side in ("left", "low") else 1.0
                    xs = np.concatenate([[loc], loc + sign * density * scale, [loc]])
                    ys = np.concatenate([[grid[0]], grid, [grid[-1]]])
            else:
                if side == "both":
                    ys = np.concatenate([loc + density * scale,
                                         (loc - density * scale)[::-1]])
                    xs = np.concatenate([grid, grid[::-1]])
                else:
                    sign = -1.0 if side in ("left", "low") else 1.0
                    ys = np.concatenate([[loc], loc + sign * density * scale, [loc]])
                    xs = np.concatenate([[grid[0]], grid, [grid[-1]]])
            color = colors[i % len(colors)] if colors else self._next_color()
            entry = _band(xs, ys, color, kwargs.get("alpha"))
            self.bands.append(entry)
            out["bodies"].append(_ViolinBody(entry, color))
            if line_color is not None:
                outline = np.append(xs, xs[0])
                outline_y = np.append(ys, ys[0])
                self._stats_line(outline, outline_y, line_color)
            vmin, vmax = float(vals.min()), float(vals.max())
            horizontal = orientation == "horizontal"
            if showextrema:
                out["cmins"].append(self._stats_line(
                    [loc - half, loc + half], [vmin, vmin], "black")
                    if not horizontal else self._stats_line(
                    [vmin, vmin], [loc - half, loc + half], "black"))
                out["cmaxes"].append(self._stats_line(
                    [loc - half, loc + half], [vmax, vmax], "black")
                    if not horizontal else self._stats_line(
                    [vmax, vmax], [loc - half, loc + half], "black"))
                out["cbars"].append(self._stats_line(
                    [loc, loc], [vmin, vmax], "black")
                    if not horizontal else self._stats_line(
                    [vmin, vmax], [loc, loc], "black"))
            if showmeans:
                mean = float(vals.mean())
                out["cmeans"].append(self._stats_line(
                    [loc - half, loc + half], [mean, mean], "black")
                    if not horizontal else self._stats_line(
                    [mean, mean], [loc - half, loc + half], "black"))
            if showmedians:
                median = float(np.median(vals))
                self._stats_line(
                    [loc - half, loc + half], [median, median], "black")
            if quantiles is not None:
                q_values = (per_group_quantiles[i] if per_group_quantiles is not None
                            else np.atleast_1d(
                                np.asarray(quantiles, dtype=np.float64)).ravel())
                for q in q_values:
                    value = float(np.percentile(vals, q))
                    out["cquantiles"].append(self._stats_line(
                        [value, value], [loc - half, loc + half], "black")
                        if horizontal else self._stats_line(
                        [loc - half, loc + half], [value, value], "black"))
        return out

    def bar(self, x, height, width=0.8, bottom=0.0, color=None, edgecolor=None, label="",
            align="center", alpha=None, linewidth=None, yerr=None, **kwargs):
        """Vertical bars; `color` may be a single colour or one per bar."""
        x = np.asarray(self._xdate(x), dtype=np.float64).ravel()
        n = x.size
        h, w, b = _fill(height, n), _fill(width, n), _fill(bottom, n)
        if align not in ("center", "edge"):
            raise ValueError(f"unsupported align: {align!r}")
        left = x - w / 2.0 if align == "center" else x
        colors = _bar_colors(color if color is not None else self._next_color(), n)
        self.bars.append(dict(left=np.ascontiguousarray(left), bottom=b, width=w, height=h,
                              colors=colors, edgecolor=_norm_color(edgecolor),
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
                              colors=_bar_colors(color if color is not None else self._next_color(), n),
                              edgecolor=_norm_color(edgecolor),
                              alpha=None if alpha is None else float(alpha), label=str(label),
                              vertical=False))
        return _BarContainer([_BarHandle(self, len(self.bars) - 1, i) for i in range(n)],
                             str(label))

    def fill_between(self, x, y1, y2=0.0, where=None, interpolate=False, color=None,
                     alpha=None, label="", step=None, **kwargs):
        """Fill between two curves; `where` masks split the area into runs."""
        x = np.asarray(self._xdate(x), dtype=np.float64).ravel()
        a, b = _fill(y1, x.size), _fill(y2, x.size)
        c = color or self._next_color()
        for xs, ya, yb in _runs(x, a, b, where):
            self.bands.append(_band(np.concatenate([xs, xs[::-1]]),
                                    np.concatenate([ya, yb[::-1]]), c, alpha, label))

    def fill_betweenx(self, y, x1, x2=0.0, where=None, color=None, alpha=None, label="",
                      **kwargs):
        y = np.asarray(y, dtype=np.float64).ravel()
        a, b = _fill(self._xdate(x1), y.size), _fill(self._xdate(x2), y.size)
        c = color or self._next_color()
        for ys, xa, xb in _runs(y, a, b, where):
            self.bands.append(_band(np.concatenate([xa, xb[::-1]]),
                                    np.concatenate([ys, ys[::-1]]), c, alpha, label))

    def fill(self, *args, color=None, alpha=None, label="", **kwargs):
        """Closed polygon: `fill(x, y)` or `fill(x1, y1, x2, y2)`."""
        c = color or self._next_color()
        if len(args) == 2:
            self.bands.append(_band(_as_f64(self._xdate(args[0])), _as_f64(args[1]),
                                    c, alpha, label))
        elif len(args) == 4:
            x1, y1, x2, y2 = (_as_f64(self._xdate(a) if i in (0, 2) else _as_f64(a))
                              for i, a in enumerate(args))
            self.bands.append(_band(np.concatenate([x1, x2[::-1]]),
                                    np.concatenate([y1, y2[::-1]]), c, alpha, label))
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
        x = self._xdate(x)
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
        values = self._xdate((xmin, xmax))
        self.vspans.append(dict(xmin=float(values[0]), xmax=float(values[1]), ymin=float(ymin),
                                ymax=float(ymax), color=color, alpha=alpha, label=str(label)))

    def pcolormesh(self, *args, cmap=None, vmin=None, vmax=None, shading="auto",
                   alpha=None, norm=None, **kwargs):
        """Quad mesh: each Z cell is filled through `cmap` via the image path.

        `X`/`Y` may be cell edges (one longer than Z's axis) or cell centres.
        """
        if len(args) == 3 and _looks_like_dates(args[0]):
            args = (self._xdate(args[0]), args[1], args[2])
        x, y, z, edges = _mesh_args(args)
        rows, cols = z.shape
        if edges:
            extent = (float(x[0]), float(x[-1]), float(y[0]), float(y[-1]))
        else:
            dx = float(x[1] - x[0]) if x.size > 1 else 1.0
            dy = float(y[1] - y[0]) if y.size > 1 else 1.0
            extent = (float(x[0]) - dx / 2, float(x[-1]) + dx / 2,
                      float(y[0]) - dy / 2, float(y[-1]) + dy / 2)
        return self.imshow(z, cmap=_cmap_name(cmap), vmin=vmin, vmax=vmax,
                           extent=extent, origin="lower", alpha=alpha)

    def pcolor(self, *args, **kwargs):
        return self.pcolormesh(*args, **kwargs)

    def pcolorfast(self, *args, **kwargs):
        return self.pcolormesh(*args, **kwargs)

    def hist2d(self, x, y, bins=10, range=None, density=False, weights=None,
               cmin=None, cmax=None, cmap=None, **kwargs):
        """2-D histogram rasterised through `imshow`; returns
        `(counts, xedges, yedges, image)`."""
        x = np.asarray(x, dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        bins = _validate_bins(bins, max_cells=_MAX_BIN_CELLS)
        counts, xedges, yedges = np.histogram2d(
            x, y, bins=bins, range=range, density=bool(density), weights=weights)
        image = self.imshow(counts.T, cmap=_cmap_name(cmap), vmin=cmin, vmax=cmax,
                            extent=(float(xedges[0]), float(xedges[-1]),
                                    float(yedges[0]), float(yedges[-1])),
                            origin="lower")
        self.set_aspect("auto")
        return counts, xedges, yedges, image

    def hexbin(self, x, y, C=None, gridsize=100, bins=None, xscale="linear",
               yscale="linear", extent=None, cmap=None, norm=None, vmin=None,
               vmax=None, alpha=None, linewidths=None, edgecolors="face",
               reduce_C_function=None, mincnt=None, marginals=False, **kwargs):
        """Hexagonal binning: one coloured hexagon per occupied grid cell."""
        x = np.asarray(x, dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        if x.size == 0:
            raise ValueError("hexbin needs at least one point")
        gridsize = _validate_bins(gridsize, name="gridsize")
        if isinstance(gridsize, (tuple, list, np.ndarray)):
            nx, ny = (max(int(v), 1) for v in np.asarray(gridsize).ravel()[:2])
        else:
            nx = max(int(gridsize), 1)
            ny = None
        if extent is None:
            extent = (float(x.min()), float(x.max()), float(y.min()), float(y.max()))
        ex0, ex1, ey0, ey1 = (float(v) for v in extent)
        if ex1 <= ex0:
            ex0, ex1 = ex0 - 0.5, ex1 + 0.5
        if ey1 <= ey0:
            ey0, ey1 = ey0 - 0.5, ey1 + 0.5
        if ny is None:
            ny = max(int(nx / np.sqrt(3.0)), 1)
        ny = max(int(ny), 1)
        if nx * ny > _MAX_BIN_CELLS // 2:
            raise ValueError(
                f"gridsize=({nx}, {ny}) creates too many hexagons "
                f"({nx * ny} > {_MAX_BIN_CELLS // 2})"
            )
        sx = (ex1 - ex0) / nx
        sy = (ey1 - ey0) / ny
        nx1, ny1 = nx + 1, ny + 1
        nx2, ny2 = nx, ny
        # Two interleaved rectangular grids form a triangular lattice. The
        # nearest of their centres gives the hexagonal Voronoi cell for a point.
        centers = np.column_stack([
            np.concatenate([
                np.repeat(np.arange(nx1), ny1),
                np.repeat(np.arange(nx2) + 0.5, ny2),
            ]) * sx + ex0,
            np.concatenate([
                np.tile(np.arange(ny1), nx1),
                np.tile(np.arange(ny2), nx2) + 0.5,
            ]) * sy + ey0,
        ])
        ix = (x - ex0) / sx
        iy = (y - ey0) / sy
        ix1 = np.rint(ix).astype(int)
        iy1 = np.rint(iy).astype(int)
        ix2 = np.floor(ix).astype(int)
        iy2 = np.floor(iy).astype(int)
        valid1 = (0 <= ix1) & (ix1 < nx1) & (0 <= iy1) & (iy1 < ny1)
        valid2 = (0 <= ix2) & (ix2 < nx2) & (0 <= iy2) & (iy2 < ny2)
        d1 = (ix - ix1) ** 2 + 3.0 * (iy - iy1) ** 2
        d2 = (ix - ix2 - 0.5) ** 2 + 3.0 * (iy - iy2 - 0.5) ** 2
        use1 = valid1 & (~valid2 | (d1 <= d2))
        valid = valid1 | valid2
        cell = np.where(use1, ix1 * ny1 + iy1, nx1 * ny1 + ix2 * ny2 + iy2)
        cell = cell[valid]
        total = nx1 * ny1 + nx2 * ny2
        counts = np.bincount(cell, minlength=total).astype(np.float64)
        if C is None:
            values = counts.copy()
        else:
            weights = np.asarray(C, dtype=np.float64).ravel()
            if weights.size != x.size:
                raise ValueError("C must have one value per point")
            sums = np.bincount(cell, weights=weights[valid], minlength=total)
            values = np.divide(sums, counts, out=np.zeros(total), where=counts > 0)
        if mincnt is None:
            keep = np.ones(total, dtype=bool)
        else:
            keep = counts >= float(mincnt)
        if not keep.any():
            keep = counts > 0
        shown = np.flatnonzero(keep)
        if vmin is None:
            vmin = float(values[shown].min())
        if vmax is None:
            vmax = float(values[shown].max())
        if not vmax > vmin:
            vmax = vmin + 1.0
        t = np.clip((values[shown] - float(vmin)) / (float(vmax) - float(vmin)), 0.0, 1.0)
        cmap = _cmap_name(cmap)
        colors = _cmap_colors(cmap, t)
        polygon = np.array([
            [0.5, -0.5], [0.5, 0.5], [0.0, 1.0],
            [-0.5, 0.5], [-0.5, -0.5], [0.0, -1.0],
        ])
        # Build every hexagon in one array and keep the cells in a single band:
        # one dict per cell dominates hexbin's Python time and cache-key hashing.
        sel = centers[shown]
        xs = (sel[:, 0:1] + sx * polygon[:, 0]).ravel()
        ys = (sel[:, 1:2] + (sy / 3.0) * polygon[:, 1]).ravel()
        self.bands.append(dict(
            x=np.ascontiguousarray(xs), y=np.ascontiguousarray(ys),
            color="#000000", alpha=None if alpha is None else float(alpha), label="",
            cells=int(shown.size),
            cell_colors="".join(c[1:] for c in colors),
        ))
        self._sticky_x += [ex0, ex1]
        self._sticky_y += [ey0, ey1]
        return _HexbinHandle(values[shown], centers[shown], colors, cmap)

    def annotate(self, text, xy, xytext=None, arrowprops=None, color=None, fontsize=None,
                 **kwargs):
        """Text at `xytext` with an arrow pointing at `xy`.

        `xycoords`/`textcoords`, alignment and box keywords are accepted; the
        renderer currently treats both coordinate systems as data coordinates.
        """
        size = _font_size(fontsize, rcParams.get("font.size", 10.0))
        color = color or kwargs.get("color") or rcParams.get("text.color", "black")
        xytext = kwargs.get("xytext", xytext)
        self.annotations.append((_mathtext(text), (float(xy[0]), float(xy[1])),
                                 None if xytext is None else (float(xytext[0]), float(xytext[1])),
                                 _norm_color(color), size))

    def scatter(self, x, y, s=None, c=None, alpha=None, cmap=None, label="", marker="o",
                vmin=None, vmax=None, data=None, **kwargs):
        """Scatter markers; `s` is an area in points^2 and `c` a colour, a list of
        colours, or numeric values mapped through `cmap`. `data=` may supply columns."""
        if data is not None:
            x = data[x] if isinstance(x, str) else x
            y = data[y] if isinstance(y, str) else y
        if not label and getattr(y, "name", None) is not None:
            label = str(y.name)
        x = np.asarray(self._xdate(x), dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        n = y.size
        values, colors = _scatter_colors(c if c is not None else self._next_color(), n)
        self.scatter_pts.append(dict(
            x=np.ascontiguousarray(x), y=np.ascontiguousarray(y), sizes=_sizes(s, n),
            values=values, cmap=_cmap_name(cmap),
            clim=None if vmin is None and vmax is None else (vmin, vmax), colors=colors,
            marker=str(marker), alpha=1.0 if alpha is None else float(alpha),
            label=str(label)))

    def quiver(self, *args, U=None, V=None, C=None, color=None, angles="xy",
               scale=None, scale_units=None, units="width", width=None,
               headwidth=3.0, headlength=5.0, headaxislength=4.5, pivot="tail",
               **kwargs):
        """Vector field arrows from `quiver(U, V)` or `quiver(X, Y, U, V)`.

        `scale` divides the vector components; `pivot` places the arrow at its
        tail, middle or tip."""
        if len(args) == 2:
            ua = np.asarray(args[0], dtype=np.float64)
            va = np.asarray(args[1], dtype=np.float64)
            if ua.shape != va.shape:
                raise ValueError("U and V must have the same shape")
            if ua.ndim == 2:
                rows, cols = ua.shape
                gx, gy = np.meshgrid(np.arange(cols, dtype=float),
                                     np.arange(rows, dtype=float))
                x, y = gx.ravel(), gy.ravel()
            else:
                x = np.arange(ua.size, dtype=float)
                y = np.zeros(ua.size)
            u, v = ua.ravel(), va.ravel()
        elif len(args) >= 4:
            xa = np.asarray(self._xdate(args[0]), dtype=np.float64)
            ya = np.asarray(args[1], dtype=np.float64)
            ua = np.asarray(args[2], dtype=np.float64)
            va = np.asarray(args[3], dtype=np.float64)
            if ua.shape != va.shape:
                raise ValueError("U and V must have the same shape")
            if ua.ndim == 2:
                if (xa.ndim == 1 and ya.ndim == 1
                        and xa.size == ua.shape[1] and ya.size == ua.shape[0]):
                    xa, ya = np.meshgrid(xa, ya)
                elif xa.shape != ua.shape or ya.shape != va.shape:
                    raise ValueError("X and Y must match U's shape or one axis each")
                x, y = xa.ravel(), ya.ravel()
            else:
                x, y = xa.ravel(), ya.ravel()
            u, v = ua.ravel(), va.ravel()
            if len(args) >= 5 and C is None:
                C = args[4]
        elif len(args) == 0 and U is not None and V is not None:
            ua = np.asarray(U, dtype=np.float64)
            va = np.asarray(V, dtype=np.float64)
            if ua.shape != va.shape:
                raise ValueError("U and V must have the same shape")
            if ua.ndim == 2:
                rows, cols = ua.shape
                x, y = np.meshgrid(np.arange(cols, dtype=float),
                                   np.arange(rows, dtype=float))
                x, y = x.ravel(), y.ravel()
            else:
                x = np.arange(ua.size, dtype=float)
                y = np.zeros(ua.size)
            u, v = ua.ravel(), va.ravel()
        else:
            raise TypeError("quiver expects U, V or X, Y, U, V")
        if not (x.size == y.size == u.size == v.size):
            raise ValueError("X, Y, U and V must have the same length")
        if x.size == 0:
            raise ValueError("quiver needs at least one vector")
        if angles not in ("xy", "uv"):
            raise ValueError(f"unsupported angles: {angles!r}")
        if pivot not in ("tail", "middle", "mid", "tip"):
            raise ValueError(f"unsupported pivot: {pivot!r}")
        if scale is not None and not isinstance(scale, str):
            if float(scale) == 0.0:
                raise ValueError("scale must not be zero")
            u, v = u / float(scale), v / float(scale)
        if pivot in ("tip",):
            x, y = x - u, y - v
        elif pivot in ("middle", "mid"):
            x, y = x - u / 2.0, y - v / 2.0
        colors = (_line_colors(color, x.size) if color is not None
                  else [self._next_color()])
        linewidth = _number(kwargs.get("linewidth", kwargs.get("lw")), 1.5)
        entry = dict(x=np.ascontiguousarray(x), y=np.ascontiguousarray(y),
                     u=np.ascontiguousarray(u), v=np.ascontiguousarray(v),
                     colors=colors, linewidth=linewidth,
                     headwidth=_number(headwidth, 3.0),
                     headlength=_number(headlength, 5.0))
        self.arrows.append(entry)
        return _QuiverHandle(entry)

    def quiverkey(self, Q, X, Y, U, label, **kwargs):
        """Accept the quiver-key annotation; keys are not drawn yet."""
        return None

    def errorbar(self, x, y, yerr=None, xerr=None, fmt="", ecolor=None, elinewidth=None,
                 capsize=None, label="", color=None, **kwargs):
        """Plot `y` against `x` with vertical (`yerr`) and/or horizontal (`xerr`)
        error bars; each error may be a scalar, a length-N array, or (2, N) lo/hi."""
        x = np.asarray(self._xdate(x), dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        n = y.size
        ylo, yhi = _err_pair(yerr, n, "yerr")
        xlo, xhi = _err_pair(xerr, n, "xerr")
        c = (color or ecolor or _FMT_COLORS.get(fmt[:1])
             or self._next_color())
        # matplotlib's default fmt='' still draws a solid line; marker-only formats
        # ('o', 's', ...) get bars only since markers are not rendered yet.
        elw = elinewidth if elinewidth is not None else rcParams.get("lines.linewidth", 1.5)
        if fmt != "none" and (fmt == "" or "-" in fmt):
            self.lines.append(_series(x, y, label, c, linewidth=elw))
        self.errors.append((np.ascontiguousarray(x), np.ascontiguousarray(y), ylo, yhi,
                            xlo, xhi, c, float(capsize or 0.0) * 1.4))
        _, _, marker = _stem_fmt(fmt, "")
        if marker:
            self.scatter(x, y, s=36, c=c, marker=marker)

    def contour(self, *args, levels=None, colors=None, cmap=None, linewidths=None,
                alpha=None, **kwargs):
        """Iso-lines of a 2-D array: `contour(Z)` or `contour(X, Y, Z)`, optionally
        followed by `levels`. Matplotlib contour kwargs are accepted."""
        return self._add_contour(args, levels, colors, cmap, False, linewidths, alpha)

    def contourf(self, *args, levels=None, colors=None, cmap=None, linewidths=None,
                 alpha=None, **kwargs):
        """Filled iso-bands of a 2-D array; takes the same forms as `contour`."""
        return self._add_contour(args, levels, colors, cmap, True, linewidths, alpha)

    def _add_contour(self, args, levels, colors, cmap, filled, linewidths=None, alpha=None):
        x, y, z, levels = _contour_args(args, levels)
        levels = _levels(z, levels)
        if linewidths is None:
            widths = []
        elif np.isscalar(linewidths):
            widths = [float(linewidths)]
        else:
            widths = [float(v) for v in np.asarray(linewidths, dtype=np.float64).ravel()]
        if widths and len(widths) not in (1, len(levels)):
            raise ValueError("linewidths must be a scalar or match the number of levels")
        opacity = 1.0 if alpha is None else float(alpha)
        if not np.isfinite(opacity):
            raise ValueError("alpha must be finite")
        entry = dict(x=x, y=y, z=z, levels=levels, linewidths=widths,
                     colors=_colors(colors), cmap=_cmap_name(cmap), filled=filled,
                     alpha=float(np.clip(opacity, 0.0, 1.0)))
        self.contours.append(entry)
        return ContourSet(entry)

    def set_title(self, t, fontsize=None, **kwargs):
        self.title = _mathtext(t)
        self.title_size = self._size_or(fontsize, "axes.titlesize")

    def set_xlabel(self, t, fontsize=None, **kwargs):
        self.xlabel = _mathtext(t)
        self.xlabel_size = self._size_or(fontsize, "axes.labelsize")

    def set_ylabel(self, t, fontsize=None, **kwargs):
        self.ylabel = _mathtext(t)
        self.ylabel_size = self._size_or(fontsize, "axes.labelsize")

    @staticmethod
    @staticmethod
    def _size_or(value, key):
        return _font_size(value, rcParams.get(key, rcParams.get("font.size", 10.0)))

    def set_xlim(self, left=None, right=None, **kwargs):
        """Set the x limits; accepts `left`/`right` or Matplotlib's `xmin`/`xmax`."""
        left = kwargs.pop("xmin", left)
        right = kwargs.pop("xmax", right)
        current = self.get_xlim()
        left = current[0] if left is None else left
        right = current[1] if right is None else right
        values = self._xdate((left, right))
        limits = self.xlim = (float(values[0]), float(values[1]))
        if self._share_x is not None:
            self._share_x.limits = limits
        return limits

    def set_ylim(self, bottom=None, top=None, **kwargs):
        """Set the y limits; accepts `bottom`/`top` or `ymin`/`ymax`."""
        bottom = kwargs.pop("ymin", bottom)
        top = kwargs.pop("ymax", top)
        current = self.get_ylim()
        bottom = current[0] if bottom is None else bottom
        top = current[1] if top is None else top
        limits = self.ylim = (float(bottom), float(top))
        if self._share_y is not None:
            self._share_y.limits = limits
        return limits

    def legend(self, *args, loc=None, ncol=None, ncols=None, frameon=None, fontsize=None,
               title=None, title_fontsize=None, bbox_to_anchor=None, handles=None,
               labels=None, **kwargs):
        """Show a legend. Supports placement, layout and explicit handles/labels."""
        if len(args) == 1:
            arg = args[0]
            if isinstance(arg, (list, tuple)) and arg and isinstance(arg[0], str):
                _labels = arg
            elif isinstance(arg, str):
                loc = arg
            else:
                _handles = arg
        elif len(args) >= 2:
            _handles, _labels = args[0], args[1]
            if len(args) > 2 and isinstance(args[2], str):
                loc = args[2]
        self.show_legend = True
        if isinstance(loc, (tuple, list)):
            self.legend_anchor = (float(loc[0]), float(loc[1]))
            self.legend_loc = "lower left"
        elif loc is not None:
            self.legend_loc = str(loc)
        cols = ncol if ncol is not None else ncols
        if cols is not None:
            self.legend_ncol = max(1, int(cols))
        if frameon is not None:
            self.legend_frameon = bool(frameon)
        if fontsize is not None:
            self.legend_fontsize = _font_size(fontsize, rcParams.get("legend.fontsize", 10.0))
        if title is not None:
            self.legend_title = _mathtext(title)
        if title_fontsize is not None:
            self.legend_title_fontsize = _font_size(title_fontsize, 11.0)
        elif title is not None and self.legend_title_fontsize is None:
            self.legend_title_fontsize = _font_size(rcParams.get("legend.fontsize", 10.0)) * 1.1
        if bbox_to_anchor is not None:
            anchor = [float(v) for v in np.asarray(bbox_to_anchor).ravel()]
            if len(anchor) not in (2, 4):
                raise ValueError("bbox_to_anchor needs 2 or 4 values")
            self.legend_anchor = (anchor[0], anchor[1])
        return None

    def minorticks_on(self): self.minor_ticks = True
    def minorticks_off(self): self.minor_ticks = False

    def eventplot(self, positions, orientation="horizontal", lineoffsets=0.0, linelengths=1.0,
                  colors=None, linestyles=None, linewidths=None, **kwargs):
        """One short line per event position, one row per positions array."""
        rows = positions
        if not isinstance(rows, (list, tuple)) or (len(rows) and np.isscalar(rows[0])):
            rows = [rows]
        rows = [np.asarray(r, dtype=np.float64).ravel() for r in rows]
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
        for i, row in enumerate(rows):
            half = float(lengths[i]) / 2.0
            if orientation == "horizontal":
                self.vlines(row, offsets[i] - half, offsets[i] + half,
                            colors=cols[i], linestyles=styles[i], linewidths=linewidths)
            elif orientation == "vertical":
                self.hlines(row, offsets[i] - half, offsets[i] + half,
                            colors=cols[i], linestyles=styles[i], linewidths=linewidths)
            else:
                raise ValueError(f"unsupported orientation: {orientation!r}")
        return None

    def broken_barh(self, xranges, yrange, colors=None, edgecolor=None, alpha=None,
                    linewidth=None, **kwargs):
        """Horizontal bars from `(xstart, width)` pairs over a shared y range."""
        colors = kwargs.get("facecolors", colors)
        pairs = [(float(a), float(b)) for a, b in xranges]
        if not pairs:
            return None
        n = len(pairs)
        self.bars.append(dict(left=np.array([a for a, _ in pairs]),
                              bottom=np.full(n, float(yrange[0])),
                              width=np.array([b for _, b in pairs]),
                              height=np.full(n, float(yrange[1])),
                              colors=_bar_colors(colors, n),
                              edgecolor=_norm_color(edgecolor),
                              alpha=None if alpha is None else float(alpha),
                              label="", vertical=True))
        return None

    def grid(self, visible=None, which="major", axis="both", **kwargs):
        """Toggle gridlines and style them (`color`, `linewidth`, `alpha`,
        `linestyle`, `axis`). `visible=None` flips the current state."""
        if axis not in ("both", "x", "y"):
            raise ValueError(f"unsupported grid axis: {axis!r}")
        self.show_grid = (not self.show_grid) if visible is None else bool(visible)
        self.grid_axis = axis
        if "color" in kwargs or "c" in kwargs:
            self.grid_color = _norm_color(kwargs.get("color", kwargs.get("c")))
        if "linewidth" in kwargs or "lw" in kwargs:
            self.grid_linewidth = float(kwargs.get("linewidth", kwargs.get("lw")))
        if "linestyle" in kwargs or "ls" in kwargs:
            self.grid_linestyle = str(kwargs.get("linestyle", kwargs.get("ls")))
        if "alpha" in kwargs:
            self.grid_alpha = float(kwargs["alpha"])
        return None

    def tick_params(self, axis="both", **kwargs):
        """Style ticks on `axis` ("x", "y" or "both"); stored for the renderer."""
        if axis not in ("x", "y", "both"):
            raise ValueError(f"unsupported tick axis: {axis!r}")
        self.tick_params_box.update(kwargs)
        axes = ("x", "y") if axis == "both" else (axis,)
        for name in axes:
            self._tick_style(name, **{
                "rotation": kwargs.get("rotation"),
                "labelsize": kwargs.get("labelsize"),
                "labelcolor": kwargs.get("labelcolor", kwargs.get("color")),
                "tickcolor": kwargs.get("color"),
                "length": kwargs.get("length"),
                "width": kwargs.get("width"),
                "pad": kwargs.get("pad"),
            })
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
        ys = np.asarray(y, dtype=np.float64).ravel()
        lo, hi = _fill(self._xdate(xmin), ys.size), _fill(self._xdate(xmax), ys.size)
        cols, styles = _line_colors(colors, ys.size), _line_styles(linestyles, ys.size)
        widths = _fill(linewidths, ys.size) if linewidths is not None else None
        for i in range(ys.size):
            self.lines.append(_series(
                [lo[i], hi[i]], [ys[i], ys[i]], label, cols[i], linestyle=styles[i],
                linewidth=2.0 if widths is None else float(widths[i])))

    def vlines(self, x, ymin, ymax, colors=None, linestyles=None, linewidths=None,
               label="", **kwargs):
        """Vertical segments from `ymin` to `ymax` at every `x`."""
        xs = np.asarray(self._xdate(x), dtype=np.float64).ravel()
        lo, hi = _fill(ymin, xs.size), _fill(ymax, xs.size)
        cols, styles = _line_colors(colors, xs.size), _line_styles(linestyles, xs.size)
        widths = _fill(linewidths, xs.size) if linewidths is not None else None
        for i in range(xs.size):
            self.lines.append(_series(
                [xs[i], xs[i]], [lo[i], hi[i]], label, cols[i], linestyle=styles[i],
                linewidth=2.0 if widths is None else float(widths[i])))

    def stem(self, *args, linefmt=None, markerfmt=None, basefmt=None, bottom=0.0, label="",
             orientation="vertical", **kwargs):
        """Stem plot: one segment per point plus a marker at the tip."""
        if len(args) == 1:
            y = np.asarray(args[0], dtype=np.float64).ravel()
            x = np.arange(y.size, dtype=np.float64)
        elif len(args) == 2:
            x = np.asarray(self._xdate(args[0]), dtype=np.float64).ravel()
            y = np.asarray(args[1], dtype=np.float64).ravel()
        else:
            raise TypeError("stem expects y or x, y")
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        if orientation not in ("vertical", "horizontal"):
            raise ValueError(f"unsupported orientation: {orientation!r}")
        colour, style, _ = _stem_fmt(linefmt)
        colour = kwargs.get("color") or colour or _CYCLE[len(self.lines) % len(_CYCLE)]
        if x.size:
            if orientation == "vertical":
                self.vlines(x, bottom, y, colors=colour, linestyles=style,
                            linewidths=rcParams.get("lines.linewidth", 1.5))
            else:
                self.hlines(y, bottom, x, colors=colour, linestyles=style,
                            linewidths=rcParams.get("lines.linewidth", 1.5))
            marker_colour, _, marker = _stem_fmt(markerfmt, "o")
            self.scatter(x, y, s=36, c=marker_colour or colour,
                         marker=marker,
                         markersize=rcParams.get("lines.markersize", 6.0))
            if basefmt != "none":
                if orientation == "vertical":
                    self.hlines([float(bottom)], float(x.min()), float(x.max()),
                                colors=colour,
                                linewidths=rcParams.get("lines.linewidth", 1.5))
                else:
                    self.vlines([float(bottom)], float(y.min()), float(y.max()),
                                colors=colour,
                                linewidths=rcParams.get("lines.linewidth", 1.5))

    def pie(self, x, labels=None, colors=None, autopct=None, explode=None, startangle=0,
            normalize=True, shadow=False, **kwargs):
        """Pie chart drawn as filled wedges; returns `(wedges, texts, autotexts)`."""
        values = np.asarray(x, dtype=np.float64).ravel()
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
            self.bands.append(_band(np.concatenate([[ex], ex + np.cos(arc)]),
                                    np.concatenate([[ey], ey + np.sin(arc)]),
                                    cols[i % len(cols)], None))
            wedges.append(_Wedge(cols[i % len(cols)]))
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
        return wedges, texts, autotexts

    def stackplot(self, x, *ys, labels=(), colors=None, alpha=None, baseline="zero",
                  **kwargs):
        """Stacked areas: each layer fills between the running total and itself."""
        if baseline not in ("zero", "sym"):
            raise NotImplementedError(f"baseline={baseline!r} is not supported yet")
        x = np.asarray(x, dtype=np.float64).ravel()
        layers = []
        for y in ys:
            a = np.asarray(y, dtype=np.float64)
            if a.ndim == 2 and a.shape[0] == x.size:
                layers.extend(a[:, i] for i in range(a.shape[1]))
            else:
                layers.append(a.ravel())
        if not layers:
            raise ValueError("stackplot needs at least one y array")
        cols = _colors(colors)
        if baseline == "sym":
            cum = -np.sum(np.stack(layers), axis=0) / 2.0
        else:
            cum = np.zeros(x.size)
        for i, layer in enumerate(layers):
            if layer.size != x.size:
                raise ValueError("x and y must have the same length")
            colour = cols[i % len(cols)] if cols else _CYCLE[i % len(_CYCLE)]
            lab = str(labels[i]) if i < len(labels) else ""
            self.fill_between(x, cum, cum + layer, color=colour, alpha=alpha, label=lab)
            cum = cum + layer

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
        if not fill:
            return self.plot(xs, ys, color=color, label=label, **kwargs)
        # A filled `stairs` is one StepPatch: `color` fills it, `alpha` applies to
        # the whole patch, and no edge is drawn unless one is asked for.
        alpha = kwargs.pop("alpha", None)
        edge = kwargs.pop("edgecolor", kwargs.pop("ec", None))
        linewidth = kwargs.pop("linewidth", kwargs.pop("lw", None))
        face = kwargs.pop("facecolor", kwargs.pop("fc", None)) or color
        self.fill_between(xs, ys, baseline, color=face, alpha=alpha, label=label)
        if edge is not None:
            self.plot(xs, ys, color=edge, alpha=alpha, label="",
                      linewidth=linewidth if linewidth is not None else 1.0)
        return None

    # Layout requests are accepted but ignored: every panel is drawn at its fixed
    # gridspec cell, so there is nothing to negotiate.
    def tight_layout(self, **kwargs): return None
    def subplots_adjust(self, **kwargs): return None
    def set_layout_engine(self, engine=None, **kwargs): self.layout_engine = engine
    def get_layout_engine(self): return getattr(self, "layout_engine", None)
    def set_in_layout(self, b): self.in_layout = bool(b)
    def get_in_layout(self): return getattr(self, "in_layout", True)

    def _panel(self, dpi=None):
        (x0, x1), (y0, y1) = self._limits()
        dx, dy = x1 - x0, y1 - y0
        # Reference lines and bands are axes-fraction based, so they are resolved
        # here, once the drawing limits are known.
        series = list(self.lines)
        for h in self._hline_refs:
            series.append(_series([x0 + h["xmin"] * dx, x0 + h["xmax"] * dx],
                                  [h["y"], h["y"]], h["label"], h["color"] or "black",
                                  linestyle=h["linestyle"] or "-",
                                  linewidth=h["linewidth"] if h["linewidth"] is not None else rcParams.get("lines.linewidth", 1.5),
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
                                  linewidth=v["linewidth"] if v["linewidth"] is not None else rcParams.get("lines.linewidth", 1.5),
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
        series = [dict(s, color=_norm_color(s["color"]), mfc=_norm_color(s["mfc"]),
                       mec=_norm_color(s["mec"])) for s in series]
        bars = [dict(b, colors=[_norm_color(c) for c in b["colors"]],
                     edgecolor=_norm_color(b["edgecolor"])) for b in bars]
        bands = [dict(b, color=_norm_color(b["color"])) for b in self.bands]
        patches = [p for p in (_patch_entry(a) for a in self.artists) if p is not None]
        collections = [c for c in (_collection_entry(a) for a in self.artists) if c is not None]
        texts = [self._resolve_text(t, x0, x1, y0, y1) for t in self.texts]
        scatter = [dict(e, colors=[_norm_color(c) for c in e["colors"]])
                   for e in self.scatter_pts]
        arrows = [dict(e, colors=[_norm_color(c) for c in e["colors"]])
                  for e in self.arrows]
        contours = [(c["x"], c["y"], c["z"], c["levels"], c["linewidths"],
                     [_norm_color(v) for v in c["colors"]], c["cmap"], c["filled"],
                     c["alpha"])
                    for c in self.contours]
        font = float(rcParams.get("font.size", 10.0))
        legend_font = (float(self.legend_fontsize) if self.legend_fontsize is not None
                       else float(rcParams.get("legend.fontsize", font)))
        legend_title = (float(self.legend_title_fontsize)
                        if self.legend_title_fontsize is not None else legend_font * 1.1)
        xticks, xticklabels = self._xticks, self._xticklabels
        if self._x_date and self.xscale == "linear":
            if xticks is None:
                lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
                xticks, xticklabels = _date_ticks(lo, hi)
                if x0 > x1:
                    xticks, xticklabels = list(reversed(xticks)), list(reversed(xticklabels))
            elif xticklabels is None:
                xticklabels = [_date_label(float(v)) for v in xticks]
        elif self._categories and xticks is None:
            xticks = [float(i) for i in range(len(self._categories))]
            xticklabels = list(self._categories)
        return dict(pos=self.pos, series=series, texts=texts, title=self.title,
                    dpi=float(self._fig.dpi if self._fig is not None else DPI),
                    xlabel=self.xlabel, ylabel=self.ylabel,
                    title_size=self.title_size, xlabel_size=self.xlabel_size,
                    ylabel_size=self.ylabel_size,
                    legend=dict(show=self.show_legend, loc=self.legend_loc,
                                ncol=self.legend_ncol, frameon=self.legend_frameon,
                                fontsize=legend_font, title=self.legend_title,
                                title_fontsize=legend_title, anchor=self.legend_anchor),
                    xlim=(x0, x1), ylim=(y0, y1), annotations=self.annotations,
                    aspect=self.aspect,
                    contours=contours,
                    errors=self.errors,
                    bars=bars,
                    bands=bands,
                    x_log=self.xscale == "log", y_log=self.yscale == "log",
                    log_base=float(getattr(self, "log_base", 10.0)),
                    grid=dict(show=self.show_grid, color=self.grid_color,
                              linewidth=self.grid_linewidth, alpha=self.grid_alpha,
                              linestyle=self.grid_linestyle, axis=self.grid_axis),
                    ticks=dict(xticks=xticks, xticklabels=xticklabels,
                               yticks=self._yticks, yticklabels=self._yticklabels,
                               xstyle=self._tick_style_dict("x"),
                               ystyle=self._tick_style_dict("y"),
                               hide_xlabels=self.hide_xticklabels or self._twin == "y",
                               hide_ylabels=self.hide_yticklabels or self._twin == "x"),
                    scatter=[dict(x=e["x"], y=e["y"], sizes=e["sizes"], values=e["values"],
                                  cmap=e["cmap"], clim=e["clim"], colors=e["colors"],
                                  marker=e["marker"], alpha=e["alpha"], label=e["label"])
                             for e in scatter],
                    arrows=arrows,
                    colorbar=(
                        (self._colorbar["cmap"], self._colorbar["vmin"],
                         self._colorbar["vmax"], self._colorbar["label"])
                        if self._colorbar is not None else None
                    ),
                    axis_off=self._axis_off,
                    facecolor=_norm_color(self.facecolor or rcParams.get("axes.facecolor")),
                    foreground=_norm_color(rcParams.get("text.color")),
                    bounds=self._render_bounds(dpi), twin=self._twin, twin_gap=self._twin_gap,
                    patches=patches, collections=collections,
                    images=[(e["data"], e["cmap"], e["vmin"], e["vmax"], e["extent"], True,
                             e["alpha"], e["interpolation"])
                            for e in self.images])

    def _resolve_text(self, t, x0, x1, y0, y1):
        """Turn axes/figure coordinates into the data coordinates the renderer uses."""
        x, y, s, c, size, ha, va, kind = t
        if kind == "axes":
            x, y = x0 + x * (x1 - x0), y0 + y * (y1 - y0)
        elif kind == "figure":
            rows, cols = self._fig.grid if self._fig is not None else (1, 1)
            row, col = divmod(self.pos, cols)
            fx0, fy0 = col / cols, (rows - 1 - row) / rows
            x = x0 + (x - fx0) * cols * (x1 - x0)
            y = y0 + (y - fy0) * rows * (y1 - y0)
        return (x, y, s, c, size, ha, va)

    def _tick_style_dict(self, axis):
        style = self.tick_params_x if axis == "x" else self.tick_params_y
        font = float(rcParams.get("font.size", 10.0))
        return dict(labelsize=float(style.get("labelsize", font)),
                    length=float(style.get("length", 3.5)),
                    width=float(style.get("width", 1.0)),
                    color=_norm_color(style.get("labelcolor")),
                    labelcolor=_norm_color(style.get("labelcolor")),
                    rotation=float(style.get("rotation", 0.0)))


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
                label=str(label), color=_norm_color(color), linestyle=str(linestyle),
                linewidth=float(linewidth), marker=str(marker), markersize=float(markersize),
                mfc=_norm_color(mfc), mec=_norm_color(mec), mew=float(mew),
                alpha=None if alpha is None else float(alpha), drawstyle=str(drawstyle))


def _hash_value(hasher, value):
    """Feed a deterministic representation of nested panel data to `hasher`."""
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(value)
        hasher.update(b"array")
        hasher.update(array.dtype.str.encode())
        hasher.update(str(array.shape).encode())
        # Hash the existing buffer directly; tobytes() copied every array on
        # every savefig even when the figure had not changed.
        try:
            payload = memoryview(array).cast("B")
        except (TypeError, ValueError):
            hasher.update(array.tobytes())
        else:
            hasher.update(payload)
    elif isinstance(value, dict):
        hasher.update(b"dict")
        for key in sorted(value, key=repr):
            _hash_value(hasher, key)
            _hash_value(hasher, value[key])
    elif isinstance(value, (list, tuple)):
        hasher.update(b"seq")
        hasher.update(str(len(value)).encode())
        for item in value:
            _hash_value(hasher, item)
    elif isinstance(value, bytes):
        hasher.update(b"bytes")
        hasher.update(value)
    elif isinstance(value, str):
        hasher.update(b"str")
        hasher.update(value.encode())
    elif value is None:
        hasher.update(b"none")
    else:
        hasher.update(b"repr")
        hasher.update(repr(value).encode())


def _panel_cache_key(panel):
    """Stable fingerprint used by the renderer's per-panel fragment cache."""
    try:
        hasher = _hashlib.blake2b(digest_size=16)
        _hash_value(hasher, panel)
        return hasher.hexdigest()
    except (TypeError, ValueError):
        return ""


def _resolve_data_args(args, data, x, y):
    """Resolve `data=` columns for `plot(..., x=, y=)` and `plot("x", "y", data=)`."""
    def with_index(values):
        index = getattr(values, "index", None)
        return (index, values) if index is not None else (values,)

    if x is not None or y is not None:
        if y is None:
            raise TypeError("plot requires y when using data=")
        if data is None:
            return (y,) if x is None else (x, y)
        pick = lambda name: data[name] if isinstance(name, str) else name
        return with_index(pick(y)) if x is None else (pick(x), pick(y))
    if data is None:
        return args

    def pick(name):
        try:
            return data[name]
        except (KeyError, IndexError, TypeError):
            return name

    if len(args) == 1:
        return with_index(pick(args[0]))
    if len(args) == 2:
        return (pick(args[0]), pick(args[1]))
    return args


def _plot_args(args, fmt):
    """Split plot args into (x, y, fmt) groups, supporting multiple data sets.

    `plot(y)`, `plot(x, y)`, `plot(y, "r--")`, `plot(x, y, "r--")` and the
    repeated `plot(x1, y1, x2, y2, ...)` form Matplotlib accepts all map to
    groups; a trailing format string applies to the group before it.
    """
    groups: list[tuple] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if isinstance(arg, str):
            if groups and groups[-1][2] is None:
                groups[-1] = (groups[-1][0], groups[-1][1], arg)
            i += 1
            continue
        if i + 1 < len(args) and not isinstance(args[i + 1], str):
            groups.append((arg, args[i + 1], None))
            i += 2
        elif i + 1 < len(args):
            groups.append((None, arg, args[i + 1]))
            i += 2
        else:
            groups.append((None, arg, None))
            i += 1
    if not groups:
        raise TypeError("plot expects y, (x, y) or (x, y, fmt)")
    if len(groups) > 1 and groups[-1][0] is None:
        raise TypeError("third arg must be a format string")
    return groups


# Marker characters the renderer understands; keep in sync with
# `marker_shape` in src/draw.rs and `_STEM_MARKERS` below.
_MARKERS = set("os^v<>Dx+.*hHpPXd8|_1234")


def _parse_fmt(fmt):
    """Split a matplotlib fmt string into (colour, linestyle, marker)."""
    color_map = {"b": "blue", "g": "green", "r": "red", "c": "cyan",
                 "m": "magenta", "y": "yellow", "k": "black", "w": "white"}
    markers = _MARKERS
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


_STEM_MARKERS = "os^v<>Dx+.*hHpPXd8|_1234"


def _stem_fmt(fmt, default_marker=None):
    """Split a stem `linefmt`/`markerfmt` into (colour, style, marker)."""
    text = str(fmt or "")
    colour = _FMT_COLORS.get(text[:1]) if text[:1] in _FMT_COLORS else None
    rest = text[1:] if colour else text
    style = "-"
    for candidate in ("--", "-.", ":", "-"):
        if candidate in rest:
            style = candidate
            break
    marker = default_marker
    if rest and rest[-1] in _STEM_MARKERS:
        marker = rest[-1]
    return colour, style, marker


def _line_colors(colors, n):
    if colors is None:
        return [_CYCLE[0]] * n
    if isinstance(colors, str):
        return [_norm_color(colors)] * n
    if _is_rgb(colors):
        return [_norm_color(colors)] * n
    vals = [_norm_color(c) for c in np.asarray(colors, dtype=object).ravel()]
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


def _band(xs, ys, color, alpha, label=""):
    return dict(x=_as_f64(xs), y=_as_f64(ys), color=_norm_color(color),
                alpha=None if alpha is None else float(alpha), label=str(label),
                cells=0, cell_colors="")


def _mid_steps(x, y):
    """Expand a line into matplotlib's `steps-mid` vertex sequence."""
    x_arr = np.asarray(x, dtype=np.float64).ravel()
    y_arr = np.asarray(y, dtype=np.float64).ravel()
    if x_arr.size != y_arr.size:
        raise ValueError("x and y must have the same length")
    if x_arr.size < 2:
        return x_arr, y_arr
    x_mid = (x_arr[:-1] + x_arr[1:]) / 2.0
    y_mid = (y_arr[:-1] + y_arr[1:]) / 2.0
    x_out = np.repeat(x_mid, 2)
    y_out = np.repeat(y_mid, 2)
    x_out[1::2] = x_arr[1:]
    y_out[1::2] = y_arr[:-1]
    return x_out, y_out


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


def _box_datasets(x):
    """Split `boxplot`/`violinplot` input into one 1-D array per dataset."""
    if isinstance(x, np.ndarray):
        if x.ndim == 2:
            return [x[:, i].astype(np.float64) for i in range(x.shape[1])]
        return [np.asarray(x, dtype=np.float64).ravel()]
    if isinstance(x, (list, tuple)):
        if len(x) == 0:
            return []
        if np.asarray(x[0]).ndim == 0:
            return [np.asarray(x, dtype=np.float64).ravel()]
        return [np.asarray(v, dtype=np.float64).ravel() for v in x]
    return [np.asarray(x, dtype=np.float64).ravel()]


def _kde(values, points=100, bw_method=None):
    """Gaussian KDE on a regular grid, with Scott/Silverman or scalar bandwidth."""
    vals = np.asarray(values, dtype=np.float64).ravel()
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        raise ValueError("a KDE needs at least one finite value")
    n = vals.size
    std = float(vals.std(ddof=1)) if n > 1 else 0.0
    if bw_method is None or bw_method == "scott":
        factor = n ** (-1.0 / 5.0)
        bw = std * factor if std > 0.0 else 1.0
    elif bw_method == "silverman":
        factor = (n / 4.0) ** (-1.0 / 5.0)
        bw = std * factor if std > 0.0 else 1.0
    elif callable(bw_method):
        bw = float(bw_method(vals))
    else:
        bw = float(bw_method) * std if std > 0.0 else float(bw_method)
    if not np.isfinite(bw) or bw <= 0.0:
        bw = 1.0
    lo, hi = float(vals.min()), float(vals.max())
    if hi <= lo:
        lo, hi = lo - 1.0, hi + 1.0
    grid = np.linspace(lo - 3.0 * bw, hi + 3.0 * bw, max(int(points), 2))
    z = (grid[:, None] - vals[None, :]) / bw
    density = np.exp(-0.5 * z * z).sum(axis=1) / (n * bw * np.sqrt(2.0 * np.pi))
    return grid, density


def _cmap_colors(cmap, values):
    """Map normalised values through any registered colormap to hex colours."""
    _, table, reverse = _cmap_lookup(cmap)
    arr = np.asarray(values, dtype=np.float64).ravel()
    t = np.clip(np.where(np.isfinite(arr), arr, 0.0), 0.0, 1.0)
    n = table.shape[0]
    index = np.minimum((t * n).astype(int), n - 1)
    if reverse:
        index = n - 1 - index
    rgb = table[index]
    return [f"#{int(r):02x}{int(g):02x}{int(b):02x}" for r, g, b in rgb]


def _bar_colors(color, n):
    if color is None:
        return []
    if isinstance(color, str):
        return [_norm_color(color)]
    if _is_rgb(color):
        return [_norm_color(color)]
    vals = [_norm_color(v) for v in np.asarray(color, dtype=object).ravel()]
    if len(vals) not in (1, n):
        raise ValueError("color must be a single colour or one per bar")
    return vals


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
    if isinstance(c, str) or _is_rgb(c):
        return None, [_norm_color(c)]
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
    return None, [_norm_color(v) for v in seq]


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
    if isinstance(colors, str) or _is_rgb(colors):
        return [_norm_color(colors)]
    return [_norm_color(c) for c in colors]


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
    def set_cmap(self, cmap): self._e["cmap"] = _cmap_name(cmap)
    def set_clim(self, vmin=None, vmax=None): pass
    def set(self, **kwargs): return self
    def clabel(self, *args, **kwargs): return []
    def get_paths(self): return []
    def get_arrays(self): return ()

    def _colorbar_spec(self):
        lv = self._e["levels"]
        return dict(cmap=self._e["cmap"], vmin=lv[0], vmax=lv[-1])


class AxesImage:
    """Handle returned by `Axes.imshow`, for later tweaks."""

    def __init__(self, entry, axes=None):
        self._e = entry
        self.axes = axes

    def get_array(self): return self._e["data"]
    def set_data(self, X): self._e["data"] = _as_image(X)
    def get_cmap(self): return self._e["cmap"]
    def set_cmap(self, cmap): self._e["cmap"] = _cmap_name(cmap)
    def set_extent(self, extent): self._e["extent"] = tuple(float(v) for v in extent)
    def get_extent(self): return self._e["extent"]
    def set_interpolation(self, value): self._e["interpolation"] = str(value)
    def get_interpolation(self): return self._e["interpolation"]
    def set_alpha(self, value): self._e["alpha"] = float(value)
    def get_alpha(self): return self._e["alpha"]
    def set_rasterized(self, value): _ignored("AxesImage.set_rasterized")
    def set_agg_filter(self, value): _ignored("AxesImage.set_agg_filter")
    def set_path_effects(self, value): _ignored("AxesImage.set_path_effects")
    def set_url(self, value): _ignored("AxesImage.set_url")
    def set_gid(self, value): _ignored("AxesImage.set_gid")
    def set_zorder(self, value): _ignored("AxesImage.set_zorder")
    def set_clip_on(self, value): _ignored("AxesImage.set_clip_on")
    def set_clip_path(self, *args, **kwargs): _ignored("AxesImage.set_clip_path")
    def set_transform(self, value): _ignored("AxesImage.set_transform")
    def set_visible(self, value): _ignored("AxesImage.set_visible")
    def get_window_extent(self, renderer=None): return _Bbox(0, 0, 1, 1)

    def set_clim(self, vmin=None, vmax=None):
        self._e["vmin"], self._e["vmax"] = vmin, vmax

    def _colorbar_spec(self):
        data = self._e["data"]
        lo = self._e["vmin"] if self._e["vmin"] is not None else float(np.nanmin(data))
        hi = self._e["vmax"] if self._e["vmax"] is not None else float(np.nanmax(data))
        return dict(cmap=self._e["cmap"], vmin=lo, vmax=hi)


def _span_index(key, size):
    """Normalise an int or slice into an inclusive (start, stop) span."""
    if isinstance(key, slice):
        step = 1 if key.step is None else int(key.step)
        if step != 1:
            raise ValueError("GridSpec slices must have step 1")
        start = 0 if key.start is None else int(key.start)
        stop = size if key.stop is None else int(key.stop)
        if start < 0:
            start += size
        if stop < 0:
            stop += size
        if not 0 <= start < stop <= size:
            raise ValueError("GridSpec slice out of range")
        return start, stop - 1
    index = int(key)
    if index < 0:
        index += size
    if not 0 <= index < size:
        raise IndexError("GridSpec index out of range")
    return index, index


class SubplotSpec:
    """A rectangular region of a `GridSpec`, accepted by `Figure.add_subplot`."""

    def __init__(self, gridspec, rows, cols):
        self.gridspec = gridspec
        self.rows = rows
        self.cols = cols

    def get_position(self, figure=None):
        x, y, w, h = self.gridspec._bounds(self.rows, self.cols)
        return _Bbox(x, y, x + w, y + h)

    def subgridspec(self, nrows, ncols, **kwargs):
        """Nested grid confined to this region."""
        x, y, w, h = self.gridspec._bounds(self.rows, self.cols)
        return GridSpec(nrows, ncols, figure=self.gridspec.figure,
                        left=x, right=x + w, bottom=y, top=y + h, **kwargs)


class GridSpec:
    """Irregular row/column layout; index it to get a `SubplotSpec`."""

    def __init__(self, nrows, ncols, figure=None, left=0.0, right=1.0,
                 bottom=0.0, top=1.0, wspace=None, hspace=None,
                 width_ratios=None, height_ratios=None):
        if int(nrows) < 1 or int(ncols) < 1:
            raise ValueError("GridSpec needs at least one row and one column")
        self.nrows, self.ncols = int(nrows), int(ncols)
        self.figure = figure
        self.left, self.right = float(left), float(right)
        self.bottom, self.top = float(bottom), float(top)
        self.wspace = 0.2 if wspace is None else float(wspace)
        self.hspace = 0.2 if hspace is None else float(hspace)
        self.width_ratios = ([1.0] * self.ncols if width_ratios is None
                             else [float(v) for v in width_ratios])
        self.height_ratios = ([1.0] * self.nrows if height_ratios is None
                              else [float(v) for v in height_ratios])
        if len(self.width_ratios) != self.ncols:
            raise ValueError("width_ratios must have one value per column")
        if len(self.height_ratios) != self.nrows:
            raise ValueError("height_ratios must have one value per row")
        if any(not np.isfinite(v) or v <= 0.0 for v in self.width_ratios + self.height_ratios):
            raise ValueError("GridSpec ratios must be positive and finite")

    def __getitem__(self, key):
        rows, cols = key if isinstance(key, tuple) else (key, key)
        return SubplotSpec(self, _span_index(rows, self.nrows),
                           _span_index(cols, self.ncols))

    def get_geometry(self):
        return self.nrows, self.ncols

    def _bounds(self, rows, cols):
        r0, r1 = rows
        c0, c1 = cols
        width = self.right - self.left
        height = self.top - self.bottom
        cell_w = width / sum(self.width_ratios)
        cell_h = height / sum(self.height_ratios)
        x0 = self.left + sum(self.width_ratios[:c0]) * cell_w
        x1 = self.left + sum(self.width_ratios[:c1 + 1]) * cell_w
        y1 = self.top - sum(self.height_ratios[:r0]) * cell_h
        y0 = self.top - sum(self.height_ratios[:r1 + 1]) * cell_h
        if c0 > 0:
            x0 += self.wspace * (width / self.ncols) / 2.0
        if c1 < self.ncols - 1:
            x1 -= self.wspace * (width / self.ncols) / 2.0
        if r0 > 0:
            y1 -= self.hspace * (height / self.nrows) / 2.0
        if r1 < self.nrows - 1:
            y0 += self.hspace * (height / self.nrows) / 2.0
        return (x0, y0, max(x1 - x0, 0.01), max(y1 - y0, 0.01))


class _ColorbarAxes:
    def get_position(self, original=False): return _Bbox(0.0, 0.0, 1.0, 1.0)
    def get_window_extent(self, renderer=None): return _Bbox(0.0, 0.0, 1.0, 1.0)
    def set_visible(self, value): return None
    def set_axis_off(self): return None
    def set_ylabel(self, *args, **kwargs): return None
    def set_xlabel(self, *args, **kwargs): return None
    def set_title(self, *args, **kwargs): return None
    def tick_params(self, *args, **kwargs): return None
    def set_yticks(self, *args, **kwargs): return None
    def set_xticks(self, *args, **kwargs): return None
    def set_yticklabels(self, *args, **kwargs): return None
    def set_xticklabels(self, *args, **kwargs): return None


class Colorbar:
    """Handle returned by `Figure.colorbar`."""

    def __init__(self, entry):
        self._e = entry
        self.ax = _ColorbarAxes()

    def set_label(self, label): self._e["label"] = str(label)
    def get_label(self): return self._e["label"]
    def add_lines(self, *args, **kwargs): return None
    def minorticks_on(self): return None
    def minorticks_off(self): return None
    def set_ticks(self, *args, **kwargs): return None
    def set_ticklabels(self, *args, **kwargs): return None
    def set_clim(self, *args, **kwargs): return None
    def update_normal(self, *args, **kwargs): return None


class Figure:
    def __init__(self, figsize=(6.4, 4.8), dpi=None, facecolor=None, edgecolor=None):
        self.figsize = _validate_figsize(figsize)
        self.grid, self.axes, self._cur = (1, 1), [], None
        self._colorbar = None
        self.dpi = _validate_dimension(
            dpi if dpi is not None else rcParams.get("figure.dpi", DPI), "dpi"
        )
        self.facecolor = _norm_color(
            facecolor if facecolor is not None else rcParams.get("figure.facecolor"))
        self.edgecolor = _norm_color(edgecolor)
        self._suptitle = None
        self._figure_texts = []
        self._render_cache = None
        self.transFigure = _CoordTransform("figure")
        self.transSubfigure = self.transFigure
        self.canvas = _Canvas(self)
        self.subplotpars = _SubplotPars()
        self.patch = Rectangle((0, 0), 1, 1, transform=self.transFigure,
                               facecolor=self.get_facecolor())
        self._gridspec = None
        self._label = ""
        self.callbacks = _Callbacks()

    def suptitle(self, t, x=0.5, y=0.98, fontsize=None, **kwargs):
        """Draw a figure-level title above the panel grid."""
        size = _font_size(fontsize, rcParams.get("figure.titlesize", 14.0))
        self._suptitle = dict(text=_mathtext(t), size=size, x=float(x), y=float(y))
        return None

    def text(self, x, y, s, fontdict=None, **kwargs):
        """Figure-fraction text, drawn above every panel so nothing clips it."""
        _transform, fontsize, colour, ha, va = _text_props(fontdict, kwargs)
        if ha not in ("left", "center", "right"):
            raise ValueError(f"unsupported ha: {ha!r}")
        if va == "center_baseline":
            va = "center"
        if va not in ("baseline", "bottom", "center", "top"):
            raise ValueError(f"unsupported va: {va!r}")
        size = _font_size(fontsize, rcParams.get("font.size", 10.0))
        colour = colour if colour is not None else rcParams.get("text.color", "black")
        self._figure_texts.append((float(x), float(y), _mathtext(s),
                                   _norm_color(colour), size, ha, va))
        return None

    def add_subplot(self, nrows=1, ncols=1, index=1, **kwargs):
        """index is 1-based, row-major (matplotlib convention); a `SubplotSpec`
        may be passed instead to place the axes on an irregular grid."""
        if isinstance(nrows, SubplotSpec):
            return self._add_spec(nrows)
        if isinstance(nrows, int) and 111 <= nrows <= 999 and ncols == 1 and index == 1:
            # `subplot(121)` is shorthand for `subplot(1, 2, 1)`.
            nrows, ncols, index = divmod(nrows, 100)[0], *divmod(nrows % 100, 10)
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

    def _add_spec(self, spec):
        ax = Axes(len(self.axes))
        ax._fig = self
        ax._pos_override = spec.gridspec._bounds(spec.rows, spec.cols)
        ax._bounds_are_axes = False
        self.axes.append(ax)
        self._cur = ax
        return ax

    def add_gridspec(self, nrows=1, ncols=1, **kwargs):
        return GridSpec(nrows, ncols, figure=self, **kwargs)

    def subplot_mosaic(self, mosaic, empty_sentinel=".", **kwargs):
        """Create one axes per mosaic label from a string or list-of-lists grid."""
        rows = [list(row) for row in mosaic]
        if not rows or not rows[0]:
            raise ValueError("subplot_mosaic needs a non-empty mosaic")
        ncols = len(rows[0])
        if any(len(row) != ncols for row in rows):
            raise ValueError("all mosaic rows must have the same length")
        gs = self.add_gridspec(len(rows), ncols)
        cells = {}
        for r, row in enumerate(rows):
            for c, label in enumerate(row):
                if label == empty_sentinel:
                    continue
                cells.setdefault(label, []).append((r, c))
        out = {}
        for label, coords in sorted(cells.items(), key=lambda item: str(item[0])):
            r0, r1 = min(r for r, _ in coords), max(r for r, _ in coords)
            c0, c1 = min(c for _, c in coords), max(c for _, c in coords)
            expected = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
            if set(coords) != expected:
                raise ValueError(f"mosaic region for {label!r} is not rectangular")
            out[label] = self.add_subplot(SubplotSpec(gs, (r0, r1), (c0, c1)))
        return out

    def subplots(self, nrows=1, ncols=1, sharex=False, sharey=False, squeeze=True,
                 **kwargs):
        axs = [self.add_subplot(nrows, ncols, i + 1) for i in range(nrows * ncols)]
        _share_axes(axs, (nrows, ncols), sharex, sharey)
        if len(axs) == 1 and squeeze:
            return axs[0]
        out = np.array(axs, dtype=object).reshape(nrows, ncols)
        return out.squeeze() if squeeze else out

    def gca(self):
        return self._cur or self.add_subplot()

    def add_axes(self, rect=None, **kwargs):
        """Add an axes whose figure-fraction rectangle is the plotting area."""
        rows, cols = self.grid
        ax = self.add_subplot(rows, cols, len(self.axes) + 1)
        ax.set_position(rect if rect is not None else (0.0, 0.0, 1.0, 1.0))
        ax._bounds_are_axes = True
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
    def get_dpi(self): return self.dpi or DPI
    def get_facecolor(self): return self.facecolor or "white"
    def get_edgecolor(self): return self.edgecolor
    def get_size_inches(self): return self.figsize
    def get_label(self): return self._label
    def set_label(self, label): self._label = str(label); return self

    def set_facecolor(self, color):
        self.facecolor = _norm_color(color)
        if getattr(self, "patch", None) is not None:
            self.patch.set_facecolor(self.facecolor)
        return self

    def legend(self, *args, **kwargs): return None
    def figimage(self, *args, **kwargs): return None
    def add_subfigure(self, *args, **kwargs): return self
    def subfigures(self, nrows=1, ncols=1, squeeze=True, **kwargs):
        """Compatibility shim: each subfigure is this figure, sharing its canvas."""
        if nrows * ncols == 1:
            return self
        out = np.empty((nrows, ncols), dtype=object)
        out.fill(self)
        return out.squeeze() if squeeze else out
    def get_children(self): return list(self.axes)
    def get_tightbbox(self, renderer=None, *args, **kwargs): return None
    def set_tight_layout(self, value): return None
    def get_tight_layout(self): return False
    def set_constrained_layout(self, value): return None
    def get_constrained_layout(self): return False
    def set_constrained_layout_pads(self, **kwargs): return None

    def set_size_inches(self, width, height=None):
        if height is None:
            width, height = width
        self.figsize = _validate_figsize((width, height))

    def colorbar(self, mappable=None, ax=None, label="", **kwargs):
        """Reserve a strip beside `mappable`'s axes showing its scale."""
        if not self.axes:
            raise ValueError("colorbar needs at least one axes")
        if isinstance(ax, (list, tuple, np.ndarray)):
            raise NotImplementedError("colorbar needs a single axes")
        if ax is None:
            ax = kwargs.get("cax")
        if ax is None:
            axes = self._cur or self.axes[0]
            if mappable is not None:
                entry = getattr(mappable, "_e", None)
                owner = next((a for a in self.axes
                              if entry is not None
                              and (any(item is entry for item in a.images)
                                   or any(item is entry for item in a.contours))), None)
                axes = owner or axes
        else:
            axes = ax
        if mappable is not None:
            spec = mappable._colorbar_spec()
        elif axes.contours:
            spec = ContourSet(axes.contours[-1])._colorbar_spec()
        elif axes.images:
            spec = AxesImage(axes.images[-1])._colorbar_spec()
        else:
            raise ValueError("colorbar needs an image or contour to describe")
        entry = dict(cmap=str(spec["cmap"]), vmin=float(spec["vmin"]),
                     vmax=float(spec["vmax"]), label=str(label))
        axes._colorbar = entry
        self._colorbar = entry
        return Colorbar(entry)


    def savefig(self, filepath=None, format=None, dpi=None, bbox_inches=None,
                transparent=False, facecolor=None, edgecolor=None,
                compression=None):
        """Write this figure, or return its bytes when `filepath` is None or a
        file-like object. `format` overrides the extension, `dpi` scales the
        pixel size and `bbox_inches="tight"` crops to the drawn content.
        `compression` selects PNG compression: "fast" (default), "default",
        or "best"."""
        dpi = _validate_dimension(dpi if dpi is not None else (self.dpi or DPI), "dpi")
        if compression is not None:
            compression = str(compression).lower()
            if compression not in _COMPRESSIONS:
                raise ValueError(
                    f"unsupported compression: {compression!r} "
                    "(use 'fast', 'default', or 'best')"
                )
        if bbox_inches not in (None, "tight"):
            raise ValueError(f"unsupported bbox_inches: {bbox_inches!r} (use 'tight')")
        fmt = _output_format(filepath, format)
        rw, rh = (round(v * dpi) for v in self.figsize)
        if rw < 1 or rh < 1:
            raise ValueError(f"figure dimensions ({rw}x{rh}) must be at least 1x1 pixels")
        if rw > _MAX_CANVAS_DIM or rh > _MAX_CANVAS_DIM:
            raise ValueError(
                f"figure dimension ({rw}x{rh}) exceeds maximum allowed dimension of {_MAX_CANVAS_DIM}px"
            )
        if rw * rh > _MAX_CANVAS_AREA:
            raise ValueError(
                f"total figure pixel count ({rw * rh}) exceeds maximum allowed ({_MAX_CANVAS_AREA}px)"
            )
        w, h = rw, rh
        panels = [a._panel(dpi) for a in self.axes if a.visible and not a._removed]
        # savefig(dpi=) overrides the figure default, and text sizes scale with it.
        for panel in panels:
            panel["dpi"] = dpi
        if transparent:
            # A transparent save drops every patch, like matplotlib.
            for panel in panels:
                panel["facecolor"] = None
        for panel in panels:
            panel["cache_key"] = _panel_cache_key(panel)
        options = {
            "format": fmt,
            "transparent": bool(transparent),
            "tight": bbox_inches == "tight",
            "dpi": dpi,
            "facecolor": _norm_color(facecolor) or self.facecolor,
            "edgecolor": _norm_color(edgecolor) or self.edgecolor,
            "compression": compression,
            "suptitle": self._suptitle["text"] if self._suptitle else "",
            "suptitle_size": self._suptitle["size"] if self._suptitle else 14.0,
            "suptitle_x": self._suptitle["x"] if self._suptitle else 0.5,
            "suptitle_y": self._suptitle["y"] if self._suptitle else 0.98,
            "figure_texts": self._figure_texts,
        }
        # An unchanged figure reuses its last encoded bytes. The key covers both
        # the panel payload and every render option, so any edit invalidates it.
        panel_keys = [panel.get("cache_key", "") for panel in panels]
        try:
            if any(not panel_key for panel_key in panel_keys):
                raise TypeError("panel data is not hashable")
            hasher = _hashlib.blake2b(digest_size=16)
            _hash_value(hasher, ((w, h), self.grid, panel_keys, options))
            key = hasher.digest()
        except (TypeError, ValueError):
            key = None
        if key is not None and self._render_cache is not None and self._render_cache[0] == key:
            data = self._render_cache[1]
        else:
            data = _render((w, h), self.grid, panels, options)
            if key is not None:
                self._render_cache = (key, data)
        if filepath is None:
            return data
        if hasattr(filepath, "write"):
            filepath.write(data)
            return None
        with open(os.fspath(filepath), "wb") as fh:
            fh.write(data)
        return None


_fig = None


def figure(*args, figsize=(6.4, 4.8), dpi=None, facecolor=None, edgecolor=None, **kwargs):
    """Create a figure; a leading scalar or string is accepted as matplotlib's
    figure number and ignored, while a leading sequence sets `figsize`."""
    global _fig
    if args:
        if isinstance(args[0], (tuple, list, np.ndarray)):
            figsize = args[0]
        if len(args) > 1:
            second = args[1]
            if isinstance(second, (tuple, list, np.ndarray)):
                figsize = second
            else:
                dpi = second
    _fig = Figure(figsize, dpi=dpi, facecolor=facecolor, edgecolor=edgecolor)
    return _fig


def gcf(): return _fig or figure()
def gca(): return gcf().gca()
def close(*_): global _fig; _fig = None


def subplots(nrows=1, ncols=1, figsize=(6.4, 4.8), dpi=None, facecolor=None,
             edgecolor=None, sharex=False, sharey=False, squeeze=True, **kwargs):
    fig = figure(figsize, dpi=dpi, facecolor=facecolor, edgecolor=edgecolor)
    return fig, fig.subplots(nrows, ncols, sharex=sharex, sharey=sharey, squeeze=squeeze)


def subplot(*args, **kwargs):
    """`subplot(nrows, ncols, index)` or `subplot(gs[row, col])`."""
    return gcf().add_subplot(*args)


def subplot_mosaic(mosaic, empty_sentinel=".", figsize=(6.4, 4.8), dpi=None,
                   facecolor=None, edgecolor=None, **kwargs):
    fig = figure(figsize, dpi=dpi, facecolor=facecolor, edgecolor=edgecolor)
    return fig, fig.subplot_mosaic(mosaic, empty_sentinel=empty_sentinel)
def suptitle(t, x=0.5, y=0.98, fontsize=None, **kwargs):
    return gcf().suptitle(t, x=x, y=y, fontsize=fontsize, **kwargs)
def figtext(x, y, s, **kwargs):
    return gcf().text(x, y, s, **kwargs)
def plot(*args, **kwargs): return gca().plot(*args, **kwargs)
def xlabel(text, fontsize=None, **kwargs): gca().set_xlabel(text, fontsize=fontsize)
def ylabel(text, fontsize=None, **kwargs): gca().set_ylabel(text, fontsize=fontsize)
def title(text, fontsize=None, **kwargs): gca().set_title(text, fontsize=fontsize)
def text(*args, **kwargs): return gca().text(*args, **kwargs)
def xticks(ticks=None, labels=None, **kwargs):
    return gca().xticks(ticks, labels=labels, **kwargs)
def yticks(ticks=None, labels=None, **kwargs):
    return gca().yticks(ticks, labels=labels, **kwargs)
def imshow(X, cmap=None, vmin=None, vmax=None, extent=None, origin="upper",
           interpolation=None, aspect=None, alpha=None, **kwargs):
    return gca().imshow(X, cmap=cmap, vmin=vmin, vmax=vmax, extent=extent, origin=origin,
                        interpolation=interpolation, aspect=aspect, alpha=alpha, **kwargs)


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
def bar_label(container, labels=None, fmt="%g", label_type="edge", padding=0, **kwargs):
    return gca().bar_label(container, labels=labels, fmt=fmt, label_type=label_type,
                           padding=padding, **kwargs)
def barh(*args, **kwargs): return gca().barh(*args, **kwargs)
def boxplot(*args, **kwargs): return gca().boxplot(*args, **kwargs)
def violinplot(*args, **kwargs): return gca().violinplot(*args, **kwargs)
def pie(*args, **kwargs): return gca().pie(*args, **kwargs)
def stackplot(*args, **kwargs): return gca().stackplot(*args, **kwargs)
def stem(*args, **kwargs): return gca().stem(*args, **kwargs)
def pcolormesh(*args, **kwargs): return gca().pcolormesh(*args, **kwargs)
def pcolor(*args, **kwargs): return gca().pcolormesh(*args, **kwargs)
def pcolorfast(*args, **kwargs): return gca().pcolormesh(*args, **kwargs)
def hist2d(*args, **kwargs): return gca().hist2d(*args, **kwargs)
def hexbin(*args, **kwargs): return gca().hexbin(*args, **kwargs)


def annotate(*args, **kwargs): return gca().annotate(*args, **kwargs)


def scatter(x, y, s=None, c=None, alpha=None, cmap=None, label="", marker="o", vmin=None,
            vmax=None, data=None, **kwargs):
    return gca().scatter(x, y, s=s, c=c, alpha=alpha, cmap=cmap, label=label, marker=marker,
                         vmin=vmin, vmax=vmax, data=data)


def axes(*args, **kwargs):
    """Compatibility shim: matplotvite lays out subplots on a grid, so this returns the
    current axes (creating one if needed)."""
    return gca()


def axis(*args, **kwargs): return gca().axis(*args, **kwargs)


def show(*args, **kwargs): pass

def draw(*args, **kwargs): pass

def pause(*args, **kwargs): pass


def ion(*args, **kwargs): pass
def ioff(*args, **kwargs): pass
def use(*args, **kwargs): pass
def connect(*args, **kwargs): return 1
def figaspect(aspect):
    """Return a figure size with the requested height/width ratio."""
    aspect = float(aspect)
    if aspect < 1.0:
        return (4.0, 4.0 * aspect)
    return (4.0 * aspect, 4.0)


def quiver(*args, **kwargs):
    return gca().quiver(*args, **kwargs)


def quiverkey(*args, **kwargs):
    return gca().quiverkey(*args, **kwargs)


def errorbar(x, y, yerr=None, xerr=None, fmt="", ecolor=None, elinewidth=None, capsize=None,
             label="", color=None, **kwargs):
    return gca().errorbar(x, y, yerr=yerr, xerr=xerr, fmt=fmt, ecolor=ecolor,
                          elinewidth=elinewidth, capsize=capsize, label=label, color=color)


def colorbar(mappable=None, ax=None, label="", **kwargs):
    return gcf().colorbar(mappable, ax=ax, label=label, **kwargs)


def contour(*args, levels=None, colors=None, cmap=None, linewidths=None, alpha=None,
            **kwargs):
    return gca().contour(*args, levels=levels, colors=colors, cmap=cmap,
                         linewidths=linewidths, alpha=alpha, **kwargs)


def contourf(*args, levels=None, colors=None, cmap=None, alpha=None, **kwargs):
    return gca().contourf(*args, levels=levels, colors=colors, cmap=cmap,
                          alpha=alpha, **kwargs)


def set_cmap(cmap):
    """Set the default colormap used by image-like artists."""
    rcParams["image.cmap"] = _cmap_name(cmap)


def xlim(*args, **kwargs):
    ax = gca()
    if not args and not kwargs:
        return ax.get_xlim()
    if len(args) == 1 and isinstance(args[0], (tuple, list, np.ndarray)):
        ax.set_xlim(*args[0], **kwargs)
    else:
        ax.set_xlim(*args, **kwargs)
    return ax.get_xlim()


def ylim(*args, **kwargs):
    ax = gca()
    if not args and not kwargs:
        return ax.get_ylim()
    if len(args) == 1 and isinstance(args[0], (tuple, list, np.ndarray)):
        ax.set_ylim(*args[0], **kwargs)
    else:
        ax.set_ylim(*args, **kwargs)
    return ax.get_ylim()
def legend(*args, **kwargs): return gca().legend(*args, **kwargs)
def eventplot(*args, **kwargs): return gca().eventplot(*args, **kwargs)
def broken_barh(*args, **kwargs): return gca().broken_barh(*args, **kwargs)
def minorticks_on(): return gca().minorticks_on()
def minorticks_off(): return gca().minorticks_off()


def getp(obj, *args):
    """Generic getter: `getp(artist, "color")` calls `artist.get_color()`."""
    out = []
    for name in args:
        getter = getattr(obj, f"get_{name}", None)
        if getter is None:
            raise AttributeError(f"{type(obj).__name__} has no get_{name}")
        out.append(getter())
    if not out:
        return None
    return out[0] if len(out) == 1 else out


def setp(obj, *args, **kwargs):
    """Generic setter: `setp(artist, color="red")` calls `artist.set_color()`."""
    for name, value in kwargs.items():
        setter = getattr(obj, f"set_{name}", None)
        if setter is None:
            raise AttributeError(f"{type(obj).__name__} has no set_{name}")
        setter(value)
    if args:
        return getp(obj, *args)
    return None
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
    "figure.titlesize": 14.0,
    "legend.fontsize": 10.0,
    "axes.prop_cycle": _CycleList(_CYCLE),
    "image.cmap": "viridis",
    "figure.facecolor": "#ffffff",
    "axes.facecolor": "#ffffff",
    "axes.edgecolor": "#000000",
    "axes.labelcolor": "#000000",
    "xtick.color": "#000000",
    "ytick.color": "#000000",
    "text.color": "#000000",
    "grid.color": "#b0b0b0",
}
_RC_DEFAULTS = dict(rcParams)


class _Namespace:
    def __init__(self, **values): self.__dict__.update(values)


class _Normalize:
    def __init__(self, vmin=None, vmax=None, clip=False):
        self.vmin, self.vmax, self.clip = vmin, vmax, clip

    def __call__(self, value, clip=None): return value
    def autoscale(self, A): return None
    def autoscale_None(self, A): return None
    def inverse(self, value): return value


class _BoundaryNorm(_Normalize):
    def __init__(self, boundaries, ncolors, clip=False, **kwargs):
        super().__init__(clip=clip)
        self.boundaries = np.asarray(boundaries, dtype=float)
        self.ncolors = int(ncolors)

    def __call__(self, value, clip=None):
        return np.clip(np.digitize(value, self.boundaries) - 1, 0, self.ncolors - 1)


class _ListedColormap:
    def __init__(self, colors, name="from_list"):
        self.colors = [_norm_color(c) for c in colors]
        self.name, self.N = str(name), len(self.colors)

    @classmethod
    def from_list(cls, name, colors, N=256):
        if colors and isinstance(colors[0], (tuple, list)) and len(colors[0]) == 2:
            colors = [c for _, c in colors]
        return cls(colors, name)

    def __call__(self, X, alpha=None, bytes=False):
        arr = np.asarray(X, dtype=float)
        index = np.clip((arr * self.N).astype(int), 0, self.N - 1)
        rgb = np.asarray([[int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)]
                          for c in self.colors], dtype=float) / 255.0
        out = rgb[index]
        return out.astype(np.uint8) if bytes else out


def _rgba_tuple(color):
    value = _norm_color(color)
    if value in (None, "none"):
        return (0.0, 0.0, 0.0, 0.0)
    body = value[1:]
    rgba = [int(body[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    rgba.append(int(body[6:8], 16) / 255.0 if len(body) == 8 else 1.0)
    return tuple(rgba)


class _MColors:
    Normalize = _Normalize
    LogNorm = _Normalize
    NoNorm = _Normalize
    BoundaryNorm = _BoundaryNorm
    Colormap = Colormap
    ListedColormap = _ListedColormap
    LinearSegmentedColormap = _ListedColormap
    TABLEAU_COLORS = dict(_TAB10)
    BASE_COLORS = {name: _norm_color(name) for name in ("b", "g", "r", "c", "m", "y", "k", "w")}
    CSS4_COLORS = _CSS_COLORS
    cnames = _CSS_COLORS

    @staticmethod
    def to_rgb(color): return _rgba_tuple(color)[:3]

    @staticmethod
    def to_rgba(color, alpha=None, **kwargs):
        rgba = _rgba_tuple(color)
        return rgba if alpha is None else (*rgba[:3], float(alpha))

    @staticmethod
    def to_rgba_array(colors, alpha=None):
        values = [_rgba_tuple(c) for c in colors]
        return np.asarray([v if alpha is None else (*v[:3], float(alpha)) for v in values])

    @staticmethod
    def rgb2hex(rgb): return _norm_color(tuple(rgb))

    @staticmethod
    def to_hex(color, keep_alpha=False):
        value = _norm_color(color)
        return value if keep_alpha or value in (None, "none") else value[:7]


class _NoopLocator:
    def __init__(self, *args, **kwargs): pass
    def __call__(self): return []
    def tick_values(self, vmin, vmax): return np.array([vmin, vmax], dtype=float)
    def set_params(self, **kwargs): return None
    def set_axis(self, axis): return None


class _NoopFormatter:
    def __init__(self, *args, **kwargs): self.args = args
    def __call__(self, value, pos=None): return str(value)
    def set_axis(self, axis): return None
    def set_locs(self, locs): return None


class _PathEffects:
    class Normal:
        def __init__(self, *args, **kwargs): pass
    class SimplePatchShadow:
        def __init__(self, *args, **kwargs): pass
    class SimpleLineShadow:
        def __init__(self, *args, **kwargs): pass
    class Stroke:
        def __init__(self, *args, **kwargs): pass

    @staticmethod
    def withStroke(*args, **kwargs): return _PathEffects.Stroke()

    @staticmethod
    def withSimplePatchShadow(*args, **kwargs): return _PathEffects.SimplePatchShadow()


class GridSpecFromSubplotSpec(GridSpec):
    """A GridSpec rooted at an existing SubplotSpec."""

    def __init__(self, nrows, ncols, subplot_spec=None, **kwargs):
        super().__init__(nrows, ncols, **kwargs)
        self.subplot_spec = subplot_spec


def _offset_copy(trans, fig=None, x=0, y=0, units="inches", **kwargs):
    _ignored("mtransforms.offset_copy")
    return _Transform()


mcolors = _MColors()
colors = mcolors
mpatches = patches
mpath = _Namespace(Path=Path)
mcollections = _Namespace(Collection=Collection, LineCollection=LineCollection,
                          PolyCollection=PolyCollection, PatchCollection=PatchCollection,
                          EventCollection=EventCollection, PathCollection=LineCollection)
mtransforms = _Namespace(Transform=_Transform, Affine2D=Affine2D, Bbox=_Bbox,
                         offset_copy=_offset_copy)
mticker = _Namespace(
    Locator=_NoopLocator, MultipleLocator=_NoopLocator, FixedLocator=_NoopLocator,
    LinearLocator=_NoopLocator, LogLocator=_NoopLocator, MaxNLocator=_NoopLocator,
    NullLocator=_NoopLocator, AutoMinorLocator=_NoopLocator, Formatter=_NoopFormatter,
    FuncFormatter=_NoopFormatter, FormatStrFormatter=_NoopFormatter,
    StrMethodFormatter=_NoopFormatter, ScalarFormatter=_NoopFormatter,
    LogFormatter=_NoopFormatter, NullFormatter=_NoopFormatter,
)
ticker = mticker
gridspec = _Namespace(GridSpec=GridSpec, SubplotSpec=SubplotSpec,
                      GridSpecFromSubplotSpec=GridSpecFromSubplotSpec)
lines = _Namespace(Line2D=Line2D)
patheffects = _PathEffects()
path_effects = patheffects
color_sequences = {"tableau": list(_CYCLE), "petroff": ["#000000", "#1f77b4", "#2ca02c",
                                                        "#d62728", "#9467bd", "#8c564b"]}


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


_STYLE_PRESETS = {
    "dark_background": {
        "figure.facecolor": "#000000", "axes.facecolor": "#000000",
        "axes.edgecolor": "#ffffff", "text.color": "#dddddd",
        "axes.labelcolor": "#dddddd", "xtick.color": "#dddddd",
        "ytick.color": "#dddddd", "grid.color": "#555555",
        "axes.prop_cycle": ["#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3",
                            "#fdb462", "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd"],
    },
    "ggplot": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#e5e5e5",
        "axes.edgecolor": "#ffffff", "text.color": "#555555",
        "axes.labelcolor": "#555555", "xtick.color": "#555555",
        "ytick.color": "#555555", "grid.color": "#ffffff",
        "axes.prop_cycle": ["#e24a33", "#348abd", "#988ed5", "#777777", "#fbc15e",
                            "#8eba42", "#ffb5b8"],
    },
    "seaborn-v0_8": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#eaeaf2",
        "axes.edgecolor": "#ffffff", "text.color": "#262626",
        "axes.labelcolor": "#262626", "xtick.color": "#262626",
        "ytick.color": "#262626", "grid.color": "#ffffff",
        "axes.prop_cycle": ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3",
                            "#937860", "#da8bc3", "#8c8c8c", "#ccb974", "#64b5cd"],
    },
    "seaborn": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#eaeaf2",
        "axes.edgecolor": "#ffffff", "text.color": "#262626",
        "axes.labelcolor": "#262626", "xtick.color": "#262626",
        "ytick.color": "#262626", "grid.color": "#ffffff",
    },
    "bmh": {
        "figure.facecolor": "#eeeeee", "axes.facecolor": "#eeeeee",
        "axes.edgecolor": "#bcbcbc", "text.color": "#262626",
        "axes.labelcolor": "#262626", "xtick.color": "#262626",
        "ytick.color": "#262626", "grid.color": "#ffffff",
    },
    "fivethirtyeight": {
        "figure.facecolor": "#f0f0f0", "axes.facecolor": "#f0f0f0",
        "axes.edgecolor": "#f0f0f0", "text.color": "#262626",
        "axes.labelcolor": "#262626", "xtick.color": "#262626",
        "ytick.color": "#262626", "grid.color": "#cbcbcb",
        "axes.prop_cycle": ["#008fd5", "#fc4f30", "#e5ae38", "#6d904f", "#8b8b8b"],
    },
    "grayscale": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#ffffff",
        "axes.edgecolor": "#000000", "text.color": "#000000",
        "axes.labelcolor": "#000000", "xtick.color": "#000000",
        "ytick.color": "#000000", "grid.color": "#b0b0b0",
        "axes.prop_cycle": ["#000000", "#555555", "#aaaaaa", "#dddddd"],
    },
    "Solarize_Light2": {
        "figure.facecolor": "#fdf6e3", "axes.facecolor": "#eee8d5",
        "axes.edgecolor": "#93a1a1", "text.color": "#073642",
        "axes.labelcolor": "#073642", "xtick.color": "#073642",
        "ytick.color": "#073642", "grid.color": "#93a1a1",
        "axes.prop_cycle": ["#268bd2", "#2aa198", "#859900", "#b58900", "#cb4b16",
                            "#dc322f", "#d33682", "#6c71c4"],
    },
    "classic": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#ffffff",
        "axes.edgecolor": "#000000", "text.color": "#000000",
        "axes.labelcolor": "#000000", "xtick.color": "#000000",
        "ytick.color": "#000000", "grid.color": "#b0b0b0",
        "axes.prop_cycle": ["#0000ff", "#00ff00", "#ff0000", "#00ffff",
                            "#ff00ff", "#ffff00", "#000000"],
    },
}


def _style_rc(style):
    """Merge a preset name, a list of names or a dict into one rc mapping."""
    if isinstance(style, dict):
        return dict(style)
    if isinstance(style, (list, tuple)):
        merged = {}
        for item in style:
            merged.update(_style_rc(item))
        return merged
    name = str(style)
    if name == "default":
        return dict(_RC_DEFAULTS)
    if name not in _STYLE_PRESETS:
        raise ValueError(f"style not found: {name!r}")
    return dict(_STYLE_PRESETS[name])


class _StyleLibrary:
    """The `plt.style` namespace: presets, `use`, and `context`."""

    available = sorted(["default", *_STYLE_PRESETS], key=str)
    library = _STYLE_PRESETS

    def use(self, style):
        if isinstance(style, str) and style == "default":
            rcdefaults()
        else:
            rcParams.update(_style_rc(style))

    def context(self, style):
        return rc_context(_style_rc(style))


style = _StyleLibrary()


def savefig(filepath=None, format=None, dpi=None, bbox_inches=None, transparent=False,
            facecolor=None, edgecolor=None, compression=None):
    return gcf().savefig(filepath, format=format, dpi=dpi, bbox_inches=bbox_inches,
                         transparent=transparent, facecolor=facecolor, edgecolor=edgecolor,
                         compression=compression)
