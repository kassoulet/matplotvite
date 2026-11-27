"""Shared helpers: colours, mathtext, validation, rc defaults."""
import copy
import datetime as _datetime
import hashlib as _hashlib
import math as _math
import os
import re as _re
import warnings
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, ClassVar, Optional

import numpy as np

from ._colors import CSS_COLORS as _CSS_COLORS
from ._core import (
    Colormap,
)
from ._core import (
    Normalize as _Normalize,
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
    margin_pad as _margin_pad_core,
)
from ._core import (
    register_colormap as _register_colormap,
)

_CMAP_DATA = {k: np.frombuffer(v, np.uint8).reshape(-1, 3) for k, v in _colormaps().items()}

# `matplotlib.pyplot.Normalize` is Matplotlib's norm class, re-exported here.
Normalize = _Normalize


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


def _ignored(name: str) -> None:
    _IGNORED_CALLS.append(name)
    if name not in _IGNORED_WARNED:
        _IGNORED_WARNED.add(name)
        warnings.warn(f"{name} is accepted but ignored by matplotvite",
                      RuntimeWarning, stacklevel=3)


def _noop_method(name: str, signature: str, *, warn: Optional[str] = None,
                 returns_self: bool = False) -> Any:
    """Build a compatibility method whose body only returns `None` or `self`.

    `warn` names the call recorded by :func:`_ignored`; the plain `return None`
    shims leave it out and stay silent. The function keeps the declared
    signature, and the marker lets `tools/trace_unsupported.py` classify it as
    accepted-and-ignored from the same declaration.
    """
    body = "return self" if returns_self else "return None"
    record = f"    _ignored({warn!r})\n" if warn is not None else ""
    scope: dict[str, Any] = {"__name__": __name__, "_ignored": _ignored}
    source = f"def {name}({signature}):\n{record}    {body}\n"
    # `signature` is a class declaration, not external input.
    exec(source, scope)  # noqa: S102  # nosec B102
    function = scope[name]
    function._matplotvite_noop = True
    return function


def _state_setter(attribute: str, signature: str, argument: str) -> Any:
    """Build a `set_x(self, value)` method that only stores its argument."""
    scope: dict[str, Any] = {"__name__": __name__}
    source = f"def _set(self, {signature}):\n    self.{attribute} = {argument}\n"
    # `signature` is a class declaration, not external input.
    exec(source, scope)  # noqa: S102  # nosec B102
    return scope["_set"]


# Artist, legend and figure properties Matplotlib accepts but the renderer does
# not model. They stay accepted, but are recorded as ignored instead of being
# treated as silently supported. Unknown names raise TypeError, as in Matplotlib.
_ARTIST_KWARGS = frozenset(
    ["agg_filter", "alpha", "animated", "clip_box", "clip_on", "clip_path", "figure", "gid", "in_layout", "label", "mouseover", "path_effects", "picker", "rasterized", "sketch_params", "snap", "transform", "url", "visible", "zorder"]
)
_LINE2D_KWARGS = _ARTIST_KWARGS | frozenset(
    ["antialiased", "color", "dash_capstyle", "dash_joinstyle", "dashes", "data", "drawstyle", "ds", "fillstyle", "gapcolor", "linestyle", "linewidth", "ls", "lw", "marker", "markeredgecolor", "markeredgewidth", "markerfacecolor", "markerfacecoloralt", "markersize", "markevery", "mec", "mfc", "mew", "ms", "pickradius", "solid_capstyle", "solid_joinstyle", "xdata", "ydata"]
)
_COLLECTION_KWARGS = _ARTIST_KWARGS | frozenset(
    ["antialiased", "array", "capstyle", "clim", "cmap", "color", "edgecolor", "edgecolors", "ec", "facecolor", "facecolors", "fc", "hatch", "hatch_linewidth", "hatchcolor", "joinstyle", "linestyle", "linewidth", "linewidths", "ls", "norm", "offset_transform", "offsets", "paths", "pickradius", "urls"]
)
_PATCH_KWARGS = _ARTIST_KWARGS | frozenset(
    ["antialiased", "capstyle", "color", "ec", "edgecolor", "edgegapcolor", "facecolor", "fc", "fill", "hatch", "hatch_linewidth", "hatchcolor", "joinstyle", "linestyle", "linewidth", "ls", "lw"]
)
_IMAGE_KWARGS = _ARTIST_KWARGS | frozenset(
    ["array", "clim", "cmap", "data", "extent", "filternorm", "filterrad", "interpolation", "interpolation_stage", "norm", "resample"]
)
_LEGEND_KWARGS = _ARTIST_KWARGS | frozenset(
    ["alignment", "bbox_to_anchor", "borderaxespad", "borderpad", "columnspacing", "draggable", "facecolor", "fancybox", "frame_on", "framealpha", "frameon", "handleheight", "handlelength", "handletextpad", "handler_map", "labelcolor", "labelspacing", "markerfirst", "markerscale", "mode", "ncol", "ncols", "numpoints", "reverse", "shadow", "title", "title_fontproperties"]
)
_FIGURE_KWARGS = _ARTIST_KWARGS | frozenset(
    ["canvas", "clear", "constrained_layout", "constrained_layout_pads", "dpi", "edgecolor", "facecolor", "figheight", "figsize", "figwidth", "frameon", "layout", "layout_engine", "linewidth", "num", "size_inches", "tight_layout"]
)
_BAR_KWARGS = _PATCH_KWARGS | frozenset(
    ["capsize", "data", "error_kw", "log", "tick_label", "xerr"]
)
_HIST_KWARGS = _BAR_KWARGS | frozenset(["ec", "fc", "fill", "log"])
_SCATTER_KWARGS = _COLLECTION_KWARGS | frozenset(
    ["clim", "color", "colorizer", "plotnonfinite"]
)


