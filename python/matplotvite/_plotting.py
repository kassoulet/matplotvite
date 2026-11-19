"""matplotvite: minimal matplotlib-like API, rendered entirely in Rust."""
import copy
import datetime as _datetime
import hashlib as _hashlib
import math as _math
import os
import re as _re
import struct as _struct
import threading
import warnings
import zlib as _zlib
from contextlib import contextmanager
from typing import ClassVar

import numpy as np

from . import tri, units
from ._colors import CSS_COLORS as _CSS_COLORS
from ._core import (
    AsinhNorm as _AsinhNorm,
)
from ._core import (
    BoundaryNorm as _BoundaryNorm,
)
from ._core import (
    Colormap,
)
from ._core import (
    LogNorm as _LogNorm,
)
from ._core import (
    Normalize as _Normalize,
)
from ._core import (
    PowerNorm as _PowerNorm,
)
from ._core import (
    SymLogNorm as _SymLogNorm,
)
from ._core import (
    TwoSlopeNorm as _TwoSlopeNorm,
)
from ._core import (
    auto_ticks as _auto_ticks_core,
)
from ._core import (
    cmap_name as _core_cmap_name,
)
from ._core import (
    colormaps as _colormaps,
)
from ._core import (
    register_colormap as _register_colormap,
)
from ._core import (
    render as _render,
)
from ._core import (
    tick_target as _tick_target_core,
)

_CMAP_DATA = {k: np.frombuffer(v, np.uint8).reshape(-1, 3) for k, v in _colormaps().items()}


# matplotlib's tab10 cycle; also the targets of the C0-C9 shorthand.
_CYCLE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
          "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
# Only the one-letter colors matplotvite can render are honoured in fmt strings.
_FMT_COLORS = {"b": "blue", "g": "green", "r": "red", "k": "black"}
_SHORT_COLORS = {"b": "blue", "g": "green", "r": "red", "c": "cyan",
                 "m": "magenta", "y": "yellow", "k": "black", "w": "white"}
# Matplotlib's C0-C9 order; the `tab:grey` spelling is a trailing alias so
# iterating the dict still lines up with the default property cycle.
_TAB10 = {"tab:blue": "#1f77b4", "tab:orange": "#ff7f0e", "tab:green": "#2ca02c",
          "tab:red": "#d62728", "tab:purple": "#9467bd", "tab:brown": "#8c564b",
          "tab:pink": "#e377c2", "tab:gray": "#7f7f7f", "tab:olive": "#bcbd22",
          "tab:cyan": "#17becf", "tab:grey": "#7f7f7f"}

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


# Artist, legend and figure properties Matplotlib accepts but the renderer does
# not model. They stay accepted, but are recorded as ignored instead of being
# treated as silently supported. Unknown names raise TypeError, as in Matplotlib.
_ARTIST_KWARGS = frozenset(
    "agg_filter alpha animated clip_box clip_on clip_path figure gid in_layout label "
    "mouseover path_effects picker rasterized sketch_params snap transform url visible "
    "zorder".split()
)
_LINE2D_KWARGS = _ARTIST_KWARGS | frozenset(
    "antialiased color dash_capstyle dash_joinstyle dashes data drawstyle ds fillstyle "
    "gapcolor linestyle linewidth ls lw marker markeredgecolor markeredgewidth "
    "markerfacecolor markerfacecoloralt markersize markevery mec mfc mew ms pickradius "
    "solid_capstyle solid_joinstyle xdata ydata".split()
)
_COLLECTION_KWARGS = _ARTIST_KWARGS | frozenset(
    "antialiased array capstyle clim cmap color edgecolor edgecolors ec facecolor "
    "facecolors fc hatch hatch_linewidth hatchcolor joinstyle linestyle linewidth "
    "linewidths ls norm offset_transform offsets paths pickradius urls".split()
)
_PATCH_KWARGS = _ARTIST_KWARGS | frozenset(
    "antialiased capstyle color ec edgecolor edgegapcolor facecolor fc fill hatch "
    "hatch_linewidth hatchcolor joinstyle linestyle linewidth ls lw".split()
)
_IMAGE_KWARGS = _ARTIST_KWARGS | frozenset(
    "array clim cmap data extent filternorm filterrad interpolation "
    "interpolation_stage norm resample".split()
)
_LEGEND_KWARGS = _ARTIST_KWARGS | frozenset(
    "alignment bbox_to_anchor borderaxespad borderpad columnspacing draggable facecolor "
    "fancybox frame_on framealpha frameon handleheight handlelength handletextpad "
    "handler_map labelcolor labelspacing markerfirst markerscale mode ncol ncols "
    "numpoints reverse shadow title title_fontproperties".split()
)
_FIGURE_KWARGS = _ARTIST_KWARGS | frozenset(
    "canvas clear constrained_layout constrained_layout_pads dpi edgecolor facecolor "
    "figheight figsize figwidth frameon layout layout_engine linewidth num size_inches "
    "tight_layout".split()
)
_BAR_KWARGS = _PATCH_KWARGS | frozenset(
    "capsize data error_kw log tick_label xerr".split()
)
_HIST_KWARGS = _BAR_KWARGS | frozenset("ec fc fill log".split())
_SCATTER_KWARGS = _COLLECTION_KWARGS | frozenset(
    "clim color colorizer plotnonfinite".split()
)


def _check_kwargs(kwargs, name, allowed):
    """Reject unknown keywords and record known compatibility keywords."""
    unexpected = sorted(key for key in kwargs if key not in allowed)
    if unexpected:
        raise TypeError(
            f"{name}() got an unexpected keyword argument {unexpected[0]!r}")
    for key in kwargs:
        _ignored(f"{name}({key}=...)")


def _deprecated(name, *, since, alternative=None, removal=None):
    """Warn that a public API is deprecated.

    ``stacklevel=3`` points the warning at the caller of the public function
    that invokes this helper, rather than at the helper or its wrapper.
    """
    message = f"{name} is deprecated since {since}"
    if alternative:
        message += f"; use {alternative} instead"
    message += "."
    if removal:
        message += f" It will be removed in {removal}."
    warnings.warn(message, FutureWarning, stacklevel=3)


def _with_alpha(value, alpha):
    """Apply an alpha value to a normalised colour string."""
    if value in (None, "none"):
        return value
    alpha = min(max(float(alpha), 0.0), 1.0)
    body = value[1:7]
    return f"#{body}{round(alpha * 255):02x}"


def _norm_color(c):
    """Normalise a matplotlib colour spec to `#rrggbb`, `#rrggbbaa` or "none".

    Accepts CSS4 names, single-letter shorthands, `C0`-`C9`, hex strings
    (3/6/8 digits), RGB(A) tuples in 0-1, greyscale strings such as "0.5" and
    Matplotlib's `(color, alpha)` pair form.
    """
    if c is None:
        return None
    if (isinstance(c, (tuple, list)) and len(c) == 2
            and not all(isinstance(v, (int, float, np.number)) for v in c)):
        return _with_alpha(_norm_color(c[0]), c[1])
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
# DejaVu Sans carries the Unicode superscript and subscript digits, signs and
# modifier letters. Geist only has the digits, so those scripts fall back to
# parenthesized baseline notation instead of rendering missing-glyph boxes.
_SUPERSCRIPTS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_MATH_SUPERSCRIPTS = str.maketrans({
    **{ord(ch): out for ch, out in zip("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")},
    **{ord(ch): out for ch, out in zip("+-=()", "⁺⁻⁼⁽⁾")},
    **{ord(ch): out for ch, out in zip("ABCDEGHIJKLMNOPRTUVW",
                                     "ᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ")},
    **{ord(ch): out for ch, out in zip("abcdefghijklmnoprstuvwxyz",
                                     "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ")},
})
_MATH_SUBSCRIPTS = str.maketrans({
    **{ord(ch): out for ch, out in zip("0123456789", "₀₁₂₃₄₅₆₇₈₉")},
    **{ord(ch): out for ch, out in zip("+-=()", "₊₋₌₍₎")},
    **{ord(ch): out for ch, out in zip("aehijklmnoprstuvx",
                                     "ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")},
})


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
    "family figure font fontfamily fontname fontfeatures fontproperties font_properties "
    "fontstretch fontstyle fontvariant variant fontweight gid in_layout language linespacing ma "
    "math_fontfamily multialignment parse_math path_effects picker rasterized "
    "rotation_mode sketch_params snap style transform_rotates_text url usetex verticalalignment "
    "visible weight wrap zorder".split()
)


def _text_bbox(value):
    """Normalise the common `bbox=dict(...)` text frame options."""
    if not isinstance(value, dict):
        return None
    style = str(value.get("boxstyle", "square"))
    match = _re.search(r"pad\s*=\s*([0-9.]+)", style)
    return dict(facecolor=_norm_color(value.get("facecolor", value.get("fc"))),
                edgecolor=_norm_color(value.get("edgecolor", value.get("ec"))),
                alpha=float(value.get("alpha", 1.0)),
                pad=float(match.group(1)) if match else 0.3,
                rounded="round" in style.lower() or "circle" in style.lower())


def _rotation_value(value):
    """Degrees for a text rotation, accepting Matplotlib's string aliases."""
    if value is None:
        return 0.0
    if isinstance(value, str):
        key = value.strip().lower()
        if key in ("vertical", "vert"):
            return 90.0
        if key in ("horizontal", "horiz"):
            return 0.0
        value = key
    return float(value)


def _text_props(fontdict, kwargs):
    """Split text keywords into the honoured subset and the compatibility no-ops."""
    props = dict(fontdict or {})
    props.update(kwargs)
    transform = props.pop("transform", None)
    fontsize = props.pop("fontsize", props.pop("size", None))
    colour = props.pop("color", props.pop("c", None))
    ha = props.pop("horizontalalignment", props.pop("ha", "left"))
    va = props.pop("verticalalignment", props.pop("va", "baseline"))
    bbox = _text_bbox(props.pop("bbox", None))
    rotation = _rotation_value(props.pop("rotation", None))
    family = props.pop("fontfamily", props.pop("family", props.pop("fontname", None)))
    family = _font_family(family)
    unexpected = [key for key in props if key not in _IGNORED_TEXT_KWARGS]
    if unexpected:
        raise TypeError(f"unexpected text keyword argument {unexpected[0]!r}")
    return transform, fontsize, colour, ha, va, bbox, rotation, family


def _mathtext(text, family=None):
    """Render a small `$...$` TeX subset as Unicode for the text renderer."""
    value = str(text)
    if not rcParams.get("text.parse_math", True):
        return value
    parts = value.split("$")
    if len(parts) % 2 == 0:
        return value
    full_scripts = _font_family(family).startswith("DejaVu")

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
                _MATH_SUPERSCRIPTS if full_scripts else _SUPERSCRIPTS,
                "^",
            ),
            body,
        )
        body = _re.sub(
            r"_\{([^{}]*)\}|_(\S)",
            lambda m: _math_script(
                m.group(1) if m.group(1) is not None else m.group(2),
                _MATH_SUBSCRIPTS if full_scripts else _SUBSCRIPTS,
                "_",
            ),
            body,
        )
        return body.replace("{", "").replace("}", "").replace("\\", "")

    out = [parts[0]]
    for i in range(1, len(parts), 2):
        out.extend((segment(parts[i]), parts[i + 1]))
    return "".join(out)


def _register_custom_cmap(cmap):
    """Add a `Colormap` built in Python to the table the renderer reads."""
    name = str(getattr(cmap, "name", "custom"))
    if name not in _CMAP_DATA:
        rgb = np.asarray(cmap._rgb, dtype=np.float64)
        if rgb.ndim != 2 or rgb.shape[1] != 3 or not len(rgb):
            raise ValueError(f"unsupported colormap: {cmap!r}")
        positions = np.linspace(0.0, 1.0, rgb.shape[0])
        samples = np.linspace(0.0, 1.0, 256)
        table = np.stack([np.interp(samples, positions, rgb[:, channel])
                          for channel in range(3)], axis=1)
        pixels = np.clip(table * 255.0, 0, 255).astype(np.uint8)
        _CMAP_DATA[name] = pixels
        _register_colormap(name, pixels.tobytes())
    return name


def _cmap_name(cmap):
    """Canonical registry name; `None` picks up the `image.cmap` rcParam."""
    if isinstance(cmap, Colormap):
        return cmap.name
    if isinstance(cmap, _ListedColormap):
        return _register_custom_cmap(cmap)
    if cmap is None:
        cmap = rcParams.get("image.cmap", "viridis")
    return _core_cmap_name(str(cmap))


def get_cmap(name=None, lut=None):
    """Return a `Colormap` by registry name (or the `image.cmap` default)."""
    cmap = name.copy() if isinstance(name, Colormap) else Colormap(
        name if name is not None else rcParams.get("image.cmap", "viridis"))
    return cmap.resampled(lut) if lut is not None else cmap


def _colormap_names():
    return sorted([*_CMAP_DATA, *(f"{name}_r" for name in _CMAP_DATA)])


class _ColormapRegistry:
    """Matplotlib's colormap registry: iterable, callable and name-indexable."""

    def __call__(self): return _colormap_names()
    def __getitem__(self, name): return get_cmap(name)
    def __iter__(self): return iter(_colormap_names())
    def __len__(self): return len(_CMAP_DATA) * 2
    def __contains__(self, name):
        try:
            _core_cmap_name(str(name))
            return True
        except ValueError:
            return False
    def keys(self): return _colormap_names()
    def values(self): return [get_cmap(name) for name in self]
    def items(self): return [(name, get_cmap(name)) for name in self]
    def get(self, name, default=None):
        try:
            return get_cmap(name)
        except ValueError:
            return default

    def register(self, cmap, name=None, force=False):
        """Register a colormap so `get_cmap`/`colormaps[name]` find it."""
        cmap_name = str(name or getattr(cmap, "name", ""))
        if not cmap_name:
            raise ValueError("a registered colormap needs a name")
        if cmap_name in _CMAP_DATA and not force:
            raise ValueError(f"colormap {cmap_name!r} is already registered")
        _register_custom_cmap(cmap)
        return cmap


colormaps = _ColormapRegistry()


class _CmapNamespace:
    """The `plt.cm` namespace, exposing one attribute per colormap."""

    def get_cmap(self, name=None, lut=None):
        return get_cmap(name, lut)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name == "colors":
            # `matplotlib.cm` re-exports the colors module; `cm.colors.Normalize`
            # is a common way to build a norm.
            return mcolors
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


def _validate_share(value, name):
    """Validate Matplotlib's share flags before building limit groups."""
    if value in (False, None, "none"):
        return False
    if value in (True, "all", "row", "col"):
        return value
    raise ValueError(
        f"{value!r} is not a valid value for {name}. "
        "Supported values are 'all', 'row', 'col', 'none', False, True")


def _share_axes(axs, shape, sharex, sharey):
    """Join axes into limit groups and hide duplicate inner tick labels."""
    sharex = _validate_share(sharex, "sharex")
    sharey = _validate_share(sharey, "sharey")
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
    """`axes.prop_cycle`: iterating yields `{"color": ...}` entries, as Cycler."""

    def __init__(self, colors):
        super().__init__({"color": c} for c in colors)

    def by_key(self): return {"color": [entry["color"] for entry in self]}
    def __call__(self): return iter(self)


def cycler(*args, **kwargs):
    """Build a colour property cycle, as `matplotlib.cycler`."""
    if len(args) == 2:
        kwargs = {**kwargs, args[0]: args[1]}
    elif len(args) == 1:
        source = args[0]
        if isinstance(source, _CycleList):
            colors = [entry.get("color") for entry in source
                      if isinstance(entry, dict) and entry.get("color") is not None]
            return _CycleList(colors)
        if hasattr(source, "by_key"):
            return _CycleList(source.by_key().get("color", []))
        if isinstance(source, dict):
            return _CycleList(source.get("color", []))
        raise TypeError("cycler needs pairs of property names and values")
    elif args:
        raise TypeError("cycler needs pairs of property names and values")
    colors = kwargs.get("color", ())
    return _CycleList(list(colors) if not isinstance(colors, str) else [colors])


def _cycle_colors(value):
    """Plain colour list from a Cycler, a dict or a list of either."""
    if value is None:
        return []
    if hasattr(value, "by_key"):
        return list(value.by_key().get("color", ()))
    if isinstance(value, dict):
        return list(value.get("color", ()))
    colors = []
    for item in value:
        if isinstance(item, dict):
            if item.get("color") is not None:
                colors.append(item["color"])
        else:
            colors.append(item)
    return colors


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
    def clear(self): return self


class Affine2D:
    """No-op affine transform accepted by annotation and locator helpers."""

    def __init__(self, *args, **kwargs): pass
    def transform(self, points): _ignored("Affine2D.transform"); return np.asarray(points, dtype=np.float64)
    def rotate_around(self, x, y, theta): _ignored("Affine2D.rotate_around"); return self
    def inverted(self): return self
    def __add__(self, other): return self
    def __radd__(self, other): return self
    def translate(self, *args, **kwargs): _ignored("Affine2D.translate"); return self
    def rotate_deg(self, *args, **kwargs): _ignored("Affine2D.rotate_deg"); return self
    def scale(self, *args, **kwargs): _ignored("Affine2D.scale"); return self
    def skew_deg(self, *args, **kwargs): _ignored("Affine2D.skew_deg"); return self
    def clear(self): return self
    def get_matrix(self): return np.eye(3)


class Path:
    """Minimal path container used by `PathPatch`."""

    STOP = 0
    MOVETO = 1
    LINETO = 2
    CURVE3 = 3
    CURVE4 = 4
    CLOSEPOLY = 79
    NUM_VERTICES_FOR_CODE: ClassVar[dict[int, int]] = {
        STOP: 1, MOVETO: 1, LINETO: 1, CURVE3: 2, CURVE4: 3, CLOSEPOLY: 1}

    def __init__(self, vertices, codes=None, **kwargs):
        self.vertices = np.asarray(vertices, dtype=float).reshape(-1, 2)
        self.codes = codes

    def get_vertices(self): return self.vertices
    def get_codes(self): return self.codes
    def transformed(self, transform): _ignored("Path.transformed"); return self
    def deepcopy(self): return copy.deepcopy(self)
    def cleaned(self, transform=None, simplify=False, **kwargs): return self
    def clip_to_bbox(self, bbox, inside=True): return self
    def __iter__(self): return iter((self.vertices, self.codes))

    def get_extents(self, transform=None, **kwargs):
        if len(self.vertices) == 0:
            return _Bbox(0.0, 0.0, 0.0, 0.0)
        return _Bbox(self.vertices[:, 0].min(), self.vertices[:, 1].min(),
                     self.vertices[:, 0].max(), self.vertices[:, 1].max())

    def to_polygons(self, transform=None, **kwargs):
        if len(self.vertices) == 0:
            return []
        return [np.asarray(self.vertices, dtype=float)]

    def intersects_bbox(self, bbox, filled=True):
        """Whether any segment of the path touches `bbox`."""
        points = self.vertices
        if len(points) == 0:
            return False
        for x, y in points:
            if bbox.contains(x, y):
                return True
        for start, end in zip(points[:-1], points[1:]):
            if _segment_intersects_bbox(start, end, bbox):
                return True
        return False

    @classmethod
    def unit_rectangle(cls):
        vertices = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0],
                             [0.0, 1.0], [0.0, 0.0]], dtype=float)
        codes = np.array([cls.MOVETO, cls.LINETO, cls.LINETO, cls.LINETO,
                          cls.CLOSEPOLY], dtype=np.uint8)
        return cls(vertices, codes)

    @classmethod
    def make_compound_path(cls, *paths):
        if not paths:
            return cls(np.empty((0, 2)), np.empty(0, dtype=np.uint8))
        vertices, codes = [], []
        for path in paths:
            points = np.asarray(getattr(path, "vertices", path), dtype=float).reshape(-1, 2)
            vertices.append(points)
            path_codes = getattr(path, "codes", None)
            if path_codes is None:
                path_codes = np.full(len(points), cls.LINETO, dtype=np.uint8)
                if len(path_codes):
                    path_codes[0] = cls.MOVETO
            codes.append(np.asarray(path_codes, dtype=np.uint8))
        return cls(np.vstack(vertices), np.concatenate(codes))

    @classmethod
    def make_compound_path_from_polys(cls, XY):
        """Build a compound path from an array of polygons, `(n, sides, 2)`."""
        polys = np.asarray(XY, dtype=float)
        if polys.ndim != 3 or polys.shape[2] != 2:
            raise ValueError("XY must have shape (n, sides, 2)")
        vertices, codes = [], []
        for poly in polys:
            vertices.extend(poly)
            vertices.append((0.0, 0.0))
            codes.extend([cls.MOVETO] + [cls.LINETO] * (len(poly) - 1)
                         + [cls.CLOSEPOLY])
        return cls(np.asarray(vertices, dtype=float),
                   np.asarray(codes, dtype=np.uint8))

    def __copy__(self):
        clone = object.__new__(type(self))
        clone.__dict__.update(self.__dict__)
        return clone

    def __deepcopy__(self, memo):
        clone = object.__new__(type(self))
        memo[id(self)] = clone
        for key, value in self.__dict__.items():
            clone.__dict__[key] = copy.deepcopy(value, memo)
        return clone

    @classmethod
    def unit_regular_polygon(cls, numVertices):
        n = int(numVertices)
        angles = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False) + np.pi / 2.0
        vertices = np.column_stack([np.cos(angles), np.sin(angles)])
        codes = np.full(n, cls.LINETO, dtype=np.uint8)
        codes[0] = cls.MOVETO
        codes[-1] = cls.CLOSEPOLY
        return cls(vertices, codes)

    @classmethod
    def unit_circle(cls):
        angles = np.linspace(0.0, 2.0 * np.pi, 65)
        vertices = np.column_stack([np.cos(angles), np.sin(angles)])
        codes = np.full(vertices.shape[0], cls.LINETO, dtype=np.uint8)
        codes[0] = cls.MOVETO
        codes[-1] = cls.CLOSEPOLY
        return cls(vertices, codes)

    @classmethod
    def unit_regular_star(cls, numVertices, innerCircle=0.5):
        n = int(numVertices)
        angles = np.linspace(0.0, 2.0 * np.pi, 2 * n, endpoint=False) + np.pi / 2.0
        radii = np.empty(2 * n)
        radii[0::2] = 1.0
        radii[1::2] = float(innerCircle)
        vertices = np.column_stack([radii * np.cos(angles), radii * np.sin(angles)])
        codes = np.full(2 * n, cls.LINETO, dtype=np.uint8)
        codes[0] = cls.MOVETO
        codes[-1] = cls.CLOSEPOLY
        return cls(vertices, codes)


class TransformedPath:
    """Path plus the transform that produced it."""

    def __init__(self, path, transform):
        self._path = path
        self._transform = transform

    def get_path(self): return self._path
    def get_fully_transformed_path(self): return self._path


class TextPath(Path):
    """Outline path for a text string.

    A full font-outline engine is out of scope for the dependency-free wheel,
    so the path is a proportional block silhouette covering the string.  It is
    a real `Path`, so `PathPatch`, markers, clipping and transforms all work.
    """

    def __init__(self, xy, s, size=None, prop=None, usetex=False, **kwargs):
        s = str(s)
        fontsize = size
        if fontsize is None and prop is not None:
            fontsize = getattr(prop, "get_size_in_points", lambda: 10)()
        fontsize = 10.0 if fontsize is None else float(fontsize)
        advance = 0.62 * fontsize
        width = max(advance * max(len(s), 1), advance)
        height = 0.75 * fontsize
        x, y = float(xy[0]), float(xy[1])
        # A shallow stepped top edge keeps the silhouette readable as text in
        # the gallery rather than looking like an unrelated filled rectangle.
        verts = [(x, y), (x + width, y), (x + width, y + height)]
        chars = max(len(s), 1)
        for i in range(chars, 0, -1):
            top = y + (height if i % 2 else 0.86 * height)
            verts.append((x + width * i / chars, top))
            verts.append((x + width * (i - 1) / chars, top))
        verts.append((x, y))
        codes = np.full(len(verts), Path.LINETO, dtype=np.uint8)
        codes[0] = Path.MOVETO
        codes[-1] = Path.CLOSEPOLY
        super().__init__(verts, codes)
        self._xy = (x, y)
        self._s = s
        self._size = fontsize
        self._usetex = bool(usetex)

    def get_text(self): return self._s
    def get_size(self): return self._size
    def get_extents(self, transform=None, **kwargs):
        return _Bbox(self.vertices[:, 0].min(), self.vertices[:, 1].min(),
                     self.vertices[:, 0].max(), self.vertices[:, 1].max())


class _Bbox:
    """Minimal Bbox with the attribute names matplotlib tests reach for."""

    def __init__(self, x0=0.0, y0=0.0, x1=None, y1=None):
        if x1 is None and y1 is None and not np.isscalar(x0):
            points = np.asarray(x0, dtype=float).reshape(-1, 2)
            x0, y0 = points[:, 0].min(), points[:, 1].min()
            x1, y1 = points[:, 0].max(), points[:, 1].max()
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
    def __len__(self): return 4
    def frozen(self): return _Bbox(self.x0, self.y0, self.x1, self.y1)
    def set(self, other):
        if hasattr(other, "x0"):
            self.x0, self.y0 = float(other.x0), float(other.y0)
            self.x1, self.y1 = float(other.x1), float(other.y1)
        else:
            self.x0, self.y0, self.x1, self.y1 = (float(v) for v in other)
        return self
    def __iter__(self): return iter(self.bounds)
    def __getitem__(self, index): return self.bounds[index]

    def __repr__(self):
        return f"Bbox({self.x0:g}, {self.y0:g}, {self.x1:g}, {self.y1:g})"


Bbox = _Bbox


class _Transform:
    """Stand-in for a matplotlib transform: data coordinates pass through."""

    def __init__(self, *args, **kwargs):
        self._args, self._kwargs = args, kwargs

    linthresh = 1.0
    linscale = 1.0

    def transform(self, points): return np.asarray(points, dtype=np.float64)
    def transform_path(self, path): return path

    def __add__(self, other): return self
    def __radd__(self, other): return self
    def translate(self, *args, **kwargs): return self
    def rotate_deg(self, *args, **kwargs): return self
    def scale(self, *args, **kwargs): return self
    def inverted(self): return self


class _IdentityTransform(_Transform):
    """Pixels from the figure's lower-left; used by `Figure.text`."""

    kind = "identity"


class _BboxPatch:
    """Stand-in for the optional patch behind a text annotation."""

    def set_path_effects(self, effects):
        _ignored("Patch.set_path_effects")
        return self


class _TextEntry(tuple):
    """Stored text record with the accessors Matplotlib text artists expose."""

    def get_position(self): return (self[0], self[1])
    def get_text(self): return self[2]
    def get_color(self): return self[3]
    def get_fontsize(self): return self[4]
    def get_ha(self): return self[5]
    def get_va(self): return self[6]
    def get_bbox(self): return self[8]
    def get_rotation(self): return self[9]


class _FigureImage:
    """Handle returned by `Figure.figimage`."""

    def __init__(self, entry):
        self._e = entry

    def get_array(self): return self._e["data"]
    def get_alpha(self): return self._e["alpha"]
    def set_alpha(self, alpha):
        self._e["alpha"] = float(np.clip(float(alpha), 0.0, 1.0))
        return self


def _segment_intersects_bbox(start, end, bbox):
    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    dx, dy = x1 - x0, y1 - y0
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, x0 - bbox.x0), (dx, bbox.x1 - x0),
                 (-dy, y0 - bbox.y0), (dy, bbox.y1 - y0)):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        t = q / p
        if p < 0.0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
        if lo > hi:
            return False
    return True


class _TextArt:
    """Return value for text creation; carries the mutable bbox patch."""

    def __init__(self, text=""):
        self._bbox_patch = _BboxPatch()
        self._text = str(text)

    def get_text(self): return self._text
    def set_text(self, text): self._text = str(text); return self

    def set_path_effects(self, effects):
        _ignored("Text.set_path_effects")
        return self

    def set_bbox(self, bbox):
        self._bbox = bbox
        return self

    def set_color(self, color): self._color = color; return self
    def get_color(self): return getattr(self, "_color", "black")
    def set_fontsize(self, size): self._fontsize = size; return self
    def get_fontsize(self): return getattr(self, "_fontsize", 10)
    def set_fontweight(self, weight): self._fontweight = weight; return self
    def set_fontstyle(self, style): self._fontstyle = style; return self
    def set_fontfamily(self, family): self._fontfamily = family; return self
    def set_fontfeatures(self, features): self._fontfeatures = features; return self
    def set_language(self, language): self._language = language; return self
    def set_ha(self, value): self._ha = value; return self
    set_horizontalalignment = set_ha
    def set_va(self, value): self._va = value; return self
    set_verticalalignment = set_va
    def set_zorder(self, zorder): self._zorder = int(zorder); return self
    def get_zorder(self): return getattr(self, "_zorder", 3)

    def get_bbox_patch(self): return self._bbox_patch
    def contains(self, mouseevent=None): return False, {}
    def draggable(self, *args, **kwargs): return None
    def get_window_extent(self, renderer=None):
        return _Bbox(0.0, 0.0, 1.0, 1.0)


class _TableCell:
    """A text artist plus the geometry the table API exposes for a cell."""

    def __init__(self, art):
        self._art = art

    def get_text(self): return self._art.get_text()
    def set_text(self, text): self._art.set_text(text); return self

    def set_text_props(self, **kwargs):
        if "color" in kwargs:
            self._art.set_color(kwargs["color"])
        if "fontsize" in kwargs:
            self._art.set_fontsize(kwargs["fontsize"])
        return self

    def get_visible(self): return getattr(self, "_visible", True)
    def set_visible(self, visible): self._visible = bool(visible); return self
    def get_facecolor(self): return getattr(self, "_facecolor", "none")
    def set_facecolor(self, color): self._facecolor = color; return self
    def get_edgecolor(self): return "black"
    def get_linewidth(self): return 0.8


class Table:
    """A lightweight table drawn with axes-fraction text cells."""

    def __init__(self, ax, cellText=None, cellColours=None, cellLoc="right",
                 colWidths=None, rowLabels=None, rowColours=None, rowLoc="left",
                 colLabels=None, colColours=None, colLoc="center", loc="bottom",
                 bbox=None, edges="closed", **kwargs):
        rows = [list(row) for row in (cellText or [])]
        nrows = len(rows)
        ncols = max((len(row) for row in rows), default=0)
        row_labels = [] if rowLabels is None else list(rowLabels)
        col_labels = [] if colLabels is None else list(colLabels)
        label_rows = 1 if col_labels else 0
        label_cols = 1 if row_labels else 0
        total_rows, total_cols = nrows + label_rows, ncols + label_cols
        if total_rows == 0 or total_cols == 0:
            raise ValueError("table needs at least one cell or label")
        if bbox is None:
            if str(loc).startswith("bottom"):
                bbox = (0.0, -0.35, 1.0, 0.30)
            elif str(loc).startswith("upper"):
                bbox = (0.0, 0.65, 1.0, 0.30)
            else:
                bbox = (0.0, 0.0, 1.0, 1.0)
        x0, y0, width, height = (float(v) for v in bbox)
        cell_w, cell_h = width / total_cols, height / total_rows
        fontsize = float(kwargs.get("fontsize", 8.0))
        self._cells = {}
        for row in range(total_rows):
            for col in range(total_cols):
                value, face, align = "", None, cellLoc
                if row < label_rows:
                    if col >= label_cols and col_labels:
                        value, align = str(col_labels[col - label_cols]), colLoc
                        if colColours is not None and (col - label_cols) < len(colColours):
                            face = colColours[col - label_cols]
                    else:
                        align = rowLoc
                elif col < label_cols:
                    if row_labels:
                        value, align = str(row_labels[row - label_rows]), rowLoc
                        if rowColours is not None and (row - label_rows) < len(rowColours):
                            face = rowColours[row - label_rows]
                else:
                    r, c = row - label_rows, col - label_cols
                    if r < len(rows) and c < len(rows[r]):
                        value = rows[r][c]
                    if cellColours is not None and r < len(cellColours):
                        colors = cellColours[r]
                        if c < len(colors):
                            face = colors[c]
                x = x0 + (col + 0.5) * cell_w
                y = y0 + (total_rows - row - 0.5) * cell_h
                box = dict(boxstyle="square,pad=0", facecolor=face if face is not None else "none",
                           edgecolor="black" if edges != "open" else "none",
                           linewidth=0.8)
                art = ax.text(x, y, value, transform=ax.transAxes,
                              ha=align, va="center", fontsize=fontsize, bbox=box)
                self._cells[(row - label_rows, col - label_cols)] = _TableCell(art)

    def get_celld(self): return dict(self._cells)
    def get_cell(self, row, col): return self._cells[(row, col)]
    def auto_set_font_size(self, *args, **kwargs): return None
    def auto_set_column_width(self, *args, **kwargs): return None
    def set_fontsize(self, size):
        for cell in self._cells.values():
            cell._art.set_fontsize(size)


class OffsetFrom:
    """Text offset anchored to another artist's bbox; only the values are kept."""

    def __init__(self, artist, ref_coord, unit="points"):
        self.artist, self.ref_coord, self.unit = artist, ref_coord, unit


class Text(_TextArt):
    """Constructible text artist used by code that imports `matplotlib.text`."""

    def __init__(self, x=0, y=0, text="", **kwargs):
        super().__init__()
        self._x, self._y, self._text = x, y, str(text)
        self._axes = kwargs.get("axes")

    def get_text(self): return self._text
    def set_text(self, text): self._text = str(text); return self
    def get_position(self): return (self._x, self._y)
    def set_position(self, xy): self._x, self._y = xy; return self
    def set_figure(self, figure): return self
    def set_transform(self, transform): return self
    def draw(self, renderer): return None


class _TextLabel:
    """Minimal tick-label stand-in for code that pokes at Text objects."""

    def __init__(self, text="", fontsize=10.0):
        self._text, self._visible, self._fontsize = str(text), True, float(fontsize)
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
    set_horizontalalignment = set_ha
    def set_va(self, value): _ignored("Text.set_va")
    set_verticalalignment = set_va
    def set_axis_direction(self, value): _ignored("Text.set_axis_direction")
    def set_pad(self, value): self._pad = float(value)
    def get_pad(self): return getattr(self, "_pad", 4.0)
    def set_tick_out(self, value): self._tick_out = bool(value)
    def set_tick_direction(self, value): self._tick_direction = str(value)
    def set_axisline_style(self, value, **kwargs): self._line_style = value
    def set_picker(self, value): self._picker = value; return self
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


def _update_extent(ext, values):
    """Update running (min, max) extent without flattening arrays into Python lists.

    Performance: Direct NumPy min/max avoids allocating large Python lists and
    copying elements into Python float objects for dense plots.
    """
    if values is None:
        return ext
    if isinstance(values, (int, float, np.number)):
        v = float(values)
        if _math.isfinite(v):
            return (min(ext[0], v), max(ext[1], v))
        return ext
    if isinstance(values, np.ndarray) and values.dtype.kind == "f" and values.ndim == 1:
        arr = values
    else:
        arr = np.asarray(values, dtype=float).ravel()
    if arr.size:
        fin = arr[np.isfinite(arr)]
        if fin.size:
            return (min(ext[0], float(fin.min())), max(ext[1], float(fin.max())))
    return ext


def _span_extent(ext):
    """Convert an accumulated (min, max) extent to non-degenerate span."""
    lo, hi = ext
    if lo > hi:
        return (0.0, 1.0)
    return (lo, hi) if lo < hi else (lo - 1.0, lo + 1.0)


def _span(values):
    """A flat series is widened so its extent is never degenerate.

    `Axes.get_xlim`/`get_ylim` add Matplotlib's autoscale margin on top of this.
    """
    ext = _update_extent((float("inf"), float("-inf")), values)
    return _span_extent(ext)


def _as_list(values):
    """Materialise dict views and other one-shot iterables as a list."""
    if isinstance(values, (str, bytes)) or np.isscalar(values):
        return values
    if hasattr(values, "__array__") and not isinstance(values, np.ndarray):
        return values
    if hasattr(values, "__iter__") and not isinstance(
            values, (list, tuple, np.ndarray, range)):
        try:
            return list(values)
        except TypeError:
            return values
    return values


def _looks_like_categories(values):
    """True for string scalars or sequences, which matplotlib treats as categories."""
    if isinstance(values, str):
        return True
    values = _as_list(values)
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


def _format_ticklabels(formatter, ticks):
    """Labels from a major formatter, or None when it cannot be used here."""
    if formatter is None or ticks is None:
        return None
    labels = []
    for pos, value in enumerate(ticks):
        if isinstance(formatter, str):
            try:
                label = formatter.format(x=float(value), pos=pos)
            except (KeyError, IndexError, ValueError):
                label = formatter
        else:
            try:
                label = formatter(float(value), pos)
            except TypeError:
                label = formatter(float(value))
        labels.append(str(label))
    return labels


def _scale_transform_pair(scale):
    """Forward and inverse callables from a Matplotlib-style scale object."""
    transform = scale.get_transform()
    forward = getattr(transform, "transform_non_affine", None)
    if forward is None:
        forward = getattr(transform, "transform", None)
    inverted = transform.inverted()
    inverse = getattr(inverted, "transform_non_affine", None)
    if inverse is None:
        inverse = getattr(inverted, "transform", None)
    if forward is None or inverse is None:
        raise TypeError("a scale transform must provide transform and inverted")
    return forward, inverse


def _scale_values(forward, values):
    """Apply a scale transform, turning masked/non-finite results into gaps."""
    array = np.asarray(values, dtype=np.float64)
    result = np.ma.filled(np.ma.asarray(forward(array), dtype=np.float64), np.nan)
    return np.ascontiguousarray(result, dtype=np.float64)


def _add_months(value, months):
    total = value.year * 12 + (value.month - 1) + int(months)
    year, month = divmod(total, 12)
    month += 1
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    last_day = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return value.replace(year=year, month=month, day=min(value.day, last_day))


def _symlog_label(value):
    return f"{value:g}".replace("-", "\u2212")


def _logit_ticks(lo, hi, one_half="1/2", use_overline=False):
    """Ticks at powers of ten in odds, symmetric around probability 0.5."""
    lo = max(float(lo), 1e-9)
    hi = min(float(hi), 1.0 - 1e-9)
    candidates = {0.5}
    for k in range(1, 10):
        candidates.add(10.0 ** -k)
        candidates.add(1.0 - 10.0 ** -k)
    ticks = sorted(v for v in candidates if lo <= v <= hi)
    if not ticks:
        ticks = sorted({lo, hi})
    labels = []
    for value in ticks:
        if abs(value - 0.5) < 1e-12:
            labels.append(str(one_half))
        elif value < 0.5:
            k = max(1, int(round(-_math.log10(value))))
            labels.append("10\u207b" + str(k).translate(_SUPERSCRIPTS))
        else:
            k = max(1, int(round(-_math.log10(max(1.0 - value, 1e-12)))))
            labels.append("1\u221210\u207b" + str(k).translate(_SUPERSCRIPTS))
    return ticks, labels


def _symlog_ticks(lo, hi, linthresh):
    """Decade ticks on both sides of `linthresh`, plus zero."""
    l = max(float(linthresh), 1e-300)
    top = max(0, int(_math.floor(_math.log10(max(abs(float(lo)), abs(float(hi)), l) / l))))
    stride = max(1, int(_math.ceil((top + 1) / 5.0)))
    ticks = [0.0]
    for sign in (1.0, -1.0):
        for k in range(0, top + 1, stride):
            value = sign * l * 10.0 ** k
            if lo <= value <= hi:
                ticks.append(value)
    ticks = sorted({float(v) for v in ticks})
    return ticks, [_symlog_label(v) for v in ticks]


def _nice_step(raw, steps):
    for step in steps:
        if step >= raw:
            return step
    return steps[-1] * max(1, int(_math.ceil(raw / steps[-1])))


def _auto_ticks(lo, hi, log=False, base=10.0, target=8):
    """Ticks for an axis with none set, computed by the Rust locator."""
    return _auto_ticks_core(float(lo), float(hi), bool(log), float(base), int(target))


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
_FORMATS = ("png", "svg", "pdf", "webp", "eps")
_COMPRESSIONS = ("fast", "default", "best")
_MAX_CANVAS_DIM = 32768
_MAX_CANVAS_AREA = 67108864  # 2^26 pixels (~256 MiB RGBA raw buffer limit)
# Figure-level images are embedded in the SVG as base64 PNGs, so they need
# their own size and payload budgets instead of only the canvas budget.
_MAX_FIGIMAGE_DIM = 16384
_MAX_FIGIMAGE_PIXELS = 67108864
_MAX_FIGIMAGE_BYTES = 64 * 1024 * 1024
_MAX_BINS = 4096
_MAX_BIN_CELLS = 4_000_000
_MAX_EDGES = 100_000
_MAX_GRID_CELLS = 10_000


def _validate_grid_shape(nrows, ncols):
    """Reject grids that would allocate one Python object per requested cell."""
    def positive(value, label):
        if (isinstance(value, bool)
                or not isinstance(value, (int, np.integer))):
            raise ValueError(
                f"Number of {label} must be a positive integer, not {value!r}")
        value = int(value)
        if value <= 0:
            raise ValueError(
                f"Number of {label} must be a positive integer, not {value!r}")
        return value

    rows, cols = positive(nrows, "rows"), positive(ncols, "columns")
    cells = rows * cols
    if cells > _MAX_GRID_CELLS:
        raise ValueError(f"grid has too many cells ({cells} > {_MAX_GRID_CELLS})")
    return rows, cols


def _apply_axes_options(ax, options, grid_helper=None):
    """Apply `add_subplot`/`add_axes` options used by axisartist examples."""
    if grid_helper is not None:
        ax._grid_helper = grid_helper
        if hasattr(grid_helper, "apply"):
            grid_helper.apply(ax)
    if "aspect" in options:
        ax.set_aspect(options["aspect"])
    for key in ("xlim", "ylim"):
        if key not in options:
            continue
        value = options[key]
        try:
            getattr(ax, "set_" + key)(*value)
        except TypeError:
            getattr(ax, "set_" + key)(value)
    if "label" in options:
        ax.set_label(options["label"])
    return ax


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
        raise ValueError(
            f"unsupported format: {fmt!r} (use 'png', 'svg', 'pdf', 'webp', or 'eps')"
        )
    return fmt


_LEGEND_LOCATIONS = frozenset({
    "best", "upper right", "upper left", "lower left", "lower right", "right",
    "center left", "center right", "lower center", "upper center", "center",
})
_LEGEND_LOCATION_CODES = {
    0: "best", 1: "upper right", 2: "upper left", 3: "lower left",
    4: "lower right", 5: "right", 6: "center left", 7: "center right",
    8: "lower center", 9: "upper center", 10: "center",
}


def _normalize_legend_loc(loc):
    """Validate a legend location, accepting Matplotlib's integer codes."""
    if loc is None:
        return None
    if isinstance(loc, str):
        if loc not in _LEGEND_LOCATIONS:
            raise ValueError(f"{loc!r} is not a valid value for loc.")
        return loc
    if isinstance(loc, (int, np.integer)) and not isinstance(loc, bool):
        code = int(loc)
        if 0 <= code <= 10:
            return _LEGEND_LOCATION_CODES[code]
        raise ValueError(
            f"loc must be string, coordinate tuple, or an integer 0-10, not {loc!r}")
    raise ValueError(
        f"loc must be string, coordinate tuple, or an integer 0-10, not {loc!r}")


def _validate_linestyle(style):
    """Reject line-style strings the renderer cannot draw."""
    if not isinstance(style, str):
        raise NotImplementedError("custom dash patterns are not supported")
    text = style.strip()
    if not text:
        return "None"
    normalized = text.lower()
    aliases = {"solid": "-", "dashed": "--", "dashdot": "-.", "dotted": ":"}
    if normalized in aliases:
        return aliases[normalized]
    if normalized in ("-", "--", "-.", ":", "none"):
        return "None" if normalized == "none" else normalized
    raise ValueError(f"{style!r} is not a valid value for ls.")


def _validate_savefig_mapping(value, name):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict, got {type(value).__name__}")
    return dict(value)


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
    def set_zorder(self, zorder): self._zorder = zorder
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
    def __init__(self, **kwargs): self.kwargs = kwargs


class _PieResult:
    """Matplotlib's PieResult: unpackable and attribute-accessible."""

    def __init__(self, wedges, texts, autotexts):
        self.wedges, self.texts, self.autotexts = wedges, texts, autotexts

    def __iter__(self): return iter((self.wedges, self.texts, self.autotexts))


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


class _LineGroupHandle(list):
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


class _BarContainer(list):
    """List of `_BarHandle`, matching matplotlib's `BarContainer`."""

    __hash__ = object.__hash__

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
        self._e["sizes"] = np.ascontiguousarray(np.asarray(sizes, dtype=np.float64).ravel())
        return self

    def set_markerfacecolor(self, color):
        self._e["colors"] = [_norm_color(color)]
        return self

    set_facecolor = set_markerfacecolor

    def set_markeredgecolor(self, color):
        _ignored("PathCollection.set_markeredgecolor")
        return self

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
        vals = np.asarray(values, dtype=float).ravel()
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
        vals = np.asarray(values, dtype=float).ravel()
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

    def set_edgecolor(self, color):
        _ignored("ViolinBody.set_edgecolor")
        return self

    def set_linewidth(self, width):
        _ignored("ViolinBody.set_linewidth")
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
    base = float(rcParams.get("font.size", 10.0))
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


class _StickyEdges:
    def __init__(self): self.x, self.y = [], []


class Patch:
    """Base class for matplotlib-style patches accepted by `add_patch`."""

    def __init__(self, **kwargs):
        self.sticky_edges = _StickyEdges()
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
        self._gid = str(kwargs.pop("gid", "") or "")
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
    def get_gid(self): return self._gid
    def set_gid(self, gid):
        self._gid = "" if gid is None else str(gid)
        return self
    def get_visible(self): return self._visible
    def get_zorder(self): return self._zorder
    def get_fill(self): return self._fill
    def get_hatch(self): return self._hatch
    def get_transform(self): return self._transform or _Transform()
    def get_path(self):
        if hasattr(self, "_path"):
            return self._path
        if hasattr(self, "_xy"):
            return Path(self._xy)
        if hasattr(self, "_x"):
            x, y = self._x, self._y
            w, h = self._width, self._height
            return Path([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)])
        return Path(np.empty((0, 2)))
    def add_callback(self, func, *args, **kwargs): return 1
    def remove_callback(self, func): return None
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

    def set(self, **kwargs):
        """Apply Matplotlib artist properties by name, as `patch.set(color=...)`."""
        setters = {
            "color": self.set_color,
            "facecolor": self.set_facecolor,
            "fc": self.set_facecolor,
            "edgecolor": self.set_edgecolor,
            "ec": self.set_edgecolor,
            "linewidth": self.set_linewidth,
            "lw": self.set_linewidth,
            "linestyle": self.set_linestyle,
            "ls": self.set_linestyle,
            "alpha": self.set_alpha,
            "label": self.set_label,
            "visible": self.set_visible,
            "zorder": self.set_zorder,
            "fill": self.set_fill,
            "hatch": self.set_hatch,
        }
        for key, value in kwargs.items():
            setter = setters.get(key)
            if setter is None:
                _ignored(f"Patch.set({key})")
            else:
                setter(value)
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
    def set_animated(self, value): self._animated = bool(value); return self
    def get_animated(self): return getattr(self, "_animated", False)
    def set_picker(self, value): self._picker = value; return self
    def set_antialiased(self, value): return None
    def set_antialiaseds(self, value): return None
    def set_joinstyle(self, value): return None
    def set_capstyle(self, value): return None
    def set_rasterized(self, value): return None
    def set_agg_filter(self, value): return None
    def set_url(self, value): return None
    def set_sketch_params(self, *args, **kwargs): return None
    def set_snap(self, value): return None
    def set_in_layout(self, value): return None
    def remove(self): self._visible = False
    def get_window_extent(self, renderer=None): return _Bbox(0, 0, 1, 1)
    def contains(self, mouseevent=None): return False, {}
    def draw(self, renderer=None): return None

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
    def set_bounds(self, *args):
        if len(args) == 1:
            x, y, width, height = args[0]
        elif len(args) == 4:
            x, y, width, height = args
        else:
            raise TypeError("set_bounds needs (x, y, width, height)")
        self._x, self._y = float(x), float(y)
        self._width, self._height = float(width), float(height)
        return self
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


class CirclePolygon(Circle):
    """Circle-compatible polygon used by Matplotlib's patch examples."""

    def __init__(self, xy, radius=5, resolution=20, **kwargs):
        super().__init__(xy, radius=radius, **kwargs)
        self.resolution = int(resolution)


class Ellipse(Patch):
    def __init__(self, xy, width, height, angle=0.0, **kwargs):
        super().__init__(**kwargs)
        self._center = (float(_as_f64(xy[0])[0]), float(_as_f64(xy[1])[0]))
        self._width = float(_as_f64(width)[0])
        self._height = float(_as_f64(height)[0])
        self.angle = float(angle)

    def get_center(self): return self._center
    def get_width(self): return self._width
    def get_height(self): return self._height
    def get_angle(self): return self.angle
    def set_center(self, xy): self._center = (float(xy[0]), float(xy[1]))
    def set_width(self, width): self._width = float(width)
    def set_height(self, height): self._height = float(height)
    def set_angle(self, angle): self.angle = float(angle)

    def get_co_vertices(self):
        """The two rotated minor-axis endpoints, as Matplotlib exposes them."""
        a = np.deg2rad(self.angle)
        dx = 0.5 * self._width * np.cos(a)
        dy = 0.5 * self._width * np.sin(a)
        return [(self._center[0] - dx, self._center[1] - dy),
                (self._center[0] + dx, self._center[1] + dy)]

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

    @property
    def xy(self): return self._xy

    @xy.setter
    def xy(self, value): self.set_xy(value)


class Arc(Patch):
    def __init__(self, xy, width, height, angle=0.0, theta1=0.0, theta2=360.0, **kwargs):
        kwargs.setdefault("fill", False)
        kwargs.setdefault("facecolor", "none")
        super().__init__(**kwargs)
        self._center = (float(_as_f64(xy[0])[0]), float(_as_f64(xy[1])[0]))
        self._width = float(_as_f64(width)[0])
        self._height = float(_as_f64(height)[0])
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

    def set_boxstyle(self, boxstyle=None, **kwargs):
        self.boxstyle = boxstyle or self.boxstyle
        return self


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
        self._r = max(float(v) for v in np.asarray(r, dtype=float).ravel())
        self._semiminor = None
        self._width = max(float(v) for v in np.asarray(width, dtype=float).ravel())
        self.angle = float(angle)

    @property
    def center(self): return self._center

    @center.setter
    def center(self, value): self._center = (float(value[0]), float(value[1]))

    @property
    def width(self): return self._width

    @width.setter
    def width(self, value): self._width = float(value)

    def set_semimajor(self, value):
        self._r = float(value)
        return self

    def set_semiminor(self, value):
        self._semiminor = float(value)
        return self

    def get_xy(self):
        t = np.linspace(0.0, 2.0 * np.pi, 97)
        ry = self._r if self._semiminor is None else self._semiminor
        outer = np.column_stack([self._center[0] + self._r * np.cos(t),
                                 self._center[1] + ry * np.sin(t)])
        inner = np.column_stack([self._center[0] + (self._r - self._width) * np.cos(t),
                                 self._center[1] + (ry - self._width) * np.sin(t)])
        return np.vstack([outer, inner[::-1]])


class StepPatch(Patch):
    """Filled step outline from bin values and edges."""

    def __init__(self, values, edges, orientation="vertical", baseline=0.0, **kwargs):
        super().__init__(**kwargs)
        self._values = np.asarray(values, dtype=float).ravel()
        self._edges = np.asarray(edges, dtype=float).ravel()
        if self._edges.size != self._values.size + 1:
            raise ValueError("edges must have len(values) + 1 entries")
        self._orientation, self._baseline = str(orientation), float(baseline)

    def get_xy(self):
        points = [(self._edges[0], self._baseline)]
        for index, value in enumerate(self._values):
            points.extend([(self._edges[index], value),
                           (self._edges[index + 1], value)])
        points.append((self._edges[-1], self._baseline))
        out = np.asarray(points, dtype=float)
        return out if self._orientation == "vertical" else out[:, ::-1]


class _PatchesNamespace:
    pass


patches = _PatchesNamespace()
for _patch_name in ("Patch", "Rectangle", "Circle", "CirclePolygon", "Ellipse", "Polygon", "Arc",
                    "Wedge", "RegularPolygon", "FancyArrow", "FancyArrowPatch",
                    "FancyBboxPatch", "PathPatch", "Annulus", "StepPatch"):
    setattr(patches, _patch_name, globals()[_patch_name])


class _FlexibleStyleNamespace:
    def __call__(self, name="", **kwargs):
        """`BoxStyle("Round", pad=...)` returns an inert style object."""
        return self.__getattr__(str(name) or "Style")(**kwargs)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        _ignored(f"patches.{name}")
        return type(name, (), {"__init__": lambda self, *args, **kwargs: None})

    def get_styles(self):
        return {name: type(name, (), {"__init__": lambda self, *args, **kwargs: None})
                for name in ("circle", "darrow", "larrow", "rarrow", "round",
                             "round4", "roundtooth", "sawtooth", "square")}


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
    # `Shadow` wraps an artist and offsets it; for pie wedges the wrapped
    # wedge's band already holds the polygon geometry.
    wrapped = getattr(artist, "patch", None)
    band = getattr(wrapped, "_band", None) if wrapped is not None else None
    if band is not None:
        shift = (float(getattr(artist, "ox", 0.0)),
                 float(getattr(artist, "oy", 0.0)))
        points = np.column_stack((np.asarray(band["x"], dtype=float) + shift[0],
                                  np.asarray(band["y"], dtype=float) + shift[1]))
        return dict(kind="polygon", x=0.0, y=0.0, width=0.0, height=0.0,
                    points=points.ravel().tolist(),
                    facecolor=_single_color(_call(wrapped, "get_facecolor")),
                    edgecolor=_single_color(_call(wrapped, "get_edgecolor")),
                    linewidth=_number(_call(artist, "get_linewidth"), 1.0),
                    alpha=_number(_call(artist, "get_alpha"), 1.0),
                    gid=str(_call(artist, "get_gid") or ""),
                    label=str(_call(artist, "get_label") or ""))
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
                gid=str(_call(artist, "get_gid") or ""),
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
        self._array = kwargs.get("array")
        self._cmap = kwargs.get("cmap")
        self._clim = None

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
    def get_array(self): return self._array
    def set_array(self, values): self._array = values; return self
    def set_clim(self, vmin=None, vmax=None):
        if vmin is not None or vmax is not None:
            self._clim = (vmin, vmax)
        return self
    def _colorbar_spec(self):
        values = self._array
        if values is None:
            raise ValueError("collection needs an array for a colorbar")
        vals = np.asarray(values, dtype=float).ravel()
        vals = vals[np.isfinite(vals)]
        if not vals.size:
            raise ValueError("collection has no finite values for a colorbar")
        lo, hi = getattr(self, "_clim", None) or (None, None)
        lo = float(vals.min()) if lo is None else float(lo)
        hi = float(vals.max()) if hi is None else float(hi)
        if not hi > lo:
            lo, hi = lo - 0.5, lo + 0.5
        return dict(cmap=getattr(self, "_cmap", None)
                    or rcParams.get("image.cmap", "viridis"),
                    vmin=lo, vmax=hi)
    def set_norm(self, norm): return self
    def set_cmap(self, cmap): return self
    def set_sizes(self, sizes): return self
    def set_capstyle(self, value): _ignored("Collection.set_capstyle"); return self
    def set_joinstyle(self, value): _ignored("Collection.set_joinstyle"); return self
    def set_path_effects(self, effects): _ignored("Collection.set_path_effects")
    def set_clip_on(self, value): _ignored("Collection.set_clip_on")
    def set_clip_path(self, *args, **kwargs): _ignored("Collection.set_clip_path")
    def set_offset_transform(self, value): return self
    def set_transform(self, value): return self


class LineCollection(Collection):
    def __init__(self, segments, colors=None, linewidths=None, label="", **kwargs):
        if colors is None and kwargs.get("array") is not None:
            values = np.asarray(kwargs["array"], dtype=float).ravel()
            finite = values[np.isfinite(values)]
            lo = float(finite.min()) if finite.size else 0.0
            hi = float(finite.max()) if finite.size else 1.0
            if not hi > lo:
                lo, hi = lo - 0.5, lo + 0.5
            cmap = get_cmap(_cmap_name(kwargs.get("cmap")))
            colors = [cmap((value - lo) / (hi - lo)) for value in values]
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


class PathCollection(LineCollection):
    def __init__(self, paths, sizes=None, offsets=None, **kwargs):
        self._paths = list(paths)
        self._sizes = sizes
        self._offsets = offsets
        segments = []
        for path in self._paths:
            points = np.asarray(getattr(path, "vertices", path), dtype=float).reshape(-1, 2)
            segments.append(np.vstack([points, points[:1]]) if len(points) else points)
        super().__init__(segments, **kwargs)

    def set_paths(self, paths):
        self._paths = list(paths)
        return self


class RegularPolyCollection(LineCollection):
    def __init__(self, numVertices, sizes=None, offsets=None, offset_transform=None, **kwargs):
        n = max(int(numVertices), 3)
        angles = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False) + np.pi / 2.0
        base = np.column_stack([np.cos(angles), np.sin(angles)])
        offsets = [] if offsets is None else list(offsets)
        sizes = [1.0] * len(offsets) if sizes is None else list(sizes)
        segments = []
        for i, offset in enumerate(offsets):
            size = float(sizes[i % len(sizes)]) if sizes else 1.0
            radius = max(np.sqrt(abs(size)) / 100.0, 0.01)
            points = base * radius + np.asarray(offset, dtype=float).ravel()[:2]
            segments.append(np.vstack([points, points[:1]]))
        super().__init__(segments, **kwargs)


class EllipseCollection(PolyCollection):
    """Ellipses at `offsets`, with widths/heights in points or data units."""

    def __init__(self, widths, heights, angles, units="points", offsets=None,
                 offset_transform=None, **kwargs):
        widths = np.atleast_1d(np.asarray(widths, dtype=float)).ravel()
        heights = np.atleast_1d(np.asarray(heights, dtype=float)).ravel()
        angles = np.atleast_1d(np.asarray(angles, dtype=float)).ravel()
        centers = np.zeros((1, 2)) if offsets is None else np.asarray(
            offsets, dtype=float).reshape(-1, 2)
        t = np.linspace(0.0, 2.0 * np.pi, 49)
        verts = []
        for i, center in enumerate(centers):
            w = float(widths[i % len(widths)]) / 2.0
            h = float(heights[i % len(heights)]) / 2.0
            a = np.deg2rad(float(angles[i % len(angles)]))
            x, y = w * np.cos(t), h * np.sin(t)
            verts.append(np.column_stack([
                center[0] + x * np.cos(a) - y * np.sin(a),
                center[1] + x * np.sin(a) + y * np.cos(a)]))
        super().__init__(verts, **kwargs)
        self._units = str(units)

    def get_offsets(self): return None


class Arrow(Patch):
    """A filled arrow from (x, y) to (x + dx, y + dy)."""

    def __init__(self, x, y, dx, dy, width=1.0, **kwargs):
        super().__init__(**kwargs)
        self.x, self.y, self.dx, self.dy = map(float, (x, y, dx, dy))
        self.width = float(width)

    def get_xy(self):
        length = _math.hypot(self.dx, self.dy)
        if length == 0.0:
            return np.array([[self.x, self.y], [self.x, self.y]])
        ux, uy = self.dx / length, self.dy / length
        nx, ny = -uy, ux
        half = self.width / 2.0
        head_length = min(3.0 * self.width, length)
        head_half = self.width
        tip = (self.x + self.dx, self.y + self.dy)
        neck = (tip[0] - ux * head_length, tip[1] - uy * head_length)
        base = (self.x + nx * half, self.y + ny * half)
        return np.array([
            base,
            (neck[0] + nx * half, neck[1] + ny * half),
            (neck[0] + nx * head_half, neck[1] + ny * head_half),
            tip,
            (neck[0] - nx * head_half, neck[1] - ny * head_half),
            (neck[0] - nx * half, neck[1] - ny * half),
            (self.x - nx * half, self.y - ny * half),
        ])


patches.Arrow = Arrow


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

    def set_offsets(self, offsets):
        self._offsets = np.asarray(offsets, dtype=float).reshape(-1, 2)
        return self

    def set_edgecolors(self, colors):
        self._edgecolors = colors
        return self
    set_edgecolor = set_edgecolors


class EventCollection(LineCollection):
    def __init__(self, positions, orientation="horizontal", lineoffset=0, linelength=1, **kwargs):
        self._positions = np.asarray(positions, dtype=float).ravel().copy()
        self._orientation = orientation
        self._lineoffset = float(lineoffset)
        self._linelength = float(linelength)
        color = kwargs.pop("color", None)
        if color is not None and "colors" not in kwargs:
            kwargs["colors"] = color
        if "linewidth" in kwargs and "linewidths" not in kwargs:
            kwargs["linewidths"] = kwargs.pop("linewidth")
        super().__init__(self._event_segments(), **kwargs)

    def _event_segments(self):
        if self._orientation not in ("horizontal", "vertical"):
            raise ValueError(f"unsupported orientation: {self._orientation!r}")
        if self._orientation == "horizontal":
            return [[(p, self._lineoffset - self._linelength / 2),
                     (p, self._lineoffset + self._linelength / 2)] for p in self._positions]
        return [[(self._lineoffset - self._linelength / 2, p),
                 (self._lineoffset + self._linelength / 2, p)] for p in self._positions]

    def _refresh(self):
        self._segments = self._event_segments()
        return self

    def get_positions(self): return self._positions.copy()
    def get_orientation(self): return self._orientation
    def get_lineoffset(self): return self._lineoffset
    def get_linelength(self): return self._linelength
    def get_colors(self):
        colors = self._colors
        if colors is None:
            return []
        values = np.asarray(colors)
        if values.ndim == 1:
            return [values]
        return [np.asarray(row) for row in values]
    def get_color(self):
        colors = self.get_colors()
        return colors[0] if colors else None
    def set_linestyle(self, linestyle):
        self._linestyle = linestyle
        return self
    def get_linestyle(self):
        return getattr(self, "_linestyle", "solid")
    def set(self, **kwargs):
        setters = {"linestyle": self.set_linestyle, "ls": self.set_linestyle,
                   "linewidth": self.set_linewidth, "lw": self.set_linewidth,
                   "color": self.set_color, "c": self.set_color,
                   "alpha": self.set_alpha}
        for key, value in kwargs.items():
            setter = setters.get(key)
            if setter is not None:
                setter(value)
        return self
    def add_positions(self, positions): return self.append_positions(positions)
    def set_positions(self, positions):
        self._positions = np.asarray(positions, dtype=float).ravel().copy()
        return self._refresh()
    def append_positions(self, positions):
        self._positions = np.append(self._positions, np.asarray(positions, dtype=float).ravel())
        return self._refresh()
    def extend_positions(self, positions): return self.append_positions(positions)
    def set_orientation(self, orientation):
        self._orientation = orientation
        return self._refresh()
    def switch_orientation(self):
        self._orientation = ("vertical" if self._orientation == "horizontal"
                             else "horizontal")
        return self._refresh()
    def set_lineoffset(self, lineoffset):
        self._lineoffset = float(lineoffset)
        return self._refresh()
    def set_linelength(self, linelength):
        self._linelength = float(linelength)
        return self._refresh()


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
        self._axes = None
        self._gid = None

    @property
    def axes(self): return self._axes

    @axes.setter
    def axes(self, value): self._axes = value

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

    def set(self, **kwargs):
        """Apply Matplotlib line properties by name, as `line.set(lw=...)`."""
        setters = {
            "color": self.set_color,
            "c": self.set_color,
            "linewidth": self.set_linewidth,
            "lw": self.set_linewidth,
            "linestyle": self.set_linestyle,
            "ls": self.set_linestyle,
            "marker": self.set_marker,
            "markersize": self.set_markersize,
            "ms": self.set_markersize,
            "markerfacecolor": self.set_markerfacecolor,
            "mfc": self.set_markerfacecolor,
            "markeredgecolor": self.set_markeredgecolor,
            "mec": self.set_markeredgecolor,
            "alpha": self.set_alpha,
            "label": self.set_label,
            "zorder": self.set_zorder,
            "drawstyle": self.set_drawstyle,
            "visible": self.set_visible,
        }
        for key, value in kwargs.items():
            setter = setters.get(key)
            if setter is None:
                _ignored(f"Line2D.set({key})")
            else:
                setter(value)
        return self

    def get_transform(self): return getattr(self, "_transform", _Transform())
    def get_path(self):
        return Path(np.column_stack([
            np.asarray(self._series["x"], dtype=float).ravel(),
            np.asarray(self._series["y"], dtype=float).ravel()]))
    def set_transform(self, transform): self._transform = transform; return self
    def set_agg_filter(self, value): return self
    def set_rasterized(self, value): return self
    def set_clip_on(self, value): return self

    def set_dashes(self, dashes):
        self._series["linestyle"] = "--" if dashes else "-"
        self._dashes = list(dashes)
        return self

    def set_dash_capstyle(self, style): return self
    def set_solid_capstyle(self, style): return self
    def set_dash_joinstyle(self, style): return self
    def set_solid_joinstyle(self, style): return self

    def get_xdata(self): return self._series["x"]
    def get_ydata(self): return self._series["y"]
    def get_data(self, *args, **kwargs): return (self.get_xdata(), self.get_ydata())
    def set_gid(self, gid):
        self._gid = gid
        self._series["gid"] = "" if gid is None else str(gid)
        return self
    def get_gid(self): return self._gid
    def set_figure(self, figure): return self
    def draw(self, renderer): return None
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


class Artist:
    """Minimal artist base class used by custom gallery artists."""

    def __init__(self, *args, **kwargs):
        self._zorder = kwargs.get("zorder", 0)
        self._visible = kwargs.get("visible", True)
        self._agg_filter = None
        self._rasterized = False

    def set_zorder(self, zorder): self._zorder = int(zorder); return self
    def get_zorder(self): return self._zorder
    def set_visible(self, visible): self._visible = bool(visible); return self
    def get_visible(self): return self._visible
    def set_agg_filter(self, value): self._agg_filter = value; return self
    def set_rasterized(self, value): self._rasterized = bool(value); return self
    def set_in_layout(self, value): return self
    def set_clip_on(self, value): return self
    def set_clip_path(self, *args, **kwargs): return self
    def set_animated(self, value): self._animated = bool(value); return self
    def get_animated(self): return getattr(self, "_animated", False)
    def set_picker(self, value): self._picker = value; return self
    def draw(self, renderer=None): return None


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


class _SpineSelection:
    """A group of spines selected with `spines[:]` or `spines[[...]]`."""

    def __init__(self, spines): self._spines = tuple(spines)
    def __iter__(self): return iter(self._spines)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        def apply(*args, **kwargs):
            for spine in self._spines:
                getattr(spine, name)(*args, **kwargs)
            return self
        return apply


class _Spines:
    """The four axes spines, addressable as a mapping or as attributes."""

    def __init__(self):
        self.left = _Spine()
        self.right = _Spine()
        self.bottom = _Spine()
        self.top = _Spine()

    def __getitem__(self, name):
        if isinstance(name, slice):
            names = ("left", "right", "bottom", "top")[name]
            return _SpineSelection(getattr(self, item) for item in names)
        if isinstance(name, (list, tuple)):
            return _SpineSelection(getattr(self, str(item)) for item in name)
        return getattr(self, name)
    def __setitem__(self, name, spine): setattr(self, name, spine)
    def register_axis(self, axis): return None
    def __iter__(self): return iter(("left", "right", "bottom", "top"))
    def keys(self): return ("left", "right", "bottom", "top")
    def values(self): return (self.left, self.right, self.bottom, self.top)
    def items(self): return ((name, getattr(self, name)) for name in self)


class _AxisHelper:
    """State holder returned by `axisartist` axis `get_helper()`."""

    def __init__(self):
        self.nth_coord_ticks = 0
        self.nth_coord = 0


class _AxisArtistProxy:
    """Small stand-in for the floating-axis artists used by axisartist."""

    def __init__(self, axes=None, name=""):
        self._axes = axes
        self.name = name
        self.label = _TextLabel()
        self.major_ticklabels = _TextLabel()
        self.major_ticks = _TextLabel()
        self.minor_ticklabels = _TextLabel()
        self.minor_ticks = _TextLabel()
        self._visible = True
        self._helper = _AxisHelper()

    def set_visible(self, visible):
        self._visible = bool(visible)
        return self

    def get_visible(self): return self._visible

    def toggle(self, all=None, ticks=None, ticklabels=None, label=None, **kwargs):
        if all is not None:
            ticks = ticklabels = label = all
        if ticks is not None:
            self.major_ticks.set_visible(ticks)
            self.minor_ticks.set_visible(ticks)
        if ticklabels is not None:
            self.major_ticklabels.set_visible(ticklabels)
            self.minor_ticklabels.set_visible(ticklabels)
        if label is not None:
            self.label.set_visible(label)
        return self

    def get_helper(self): return self._helper
    def set_axisline_style(self, *args, **kwargs): return self
    def set_axis_direction(self, *args, **kwargs): return self
    def set_axislabel_direction(self, *args, **kwargs): return self
    def set_ticklabel_direction(self, *args, **kwargs): return self

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args, **kwargs: self


class _AxisSelection:
    """Forward an axisartist operation to several axis proxies."""

    def __init__(self, artists): self._artists = tuple(artists)

    def __iter__(self): return iter(self._artists)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        values = [getattr(artist, name, None) for artist in self._artists]
        if values and all(value is not None and not callable(value) for value in values):
            return _AxisSelection(values)

        def apply(*args, **kwargs):
            for artist in self._artists:
                getattr(artist, name)(*args, **kwargs)
            return self
        return apply


class _AxisAccessor:
    """`ax.axis` is both callable and subscriptable (axisartist)."""

    _STANDARD = ("left", "right", "bottom", "top")

    def __init__(self, axes):
        self._axes = axes
        self._artists = {}

    def _artist(self, key):
        return self._artists.setdefault(str(key), _AxisArtistProxy(self._axes, str(key)))

    def _standard(self):
        return [self._artist(name) for name in self._STANDARD]

    def __call__(self, *args, **kwargs): return self._axes._axis(*args, **kwargs)

    def __getitem__(self, key):
        if isinstance(key, slice):
            names = self._STANDARD[key]
            return _AxisSelection(self._artist(name) for name in names)
        if isinstance(key, (list, tuple, np.ndarray)) and all(
                isinstance(item, str) for item in key):
            return _AxisSelection(self._artist(item) for item in key)
        if isinstance(key, (list, tuple, np.ndarray)):
            return self._axes.spines[key]
        return self._artist(key)

    def __setitem__(self, key, value): self._artists[str(key)] = value

    def __iter__(self): return iter(self._standard())
    def keys(self):
        return tuple(dict.fromkeys((*self._STANDARD, *self._artists)))
    def values(self): return tuple(self._artist(name) for name in self.keys())
    def items(self): return tuple((name, self._artist(name)) for name in self.keys())
    def __getattr__(self, name): return getattr(self._axes, name)


class _Axis:
    """Stand-in for `ax.xaxis` / `ax.yaxis` with tick and label shims."""

    def __init__(self, parent, axis):
        self._parent, self._axis = parent, axis
        self.axes = parent
        self.label = _TextLabel()
        self.offsetText = _TextLabel()
        self._visible = True
        self._locator = None
        self._minor_locator = None
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
    def set(self, **kwargs):
        """`ax.xaxis.set(major_locator=..., major_formatter=..., label=...)`."""
        for key, value in kwargs.items():
            if key in ("major_locator", "minor_locator", "major_formatter",
                       "minor_formatter"):
                getattr(self, f"set_{key}")(value)
            elif key == "label":
                self.label.set_text(value)
            elif key == "ticks":
                self.set_ticks(value)
            elif key == "ticklabels":
                self.set_ticklabels(value)
            elif key in ("visible", "rotation", "labelsize", "labelpad"):
                _ignored(f"Axis.set({key})")
            else:
                raise AttributeError(f"Axis.set() does not support {key!r}")

    def set_major_locator(self, locator):
        """Place the major ticks with `locator`, dropping explicit tick lists."""
        self._locator = locator
        if hasattr(locator, "set_axis"):
            locator.set_axis(self)
        if self._axis == "x":
            self._parent._xlocator = locator
            self._parent._xticks = self._parent._xticklabels = None
        else:
            self._parent._ylocator = locator
            self._parent._yticks = self._parent._yticklabels = None
    def set_minor_locator(self, locator):
        self._minor_locator = locator
        if hasattr(locator, "set_axis"):
            locator.set_axis(self)
    def get_minor_locator(self): return self._minor_locator or _LocatorHandle()
    def minorticks_on(self): self._parent.minorticks_on()
    def minorticks_off(self): self._parent.minorticks_off()
    def set_major_formatter(self, formatter): self._formatter = formatter
    def set_minor_formatter(self, formatter): return None
    def get_major_locator(self): return self._locator or _LocatorHandle()
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


class _LocatorHandle:
    """Placeholder locator returned before an explicit locator is installed."""

    @property
    def base(self): return self
    def set_params(self, *args, **kwargs): return None
    def set_nbins(self, *args, **kwargs): return None
    def numticks(self, *args, **kwargs): return 8


class _Callbacks:
    def connect(self, *args, **kwargs): return 1
    def disconnect(self, *args, **kwargs): return None


class _Timer:
    """Headless timer accepted by Matplotlib's animation event sources."""

    def __init__(self, interval=1000, callbacks=None, **kwargs):
        self.interval = interval
        self.callbacks = []
        self._running = False
        for callback in callbacks or ():
            self.add_callback(callback)

    def add_callback(self, func, *args, **kwargs):
        self.callbacks.append((func, args, kwargs))
        return len(self.callbacks)

    def remove_callback(self, func):
        self.callbacks = [item for item in self.callbacks if item[0] is not func]

    def start(self, interval=None):
        if interval is not None:
            self.interval = interval
        self._running = True

    def stop(self):
        self._running = False

    def single_shot(self, func, *args, **kwargs):
        self.add_callback(func, *args, **kwargs)


class MouseEvent:
    """Headless mouse event used by examples that simulate a pointer move."""

    def __init__(self, name, canvas, x, y, button=None, key=None,
                 step=0, dblclick=False, guiEvent=None):
        self.name, self.canvas = str(name), canvas
        self.x, self.y = float(x), float(y)
        self.xdata = self.ydata = None
        self.button, self.key, self.step = button, key, step
        self.dblclick, self.guiEvent = bool(dblclick), guiEvent
        self.inaxes = None

    def _process(self):
        return None


class _Manager:
    def __init__(self, canvas):
        self.canvas = canvas
        self.key_press_handler_id = None
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
    def add_callback(self, *args, **kwargs): return 1
    def remove_callback(self, *args, **kwargs): return None
    def supports_blit(self): return False
    def blit(self, *args, **kwargs): return None
    def restore_region(self, *args, **kwargs): return None
    def copy_from_bbox(self, *args, **kwargs): return None
    def new_timer(self, interval=1000, callbacks=None, **kwargs):
        return _Timer(interval, callbacks, **kwargs)
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


class _LayoutEngine:
    """Accepted layout-engine object; matplotvite owns the actual layout."""

    def __init__(self, name=None):
        self.name = name
        self.params = {}

    def set(self, **kwargs):
        self.params.update(kwargs)
        return None

    def get(self): return dict(self.params)


class _GroupedBarResult:
    """Result of `Axes.grouped_bar`: one bar container per data series."""

    def __init__(self, bar_containers):
        self.bar_containers = list(bar_containers)


def _spectral_estimates(x, y=None, NFFT=256, Fs=2.0, Fc=0.0, window=None,
                        noverlap=None, pad_to=None):
    """One-sided periodogram estimates used by the signal-processing helpers."""
    x = np.asarray(x, dtype=np.float64).ravel()
    nfft = max(int(NFFT), 2)
    if x.size < nfft:
        raise ValueError("the signal must be at least NFFT samples long")
    step = nfft - (nfft // 2 if noverlap is None else int(noverlap))
    if step <= 0:
        raise ValueError("noverlap must be smaller than NFFT")
    size = max(int(pad_to or nfft), nfft)
    taper = np.ones(nfft) if window is None else np.asarray(window(np.ones(nfft)))
    px = np.stack([x[i:i + nfft] * taper
                   for i in range(0, x.size - nfft + 1, step)])
    freqs = np.fft.rfftfreq(size, d=1.0 / float(Fs)) + float(Fc)
    fx = np.fft.rfft(px, n=size, axis=1)
    norm = max(float(Fs) * float(np.sum(taper ** 2)), 1e-20)
    pxx = np.mean(np.abs(fx) ** 2, axis=0) / norm
    if y is None:
        return pxx, freqs
    y = np.asarray(y, dtype=np.float64).ravel()
    if y.size != x.size:
        raise ValueError("x and y must have the same length")
    py = np.stack([y[i:i + nfft] * taper
                   for i in range(0, y.size - nfft + 1, step)])
    fy = np.fft.rfft(py, n=size, axis=1)
    pxy = np.mean(fx * np.conj(fy), axis=0) / norm
    return pxx, np.mean(np.abs(fy) ** 2, axis=0) / norm, pxy, freqs


# Matplotlib's `Axes.set` is `Artist.set` plus the Axes-specific aliases below,
# so an Artist property without a dedicated setter is still accepted (and, for
# the ones the renderer has no model for, recorded as an ignored shim).
_AXES_ARTIST_PROPS = frozenset(
    "agg_filter alpha animated clip_box clip_on clip_path gid in_layout label "
    "path_effects picker rasterized sketch_params snap url visible zorder".split()
)


class Axes:
    def __init__(self, pos=0, *args, **kwargs):
        # axes_grid creates Axes(fig, rect) directly. Preserve the rectangle
        # when one is supplied; normal pyplot paths pass a single index.
        fig_arg = pos if args else None
        rect_arg = args[0] if args else None
        if args:
            pos = 0
        self._artist_seq = 0
        self.pos, self.lines, self.texts = pos, [], []
        self._subplotspec = None
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
        self._adjustable = "box"
        self.title = self.xlabel = self.ylabel = ""
        self.show_legend, self.xlim, self.ylim = False, None, None
        self.legend_labels = None
        self._sticky_x, self._sticky_y = [], []
        self.visible, self._removed, self._axis_off = True, False, False
        self.artists, self.label, self.zorder = [], "", 0
        self.facecolor, self.alpha = None, None
        self.xscale = self.yscale = "linear"
        self.log_base = 10.0
        self.symlog_linthresh_x = self.symlog_linthresh_y = 1.0
        self.asinh_linear_width_x = self.asinh_linear_width_y = 1.0
        self.logit_one_half = "1/2"
        self.logit_use_overline = False
        self._xscale_obj = self._yscale_obj = None
        self._xscale_forward = self._yscale_forward = None
        self.show_grid = False
        self.grid_color = self.grid_linewidth = self.grid_alpha = self.grid_linestyle = None
        self.grid_minor_show = False
        self.grid_minor_color = self.grid_minor_linewidth = self.grid_minor_alpha = None
        self.grid_axis = "both"
        self.minor_ticks = False
        self.tick_params_box = {}
        self._yside = ""
        self.tick_params_x = {}
        self.tick_params_y = {}
        self.legend_loc = "best"
        self.legend_ncol = 1
        self.legend_frameon = True
        self.legend_fontsize = None
        self.legend_title = ""
        self.legend_title_fontsize = None
        self.legend_anchor = None
        self.legend_family = None
        self.title_size = self.xlabel_size = self.ylabel_size = None
        self.title_family = self.xlabel_family = self.ylabel_family = None
        self.transAxes = _CoordTransform("axes")
        self.transData = _CoordTransform("data")
        self.transScale = _Transform()
        self.transLimits = _Transform()
        self.patch = Rectangle((0, 0), 1, 1, transform=self.transAxes,
                               facecolor=self.get_facecolor(), edgecolor="none")
        self._axlines = []
        self._xticks = self._yticks = None
        self._xlocator = self._ylocator = None
        self._xticklabels = self._yticklabels = None
        self._x_date = False
        self._categories = []
        self._inverted = [False, False]
        self._pos_override = None
        if rect_arg is not None and len(rect_arg) == 4:
            self._pos_override = tuple(float(v) for v in rect_arg)
        self._fig = fig_arg
        self._share_x = self._share_y = None
        self.hide_xticklabels = self.hide_yticklabels = False
        self._prop_cycle = _cycle_colors(rcParams.get("axes.prop_cycle")) or list(_CYCLE)
        self._cycle_pos = self._patch_pos = 0
        self._twin, self._twin_gap, self._twin_of = "", 0.0, None
        self._twin_reserve = ""
        self.xlabel_color = self.ylabel_color = None
        self._fig = None
        self._colorbar = None
        self._bounds_are_axes = False
        self.xaxis = _Axis(self, "x")
        self.yaxis = _Axis(self, "y")
        self.spines = _Spines()
        self.axis = _AxisAccessor(self)
        self.patches = []
        self.collections = []
        self.callbacks = _Callbacks()
        self._box_aspect = None
        self._axes_locator = None
        # Custom projections (Hammer, geo, ...) initialise their transform
        # graph here; base axes have no such method.
        if hasattr(self, "_set_lim_and_transforms"):
            self._set_lim_and_transforms()

    def _set_lim_and_transforms(self):
        """Transform hook for projection subclasses; base axes add none."""
        return None

    def _next_color(self, patch=False):
        # Matplotlib keeps one cycle position for lines and another for
        # patches (bar, fill*, scatter, ...).
        cycle = self._prop_cycle or _CYCLE
        if patch:
            color = cycle[self._patch_pos % len(cycle)]
            self._patch_pos += 1
        else:
            color = cycle[self._cycle_pos % len(cycle)]
            self._cycle_pos += 1
        return color

    def set_prop_cycle(self, *args, **kwargs):
        """Replace the colour cycle used by artists without an explicit colour."""
        colors = kwargs.get("color", kwargs.get("colors"))
        if colors is None and args:
            arg = args[0]
            if arg is None:
                colors = _cycle_colors(rcParams.get("axes.prop_cycle")) or list(_CYCLE)
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
        self._cycle_pos = self._patch_pos = 0
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

    def set_aspect(self, aspect, adjustable=None, anchor=None, share=False):
        self.aspect = _norm_aspect(aspect)
        if adjustable is not None:
            self.set_adjustable(adjustable)

    def set_adjustable(self, adjustable, share=False):
        """'box' shrinks the plot area, 'datalim' bends the data limits."""
        if adjustable not in ("box", "datalim"):
            raise ValueError(
                f"adjustable must be 'box' or 'datalim', got {adjustable!r}")
        self._adjustable = adjustable

    def get_adjustable(self): return self._adjustable

    def set_forward_navigation_events(self, visible): return None
    def get_forward_navigation_events(self): return "auto"
    def set_navigate(self, visible): return None

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

    def _exact_axes_box(self):
        """True when the renderer can preserve a plain `add_axes` rectangle."""
        return (self._pos_override is not None
                and getattr(self, "_bounds_are_axes", False)
                and self._colorbar is None
                and not self._twin and self.aspect is None)

    def _render_bounds(self, dpi=None):
        """Expand an axes rectangle by the renderer's label margins.

        Matplotlib's `add_axes`/`set_position` rectangle is the axes box, not
        the outer panel; the tick, label and title margins live outside it.
        The renderer takes a panel rectangle, so add those margins back before
        drawing. Plain axes boxes use the same 40/30/25/25 px margins as the
        renderer's exact path ; styled panels keep the roomier legacy margins.
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
        exact = self._exact_axes_box()
        left = (40.0 if exact else 70.0) / width
        right = 25.0 / width
        bottom = (30.0 if exact else 60.0) / height
        title_pad = 0.0
        # The exact path draws `add_axes` titles manually inside its 25 px top
        # margin, so it must not reserve a caption band as well.
        if self.title and not exact:
            title_size = _font_size(self.title_size or rcParams.get("axes.titlesize", 12.0), 12.0)
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
        # A bad transform used to turn into a gigantic canvas request; reject it.
        if not all(_math.isfinite(v) and abs(v) <= 100.0 for v in (x, y, w, h)):
            raise ValueError(f"inset_axes bounds must be finite axes fractions: {bounds!r}")
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

    def indicate_inset(self, *args, **kwargs):
        return _Namespace(connectors=[Patch(), Patch()], rectangle=Patch())

    def indicate_inset_zoom(self, *args, **kwargs):
        return _Namespace(connectors=[Patch(), Patch()], rectangle=Patch())

    def twinx(self, **kwargs):
        """A second axes sharing the x axis, with its own y axis on the right."""
        return self._make_twin("y")

    def twiny(self, **kwargs):
        """A second axes sharing the y axis, with its own x axis on top."""
        return self._make_twin("x")

    def sharex(self, other):
        group = other._share_x or _Share()
        if other._share_x is None:
            group.axes.append(other)
            other._share_x = group
        self._share_x = group
        group.axes.append(self)
        self.hide_xticklabels = True
        return self

    def sharey(self, other):
        group = other._share_y or _Share()
        if other._share_y is None:
            group.axes.append(other)
            other._share_y = group
        self._share_y = group
        group.axes.append(self)
        self.hide_yticklabels = True
        return self

    def twin(self, *args, **kwargs):
        """Overlay axes sharing y, with top/right axes (axes_grid1's `twin`)."""
        return self.twiny()

    def colorbar(self, mappable=None, **kwargs):
        """Draw a colorbar for `mappable` in this axes' right margin."""
        if self._fig is None:
            raise RuntimeError("colorbar needs an axes attached to a figure")
        return self._fig.colorbar(mappable, cax=self, **kwargs)

    def _make_twin(self, axis):
        if self._fig is None:
            raise RuntimeError("twinx/twiny needs an axes attached to a figure")
        fig = self._fig
        box = self.get_position()
        gap = (60.0 if axis == "y" else 50.0) / (
            fig.figsize[0 if axis == "y" else 1] * fig.get_dpi())
        # Both panels keep the same plot rectangle; the shared margin reserves
        # the room for the overlay's right/top labels instead of shrinking the
        # primary axes.
        self._twin_gap, self._twin_reserve = gap, axis
        self._pos_override = box.bounds
        self._bounds_are_axes = False
        twin = Axes(self.pos)
        twin._fig, twin._twin, twin._twin_gap = fig, axis, gap
        twin._twin_reserve = axis
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
        # Accumulate extent iteratively across primitives to avoid creating
        # giant Python lists and converting millions of elements.
        ext = (float("inf"), float("-inf"))
        for entry in self.lines:
            ext = _update_extent(ext, entry["x"])
        for im in self.images:
            ext = _update_extent(ext, im._e["extent"][0])
            ext = _update_extent(ext, im._e["extent"][1])
        for c in self.contours:
            ext = _update_extent(ext, float(c["x"][0]))
            ext = _update_extent(ext, float(c["x"][-1]))
        for sc in self.scatter_pts:
            ext = _update_extent(ext, sc["x"])
        for a in self.arrows:
            # Matplotlib autoscales quiver on the tails, not the arrow tips.
            ext = _update_extent(ext, a["x"])
        for bars in self.bars:
            ext = _update_extent(ext, bars["left"])
            ext = _update_extent(ext, bars["left"] + bars["width"])
        for band in self.bands:
            ext = _update_extent(ext, band["x"])
        for e in self.errors:
            ext = _update_extent(ext, e[0] - e[4])
            ext = _update_extent(ext, e[0] + e[5])
        ext = _update_extent(ext, self._artist_extents()[0])
        return _span_extent(ext)

    def _extent_y(self):
        ext = (float("inf"), float("-inf"))
        for entry in self.lines:
            ext = _update_extent(ext, entry["y"])
        for im in self.images:
            ext = _update_extent(ext, im._e["extent"][2])
            ext = _update_extent(ext, im._e["extent"][3])
        for c in self.contours:
            ext = _update_extent(ext, float(c["y"][0]))
            ext = _update_extent(ext, float(c["y"][-1]))
        for sc in self.scatter_pts:
            ext = _update_extent(ext, sc["y"])
        for a in self.arrows:
            ext = _update_extent(ext, a["y"])
        for bars in self.bars:
            ext = _update_extent(ext, bars["bottom"])
            ext = _update_extent(ext, bars["bottom"] + bars["height"])
        for band in self.bands:
            ext = _update_extent(ext, band["y"])
        for e in self.errors:
            ext = _update_extent(ext, e[1] - e[2])
            ext = _update_extent(ext, e[1] + e[3])
        ext = _update_extent(ext, self._artist_extents()[1])
        return _span_extent(ext)

    def get_xlim(self):
        group = self._share_x
        explicit = group.limits if group is not None else self.xlim
        extent = None
        if explicit is not None:
            lo, hi = explicit
        elif group is not None:
            lo, hi = group.union("x")
        else:
            lo, hi = extent = self._extent_x()
        lo, hi = _log_bounds(
            lo, hi, self.xscale,
            (lambda: extent) if extent is not None else (lambda: self._extent_x()))
        bounds = (lo, hi) if explicit is not None else _margin(
            lo, hi, self.xscale,
            [e for im in self.images for e in (im._e["extent"][0], im._e["extent"][1])]
            + self._sticky_x + [float(c["x"][k]) for c in self.contours for k in (0, -1)],
        )
        if self._xscale_obj is not None:
            lo, hi = self._xscale_obj.limit_range_for_scale(bounds[0], bounds[1], 0.0)
            bounds = (float(lo), float(hi))
        return (bounds[1], bounds[0]) if self._inverted[0] else bounds

    def get_ylim(self):
        group = self._share_y
        explicit = group.limits if group is not None else self.ylim
        extent = None
        if explicit is not None:
            lo, hi = explicit
        elif group is not None:
            lo, hi = group.union("y")
        else:
            lo, hi = extent = self._extent_y()
        lo, hi = _log_bounds(
            lo, hi, self.yscale,
            (lambda: extent) if extent is not None else (lambda: self._extent_y()))
        bounds = (lo, hi) if explicit is not None else _margin(
            lo, hi, self.yscale,
            [e for im in self.images for e in (im._e["extent"][2], im._e["extent"][3])]
            + self._sticky_y + [float(c["y"][k]) for c in self.contours for k in (0, -1)],
        )
        if self._yscale_obj is not None:
            lo, hi = self._yscale_obj.limit_range_for_scale(bounds[0], bounds[1], 0.0)
            bounds = (float(lo), float(hi))
        return (bounds[1], bounds[0]) if self._inverted[1] else bounds
    def get_xbound(self): return self.get_xlim()
    def get_ybound(self): return self.get_ylim()
    def set_xbound(self, lower=None, upper=None): self.set_xlim(lower, upper)
    def set_ybound(self, lower=None, upper=None): self.set_ylim(lower, upper)

    def invert_xaxis(self): self._inverted[0] = not self._inverted[0]
    def invert_yaxis(self): self._inverted[1] = not self._inverted[1]
    def xaxis_inverted(self): return self._inverted[0]
    def yaxis_inverted(self): return self._inverted[1]

    def _limits(self):
        """Drawing limits; the getters already apply axis inversion."""
        return self.get_xlim(), self.get_ylim()

    def get_visible(self): return self.visible
    def set_visible(self, visible): self.visible = bool(visible)
    def set_axis_off(self): self._axis_off = True
    def set_axis_on(self): self._axis_off = False

    def axis(self, *args, **kwargs):
        """Class-level hook so `Axes.axis` is discoverable; instances use `_AxisAccessor`."""
        return self._axis(*args, **kwargs)

    def _axis(self, arg=None, **kwargs):
        if arg is None:
            return (self.get_xlim(), self.get_ylim())
        if isinstance(arg, str):
            key = arg.lower()
            if key in ("off", "false", "tight"):
                self._axis_off = True
            elif key in ("on", "true", "image"):
                self._axis_off = False
            elif key == "equal":
                # Matplotlib bends the data limits here, unlike set_aspect.
                self.set_aspect("equal", adjustable="datalim")
            elif key == "scaled":
                self.set_aspect("equal", adjustable="box")
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

    def new_floating_axis(self, nth_coord, value, axis_direction="bottom", **kwargs):
        return _AxisArtistProxy()

    def new_fixed_axis(self, loc, offset=None, axis_direction="bottom", **kwargs):
        return _AxisArtistProxy()

    def remove(self): self._removed = True

    def get_facecolor(self):
        return self.facecolor or rcParams.get("axes.facecolor", "white")

    def set_facecolor(self, color): self.facecolor = color
    def get_alpha(self): return self.alpha
    def set_alpha(self, alpha): self.alpha = None if alpha is None else float(alpha)

    def get_transform(self): return _Transform()
    @property
    def bbox(self): return self.get_window_extent()

    @property
    def viewLim(self):
        x0, x1 = self.get_xlim()
        y0, y1 = self.get_ylim()
        return _Bbox(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

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

    def specgram(self, x, NFFT=256, Fs=2, Fc=0, detrend=None, window=None,
                 noverlap=None, cmap=None, xextent=None, pad_to=None, sides=None,
                 scale_by_freq=None, mode=None, scale=None, vmin=None, vmax=None,
                 **kwargs):
        """Windowed FFT magnitude, drawn as an image; returns (Pxx, freqs, bins, image)."""
        data = np.asarray(x, dtype=np.float64).ravel()
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
        pxx = spectrum.T / max(float(Fs), 1e-12)
        freqs = np.fft.rfftfreq(nfft, d=1.0 / float(Fs)) + float(Fc)
        bins = np.arange(frames.shape[0]) * step / float(Fs)
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
        x = np.asarray(x, dtype=np.float64).ravel()
        taper = np.ones(x.size) if window is None else np.asarray(window(np.ones(x.size)))
        spectrum = np.fft.rfft(x * taper, n=max(int(pad_to or x.size), x.size))
        freqs = np.fft.rfftfreq(spectrum.size * 2 - 1, d=1.0 / float(Fs)) + float(Fc)
        angle = np.angle(spectrum)
        line = self.plot(freqs[:angle.size], angle, **kwargs)
        return angle, freqs[:angle.size], line[0]

    def phase_spectrum(self, x, Fs=2, Fc=0, window=None, pad_to=None,
                       sides="default", **kwargs):
        """Plot the unwrapped phase spectrum of a signal."""
        x = np.asarray(x, dtype=np.float64).ravel()
        taper = np.ones(x.size) if window is None else np.asarray(window(np.ones(x.size)))
        spectrum = np.fft.rfft(x * taper, n=max(int(pad_to or x.size), x.size))
        freqs = np.fft.rfftfreq(spectrum.size * 2 - 1, d=1.0 / float(Fs)) + float(Fc)
        phase = np.unwrap(np.angle(spectrum))
        line = self.plot(freqs[:phase.size], phase, **kwargs)
        return phase, freqs[:phase.size], line[0]

    def xcorr(self, x, y, normed=False, maxlags=10, usevlines=True, **kwargs):
        """Plot the cross-correlation of two signals."""
        x = np.asarray(x, dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
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
        x = np.sort(np.asarray(x, dtype=np.float64).ravel())
        if weights is None:
            y = np.arange(1, x.size + 1) / max(x.size, 1)
        else:
            w = np.asarray(weights, dtype=np.float64).ravel()
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

    def set_rorigin(self, value): return None
    def set_rlabel_position(self, value): return None
    def set_thetalim(self, *args, **kwargs): return None
    def set_theta_zero_location(self, loc, offset=0.0): return None
    def set_theta_offset(self, offset): return None
    def set_thetamin(self, value): return None
    def set_thetamax(self, value): return None
    def pie_label(self, *args, **kwargs): return None

    def set_rticks(self, ticks, labels=None, **kwargs):
        """Set the radial tick positions, as PolarAxes.set_rticks."""
        return self.set_yticks(ticks, labels=labels, **kwargs)

    def set_rgrids(self, radii, labels=None, angle=None, fmt=None, **kwargs):
        """Set the radial grid positions, as PolarAxes.set_rgrids."""
        if labels is None and fmt is not None:
            labels = [fmt % r for r in radii]
        return self.set_yticks(radii, labels=labels, **kwargs)

    def set_thetagrids(self, angles, labels=None, fmt=None, **kwargs):
        """Set the angular grid positions, as PolarAxes.set_thetagrids."""
        if labels is None and fmt is not None:
            labels = [fmt % a for a in angles]
        return self.set_xticks(angles, labels=labels, **kwargs)

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
        size = _font_size(self.title_size or rcParams.get("axes.titlesize", 12.0), 12.0)
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
    def set_axes_locator(self, locator):
        self._axes_locator = locator
        if locator is not None and hasattr(locator, "apply"):
            locator.apply(self)
        return self
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
    def clabel(self, *args, **kwargs):
        if args and hasattr(args[0], "clabel"):
            return args[0].clabel(*args[1:], **kwargs)
        return []
    def secondary_xaxis(self, *args, **kwargs): _ignored("Axes.secondary_xaxis"); return self
    def secondary_yaxis(self, *args, **kwargs): _ignored("Axes.secondary_yaxis"); return self
    def get_aux_axes(self, *args, **kwargs): return self
    def barbs(self, *args, **kwargs):
        pivot = kwargs.get("pivot")
        if isinstance(pivot, (int, float, np.number)):
            kwargs["pivot"] = "middle"
        return self.quiver(*args, **kwargs)

    def add_artist(self, artist, **kwargs):
        if isinstance(artist, Text):
            self.text(artist._x, artist._y, artist._text)
        elif isinstance(artist, Line2D):
            self._append_series(artist._series)
        elif hasattr(artist, "_add_to_axes"):
            artist._add_to_axes(self)
        else:
            self.artists.append(self._stamp(artist))
        return artist
    def set_anchor(self, anchor, **kwargs):
        self._anchor = anchor
        return None
    def matshow(self, Z, **kwargs):
        kwargs.setdefault("origin", "upper")
        kwargs.setdefault("aspect", "equal")
        return self.imshow(Z, **kwargs)

    def table(self, cellText=None, cellColours=None, **kwargs):
        """Add a table to the Axes, as `Axes.table`."""
        return Table(self, cellText=cellText, cellColours=cellColours, **kwargs)

    def spy(self, Z, precision=0, marker=None, markersize=None,
            aspect="equal", origin="upper", **kwargs):
        """Plot the sparsity pattern of an array."""
        data = np.asarray(Z)
        if precision == "present":
            mask = np.isfinite(data)
        elif precision in (None, 0):
            mask = data != 0
        else:
            mask = np.abs(data) > float(precision)
        image = self.imshow(
            mask.astype(float), cmap="binary_r", interpolation="nearest",
            aspect=aspect, origin=origin, **kwargs)
        self.set_xticks([])
        self.set_yticks([])
        return image
    def arrow(self, x, y, dx, dy, **kwargs):
        """Add a data-space `FancyArrow` and return the patch."""
        patch = FancyArrow(x, y, dx, dy, **kwargs)
        self.add_patch(patch)
        return patch

    def add_image(self, image):
        if isinstance(image, NonUniformImage):
            data, extent = image._render_spec()
            return self.imshow(data, extent=extent, cmap=image._cmap,
                               interpolation=image._interpolation, origin="lower")
        if isinstance(image, AxesImage):
            self.images.append(image)
            return image
        raise TypeError("add_image expects an AxesImage or NonUniformImage")

    def add_patch(self, patch):
        try:
            patch.axes = self
            patch.figure = self._fig
        except AttributeError:
            pass
        self.artists.append(self._stamp(patch))
        self.patches.append(patch)
        return patch
    def add_collection(self, collection, autolim=True):
        self.artists.append(self._stamp(collection))
        self.collections.append(collection)
        return collection
    def add_line(self, line):
        if isinstance(line, Line2D):
            line.axes = self
            self._append_series(line._series)
        else:
            self.artists.append(self._stamp(line))
        return line
    def get_children(self): return [*list(self.artists), self]
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
        self.legend_labels = None
        self._xticks = self._yticks = None
        self._xlocator = self._ylocator = None
        self.xaxis._locator = self.yaxis._locator = None
        self._xticklabels = self._yticklabels = None
        self.grid_color = self.grid_linewidth = self.grid_alpha = self.grid_linestyle = None
        self.grid_minor_show = False
        self.grid_minor_color = self.grid_minor_linewidth = self.grid_minor_alpha = None
        self.grid_axis = "both"
        self.tick_params_x.clear()
        self.tick_params_y.clear()
        self.tick_params_box.clear()
        self._artist_seq = 0
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
            array = np.asarray(_as_list(values))
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

    def _locator_ticks(self, axis):
        """Tick positions from the major locator, or None for the automatic ones."""
        locator = self._xlocator if axis == "x" else self._ylocator
        if locator is None:
            return None
        lo, hi = self.get_xlim() if axis == "x" else self.get_ylim()
        try:
            ticks = np.asarray(locator.tick_values(lo, hi), dtype=float).ravel()
        except (AttributeError, TypeError, ValueError):
            return None
        ticks = ticks[np.isfinite(ticks)]
        return [float(v) for v in ticks] or None

    def _auto_tick_target(self, axis):
        """Label budget for an auto axis, scaled to its drawn pixel extent."""
        try:
            position = self.get_position()
            figure = self._fig
            if figure is None:
                return 8
            dpi = float(figure.dpi)
            pixels = (position.width * figure.figsize[0] * dpi if axis == "x"
                      else position.height * figure.figsize[1] * dpi)
        except (AttributeError, TypeError, ValueError):
            return 8
        if axis == "x" and self._colorbar is not None:
            pixels -= 95.0  # the renderer's colorbar strip takes room from the right
        per_label = 55.0 if axis == "x" else 45.0
        return _tick_target_core(pixels, per_label)

    def _drawn_ticks(self, axis):
        """The positions `_panel` hands the renderer when no ticks were set."""
        base = float(getattr(self, "log_base", 10.0))
        if axis == "x":
            lo, hi = self.get_xlim()
            scale = self.xscale
            if self._x_date and scale == "linear":
                asc = (lo, hi) if lo <= hi else (hi, lo)
                ticks = _date_ticks(*asc)[0]
                return list(reversed(ticks)) if lo > hi else ticks
            if self._categories:
                return [float(i) for i in range(len(self._categories))]
            if scale == "symlog":
                return _symlog_ticks(lo, hi, self.symlog_linthresh_x)[0]
            if scale == "logit":
                return _logit_ticks(lo, hi, self.logit_one_half,
                                    self.logit_use_overline)[0]
            return _auto_ticks(lo, hi, scale == "log", base,
                               self._auto_tick_target("x"))
        lo, hi = self.get_ylim()
        scale = self.yscale
        if scale == "symlog":
            return _symlog_ticks(lo, hi, self.symlog_linthresh_y)[0]
        if scale == "logit":
            return _logit_ticks(lo, hi, self.logit_one_half,
                                self.logit_use_overline)[0]
        return _auto_ticks(lo, hi, scale == "log", base,
                           self._auto_tick_target("y"))

    def get_xticks(self, minor=False):
        if self._xticks is not None:
            return np.asarray(self._xticks)
        ticks = self._locator_ticks("x")
        if ticks is not None:
            return np.asarray(ticks)
        return np.asarray(self._drawn_ticks("x"))

    def get_yticks(self, minor=False):
        if self._yticks is not None:
            return np.asarray(self._yticks)
        ticks = self._locator_ticks("y")
        if ticks is not None:
            return np.asarray(ticks)
        return np.asarray(self._drawn_ticks("y"))

    def set_xticklabels(self, labels, **kwargs):
        self._xticklabels = [str(v) for v in np.asarray(labels).ravel()]

    def set_yticklabels(self, labels, **kwargs):
        self._yticklabels = [str(v) for v in np.asarray(labels).ravel()]

    def get_xticklabels(self, minor=False, which=None):
        labels = self._xticklabels
        if labels is None and self.xscale == "logit":
            labels = _logit_ticks(*self.get_xlim(), self.logit_one_half,
                                  self.logit_use_overline)[1]
        if labels is None:
            labels = _format_ticklabels(self.xaxis._formatter, self.get_xticks())
        if labels is None:
            labels = [f"{v:g}" for v in self.get_xticks()]
        size = self._tick_style_dict("x")["labelsize"]
        return [_TextLabel(t, size) for t in labels]

    def get_yticklabels(self, minor=False, which=None):
        labels = self._yticklabels
        if labels is None and self.yscale == "logit":
            labels = _logit_ticks(*self.get_ylim(), self.logit_one_half,
                                  self.logit_use_overline)[1]
        if labels is None:
            labels = _format_ticklabels(self.yaxis._formatter, self.get_yticks())
        if labels is None:
            labels = [f"{v:g}" for v in self.get_yticks()]
        size = self._tick_style_dict("y")["labelsize"]
        return [_TextLabel(t, size) for t in labels]

    def _set_scale(self, axis, value, base=10, **kwargs):
        """Install a built-in, function, or registered custom scale on `axis`."""
        name = str(value)
        scale_attr = f"{axis}scale"
        axis_obj = getattr(self, f"{axis}axis")
        setattr(self, f"_{axis}scale_obj", None)
        setattr(self, f"_{axis}scale_forward", None)
        setattr(self, f"_{axis}scale_inverse", None)
        scale_obj = None
        if name == "linear":
            setattr(self, scale_attr, "linear")
        elif name == "log":
            setattr(self, scale_attr, "log")
            self.log_base = float(base)
        elif name == "symlog":
            setattr(self, scale_attr, "symlog")
            setattr(self, f"symlog_linthresh_{axis}", self._symlog_linthresh(kwargs))
        elif name == "asinh":
            setattr(self, scale_attr, "asinh")
            setattr(self, f"asinh_linear_width_{axis}", self._asinh_width(kwargs))
        elif name == "logit":
            setattr(self, scale_attr, "logit")
            self.logit_one_half = kwargs.get("one_half", self.logit_one_half)
            self.logit_use_overline = bool(kwargs.get("use_overline", self.logit_use_overline))
        elif name in ("function", "functionlog"):
            functions = kwargs.pop("functions", None)
            if functions is None:
                raise TypeError(f"{name} scale needs a (forward, inverse) 'functions' pair")
            from .scale import FuncScale, FuncScaleLog
            cls = FuncScaleLog if name == "functionlog" else FuncScale
            extra = {"base": base} if name == "functionlog" else {}
            scale_obj = cls(axis_obj, functions, **extra, **kwargs)
            forward, inverse = _scale_transform_pair(scale_obj)
            setattr(self, f"_{axis}scale_forward", forward)
            setattr(self, f"_{axis}scale_inverse", inverse)
            setattr(self, scale_attr, name)
            setattr(self, f"_{axis}scale_obj", scale_obj)
            scale_obj.set_default_locators_and_formatters(axis_obj)
        else:
            from .scale import _SCALES
            cls = _SCALES.get(name)
            if cls is None:
                raise NotImplementedError(f"unsupported {axis} scale: {value!r}")
            scale_obj = cls(axis_obj, **kwargs)
            forward, inverse = _scale_transform_pair(scale_obj)
            setattr(self, f"_{axis}scale_forward", forward)
            setattr(self, f"_{axis}scale_inverse", inverse)
            setattr(self, scale_attr, name)
            setattr(self, f"_{axis}scale_obj", scale_obj)
            scale_obj.set_default_locators_and_formatters(axis_obj)
        return scale_obj

    def set_xscale(self, value, base=10, **kwargs):
        return self._set_scale("x", value, base, **kwargs)

    def set_yscale(self, value, base=10, **kwargs):
        return self._set_scale("y", value, base, **kwargs)

    @staticmethod
    def _symlog_linthresh(kwargs):
        value = kwargs.get("linthresh")
        return 1.0 if value is None else max(float(value), 1e-300)

    @staticmethod
    def _asinh_width(kwargs):
        value = kwargs.get("linear_width")
        return 1.0 if value is None else max(float(value), 1e-300)

    def semilogx(self, *args, **kwargs):
        base = kwargs.pop("base", 10)
        self.set_xscale("log", base=base)
        return self.plot(*args, **kwargs)

    def semilogy(self, *args, **kwargs):
        base = kwargs.pop("base", 10)
        self.set_yscale("log", base=base)
        return self.plot(*args, **kwargs)

    def loglog(self, *args, **kwargs):
        base = kwargs.pop("base", 10)
        self.set_xscale("log", base=base)
        self.set_yscale("log", base=base)
        return self.plot(*args, **kwargs)

    def get_subplotspec(self):
        """The `SubplotSpec` this axes was created from, or its grid cell."""
        if self._subplotspec is not None:
            return self._subplotspec
        rows, cols = self._fig.grid if self._fig is not None else (1, 1)
        row, col = divmod(int(self.pos), cols)
        return SubplotSpec(GridSpec(rows, cols, figure=self._fig),
                           (row, row), (col, col))

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
                if setter is not None:
                    setter(value)
                elif key in _AXES_ARTIST_PROPS:
                    _ignored(f"Axes.set({key}=...)")
                elif key in {"frame_on", "xmargin", "ymargin", "axisbelow",
                             "autoscale_on", "autoscalex_on", "autoscaley_on",
                             "xbound", "ybound"}:
                    continue
                else:
                    raise AttributeError(f"Axes.set() does not support {key!r}")

    def text(self, x, y, s, fontdict=None, offset=(0.0, 0.0), **kwargs):
        """Place text at (x, y); `transform` may be `ax.transAxes` or
        `fig.transFigure` to use axes- or figure-fraction coordinates. `offset`
        shifts the glyphs by that many points from the anchor. Other Matplotlib
        text properties are accepted but not drawn yet."""
        transform, fontsize, colour, ha, va, bbox, rotation, family = _text_props(
            fontdict, kwargs)
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
        x = _as_f64(self._xdate(x) if kind == "data" else x)
        y = _as_f64(y)
        self.texts.append(_TextEntry((float(x[0]), float(y[0]), _mathtext(s, family),
                                      _norm_color(colour), size, ha, va, kind, bbox,
                                      rotation, family,
                                      (float(offset[0]), float(offset[1])))))
        return _TextArt(str(s))

    def imshow(self, X, cmap=None, vmin=None, vmax=None, extent=None, origin="upper",
               interpolation=None, aspect=None, alpha=None, clim=None, norm=None,
               colorizer=None, **kwargs):
        """Draw an array as an image. `X` is 2-D (mapped through `cmap`) or
        (H, W, 3|4) RGB(A) floats in 0-1. `interpolation` accepts `none`,
        `nearest`, `antialiased`, `bilinear` or `bicubic`; `alpha` scales the
        image's opacity. When omitted, `rcParams["image.interpolation"]`
        supplies the default. `clim` and Matplotlib's extra artist kwargs are
        accepted."""
        _check_kwargs(kwargs, "imshow", _IMAGE_KWARGS)
        if clim is not None:
            vmin, vmax = clim
        if colorizer is not None:
            cmap = colorizer.cmap if colorizer.cmap is not None else cmap
            if colorizer.norm is not None:
                vmin = getattr(colorizer.norm, "vmin", vmin)
                vmax = getattr(colorizer.norm, "vmax", vmax)
        setting = (rcParams.get("image.interpolation", "nearest")
                   if interpolation is None else interpolation)
        interp = str(setting).lower()
        interp = {
            "spline16": "bicubic", "spline36": "bicubic", "hanning": "bilinear",
            "hamming": "bilinear", "hermite": "bicubic", "kaiser": "bicubic",
            "quadric": "bicubic", "catrom": "bicubic", "gaussian": "bicubic",
            "lanczos": "bicubic", "blackman": "bilinear", "sinc": "bicubic",
            "bessel": "bicubic", "mitchell": "bicubic",
        }.get(interp, interp)
        a = _as_image(X)
        if isinstance(norm, str):
            # Matplotlib accepts "log" as shorthand for a LogNorm; map it before
            # the normalisation pass, which expects an object with vmin/vmax.
            kind = norm.lower()
            if kind == "log":
                positive = a[np.isfinite(a) & (a > 0.0)] if a.ndim == 2 else np.empty(0)
                lo = vmin if vmin is not None else (
                    float(positive.min()) if positive.size else 1.0)
                hi = vmax if vmax is not None else (
                    float(positive.max()) if positive.size else float(lo) * 10.0)
                if not float(hi) > float(lo):
                    hi = float(lo) * 10.0
                norm = _LogNorm(vmin=lo, vmax=hi)
            elif kind in ("linear", "none", ""):
                norm = None
            else:
                raise NotImplementedError(f"norm={norm!r} is not supported yet")
        if norm is not None and a.ndim == 2:
            a, vmin, vmax = _norm_values(norm, a)
        h, w = a.shape[:2]
        if origin == "lower":
            a = a[::-1]
        elif origin != "upper":
            raise ValueError(f"unsupported origin: {origin!r}")
        if extent is None:
            # Matplotlib centres pixels on integer data coordinates. An upper
            # origin puts row 0 at the top, which requires a descending y axis.
            extent = (-0.5, float(w) - 0.5, -0.5, float(h) - 0.5)
            self._inverted[1] = origin == "upper"
            if origin == "upper":
                extent = (extent[0], extent[1], extent[3], extent[2])
        elif len(extent) != 4:
            raise ValueError("extent must be (left, right, bottom, top)")
        elif extent[2] > extent[3]:
            self._inverted[1] = True  # bottom > top reads as a descending y axis
        alpha_data = None
        if alpha is not None and np.ndim(alpha) > 0:
            alpha_data = np.asarray(alpha, dtype=np.float64)
            opacity = 1.0
        else:
            opacity = 1.0 if alpha is None else float(alpha)
        if alpha_data is not None:
            alpha_data = np.broadcast_to(alpha_data, a.shape[:2])
            if a.ndim == 2:
                lo = vmin if vmin is not None else float(np.nanmin(a))
                hi = vmax if vmax is not None else float(np.nanmax(a))
                span = hi - lo
                normalized = (np.zeros_like(a) if span == 0.0
                              else np.clip((a - lo) / span, 0.0, 1.0))
                a = np.dstack([get_cmap(cmap)(normalized)[..., :3], alpha_data])
            elif a.shape[2] == 3:
                a = np.dstack([a, alpha_data])
            else:
                a = a.copy()
                a[..., 3] *= alpha_data
        if interp == "auto":
            interp = "antialiased"
        if interp not in ("none", "nearest", "antialiased", "bilinear", "bicubic"):
            raise ValueError(f"unsupported interpolation: {setting!r}")
        if not np.isfinite(opacity):
            raise ValueError("alpha must be finite")
        entry = dict(data=a, cmap=_cmap_name(cmap), vmin=vmin, vmax=vmax,
                     extent=tuple(float(v) for v in extent),
                     alpha=float(np.clip(opacity, 0.0, 1.0)), interpolation=interp)
        image = AxesImage(entry, self)
        self.images.append(image)
        # matplotlib's image.aspect default is "equal".
        self.set_aspect("equal" if aspect is None else aspect)
        return image

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
                datasets = [np.asarray(item, dtype=np.float64).ravel() for item in x]
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
                else np.asarray(x, dtype=np.float64).ravel())
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
                        self._append_band(_band(xs, ys, box_color, box_style.get("alpha")))
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
                mean = float(vals.mean())
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
        out = dict(boxes=[], medians=[], whiskers=[], caps=[], fliers=[], means=[])
        for i, stat in enumerate(stats):
            q1 = float(stat.get("q1", 0.0))
            q3 = float(stat.get("q3", q1))
            med = float(stat.get("med", 0.5 * (q1 + q3)))
            lo = float(stat.get("whislo", q1))
            hi = float(stat.get("whishi", q3))
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
            fliers = np.asarray(stat.get("fliers", []), dtype=float).ravel()
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

    def _stamp(self, item, *, container=False):
        """Give an artist a creation sequence number for legend ordering."""
        self._artist_seq += 1
        if isinstance(item, dict):
            item["_seq"] = self._artist_seq
            item["_container"] = bool(container)
        else:
            try:
                item._seq = self._artist_seq
                item._container = bool(container)
            except (AttributeError, TypeError):
                # add_artist also accepts opaque compatibility objects.
                pass
        return item

    def _append_series(self, entry):
        self.lines.append(self._stamp(entry))
        return entry

    def _append_band(self, entry):
        self.bands.append(self._stamp(entry))
        return entry

    def _append_scatter(self, entry):
        self.scatter_pts.append(self._stamp(entry))
        return entry

    def _append_bar(self, entry, *, container=True):
        self.bars.append(self._stamp(entry, container=container))
        return entry

    def _legend_order(self):
        """Legend labels in creation order, with bar containers last."""
        entries = []
        for item in (*self.lines, *self.scatter_pts, *self.bands, *self.bars):
            label = item.get("label", "")
            if label and isinstance(label, str):
                entries.append((bool(item.get("_container")),
                                item.get("_seq", 0), label))
        for artist in self.artists:
            if isinstance(artist, (Patch, Collection)):
                label = getattr(artist, "label", "") or artist.get_label()
                if label and isinstance(label, str):
                    entries.append((bool(getattr(artist, "_container", False)),
                                    getattr(artist, "_seq", 0), label))
        entries.sort(key=lambda entry: (entry[0], entry[1]))
        return [label for _, _, label in entries]

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

    def _ydate(self, values):
        """Convert date-like or categorical y values to numbers and label the axis."""
        if _looks_like_dates(values):
            return _date_to_num(values)
        if _looks_like_categories(values):
            return self._category_positions(values)
        return values

    def _category_positions(self, values):
        """Map y category labels to positions, labelling the y axis with them."""
        labels = [str(v) for v in np.asarray(_as_list(values), dtype=object).ravel()]
        self._yticks = [float(i) for i in range(len(labels))]
        self._yticklabels = labels
        return np.arange(len(labels), dtype=np.float64)

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
        x = np.asarray(self._xdate(x), dtype=np.float64).ravel()
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
        groups, pair = [], []
        for arg in args:
            if isinstance(arg, str):
                if not groups or groups[-1][1] is not None:
                    raise TypeError("fill expects x, y pairs, optionally followed by a colour")
                groups[-1] = (groups[-1][0], arg)
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

    def pcolormesh(self, *args, cmap=None, vmin=None, vmax=None, shading="auto",
                   alpha=None, norm=None, **kwargs):
        """Quad mesh: each Z cell is filled through `cmap` via the image path.

        `X`/`Y` may be cell edges (one longer than Z's axis) or cell centres.
        """
        if len(args) == 3 and _looks_like_dates(args[0]):
            args = (self._xdate(args[0]), args[1], args[2])
        x, y, z, edges = _mesh_args(args)
        if edges:
            extent = (float(x[0]), float(x[-1]), float(y[0]), float(y[-1]))
        else:
            dx = float(x[1] - x[0]) if x.size > 1 else 1.0
            dy = float(y[1] - y[0]) if y.size > 1 else 1.0
            extent = (float(x[0]) - dx / 2, float(x[-1]) + dx / 2,
                      float(y[0]) - dy / 2, float(y[-1]) + dy / 2)
        return self.imshow(z, cmap=_cmap_name(cmap), vmin=vmin, vmax=vmax,
                           extent=extent, origin="lower", alpha=alpha, norm=norm)

    def pcolor(self, *args, **kwargs):
        return self.pcolormesh(*args, **kwargs)

    def pcolorfast(self, *args, **kwargs):
        return self.pcolormesh(*args, **kwargs)

    def hist2d(self, x, y, bins=10, range=None, density=False, weights=None,
               cmin=None, cmax=None, cmap=None, data=None, **kwargs):
        """2-D histogram rasterised through `imshow`; returns
        `(counts, xedges, yedges, image)`."""
        if data is not None:
            x = data[x] if isinstance(x, str) else x
            y = data[y] if isinstance(y, str) else y
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
               reduce_C_function=None, mincnt=None, marginals=False, data=None, **kwargs):
        """Hexagonal binning: one coloured hexagon per occupied grid cell."""
        if data is not None:
            x = data[x] if isinstance(x, str) else x
            y = data[y] if isinstance(y, str) else y
            C = data[C] if isinstance(C, str) else C
        x = np.asarray(x, dtype=np.float64).ravel()
        y = np.asarray(y, dtype=np.float64).ravel()
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
        if x.size == 0:
            handle = Collection(colors=[])
            self.add_collection(handle)
            return handle
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
        self._append_band(dict(
            x=np.ascontiguousarray(xs), y=np.ascontiguousarray(ys),
            color="#000000", alpha=None if alpha is None else float(alpha), label="",
            cells=int(shown.size),
            cell_colors="".join(c[1:] for c in colors), gid="",
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
        family = _family_override(kwargs)
        color = color or kwargs.get("color") or rcParams.get("text.color", "black")
        xytext = kwargs.get("xytext", xytext)
        xy = _as_f64(xy)
        xytext = None if xytext is None else _as_f64(xytext)
        self.annotations.append((_mathtext(text, family), (float(xy[0]), float(xy[1])),
                                 None if xytext is None else (float(xytext[0]), float(xytext[1])),
                                 _norm_color(color), size, family or ""))
        art = _TextArt(str(text))
        art.arrow_patch = _TextArt()
        return art

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
        if x.size != y.size:
            raise ValueError("x and y must have the same length")
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

    def streamplot(self, x, y, u, v, density=1, linewidth=None, color=None,
                   cmap=None, norm=None, arrowsize=1, arrowstyle="-|>",
                   minlength=0.1, maxlength=4.0, integration_direction="both",
                   broken_streamlines=True, start_points=None, num_arrows=1,
                   integration_max_step_scale=1.0,
                   integration_max_error_scale=1.0, **kwargs):
        """Draw streamlines for a 2-D vector field.

        This is a compact integrator: it seeds a regular grid (or the supplied
        `start_points`), integrates the normalised field with a midpoint step,
        and draws each streamline as a segment collection so colour can vary
        along the path.
        """
        if integration_max_step_scale <= 0:
            raise ValueError("The value of integration_max_step_scale must be > 0")
        if integration_max_error_scale <= 0:
            raise ValueError("The value of integration_max_error_scale must be > 0")
        if integration_direction not in ("forward", "backward", "both"):
            raise ValueError(f"unsupported integration_direction: {integration_direction!r}")
        xs, ys, uu, vv, mask = _streamplot_field(x, y, u, v)
        x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
        dx = abs(xs[1] - xs[0]) if xs.size > 1 else 1.0
        dy = abs(ys[1] - ys[0]) if ys.size > 1 else 1.0
        step = 0.5 * min(dx, dy)
        max_distance = float(maxlength) * max(x1 - x0, y1 - y0, 1.0)
        max_steps = min(600, max(10, int(np.ceil(max_distance / max(step, 1e-12)))))

        if start_points is not None:
            seeds = np.asarray(start_points, dtype=float)
            if seeds.ndim == 1:
                seeds = seeds.reshape(1, -1)
            if seeds.shape[0] == 2 and seeds.shape[1] != 2:
                seeds = seeds.T
            seeds = seeds[:, :2]
        else:
            dens = np.asarray(density, dtype=float).ravel()
            if dens.size == 1:
                dens = np.repeat(dens, 2)
            nx = max(2, int(round((xs.size - 1) / 10.0 * dens[0])))
            ny = max(2, int(round((ys.size - 1) / 10.0 * dens[1])))
            seeds = np.array([[sx, sy] for sy in np.linspace(y0, y1, ny)
                              for sx in np.linspace(x0, x1, nx)])

        sampler = _streamplot_sampler(xs, ys, uu, vv, mask)

        def field(px, py):
            ux, vy = sampler(px, py)
            speed = _math.hypot(ux, vy)
            if not np.isfinite(speed) or speed <= 1e-12:
                return None
            return ux / speed, vy / speed

        def advance(px, py, sign):
            first = field(px, py)
            if first is None:
                return None
            mx = px + sign * step * 0.5 * first[0]
            my = py + sign * step * 0.5 * first[1]
            mid = field(mx, my)
            if mid is None:
                return None
            return px + sign * step * mid[0], py + sign * step * mid[1]

        def trace(sx, sy, sign):
            points = [(float(sx), float(sy))]
            px, py, travelled = float(sx), float(sy), 0.0
            for _ in range(max_steps):
                nxt = advance(px, py, sign)
                if nxt is None:
                    break
                nxv, nyv = nxt
                if not (x0 - step <= nxv <= x1 + step and y0 - step <= nyv <= y1 + step):
                    break
                travelled += _math.hypot(nxv - px, nyv - py)
                if travelled > max_distance:
                    break
                points.append((nxv, nyv))
                px, py = nxv, nyv
            return points

        trajectories = []
        for sx, sy in seeds:
            if not (x0 <= sx <= x1 and y0 <= sy <= y1):
                continue
            if integration_direction == "forward":
                pts = trace(sx, sy, 1)
            elif integration_direction == "backward":
                pts = trace(sx, sy, -1)
            else:
                back = trace(sx, sy, -1)[1:]
                pts = list(reversed(back)) + trace(sx, sy, 1)
            if len(pts) >= 2:
                trajectories.append(np.asarray(pts, dtype=float))

        color_values = None
        if color is not None and not isinstance(color, str):
            candidate = np.asarray(color)
            if candidate.shape == uu.shape and candidate.dtype.kind in "iuf":
                color_values = np.asarray(candidate, dtype=float)
        if color_values is not None:
            vals = color_values[np.isfinite(color_values)]
            lo = float(vals.min()) if vals.size else 0.0
            hi = float(vals.max()) if vals.size else 1.0
            if not hi > lo:
                lo, hi = lo - 0.5, lo + 0.5
            cmap_obj = get_cmap(cmap)
            color_at = lambda px, py: cmap_obj((_streamplot_sample(color_values, xs, ys, px, py) - lo) / (hi - lo))
        else:
            uniform = _norm_color(color) if color is not None else self._next_color()
            color_at = lambda px, py: uniform

        linewidth_values = None
        if linewidth is not None and not np.isscalar(linewidth):
            candidate = np.asarray(linewidth, dtype=float)
            if candidate.shape == uu.shape:
                linewidth_values = candidate
        if linewidth_values is not None:
            widths = linewidth_values[np.isfinite(linewidth_values)]
            line_width = float(widths.mean()) if widths.size else 2.0
        else:
            line_width = 2.0 if linewidth is None else float(linewidth)

        segments, colors, shown_values = [], [], []
        arrow_segments, arrow_colors = [], []
        for pts in trajectories:
            good = np.isfinite(pts).all(axis=1)
            pts = pts[good]
            if len(pts) < 2:
                continue
            for i in range(len(pts) - 1):
                p0, p1 = pts[i], pts[i + 1]
                if np.allclose(p0, p1):
                    continue
                segments.append(np.vstack([p0, p1]).ravel().tolist())
                mid = (p0 + p1) * 0.5
                colors.append(color_at(mid[0], mid[1]))
                if color_values is not None:
                    shown_values.append(_streamplot_sample(color_values, xs, ys, mid[0], mid[1]))
            if num_arrows and arrowsize and arrowsize > 1e-3 and len(pts) > 2:
                count = max(1, int(num_arrows))
                for idx in np.linspace(1, len(pts) - 1, count, endpoint=False):
                    i = int(np.clip(round(idx), 1, len(pts) - 1))
                    tip = pts[i]
                    direction = pts[i] - pts[i - 1]
                    norm = _math.hypot(direction[0], direction[1])
                    if not norm:
                        continue
                    direction = direction / norm
                    normal = np.array([-direction[1], direction[0]])
                    size = 0.45 * min(dx, dy)
                    left = tip - direction * size + normal * size * 0.45
                    right = tip - direction * size - normal * size * 0.45
                    arrow_segments.append(np.vstack([left, tip, right]).ravel().tolist())
                    arrow_colors.append(color_at(tip[0], tip[1]))

        segments.extend(arrow_segments)
        colors.extend(arrow_colors)
        lines = LineCollection(segments, colors=colors, linewidths=line_width,
                               label=kwargs.get("label", ""))
        lines.axes = self
        lines._array = np.asarray(shown_values) if shown_values else None
        lines._cmap = _cmap_name(cmap) if color_values is not None else None
        if color_values is not None:
            vals = color_values[np.isfinite(color_values)]
            lines._clim = ((float(vals.min()), float(vals.max()))
                           if vals.size else None)
        self.add_collection(lines)
        arrows = Collection(colors=[])
        return _StreamplotSet(lines, arrows)

    def quiver(self, *args, U=None, V=None, C=None, color=None, angles="xy",
               scale=None, scale_units=None, units="width", width=None,
               headwidth=3.0, headlength=5.0, headaxislength=4.5, pivot="tail",
               **kwargs):
        """Vector field arrows from `quiver(U, V)` or `quiver(X, Y, U, V)`.

        `scale` and `units` set the arrow length from the finished axes box, as
        in Matplotlib; `pivot` places the arrow at its tail, middle or tip."""
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
        supported_units = ("width", "height", "dots", "inches", "x", "y", "xy")
        if units not in supported_units:
            raise ValueError(f"unsupported units: {units!r}")
        if scale_units is not None and scale_units not in supported_units:
            raise ValueError(f"unsupported scale_units: {scale_units!r}")
        if isinstance(scale, str):
            if scale != "auto":
                raise ValueError(f"unsupported scale: {scale!r}")
            scale = None
        if scale is not None:
            scale = float(scale)
            if scale == 0.0:
                raise ValueError("scale must not be zero")
        # Matplotlib sizes arrows from the axes box, so keep U/V in data units
        # and hand `scale`/`units` to the renderer.
        colors = (_line_colors(color, x.size) if color is not None
                  else [self._next_color()])
        entry = dict(x=np.ascontiguousarray(x), y=np.ascontiguousarray(y),
                     u=np.ascontiguousarray(u), v=np.ascontiguousarray(v),
                     colors=colors,
                     scale=scale, units=str(units),
                     scale_units=None if scale_units is None else str(scale_units),
                     angles=str(angles),
                     width=None if width is None else _number(width, 0.005),
                     headwidth=_number(headwidth, 3.0),
                     headlength=_number(headlength, 5.0),
                     headaxislength=_number(headaxislength, 4.5),
                     pivot="middle" if pivot == "mid" else str(pivot))
        self.arrows.append(entry)
        return _QuiverHandle(entry)

    def quiverkey(self, Q, X, Y, U, label, **kwargs):
        """Accept the quiver-key annotation; keys are not drawn yet."""
        return None

    def errorbar(self, x, y, yerr=None, xerr=None, fmt="", ecolor=None, elinewidth=None,
                 capsize=None, label="", color=None, **kwargs):
        """Plot `y` against `x` with vertical (`yerr`) and/or horizontal (`xerr`)
        error bars; each error may be a scalar, a length-N array, or (2, N) lo/hi."""
        x = _as_f64(self._xdate(x))
        y = _as_f64(y)
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
            self._append_series(_series(x, y, label, c, linewidth=elw))
        self.errors.append((np.ascontiguousarray(x), np.ascontiguousarray(y), ylo, yhi,
                            xlo, xhi, c, float(capsize or 0.0) * 1.4))
        _, _, marker = _stem_fmt(fmt, "")
        if marker:
            self.scatter(x, y, s=36, c=c, marker=marker)

    def contour(self, *args, levels=None, colors=None, cmap=None, linewidths=None,
                alpha=None, locator=None, **kwargs):
        """Iso-lines of a 2-D array: `contour(Z)` or `contour(X, Y, Z)`, optionally
        followed by `levels`. Matplotlib contour kwargs are accepted."""
        return self._add_contour(args, levels, colors, cmap, False, linewidths,
                                 alpha, locator)

    def contourf(self, *args, levels=None, colors=None, cmap=None, linewidths=None,
                 alpha=None, locator=None, **kwargs):
        """Filled iso-bands of a 2-D array; takes the same forms as `contour`."""
        return self._add_contour(args, levels, colors, cmap, True, linewidths,
                                 alpha, locator)

    def triplot(self, *args, **kwargs):
        """Draw the edges of an unstructured triangular grid.

        Accepts `triplot(triangulation, fmt, ...)` or `triplot(x, y, triangles,
        fmt, ...)`; a missing triangle array asks for a Delaunay triangulation.
        """
        triangulation, _, rest = _tri_args(args)
        fmt = rest[0] if rest and isinstance(rest[0], str) else None
        edges = triangulation.get_masked_triangles()
        if len(edges) == 0:
            return []
        ex, ey = [], []
        for a, b, c in edges:
            for i, j in ((a, b), (b, c), (c, a)):
                ex.extend((triangulation.x[i], triangulation.x[j], np.nan))
                ey.extend((triangulation.y[i], triangulation.y[j], np.nan))
        color = kwargs.pop("color", kwargs.pop("c", None))
        return self.plot(np.asarray(ex), np.asarray(ey), fmt or "-",
                         color=color, **kwargs)

    def tricontour(self, *args, levels=None, colors=None, cmap=None,
                   linewidths=None, alpha=None, **kwargs):
        """Iso-lines of data on an unstructured triangular grid."""
        triangulation, z, rest = _tri_args(args)
        if levels is None and rest:
            levels = rest[0]
        xi, yi, zi = _tri_field(triangulation, z)
        return self.contour(xi, yi, zi, levels=levels, colors=colors, cmap=cmap,
                            linewidths=linewidths, alpha=alpha, **kwargs)

    def tricontourf(self, *args, levels=None, colors=None, cmap=None,
                    linewidths=None, alpha=None, **kwargs):
        """Filled iso-bands of data on an unstructured triangular grid."""
        triangulation, z, rest = _tri_args(args)
        if levels is None and rest:
            levels = rest[0]
        xi, yi, zi = _tri_field(triangulation, z)
        return self.contourf(xi, yi, zi, levels=levels, colors=colors, cmap=cmap,
                             linewidths=linewidths, alpha=alpha, **kwargs)

    def tripcolor(self, *args, shading="flat", facecolors=None, edgecolors=None,
                  cmap=None, vmin=None, vmax=None, alpha=None, **kwargs):
        """Pseudocolour of an unstructured triangular grid."""
        triangulation, z, _ = _tri_args(args)
        if z is None and facecolors is not None:
            values = np.asarray(facecolors, dtype=float).ravel()
            totals = np.zeros(len(triangulation.x))
            counts = np.zeros(len(triangulation.x))
            for tri, value in zip(triangulation.get_masked_triangles(), values):
                totals[tri] += value
                counts[tri] += 1
            z = np.divide(totals, counts, out=np.full_like(totals, np.nan),
                          where=counts > 0)
        if z is None:
            raise TypeError("tripcolor expects z or facecolors")
        xi, yi, zi = _tri_field(triangulation, z, resolution=140)
        image = self.pcolormesh(xi, yi, zi, cmap=cmap, vmin=vmin, vmax=vmax,
                                shading=shading, alpha=alpha, **kwargs)
        if edgecolors is not None:
            self.triplot(triangulation, color=edgecolors)
        return image

    def _add_contour(self, args, levels, colors, cmap, filled, linewidths=None,
                     alpha=None, locator=None):
        x, y, z, levels = _contour_args(args, levels)
        levels = _levels(z, levels, allow_single=not filled, locator=locator)
        if linewidths is None:
            widths = []
        elif np.isscalar(linewidths):
            widths = [float(linewidths)]
        else:
            widths = [float(v) for v in np.asarray(linewidths, dtype=np.float64).ravel()]
        if widths and len(widths) not in (1, len(levels)):
            # Matplotlib cycles the sequence across levels.
            widths = [widths[i % len(widths)] for i in range(len(levels))]
        opacity = 1.0 if alpha is None else float(alpha)
        if not np.isfinite(opacity):
            raise ValueError("alpha must be finite")
        entry = dict(x=x, y=y, z=z, levels=levels, linewidths=widths,
                     colors=_colors(colors), cmap=_cmap_name(cmap), filled=filled,
                     alpha=float(np.clip(opacity, 0.0, 1.0)))
        self.contours.append(entry)
        return ContourSet(entry, axes=self)

    def set_title(self, t, fontsize=None, **kwargs):
        family = _family_override(kwargs)
        self.title = _mathtext(t, family)
        self.title_size = self._size_or(fontsize, "axes.titlesize")
        self.title_family = family

    def set_xlabel(self, t, fontsize=None, **kwargs):
        family = _family_override(kwargs)
        self.xlabel = _mathtext(t, family)
        self.xlabel_size = self._size_or(fontsize, "axes.labelsize")
        self.xlabel_family = family
        if "color" in kwargs or "labelcolor" in kwargs:
            self.xlabel_color = _norm_color(kwargs.get("color", kwargs.get("labelcolor")))

    def set_ylabel(self, t, fontsize=None, **kwargs):
        family = _family_override(kwargs)
        self.ylabel = _mathtext(t, family)
        self.ylabel_size = self._size_or(fontsize, "axes.labelsize")
        self.ylabel_family = family
        if "color" in kwargs or "labelcolor" in kwargs:
            self.ylabel_color = _norm_color(kwargs.get("color", kwargs.get("labelcolor")))

    @staticmethod
    def _size_or(value, key):
        return _font_size(value, rcParams.get(key, rcParams.get("font.size", 10.0)))

    def set_xlim(self, left=None, right=None, **kwargs):
        """Set the x limits; accepts `left`/`right` or Matplotlib's `xmin`/`xmax`."""
        left = kwargs.pop("xmin", left)
        right = kwargs.pop("xmax", right)
        if right is None and left is not None:
            candidate = np.asarray(left)
            if candidate.ndim == 1 and candidate.size == 2:
                left, right = candidate
        current = self.get_xlim()
        left = current[0] if left is None else left
        right = current[1] if right is None else right
        values = _as_f64(self._xdate((left, right)))
        lo, hi = sorted((float(values[0]), float(values[1])))
        limits = self.xlim = (lo, hi)
        self._inverted[0] = float(values[0]) > float(values[1])
        if self._share_x is not None:
            self._share_x.limits = limits
        return self.get_xlim()

    def set_ylim(self, bottom=None, top=None, **kwargs):
        """Set the y limits; accepts `bottom`/`top` or `ymin`/`ymax`."""
        bottom = kwargs.pop("ymin", bottom)
        top = kwargs.pop("ymax", top)
        if top is None and bottom is not None:
            candidate = np.asarray(bottom)
            if candidate.ndim == 1 and candidate.size == 2:
                bottom, top = candidate
        current = self.get_ylim()
        bottom = current[0] if bottom is None else bottom
        top = current[1] if top is None else top
        values = _as_f64((bottom, top))
        lo, hi = sorted((float(values[0]), float(values[1])))
        limits = self.ylim = (lo, hi)
        self._inverted[1] = float(values[0]) > float(values[1])
        if self._share_y is not None:
            self._share_y.limits = limits
        return self.get_ylim()

    def legend(self, *args, loc=None, ncol=None, ncols=None, frameon=None, fontsize=None,
               title=None, title_fontsize=None, bbox_to_anchor=None, handles=None,
               labels=None, fontfamily=None, **kwargs):
        """Show a legend. Supports placement, layout and explicit handles/labels."""
        _check_kwargs(kwargs, "legend", _LEGEND_KWARGS)
        _handles = _labels = None
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
        explicit_labels = labels if labels is not None else _labels
        if explicit_labels is not None:
            self.legend_labels = [str(v) for v in explicit_labels]
        if isinstance(loc, (tuple, list)):
            self.legend_anchor = (float(loc[0]), float(loc[1]))
            self.legend_loc = "lower left"
        else:
            normalized_loc = _normalize_legend_loc(loc)
            if normalized_loc is not None:
                self.legend_loc = normalized_loc
        cols = ncol if ncol is not None else ncols
        if cols is not None:
            self.legend_ncol = max(1, int(cols))
        if frameon is not None:
            self.legend_frameon = bool(frameon)
        if fontsize is not None:
            self.legend_fontsize = _font_size(fontsize, rcParams.get("legend.fontsize", 10.0))
        if title is not None:
            self.legend_title = _mathtext(title, _font_family(fontfamily))
        if title_fontsize is not None:
            self.legend_title_fontsize = _font_size(title_fontsize, 11.0)
        if fontfamily is not None:
            self.legend_family = _font_family(fontfamily)
        elif title is not None and self.legend_title_fontsize is None:
            self.legend_title_fontsize = _font_size(rcParams.get("legend.fontsize", 10.0)) * 1.1
        if bbox_to_anchor is not None:
            if hasattr(bbox_to_anchor, "get_points"):
                bbox_to_anchor = np.asarray(bbox_to_anchor.get_points()).ravel()
            anchor = [float(v) for v in np.asarray(bbox_to_anchor).ravel()]
            if len(anchor) not in (2, 4):
                raise ValueError("bbox_to_anchor needs 2 or 4 values")
            self.legend_anchor = (anchor[0], anchor[1])
        return _LegendHandle()

    def minorticks_on(self): self.minor_ticks = True
    def minorticks_off(self): self.minor_ticks = False
    def ticklabel_format(self, **kwargs): return None
    def set_rasterization_zorder(self, zorder):
        self._rasterization_zorder = None if zorder is None else float(zorder)

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

    def grid(self, visible=None, which="major", axis="both", **kwargs):
        """Toggle gridlines and style them (`color`, `linewidth`, `alpha`,
        `linestyle`, `axis`). `visible=None` flips the current state."""
        if axis not in ("both", "x", "y"):
            raise ValueError(f"unsupported grid axis: {axis!r}")
        if which not in ("major", "minor", "both"):
            raise ValueError(f"unsupported grid which: {which!r}")
        targets = ("major", "minor") if which == "both" else (which,)
        self.grid_axis = axis
        for target in targets:
            if target == "major":
                self.show_grid = (not self.show_grid) if visible is None else bool(visible)
                prefix, active = "grid_", self.show_grid
            else:
                self.grid_minor_show = ((not self.grid_minor_show)
                                        if visible is None else bool(visible))
                prefix, active = "grid_minor_", self.grid_minor_show
            if "color" in kwargs or "c" in kwargs:
                setattr(self, f"{prefix}color",
                        _norm_color(kwargs.get("color", kwargs.get("c"))))
            if "linewidth" in kwargs or "lw" in kwargs:
                setattr(self, f"{prefix}linewidth",
                        float(kwargs.get("linewidth", kwargs.get("lw"))))
            if "linestyle" in kwargs or "ls" in kwargs:
                setattr(self, f"{prefix}linestyle",
                        str(kwargs.get("linestyle", kwargs.get("ls"))))
            if "alpha" in kwargs:
                setattr(self, f"{prefix}alpha", float(kwargs["alpha"]))
            if active:
                # Matplotlib's default grid is light grey and thin.
                if getattr(self, f"{prefix}color") is None:
                    setattr(self, f"{prefix}color", "#b0b0b0")
                if getattr(self, f"{prefix}linewidth") is None:
                    setattr(self, f"{prefix}linewidth", 0.8)
                if getattr(self, f"{prefix}alpha") is None:
                    setattr(self, f"{prefix}alpha", 1.0)
        return None

    def tick_params(self, axis="both", **kwargs):
        """Style ticks on `axis` ("x", "y" or "both"); stored for the renderer."""
        if axis not in ("x", "y", "both"):
            raise ValueError(f"unsupported tick axis: {axis!r}")
        self.tick_params_box.update(kwargs)
        axes = ("x", "y") if axis == "both" else (axis,)
        if "y" in axes:
            # Moving the labels to one side of the axes (twinx idiom).
            left = kwargs.get("labelleft", kwargs.get("left"))
            right = kwargs.get("labelright", kwargs.get("right"))
            if right and not left:
                self._yside = "right"
            elif left and not right:
                self._yside = "left"
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
        xs = np.asarray(self._xdate(x), dtype=np.float64).ravel()
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
        return _PieResult(wedges, texts, autotexts)

    def stackplot(self, x, *ys, labels=(), colors=None, alpha=None, baseline="zero",
                  **kwargs):
        """Stacked areas: each layer fills between the running total and itself."""
        if baseline not in ("zero", "sym", "wiggle", "weighted_wiggle"):
            raise NotImplementedError(f"baseline={baseline!r} is not supported yet")
        wiggle = baseline in ("wiggle", "weighted_wiggle")
        x = np.asarray(x, dtype=np.float64).ravel()
        layers = []
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
            if layer.size != x.size:
                raise ValueError("x and y must have the same length")
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
        v = np.asarray(values, dtype=np.float64).ravel()
        if edges is None:
            e = np.arange(v.size + 1.0)
        else:
            e = np.asarray(edges, dtype=np.float64).ravel()
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
            base = np.repeat(np.asarray(baseline, dtype=float).ravel(), 2)
        if orientation == "vertical":
            self.fill_between(xs, ys, base, color=face, alpha=alpha, label=label)
        else:
            self.fill_betweenx(ys, xs, base, color=face, alpha=alpha, label=label)
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

    def _colorbar_tuple(self):
        entry = self._colorbar
        if entry is None:
            return None
        orientation = entry.get("orientation", "vertical")
        axis = "x" if orientation == "horizontal" else "y"
        return (entry["cmap"], entry["vmin"], entry["vmax"], entry["label"],
                entry.get(f"{axis}scale", "linear") == "log",
                entry.get(f"{axis}lim"), float(entry.get("log_base", 10.0)),
                orientation, entry.get("extend", "neither"),
                bool(entry.get("extendrect", False)),
                float(entry.get("extendfrac", 0.05)))

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
        bars = [dict(b, colors=[_norm_color(c) for c in b["colors"]],                              edgecolor=b["edgecolor"]) for b in bars]
        bands = [dict(b, color=_norm_color(b["color"])) for b in self.bands]
        polar_texts = []
        if getattr(self, "_polar", False):
            polar_lines, polar_texts = self._polar_grid()
            projected = []
            for s in series:
                for t, r in self._polar_segments(s["x"], s["y"]):
                    if t.size:
                        x, y = self._polar_xy(t, r)
                        projected.append(dict(s, x=x, y=y))
            series = polar_lines + projected
            clipped_bands = []
            for b in bands:
                for t, r in self._polar_segments(b["x"], b["y"]):
                    if t.size:
                        x, y = self._polar_xy(t, r)
                        clipped_bands.append(dict(b, x=x, y=y))
            bands = clipped_bands
        patches = [p for p in (_patch_entry(a) for a in self.artists) if p is not None]
        collections = [c for c in (_collection_entry(a) for a in self.artists) if c is not None]
        texts = polar_texts + [self._resolve_text(t, x0, x1, y0, y1)
                              for t in self.texts]
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
        if xticks is None:
            xticks = self._locator_ticks("x")
        yticks = self._yticks if self._yticks is not None else self._locator_ticks("y")
        yticklabels = self._yticklabels
        # A user-set major formatter decides the tick text, before the date and
        # category defaults fill it in.
        if xticklabels is None:
            xticklabels = _format_ticklabels(self.xaxis._formatter, xticks)
        if yticklabels is None:
            yticklabels = _format_ticklabels(self.yaxis._formatter, yticks)
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
        # Symlog ticks are placed in data space and transformed by the renderer;
        # always supply their labels so the raw values are shown.
        if self.xscale == "symlog":
            if xticks is None:
                xticks, xticklabels = _symlog_ticks(x0, x1, self.symlog_linthresh_x)
            elif xticklabels is None:
                xticklabels = [_symlog_label(v) for v in xticks]
        if self.yscale == "symlog":
            if yticks is None:
                yticks, yticklabels = _symlog_ticks(y0, y1, self.symlog_linthresh_y)
            elif yticklabels is None:
                yticklabels = [_symlog_label(v) for v in yticks]
        if self.xscale == "logit":
            if xticks is None:
                xticks, xticklabels = _logit_ticks(
                    x0, x1, self.logit_one_half, self.logit_use_overline)
            elif xticklabels is None:
                xticklabels = _logit_ticks(
                    x0, x1, self.logit_one_half, self.logit_use_overline)[1]
        if self.yscale == "logit":
            if yticks is None:
                yticks, yticklabels = _logit_ticks(
                    y0, y1, self.logit_one_half, self.logit_use_overline)
            elif yticklabels is None:
                yticklabels = _logit_ticks(
                    y0, y1, self.logit_one_half, self.logit_use_overline)[1]
        # plotters would pick its own mesh key points, which Python cannot see.
        # Choose the auto ticks here instead and pass them down, so the drawn
        # axis, its gridlines and get_xticks()/get_yticks() hold one list.
        if xticks is None:
            xticks = _auto_ticks(x0, x1, self.xscale == "log",
                                 float(getattr(self, "log_base", 10.0)),
                                 self._auto_tick_target("x"))
        if yticks is None:
            yticks = _auto_ticks(y0, y1, self.yscale == "log",
                                 float(getattr(self, "log_base", 10.0)),
                                 self._auto_tick_target("y"))
        # Function/custom scales draw ticks at transformed positions but label
        # them with the original data values.
        if self._xscale_forward is not None and xticklabels is None and xticks is not None:
            xticklabels = [f"{float(v):g}" for v in xticks]
        if self._yscale_forward is not None and yticklabels is None and yticks is not None:
            yticklabels = [f"{float(v):g}" for v in yticks]
        for payload in [*series, *bars, *bands]:
            payload.pop("_seq", None)
            payload.pop("_container", None)
        panel = dict(pos=self.pos, series=series, texts=texts, title=self.title,
                    font_family=_font_family(),
                    title_family=self.title_family,
                    xlabel_family=self.xlabel_family,
                    ylabel_family=self.ylabel_family,
                    dpi=float(self._fig.dpi if self._fig is not None else DPI),
                    xlabel=self.xlabel, ylabel=self.ylabel,
                    title_size=self.title_size, xlabel_size=self.xlabel_size,
                    ylabel_size=self.ylabel_size,
                    legend=dict(show=self.show_legend, loc=self.legend_loc,
                                ncol=self.legend_ncol, frameon=self.legend_frameon,
                                fontsize=legend_font, family=self.legend_family or _font_family(),
                                title=self.legend_title,
                                title_fontsize=legend_title, anchor=self.legend_anchor,
                                labels=list(self.legend_labels or []),
                                order=self._legend_order()),
                    xlim=(x0, x1), ylim=(y0, y1), annotations=self.annotations,
                    aspect=self.aspect,
                    aspect_datalim=self._adjustable == "datalim",
                    contours=contours,
                    errors=self.errors,
                    bars=bars,
                    bands=bands,
                    x_log=self.xscale == "log", y_log=self.yscale == "log",
                    x_symlog=self.xscale == "symlog", y_symlog=self.yscale == "symlog",
                    x_logit=self.xscale == "logit", y_logit=self.yscale == "logit",
                    x_asinh=self.xscale == "asinh", y_asinh=self.yscale == "asinh",
                    x_symlog_linthresh=float(self.symlog_linthresh_x),
                    y_symlog_linthresh=float(self.symlog_linthresh_y),
                    x_asinh_linear_width=float(self.asinh_linear_width_x),
                    y_asinh_linear_width=float(self.asinh_linear_width_y),
                    log_base=float(getattr(self, "log_base", 10.0)),
                    grid=dict(show=self.show_grid, color=self.grid_color,
                              linewidth=self.grid_linewidth, alpha=self.grid_alpha,
                              linestyle=self.grid_linestyle, axis=self.grid_axis,
                              minor_show=bool(self.grid_minor_show and self.minor_ticks),
                              minor_color=self.grid_minor_color,
                              minor_linewidth=self.grid_minor_linewidth,
                              minor_alpha=self.grid_minor_alpha),
                    ticks=dict(xticks=xticks, xticklabels=xticklabels,
                               yticks=yticks, yticklabels=yticklabels,
                               xstyle=self._tick_style_dict("x"),
                               ystyle=self._tick_style_dict("y"),
                               hide_xlabels=self.hide_xticklabels or self._twin == "y",
                               hide_ylabels=self.hide_yticklabels or self._twin == "x",
                               yside=self._yside),
                    scatter=[dict(x=e["x"], y=e["y"], sizes=e["sizes"], values=e["values"],
                                  cmap=e["cmap"], clim=e["clim"], colors=e["colors"],
                                  marker=e["marker"], alpha=e["alpha"], label=e["label"])
                             for e in scatter],
                    arrows=arrows,
                    colorbar=self._colorbar_tuple(),
                    axis_off=self._axis_off,
                    facecolor=_norm_color(self.facecolor or rcParams.get("axes.facecolor")),
                    foreground=_norm_color(rcParams.get("text.color")),
                    bounds=self._render_bounds(dpi), axes_bounds=self._exact_axes_box(),
                    twin=self._twin, twin_gap=self._twin_gap,
                    twin_reserve=self._twin_reserve,
                    xlabel_color=self.xlabel_color, ylabel_color=self.ylabel_color,
                    patches=patches, collections=collections,
                    images=[(im._e["data"], im._e["cmap"], im._e["vmin"],
                             im._e["vmax"], im._e["extent"], True,
                             im._e["alpha"], im._e["interpolation"])
                            for im in self.images])
        return self._apply_axis_scales(panel)

    def _apply_axis_scales(self, panel):
        """Map panel coordinates through function or registered custom scales."""
        fx, fy = self._xscale_forward, self._yscale_forward
        if fx is None and fy is None:
            return panel

        def scale(forward, values):
            return (_scale_values(forward, values) if forward is not None
                    else np.asarray(values, dtype=float))

        def scalar(forward, value):
            return float(scale(forward, [value])[0])

        def points(flat):
            pts = np.asarray(flat, dtype=float).reshape(-1, 2)
            if fx is not None:
                pts[:, 0] = _scale_values(fx, pts[:, 0])
            if fy is not None:
                pts[:, 1] = _scale_values(fy, pts[:, 1])
            return pts.ravel().tolist()

        ticks = panel["ticks"]
        if fx is not None and ticks["xticks"] is not None:
            ticks["xticks"] = [float(v) for v in scale(fx, ticks["xticks"])]
        if fy is not None and ticks["yticks"] is not None:
            ticks["yticks"] = [float(v) for v in scale(fy, ticks["yticks"])]
        panel["series"] = [
            dict(item,
                 x=_scale_values(fx, item["x"]) if fx is not None else item["x"],
                 y=_scale_values(fy, item["y"]) if fy is not None else item["y"])
            for item in panel["series"]]
        scaled_bars = []
        for item in panel["bars"]:
            bar = dict(item)
            if fx is not None:
                left = np.asarray(bar["left"], dtype=float)
                new_left = _scale_values(fx, left)
                bar["left"] = new_left
                bar["width"] = (_scale_values(fx, left + np.asarray(bar["width"], dtype=float))
                                - new_left)
            if fy is not None:
                bottom = np.asarray(bar["bottom"], dtype=float)
                new_bottom = _scale_values(fy, bottom)
                bar["bottom"] = new_bottom
                bar["height"] = (_scale_values(fy, bottom + np.asarray(bar["height"], dtype=float))
                                 - new_bottom)
            scaled_bars.append(bar)
        panel["bars"] = scaled_bars
        panel["bands"] = [
            dict(item,
                 x=_scale_values(fx, item["x"]) if fx is not None else item["x"],
                 y=_scale_values(fy, item["y"]) if fy is not None else item["y"])
            for item in panel["bands"]]
        panel["scatter"] = [
            dict(item,
                 x=_scale_values(fx, item["x"]) if fx is not None else item["x"],
                 y=_scale_values(fy, item["y"]) if fy is not None else item["y"])
            for item in panel["scatter"]]
        scaled_arrows = []
        for item in panel["arrows"]:
            arrow = dict(item)
            x = np.asarray(arrow["x"], dtype=float)
            y = np.asarray(arrow["y"], dtype=float)
            if fx is not None:
                if arrow.get("angles") == "xy":
                    u = np.asarray(arrow["u"], dtype=float)
                    new_x = _scale_values(fx, x)
                    arrow["u"] = _scale_values(fx, x + u) - new_x
                    arrow["x"] = new_x
                else:
                    arrow["x"] = _scale_values(fx, x)
            if fy is not None:
                if arrow.get("angles") == "xy":
                    v = np.asarray(arrow["v"], dtype=float)
                    new_y = _scale_values(fy, y)
                    arrow["v"] = _scale_values(fy, y + v) - new_y
                    arrow["y"] = new_y
                else:
                    arrow["y"] = _scale_values(fy, y)
            scaled_arrows.append(arrow)
        panel["arrows"] = scaled_arrows
        scaled_errors = []
        for item in panel["errors"]:
            x = np.asarray(item[0], dtype=float)
            y = np.asarray(item[1], dtype=float)
            nx, ny = x, y
            ylo, yhi, xlo, xhi = item[2], item[3], item[4], item[5]
            if fx is not None:
                nx = _scale_values(fx, x)
                xlo = nx - _scale_values(fx, x - np.asarray(item[4], dtype=float))
                xhi = _scale_values(fx, x + np.asarray(item[5], dtype=float)) - nx
            if fy is not None:
                ny = _scale_values(fy, y)
                ylo = ny - _scale_values(fy, y - np.asarray(item[2], dtype=float))
                yhi = _scale_values(fy, y + np.asarray(item[3], dtype=float)) - ny
            scaled_errors.append((nx, ny, ylo, yhi, xlo, xhi, *item[6:]))
        panel["errors"] = scaled_errors
        scaled_contours = []
        for item in panel["contours"]:
            contour = list(item)
            if fx is not None:
                contour[0] = scale(fx, contour[0])
            if fy is not None:
                contour[1] = scale(fy, contour[1])
            scaled_contours.append(tuple(contour))
        panel["contours"] = scaled_contours
        scaled_images = []
        for item in panel["images"]:
            image = list(item)
            if image[4] is not None:
                extent = list(image[4])
                if fx is not None:
                    extent[0], extent[1] = (scalar(fx, extent[0]), scalar(fx, extent[1]))
                if fy is not None:
                    extent[2], extent[3] = (scalar(fy, extent[2]), scalar(fy, extent[3]))
                image[4] = tuple(extent)
            scaled_images.append(tuple(image))
        panel["images"] = scaled_images
        scaled_texts = []
        for item in panel["texts"]:
            text = list(item)
            if fx is not None:
                text[0] = scalar(fx, text[0])
            if fy is not None:
                text[1] = scalar(fy, text[1])
            scaled_texts.append(tuple(text))
        panel["texts"] = scaled_texts
        scaled_annotations = []
        for item in panel["annotations"]:
            annotation = list(item)
            xy, xytext = annotation[1], annotation[2]
            annotation[1] = (scalar(fx, xy[0]) if fx is not None else xy[0],
                             scalar(fy, xy[1]) if fy is not None else xy[1])
            if xytext is not None:
                annotation[2] = (scalar(fx, xytext[0]) if fx is not None else xytext[0],
                                 scalar(fy, xytext[1]) if fy is not None else xytext[1])
            scaled_annotations.append(tuple(annotation))
        panel["annotations"] = scaled_annotations
        scaled_patches = []
        for item in panel["patches"]:
            patch = dict(item)
            kind = patch.get("kind")
            if kind == "rect":
                x, y = float(patch["x"]), float(patch["y"])
                w, h = float(patch["width"]), float(patch["height"])
                if fx is not None:
                    left = scalar(fx, x)
                    patch["x"], patch["width"] = left, scalar(fx, x + w) - left
                if fy is not None:
                    bottom = scalar(fy, y)
                    patch["y"], patch["height"] = bottom, scalar(fy, y + h) - bottom
            elif kind == "circle":
                x, y, r = float(patch["x"]), float(patch["y"]), float(patch["width"])
                if fx is not None:
                    left, right = scalar(fx, x - r), scalar(fx, x + r)
                    patch["x"], patch["width"] = (left + right) / 2.0, abs(right - left) / 2.0
                if fy is not None:
                    bottom, top = scalar(fy, y - r), scalar(fy, y + r)
                    patch["y"], patch["width"] = (bottom + top) / 2.0, abs(top - bottom) / 2.0
            else:
                patch["points"] = points(patch["points"])
            scaled_patches.append(patch)
        panel["patches"] = scaled_patches
        scaled_collections = []
        for item in panel["collections"]:
            collection = dict(item)
            collection["points"] = points(collection["points"])
            collection["segments"] = [points(seg) for seg in collection["segments"]]
            scaled_collections.append(collection)
        panel["collections"] = scaled_collections

        def finite_bounds(key):
            lo, hi = np.inf, -np.inf

            def take(values):
                nonlocal lo, hi
                arr = np.asarray(values, dtype=float)
                arr = arr[np.isfinite(arr)]
                if arr.size:
                    lo, hi = min(lo, float(arr.min())), max(hi, float(arr.max()))

            for item in panel["series"]:
                take(item[key])
            for item in panel["bands"]:
                take(item[key])
            for item in panel["scatter"]:
                take(item[key])
            for item in panel["bars"]:
                if key == "x":
                    take(item["left"])
                    take(np.asarray(item["left"], dtype=float)
                         + np.asarray(item["width"], dtype=float))
                else:
                    take(item["bottom"])
                    take(np.asarray(item["bottom"], dtype=float)
                         + np.asarray(item["height"], dtype=float))
            return lo, hi

        def scaled_limits(forward, current, key):
            values = scale(forward, current)
            if np.isfinite(values).all():
                return tuple(float(v) for v in values)
            lo, hi = finite_bounds(key)
            if np.isfinite(lo) and np.isfinite(hi):
                return (lo, hi) if current[0] <= current[1] else (hi, lo)
            return tuple(float(v) for v in values)

        if fx is not None:
            panel["xlim"] = scaled_limits(fx, panel["xlim"], "x")
        if fy is not None:
            panel["ylim"] = scaled_limits(fy, panel["ylim"], "y")
        return panel

    def _resolve_text(self, t, x0, x1, y0, y1):
        """Turn axes/figure coordinates into the data coordinates the renderer uses."""
        x, y, s, c, size, ha, va, kind, bbox, rotation, family, shift = t
        if kind == "axes":
            x, y = x0 + x * (x1 - x0), y0 + y * (y1 - y0)
        elif kind == "figure":
            rows, cols = self._fig.grid if self._fig is not None else (1, 1)
            row, col = divmod(self.pos, cols)
            fx0, fy0 = col / cols, (rows - 1 - row) / rows
            x = x0 + (x - fx0) * cols * (x1 - x0)
            y = y0 + (y - fy0) * rows * (y1 - y0)
        return (x, y, s, c, size, ha, va, bbox, rotation, family, shift)

    def _tick_style_dict(self, axis):
        style = self.tick_params_x if axis == "x" else self.tick_params_y
        font = float(rcParams.get("font.size", 10.0))
        default = rcParams.get(f"{axis}tick.labelsize", font)
        rotation = style.get("rotation", 0.0)
        rotation = 0.0 if rotation == "auto" else float(rotation)
        return dict(labelsize=_font_size(style.get("labelsize"), default),
                    length=float(style.get("length", 3.5)),
                    width=float(style.get("width", 1.0)),
                    color=_norm_color(style.get("labelcolor")),
                    labelcolor=_norm_color(style.get("labelcolor")),
                    rotation=rotation)


def _norm_aspect(a):
    if isinstance(a, str):
        if a == "auto": return None
        if a == "equal": return 1.0
        raise ValueError(f"unsupported aspect: {a!r} (use 'auto', 'equal' or a number)")
    a = float(a)
    if not a > 0:
        raise ValueError(f"aspect must be positive, got {a!r}")
    return a


def _figimage_payload_estimate(data):
    """Upper bound on the base64 payload for one RGBA figure image."""
    pixels = int(data.shape[0]) * int(data.shape[1])
    return (pixels * 4 + 2) // 3 * 4


def _as_image(X):
    a = np.asarray(X, dtype=np.float64)
    if a.ndim == 3 and a.shape[2] in (3, 4):
        return a
    if a.ndim == 2:
        return a
    raise ValueError("imshow expects a 2-D array or an (H, W, 3|4) RGB(A) array")


def _convert_units(values, axis, unit=None):
    """Apply a registered `matplotlib.units` converter, if the data has one."""
    if values is None:
        return values
    items = _as_list(values)
    if (np.ndim(items) == 0 or not hasattr(items, "__getitem__")
            or np.asarray(items).size == 0):
        return values
    converter = units.registry.get_converter(np.asarray(items).ravel()[0])
    if converter is None:
        return values
    if unit is None:
        unit = converter.default_units(values, axis)
    info = converter.axisinfo(unit, axis)
    if info is not None:
        if info.label:
            axis.set_label_text(info.label)
        if info.majloc is not None:
            axis.set_major_locator(info.majloc)
        if info.majfmt is not None:
            axis.set_major_formatter(info.majfmt)
    return converter.convert(values, unit, axis)


def _series(x, y, label, color, linestyle="-", linewidth=2.0, marker="", markersize=6.0,
            mfc=None, mec=None, mew=1.0, alpha=None, drawstyle="default", gid=""):
    return dict(x=_as_f64(x), y=_as_f64(y),
                label=str(label), color=_norm_color(color), linestyle=str(linestyle),
                linewidth=float(linewidth), marker=str(marker), markersize=float(markersize),
                mfc=_norm_color(mfc), mec=_norm_color(mec), mew=float(mew),
                alpha=None if alpha is None else float(alpha), drawstyle=str(drawstyle),
                gid=str(gid or ""))


def _streamplot_field(x, y, u, v):
    """Validate and unpack a streamplot's rectangular vector field."""
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    mask = np.ma.getmaskarray(u) if np.ma.isMaskedArray(u) else None
    ua = np.asarray(np.ma.filled(u, np.nan), dtype=float)
    va = np.asarray(np.ma.filled(v, np.nan), dtype=float)
    if ua.ndim > 2 or va.ndim > 2:
        raise ValueError("'u' and 'v' can have at maximum 2 dimensions")
    if ua.shape != va.shape:
        raise ValueError("U and V must have the same shape")
    if xa.ndim > 2 or ya.ndim > 2:
        raise ValueError("'x' and 'y' can have at maximum 2 dimensions")
    if xa.ndim == 1 and ya.ndim == 1:
        if xa.size == ua.shape[1] and ya.size == ua.shape[0]:
            xa, ya = np.meshgrid(xa, ya)
        elif xa.size == ua.size and ya.size == ua.size:
            xa, ya = xa.reshape(ua.shape), ya.reshape(ua.shape)
        else:
            raise ValueError("X and Y must match U's shape or one axis each")
    if xa.shape != ua.shape or ya.shape != ua.shape:
        raise ValueError("X, Y, U and V must have the same shape")
    if not np.allclose(xa, xa[0:1, :]):
        raise ValueError("The rows of 'x' must be equal")
    if not np.allclose(ya, ya[:, 0:1]):
        raise ValueError("The columns of 'y' must be equal")
    xs, ys = np.asarray(xa[0, :], dtype=float), np.asarray(ya[:, 0], dtype=float)
    if xs.size < 2 or ys.size < 2:
        raise ValueError("streamplot needs at least a 2x2 grid")
    for values, name in ((xs, "x"), (ys, "y")):
        spacing = np.diff(values)
        if spacing.size > 1 and not np.allclose(spacing, spacing[0], rtol=1e-7, atol=1e-12):
            raise ValueError(f"'{name}' values must be equally spaced")
        if not np.all(spacing > 0):
            raise ValueError(f"'{name}' values must be strictly increasing")
    if mask is None:
        mask = ~np.isfinite(ua)
    else:
        mask = np.asarray(mask, dtype=bool) | ~np.isfinite(ua)
    ua = np.where(mask, np.nan, ua)
    va = np.where(mask, np.nan, va)
    return xs, ys, ua, va, mask


def _streamplot_bracket(values, coordinate):
    if coordinate < values[0] or coordinate > values[-1]:
        return None, None
    index = int(np.searchsorted(values, coordinate, side="right") - 1)
    index = min(max(index, 0), len(values) - 2)
    t = (coordinate - values[index]) / (values[index + 1] - values[index])
    return index, float(t)


def _streamplot_sample(values, xs, ys, px, py):
    """Bilinear sample of a scalar field, returning NaN outside the grid."""
    ix, tx = _streamplot_bracket(xs, px)
    iy, ty = _streamplot_bracket(ys, py)
    if ix is None or iy is None:
        return float("nan")
    v00, v01 = values[iy, ix], values[iy, ix + 1]
    v10, v11 = values[iy + 1, ix], values[iy + 1, ix + 1]
    return float((1 - tx) * (1 - ty) * v00 + tx * (1 - ty) * v01
                 + (1 - tx) * ty * v10 + tx * ty * v11)


def _streamplot_sampler(xs, ys, u, v, mask):
    """Bilinear vector-field sampler that rejects samples touching a mask."""
    def sample(px, py):
        ix, tx = _streamplot_bracket(xs, px)
        iy, ty = _streamplot_bracket(ys, py)
        if ix is None or iy is None:
            return float("nan"), float("nan")
        if mask[iy:iy + 2, ix:ix + 2].any():
            return float("nan"), float("nan")
        weights = ((1 - tx) * (1 - ty), tx * (1 - ty),
                   (1 - tx) * ty, tx * ty)
        ux = (weights[0] * u[iy, ix] + weights[1] * u[iy, ix + 1]
              + weights[2] * u[iy + 1, ix] + weights[3] * u[iy + 1, ix + 1])
        vy = (weights[0] * v[iy, ix] + weights[1] * v[iy, ix + 1]
              + weights[2] * v[iy + 1, ix] + weights[3] * v[iy + 1, ix + 1])
        return float(ux), float(vy)
    return sample


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
        # Change detection, not security: SHA-1 hashes large arrays ~2.7x faster
        # than BLAKE2b (the hash was over half of a 1M-point scatter save).
        hasher = _hashlib.sha1(usedforsecurity=False)
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
    if len(args) >= 2:
        return (pick(args[0]), pick(args[1]), *args[2:])
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
Line2D.markers: ClassVar[dict[str, str]] = {
    **{marker: "marker" for marker in sorted(_MARKERS)},
    "None": "nothing", "none": "nothing", " ": "nothing", "": "nothing"}
Line2D.filled_markers = tuple("osD^v<>pP*hHX")
Line2D.fillStyles = ("full", "left", "right", "bottom", "top", "none")


class MarkerStyle:
    """Marker descriptor, as `matplotlib.markers.MarkerStyle`."""

    markers: ClassVar[dict[str, None]] = {
        **{name: None for name in sorted(_MARKERS)},
        "None": None, "none": None, " ": None, "": None}
    filled_markers = tuple("osD^v<>pP*hHX")

    def __init__(self, marker="o", fillstyle=None, transform=None,
                 capstyle=None, joinstyle=None):
        if isinstance(marker, MarkerStyle):
            marker = marker.get_marker()
        self._marker = marker
        self._fillstyle = "full" if fillstyle is None else str(fillstyle)

    def get_marker(self): return self._marker
    def set_marker(self, marker): self._marker = marker; return self
    def get_fillstyle(self): return self._fillstyle
    def set_fillstyle(self, fillstyle): self._fillstyle = str(fillstyle); return self
    def get_transform(self): return _Transform()
    def get_alt_transform(self): return _Transform()
    def get_capstyle(self): return "butt"
    def get_joinstyle(self): return "round"
    def get_snap_threshold(self): return None
    def is_filled(self):
        return self._fillstyle == "full" and str(self._marker) in self.filled_markers
    def get_path(self): return Path.unit_circle()
    def get_alt_path(self): return None
    def rotated(self, *args, **kwargs): return self
    def scaled(self, *args, **kwargs): return self
    def __str__(self): return str(self._marker)
    def __repr__(self): return f"MarkerStyle({self._marker!r})"


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
    if not style:
        style = "None" if mark else "-"
    return color, style, mark


def _log_bounds(lo, hi, scale, extent):
    """Log axes can only cover positive data; the lower bound climbs to the
    smallest positive sample when the data crosses zero.

    Avoids evaluating extent if scale is not 'log'.
    """
    lo, hi = float(lo), float(hi)
    if scale != "log":
        return (lo, hi)
    extent_vals = extent() if callable(extent) else extent
    positive = [float(v) for v in extent_vals if v > 0]
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
    values = list(colors) if isinstance(colors, (list, tuple, np.ndarray)) else []
    if len(values) == n and all(_is_rgb(c) for c in values):
        return [_norm_color(c) for c in values]
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
    arr = np.asarray(_as_list(v))
    if arr.dtype.kind == "O":
        def number(item):
            if item is None or np.ma.is_masked(item):
                return np.nan
            if isinstance(item, (np.datetime64, _datetime.date)):
                return _datetime_to_num(item)
            if hasattr(item, "_seconds") and hasattr(item, "frame"):
                return float(item._seconds)
            if hasattr(item, "_jd"):
                return float(item._jd + getattr(item, "_seconds", 0.0) / 86400.0)
            if hasattr(item, "get_value"):
                value = item.get_value()
                if np.isscalar(value):
                    return float(value)
            if hasattr(item, "_value"):
                return float(item._value)
            if hasattr(item, "value"):
                return float(item.value)
            return float(item)
        arr = np.asarray([number(item) for item in arr.ravel()],
                         dtype=np.float64).reshape(arr.shape)
    return np.ascontiguousarray(np.asarray(arr, dtype=np.float64).ravel())


def _band(xs, ys, color, alpha, label=""):
    return dict(x=_as_f64(xs), y=_as_f64(ys), color=_norm_color(color),
                alpha=None if alpha is None else float(alpha), label=str(label),
                cells=0, cell_colors="", gid="")


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
    a = _as_f64(values)
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


def _boxplot_stats(x, whis=1.5, bootstrap=None, labels=None, autorange=False):
    """Matplotlib-compatible `cbook.boxplot_stats` for `Axes.bxp`."""
    groups = _box_datasets(x)
    if labels is None:
        names = [""] * len(groups)
    elif isinstance(labels, str):
        names = [labels] + [""] * (len(groups) - 1)
    else:
        names = [str(v) for v in labels]
    stats = []
    for index, raw in enumerate(groups):
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
        stats.append(dict(
            label=names[index] if index < len(names) else "",
            mean=float(vals.mean()), iqr=float(iqr), q1=q1, med=med, q3=q3,
            whislo=lo, whishi=hi, fliers=[float(v) for v in fliers],
            cilo=None, cihi=None))
    return stats


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
    # Matplotlib evaluates the density between the data extremes only, so the
    # violin ends exactly at its extrema and the extremes bars sit on the tips.
    grid = np.linspace(lo, hi, max(int(points), 2))
    z = (grid[:, None] - vals[None, :]) / bw
    density = np.exp(-0.5 * z * z).sum(axis=1) / (n * bw * np.sqrt(2.0 * np.pi))
    return grid, density


def _cmap_colors(cmap, values):
    """Map normalised values through any registered colormap to hex colours."""
    arr = np.asarray(values, dtype=np.float64).ravel()
    clean = np.where(np.isfinite(arr), arr, 0.0)
    rgb = np.asarray(get_cmap(cmap)(clean, bytes=True))[:, :3]
    return [f"#{int(r):02x}{int(g):02x}{int(b):02x}" for r, g, b in rgb]


def _bar_colors(color, n):
    """One colour per bar; a short list cycles, as Matplotlib's fill loop does."""
    if color is None:
        return []
    if isinstance(color, str) or _is_rgb(color):
        return [_norm_color(color)]
    array = np.asarray(color)
    if array.ndim == 2 and array.shape[1] in (3, 4):
        vals = [_norm_color(row) for row in array]
    else:
        vals = [_norm_color(v) for v in np.asarray(_as_list(color), dtype=object).ravel()]
    if not vals:
        return []
    return [vals[i % len(vals)] for i in range(n)]


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


def _is_color_sequence(value):
    """A list of colour specs, e.g. `[cmap(0.2), cmap(0.4)]`."""
    if not isinstance(value, (list, tuple)) or not value:
        return False
    return all(isinstance(v, str) or _is_rgb(v) for v in value)


def _scatter_colors(c, n):
    """Split `c` into (numeric values for cmap, explicit colour strings)."""
    if c is None:
        return None, []
    if isinstance(c, str) or _is_rgb(c):
        return None, [_norm_color(c)]
    if _is_color_sequence(c):
        seq = list(c)
        if len(seq) not in (1, n):
            raise ValueError("c must be a single colour or one colour per point")
        return None, [_norm_color(seq[i % len(seq)]) for i in range(n)]
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
    if _looks_like_dates(x):
        x = _date_to_num(x)
    if _looks_like_dates(y):
        y = _date_to_num(y)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim == 2 or y.ndim == 2:
        if x.ndim != 2 or y.ndim != 2 or x.shape != y.shape:
            raise ValueError("pcolormesh 2-D X and Y must have the same shape")
        if x.shape == (rows + 1, cols + 1):
            if not (np.allclose(x, x[0:1, :]) and np.allclose(y, y[:, 0:1])):
                return (np.array([float(x.min()), float(x.max())]),
                        np.array([float(y.min()), float(y.max())]), z, True)
            x, y = x[0, :], y[:, 0]
        elif x.shape == z.shape:
            if not (np.allclose(x, x[0:1, :]) and np.allclose(y, y[:, 0:1])):
                return (np.array([float(x.min()), float(x.max())]),
                        np.array([float(y.min()), float(y.max())]), z, True)
            x, y = x[0, :], y[:, 0]
        else:
            raise ValueError("2-D X and Y must match Z's shape or have one extra edge")
    x, y = x.ravel(), y.ravel()
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
    if np.isscalar(err) or not np.iterable(err):
        v = np.full(n, abs(float(_as_f64(err)[0])))
        return v, v.copy()
    raw = np.asarray(err, dtype=object)
    if raw.ndim == 2:
        a = np.asarray([_as_f64(row) for row in err])
    else:
        a = _as_f64(err)
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


def _levels(z, levels, allow_single=False, locator=None):
    lo, hi = float(np.nanmin(z)), float(np.nanmax(z))
    if not hi > lo:
        hi = lo + 1.0
    if locator is not None and levels is None:
        values = np.asarray(locator.tick_values(lo, hi), dtype=float).ravel()
        values = values[np.isfinite(values)]
        if isinstance(locator, _LogLocator) and values.size:
            base = locator.base if locator.base > 1.0 else 10.0
            values = np.concatenate(([values[0] / base], values,
                                     [values[-1] * base]))
        if values.size >= (1 if allow_single else 2):
            return [float(v) for v in np.unique(values)]
    if levels is None:
        return [float(v) for v in np.linspace(lo, hi, 7)]
    if isinstance(levels, (int, np.integer)):
        if levels < 2:
            raise ValueError("levels must be at least 2")
        return [float(v) for v in np.linspace(lo, hi, int(levels))]
    lv = np.atleast_1d(np.asarray(levels, dtype=np.float64)).ravel()
    if lv.size < (1 if allow_single else 2):
        raise ValueError("levels needs at least two entries")
    return [float(v) for v in np.sort(lv)]


def _colors(colors):
    if colors is None:
        return []
    if isinstance(colors, str) or _is_rgb(colors):
        return [_norm_color(colors)]
    return [_norm_color(c) for c in colors]


def _is_triangulation(value):
    return all(hasattr(value, name) for name in ("x", "y", "triangles", "mask"))


def _tri_args(args):
    """Resolve (triangulation, z, remaining) from tripcolor-style arguments."""
    if not args:
        raise TypeError("expected a triangulation or x, y arrays")
    if _is_triangulation(args[0]):
        triangulation = args[0]
        rest = list(args[1:])
    elif len(args) >= 3 and np.asarray(args[2]).ndim == 2:
        x, y, triangles = args[:3]
        triangulation = tri.Triangulation(x, y, triangles)
        rest = list(args[3:])
    else:
        if len(args) < 2:
            raise TypeError("expected x and y coordinates")
        x, y = args[:2]
        triangulation = tri.Triangulation(x, y)
        rest = list(args[2:])
    z = rest.pop(0) if rest else None
    return triangulation, z, rest


def _tri_field(triangulation, z, resolution=100):
    """Sample a triangular field on a rectilinear grid for the contour path."""
    values = np.asarray(z, dtype=float).ravel()
    if values.size != len(triangulation.x):
        raise ValueError("z must have one value per triangulation point")
    xi = np.linspace(float(np.min(triangulation.x)),
                     float(np.max(triangulation.x)), resolution)
    yi = np.linspace(float(np.min(triangulation.y)),
                     float(np.max(triangulation.y)), resolution)
    gx, gy = np.meshgrid(xi, yi)
    zi = tri.LinearTriInterpolator(triangulation, values)(gx, gy)
    return xi, yi, zi


def _contour_args(args, levels):
    if args and isinstance(args[0], ContourSet):
        # `contour(cs, ...)` re-contours an existing set at new levels.
        if levels is None and len(args) > 1:
            levels = args[1]
        entry = args[0]._e
        return entry["x"], entry["y"], entry["z"], levels
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
    if _looks_like_dates(x):
        x = _date_to_num(x)
    if _looks_like_dates(y):
        y = _date_to_num(y)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim == 2 or y.ndim == 2:
        if x.shape != z.shape or y.shape != z.shape:
            raise ValueError("2-D X and Y must match Z's shape")
        # Keep the 1-D coordinates when the grid is rectilinear. `meshgrid`
        # puts x along columns, while `mgrid` puts it along rows.
        if np.allclose(x, x[0:1, :]) and np.allclose(y, y[:, 0:1]):
            x, y = x[0, :], y[:, 0]
        elif np.allclose(x, x[:, 0:1]) and np.allclose(y, y[0:1, :]):
            x, y, z = y[0, :], x[:, 0], z.T
        else:
            raise NotImplementedError("only rectilinear X/Y grids are supported")
    x, y = x.ravel(), y.ravel()
    if x.size != cols or y.size != rows:
        raise ValueError("expected len(X) == Z.shape[1] and len(Y) == Z.shape[0]")
    return (np.ascontiguousarray(x), np.ascontiguousarray(y),
            np.ascontiguousarray(z), levels)


def _contour_segments(x, y, z, level):
    """Marching-squares iso-line segments for one level on a rectilinear grid."""
    segments = []
    rows, cols = z.shape
    for i in range(rows - 1):
        for j in range(cols - 1):
            values = (z[i, j], z[i, j + 1], z[i + 1, j + 1], z[i + 1, j])
            if not all(_math.isfinite(float(v)) for v in values):
                continue
            corners = ((x[j], y[i]), (x[j + 1], y[i]),
                       (x[j + 1], y[i + 1]), (x[j], y[i + 1]))
            crossings = []
            for k in range(4):
                a, b = values[k], values[(k + 1) % 4]
                if (a < level <= b) or (b < level <= a):
                    t = (level - a) / (b - a)
                    (xa, ya), (xb, yb) = corners[k], corners[(k + 1) % 4]
                    crossings.append((xa + t * (xb - xa), ya + t * (yb - ya)))
            if len(crossings) == 2:
                segments.append((crossings[0], crossings[1]))
            elif len(crossings) == 4:
                segments.extend([(crossings[0], crossings[1]),
                                 (crossings[2], crossings[3])])
    return segments


def _contour_label_text(level, fmt):
    if callable(fmt):
        return str(fmt(level))
    if isinstance(fmt, dict):
        return str(fmt.get(level, f"{level:g}"))
    if fmt is None:
        magnitude = abs(level)
        text = (f"{level:g}" if magnitude >= 1000.0 or 0.0 < magnitude < 1e-3
                else f"{level:.3f}".rstrip("0").rstrip("."))
        return text.replace("-", "\u2212")
    return str(fmt % level)


def _contour_label_colour(entry, index, level):
    """The colour the renderer uses for this level's line."""
    colours = entry.get("colors") or []
    if colours:
        return _norm_color(colours[index % len(colours)])
    levels = entry["levels"]
    lo, hi = float(levels[0]), float(levels[-1])
    t = (level - lo) / (hi - lo) if hi > lo else 0.5
    rgb = np.asarray(get_cmap(entry.get("cmap"))(t), dtype=float).ravel()[:3]
    return "#{:02x}{:02x}{:02x}".format(*tuple(int(round(float(v) * 255)) for v in rgb))


def _point_segment_distance(px, py, xa, ya, xb, yb):
    """Shortest distance from a point to a line segment."""
    dx, dy = xb - xa, yb - ya
    length = dx * dx + dy * dy
    if length == 0.0:
        return _math.hypot(px - xa, py - ya)
    t = max(0.0, min(1.0, ((px - xa) * dx + (py - ya) * dy) / length))
    return _math.hypot(px - (xa + t * dx), py - (ya + t * dy))


def _path_subpaths(vertices, codes):
    """Split a compound path into rings, dropping CLOSEPOLY placeholders."""
    verts = np.asarray(vertices, dtype=float).reshape(-1, 2)
    if codes is None:
        return [verts] if len(verts) else []
    codes = np.asarray(codes).ravel()
    if codes.size != len(verts):
        return [verts] if len(verts) else []
    starts = [i for i, code in enumerate(codes) if code == Path.MOVETO]
    if not starts:
        return [verts] if len(verts) else []
    starts.append(len(verts))
    out = []
    for start, stop in zip(starts, starts[1:]):
        ring, ring_codes = verts[start:stop], codes[start:stop]
        if (ring_codes.size and ring_codes[-1] == Path.CLOSEPOLY
                and len(ring) > 2):
            ring = ring[:-1]
        if len(ring) >= 2:
            out.append(ring)
    return out


def _polygon_area_sign(points):
    """Winding direction of a ring, used to spot holes in filled contours."""
    pts = np.asarray(points, dtype=float).reshape(-1, 2)
    if len(pts) < 3:
        return 1.0
    area = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1)
                        - np.roll(pts[:, 0], -1) * pts[:, 1])
    return 1.0 if area >= 0.0 else -1.0


class ContourSet:
    """Handle returned by `Axes.contour` / `Axes.contourf`."""

    def __init__(self, ax=None, levels=None, segments=None, *args, axes=None, **kwargs):
        self.axes = ax if axes is None else axes
        self._manual = None
        self._manual_kinds = None
        if isinstance(ax, dict) and levels is None and segments is None:
            self._e = ax
            return
        if levels is None or segments is None:
            raise TypeError("ContourSet needs levels and paths")
        allkinds = args[0] if args else kwargs.pop("allkinds", None)
        levels = [float(v) for v in np.asarray(levels, dtype=float).ravel()]
        filled = bool(kwargs.get("filled", False))
        if not levels or (len(levels) < 2 and filled):
            raise ValueError("ContourSet needs at least two levels when filled")
        cmap = _cmap_name(kwargs.pop("cmap", None))
        colors = kwargs.pop("colors", None)
        if colors is None:
            colors = None
        elif isinstance(colors, str):
            colors = [_norm_color(colors)]
        else:
            colors = [_norm_color(c) for c in colors]
        linewidths = kwargs.pop("linewidths", None)
        widths = ([] if linewidths is None else
                  [float(v) for v in np.atleast_1d(
                      np.asarray(linewidths, dtype=float)).ravel()])
        self._e = dict(levels=levels, cmap=cmap, colors=colors,
                       filled=filled,
                       linewidths=widths, alpha=kwargs.pop("alpha", None),
                       x=None, y=None, z=None)
        self._draw_manual(list(segments), allkinds)

    def _manual_colour(self, index):
        colours = self._e.get("colors")
        if colours:
            return _norm_color(colours[index % len(colours)])
        levels = self._e["levels"]
        if self._e["filled"]:
            value = 0.5 * (levels[index] + levels[min(index + 1, len(levels) - 1)])
        else:
            value = levels[min(index, len(levels) - 1)]
        lo, hi = levels[0], levels[-1]
        t = (value - lo) / (hi - lo) if hi > lo else 0.5
        rgb = np.asarray(get_cmap(self._e["cmap"])(t), dtype=float).ravel()[:3]
        return "#{:02x}{:02x}{:02x}".format(*tuple(int(round(float(v) * 255)) for v in rgb))

    def _manual_linewidth(self, index):
        widths = self._e["linewidths"]
        if not widths:
            return rcParams.get("lines.linewidth", 1.5)
        return widths[index % len(widths)]

    def _draw_manual(self, groups, allkinds):
        """Draw user-supplied contour paths through the normal artist layer."""
        kinds = (list(allkinds) if allkinds is not None
                 else [None] * len(groups))
        self._manual, self._manual_kinds = groups, kinds
        for index, group in enumerate(groups):
            colour = self._manual_colour(index)
            width = self._manual_linewidth(index)
            level_kinds = kinds[index] if index < len(kinds) else None
            for path_index, vertices in enumerate(list(group)):
                codes = (level_kinds[path_index] if level_kinds is not None
                         and path_index < len(level_kinds) else None)
                subpaths = _path_subpaths(vertices, codes)
                base_sign = None
                for subpath in subpaths:
                    sign = _polygon_area_sign(subpath)
                    if (self._e["filled"] and base_sign is not None
                            and sign * base_sign < 0):
                        # A subpath wound the other way is a hole; paint it in
                        # the axes colour because the renderer fills one ring.
                        self.axes.fill(subpath[:, 0], subpath[:, 1],
                                       color=self.axes.get_facecolor())
                        continue
                    if base_sign is None:
                        base_sign = sign
                    if self._e["filled"]:
                        self.axes.fill(subpath[:, 0], subpath[:, 1], color=colour,
                                       alpha=self._e["alpha"])
                    else:
                        self.axes.plot(subpath[:, 0], subpath[:, 1], color=colour,
                                       linewidth=width, alpha=self._e["alpha"])

    @property
    def levels(self): return list(self._e["levels"])

    def set_edgecolors(self, colors):
        if colors is None:
            self._e["colors"] = None
        elif isinstance(colors, str):
            self._e["colors"] = [_norm_color(colors)]
        else:
            self._e["colors"] = [_norm_color(c) for c in colors]
        return self
    set_edgecolor = set_edgecolors

    def legend_elements(self, variable_name="x", str_format=None, **kwargs):
        """Handles and labels for one entry per contour level."""
        levels = list(self._e["levels"])
        artists, labels = [], []
        for index, level in enumerate(levels):
            color = _contour_label_colour(self._e, index, level)
            style = ({"facecolor": color} if self._e.get("filled")
                     else {"edgecolor": color, "facecolor": "none"})
            artists.append(Patch(**style))
            if str_format is None:
                labels.append(_contour_label_text(level, None))
            elif callable(str_format):
                labels.append(str(str_format(level)))
            else:
                labels.append(str_format.format(level))
        return artists, labels

    @property
    def cmap(self): return get_cmap(self._e["cmap"])
    @property
    def linewidths(self):
        widths = self._e.get("linewidths") or []
        return widths[0] if len(widths) == 1 and widths else widths

    def get_linewidth(self): return self.linewidths
    def set_linewidth(self, width):
        values = np.atleast_1d(np.asarray(width, dtype=np.float64)).ravel()
        self._e["linewidths"] = [float(v) for v in values]
        return self
    def get_linewidths(self):
        widths = self._e.get("linewidths") or []
        return list(widths)
    @property
    def linestyles(self):
        return self._e.get("linestyles") or "solid"
    def set_linestyle(self, linestyle):
        self._e["linestyles"] = linestyle
        return self
    def get_linestyle(self): return self.linestyles
    def get_cmap(self): return get_cmap(self._e["cmap"])
    def set_cmap(self, cmap): self._e["cmap"] = _cmap_name(cmap)
    def set_clim(self, vmin=None, vmax=None): pass
    def set(self, **kwargs): return self

    def add_label_near(self, x, y, inline=True, inline_spacing=5, transform=None):
        """Accept the explicit label placement; automatic labels still draw."""
        return None

    def clabel(self, levels=None, *, fontsize=None, inline=True, inline_spacing=5,
               fmt=None, colors=None, use_clabeltext=False, manual=False,
               rightside_up=True, zorder=None, **kwargs):
        """Label each contour level at its longest segment or at given points.

        Labels are drawn horizontally or vertically, whichever is closer to the
        local line direction; Matplotlib's inline gap is not cut out of the line.
        `manual` accepts a sequence of data-coordinate positions, as Matplotlib's
        gallery does; `manual=True` falls back to automatic placement.
        """
        if self.axes is None or self._e.get("x") is None:
            return []
        all_levels = self.levels
        if levels is None:
            chosen = list(range(len(all_levels)))
        else:
            wanted = set(np.atleast_1d(np.asarray(levels, dtype=float)).ravel().tolist())
            chosen = [i for i, value in enumerate(all_levels) if value in wanted]
        palette = (None if colors is None else
                   [_norm_color(c) for c in np.atleast_1d(colors).ravel()])
        manual_positions = None
        if (manual is not None and manual is not False
                and not isinstance(manual, (bool, int))):
            manual_positions = [(float(point[0]), float(point[1]))
                                for point in manual]
        texts = []

        def add_label(index, px, py, xa, ya, xb, yb):
            level = all_levels[index]
            angle = _math.degrees(_math.atan2(yb - ya, xb - xa))
            if rightside_up:
                if angle > 90.0:
                    angle -= 180.0
                elif angle < -90.0:
                    angle += 180.0
            colour = (palette[index % len(palette)] if palette
                      else _contour_label_colour(self._e, index, level))
            texts.append(self.axes.text(
                px, py, _contour_label_text(level, fmt),
                fontsize=fontsize, color=colour, ha="center", va="center",
                rotation=angle,
                **{k: v for k, v in kwargs.items() if k in ("alpha", "clip_on")}))

        if manual_positions is not None:
            for px, py in manual_positions:
                best = None
                for index in chosen:
                    for (xa, ya), (xb, yb) in _contour_segments(
                            self._e["x"], self._e["y"], self._e["z"],
                            all_levels[index]):
                        distance = _point_segment_distance(px, py, xa, ya, xb, yb)
                        if best is None or distance < best[0]:
                            best = (distance, index, xa, ya, xb, yb)
                if best is not None:
                    add_label(best[1], px, py, best[2], best[3], best[4], best[5])
            return texts

        for index in chosen:
            segments = _contour_segments(
                self._e["x"], self._e["y"], self._e["z"], all_levels[index])
            if not segments:
                continue
            (xa, ya), (xb, yb) = max(
                segments, key=lambda s: (s[1][0] - s[0][0]) ** 2 + (s[1][1] - s[0][1]) ** 2)
            add_label(index, (xa + xb) / 2.0, (ya + yb) / 2.0, xa, ya, xb, yb)
        return texts

    def get_paths(self):
        if self._manual is not None:
            out = []
            for index, group in enumerate(self._manual):
                level_kinds = (self._manual_kinds[index]
                               if index < len(self._manual_kinds) else None)
                for path_index, vertices in enumerate(group):
                    codes = (level_kinds[path_index] if level_kinds is not None
                             and path_index < len(level_kinds) else None)
                    out.append(Path(vertices, codes))
            return out
        x, y, z = self._e.get("x"), self._e.get("y"), self._e.get("z")
        if x is None or y is None or z is None:
            return []
        paths = []
        for level in self._e["levels"]:
            for start, end in _contour_segments(x, y, z, float(level)):
                paths.append(Path(np.asarray([start, end], dtype=float)))
        return paths

    def get_transform(self): return _Transform()

    def get_arrays(self): return ()

    def _colorbar_spec(self):
        lv = self._e["levels"]
        return dict(cmap=self._e["cmap"], vmin=lv[0], vmax=lv[-1], ticks=lv)


class BboxImage:
    """Image positioned by a bbox callback, used by text-path examples."""

    def __init__(self, bbox, norm=None, origin=None, **kwargs):
        self._bbox = bbox
        self.norm = norm
        self.origin = origin
        self._data = None
        self._clip_path = None

    def set_data(self, data):
        self._data = data
        return self

    def get_array(self): return self._data

    def set_clip_path(self, path, transform=None):
        self._clip_path = (path, transform)
        return self
    def set_clip_on(self, value): return self

    def get_window_extent(self, renderer=None):
        return self._bbox(renderer) if callable(self._bbox) else self._bbox

    def draw(self, renderer=None): return None


class NonUniformImage:
    """Rectilinear image; irregular coordinate arrays are resampled for display."""

    def __init__(self, ax=None, *, extent=None, cmap=None, interpolation="nearest",
                 **kwargs):
        self.axes = ax
        self._extent = None if extent is None else tuple(float(v) for v in extent)
        self._cmap = _cmap_name(cmap)
        self._interpolation = str(interpolation)
        self._data = None

    def set_data(self, x, y, z):
        self._x = np.asarray(x, dtype=float).ravel()
        self._y = np.asarray(y, dtype=float).ravel()
        self._data = np.asarray(z, dtype=float)
        if self._data.shape != (self._y.size, self._x.size):
            raise ValueError("z must have shape (len(y), len(x))")
        return self

    def get_array(self): return self._data
    def get_extent(self): return self._extent
    def set_extent(self, extent): self._extent = tuple(float(v) for v in extent)
    def get_cmap(self): return get_cmap(self._cmap)
    def set_cmap(self, cmap): self._cmap = _cmap_name(cmap)
    def set_interpolation(self, value): self._interpolation = str(value)

    def _render_spec(self):
        data = np.asarray(self._data, dtype=float)
        x, y = self._x, self._y
        if x.size > 1 and not np.allclose(np.diff(x), np.diff(x)[0]):
            target = np.linspace(x[0], x[-1], x.size)
            data = np.vstack([np.interp(target, x, row) for row in data])
        if y.size > 1 and not np.allclose(np.diff(y), np.diff(y)[0]):
            target = np.linspace(y[0], y[-1], y.size)
            data = np.vstack([np.interp(target, y, data[:, col])
                              for col in range(data.shape[1])]).T
        extent = self._extent or (float(x[0]), float(x[-1]),
                                  float(y[0]), float(y[-1]))
        return data, extent


class AxesImage:
    """Handle returned by `Axes.imshow`, for later tweaks.

    The constructor also accepts Matplotlib's artist form,
    `AxesImage(axes, extent=..., cmap=..., interpolation=...)`, which subclasses
    use before calling `set_array`.
    """

    def __init__(self, entry=None, axes=None, *, extent=None, cmap="viridis",
                 interpolation="nearest", alpha=1.0, origin="upper", **kwargs):
        if isinstance(entry, dict):  # internal entry from Axes.imshow
            self._e = entry
            self.axes = axes
        else:
            self.axes = entry if axes is None else axes
            self._e = dict(data=None, cmap=_cmap_name(cmap), vmin=None, vmax=None,
                           extent=None if extent is None else tuple(float(v) for v in extent),
                           alpha=float(alpha), interpolation=str(interpolation))
        self._visible = True
        self._zorder = 0
        self._transform = None

    def get_array(self): return self._e.get("data")
    def set_data(self, X): self._e["data"] = _as_image(X)
    set_array = set_data
    def get_transform(self): return self._transform
    def draw(self, renderer=None): return None
    def get_cmap(self): return get_cmap(self._e["cmap"])

    @property
    def norm(self):
        return _Normalize(vmin=self._e["vmin"], vmax=self._e["vmax"])

    def set_norm(self, norm):
        self._e["vmin"] = getattr(norm, "vmin", None)
        self._e["vmax"] = getattr(norm, "vmax", None)
        return self
    def set_cmap(self, cmap): self._e["cmap"] = _cmap_name(cmap)
    def set_extent(self, extent): self._e["extent"] = tuple(float(v) for v in extent)
    def get_extent(self): return self._e["extent"]
    def set_interpolation(self, value): self._e["interpolation"] = str(value)
    def get_interpolation(self): return self._e["interpolation"]
    def set_alpha(self, value): self._e["alpha"] = float(value)
    def get_alpha(self): return self._e["alpha"]
    def set_rasterized(self, value): _ignored("AxesImage.set_rasterized")
    def set_agg_filter(self, value): _ignored("AxesImage.set_agg_filter")
    def remove(self):
        if self.axes is not None:
            self.axes.images[:] = [image for image in self.axes.images
                                   if image is not self]
        return None
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

    def get_clim(self): return self._e["vmin"], self._e["vmax"]

    def set(self, **kwargs):
        """Apply Matplotlib's image `.set(data=..., extent=..., clim=...)` form."""
        for key, value in kwargs.items():
            if key == "data":
                self.set_data(value)
            elif key == "extent":
                self.set_extent(value)
            elif key == "clim":
                self.set_clim(*value)
            elif key == "cmap":
                self.set_cmap(value)
            elif key == "alpha":
                self.set_alpha(value)
            elif key == "interpolation":
                self.set_interpolation(value)
            elif key in ("vmin", "vmax"):
                self._e[key] = value
            else:
                _ignored(f"AxesImage.set({key})")
        return self

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

    def get_gridspec(self): return self.gridspec
    def is_first_row(self): return self.rows[0] == 0
    def is_last_row(self): return self.rows[1] == self.gridspec.nrows - 1
    def is_first_col(self): return self.cols[0] == 0
    def is_last_col(self): return self.cols[1] == self.gridspec.ncols - 1

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
        self.nrows, self.ncols = _validate_grid_shape(nrows, ncols)
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
        if isinstance(key, tuple):
            rows, cols = key
            return SubplotSpec(self, _span_index(rows, self.nrows),
                               _span_index(cols, self.ncols))
        # A single index is flat, row-major, matching Matplotlib's GridSpec.
        index = int(key)
        size = self.nrows * self.ncols
        if index < 0:
            index += size
        if not 0 <= index < size:
            raise IndexError("GridSpec index out of range")
        row, col = divmod(index, self.ncols)
        return SubplotSpec(self, (row, row), (col, col))

    def get_geometry(self):
        return self.nrows, self.ncols

    def __iter__(self):
        for row in range(self.nrows):
            for col in range(self.ncols):
                yield SubplotSpec(self, (row, row), (col, col))

    def __len__(self):
        return self.nrows * self.ncols

    def update(self, **kwargs):
        for key in ("left", "right", "bottom", "top", "wspace", "hspace"):
            if kwargs.get(key) is not None:
                setattr(self, key, float(kwargs[key]))
        return self

    def tight_layout(self, *args, **kwargs): return None

    def subplots(self, sharex=False, sharey=False, squeeze=True, subplot_kw=None):
        if self.figure is None:
            raise RuntimeError("GridSpec.subplots needs a figure")
        options = dict(subplot_kw or {})
        axs = [self.figure.add_subplot(spec, **options) for spec in self]
        _share_axes(axs, (self.nrows, self.ncols), sharex, sharey)
        if len(axs) == 1 and squeeze:
            return axs[0]
        out = np.array(axs, dtype=object).reshape(self.nrows, self.ncols)
        return out.squeeze() if squeeze else out

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


class _ColorbarAxis:
    """Tick and label shim for the synthetic colorbar axes."""

    def set_tick_params(self, *args, **kwargs): return None
    def tick_right(self): return None
    def tick_left(self): return None
    def set_label_text(self, *args, **kwargs): return None
    def set_label_position(self, position): return None
    def set_ticks_position(self, position): return None
    def get_major_locator(self): return _LocatorHandle()
    def get_minor_locator(self): return _LocatorHandle()


class _ColorbarAxes:
    def __init__(self, entry=None):
        self._e = entry or {}
        self._position = None
        self.yaxis = self.xaxis = _ColorbarAxis()
    def get_position(self, original=False):
        return self._position or _Bbox(0.0, 0.0, 1.0, 1.0)
    def set_position(self, bounds):
        """Remember a reposition request; the colorbar keeps its own strip."""
        values = tuple(float(v) for v in bounds)
        self._position = _Bbox(*values) if len(values) == 4 else None
        return self._position
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
    def get_yticklabels(self): return self._ticklabels()
    def get_xticklabels(self): return self._ticklabels()
    def get_yticks(self): return self._e.get("ticks") or []
    def get_xticks(self): return self._e.get("ticks") or []

    def _set_scale(self, axis, value, base):
        name = str(value).lower()
        if name not in ("linear", "log"):
            raise NotImplementedError(f"unsupported colorbar scale: {value!r}")
        self._e[f"{axis}scale"] = name
        self._e["log_base"] = float(base)
        return None

    def set_xscale(self, value, base=10, **kwargs):
        return self._set_scale("x", value, base)

    def set_yscale(self, value, base=10, **kwargs):
        return self._set_scale("y", value, base)

    def get_xscale(self): return self._e.get("xscale", "linear")
    def get_yscale(self): return self._e.get("yscale", "linear")

    def _set_lim(self, axis, low, high, kwargs):
        low = kwargs.pop(f"{axis}min", low)
        high = kwargs.pop(f"{axis}max", high)
        if high is None and low is not None:
            candidate = np.asarray(low, dtype=float).ravel()
            if candidate.size == 2:
                low, high = candidate
        current = self.get_xlim() if axis == "x" else self.get_ylim()
        low = current[0] if low is None else float(low)
        high = current[1] if high is None else float(high)
        self._e[f"{axis}lim"] = (low, high)
        return self.get_xlim() if axis == "x" else self.get_ylim()

    def set_xlim(self, left=None, right=None, **kwargs):
        return self._set_lim("x", left, right, kwargs)

    def set_ylim(self, bottom=None, top=None, **kwargs):
        return self._set_lim("y", bottom, top, kwargs)

    def get_xlim(self):
        limits = self._e.get("xlim")
        if limits is not None:
            return tuple(float(v) for v in limits)
        return (float(self._e.get("vmin", 0.0)), float(self._e.get("vmax", 1.0)))

    def get_ylim(self):
        limits = self._e.get("ylim")
        if limits is not None:
            return tuple(float(v) for v in limits)
        return (float(self._e.get("vmin", 0.0)), float(self._e.get("vmax", 1.0)))

    def _ticklabels(self):
        ticks = self._e.get("ticks")
        if ticks is None:
            return []
        formatter = self._e.get("format")
        if formatter is None:
            return [_TextLabel(f"{tick:g}") for tick in ticks]
        return [_TextLabel(str(formatter(tick, i))) for i, tick in enumerate(ticks)]


class _ColorbarDividers:
    """Divider lines for a standalone colorbar, in the colorbar axes' data units."""

    def __init__(self, axes, boundaries, orientation, enabled, extend=None):
        self.axes = axes
        self.boundaries = np.asarray(boundaries, dtype=float) if boundaries is not None else None
        self.orientation = orientation or "vertical"
        self.enabled = bool(enabled)
        self.extend = extend

    def get_segments(self):
        if not self.enabled:
            return []
        horizontal = self.orientation == "horizontal"
        lo, hi = self.axes.get_xlim() if horizontal else self.axes.get_ylim()
        lo, hi = float(lo), float(hi)
        if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
            return []
        cuts = [float(v) for v in (self.boundaries if self.boundaries is not None else ())
                if lo < float(v) < hi]
        if self.extend is None or self.extend in ("both", "min"):
            cuts.append(lo)
        if self.extend is None or self.extend in ("both", "max"):
            cuts.append(hi)
        cuts.sort()
        if horizontal:
            return [[[v, 0.0], [v, 1.0]] for v in cuts]
        return [[[0.0, v], [1.0, v]] for v in cuts]


def _resolve_colorbar_extendfrac(value, boundaries, extend):
    """Normalize `extendfrac` to the fraction of the strip used per end."""
    if value is None:
        return 0.05
    if isinstance(value, str):
        if value != "auto":
            raise ValueError(f"invalid extendfrac: {value!r}")
        if boundaries is None:
            return 0.05
        bounds = np.asarray(boundaries, dtype=float).ravel()
        bounds = bounds[np.isfinite(bounds)]
        if bounds.size < 2:
            return 0.05
        if extend == "both" and bounds.size >= 3:
            interior = bounds[1:-1]
        elif extend == "min":
            interior = bounds[1:]
        elif extend == "max":
            interior = bounds[:-1]
        else:
            return 0.05
        span = interior[-1] - interior[0] if interior.size else 0.0
        if not span > 0.0:
            return 0.05
        if extend == "both":
            return max((interior[0] - bounds[0]) / span,
                       (bounds[-1] - interior[-1]) / span)
        if extend == "min":
            return (interior[0] - bounds[0]) / span
        return (bounds[-1] - interior[-1]) / span
    fraction = float(value)
    if not np.isfinite(fraction) or fraction < 0.0:
        raise ValueError(f"invalid extendfrac: {value!r}")
    return fraction


class Colorbar:
    """Handle returned by `Figure.colorbar` or constructed around an axes."""

    def __init__(self, ax=None, mappable=None, *, cmap=None, norm=None, values=None,
                 boundaries=None, orientation=None, ticklocation="auto", extend=None,
                 spacing="uniform", ticks=None, format=None, drawedges=False,
                 extendfrac=None, extendrect=False, label="", **kwargs):
        if isinstance(ax, dict):
            self._e = ax
            self.ax = _ColorbarAxes(ax)
            self.dividers = _ColorbarDividers(
                self.ax, boundaries,
                orientation or ax.get("orientation", "vertical"),
                drawedges or ax.get("drawedges", False),
                extend or ax.get("extend"))
            return
        if ax is None:
            raise TypeError("Colorbar needs an axes")
        self.ax = ax
        if extend is None:
            extend = getattr(norm, "extend", None)
        if extend is None and cmap is not None:
            under = getattr(cmap, "_under", None) is not None
            over = getattr(cmap, "_over", None) is not None
            extend = ("both" if under and over else "min" if under else "max" if over
                       else "neither")
        bounds = boundaries
        if bounds is None and hasattr(norm, "boundaries"):
            bounds = norm.boundaries
        if bounds is not None:
            values_arr = np.asarray(bounds, dtype=float).ravel()
            values_arr = values_arr[np.isfinite(values_arr)]
        else:
            values_arr = np.array([], dtype=float)
        lo = getattr(norm, "vmin", None)
        hi = getattr(norm, "vmax", None)
        if lo is None and values_arr.size:
            lo = values_arr[0]
        if hi is None and values_arr.size:
            hi = values_arr[-1]
        if lo is None:
            lo = 0.0
        if hi is None:
            hi = 1.0
        if not float(hi) > float(lo):
            lo, hi = float(lo) - 0.5, float(lo) + 0.5
        orientation = ("horizontal" if str(orientation or "vertical").lower() == "horizontal"
                       else "vertical")
        extend = str(extend or "neither").lower()
        entry = dict(cmap=_cmap_name(cmap), vmin=float(lo), vmax=float(hi),
                     label=str(label), ticks=ticks, format=format,
                     orientation=orientation, extend=extend,
                     extendrect=bool(extendrect),
                     extendfrac=_resolve_colorbar_extendfrac(extendfrac, bounds, extend))
        ax._colorbar = entry
        fig = getattr(ax, "_fig", None)
        if fig is not None:
            fig._colorbar = entry
        self._e = entry
        self.dividers = _ColorbarDividers(ax, bounds, orientation, drawedges, extend)

    def set_label(self, label, loc=None, **kwargs): self._e["label"] = str(label)
    def get_label(self): return self._e["label"]
    def add_lines(self, *args, **kwargs): return None
    def minorticks_on(self): return None
    def minorticks_off(self): return None
    def set_ticks(self, *args, **kwargs): return None
    def set_ticklabels(self, *args, **kwargs): return None
    def set_clim(self, *args, **kwargs): return None
    def update_normal(self, *args, **kwargs): return None


class Figure:
    def __init__(self, figsize=None, dpi=None, facecolor=None, edgecolor=None):
        if figsize is None:
            figsize = rcParams.get("figure.figsize", (6.4, 4.8))
        self.figsize = _validate_figsize(figsize)
        self.number = None
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
        self._figure_images = []
        self.artists = []
        self.patches = []
        self._render_cache = None
        self.transFigure = _CoordTransform("figure")
        self.transSubfigure = self.transFigure
        self.canvas = _Canvas(self)
        self.layout_engine = _LayoutEngine()
        self.subplotpars = _SubplotPars()
        self.patch = Rectangle((0, 0), 1, 1, transform=self.transFigure,
                               facecolor=self.get_facecolor())
        self._gridspec = None
        self._label = ""
        self.callbacks = _Callbacks()

    def suptitle(self, t, x=0.5, y=0.98, fontsize=None, **kwargs):
        """Draw a figure-level title above the panel grid."""
        size = _font_size(fontsize, rcParams.get("figure.titlesize", 12.0))
        family = _family_override(kwargs)
        self._suptitle = dict(text=_mathtext(t, family), size=size, x=float(x),
                              y=float(y), family=family)
        return None

    def supxlabel(self, t, x=0.5, y=0.01, fontsize=None, **kwargs):
        """Draw a figure-level x label below the panel grid."""
        kwargs.setdefault("ha", "center")
        kwargs.setdefault("va", "bottom")
        return self.text(x, y, t, fontsize=fontsize, **kwargs)

    def supylabel(self, t, x=0.02, y=0.5, fontsize=None, **kwargs):
        """Draw a figure-level y label left of the panel grid."""
        kwargs.setdefault("ha", "center")
        kwargs.setdefault("va", "bottom")
        kwargs.setdefault("rotation", 90)
        return self.text(x, y, t, fontsize=fontsize, **kwargs)

    def align_xlabels(self, axs=None): return None
    def align_ylabels(self, axs=None): return None
    def align_titles(self, axs=None): return None
    def align_labels(self, axs=None): return None

    def text(self, x, y, s, fontdict=None, **kwargs):
        """Figure-fraction text, drawn above every panel so nothing clips it."""
        transform, fontsize, colour, ha, va, bbox, rotation, family = _text_props(
            fontdict, kwargs)
        if ha not in ("left", "center", "right"):
            raise ValueError(f"unsupported ha: {ha!r}")
        if va == "center_baseline":
            va = "center"
        if va not in ("baseline", "bottom", "center", "top"):
            raise ValueError(f"unsupported va: {va!r}")
        size = _font_size(fontsize, rcParams.get("font.size", 10.0))
        colour = colour if colour is not None else rcParams.get("text.color", "black")
        values = _as_f64((x, y))
        if getattr(transform, "kind", None) == "identity":
            # `IdentityTransform` addresses the figure in pixels from the
            # lower-left; the renderer stores figure-fraction positions.
            width = self.figsize[0] * self.get_dpi()
            height = self.figsize[1] * self.get_dpi()
            values = (values[0] / width, values[1] / height)
        self._figure_texts.append((float(values[0]), float(values[1]), _mathtext(s, family),
                                   _norm_color(colour), size, ha, va, bbox, rotation,
                                   family, (0.0, 0.0)))
        return _TextArt()

    def add_subplot(self, nrows=1, ncols=1, index=1, **kwargs):
        """index is 1-based, row-major (matplotlib convention); a `SubplotSpec`
        may be passed instead to place the axes on an irregular grid."""
        axes_class = kwargs.pop("axes_class", None)
        projection = kwargs.pop("projection", None)
        polar = bool(kwargs.pop("polar", False))
        if projection is not None:
            axes_class = _get_projection_class(projection)
        elif polar:
            axes_class = PolarAxes
        elif axes_class is None:
            axes_class = Axes
        grid_helper = kwargs.pop("grid_helper", None)
        options = dict(kwargs)
        if isinstance(nrows, SubplotSpec):
            return self._add_spec(nrows, axes_class=axes_class,
                                  grid_helper=grid_helper, **options)
        if isinstance(nrows, int) and 111 <= nrows <= 999 and ncols == 1 and index == 1:
            # `subplot(121)` is shorthand for `subplot(1, 2, 1)`.
            nrows, ncols, index = divmod(nrows, 100)[0], *divmod(nrows % 100, 10)
        nrows, ncols = _validate_grid_shape(nrows, ncols)
        changed = (nrows, ncols) != self.grid
        if changed:
            old_rows, old_cols = self.grid
            for existing in self.axes:
                if existing._pos_override is None:
                    row, col = divmod(existing.pos, old_cols)
                    existing._pos_override = GridSpec(
                        old_rows, old_cols, figure=self)._bounds((row, row), (col, col))
                    existing._bounds_are_axes = False
            self.grid = (nrows, ncols)
        mixed = bool(self.axes) and (
            changed or any(a._pos_override is not None for a in self.axes))
        ax = (next((a for a in self.axes if a.pos == index - 1), None)
              if axes_class is Axes else None)
        if ax is None:
            ax = axes_class(index - 1)
        if ax not in self.axes:
            self.axes.append(ax)
        ax._fig = self
        if mixed:
            row, col = divmod(index - 1, ncols)
            ax._pos_override = GridSpec(
                nrows, ncols, figure=self)._bounds((row, row), (col, col))
            ax._bounds_are_axes = False
        _apply_axes_options(ax, options, grid_helper)
        self._cur = ax
        return ax

    def _add_spec(self, spec, axes_class=Axes, grid_helper=None, **kwargs):
        ax = axes_class(len(self.axes))
        ax._subplotspec = spec
        ax._fig = self
        ax._pos_override = spec.gridspec._bounds(spec.rows, spec.cols)
        ax._bounds_are_axes = False
        self.axes.append(ax)
        _apply_axes_options(ax, kwargs, grid_helper)
        self._cur = ax
        return ax

    def add_gridspec(self, nrows=1, ncols=1, **kwargs):
        kwargs.setdefault("figure", self)
        return GridSpec(nrows, ncols, **kwargs)

    def subplot2grid(self, shape, loc, rowspan=1, colspan=1, **kwargs):
        rows, cols = (int(v) for v in shape)
        row, col = (int(v) for v in loc)
        gs = GridSpec(rows, cols, figure=self)
        return self.add_subplot(SubplotSpec(
            gs, (row, row + int(rowspan) - 1), (col, col + int(colspan) - 1)))

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

    def subplots(self, nrows=1, ncols=1, *, sharex=False, sharey=False,
                 squeeze=True, subplot_kw=None, gridspec_kw=None):
        nrows, ncols = _validate_grid_shape(nrows, ncols)
        # `plt.subplots` builds its grid from a GridSpec in Matplotlib, so
        # `ax.get_gridspec()` must return one here too.
        self._gridspec = GridSpec(nrows, ncols, figure=self, **(gridspec_kw or {}))
        subplot_kw = dict(subplot_kw or {})
        axs = [self.add_subplot(nrows, ncols, i + 1, **subplot_kw)
               for i in range(nrows * ncols)]
        _share_axes(axs, (nrows, ncols), sharex, sharey)
        if len(axs) == 1 and squeeze:
            return axs[0]
        out = np.array(axs, dtype=object).reshape(nrows, ncols)
        return out.squeeze() if squeeze else out

    def gca(self):
        return self._cur or self.add_subplot()

    def add_axes(self, rect=None, **kwargs):
        """Add an axes whose figure-fraction rectangle is the plotting area."""
        if isinstance(rect, Axes):
            ax = rect
            ax._fig = self
            if ax not in self.axes:
                self.axes.append(ax)
            self._cur = ax
            return ax
        locator = kwargs.pop("axes_locator", None)
        axes_class = kwargs.pop("axes_class", None)
        projection = kwargs.pop("projection", None)
        polar = bool(kwargs.pop("polar", False))
        if projection is not None:
            axes_class = _get_projection_class(projection)
        elif polar:
            axes_class = PolarAxes
        elif axes_class is None:
            axes_class = Axes
        grid_helper = kwargs.pop("grid_helper", None)
        ax = axes_class(len(self.axes) + 1000)
        ax._fig = self
        ax.set_position(rect if rect is not None else (0.0, 0.0, 1.0, 1.0))
        ax._bounds_are_axes = True
        if "label" in kwargs:
            ax.set_label(kwargs.pop("label"))
        _apply_axes_options(ax, kwargs, grid_helper)
        self.axes.append(ax)
        self._cur = ax
        if locator is not None:
            ax.set_axes_locator(locator)
        return ax

    def add_artist(self, artist, **kwargs):
        self.artists.append(artist)
        if isinstance(artist, Patch):
            self.patches.append(artist)
        return artist

    def draw_without_rendering(self): return None
    def draw(self, *args, **kwargs): return None

    # Layout requests are accepted but ignored: panels always fill their gridspec
    # cells, so there are no margins to negotiate.
    def tight_layout(self, **kwargs): return None
    def subplots_adjust(self, *args, **kwargs): return None
    def set_layout_engine(self, engine=None, **kwargs):
        self.layout_engine = (engine if isinstance(engine, _LayoutEngine)
                              else _LayoutEngine(engine))

    def get_layout_engine(self): return getattr(self, "layout_engine", None)
    def get_axes(self): return list(self.axes)
    def get_dpi(self): return self.dpi or DPI

    @property
    def dpi_scale_trans(self): return _Transform()
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

    def legend(self, *args, **kwargs): return _LegendHandle()
    def figimage(self, X, xo=0, yo=0, alpha=None, norm=None, cmap=None,
                 vmin=None, vmax=None, origin=None, resize=False, **kwargs):
        """Place an image directly on the figure at pixel offsets from the
        lower-left corner. `resize` and artist kwargs are accepted and ignored."""
        raw = np.asarray(X)
        a = _as_image(raw)
        # Matplotlib also accepts 8-bit RGB(A) arrays, while the renderer's
        # RGB path expects floats in 0-1.
        if a.ndim == 3 and raw.dtype.kind in "ui":
            a = a / 255.0
        if norm is not None and a.ndim == 2:
            a, vmin, vmax = _norm_values(norm, a)
        origin = "upper" if origin is None else str(origin)
        if origin == "lower":
            a = a[::-1]
        elif origin != "upper":
            raise ValueError(f"unsupported origin: {origin!r}")
        opacity = 1.0 if alpha is None else float(alpha)
        if not np.isfinite(opacity):
            raise ValueError("alpha must be finite")
        height, width = (int(v) for v in a.shape[:2])
        if height < 1 or width < 1:
            raise ValueError("figimage needs a non-empty array")
        if height > _MAX_FIGIMAGE_DIM or width > _MAX_FIGIMAGE_DIM:
            raise ValueError(
                f"figimage dimensions ({height}x{width}) exceed maximum allowed "
                f"dimension of {_MAX_FIGIMAGE_DIM}px"
            )
        if height * width > _MAX_FIGIMAGE_PIXELS:
            raise ValueError(
                f"figimage pixel count ({height * width}) exceeds maximum allowed "
                f"({_MAX_FIGIMAGE_PIXELS}px)"
            )
        payload = sum(_figimage_payload_estimate(e["data"])
                      for e in self._figure_images)
        payload += _figimage_payload_estimate(a)
        if payload > _MAX_FIGIMAGE_BYTES:
            raise ValueError(
                f"figimage embedded base64 payload ({payload} bytes) exceeds "
                f"maximum allowed ({_MAX_FIGIMAGE_BYTES} bytes)"
            )
        entry = dict(data=a, cmap=_cmap_name(cmap), vmin=vmin, vmax=vmax,
                     alpha=float(np.clip(opacity, 0.0, 1.0)),
                     xo=int(xo), yo=int(yo))
        self._figure_images.append(entry)
        return _FigureImage(entry)
    def add_subfigure(self, spec=None, **kwargs):
        if isinstance(spec, SubplotSpec):
            return _SubFigure(self, spec.get_position().bounds)
        return _SubFigure(self, (0.0, 0.0, 1.0, 1.0))

    def subfigures(self, nrows=1, ncols=1, squeeze=True, **kwargs):
        """Create independent subfigure views that place their own axes."""
        return _subfigure_array(self, nrows, ncols, squeeze=squeeze, **kwargs)
    def get_children(self): return list(self.axes)

    def findobj(self, match=None, include_self=True):
        """Return children accepted by `match`, a class or predicate."""
        candidates = ([self] if include_self else []) + list(self.axes) + list(self.artists)
        if match is None:
            return candidates
        if isinstance(match, type):
            return [item for item in candidates if isinstance(item, match)]
        return [item for item in candidates if match(item)]

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

    def autofmt_xdate(self, bottom=0.2, rotation=30, ha="right", **kwargs):
        for axes in self.axes:
            for label in axes.get_xticklabels():
                label.set_rotation(rotation)
                if hasattr(label, "set_ha"):
                    label.set_ha(ha)

    def colorbar(self, mappable=None, ax=None, label="", **kwargs):
        """Reserve a strip beside `mappable`'s axes showing its scale."""
        if not self.axes:
            raise ValueError("colorbar needs at least one axes")
        cax = kwargs.get("cax")
        if cax is not None:
            ax = cax
        if isinstance(ax, (list, tuple, np.ndarray)):
            candidates = np.asarray(ax, dtype=object).ravel()
            ax = next((item for item in candidates
                       if isinstance(item, Axes) and item.visible), None)
        if ax is None:
            ax = kwargs.get("cax")
        if ax is None:
            axes = self._cur or self.axes[0]
            if mappable is not None:
                mappable_axes = getattr(mappable, "axes", None)
                if isinstance(mappable_axes, Axes):
                    axes = mappable_axes
                entry = getattr(mappable, "_e", None)
                owner = next((a for a in self.axes
                              if entry is not None
                              and (any(item is mappable or item._e is entry
                                       for item in a.images)
                                   or any(item is entry for item in a.contours)
                                   or any(item is entry for item in a.scatter_pts))), None)
                axes = owner or axes
        else:
            axes = ax
        if mappable is not None:
            spec = mappable._colorbar_spec()
        elif axes.contours:
            spec = ContourSet(axes.contours[-1])._colorbar_spec()
        elif axes.images:
            spec = axes.images[-1]._colorbar_spec()
        else:
            collection = next(
                (artist for artist in reversed(axes.artists)
                 if getattr(artist, "_array", None) is not None
                 and hasattr(artist, "_colorbar_spec")), None)
            if collection is None:
                raise ValueError("colorbar needs an image or contour to describe")
            spec = collection._colorbar_spec()
        orientation = str(kwargs.get("orientation", "vertical")).lower()
        if orientation not in ("horizontal", "vertical"):
            raise ValueError(f"unsupported colorbar orientation: {orientation!r}")
        entry = dict(cmap=str(spec["cmap"]), vmin=float(spec["vmin"]),
                     vmax=float(spec["vmax"]), label=str(label),
                     ticks=(kwargs["ticks"] if "ticks" in kwargs
                            else spec.get("ticks")),
                     format=kwargs.get("format"),
                     orientation=orientation,
                     extend=str(kwargs.get("extend", "neither")).lower(),
                     extendrect=bool(kwargs.get("extendrect", False)),
                     extendfrac=_resolve_colorbar_extendfrac(
                         kwargs.get("extendfrac"), None,
                         str(kwargs.get("extend", "neither")).lower()))
        axes._colorbar = entry
        self._colorbar = entry
        return Colorbar(entry)


    def savefig(self, fname=None, format=None, dpi=None, bbox_inches=None,
                transparent=None, facecolor=None, edgecolor=None,
                compression=None, pad_inches=None, metadata=None,
                pil_kwargs=None, **kwargs):
        """Write this figure, or return its bytes when `fname` is None or a
        file-like object. `format` overrides the extension, `dpi` scales the
        pixel size and `bbox_inches="tight"` crops to the drawn content.
        `compression` selects PNG compression: "fast" (default), "default",
        or "best". `metadata` and `pil_kwargs` are accepted for Matplotlib
        compatibility; the renderer currently has no metadata model for them."""
        if "filepath" in kwargs:
            _deprecated("filepath", since="0.8", alternative="fname")
            if fname is not None:
                raise TypeError("savefig() got multiple values for argument 'fname'")
            fname = kwargs.pop("filepath")
        if kwargs:
            unexpected = next(iter(kwargs))
            raise TypeError(f"savefig() got an unexpected keyword argument {unexpected!r}")
        if transparent is None:
            transparent = bool(rcParams.get("savefig.transparent", False))
        metadata = _validate_savefig_mapping(metadata, "metadata")
        pil_kwargs = _validate_savefig_mapping(pil_kwargs, "pil_kwargs")
        if metadata:
            _ignored("savefig(metadata=...)")
        if pil_kwargs:
            _ignored("savefig(pil_kwargs=...)")
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
        fmt = _output_format(fname, format)
        # Matplotlib truncates fractional pixels here (`int(width * dpi)`),
        # matching its canvas; rounding made 6.4x4.8 in at 72 dpi 461x346
        # instead of 460x345.
        rw, rh = (int(v * dpi) for v in self.figsize)
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
            "suptitle_family": (self._suptitle.get("family") or _font_family())
            if self._suptitle else _font_family(),
            "suptitle_size": self._suptitle["size"] if self._suptitle else 12.0,
            "suptitle_x": self._suptitle["x"] if self._suptitle else 0.5,
            "suptitle_y": self._suptitle["y"] if self._suptitle else 0.98,
            "figure_texts": self._figure_texts,
            "figure_images": [(e["data"], e["cmap"], e["vmin"], e["vmax"],
                              e["alpha"], True, e["xo"], e["yo"])
                             for e in self._figure_images],
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
        if fname is None:
            return data
        if hasattr(fname, "write"):
            fname.write(data)
            return None
        with open(os.fspath(fname), "wb") as fh:
            fh.write(data)
        return None


def _subfigure_array(figure, nrows=1, ncols=1, squeeze=True, bounds=(0.0, 0.0, 1.0, 1.0),
                     width_ratios=None, height_ratios=None, wspace=None, hspace=None,
                     **kwargs):
    """Lay out subfigures on a grid confined to `bounds`."""
    nrows, ncols = _validate_grid_shape(nrows, ncols)
    left, bottom, width, height = bounds
    gs = GridSpec(nrows, ncols, figure=figure, left=left, right=left + width,
                  bottom=bottom, top=bottom + height, wspace=wspace, hspace=hspace,
                  width_ratios=width_ratios, height_ratios=height_ratios)
    out = np.empty((nrows, ncols), dtype=object)
    for row in range(nrows):
        for col in range(ncols):
            out[row, col] = _SubFigure(figure, gs._bounds((row, row), (col, col)))
    if nrows * ncols == 1 and squeeze:
        return out[0, 0]
    return out.squeeze() if squeeze else out


class _SubFigure:
    """A rectangular view of a figure with its own subplot grid."""

    def __init__(self, figure, bounds):
        self.figure = figure
        self._bounds = tuple(bounds)
        self._zorder = 0

    def get_position(self):
        x, y, width, height = self._bounds
        return _Bbox(x, y, x + width, y + height)

    @property
    def canvas(self): return self.figure.canvas

    def subplots(self, nrows=1, ncols=1, *, sharex=False, sharey=False,
                 squeeze=True, subplot_kw=None, gridspec_kw=None):
        nrows, ncols = _validate_grid_shape(nrows, ncols)
        x, y, width, height = self._bounds
        gs = GridSpec(nrows, ncols, figure=self.figure,
                      left=x, right=x + width, bottom=y, top=y + height,
                      **(gridspec_kw or {}))
        subplot_kw = dict(subplot_kw or {})
        axs = [self.figure.add_subplot(gs[i], **subplot_kw)
               for i in range(nrows * ncols)]
        _share_axes(axs, (nrows, ncols), sharex, sharey)
        if len(axs) == 1 and squeeze:
            return axs[0]
        out = np.array(axs, dtype=object).reshape(nrows, ncols)
        return out.squeeze() if squeeze else out

    def add_subplot(self, *args, **kwargs):
        if args and isinstance(args[0], SubplotSpec):
            return self.figure.add_subplot(*args, **kwargs)
        x, y, width, height = self._bounds
        gs = GridSpec(1, 1, figure=self.figure, left=x, right=x + width,
                      bottom=y, top=y + height)
        return self.figure.add_subplot(gs[0])

    def subfigures(self, nrows=1, ncols=1, squeeze=True, **kwargs):
        return _subfigure_array(self.figure, nrows, ncols, squeeze=squeeze,
                                bounds=self._bounds, **kwargs)

    def add_subfigure(self, spec=None, **kwargs):
        if isinstance(spec, SubplotSpec):
            return _SubFigure(self.figure, spec.get_position().bounds)
        return _SubFigure(self.figure, self._bounds)

    def colorbar(self, *args, **kwargs): return self.figure.colorbar(*args, **kwargs)
    def text(self, *args, **kwargs): return self.figure.text(*args, **kwargs)

    def suptitle(self, text, x=0.5, y=0.98, fontsize=None, **kwargs):
        left, bottom, width, height = self._bounds
        size = _font_size(fontsize, rcParams.get("figure.titlesize", 12.0))
        return self.figure.text(left + x * width, bottom + y * height, text,
                                ha="center", va="top", fontsize=size)

    def supxlabel(self, text, x=0.5, y=0.01, fontsize=None, **kwargs):
        left, bottom, width, height = self._bounds
        return self.figure.text(left + x * width, bottom + y * height, text,
                                ha="center", va="bottom", fontsize=fontsize, **kwargs)

    def supylabel(self, text, x=0.02, y=0.5, fontsize=None, **kwargs):
        left, bottom, width, height = self._bounds
        kwargs.setdefault("rotation", 90)
        return self.figure.text(left + x * width, bottom + y * height, text,
                                ha="center", va="bottom", fontsize=fontsize, **kwargs)

    def set_facecolor(self, color): return self
    def set_zorder(self, zorder): self._zorder = int(zorder); return self
    def get_zorder(self): return self._zorder


# The pyplot shims share a process-wide registry. The lock only protects the
# registry and current-figure selection; Figure objects remain independent, so
# the object-oriented API is the thread-safe path for concurrent work.
_figures = {}
_current_fig = None
_figure_lock = threading.RLock()


def _find_figure_locked(fig):
    if isinstance(fig, Figure):
        for number, candidate in _figures.items():
            if candidate is fig:
                return number
        number = getattr(fig, "number", None)
        return number if isinstance(number, int) and _figures.get(number) is fig else None
    if isinstance(fig, str):
        return next((number for number, candidate in sorted(_figures.items())
                     if candidate.get_label() == fig), None)
    if isinstance(fig, (int, np.integer)):
        number = int(fig)
        return number if number in _figures else None
    return None


def _new_figure_locked(number, label=None, **kwargs):
    global _current_fig
    fig = Figure(**kwargs)
    fig.number = number
    if label is not None:
        fig.set_label(label)
    _figures[number] = fig
    _current_fig = number
    return fig


def figure(*args, num=None, figsize=None, dpi=None, facecolor=None,
           edgecolor=None, **kwargs):
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


def gcf():
    with _figure_lock:
        current = _figures.get(_current_fig)
        if current is not None:
            return current
        return figure()


def gca(): return gcf().gca()


def close(fig=None):
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


def get_fignums():
    """Return the numbers of all open figures, in ascending order."""
    with _figure_lock:
        return sorted(_figures)


def fignum_exists(num):
    """Return whether a figure with the given number is open."""
    if isinstance(num, np.integer):
        num = int(num)
    if not isinstance(num, int):
        return False
    with _figure_lock:
        return num in _figures


def subplots(nrows=1, ncols=1, *, sharex=False, sharey=False, squeeze=True,
             subplot_kw=None, gridspec_kw=None, **fig_kw):
    fig = figure(**fig_kw)
    return fig, fig.subplots(nrows, ncols, sharex=sharex, sharey=sharey,
                             squeeze=squeeze, subplot_kw=subplot_kw,
                             gridspec_kw=gridspec_kw)


def subplot(*args, **kwargs):
    """`subplot(nrows, ncols, index)` or `subplot(gs[row, col])`."""
    return gcf().add_subplot(*args, **kwargs)


def subplot2grid(shape, loc, rowspan=1, colspan=1, fig=None, **kwargs):
    return (fig or gcf()).subplot2grid(shape, loc, rowspan=rowspan,
                                      colspan=colspan, **kwargs)


def subplot_mosaic(mosaic, empty_sentinel=".", figsize=None, dpi=None,
                   facecolor=None, edgecolor=None, **kwargs):
    fig = figure(figsize, dpi=dpi, facecolor=facecolor, edgecolor=edgecolor)
    return fig, fig.subplot_mosaic(mosaic, empty_sentinel=empty_sentinel)
class FormatStrFormatter:
    """Old-style `%` formatter used by `FormatStrFormatter`."""

    def __init__(self, fmt):
        self.fmt = str(fmt)

    def __call__(self, x, pos=None):
        return self.fmt % x


class _Epoch(float):
    """Date-number-compatible epoch used by the harvested JPL unit tests."""

    def __new__(cls, name, dt=None):
        if dt is None:
            value = 0.0
        elif isinstance(dt, _datetime.datetime):
            value = (dt - _datetime.datetime(1970, 1, 1)).total_seconds() / 86400.0
        else:
            value = float(dt)
        return float.__new__(cls, value)


class _Duration(float):
    """Second-based duration with the small `convert` surface tests use."""

    def __new__(cls, name, seconds=0.0):
        return float.__new__(cls, float(seconds))

    def convert(self, unit):
        return float(self)


class _TestingUnits:
    """Small `matplotlib.testing` stand-in for the harvested unit tests."""

    sec = 1.0
    km = 1.0
    deg = 1.0
    Epoch = _Epoch
    Duration = _Duration

    def __init__(self):
        self.day = _Duration("ET", 86400.0)

    def register(self):
        return None


testing = _TestingUnits()


def twinx(ax=None):
    """`plt.twinx()` shim."""
    return (ax or gca()).twinx()


def twiny(ax=None):
    """`plt.twiny()` shim."""
    return (ax or gca()).twiny()


def clabel(CS, levels=None, **kwargs):
    """`plt.clabel()` shim for the current axes."""
    return gca().clabel(CS, levels=levels, **kwargs)


def suptitle(t, x=0.5, y=0.98, fontsize=None, **kwargs):
    return gcf().suptitle(t, x=x, y=y, fontsize=fontsize, **kwargs)
def figtext(x, y, s, **kwargs):
    return gcf().text(x, y, s, **kwargs)
def plot(*args, **kwargs): return gca().plot(*args, **kwargs)
def polar(*args, **kwargs): return gca().plot(*args, **kwargs)
def xlabel(text, fontsize=None, **kwargs): gca().set_xlabel(text, fontsize=fontsize)
def ylabel(text, fontsize=None, **kwargs): gca().set_ylabel(text, fontsize=fontsize)
def title(text, fontsize=None, **kwargs):
    return gca().set_title(text, fontsize=fontsize, **kwargs)
def text(*args, **kwargs): return gca().text(*args, **kwargs)
text.Text = Text
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
def matshow(A, fignum=None, **kwargs): return gca().matshow(A, **kwargs)
def table(cellText=None, cellColours=None, **kwargs):
    return gca().table(cellText=cellText, cellColours=cellColours, **kwargs)
def spy(Z, precision=0, marker=None, markersize=None, aspect="equal",
        origin="upper", **kwargs):
    return gca().spy(Z, precision=precision, marker=marker,
                     markersize=markersize, aspect=aspect, origin=origin, **kwargs)
def xkcd(scale=1, length=100, randomness=2):
    """Matplotlib's sketch style has no renderer support; accept and ignore it.

    The call also works as `with plt.xkcd():`, so return a context manager.
    """
    _ignored("xkcd")
    return _NoopContext()
def get_data_path(): return os.path.dirname(os.path.abspath(__file__))
def axhline(*args, **kwargs): return gca().axhline(*args, **kwargs)
def axvline(*args, **kwargs): return gca().axvline(*args, **kwargs)
def axhspan(*args, **kwargs): return gca().axhspan(*args, **kwargs)
def axvspan(*args, **kwargs): return gca().axvspan(*args, **kwargs)
def bar(*args, **kwargs): return gca().bar(*args, **kwargs)
def bar_label(container, labels=None, fmt="%g", label_type="edge", padding=0, **kwargs):
    return gca().bar_label(container, labels=labels, fmt=fmt, label_type=label_type,
                           padding=padding, **kwargs)
def barh(*args, **kwargs): return gca().barh(*args, **kwargs)
def grouped_bar(*args, **kwargs): return gca().grouped_bar(*args, **kwargs)
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
            vmax=None, data=None, norm=None, **kwargs):
    return gca().scatter(x, y, s=s, c=c, alpha=alpha, cmap=cmap, label=label, marker=marker,
                         vmin=vmin, vmax=vmax, data=data, norm=norm, **kwargs)


def axes(*args, **kwargs):
    """Compatibility shim: matplotvite lays out subplots on a grid, so this returns the
    current axes (creating one if needed)."""
    return gca()





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


def streamplot(*args, **kwargs): return gca().streamplot(*args, **kwargs)
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


def triplot(*args, **kwargs):
    return gca().triplot(*args, **kwargs)


def tricontour(*args, levels=None, colors=None, cmap=None, linewidths=None,
               alpha=None, **kwargs):
    return gca().tricontour(*args, levels=levels, colors=colors, cmap=cmap,
                            linewidths=linewidths, alpha=alpha, **kwargs)


def tricontourf(*args, levels=None, colors=None, cmap=None, linewidths=None,
                alpha=None, **kwargs):
    return gca().tricontourf(*args, levels=levels, colors=colors, cmap=cmap,
                             linewidths=linewidths, alpha=alpha, **kwargs)


def tripcolor(*args, **kwargs):
    return gca().tripcolor(*args, **kwargs)


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


def _is_artist_sequence(obj):
    """True for a list of artists such as a `BarContainer`, not a string."""
    return isinstance(obj, (list, tuple, np.flatiter)) and not isinstance(obj, (str, bytes))


def getp(obj, *args):
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


def setp(obj, *args, **kwargs):
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
    "xtick.labelsize": 10.0,
    "ytick.labelsize": 10.0,
    "figure.titlesize": 12.0,
    "legend.fontsize": 10.0,
    "axes.prop_cycle": _CycleList(_CYCLE),
    "image.cmap": "viridis",
    "image.interpolation": "nearest",
    "figure.facecolor": "#ffffff",
    "axes.facecolor": "#ffffff",
    "axes.edgecolor": "#000000",
    "axes.grid": False,
    "axes.labelcolor": "#000000",
    "xtick.color": "#000000",
    "ytick.color": "#000000",
    "text.color": "#000000",
    "text.parse_math": True,
    "text.usetex": False,
    "grid.color": "#b0b0b0",
    "font.family": ["sans-serif"],
    "font.sans-serif": ["DejaVu Sans", "Bitstream Vera Sans", "Arial"],
    "font.serif": ["DejaVu Serif", "Times New Roman"],
    "font.monospace": ["DejaVu Sans Mono", "Courier New"],
    "savefig.transparent": False,
}
_RC_DEFAULTS = dict(rcParams)


class _Namespace:
    def __init__(self, **values): self.__dict__.update(values)


class _BivarColormap:
    """A small bivariate two-input colormap used by the Matplotlib corpus."""

    def __init__(self, name, shape="square"):
        self.name = str(name)
        self.shape = str(shape)

    def __call__(self, values):
        if isinstance(values, tuple) and len(values) == 2:
            x0, x1 = values
        else:
            array = np.asarray(values, dtype=float)
            if array.shape[-1] != 2:
                raise ValueError("a bivariate colormap needs two input channels")
            x0, x1 = array[..., 0], array[..., 1]
        x0 = np.asarray(x0, dtype=float)
        x1 = np.asarray(x1, dtype=float)
        u = np.clip((x0 + 0.1) / 1.2, 0.0, 1.0)
        v = np.clip((x1 + 0.1) / 1.2, 0.0, 1.0)
        if self.shape.startswith("circle"):
            radius = np.hypot(u - 0.5, v - 0.5)
            angle = np.arctan2(v - 0.5, u - 0.5)
            red = 0.5 + 0.5 * np.cos(angle)
            green = 0.5 + 0.5 * np.cos(angle - 2.0 * np.pi / 3.0)
            blue = 0.5 + 0.5 * np.cos(angle + 2.0 * np.pi / 3.0)
            shade = np.clip(1.0 - radius / 0.72, 0.0, 1.0)
            rgb = np.stack([red * shade, green * shade, blue * shade], axis=-1)
            if self.shape.endswith("ignore"):
                rgb = np.where((radius <= 0.72)[..., None], rgb, 1.0)
        else:
            red = np.clip(1.0 - np.abs(u - v), 0.0, 1.0)
            green = np.clip(1.0 - np.abs(u - 0.35), 0.0, 1.0)
            blue = np.clip(1.0 - np.abs(v - 0.65), 0.0, 1.0)
            rgb = np.stack([red, green, blue], axis=-1)
        return np.clip(rgb, 0.0, 1.0)

    def with_extremes(self, **kwargs):
        shape = kwargs.get("shape", self.shape)
        return _BivarColormap(self.name, shape)


bivar_colormaps = {
    "BiPeak": _BivarColormap("BiPeak", "square"),
    "BiCone": _BivarColormap("BiCone", "circle"),
}


class _AxisModule(_Namespace):
    """`matplotlib.axis` plus the callable `plt.axis` compatibility shim."""

    def __call__(self, *args, **kwargs): return gca().axis(*args, **kwargs)


class _NoopContext:
    """A context manager for calls such as `with plt.xkcd():` that do nothing."""

    def __enter__(self): return self
    def __exit__(self, *exc): return False


class _ListedColormap:
    def __init__(self, colors, name="from_list", over=None, under=None, bad=None):
        self.colors = [_norm_color(c) for c in colors]
        self.name, self.N = str(name), len(self.colors)
        self._bad = _norm_color(bad) if bad is not None else None
        self._under = _norm_color(under) if under is not None else None
        self._over = _norm_color(over) if over is not None else None

    @classmethod
    def from_list(cls, name, colors, N=256):
        if len(colors) and isinstance(colors[0], (tuple, list)) and len(colors[0]) == 2:
            colors = [c for _, c in colors]
        return cls(colors, name)

    @property
    def _rgb(self):
        return np.asarray([_rgba_tuple(c)[:3] for c in self.colors], dtype=np.float64)

    def set_bad(self, color="k", alpha=None): self._bad = _norm_color(color)
    def set_under(self, color="k", alpha=None): self._under = _norm_color(color)
    def set_over(self, color="k", alpha=None): self._over = _norm_color(color)

    def __call__(self, X, alpha=None, bytes=False):
        arr = np.asarray(X, dtype=float)
        index = np.clip((arr * self.N).astype(int), 0, self.N - 1)
        rgb = np.asarray([[int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)]
                          for c in self.colors], dtype=float) / 255.0
        out = rgb[index]
        return out.astype(np.uint8) if bytes else out


def from_levels_and_colors(levels, colors, extend="neither"):
    """A `(cmap, norm)` pair for discrete levels, as `colors.from_levels_and_colors`."""
    boundaries = np.asarray(levels, dtype=float).ravel()
    if boundaries.size < 2:
        raise ValueError("levels needs at least two boundaries")
    palette = [_norm_color(c) for c in colors]
    if not palette:
        raise ValueError("from_levels_and_colors needs at least one colour")
    ncolors = boundaries.size - 1
    palette = [palette[i % len(palette)] for i in range(ncolors)]
    cmap = _ListedColormap(palette, "from_levels_and_colors")
    if extend in ("both", "min"):
        cmap.set_under(palette[0])
    if extend in ("both", "max"):
        cmap.set_over(palette[-1])
    return cmap, _BoundaryNorm(boundaries, ncolors, extend=extend)


def _norm_values(norm, data):
    """Fold `norm` into the data so the renderer's 0-1 mapping is linear."""
    if isinstance(norm, str):
        kind = norm.lower()
        if kind in ("linear", "none", ""):
            return np.asarray(data, dtype=float), None, None
        if kind == "log":
            norm = _LogNorm()
        else:
            raise NotImplementedError(f"norm={norm!r} is not supported yet")
    values = np.asarray(data, dtype=float)
    finite = values[np.isfinite(values)]
    if getattr(norm, "vmin", None) is None and finite.size:
        norm.vmin = float(finite.min())
    if getattr(norm, "vmax", None) is None and finite.size:
        norm.vmax = float(finite.max())
    return np.asarray(norm(values), dtype=float), 0.0, 1.0


class _LinearSegmentedColormap(_ListedColormap):
    """Colormap built from channel tables, as `LinearSegmentedColormap`."""

    def __init__(self, name, segmentdata, N=256, gamma=1.0):
        samples = np.linspace(0.0, 1.0, max(int(N), 2))
        channels = []
        for key in ("red", "green", "blue"):
            table = segmentdata.get(key, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))
            points = np.asarray(table, dtype=float)
            middle = points[:, 2] if points.shape[1] >= 3 else points[:, 1]
            channels.append(np.interp(samples, points[:, 0], middle))
        rows = np.clip(np.stack(channels, axis=1), 0.0, 1.0) ** (1.0 / float(gamma))
        colors = [f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"
                  for r, g, b in rows]
        super().__init__(colors, name)

    @classmethod
    def from_list(cls, name, colors, N=256):
        """Resample a list of colours (or value/colour pairs) into `N` steps."""
        if len(colors) and isinstance(colors[0], (tuple, list)) and len(colors[0]) == 2:
            colors = [c for _, c in colors]
        stops = np.asarray([_rgba_tuple(c)[:3] for c in colors], dtype=float)
        positions = (np.linspace(0.0, 1.0, stops.shape[0]) if stops.shape[0] > 1
                     else np.asarray([0.0]))
        samples = np.linspace(0.0, 1.0, max(int(N), 2))
        table = (np.stack([np.interp(samples, positions, stops[:, channel])
                           for channel in range(3)], axis=1)
                 if stops.shape[0] > 1 else np.tile(stops[0], (samples.size, 1)))
        hexes = [f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"
                 for r, g, b in table]
        instance = cls.__new__(cls)
        _ListedColormap.__init__(instance, hexes, name)
        return instance


def _rgba_tuple(color):
    value = _norm_color(color)
    if value in (None, "none"):
        return (0.0, 0.0, 0.0, 0.0)
    body = value[1:]
    rgba = [int(body[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    rgba.append(int(body[6:8], 16) / 255.0 if len(body) == 8 else 1.0)
    return tuple(rgba)


class _Mlab:
    """Small subset of matplotlib.mlab used by the signal examples."""

    @staticmethod
    def window_hanning(x):
        x = np.asarray(x)
        return np.hanning(x.size) * x

    @staticmethod
    def window_none(x): return x

    @staticmethod
    def detrend_none(x, axis=-1): return x

    @staticmethod
    def detrend_mean(x, axis=-1):
        x = np.asarray(x)
        return x - np.mean(x, axis=axis, keepdims=True)


class _MultivarColormap:
    """Minimal multivariate colormap: sample the first component."""

    def __init__(self, cmaps, combination_mode=None):
        self.cmaps = list(cmaps)
        self.combination_mode = combination_mode
        self.N = min(int(getattr(c, "N", 256)) for c in self.cmaps) if self.cmaps else 0

    def __call__(self, X, alpha=None, bytes=False):
        values = X[0] if isinstance(X, tuple) else X
        if not self.cmaps:
            raise ValueError("MultivarColormap needs at least one component")
        result = np.asarray(self.cmaps[0](values, alpha=alpha))
        if result.ndim == 2:
            result = np.stack([result] * 3, axis=-1)
        if result.shape[-1] == 3:
            result = np.concatenate(
                [result, np.ones((*result.shape[:-1], 1), dtype=result.dtype)],
                axis=-1)
        return (np.round(result * 255.0).astype(np.uint8) if bytes else result)


class _MColors:
    Normalize = _Normalize
    Norm = _Normalize
    MultivarColormap = _MultivarColormap
    LogNorm = _LogNorm
    PowerNorm = _PowerNorm
    SymLogNorm = _SymLogNorm
    NoNorm = _Normalize
    TwoSlopeNorm = _TwoSlopeNorm
    BoundaryNorm = _BoundaryNorm
    AsinhNorm = _AsinhNorm
    Colormap = Colormap
    ListedColormap = _ListedColormap
    LinearSegmentedColormap = _LinearSegmentedColormap
    TABLEAU_COLORS: ClassVar[dict] = dict(_TAB10)
    BASE_COLORS: ClassVar[dict] = {
        name: _norm_color(name) for name in ("b", "g", "r", "c", "m", "y", "k", "w")}
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


def rgb_to_hsv(rgb):
    """Convert an RGB(A) array in 0..1 to HSV on the trailing axis."""
    rgb = np.asarray(rgb, dtype=float)
    r, g, b = np.moveaxis(rgb[..., :3], -1, 0)
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    delta = maxc - minc
    hue = np.zeros_like(maxc)
    safe = delta > 1e-300
    rmax = safe & (maxc == r)
    gmax = safe & (maxc == g) & ~rmax
    bmax = safe & ~rmax & ~gmax
    hue[rmax] = ((g[rmax] - b[rmax]) / delta[rmax]) % 6.0
    hue[gmax] = (b[gmax] - r[gmax]) / delta[gmax] + 2.0
    hue[bmax] = (r[bmax] - g[bmax]) / delta[bmax] + 4.0
    hue /= 6.0
    sat = np.divide(delta, maxc, out=np.zeros_like(delta), where=maxc > 1e-300)
    return np.stack([hue, sat, maxc], axis=-1)


def hsv_to_rgb(hsv):
    """Convert an HSV array in 0..1 to RGB on the trailing axis."""
    hsv = np.asarray(hsv, dtype=float)
    h, s, v = np.moveaxis(hsv[..., :3], -1, 0)
    i = np.floor(h * 6.0)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i = i.astype(int) % 6
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


class LightSource:
    """Light source for hillshading, matching Matplotlib's blend modes."""

    def __init__(self, azdeg=315, altdeg=45, hsv_min_val=0, hsv_max_val=1,
                 hsv_min_sat=1, hsv_max_sat=0):
        self.azdeg = float(azdeg)
        self.altdeg = float(altdeg)
        self.hsv_min_val = hsv_min_val
        self.hsv_max_val = hsv_max_val
        self.hsv_min_sat = hsv_min_sat
        self.hsv_max_sat = hsv_max_sat

    @property
    def direction(self):
        az = np.radians(90 - self.azdeg)
        alt = np.radians(self.altdeg)
        return np.array([np.cos(az) * np.cos(alt),
                         np.sin(az) * np.cos(alt),
                         np.sin(alt)])

    def hillshade(self, elevation, vert_exag=1, dx=1, dy=1, fraction=1.0):
        dy = -float(dy)
        elevation = np.asarray(elevation, dtype=float)
        e_dy, e_dx = np.gradient(float(vert_exag) * elevation, dy, dx)
        normal = np.empty((*elevation.shape, 3), dtype=float)
        normal[..., 0], normal[..., 1], normal[..., 2] = -e_dx, -e_dy, 1.0
        normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
        return self.shade_normals(normal, fraction=fraction)

    def shade_normals(self, normals, fraction=1.0):
        intensity = np.asarray(normals, dtype=float).dot(self.direction)
        imin, imax = float(np.nanmin(intensity)), float(np.nanmax(intensity))
        intensity = intensity * float(fraction)
        if imax - imin > 1e-6:
            intensity = (intensity - imin) / (imax - imin)
        return np.clip(intensity, 0.0, 1.0)

    def shade(self, data, cmap, norm=None, blend_mode="overlay", vmin=None,
              vmax=None, vert_exag=1, dx=1, dy=1, fraction=1, **kwargs):
        data = np.asarray(data, dtype=float)
        if norm is None:
            lo = np.nanmin(data) if vmin is None else float(vmin)
            hi = np.nanmax(data) if vmax is None else float(vmax)
            normed = np.clip((data - lo) / (hi - lo if hi > lo else 1.0), 0.0, 1.0)
        elif getattr(norm, "vmin", None) is not None and getattr(norm, "vmax", None) is not None:
            lo, hi = float(norm.vmin), float(norm.vmax)
            normed = np.clip((data - lo) / (hi - lo if hi > lo else 1.0), 0.0, 1.0)
        else:
            normed = np.asarray(norm(data), dtype=float)
        rgb0 = get_cmap(_cmap_name(cmap))(normed)
        rgb1 = self.shade_rgb(rgb0[..., :3], data, blend_mode=blend_mode,
                              vert_exag=vert_exag, dx=dx, dy=dy,
                              fraction=fraction, **kwargs)
        rgb0 = np.array(rgb0, copy=True)
        rgb0[..., :3] = rgb1
        return rgb0

    def shade_rgb(self, rgb, elevation, fraction=1.0, blend_mode="hsv",
                  vert_exag=1, dx=1, dy=1, **kwargs):
        rgb = np.asarray(rgb, dtype=float)
        intensity = self.hillshade(elevation, vert_exag=vert_exag, dx=dx, dy=dy,
                                   fraction=fraction)[..., np.newaxis]
        lookup = {"hsv": self.blend_hsv, "soft": self.blend_soft_light,
                  "overlay": self.blend_overlay}
        if blend_mode in lookup:
            return lookup[blend_mode](rgb, intensity, **kwargs)
        if callable(blend_mode):
            return blend_mode(rgb, intensity, **kwargs)
        raise ValueError(f'"blend_mode" must be callable or one of {tuple(lookup)}')

    def blend_hsv(self, rgb, intensity, hsv_max_sat=None, hsv_max_val=None,
                  hsv_min_val=None, hsv_min_sat=None):
        hsv_max_sat = self.hsv_max_sat if hsv_max_sat is None else hsv_max_sat
        hsv_max_val = self.hsv_max_val if hsv_max_val is None else hsv_max_val
        hsv_min_sat = self.hsv_min_sat if hsv_min_sat is None else hsv_min_sat
        hsv_min_val = self.hsv_min_val if hsv_min_val is None else hsv_min_val
        intensity = np.asarray(intensity, dtype=float)[..., 0] * 2.0 - 1.0
        hsv = rgb_to_hsv(np.asarray(rgb, dtype=float)[..., :3])
        _hue, sat, val = np.moveaxis(hsv, -1, 0)
        positive = (np.abs(sat) > 1e-10) & (intensity > 0)
        negative = (np.abs(sat) > 1e-10) & (intensity < 0)
        sat[positive] = (1 - intensity[positive]) * sat[positive] + intensity[positive] * hsv_max_sat
        sat[negative] = (1 + intensity[negative]) * sat[negative] - intensity[negative] * hsv_min_sat
        val[intensity > 0] = ((1 - intensity[intensity > 0]) * val[intensity > 0]
                              + intensity[intensity > 0] * hsv_max_val)
        val[intensity < 0] = ((1 + intensity[intensity < 0]) * val[intensity < 0]
                              - intensity[intensity < 0] * hsv_min_val)
        hsv[..., 1:] = np.clip(hsv[..., 1:], 0.0, 1.0)
        return hsv_to_rgb(hsv)

    def blend_soft_light(self, rgb, intensity):
        rgb = np.asarray(rgb, dtype=float)
        return 2 * intensity * rgb + (1 - 2 * intensity) * rgb**2

    def blend_overlay(self, rgb, intensity):
        rgb = np.asarray(rgb, dtype=float)
        low = 2 * intensity * rgb
        high = 1 - 2 * (1 - intensity) * (1 - rgb)
        return np.where(rgb <= 0.5, low, high)


class Colorizer:
    """Shared norm/cmap pair accepted by `imshow(colorizer=...)`."""

    def __init__(self, norm=None, cmap=None):
        self.norm = norm
        self.cmap = cmap


class ScalarMappable:
    """Minimal `matplotlib.cm.ScalarMappable` for standalone colorbars."""

    def __init__(self, norm=None, cmap=None):
        self.norm = norm if norm is not None else _Normalize()
        self.cmap = _cmap_name(cmap)
        self._array = None

    def set_array(self, values):
        self._array = None if values is None else np.asarray(values, dtype=float)
        return self

    def get_array(self): return self._array

    def set_clim(self, vmin=None, vmax=None):
        self.norm.vmin = vmin
        self.norm.vmax = vmax
        return self

    def get_clim(self): return (self.norm.vmin, self.norm.vmax)
    def get_cmap(self): return self.cmap

    def _colorbar_spec(self):
        lo, hi = self.norm.vmin, self.norm.vmax
        if self._array is not None and (lo is None or hi is None):
            values = self._array[np.isfinite(self._array)]
            if values.size:
                lo = float(values.min()) if lo is None else lo
                hi = float(values.max()) if hi is None else hi
        lo = 0.0 if lo is None else float(lo)
        hi = 1.0 if hi is None else float(hi)
        if not hi > lo:
            lo, hi = lo - 0.5, lo + 0.5
        return dict(cmap=self.cmap, vmin=lo, vmax=hi)


class _NoopLocator:
    def __init__(self, *args, **kwargs): pass
    def __call__(self): return []
    def tick_values(self, vmin, vmax): return np.array([vmin, vmax], dtype=float)
    def set_params(self, **kwargs): return None
    def set_axis(self, axis): return None


NullLocator = _NoopLocator


class _Locator:
    """Base for the major locators that really place ticks.

    Matplotlib derives tick positions from the locator attached to the axis,
    so accepting `set_major_locator` without using it silently ignores the
    caller's tick choice. `_NoopLocator` stays for the locators that only
    need to be accepted, such as `LogLocator` and `NullLocator`.
    """

    axis = None

    def set_axis(self, axis): self.axis = axis
    def set_params(self, **kwargs): return None
    def __call__(self, vmin=None, vmax=None):
        if vmin is None or vmax is None:
            raise ValueError("a locator needs the axis limits")
        return self.tick_values(vmin, vmax)


def _locator_span(vmin, vmax):
    return (vmin, vmax) if vmin <= vmax else (vmax, vmin)


def _locator_value(value):
    """Drop the binary noise so 3 * 0.1 reads as 0.3."""
    return float(f"{value:.12g}")


class _MultipleLocator(_Locator):
    """Ticks at multiples of `base`, as `ticker.MultipleLocator`."""

    def __init__(self, base=1.0, offset=0.0):
        self.base, self.offset = float(base), float(offset)

    def set_params(self, base=None, offset=None):
        if base is not None:
            self.base = float(base)
        if offset is not None:
            self.offset = float(offset)

    def tick_values(self, vmin, vmax):
        lo, hi = _locator_span(vmin, vmax)
        base = self.base if self.base > 0 else 1.0
        first = _math.ceil((lo - self.offset) / base - 1e-9) * base + self.offset
        last = _math.floor((hi - self.offset) / base + 1e-9) * base + self.offset
        count = int(round((last - first) / base)) + 1 if last >= first else 0
        return np.asarray([_locator_value(first + i * base) for i in range(count)])


class _IndexLocator(_Locator):
    """Ticks at `offset + base * i`, as `ticker.IndexLocator`."""

    def __init__(self, base, offset=0.0):
        self.base, self.offset = float(base), float(offset)

    def tick_values(self, vmin, vmax):
        lo, hi = _locator_span(vmin, vmax)
        if self.base <= 0:
            return np.asarray([], dtype=float)
        count = int(_math.floor((hi - self.offset) / self.base + 1e-9)) + 1
        values = [self.offset + i * self.base for i in range(max(count, 0))]
        return np.asarray([v for v in values if v >= lo - 1e-9], dtype=float)


class _LogLocator(_Locator):
    """Ticks at powers of `base`, optionally at `subs` multiples of each power."""

    def __init__(self, base=10.0, subs=(1.0,), numticks=None, **kwargs):
        self.base = float(base)
        self.subs = subs
        self.numticks = numticks

    def set_params(self, base=None, subs=None, numticks=None):
        if base is not None:
            self.base = float(base)
        if subs is not None:
            self.subs = subs
        if numticks is not None:
            self.numticks = numticks

    def tick_values(self, vmin, vmax):
        lo, hi = sorted((float(vmin), float(vmax)))
        if hi <= 0.0:
            return np.array([], dtype=float)
        lo = lo if lo > 0.0 else hi * 1e-12
        base = self.base if self.base > 1.0 else 10.0
        first = int(_math.floor(_math.log(lo, base))) - 1
        last = int(_math.ceil(_math.log(hi, base))) + 1
        if self.subs is None:
            subs = (1.0,)
        elif np.isscalar(self.subs):
            subs = (float(self.subs),)
        else:
            subs = tuple(float(s) for s in np.ravel(self.subs))
        values = [sub * base ** exp
                  for exp in range(first, last + 1) for sub in subs]
        values = [v for v in values if lo * (1 - 1e-9) <= v <= hi * (1 + 1e-9)]
        return np.asarray(sorted(values), dtype=float)


class _MaxNLocator(_Locator):
    """Roughly `nbins` "nice" ticks, as `ticker.MaxNLocator`."""

    _STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)

    def __init__(self, nbins=None, steps=None, **kwargs):
        self.nbins = nbins
        self.steps = tuple(float(v) for v in steps) if steps else self._STEPS

    def set_params(self, nbins=None, steps=None, **kwargs):
        if nbins is not None:
            self.nbins = nbins
        if steps is not None:
            self.steps = tuple(float(v) for v in steps)

    def tick_values(self, vmin, vmax):
        lo, hi = _locator_span(vmin, vmax)
        if not hi > lo:
            return np.asarray([_locator_value(lo)])
        nbins = 9 if self.nbins in (None, "auto") else max(1, int(self.nbins))
        raw = (hi - lo) / nbins
        magnitude = 10.0 ** _math.floor(_math.log10(raw))
        step = magnitude * self.steps[-1]
        for candidate in sorted(self.steps):
            if magnitude * candidate >= raw - 1e-12:
                step = magnitude * candidate
                break
        first = _math.ceil(lo / step - 1e-9) * step
        count = int(_math.floor((hi - first) / step + 1e-9)) + 1
        return np.asarray([_locator_value(first + i * step) for i in range(max(count, 0))])


class _FixedLocator(_Locator):
    """Ticks exactly at `locs`."""

    def __init__(self, locs, **kwargs):
        self.locs = np.asarray(locs, dtype=float).ravel()

    def tick_values(self, vmin, vmax): return self.locs
    def __call__(self, vmin=None, vmax=None): return self.locs


class _LinearLocator(_Locator):
    """`numticks` ticks evenly spaced over the axis limits."""

    def __init__(self, numticks=None, **kwargs):
        self.numticks = numticks

    def set_params(self, numticks=None, **kwargs):
        if numticks is not None:
            self.numticks = numticks

    def tick_values(self, vmin, vmax):
        num = 6 if self.numticks is None else max(2, int(self.numticks))
        return np.linspace(vmin, vmax, num)


class _NoopFormatter:
    def __init__(self, *args, **kwargs): self.args = args
    def __call__(self, value, pos=None): return str(value)
    def set_axis(self, axis): return None
    def set_locs(self, locs): return None
    def create_dummy_axis(self, **kwargs): return None


class _PathEffects:
    class Normal:
        def __init__(self, *args, **kwargs): pass
    class SimplePatchShadow:
        def __init__(self, *args, **kwargs): pass
    class SimpleLineShadow:
        def __init__(self, *args, **kwargs): pass
    class Stroke:
        def __init__(self, *args, **kwargs): pass
    class PathPatchEffect:
        def __init__(self, *args, **kwargs): pass

    @staticmethod
    def withStroke(*args, **kwargs): return _PathEffects.Stroke()

    @staticmethod
    def withTickedStroke(*args, **kwargs): return _PathEffects.Stroke()

    @staticmethod
    def withSimplePatchShadow(*args, **kwargs): return _PathEffects.SimplePatchShadow()


class _TransformedBbox:
    """Bbox carried through a transform; matplotvite transforms are identities."""

    def __init__(self, bbox, transform=None):
        self._bbox, self._transform = bbox, transform

    @property
    def x0(self): return float(self._bbox.x0)
    @property
    def y0(self): return float(self._bbox.y0)
    @property
    def x1(self): return float(self._bbox.x1)
    @property
    def y1(self): return float(self._bbox.y1)
    @property
    def width(self): return self.x1 - self.x0
    @property
    def height(self): return self.y1 - self.y0

    def get_points(self):
        return np.asarray([[self.x0, self.y0], [self.x1, self.y1]], dtype=float)

    def transformed(self, transform):
        return _TransformedBbox(self._bbox, transform)


class FontProperties:
    """`FontProperties` accepts Matplotlib's font settings; size is the one the
    renderer uses, the rest are kept for code that reads them back."""

    def __init__(self, family=None, style=None, variant=None, weight=None,
                 stretch=None, size=None, fname=None, math_fontfamily=None, **kwargs):
        self._family, self._style, self._variant = family, style, variant
        self._weight, self._stretch, self._size = weight, stretch, size
        self._fname, self._math_fontfamily = fname, math_fontfamily

    def copy(self):
        return FontProperties(self._family, self._style, self._variant, self._weight,
                              self._stretch, self._size, self._fname,
                              self._math_fontfamily)

    get_family = lambda self: self._family
    get_style = lambda self: self._style
    get_variant = lambda self: self._variant
    get_weight = lambda self: self._weight
    get_stretch = lambda self: self._stretch
    get_size = lambda self: self._size
    get_size_in_points = lambda self: self._size
    get_file = lambda self: self._fname
    set_family = lambda self, value: setattr(self, "_family", value)
    set_style = lambda self, value: setattr(self, "_style", value)
    set_variant = lambda self, value: setattr(self, "_variant", value)
    set_weight = lambda self, value: setattr(self, "_weight", value)
    set_stretch = lambda self, value: setattr(self, "_stretch", value)
    set_size = lambda self, value: setattr(self, "_size", value)
    set_file = lambda self, value: setattr(self, "_fname", value)


class _StyleValue(str):
    def __new__(cls, value, name):
        obj = super().__new__(cls, value)
        obj.name = name
        return obj


class _StyleMeta(type):
    def __iter__(cls): return iter(cls._members())
    def __len__(cls): return len(cls._members())


class CapStyle(str, metaclass=_StyleMeta):
    butt = _StyleValue("butt", "butt")
    round = _StyleValue("round", "round")
    projecting = _StyleValue("projecting", "projecting")

    @classmethod
    def _members(cls): return (cls.butt, cls.round, cls.projecting)

    @staticmethod
    def demo():
        _, ax = subplots(figsize=(5, 2.5))
        for row, style in enumerate(("butt", "round", "projecting")):
            line, = ax.plot([0.2, 0.8], [row, row], linewidth=12)
            line.set_solid_capstyle(style)
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(-0.5, 2.5)
        ax.set_axis_off()


class JoinStyle(str, metaclass=_StyleMeta):
    miter = _StyleValue("miter", "miter")
    round = _StyleValue("round", "round")
    bevel = _StyleValue("bevel", "bevel")

    @classmethod
    def _members(cls): return (cls.miter, cls.round, cls.bevel)

    @staticmethod
    def demo():
        _, ax = subplots(figsize=(5, 2.5))
        for row, style in enumerate(("miter", "round", "bevel")):
            line, = ax.plot([0.1, 0.4, 0.7], [row, row + 0.8, row], linewidth=12)
            line.set_solid_joinstyle(style)
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(-0.5, 2.8)
        ax.set_axis_off()


def same_color(*colors):
    """True when every colour argument normalises to the same value."""
    return len({_norm_color(c) for c in colors}) == 1


def _num_to_date(value, tz=None): return _date_from_num(float(value))


class _DateFormatter:
    """Format a date number with `strftime`; `fmt` is Matplotlib's format."""

    def __init__(self, fmt="%Y-%m-%d", tz=None):
        self.fmt, self.tz = str(fmt), tz

    def __call__(self, x, pos=None):
        return _date_from_num(float(x)).strftime(self.fmt)

    def set_tzinfo(self, tz): self.tz = tz
    def get_offset(self): return ""


class _AutoDateFormatter:
    """Date formatter that chooses a readable format from the tick value."""

    def __init__(self, locator=None, tz=None, formats=None, offset_formats=None,
                 zero_formats=None, show_offset=True):
        self.locator = locator
        self.tz = tz
        self.formats = formats
        self.offset_formats = offset_formats
        self.zero_formats = zero_formats
        self.show_offset = show_offset

    def __call__(self, x, pos=None):
        dt = _date_from_num(float(x))
        if dt.hour or dt.minute or dt.second or dt.microsecond:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d")

    def format_ticks(self, values):
        return [self(value, i) for i, value in enumerate(values)]

    def get_offset(self): return ""
    def set_axis(self, axis): self.axis = axis


class _ConciseDateFormatter:
    """Date formatter that picks a compact unit based on the tick's resolution."""

    _DEFAULT_FORMATS: ClassVar[tuple[str, ...]] = (
        "%Y", "%b", "%d", "%H:%M", "%H:%M", "%S.%f")

    def __init__(self, locator=None, tz=None, formats=None,
                 offset_formats=None, zero_formats=None, show_offset=True):
        self.locator = locator
        self.tz = tz
        self.formats = list(formats or self._DEFAULT_FORMATS)
        self.zero_formats = list(zero_formats or ["", *self.formats[:-1]])
        self.offset_formats = list(offset_formats or [""] * 6)
        self.show_offset = show_offset

    def __call__(self, x, pos=None):
        dt = _date_from_num(float(x))
        if dt.microsecond or dt.second:
            level = 5
        elif dt.minute:
            level = 4
        elif dt.hour:
            level = 3
        elif dt.day != 1:
            level = 2
        elif dt.month != 1:
            level = 1
        else:
            level = 0
        fmt = self.formats[min(level, len(self.formats) - 1)]
        return dt.strftime(fmt)

    def format_ticks(self, values):
        return [self(value, i) for i, value in enumerate(values)]

    def format_data(self, value): return self(value)
    def format_data_short(self, value): return self(value)
    def get_offset(self): return ""
    def set_axis(self, axis): self.axis = axis
    def set_tzinfo(self, tz): self.tz = tz


class _ConciseDateConverter:
    """Units converter that installs the concise date locator and formatter."""

    def __init__(self, formats=None, zero_formats=None, offset_formats=None):
        self.formats = formats
        self.zero_formats = zero_formats
        self.offset_formats = offset_formats

    def axisinfo(self, unit, axis):
        locator = _AutoDateLocator()
        formatter = _ConciseDateFormatter(
            locator, formats=self.formats, zero_formats=self.zero_formats,
            offset_formats=self.offset_formats)
        return units.AxisInfo(majloc=locator, majfmt=formatter)

    def default_units(self, x, axis): return None

    def convert(self, value, unit, axis): return _date_to_num(value)


class _AutoDateLocator:
    """Calendar-aware locator on the date-number axis."""

    def __init__(self, *args, **kwargs): pass

    def tick_values(self, vmin, vmax):
        ticks, _ = _date_ticks(float(vmin), float(vmax))
        return np.asarray(ticks, dtype=float)

    def __call__(self, vmin, vmax): return self.tick_values(vmin, vmax)
    def set_axis(self, axis): self.axis = axis


class _rrulewrapper:
    """Store recurrence-rule arguments; date ticks use the calendar fallback."""

    def __init__(self, freq, **kwargs):
        self.freq = freq
        self.kwargs = kwargs


class _RRuleLocator(_AutoDateLocator):
    """Recurrence-rule locator, backed by the calendar locator."""

    def __init__(self, rule=None, *args, **kwargs):
        super().__init__()
        self.rule = rule


def _drange(dstart, dend, delta):
    """Inclusive sequence of dates from `dstart` to `dend` by `delta`."""
    out = []
    current = dstart
    while current <= dend:
        out.append(current)
        current = current + delta
    return out


class _CalendarLocator:
    """Ticks aligned to a calendar unit: years, months, days or smaller.

    `interval` steps by that many units; `bymonth`/`bymonthday` accept
    Matplotlib's arguments but only the first value is honoured.
    """

    unit = "day"

    def __init__(self, interval=1, bymonth=None, bymonthday=None, **kwargs):
        if isinstance(interval, (list, tuple, range, np.ndarray)):
            self.byhour = list(interval)
            interval = 1
        self.interval = max(int(interval), 1)
        self.bymonth = (list(bymonth) if isinstance(bymonth, (list, tuple))
                        else ([bymonth] if bymonth is not None else None))
        self.bymonthday = (list(bymonthday) if isinstance(bymonthday, (list, tuple))
                           else ([bymonthday] if bymonthday is not None else None))

    def set_axis(self, axis): self.axis = axis

    def tick_values(self, vmin, vmax):
        vmin, vmax = float(vmin), float(vmax)
        if not (np.isfinite(vmin) and np.isfinite(vmax)) or vmax <= vmin:
            return np.asarray([vmin], dtype=float)
        if self.unit in ("year", "month"):
            ticks = self._calendar_ticks(vmin, vmax)
        else:
            step = {"day": 1.0, "hour": 1.0 / 24.0, "minute": 1.0 / 1440.0,
                    "second": 1.0 / 86400.0}[self.unit] * self.interval
            first = _math.ceil(vmin / step - 1e-9) * step
            ticks = [first + i * step for i in range(50) if first + i * step <= vmax + 1e-9]
        return np.asarray(ticks, dtype=float)

    def __call__(self, vmin, vmax): return self.tick_values(vmin, vmax)

    def _calendar_ticks(self, vmin, vmax):
        start = _date_from_num(vmin)
        if self.unit == "year":
            month = (self.bymonth or [1])[0]
            day = (self.bymonthday or [1])[0]
            year = start.year if (start.month, start.day) <= (month, day) else start.year + 1
            step, ticks = self.interval, []
            for i in range(60):
                year += step if i else 0
                try:
                    current = _datetime.datetime(year, month, day)
                except ValueError:
                    break
                value = _datetime_to_num(current)
                if value > vmax + 1e-9:
                    break
                ticks.append(value)
            return ticks
        month = (self.bymonth or [start.month])[0]
        current = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if self.bymonth is None and current.month != month:
            current = current.replace(month=month)
        ticks = []
        for _ in range(60):
            value = _datetime_to_num(current)
            if value > vmax + 1e-9:
                break
            if value >= vmin - 1e-9:
                ticks.append(value)
            current = _add_months(current, self.interval)
        return ticks


class _YearLocator(_CalendarLocator):
    unit = "year"


class _MonthLocator(_CalendarLocator):
    unit = "month"


class _DayLocator(_CalendarLocator):
    unit = "day"


class _HourLocator(_CalendarLocator):
    unit = "hour"


class _MinuteLocator(_CalendarLocator):
    unit = "minute"


class _SecondLocator(_CalendarLocator):
    unit = "second"


class _PercentFormatter:
    """Format a value as a percentage of `xmax`."""

    def __init__(self, xmax=100, decimals=None, symbol="%", is_latex=False):
        self.xmax = float(xmax)
        self.decimals = decimals
        self.symbol = symbol
        self.is_latex = is_latex

    def __call__(self, x, pos=None):
        if self.xmax == 0:
            return ""
        value = float(x) / self.xmax * 100.0
        decimals = self.decimals
        if decimals is None:
            decimals = 0 if abs(value - round(value)) < 1e-9 else 1
        return f"{value:.{decimals}f}{self.symbol}"

    def set_axis(self, axis): return None


class _EngFormatter:
    """Format values with SI prefixes, as Matplotlib's EngFormatter."""

    _PREFIXES = (("", 0), ("k", 3), ("M", 6), ("G", 9), ("T", 12),
                 ("P", 15), ("E", 18), ("Z", 21), ("Y", 24))

    def __init__(self, unit="", places=None, sep=" ", format=None, **kwargs):
        self.unit = str(unit)
        self.places = places
        self.sep = str(sep)
        self.format = format

    def __call__(self, x, pos=None):
        value = float(x)
        if value == 0 or not np.isfinite(value):
            return f"0{self.sep}{self.unit}" if self.unit else "0"
        sign = "-" if value < 0 else ""
        magnitude = abs(value)
        exponent = int(np.floor(np.log10(magnitude) / 3.0) * 3)
        exponent = max(-24, min(24, exponent))
        prefix = ""
        for text, power in self._PREFIXES:
            if exponent == power:
                prefix = text
                break
        else:
            if exponent < 0:
                prefix = ("m", "\u03bc", "n", "p", "f", "a", "z", "y")[
                    min(7, (-exponent // 3) - 1)]
        scaled = magnitude / (10.0 ** exponent)
        places = self.places
        if places is None:
            places = 0 if abs(scaled - round(scaled)) < 1e-9 else 1
        number = f"{scaled:.{places}f}"
        return f"{sign}{number}{self.sep}{prefix}{self.unit}"

    def set_axis(self, axis): return None


class _FixedFormatter:
    """Formatter that returns `seq[pos]`, as Matplotlib's FixedFormatter."""

    def __init__(self, seq): self.seq = list(seq)

    def __call__(self, x, pos=None):
        if pos is None or not 0 <= int(pos) < len(self.seq):
            raise IndexError("FixedFormatter position out of range")
        return self.seq[int(pos)]

    def set_axis(self, axis): return None


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_samples(row, count, channels, depth):
    """Unpack one unfiltered PNG scanline into integer samples."""
    total = count * channels
    if depth == 8:
        return list(row[:total])
    if depth == 16:
        return [_struct.unpack(">H", row[i:i + 2])[0]
                for i in range(0, total * 2, 2)]
    mask, values = (1 << depth) - 1, []
    for byte in row:
        for shift in range(8 - depth, -1, -depth):
            values.append((byte >> shift) & mask)
            if len(values) == total:
                return values
    return values


def _decode_png(data):
    """Decode a non-interlaced PNG into a float array in the range 0-1.

    Matplotlib's image tests use every PNG colour type and bit depth, while
    matplotvite deliberately has no Pillow dependency. This decoder covers the
    standard non-interlaced grayscale, palette, RGB and alpha variants.
    """
    if data[:8] != _PNG_SIGNATURE:
        raise ValueError("not a PNG file")
    width = height = depth = color = interlace = None
    palette = transparency = None
    compressed = bytearray()
    pos = 8
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, compression, filter_method, interlace = \
                _struct.unpack(">IIBBBBB", body[:13])
            if compression != 0 or filter_method != 0:
                raise ValueError("unsupported PNG compression or filter method")
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            transparency = body
        elif kind == b"IDAT":
            compressed.extend(body)
        elif kind == b"IEND":
            break
    if width is None:
        raise ValueError("PNG has no IHDR chunk")
    if interlace:
        raise NotImplementedError("interlaced PNG files are not supported")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
    if channels is None:
        raise ValueError(f"unsupported PNG colour type {color}")
    if depth not in (1, 2, 4, 8, 16) or (depth < 8 and color not in (0, 3)):
        raise ValueError(f"unsupported PNG bit depth {depth}")
    if color == 3 and palette is None:
        raise ValueError("palette PNG has no PLTE chunk")
    raw = _zlib.decompress(bytes(compressed))
    bits_per_pixel = channels * depth
    stride = (width * bits_per_pixel + 7) // 8
    bpp = max(1, (bits_per_pixel + 7) // 8)
    if len(raw) < height * (stride + 1):
        raise ValueError("truncated PNG image data")
    rows, previous, offset = [], bytearray(stride), 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset:offset + stride])
        offset += stride
        for i in range(stride):
            left = row[i - bpp] if i >= bpp else 0
            above = previous[i]
            upper_left = previous[i - bpp] if i >= bpp else 0
            if filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                p = left + above - upper_left
                pa, pb, pc = abs(p - left), abs(p - above), abs(p - upper_left)
                predictor = left if pa <= pb and pa <= pc else above if pb <= pc else upper_left
            elif filter_type == 0:
                predictor = 0
            else:
                raise ValueError(f"unsupported PNG filter type {filter_type}")
            row[i] = (row[i] + predictor) & 255
        rows.append(row)
        previous = row

    samples = [_png_samples(row, width, channels, depth) for row in rows]
    scale = (float((1 << depth) - 1) if color == 0 and depth < 8
             else 255.0 if depth <= 8 else 65535.0)
    if color == 3:
        entries = [tuple(palette[i:i + 3]) for i in range(0, len(palette), 3)]
        alpha = (list(transparency) if transparency else [])
        has_alpha = any(value != 255 for value in alpha)
        out = np.empty((height, width, 4 if has_alpha else 3), dtype=np.float64)
        for y, row in enumerate(samples):
            for x, index in enumerate(row):
                if index >= len(entries):
                    raise ValueError("PNG palette index out of range")
                rgb = entries[index]
                out[y, x, :3] = np.asarray(rgb, dtype=np.float64) / 255.0
                if has_alpha:
                    out[y, x, 3] = (alpha[index] if index < len(alpha) else 255) / 255.0
        return out

    array = np.asarray(samples, dtype=np.float64) / scale
    if color == 0:
        return array.reshape(height, width)
    image = array.reshape(height, width, channels)
    if color == 4:
        gray = image[..., 0:1]
        return np.concatenate([np.repeat(gray, 3, axis=2), image[..., 1:2]], axis=2)
    if color == 2 and transparency and len(transparency) == 6:
        key = np.asarray(_struct.unpack(">HHH", transparency), dtype=np.float64) / scale
        mask = np.all(image == key, axis=2)
        return np.concatenate([image, (~mask)[..., None].astype(np.float64)], axis=2)
    return image


def _imread(fname, format=None):
    """Read a PNG natively, or another image format through Pillow."""
    if hasattr(fname, "read"):
        data = fname.read()
    else:
        with open(os.fspath(fname), "rb") as stream:
            data = stream.read()
    if isinstance(data, str):
        data = data.encode("latin-1")
    if (format is None or str(format).lower() == "png") and data.startswith(_PNG_SIGNATURE):
        return _decode_png(data)
    try:
        import io

        from PIL import Image
    except ImportError as exc:
        raise ImportError(
            "matplotvite.imread supports PNG without Pillow; other formats need Pillow"
        ) from exc
    with Image.open(io.BytesIO(data), formats=None if format is None else [format]) as image:
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            return np.asarray(image.convert("RGBA"), dtype=np.float64) / 255.0
        return np.asarray(image.convert("RGB"), dtype=np.float64) / 255.0


imread = _imread


def _get_sample_data(name, asfileobj=True):
    """Matplotlib's sample-data directory is not shipped with matplotvite."""
    raise FileNotFoundError(
        f"matplotvite does not bundle Matplotlib's sample data ({name!r})")


def _flatten(seq, scalarp=None):
    """Depth-first flatten of nested sequences, as `cbook.flatten`."""
    if scalarp is None:
        scalarp = lambda value: not hasattr(value, "__iter__") or isinstance(value, str)
    if scalarp(seq):
        return [seq]
    out = []
    for item in seq:
        out.extend(_flatten(item, scalarp))
    return out


class GridSpecFromSubplotSpec(GridSpec):
    """A GridSpec rooted at an existing SubplotSpec."""

    def __init__(self, nrows, ncols, subplot_spec=None, **kwargs):
        super().__init__(nrows, ncols, **kwargs)
        self.subplot_spec = subplot_spec


def _offset_copy(trans, fig=None, x=0, y=0, units="inches", **kwargs):
    _ignored("mtransforms.offset_copy")
    return _Transform()


def _blended_transform_factory(x_transform, y_transform):
    """Combined transform: matplotvite only distinguishes data/axes/figure."""
    kinds = {getattr(t, "kind", None) for t in (x_transform, y_transform)}
    for kind in ("axes", "figure"):
        if kind in kinds:
            return _CoordTransform(kind)
    return _Transform()


mcolors = _MColors()
mcolors.ScalarMappable = ScalarMappable
mcolors.LightSource = LightSource
mcolors.rgb_to_hsv = rgb_to_hsv
mcolors.hsv_to_rgb = hsv_to_rgb
mcolors.Normalize = _Normalize
mcolors.from_levels_and_colors = from_levels_and_colors
mcolorbar = _Namespace(Colorbar=Colorbar, ColorbarBase=Colorbar)
# The gallery binds `matplotlib.colorbar` to this callable, so expose the
# classes on the function as well as in the standalone namespace.
colorbar.Colorbar = Colorbar
colorbar.ColorbarBase = Colorbar
cm.ScalarMappable = ScalarMappable
colors = mcolors
mpatches = patches
mpath = _Namespace(Path=Path, TransformedPath=TransformedPath)
path = mpath
mcollections = _Namespace(Collection=Collection, LineCollection=LineCollection,
                          PolyCollection=PolyCollection, PatchCollection=PatchCollection,
                          EventCollection=EventCollection, PathCollection=PathCollection,
                          RegularPolyCollection=RegularPolyCollection,
                          EllipseCollection=EllipseCollection)
collections = mcollections
markers = _Namespace(MarkerStyle=MarkerStyle)
mmarkers = markers
_INTERPD = {name: name for name in (
    "none", "nearest", "antialiased", "bilinear", "bicubic", "spline16",
    "spline36", "hanning", "hamming", "hermite", "kaiser", "quadric",
    "catrom", "gaussian", "lanczos", "blackman", "sinc", "bessel",
    "mitchell", "auto",
)}
image = _Namespace(imread=_imread, NonUniformImage=NonUniformImage,
                   _interpd_=_INTERPD)
colorizer = _Namespace(Colorizer=Colorizer)
mtransforms = _Namespace(Transform=_Transform, Affine2D=Affine2D, Bbox=_Bbox,
                         TransformedPath=TransformedPath,
                         BboxTransformTo=_Transform, IdentityTransform=_IdentityTransform,
                         ScaledTranslation=_Transform, TransformedBbox=_TransformedBbox,
                         blended_transform_factory=_blended_transform_factory,
                         offset_copy=_offset_copy)
transforms = mtransforms
class _Tick:
    """Minimal tick container for projection subclasses."""

    def __init__(self, axes=None, loc=None, major=True):
        self.axes = axes
        self._loc = loc
        self.major = major

    def get_loc(self): return self._loc


class _ProjectionAxis:
    """Minimal axis object for custom projection class definitions."""

    def __init__(self, axes=None): self.axes = axes

    def set_minor_locator(self, locator): return None
    def set_major_locator(self, locator): return None
    def set_ticks_position(self, position): return None
    def get_view_interval(self): return (0.0, 1.0)


class _XAxis(_ProjectionAxis): pass
class _YAxis(_ProjectionAxis): pass
class _XTick(_Tick): pass
class _YTick(_Tick): pass


axis = _AxisModule(Axis=_ProjectionAxis, XAxis=_XAxis, YAxis=_YAxis,
                   Tick=_Tick, XTick=_XTick, YTick=_YTick)
_PROJECTIONS = {}


def _register_projection(cls):
    """Register a projection class under its `name`, as Matplotlib does."""
    _PROJECTIONS[str(getattr(cls, "name", cls.__name__)).lower()] = cls
    return None


def _get_projection_class(projection):
    if isinstance(projection, type):
        return projection
    name = str(projection).lower()
    cls = _PROJECTIONS.get(name)
    if cls is None:
        raise ValueError(f"unknown projection: {projection!r}")
    return cls


def _get_projection_names():
    return tuple(sorted(_PROJECTIONS))


def _polar_text(texts, x, y, label, ha, va):
    """Append one data-space label used by the polar grid."""
    texts.append((float(x), float(y), str(label),
                  rcParams.get("xtick.color", "black"), 10.0, ha, va,
                  None, 0.0, _font_family(), (0.0, 0.0)))


class PolarAxes(Axes):
    """Polar axes drawn by projecting theta/r data into Cartesian series.

    The renderer has one Cartesian panel model, so polar support lives here:
    data and grid geometry are projected before they reach `_panel`, while
    labels and frames are ordinary line and text entries.
    """
    name = "polar"

    class PolarTransform:
        def __init__(self, axis=None): self.axis = axis

        def transform(self, values):
            values = np.asarray(values, dtype=float)
            theta, radius = values[..., 0], values[..., 1]
            return np.stack((radius * np.cos(theta),
                             radius * np.sin(theta)), axis=-1)

        def transform_non_affine(self, values): return self.transform(values)

        def transform_path_non_affine(self, path):
            return Path(self.transform(path.vertices), getattr(path, "codes", None))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._polar = True
        self._axis_off = True
        self.aspect = 1.0
        self._polar_theta_offset = 0.0
        self._polar_theta_direction = 1.0
        self._polar_rmax = None
        self._polar_rmin = 0.0
        self._polar_data_max = 0.0
        self._polar_rgrids = []
        self._polar_rgrid_labels = []
        self._polar_thetagrids = []
        self._polar_thetagrid_labels = None
        self._polar_thetamin = None
        self._polar_thetamax = None
        self._polar_rlabel_position = 22.5
        self._polar_frame = "circle"
        self._polar_num_vertices = 0
        patch = self._gen_axes_patch()
        if isinstance(patch, RegularPolygon):
            self._polar_frame = "polygon"
            self._polar_num_vertices = int(getattr(patch, "numvertices", 0))
        self._update_polar_limits()

    def _gen_axes_patch(self): return Circle((0.5, 0.5), 0.5)
    def _gen_axes_spines(self): return {}

    def _polar_rmax_value(self):
        if self._polar_rmax is not None:
            return max(float(self._polar_rmax), 1e-9)
        return self._polar_data_max if self._polar_data_max > 0 else 1.0

    def _polar_limit(self):
        return max(self._polar_rmax_value() * 1.18, 1e-6)

    def _update_polar_limits(self):
        limit = self._polar_limit()
        self.xlim = (-limit, limit)
        self.ylim = (-limit, limit)

    def _limits(self):
        radii = []
        for entry in list(self.lines) + list(self.bands):
            values = np.asarray(entry["y"], dtype=float)
            finite = values[np.isfinite(values)]
            if finite.size:
                radii.append(float(np.max(np.abs(finite))))
        if radii:
            self._polar_data_max = max(self._polar_data_max, max(radii))
        self._update_polar_limits()
        return super()._limits()

    def _polar_xy(self, theta, radius):
        theta = np.asarray(theta, dtype=float)
        radius = np.asarray(radius, dtype=float)
        theta, radius = np.broadcast_arrays(theta, radius)
        finite = radius[np.isfinite(radius)]
        if finite.size:
            self._polar_data_max = max(self._polar_data_max,
                                       float(np.max(np.abs(finite))))
        angle = self._polar_theta_offset + self._polar_theta_direction * theta
        self._update_polar_limits()
        return radius * np.cos(angle), radius * np.sin(angle)

    def plot(self, *args, **kwargs): return super().plot(*args, **kwargs)

    def fill(self, *args, closed=True, **kwargs):
        """Polar fill, closing the polygon at the first theta by default."""
        if closed:
            values, i = [], 0
            args = list(args)
            while i < len(args):
                if isinstance(args[i], str) or i + 1 >= len(args):
                    values.append(args[i])
                    i += 1
                    continue
                x = np.asarray(args[i], dtype=float).ravel()
                y = np.asarray(args[i + 1], dtype=float).ravel()
                if x.size and (x[0] != x[-1] or y[0] != y[-1]):
                    x, y = np.append(x, x[0]), np.append(y, y[0])
                values.extend((x, y))
                i += 2
            args = values
        return super().fill(*args, **kwargs)

    def set_theta_zero_location(self, loc, offset=0.0):
        points = {"N": 90.0, "NNE": 67.5, "NE": 45.0, "ENE": 22.5,
                  "E": 0.0, "ESE": -22.5, "SE": -45.0, "SSE": -67.5,
                  "S": -90.0, "SSW": -112.5, "SW": -135.0, "WSW": -157.5,
                  "W": 180.0, "WNW": 157.5, "NW": 135.0, "NNW": 112.5}
        try:
            degrees = points[str(loc).upper()] if isinstance(loc, str) else float(loc)
        except KeyError:
            raise ValueError(f"unknown theta zero location: {loc!r}") from None
        self._polar_theta_offset = np.deg2rad(degrees + float(offset))

    def set_theta_offset(self, offset): self._polar_theta_offset = float(offset)

    def set_theta_direction(self, direction):
        if isinstance(direction, str):
            direction = -1.0 if direction.lower() == "clockwise" else 1.0
        self._polar_theta_direction = 1.0 if float(direction) >= 0 else -1.0

    def set_rlabel_position(self, value): self._polar_rlabel_position = float(value)
    def set_rorigin(self, value): self._polar_rorigin = float(value)

    def _polar_theta_limits(self):
        if self._polar_thetamin is None or self._polar_thetamax is None:
            return None
        lo, hi = sorted((float(self._polar_thetamin), float(self._polar_thetamax)))
        return None if hi - lo >= 2.0 * np.pi - 1e-12 else (lo, hi)

    def set_thetalim(self, *args, **kwargs):
        left = kwargs.pop("left", kwargs.pop("thetamin", None))
        right = kwargs.pop("right", kwargs.pop("thetamax", None))
        if args:
            if len(args) == 1 and np.ndim(args[0]) == 1:
                left, right = args[0]
            else:
                left = args[0] if left is None else left
                if len(args) > 1 and right is None:
                    right = args[1]
        if left is not None:
            self._polar_thetamin = float(left)
        if right is not None:
            self._polar_thetamax = float(right)
        return self.get_thetalim()

    def set_thetamin(self, value):
        self._polar_thetamin = np.deg2rad(float(value))
        return self.get_thetamin()

    def set_thetamax(self, value):
        self._polar_thetamax = np.deg2rad(float(value))
        return self.get_thetamax()

    def get_thetamin(self):
        return np.rad2deg(self._polar_theta_limits()[0]
                          if self._polar_theta_limits() else 0.0)

    def get_thetamax(self):
        return np.rad2deg(self._polar_theta_limits()[1]
                          if self._polar_theta_limits() else 360.0)

    def get_thetalim(self):
        limits = self._polar_theta_limits()
        return limits if limits is not None else (0.0, 2.0 * np.pi)

    def _polar_arc(self, radius, start=None, stop=None, count=181):
        limits = self._polar_theta_limits()
        if start is None or stop is None:
            start, stop = limits if limits is not None else (0.0, 2.0 * np.pi)
        angles = (self._polar_theta_offset
                  + self._polar_theta_direction * np.linspace(start, stop, count))
        return radius * np.cos(angles), radius * np.sin(angles)

    def _polar_segments(self, theta, radius):
        """Split a theta/r path into the pieces inside the theta limits."""
        theta = np.asarray(theta, dtype=float).ravel()
        radius = np.asarray(radius, dtype=float).ravel()
        if theta.size != radius.size:
            theta, radius = np.broadcast_arrays(theta, radius)
            theta, radius = theta.ravel(), radius.ravel()
        limits = self._polar_theta_limits()
        if limits is None:
            return [(theta, radius)]
        lo, hi = limits
        inside = (theta >= lo - 1e-12) & (theta <= hi + 1e-12)
        segments, current_t, current_r = [], [], []

        def crossing(i, j, boundary):
            span = theta[j] - theta[i]
            if abs(span) < 1e-15:
                return float(boundary), float(radius[j])
            fraction = np.clip((boundary - theta[i]) / span, 0.0, 1.0)
            return float(boundary), float(radius[i] + fraction * (radius[j] - radius[i]))

        for i in range(theta.size):
            if inside[i]:
                if not current_t and i > 0:
                    edge = lo if theta[i] >= lo else hi
                    t, r = crossing(i - 1, i, edge)
                    current_t.append(t)
                    current_r.append(r)
                current_t.append(float(theta[i]))
                current_r.append(float(radius[i]))
            elif current_t:
                edge = lo if theta[i] < lo else hi
                t, r = crossing(i - 1, i, edge)
                current_t.append(t)
                current_r.append(r)
                segments.append((np.asarray(current_t), np.asarray(current_r)))
                current_t, current_r = [], []
        if current_t:
            segments.append((np.asarray(current_t), np.asarray(current_r)))
        return segments

    def bar(self, x, height, width=0.8, bottom=0.0, color=None, edgecolor=None,
            label="", align="center", alpha=None, linewidth=None, yerr=None, **kwargs):
        """Polar bars as filled annular wedges."""
        theta = _as_f64(x)
        n = theta.size
        heights, widths, bases = _fill(height, n), _fill(width, n), _fill(bottom, n)
        if align not in ("center", "edge"):
            raise ValueError(f"unsupported align: {align!r}")
        starts = theta - widths / 2.0 if align == "center" else theta
        ends = starts + widths
        colors = _bar_colors(color if color is not None else self._next_color(patch=True), n)
        edges = _bar_colors(edgecolor, n) if edgecolor is not None else None
        line_widths = None if linewidth is None else _fill(linewidth, n)
        limits = self._polar_theta_limits()
        wedges = []
        for i in range(n):
            start, end = float(starts[i]), float(ends[i])
            if limits is not None:
                start, end = max(start, limits[0]), min(end, limits[1])
            if not (np.isfinite(start) and np.isfinite(end)) or end <= start:
                continue
            r0, r1 = float(bases[i]), float(bases[i]) + float(heights[i])
            if not (np.isfinite(r0) and np.isfinite(r1)):
                continue
            if r1 < r0:
                r0, r1 = r1, r0
            self._polar_data_max = max(self._polar_data_max, abs(r0), abs(r1))
            ox, oy = self._polar_arc(r1, start, end, 65)
            if r0 > 0.0:
                ix, iy = self._polar_arc(r0, start, end, 65)
                points = np.column_stack((np.concatenate((ox, ix[::-1])),
                                          np.concatenate((oy, iy[::-1]))))
            else:
                points = np.column_stack((np.concatenate((ox, [0.0])),
                                          np.concatenate((oy, [0.0]))))
            face = colors[i % len(colors)] if colors else "#1f77b4"
            edge = edges[i % len(edges)] if edges else None
            patch = Polygon(points, closed=True, facecolor=face, edgecolor=edge,
                            linewidth=0.0 if line_widths is None else float(line_widths[i]),
                            alpha=alpha, label=label if not wedges else "")
            self.add_patch(patch)
            wedges.append(patch)
        self._update_polar_limits()
        return _BarContainer(wedges, str(label))

    def set_rlim(self, bottom=None, top=None, **kwargs):
        if top is None and bottom is not None:
            values = np.asarray(bottom, dtype=float).ravel()
            if values.size == 2:
                bottom, top = values
        if bottom is not None:
            self._polar_rmin = float(bottom)
        if top is not None:
            self._polar_rmax = float(top)
        self._update_polar_limits()
        return self.get_rlim()

    def set_rmax(self, value):
        self._polar_rmax = float(value)
        self._update_polar_limits()
        return self.get_rmax()

    def set_rmin(self, value):
        self._polar_rmin = float(value)
        return self.get_rmin()

    def get_rmax(self): return self._polar_rmax_value()
    def get_rmin(self): return self._polar_rmin
    def get_rlim(self): return (self._polar_rmin, self.get_rmax())

    def set_rscale(self, value, base=10, **kwargs):
        self.set_yscale(value, base=base, **kwargs)
    def get_rscale(self): return self.yscale

    def set_rgrids(self, radii, labels=None, angle=None, fmt=None, **kwargs):
        radii = [float(v) for v in np.asarray(radii, dtype=float).ravel()]
        if labels is None and fmt is not None:
            labels = [fmt % r for r in radii]
        self._polar_rgrids = radii
        self._polar_rgrid_labels = [] if labels is None else [str(v) for v in labels]
        if angle is not None:
            self._polar_rlabel_position = float(angle)
        self._yticks = radii
        self._yticklabels = self._polar_rgrid_labels or None

    def set_rticks(self, ticks, labels=None, **kwargs):
        return self.set_rgrids(ticks, labels=labels)

    def set_thetagrids(self, angles, labels=None, fmt=None, **kwargs):
        angles = [float(v) for v in np.asarray(angles, dtype=float).ravel()]
        if labels is None and fmt is not None:
            labels = [fmt % a for a in angles]
        self._polar_thetagrids = angles
        self._polar_thetagrid_labels = (None if labels is None
                                        else [str(v) for v in labels])
        self._xticks = angles
        self._xticklabels = self._polar_thetagrid_labels

    def _polar_grid(self):
        rmax = self._polar_rmax_value()
        limits = self._polar_theta_limits()
        offset, direction = self._polar_theta_offset, self._polar_theta_direction
        edge = rcParams.get("axes.edgecolor", "black")
        grid = rcParams.get("grid.color", "#b0b0b0")
        lines, texts = [], []

        if limits is None and self._polar_frame == "polygon" and self._polar_num_vertices >= 3:
            angles = (offset + direction * np.arange(self._polar_num_vertices + 1)
                      * 2.0 * np.pi / self._polar_num_vertices)
            lines.append(_series(rmax * np.cos(angles), rmax * np.sin(angles),
                                 "", edge, linewidth=0.8))
        else:
            x, y = self._polar_arc(rmax)
            lines.append(_series(x, y, "", edge, linewidth=0.8))
            if limits is not None:
                for boundary in limits:
                    angle = offset + direction * boundary
                    lines.append(_series([0.0, rmax * np.cos(angle)],
                                         [0.0, rmax * np.sin(angle)],
                                         "", edge, linewidth=0.8))

        for radius in self._polar_rgrids:
            if 0.0 < radius <= rmax:
                x, y = self._polar_arc(radius)
                lines.append(_series(x, y, "", grid, linewidth=0.8))

        angles = self._polar_thetagrids or list(np.arange(0.0, 360.0, 45.0))
        for degrees in angles:
            radians = np.deg2rad(float(degrees))
            if limits is not None and not (limits[0] - 1e-12 <= radians <= limits[1] + 1e-12):
                continue
            angle = offset + direction * radians
            lines.append(_series([0.0, rmax * np.cos(angle)],
                                 [0.0, rmax * np.sin(angle)],
                                 "", grid, linewidth=0.8))

        labels = self._polar_thetagrid_labels
        if labels is None:
            labels = [f"{float(a):g}°" for a in angles]
        for degrees, label in zip(angles, labels):
            radians = np.deg2rad(float(degrees))
            if limits is not None and not (limits[0] - 1e-12 <= radians <= limits[1] + 1e-12):
                continue
            angle = offset + direction * radians
            x, y = rmax * 1.06 * np.cos(angle), rmax * 1.06 * np.sin(angle)
            c, s = np.cos(angle), np.sin(angle)
            ha = "center" if abs(c) < 0.35 else ("left" if c > 0 else "right")
            va = "center" if abs(s) < 0.35 else ("bottom" if s > 0 else "top")
            _polar_text(texts, x, y, label, ha, va)

        if self._polar_rgrids:
            radial_labels = self._polar_rgrid_labels or [
                f"{float(r):g}" for r in self._polar_rgrids]
            radians = np.deg2rad(self._polar_rlabel_position)
            if limits is not None and not (limits[0] <= radians <= limits[1]):
                radians = None
            if radians is not None:
                angle = offset + direction * radians
                for radius, label in zip(self._polar_rgrids, radial_labels):
                    if 0.0 < radius <= rmax:
                        _polar_text(texts, radius * np.cos(angle),
                                    radius * np.sin(angle), label, "center", "center")
        return lines, texts


class Axes3D(Axes):
    """Compatibility axes for the Axes3D imports used by gallery tests.

    The renderer is two-dimensional, so collections and limits are accepted
    and drawn on the flat panel instead of raising a projection error.
    """
    name = "3d"

    def __init__(self, *args, **kwargs):
        if args and not isinstance(args[0], (int, np.integer)):
            fig = args[0]
            super().__init__(0)
            self._fig = fig
            if len(args) > 1:
                self.set_position(args[1])
        else:
            super().__init__(*args, **kwargs)
        self._zlim = None
        self.zaxis = _ProjectionAxis(self)

    def add_collection3d(self, collection, zs=None, zdir="z", **kwargs):
        self.add_collection(collection)
        return collection

    def set_xlim3d(self, *args, **kwargs): return self.set_xlim(*args, **kwargs)
    def set_ylim3d(self, *args, **kwargs): return self.set_ylim(*args, **kwargs)
    def set_zlim3d(self, bottom=None, top=None, **kwargs):
        if top is None and bottom is not None:
            values = np.asarray(bottom, dtype=float).ravel()
            if values.size == 2:
                bottom, top = values
        self._zlim = (0.0 if bottom is None else float(bottom),
                      1.0 if top is None else float(top))
        return self._zlim
    def get_zlim3d(self): return self._zlim or (0.0, 1.0)
    set_zlim = set_zlim3d
    get_zlim = get_zlim3d


class SkewXAxes(Axes):
    """Skew projection shim; the common line primitives draw unchanged."""
    name = "skewx"


class GeoAxes(PolarAxes):
    """Geographic projection frame drawn with the polar renderer."""

    name = "geo"
    _geo_height = 0.5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._polar_thetagrids = []
        self._polar_rgrids = []
        self._polar_rmax = 1.0
        self.xlim = (-1.05, 1.05)
        self.ylim = (-0.55, 0.55)

    def _limits(self):
        return self.xlim, self.ylim

    def _polar_grid(self):
        edge = rcParams.get("axes.edgecolor", "black")
        grid = rcParams.get("grid.color", "#b0b0b0")
        lines = []
        angles = np.linspace(0.0, 2.0 * np.pi, 181)
        lines.append(_series(np.cos(angles), self._geo_height * np.sin(angles),
                             "", edge, linewidth=0.8))
        if self.show_grid:
            latitude = np.linspace(-np.pi / 2.0, np.pi / 2.0, 91)
            for longitude in np.linspace(-2.0 * np.pi / 3.0, 2.0 * np.pi / 3.0, 5):
                lines.append(_series(
                    np.sin(longitude) * np.cos(latitude),
                    self._geo_height * np.sin(latitude),
                    "", grid, linewidth=0.5))
            longitude = np.linspace(-np.pi, np.pi, 181)
            for lat in np.deg2rad([-60.0, -30.0, 0.0, 30.0, 60.0]):
                lines.append(_series(
                    np.sin(longitude) * np.cos(lat),
                    np.full(longitude.size, self._geo_height * np.sin(lat)),
                    "", grid, linewidth=0.5))
        return lines, []


class AitoffAxes(GeoAxes): name = "aitoff"
class HammerAxes(GeoAxes): name = "hammer"
class LambertAxes(GeoAxes): name = "lambert"
class MollweideAxes(GeoAxes): name = "mollweide"

for _geo_axes in (AitoffAxes, HammerAxes, LambertAxes, MollweideAxes):
    _register_projection(_geo_axes)


projections = _Namespace(
    register_projection=_register_projection,
    get_projection_class=_get_projection_class,
    get_projection_names=_get_projection_names,
    polar=_Namespace(PolarAxes=PolarAxes, PolarTransform=PolarAxes.PolarTransform),
)
register_projection = projections.register_projection
_register_projection(PolarAxes)
_register_projection(Axes3D)
_register_projection(SkewXAxes)

mticker = _Namespace(
    Locator=_NoopLocator, MultipleLocator=_MultipleLocator, FixedLocator=_FixedLocator,
    LinearLocator=_LinearLocator, LogLocator=_LogLocator, MaxNLocator=_MaxNLocator,
    NullLocator=_NoopLocator, AutoMinorLocator=_NoopLocator, Formatter=_NoopFormatter,
    FuncFormatter=_NoopFormatter, FormatStrFormatter=_NoopFormatter,
    StrMethodFormatter=_NoopFormatter, ScalarFormatter=_NoopFormatter,
    LogFormatter=_NoopFormatter, LogFormatterMathtext=_NoopFormatter,
    NullFormatter=_NoopFormatter,
    FixedFormatter=_FixedFormatter, IndexLocator=_IndexLocator,
    PercentFormatter=_PercentFormatter, EngFormatter=_EngFormatter,
    AutoLocator=_MaxNLocator,
)
ticker = mticker
MultipleLocator = _MultipleLocator
MaxNLocator = _MaxNLocator
FixedLocator = _FixedLocator
LinearLocator = _LinearLocator
LogLocator = _LogLocator
FixedFormatter = _FixedFormatter
PercentFormatter = _PercentFormatter
EngFormatter = _EngFormatter

MO, TU, WE, TH, FR, SA, SU = range(7)
YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, MINUTELY, SECONDLY = range(7)
AutoDateLocator = _AutoDateLocator
AutoDateFormatter = _AutoDateFormatter
DateFormatter = _DateFormatter
YearLocator = _YearLocator
MonthLocator = _MonthLocator
DayLocator = _DayLocator
HourLocator = _HourLocator
MinuteLocator = _MinuteLocator
SecondLocator = _SecondLocator
MicrosecondLocator = _SecondLocator
WeekdayLocator = _DayLocator
RRuleLocator = _RRuleLocator
rrulewrapper = _rrulewrapper
drange = _drange
ConciseDateFormatter = _ConciseDateFormatter
ConciseDateConverter = _ConciseDateConverter

_epoch = {"value": "1970-01-01T00:00:00"}


def _set_epoch(epoch): _epoch["value"] = str(epoch)
def _get_epoch(): return _epoch["value"]

dates = _Namespace(
    date2num=_date_to_num, num2date=_num_to_date, DateFormatter=_DateFormatter,
    AutoDateLocator=_AutoDateLocator, AutoDateFormatter=_AutoDateFormatter,
    YearLocator=_YearLocator, MonthLocator=_MonthLocator, DayLocator=_DayLocator,
    HourLocator=_HourLocator, MinuteLocator=_MinuteLocator,
    SecondLocator=_SecondLocator, WeekdayLocator=_DayLocator,
    MicrosecondLocator=_SecondLocator, RRuleLocator=_RRuleLocator,
    rrulewrapper=_rrulewrapper, drange=_drange,
    ConciseDateFormatter=_ConciseDateFormatter,
    ConciseDateConverter=_ConciseDateConverter,
    MO=MO, TU=TU, WE=WE, TH=TH, FR=FR, SA=SA, SU=SU,
    YEARLY=YEARLY, MONTHLY=MONTHLY, WEEKLY=WEEKLY, DAILY=DAILY,
    HOURLY=HOURLY, MINUTELY=MINUTELY, SECONDLY=SECONDLY,
    _reset_epoch_test_example=lambda: None,
    set_epoch=_set_epoch, get_epoch=_get_epoch,
)
mdates = dates

cbook = _Namespace(get_sample_data=_get_sample_data, flatten=_flatten,
                   boxplot_stats=_boxplot_stats,
                   silent_list=lambda *items: list(items[0]) if items else [],
                   to_rgba=lambda color, alpha=None: _rgba_tuple(color) if alpha is None
                   else (*_rgba_tuple(color)[:3], float(alpha)))
mlab = _Mlab()


def _findfont(prop=None, **kwargs):
    """Return a placeholder bundled-font path.

    The renderer uses its own bundled font bytes, so resolving a real path is
    unnecessary for drawing; callers such as the logo example only inspect the
    returned name.
    """
    return "DejaVuSans.ttf"


findfont = _findfont


class _FontFlag:
    """One named FreeType style or face flag."""

    def __init__(self, name):
        self.name = name

    def __repr__(self): return f"<FontFlag {self.name}>"


class _FontFlagSet:
    """The flags present on a font face, testable with `flag in font.flags`."""

    def __init__(self, names):
        self._names = set(names)

    def __contains__(self, flag):
        return getattr(flag, "name", flag) in self._names

    def __iter__(self): return iter(self._names)


class _FontFlagsMeta(type):
    def __iter__(cls): return iter(cls._members())
    def __len__(cls): return len(cls._members())


class StyleFlags(metaclass=_FontFlagsMeta):
    """`ft2font.StyleFlags`: the font's style bits."""

    ITALIC = _FontFlag("ITALIC")
    BOLD = _FontFlag("BOLD")

    @classmethod
    def _members(cls): return (cls.ITALIC, cls.BOLD)


class FaceFlags(metaclass=_FontFlagsMeta):
    """`ft2font.FaceFlags`: the capabilities of a font face."""

    SCALABLE = _FontFlag("SCALABLE")
    FIXED_SIZES = _FontFlag("FIXED_SIZES")
    FIXED_WIDTH = _FontFlag("FIXED_WIDTH")
    SFNT = _FontFlag("SFNT")
    HORIZONTAL = _FontFlag("HORIZONTAL")
    VERTICAL = _FontFlag("VERTICAL")
    KERNING = _FontFlag("KERNING")
    FAST_GLYPHS = _FontFlag("FAST_GLYPHS")
    MULTIPLE_MASTERS = _FontFlag("MULTIPLE_MASTERS")
    GLYPH_NAMES = _FontFlag("GLYPH_NAMES")
    EXTERNAL_STREAM = _FontFlag("EXTERNAL_STREAM")
    HINTER = _FontFlag("HINTER")

    @classmethod
    def _members(cls):
        return tuple(getattr(cls, name) for name in (
            "SCALABLE", "FIXED_SIZES", "FIXED_WIDTH", "SFNT", "HORIZONTAL",
            "VERTICAL", "KERNING", "FAST_GLYPHS", "MULTIPLE_MASTERS",
            "GLYPH_NAMES", "EXTERNAL_STREAM", "HINTER"))


class Kerning:
    """Kerning modes accepted by `FT2Font.get_kerning`."""

    DEFAULT = 0
    UNFITTED = 1
    UNSCALED = 2


class _FT2Glyph:
    """Glyph metrics returned by the font-inspection shim."""

    def __init__(self, glyph_index):
        self.glyph_index = int(glyph_index)
        self.bbox = (0, 0, 600, 700)
        self.width = self.horiAdvance = 600
        self.height = self.horiBearingY = 700
        self.horiBearingX = 0


class FT2Font:
    """Small font-inspection stand-in backed by the bundled DejaVu metrics."""

    def __init__(self, filename):
        self.fname = str(filename)
        name = self.fname.lower()
        self.num_faces = 1
        self.num_named_instances = 0
        self.num_glyphs = 0x2400
        self.num_fixed_sizes = 0
        self.family_name = "DejaVu Sans"
        self.style_name = ("Bold" if "bold" in name else
                           "Oblique" if "oblique" in name or "italic" in name
                           else "Book")
        self.postscript_name = "DejaVuSans"
        self.scalable = True
        self.bbox = (-1021, -463, 1793, 1233)
        self.units_per_EM = 2048
        self.ascender = 1901
        self.descender = -483
        self.height = 2384
        self.max_advance_width = 3838
        self.max_advance_height = 2384
        self.underline_position = -175
        self.underline_thickness = 90
        styles = []
        if "oblique" in name or "italic" in name:
            styles.append("ITALIC")
        if "bold" in name:
            styles.append("BOLD")
        self.style_flags = _FontFlagSet(styles)
        self.face_flags = _FontFlagSet((
            "SCALABLE", "SFNT", "HORIZONTAL", "KERNING", "GLYPH_NAMES"))
        self._charmap = 0
        self._size = (12.0, 72.0)

    def set_charmap(self, charmap):
        """Select a character map; the bundled font only has one."""
        self._charmap = int(charmap)

    def set_size(self, size, dpi=72):
        self._size = (float(size), float(dpi))

    def get_charmap(self):
        return {code: code for code in range(0x20, 0x100)}

    def get_name_index(self, name):
        """Index of a named font table entry; the stand-in has none."""
        return 0

    def get_glyph_name(self, glyph_index):
        index = int(glyph_index)
        if 0x20 <= index <= 0x7E:
            return chr(index)
        return f"uni{index:04X}"

    def load_char(self, charcode):
        return _FT2Glyph(charcode)

    def get_kerning(self, left, right, mode=Kerning.DEFAULT):
        """The bundled metrics shim has no kerning table."""
        return 0


font_manager = _Namespace(FontProperties=FontProperties, findfont=_findfont,
                          fontManager=_Namespace(addfont=lambda path: None))
ft2font = _Namespace(FT2Font=FT2Font, Kerning=Kerning,
                     StyleFlags=StyleFlags, FaceFlags=FaceFlags)
gridspec = _Namespace(GridSpec=GridSpec, SubplotSpec=SubplotSpec,
                      GridSpecFromSubplotSpec=GridSpecFromSubplotSpec)
lines = _Namespace(Line2D=Line2D)
patheffects = _PathEffects()
path_effects = patheffects
class _ColorSequences(dict):
    """`matplotlib.color_sequences`: named colour lists, looked up by name."""

    def __missing__(self, key):
        raise KeyError(key)


def _colormap_sequence(name):
    cmap = get_cmap(name)
    rows = np.asarray(cmap.colors)[::-1] if cmap.name.endswith("_r") else np.asarray(cmap.colors)
    return [f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"
            for r, g, b in rows]


_PETROFF = ["#3f90da", "#ffa90e", "#bd1f01", "#94a4a2", "#832db6",
            "#a96b59", "#e76300", "#b9ac70", "#717581", "#92dadd"]
color_sequences = _ColorSequences(
    tableau=list(_CYCLE), petroff=_PETROFF[:6], petroff6=_PETROFF[:6],
    petroff8=_PETROFF[:8], petroff10=list(_PETROFF))
for _sequence in ("tab10", "tab20", "tab20b", "tab20c", "Pastel1", "Pastel2",
                  "Paired", "Accent", "Dark2", "Set1", "Set2", "Set3", "okabe_ito"):
    try:
        color_sequences[_sequence] = _colormap_sequence(_sequence)
    except ValueError:
        pass


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
    # Matplotlib's test-suite style; it is the current default look.
    "mpl20": {},
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
for _petroff_style in ("petroff6", "petroff8", "petroff10"):
    _STYLE_PRESETS[_petroff_style] = {
        "axes.prop_cycle": list(color_sequences[_petroff_style])}


def _style_rc(style):
    """Merge a preset name, a list of names or a dict into one rc mapping."""
    if isinstance(style, dict):
        merged = dict(style)
        if isinstance(merged.get("axes.prop_cycle"), list):
            merged["axes.prop_cycle"] = _CycleList(merged["axes.prop_cycle"])
        return merged
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
    return _style_rc(_STYLE_PRESETS[name])


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


def savefig(fname=None, format=None, dpi=None, bbox_inches=None, transparent=None,
            facecolor=None, edgecolor=None, compression=None, pad_inches=None,
            metadata=None, pil_kwargs=None, **kwargs):
    return gcf().savefig(fname, format=format, dpi=dpi, bbox_inches=bbox_inches,
                         transparent=transparent, facecolor=facecolor, edgecolor=edgecolor,
                         compression=compression, pad_inches=pad_inches,
                         metadata=metadata, pil_kwargs=pil_kwargs, **kwargs)
