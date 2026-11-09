"""matplotvite: minimal matplotlib-like API, rendered entirely in Rust."""
import datetime as _datetime
import hashlib as _hashlib
import math as _math
import os
import re as _re
from contextlib import contextmanager

import numpy as np

from ._cmaps import COLORMAPS as _CMAP_DATA
from ._colors import CSS_COLORS as _CSS_COLORS
from ._core import __version__, render as _render

__all__ = (
    "Axes", "AxesImage", "Colorbar", "Colormap", "ContourSet", "DPI", "Figure", "GridSpec",
    "SubplotSpec", "cm", "colormaps",
    "annotate", "axes", "axis", "axhline", "axhspan", "axline", "axvline", "axvspan",
    "bar", "bar_label", "barh", "boxplot", "broken_barh", "close", "colorbar", "contour", "contourf",
    "draw", "errorbar", "eventplot", "figure", "fill", "fill_between", "violinplot",
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
_SUPERSCRIPTS = str.maketrans(
    "0123456789+-=()abcdefghijklmnoprstuvwxyz",
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ",
)
_SUBSCRIPTS = str.maketrans(
    "0123456789+-=()aehijklmnoprstuvx",
    "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ",
)


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
        body = _re.sub(r"\^\{([^{}]*)\}", lambda m: m.group(1).translate(_SUPERSCRIPTS), body)
        body = _re.sub(r"\^(\S)", lambda m: m.group(1).translate(_SUPERSCRIPTS), body)
        body = _re.sub(r"_\{([^{}]*)\}", lambda m: m.group(1).translate(_SUBSCRIPTS), body)
        body = _re.sub(r"_(\S)", lambda m: m.group(1).translate(_SUBSCRIPTS), body)
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
        t = np.clip(arr, 0.0, 1.0)
        index = np.minimum((t * self.N).astype(int), self.N - 1)
        if self._reverse:
            index = self.N - 1 - index
        rgb = self._rgb[index]
        if alpha is None:
            alpha_arr = np.ones(rgb.shape[:-1], dtype=np.float64)
        else:
            alpha_arr = np.broadcast_to(np.asarray(alpha, dtype=np.float64),
                                        rgb.shape[:-1])
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


class _CoordTransform:
    """Marker for `text(transform=...)`: data, axes or figure coordinates."""

    def __init__(self, kind):
        self.kind = kind


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
    """Same padding rule as the Rust renderer: a flat series gets a unit window.

    Optimized with NumPy vectorized min/max to avoid Python list-comprehension
    overhead on large series (e.g. 10k-100k points), with fallback for mixed types.
    """
    try:
        arr = np.asarray(values, dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        if not arr.size:
            return (0.0, 1.0)
        lo = float(np.min(arr))
        hi = float(np.max(arr))
        return (lo, hi) if lo < hi else (lo - 1.0, lo + 1.0)
    except (TypeError, ValueError):
        vals = [float(v) for v in values]
        vals = [v for v in vals if np.isfinite(v)]
        if not vals:
            return (0.0, 1.0)
        lo, hi = min(vals), max(vals)
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


def _patch_entry(artist):
    """Reduce a Rectangle/Circle/Polygon-like object, or return None."""
    kind = None
    x = y = w = h = 0.0
    points = []
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
    if kind is None and _call(artist, "get_radius") is not None:
        center = _call(artist, "get_center")
        if center is not None:
            kind, x, y = "circle", float(center[0]), float(center[1])
            w = float(_call(artist, "get_radius"))
    if kind is None:
        vals = [_call(artist, name) for name in
                ("get_x", "get_y", "get_width", "get_height")]
        if all(v is not None for v in vals):
            kind = "rect"
            x, y, w, h = (float(v) for v in vals)
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
        x, y, fmt = _plot_args(args, fmt)
        if y is None:
            x, y = np.arange(len(x)), x
        if not label and getattr(y, "name", None) is not None:
            label = str(y.name)
        x = self._xdate(x)
        style = linestyle or ls or "-"
        if fmt:
            f_color, f_style, f_marker = _parse_fmt(fmt)
            color = color or c or f_color
            if linestyle is None and ls is None:
                style = f_style or style
            if not marker:
                marker = f_marker
        line_color = color or c or self._next_color()
        if drawstyle not in ("default", "steps-pre", "steps-post"):
            raise ValueError(f"unsupported drawstyle: {drawstyle!r}")
        edge = markeredgecolor or mec
        self.lines.append(_series(
            x, y, label, line_color, linestyle=style,
            linewidth=linewidth if linewidth is not None else (lw if lw is not None else rcParams.get("lines.linewidth", 2.0)),
            marker=marker or "",
            markersize=markersize if markersize is not None else (ms if ms is not None else rcParams.get("lines.markersize", 6.0)),
            mfc=markerfacecolor or mfc, mec=edge,
            mew=markeredgewidth if markeredgewidth is not None else (mew if mew is not None else rcParams.get("lines.markerlinewidth", 1.0)),
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
        twin = Axes(self.pos)
        twin._fig, twin._twin, twin._twin_gap = fig, axis, gap
        twin._twin_of = self
        twin._pos_override = box.bounds
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
        if self._share_x is not None:
            lo, hi = self._share_x.limits or self._share_x.union("x")
        else:
            lo, hi = self.xlim or self._extent_x()
        return _log_bounds(lo, hi, self.xscale, self._extent_x())

    def get_ylim(self):
        if self._share_y is not None:
            lo, hi = self._share_y.limits or self._share_y.union("y")
        else:
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

    def get_facecolor(self):
        return self.facecolor or rcParams.get("axes.facecolor", "white")

    def set_facecolor(self, color): self.facecolor = str(color)
    def get_alpha(self): return self.alpha
    def set_alpha(self, alpha): self.alpha = None if alpha is None else float(alpha)

    def get_transform(self): return _Transform()

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
        self.arrows.clear()
        self.bars.clear()
        self.bands.clear()
        self._hline_refs.clear()
        self._vline_refs.clear()
        self.hspans.clear()
        self.vspans.clear()
        self.artists.clear()
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
                    raise AttributeError(f"Axes.set() does not support {key!r}")
                setter(value)

    def text(self, x, y, s, color=None, fontsize=None, ha="left", va="baseline",
             transform=None):
        """Place text at (x, y); `transform` may be `ax.transAxes` or
        `fig.transFigure` to use axes- or figure-fraction coordinates."""
        if ha not in ("left", "center", "right"):
            raise ValueError(f"unsupported ha: {ha!r}")
        if va not in ("baseline", "bottom", "center", "top"):
            raise ValueError(f"unsupported va: {va!r}")
        kind = getattr(transform, "kind", "data") if transform is not None else "data"
        if kind not in ("data", "axes", "figure"):
            raise ValueError(f"unsupported text transform: {transform!r}")
        size = float(fontsize) if fontsize is not None else float(rcParams.get("font.size", 10.0))
        color = color if color is not None else rcParams.get("text.color", "black")
        if kind == "data":
            x = self._xdate(x)
        self.texts.append((float(x), float(y), _mathtext(s), _norm_color(color), size, ha, va, kind))

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
        entry = dict(data=a, cmap=_cmap_name(cmap), vmin=vmin, vmax=vmax,
                     extent=tuple(float(v) for v in extent))
        self.images.append(entry)
        # matplotlib's image.aspect default is "equal".
        self.set_aspect("equal" if aspect is None else aspect)
        return AxesImage(entry)

    def hist(self, x, bins=10, range=None, density=False, weights=None, cumulative=False,
             bottom=None, histtype="bar", align="mid", orientation="vertical", color=None,
             label=None, alpha=None, edgecolor=None, stacked=False, **kwargs):
        """Histogram of `x`, drawn as bars; returns `(counts, edges, handles)`."""
        if histtype not in ("bar", "step", "stepfilled"):
            raise NotImplementedError(f"histtype={histtype!r} is not supported yet")
        data = np.asarray(x, dtype=np.float64).ravel()
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
                for q in np.atleast_1d(np.asarray(quantiles, dtype=np.float64)).ravel():
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
        width = (ex1 - ex0) / nx
        height = width * np.sqrt(3.0) / 2.0
        rows = ny or max(int(np.ceil((ey1 - ey0) / height)), 1)
        rows = max(rows, 1) + 1  # odd columns are offset by half a row
        centers, cell = _hexbin_cells(x, y, nx, rows, width, height, ex0, ey0)
        total = nx * rows
        counts = np.bincount(cell, minlength=total).astype(np.float64)
        if C is None:
            values = counts.copy()
        else:
            weights = np.asarray(C, dtype=np.float64).ravel()
            if weights.size != x.size:
                raise ValueError("C must have one value per point")
            sums = np.bincount(cell, weights=weights, minlength=total)
            values = np.divide(sums, counts, out=np.zeros(total), where=counts > 0)
        keep = np.ones(total, dtype=bool) if mincnt is None else counts > float(mincnt)
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
        radius = width / np.sqrt(3.0)
        angles = np.deg2rad(90.0 + 60.0 * np.arange(6))
        for k, color in zip(shown, colors):
            cx, cy = centers[k]
            self.bands.append(_band(cx + radius * np.cos(angles),
                                    cy + radius * np.sin(angles), color, alpha))
        return _HexbinHandle(values[shown], centers[shown], colors, cmap)

    def annotate(self, text, xy, xytext=None, arrowprops=None, color=None, fontsize=None):
        """Text at `xytext` with an arrow pointing at `xy`."""
        size = float(fontsize) if fontsize is not None else float(rcParams.get("font.size", 10.0))
        color = color if color is not None else rcParams.get("text.color", "black")
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
            x = np.asarray(self._xdate(args[0]), dtype=np.float64).ravel()
            y, u, v = (np.asarray(a, dtype=np.float64).ravel() for a in args[1:4])
            if len(args) >= 5 and C is None:
                C = args[4]
        elif len(args) == 0 and U is not None and V is not None:
            ua = np.asarray(U, dtype=np.float64).ravel()
            va = np.asarray(V, dtype=np.float64).ravel()
            if ua.size != va.size:
                raise ValueError("U and V must have the same shape")
            x = np.arange(ua.size, dtype=float)
            y = np.zeros(ua.size)
            u, v = ua, va
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
                     colors=_colors(colors), cmap=_cmap_name(cmap), filled=filled)
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
    def _size_or(value, key):
        return float(value) if value is not None else float(rcParams.get(key, rcParams.get("font.size", 10.0)))

    def set_xlim(self, lo, hi):
        values = self._xdate((lo, hi))
        limits = self.xlim = (float(values[0]), float(values[1]))
        if self._share_x is not None:
            self._share_x.limits = limits

    def set_ylim(self, lo, hi):
        limits = self.ylim = (float(lo), float(hi))
        if self._share_y is not None:
            self._share_y.limits = limits

    def legend(self, loc=None, ncol=None, ncols=None, frameon=None, fontsize=None,
               title=None, title_fontsize=None, bbox_to_anchor=None, **kwargs):
        """Show a legend. Supports matplotlib's common placement and layout kwargs."""
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
            self.legend_fontsize = float(fontsize)
        if title is not None:
            self.legend_title = _mathtext(title)
        if title_fontsize is not None:
            self.legend_title_fontsize = float(title_fontsize)
        elif title is not None and self.legend_title_fontsize is None:
            self.legend_title_fontsize = float(rcParams.get("legend.fontsize", 10.0)) * 1.1
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
            # For 'mid', corners are at midpoints of each interval
            x_arr = np.asarray(x, dtype=np.float64).ravel()
            y_arr = np.asarray(y, dtype=np.float64).ravel()
            x_mid = (x_arr[:-1] + x_arr[1:]) / 2.0
            y_mid = (y_arr[:-1] + y_arr[1:]) / 2.0
            # Repeat mids to create steps: left-right pairs per interval
            x_out = np.repeat(x_mid, 2)
            y_out = np.repeat(y_mid, 2)
            # Shift the second of each pair to the next x value
            x_out[1::2] = x_arr[1:]
            y_out[1::2] = y_arr[:-1]
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
        contours = [(c["x"], c["y"], c["z"], c["levels"],
                     [_norm_color(v) for v in c["colors"]], c["cmap"], c["filled"])
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
                    colorbar=None,
                    axis_off=self._axis_off,
                    facecolor=_norm_color(self.facecolor or rcParams.get("axes.facecolor")),
                    foreground=_norm_color(rcParams.get("text.color")),
                    bounds=self._pos_override, twin=self._twin, twin_gap=self._twin_gap,
                    patches=patches, collections=collections,
                    images=[(e["data"], e["cmap"], e["vmin"], e["vmax"], e["extent"], True)
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
        hasher.update(b"array")
        hasher.update(value.dtype.str.encode())
        hasher.update(str(value.shape).encode())
        hasher.update(np.ascontiguousarray(value).tobytes())
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
        hasher = _hashlib.blake2b(digest_size=8)
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


_STEM_MARKERS = "os^v<>Dx+."


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
                alpha=None if alpha is None else float(alpha), label=str(label))


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
    t = np.clip(np.asarray(values, dtype=np.float64).ravel(), 0.0, 1.0)
    n = table.shape[0]
    index = np.minimum((t * n).astype(int), n - 1)
    if reverse:
        index = n - 1 - index
    rgb = table[index]
    return [f"#{int(r):02x}{int(g):02x}{int(b):02x}" for r, g, b in rgb]


def _hexbin_cells(x, y, nx, rows, width, height, x0, y0):
    """Nearest hexagonal cell for every point, plus the cell centres."""
    cols = np.clip(np.floor((x - x0) / width).astype(int), 0, nx - 1)
    best = np.zeros(x.size, dtype=int)
    best_d = np.full(x.size, np.inf)
    for di in (-1, 0, 1):
        ci = np.clip(cols + di, 0, nx - 1)
        offset = 0.5 * (ci % 2)
        base_row = np.floor((y - y0) / height - 0.5 - offset).astype(int)
        for dj in (-1, 0, 1):
            cj = np.clip(base_row + dj, 0, rows - 1)
            cx = x0 + (ci + 0.5) * width
            cy = y0 + (cj + 0.5 + offset) * height
            distance = (x - cx) ** 2 + (y - cy) ** 2
            better = distance < best_d
            best_d[better] = distance[better]
            best[better] = ci[better] * rows + cj[better]
    ci = np.repeat(np.arange(nx), rows)
    cj = np.tile(np.arange(rows), nx)
    centers = np.column_stack([x0 + (ci + 0.5) * width,
                               y0 + (cj + 0.5 + 0.5 * (ci % 2)) * height])
    return centers, best


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

    def _colorbar_spec(self):
        lv = self._e["levels"]
        return dict(cmap=self._e["cmap"], vmin=lv[0], vmax=lv[-1])


class AxesImage:
    """Handle returned by `Axes.imshow`, for later tweaks."""

    def __init__(self, entry): self._e = entry

    def get_array(self): return self._e["data"]
    def set_data(self, X): self._e["data"] = _as_image(X)
    def get_cmap(self): return self._e["cmap"]
    def set_cmap(self, cmap): self._e["cmap"] = _cmap_name(cmap)
    def set_extent(self, extent): self._e["extent"] = tuple(float(v) for v in extent)

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
                 bottom=0.0, top=1.0, wspace=None, hspace=None):
        if int(nrows) < 1 or int(ncols) < 1:
            raise ValueError("GridSpec needs at least one row and one column")
        self.nrows, self.ncols = int(nrows), int(ncols)
        self.figure = figure
        self.left, self.right = float(left), float(right)
        self.bottom, self.top = float(bottom), float(top)
        self.wspace = 0.2 if wspace is None else float(wspace)
        self.hspace = 0.2 if hspace is None else float(hspace)

    def __getitem__(self, key):
        rows, cols = key if isinstance(key, tuple) else (key, key)
        return SubplotSpec(self, _span_index(rows, self.nrows),
                           _span_index(cols, self.ncols))

    def get_geometry(self):
        return self.nrows, self.ncols

    def _bounds(self, rows, cols):
        r0, r1 = rows
        c0, c1 = cols
        cell_w = (self.right - self.left) / self.ncols
        cell_h = (self.top - self.bottom) / self.nrows
        x0 = self.left + c0 * cell_w
        x1 = self.left + (c1 + 1) * cell_w
        y1 = self.top - r0 * cell_h
        y0 = self.top - (r1 + 1) * cell_h
        if c0 > 0:
            x0 += self.wspace * cell_w / 2.0
        if c1 < self.ncols - 1:
            x1 -= self.wspace * cell_w / 2.0
        if r0 > 0:
            y1 -= self.hspace * cell_h / 2.0
        if r1 < self.nrows - 1:
            y0 += self.hspace * cell_h / 2.0
        return (x0, y0, max(x1 - x0, 0.01), max(y1 - y0, 0.01))


class Colorbar:
    """Handle returned by `Figure.colorbar`."""

    def __init__(self, entry): self._e = entry

    def set_label(self, label): self._e["label"] = str(label)
    def get_label(self): return self._e["label"]


class Figure:
    def __init__(self, figsize=(6.4, 4.8), dpi=None, facecolor=None, edgecolor=None):
        self.figsize, self.grid, self.axes, self._cur = figsize, (1, 1), [], None
        self._colorbar = None
        self.dpi = float(dpi if dpi is not None else rcParams.get("figure.dpi", DPI))
        self.facecolor = _norm_color(
            facecolor if facecolor is not None else rcParams.get("figure.facecolor"))
        self.edgecolor = _norm_color(edgecolor)
        self._suptitle = None
        self._render_cache = None
        self.transFigure = _CoordTransform("figure")

    def suptitle(self, t, x=0.5, y=0.98, fontsize=None, **kwargs):
        """Draw a figure-level title above the panel grid."""
        size = (float(fontsize) if fontsize is not None
                else float(rcParams.get("figure.titlesize", 14.0)))
        self._suptitle = dict(text=_mathtext(t), size=size, x=float(x), y=float(y))
        return None

    def add_subplot(self, nrows=1, ncols=1, index=1, **kwargs):
        """index is 1-based, row-major (matplotlib convention); a `SubplotSpec`
        may be passed instead to place the axes on an irregular grid."""
        if isinstance(nrows, SubplotSpec):
            return self._add_spec(nrows)
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

    def subplots(self, nrows=1, ncols=1, sharex=False, sharey=False, squeeze=True):
        axs = [self.add_subplot(nrows, ncols, i + 1) for i in range(nrows * ncols)]
        _share_axes(axs, (nrows, ncols), sharex, sharey)
        if len(axs) == 1 and squeeze:
            return axs[0]
        out = np.array(axs, dtype=object).reshape(nrows, ncols)
        return out.squeeze() if squeeze else out

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
    def get_dpi(self): return self.dpi or DPI
    def get_facecolor(self): return self.facecolor or "white"
    def get_edgecolor(self): return self.edgecolor
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
        tick = dict(labelsize=10.0, length=3.5, width=1.0, color=None,
                    labelcolor=None, rotation=0.0)
        return dict(pos=1, series=[], texts=[], title="", xlabel="", ylabel="",
                    dpi=float(self.dpi or DPI),
                    title_size=None, xlabel_size=None, ylabel_size=None,
                    legend=dict(show=False, loc="best", ncol=1, frameon=True,
                                fontsize=10.0, title="", title_fontsize=11.0,
                                anchor=None),
                    grid=dict(show=False, color=None, linewidth=None, alpha=None,
                              linestyle=None, axis="both"),
                    ticks=dict(xticks=None, xticklabels=None, yticks=None,
                               yticklabels=None, xstyle=dict(tick), ystyle=dict(tick),
                               hide_xlabels=False, hide_ylabels=False),
                    xlim=None, ylim=None, annotations=[], images=[],
                    contours=[], errors=[], scatter=[], arrows=[], bars=[], bands=[],
                    x_log=False, y_log=False, log_base=10.0, aspect=None,
                    axis_off=False, facecolor=None, foreground=None,
                    bounds=None, twin="", twin_gap=0.0, patches=[], collections=[],
                    colorbar=(cb["cmap"], cb["vmin"], cb["vmax"], cb["label"]))

    def savefig(self, filepath=None, format=None, dpi=None, bbox_inches=None,
                transparent=False, facecolor=None, edgecolor=None,
                compression=None):
        """Write this figure, or return its bytes when `filepath` is None or a
        file-like object. `format` overrides the extension, `dpi` scales the
        pixel size and `bbox_inches="tight"` crops to the drawn content.
        `compression` selects PNG compression: "fast" (default), "default",
        or "best"."""
        dpi = float(dpi or self.dpi or DPI)
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
        w, h = (round(v * dpi) for v in self.figsize)
        panels = [a._panel() for a in self.axes if a.visible and not a._removed]
        if self._colorbar is not None:
            panels.append(self._colorbar_panel())
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
        }
        # An unchanged figure reuses its last encoded bytes. The key covers both
        # the panel payload and every render option, so any edit invalidates it.
        try:
            hasher = _hashlib.blake2b(digest_size=16)
            _hash_value(hasher, ((w, h), self.grid, panels, options))
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


def figure(figsize=(6.4, 4.8), dpi=None, facecolor=None, edgecolor=None, **kwargs):
    global _fig
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
def plot(*args, **kwargs): return gca().plot(*args, **kwargs)
def xlabel(text, fontsize=None, **kwargs): gca().set_xlabel(text, fontsize=fontsize)
def ylabel(text, fontsize=None, **kwargs): gca().set_ylabel(text, fontsize=fontsize)
def title(text, fontsize=None, **kwargs): gca().set_title(text, fontsize=fontsize)
def text(x, y, s, color=None, fontsize=None, ha="left", va="baseline", transform=None):
    gca().text(x, y, s, color=color, fontsize=fontsize, ha=ha, va=va, transform=transform)
def xticks(ticks=None, labels=None, **kwargs):
    return gca().xticks(ticks, labels=labels, **kwargs)
def yticks(ticks=None, labels=None, **kwargs):
    return gca().yticks(ticks, labels=labels, **kwargs)
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


def annotate(text, xy, xytext=None, arrowprops=None, color=None, fontsize=None):
    gca().annotate(text, xy, xytext=xytext, arrowprops=arrowprops, color=color,
                   fontsize=fontsize)


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


def quiver(*args, **kwargs):
    return gca().quiver(*args, **kwargs)


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


def set_cmap(cmap):
    """Set the default colormap used by image-like artists."""
    rcParams["image.cmap"] = _cmap_name(cmap)


def xlim(lo, hi): gca().set_xlim(lo, hi)
def ylim(lo, hi): gca().set_ylim(lo, hi)
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
    "axes.prop_cycle": list(_CYCLE),
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

    available = sorted(["default", *_STYLE_PRESETS])
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