def _check_kwargs(kwargs: dict[str, Any], name: str, allowed: Any) -> None:
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


def _with_alpha(value: Optional[str], alpha: Any) -> Optional[str]:
    """Apply an alpha value to a normalised colour string."""
    if value is None or value == "none":
        return value
    alpha = min(max(float(alpha), 0.0), 1.0)
    body = value[1:7]
    return f"#{body}{round(alpha * 255):02x}"


def _norm_color(c: Any) -> Optional[str]:
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
        vals = [float(v) for v in _as_f64(c)]
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
    ["alpha", "antialiased", "antialiasing", "backgroundcolor", "bbox", "clip_box", "clip_on", "clip_path", "family", "figure", "font", "fontfamily", "fontname", "fontfeatures", "fontproperties", "font_properties", "fontstretch", "fontstyle", "fontvariant", "variant", "fontweight", "gid", "in_layout", "language", "linespacing", "ma", "math_fontfamily", "multialignment", "parse_math", "path_effects", "picker", "rasterized", "rotation_mode", "sketch_params", "snap", "style", "transform_rotates_text", "url", "usetex", "verticalalignment", "visible", "weight", "wrap", "zorder"]
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


def _text_props(fontdict: Any, kwargs: dict[str, Any]
                ) -> tuple[Any, Any, Any, Any, Any, Any, Any, str]:
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


def _mathtext(text: Any, family: Any = None) -> str:
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


# Names registered only so the renderer can read a Python-built table. Using a
# `_ListedColormap` in a plot must not add it to the public registry, and two
# colormaps from different levels must not share one table.
_AUTO_CMAP_KEYS: set[str] = set()


def _register_custom_cmap(cmap, name=None, anonymous=False):
    """Add a `Colormap` built in Python to the table the renderer reads."""
    base = str(name or getattr(cmap, "name", "custom"))
    rgb = np.asarray(cmap._rgb, dtype=np.float64)
    if rgb.ndim != 2 or rgb.shape[1] != 3 or not len(rgb):
        raise ValueError(f"unsupported colormap: {cmap!r}")
    positions = np.linspace(0.0, 1.0, rgb.shape[0])
    samples = np.linspace(0.0, 1.0, 256)
    table = np.stack([np.interp(samples, positions, rgb[:, channel])
                      for channel in range(3)], axis=1)
    pixels = np.clip(table * 255.0, 0, 255).astype(np.uint8)
    if anonymous:
        # The key carries a fingerprint of the table, so different levels keep
        # their own colours and the registry listing stays unchanged.
        key = f"{base}#{_hashlib.sha1(pixels.tobytes(), usedforsecurity=False).hexdigest()[:12]}"
        _AUTO_CMAP_KEYS.add(key)
    else:
        key = base
    _CMAP_DATA[key] = pixels
    _register_colormap(key, pixels.tobytes())
    return key


