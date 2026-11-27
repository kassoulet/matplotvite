"""Plotting helpers shared by the axes mixins."""
import datetime as _datetime
import hashlib as _hashlib
import math as _math
from typing import TYPE_CHECKING, ClassVar

import numpy as np

from . import tri, units
from ._artists import _MARKERS
from ._helpers import (
    _CYCLE,
    _FMT_COLORS,
    Path,
    _as_list,
    _date_to_num,
    _datetime_to_num,
    _is_rgb,
    _looks_like_dates,
    _noop_method,
    _norm_color,
    _Transform,
    get_cmap,
)


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

    def pick(name):  # type: ignore[no-redef]
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
    groups: list[tuple[object, ...]] = []
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
    get_snap_threshold = _noop_method("get_snap_threshold", 'self')
    def is_filled(self):
        return self._fillstyle == "full" and str(self._marker) in self.filled_markers
    def get_path(self): return Path.unit_circle()
    get_alt_path = _noop_method("get_alt_path", 'self')
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


def _check_same_length(a, b, message="x and y must have the same length"):
    """Raise the axis-length error shared by the plotting helpers."""
    if a.size != b.size:
        raise ValueError(message)


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
    x_arr = _as_f64(x)
    y_arr = _as_f64(y)
    _check_same_length(x_arr, y_arr)
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
        return [_as_f64(x)]
    if isinstance(x, (list, tuple)):
        if len(x) == 0:
            return []
        if np.asarray(x[0]).ndim == 0:
            return [_as_f64(x)]
        return [_as_f64(v) for v in x]
    return [_as_f64(x)]


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
        vals = _as_f64(raw)
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
    vals = _as_f64(values)
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
    arr = _as_f64(values)
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
        v = _as_f64(a)
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
        if x.shape == (rows + 1, cols + 1) or x.shape == z.shape:
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
    a = (np.asarray([_as_f64(row) for row in err]) if raw.ndim == 2
         else _as_f64(err))
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
        values = _as_f64(locator.tick_values(lo, hi))
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
    values = _as_f64(z)
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
    rgb = _as_f64(get_cmap(entry.get("cmap"))(t))[:3]
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


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._images import ContourSet
    from ._ticker import _LogLocator
