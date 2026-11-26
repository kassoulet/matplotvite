"""Colormaps, scalar mappables and light sources."""
from typing import Any, ClassVar

import numpy as np

from ._colors import CSS_COLORS as _CSS_COLORS
from ._config import _Namespace
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
from ._helpers import _TAB10, _cmap_name, _norm_color, get_cmap
from ._plot_helpers import _as_f64
from ._pyplot import gca


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
    boundaries = _as_f64(levels)
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
    # Attached at module scope once these helpers are defined below.
    ScalarMappable: Any
    LightSource: Any
    rgb_to_hsv: Any
    hsv_to_rgb: Any
    from_levels_and_colors: Any

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
            return lookup[blend_mode](rgb, intensity, **kwargs)  # type: ignore[operator]
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