def _cmap_name(cmap: Any) -> str:
    """Canonical registry name; `None` picks up the `image.cmap` rcParam."""
    if isinstance(cmap, Colormap):
        return str(cmap.name)
    if isinstance(cmap, _ListedColormap):
        name = str(getattr(cmap, "name", "custom"))
        if name in _CMAP_DATA and name not in _AUTO_CMAP_KEYS:
            return name
        return str(_register_custom_cmap(cmap, anonymous=True))
    if cmap is None:
        cmap = rcParams.get("image.cmap", "viridis")
    return str(_core_cmap_name(str(cmap)))


def get_cmap(name: Any = None, lut: Any = None) -> Colormap:
    """Return a `Colormap` by registry name (or the `image.cmap` default)."""
    cmap = name.copy() if isinstance(name, Colormap) else Colormap(
        name if name is not None else rcParams.get("image.cmap", "viridis"))  # type: ignore[arg-type]
    return cmap.resampled(lut) if lut is not None else cmap


def _colormap_names():
    names = [name for name in _CMAP_DATA if name not in _AUTO_CMAP_KEYS]
    return sorted([*names, *(f"{name}_r" for name in names)])


class _ColormapRegistry:
    """Matplotlib's colormap registry: iterable, callable and name-indexable."""

    def __call__(self): return _colormap_names()
    def __getitem__(self, name): return get_cmap(name)
    def __iter__(self): return iter(_colormap_names())
    def __len__(self): return len(_colormap_names())
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
        _AUTO_CMAP_KEYS.difference_update([cmap_name])
        _register_custom_cmap(cmap, name=cmap_name)
        return cmap


colormaps = _ColormapRegistry()


class _CmapNamespace:
    """The `plt.cm` namespace, exposing one attribute per colormap."""

    # Attached at module scope once `ScalarMappable` is defined.
    ScalarMappable: Any

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
        groups = {}  # type: ignore[var-annotated]
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


class _CycleList(list[dict[str, object]]):
    """`axes.prop_cycle`: iterating yields `{"color": ...}` entries, as Cycler."""

    def __init__(self, colors: Iterable[object]) -> None:
        super().__init__({"color": c} for c in colors)

    def by_key(self) -> dict[str, list[object]]:
        return {"color": [entry["color"] for entry in self]}

    def __call__(self) -> Iterator[dict[str, object]]: return iter(self)


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

    def __init__(self, kind: Any) -> None:
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
    rotate_around = _noop_method(
        "rotate_around", 'self, x, y, theta', warn='Affine2D.rotate_around', returns_self=True)
    def inverted(self): return self
    def __add__(self, other): return self
    def __radd__(self, other): return self
    translate = _noop_method(
        "translate", 'self, *args, **kwargs', warn='Affine2D.translate', returns_self=True)
    rotate_deg = _noop_method(
        "rotate_deg", 'self, *args, **kwargs', warn='Affine2D.rotate_deg', returns_self=True)
    scale = _noop_method(
        "scale", 'self, *args, **kwargs', warn='Affine2D.scale', returns_self=True)
    skew_deg = _noop_method(
        "skew_deg", 'self, *args, **kwargs', warn='Affine2D.skew_deg', returns_self=True)
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

    def __init__(self, vertices: Any, codes: Any = None, **kwargs: Any) -> None:
        self.vertices = np.asarray(vertices, dtype=float).reshape(-1, 2)
        self.codes = codes

    def get_vertices(self): return self.vertices
    def get_codes(self): return self.codes
    transformed = _noop_method(
        "transformed", 'self, transform', warn='Path.transformed', returns_self=True)
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
    transformed = _noop_method(
        "transformed", 'self, transform', warn='Bbox.transformed', returns_self=True)
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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

    set_path_effects = _noop_method(
        "set_path_effects", 'self, effects', warn='Patch.set_path_effects', returns_self=True)


class _TextEntry(tuple[object, ...]):
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

    def __init__(self, text: Any = "") -> None:
        self._bbox_patch = _BboxPatch()
        self._text = str(text)

    def get_text(self): return self._text
    def set_text(self, text): self._text = str(text); return self

    set_path_effects = _noop_method(
        "set_path_effects", 'self, effects', warn='Text.set_path_effects', returns_self=True)

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
    draggable = _noop_method("draggable", 'self, *args, **kwargs')
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
    auto_set_font_size = _noop_method("auto_set_font_size", 'self, *args, **kwargs')
    auto_set_column_width = _noop_method("auto_set_column_width", 'self, *args, **kwargs')
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
    draw = _noop_method("draw", 'self, renderer')


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
    set_color = _state_setter(
        "_color", 'color', 'color')
    set_ha = _noop_method(
        "set_ha", 'self, value', warn='Text.set_ha')
    set_horizontalalignment = set_ha
    set_va = _noop_method(
        "set_va", 'self, value', warn='Text.set_va')
    set_verticalalignment = set_va
    set_axis_direction = _noop_method(
        "set_axis_direction", 'self, value', warn='Text.set_axis_direction')
    def set_pad(self, value): self._pad = float(value)
    def get_pad(self): return getattr(self, "_pad", 4.0)
    def set_tick_out(self, value): self._tick_out = bool(value)
    def set_tick_direction(self, value): self._tick_direction = str(value)
    set_axisline_style = _state_setter(
        "_line_style", 'value, **kwargs', 'value')
    def set_picker(self, value): self._picker = value; return self
    set_fontweight = _noop_method(
        "set_fontweight", 'self, value', warn='Text.set_fontweight')
    set_fontstyle = _noop_method(
        "set_fontstyle", 'self, value', warn='Text.set_fontstyle')
    set_fontfamily = _noop_method(
        "set_fontfamily", 'self, value', warn='Text.set_fontfamily')
    set_fontname = _noop_method(
        "set_fontname", 'self, value', warn='Text.set_fontname')
    set_fontproperties = _noop_method(
        "set_fontproperties", 'self, value', warn='Text.set_fontproperties')
    set_multialignment = _noop_method(
        "set_multialignment", 'self, value', warn='Text.set_multialignment')
    set_linespacing = _noop_method(
        "set_linespacing", 'self, value', warn='Text.set_linespacing')
    set_wrap = _noop_method(
        "set_wrap", 'self, value', warn='Text.set_wrap')
    def get_window_extent(self, renderer=None): return _Bbox(0, 0, 1, 1)


def _margin(lo, hi, scale, sticky=(), fraction=0.05):
    """Matplotlib's autoscale margin (in log space for log axes).

    `fraction` is the axes' stored margin (`Axes.margins`), 5% by default.
    `sticky` edges (images, hexbin) swallow the margin on their side, like
    Matplotlib's `sticky_edges`.
    """
    f = np.log10 if scale == "log" else float
    lo, hi = f(lo), f(hi)
    sticky = [f(e) for e in sticky if e > 0 or scale != "log"]
    pad = _margin_pad_core(lo, hi, float(fraction))
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
        arr = _as_f64(values)
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


def _datetime_to_num(value: Any) -> float:
    """Matplotlib date number: proleptic Gregorian ordinal plus day fraction."""
    if isinstance(value, np.datetime64):
        if np.isnat(value):
            return float(np.nan)
        delta = value - np.datetime64("1970-01-01T00:00:00")
        return 719163.0 + float(delta / np.timedelta64(1, "D"))
    if isinstance(value, _datetime.datetime):
        if value.tzinfo is not None:
            value = value.astimezone(_datetime.timezone.utc).replace(tzinfo=None)
        seconds = (value.hour * 3600.0 + value.minute * 60.0 + value.second
                   + value.microsecond / 1e6)
        return float(value.toordinal() + seconds / 86400.0)
    return float(value.toordinal())


def _date_to_num(values: Any) -> Any:
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


def _date_from_num(value: Any) -> _datetime.datetime:
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


def _add_months(value: _datetime.datetime, months: Any) -> _datetime.datetime:
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


def _date_ticks(lo: float, hi: float) -> tuple[list[float], list[str]]:
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
        ticks: list[float] = []
        labels: list[str] = []
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


def _normalize_legend_loc(loc: Any) -> Optional[str]:
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


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._cm import _ListedColormap
    from ._config import rcParams
    from ._containers import _font_family, _font_size
    from ._misc import mcolors
    from ._plot_helpers import _as_f64
