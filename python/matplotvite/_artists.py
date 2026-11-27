"""Patches, collections, lines and the artist base classes."""
import math as _math
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

from ._containers import (
    _call,
    _color_list,
    _number,
    _numbers,
    _single_color,
    _StickyEdges,
)
from ._helpers import (
    _CYCLE,
    Path,
    _Bbox,
    _cmap_name,
    _ignored,
    _noop_method,
    _norm_color,
    _state_setter,
    _TextLabel,
    _Transform,
    get_cmap,
)


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
            x, y = self._x, self._y  # type: ignore[attr-defined]
            w, h = self._width, self._height  # type: ignore[attr-defined]
            return Path([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)])
        return Path(np.empty((0, 2)))
    def add_callback(self, func, *args, **kwargs): return 1
    remove_callback = _noop_method("remove_callback", 'self, func')
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

    set_transform = _state_setter(
        "_transform", 'transform', 'transform')
    set_clip_on = _noop_method(
        "set_clip_on", 'self, clip', warn='Patch.set_clip_on')
    set_clip_path = _noop_method(
        "set_clip_path", 'self, path, transform=None', warn='Patch.set_clip_path')
    set_clip_box = _noop_method(
        "set_clip_box", 'self, box', warn='Patch.set_clip_box')
    set_path_effects = _noop_method(
        "set_path_effects", 'self, effects', warn='Patch.set_path_effects')
    def set_animated(self, value): self._animated = bool(value); return self
    def get_animated(self): return getattr(self, "_animated", False)
    def set_picker(self, value): self._picker = value; return self
    set_antialiased = _noop_method("set_antialiased", 'self, value')
    set_antialiaseds = _noop_method("set_antialiaseds", 'self, value')
    set_joinstyle = _noop_method("set_joinstyle", 'self, value')
    set_capstyle = _noop_method("set_capstyle", 'self, value')
    set_rasterized = _noop_method("set_rasterized", 'self, value')
    set_agg_filter = _noop_method("set_agg_filter", 'self, value')
    set_url = _noop_method("set_url", 'self, value')
    set_sketch_params = _noop_method("set_sketch_params", 'self, *args, **kwargs')
    set_snap = _noop_method("set_snap", 'self, value')
    set_in_layout = _noop_method("set_in_layout", 'self, value')
    def remove(self): self._visible = False
    def get_window_extent(self, renderer=None): return _Bbox(0, 0, 1, 1)
    def contains(self, mouseevent=None): return False, {}
    draw = _noop_method("draw", 'self, renderer=None')

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
    def __init__(self, x: Any, y: Any, dx: Any, dy: Any, width: float = 0.001,
                 length_includes_head: bool = False, head_width: Any = None,
                 head_length: Any = None, **kwargs: Any) -> None:
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
        if str(self.arrowstyle) == "-":
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
    set_path = _state_setter(
        "_path", 'path', 'path')

    def get_xy(self):
        vertices = getattr(self._path, "vertices", None)
        return np.empty((0, 2)) if vertices is None else np.asarray(vertices, dtype=float)


class Annulus(Patch):
    def __init__(self, xy, r, width, angle=0.0, **kwargs):
        super().__init__(**kwargs)
        self._center = (float(xy[0]), float(xy[1]))
        self._r = max(float(v) for v in _as_f64(r))
        self._semiminor = None
        self._width = max(float(v) for v in _as_f64(width))
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
        self._values = _as_f64(values)
        self._edges = _as_f64(edges)
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
    """The `plt.patches` namespace; members are attached as they are defined."""

    # Set below through the `_patch_name` loop and the style assignments.
    ArrowStyle: "_FlexibleStyleNamespace"
    BoxStyle: "_FlexibleStyleNamespace"
    ConnectionStyle: "_FlexibleStyleNamespace"
    Arrow: type
    ConnectionPatch: type


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
        vals = _as_f64(values)
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
    set_capstyle = _noop_method(
        "set_capstyle", 'self, value', warn='Collection.set_capstyle', returns_self=True)
    set_joinstyle = _noop_method(
        "set_joinstyle", 'self, value', warn='Collection.set_joinstyle', returns_self=True)
    set_path_effects = _noop_method(
        "set_path_effects", 'self, effects', warn='Collection.set_path_effects')
    set_clip_on = _noop_method(
        "set_clip_on", 'self, value', warn='Collection.set_clip_on')
    set_clip_path = _noop_method(
        "set_clip_path", 'self, *args, **kwargs', warn='Collection.set_clip_path')
    def set_offset_transform(self, value): return self
    def set_transform(self, value): return self


class LineCollection(Collection):
    def __init__(self, segments, colors=None, linewidths=None, label="", **kwargs):
        if colors is None and kwargs.get("array") is not None:
            values = _as_f64(kwargs["array"])
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
    get_offsets = _noop_method("get_offsets", 'self')


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
            points = base * radius + _as_f64(offset)[:2]
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

    get_offsets = _noop_method("get_offsets", 'self')


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
        self._positions = _as_f64(positions).copy()
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
        self._positions = _as_f64(positions).copy()
        return self._refresh()
    def append_positions(self, positions):
        self._positions = np.append(self._positions, _as_f64(positions))
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


# Marker characters the renderer understands; keep in sync with
# `marker_shape` in src/draw.rs and `_STEM_MARKERS` below.
_MARKERS = set("os^v<>Dx+.*hHpPXd8|_1234")


class Line2D:
    """Handle for a plotted series, mirroring Matplotlib's `Line2D` setters.

    It mutates the series the axes will draw, so `line, = plot(...)` followed by
    `line.set_color(...)` behaves like Matplotlib.
    """

    # Mirrors Matplotlib's `Line2D.markers`; the source list is `_MARKERS`.
    markers: ClassVar[dict[str, str]] = {
        **{marker: "marker" for marker in sorted(_MARKERS)},
        "None": "nothing", "none": "nothing", " ": "nothing", "": "nothing"}
    filled_markers: ClassVar[tuple[str, ...]] = tuple("osD^v<>pP*hHX")
    fillStyles: ClassVar[tuple[str, ...]] = (
        "full", "left", "right", "bottom", "top", "none")

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
            _as_f64(self._series["x"]),
            _as_f64(self._series["y"])]))
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
    draw = _noop_method("draw", 'self, renderer')
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
    set_path_effects = _noop_method(
        "set_path_effects", 'self, effects', warn='Line2D.set_path_effects', returns_self=True)
    def set_zorder(self, zorder): self._series["zorder"] = int(zorder)
    def get_zorder(self): return self._series.get("zorder", 2)
    set_visible = _noop_method(
        "set_visible", 'self, visible', warn='Line2D.set_visible')


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
    draw = _noop_method("draw", 'self, renderer=None')


class _Spine:
    """Compatibility stand-in for one axes spine."""

    def __init__(self):
        self._visible = True
        self._color = None
        self._linewidth = 1.0
        self._position = ""

    def set_visible(self, visible): self._visible = bool(visible)
    def get_visible(self): return self._visible
    set_color = _state_setter(
        "_color", 'color', 'color')
    def get_color(self): return self._color
    def get_edgecolor(self): return self._color
    def set_linewidth(self, width): self._linewidth = float(width)
    def get_linewidth(self): return self._linewidth
    set_position = _state_setter(
        "_position", 'position', 'position')
    def get_position(self): return self._position
    set_bounds = _noop_method("set_bounds", 'self, *args')
    set_smart_bounds = _noop_method("set_smart_bounds", 'self, *args')
    set_zorder = _noop_method("set_zorder", 'self, zorder')
    set_path_effects = _noop_method("set_path_effects", 'self, effects')


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
    register_axis = _noop_method("register_axis", 'self, axis')
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

    set_label_coords = _noop_method("set_label_coords", 'self, x, y, transform=None')
    set_label_position = _noop_method("set_label_position", 'self, position')
    set_ticks_position = _noop_method("set_ticks_position", 'self, position')
    tick_top = _noop_method("tick_top", 'self')
    tick_bottom = _noop_method("tick_bottom", 'self')
    tick_left = _noop_method("tick_left", 'self')
    tick_right = _noop_method("tick_right", 'self')
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
    set_major_formatter = _state_setter(
        "_formatter", 'formatter', 'formatter')
    set_minor_formatter = _noop_method("set_minor_formatter", 'self, formatter')
    def get_major_locator(self): return self._locator or _LocatorHandle()
    def get_major_formatter(self): return self._formatter
    set_units = _noop_method("set_units", 'self, units')
    get_units = _noop_method("get_units", 'self')
    update_units = _noop_method("update_units", 'self, data')
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
    set_params = _noop_method("set_params", 'self, *args, **kwargs')
    set_nbins = _noop_method("set_nbins", 'self, *args, **kwargs')
    def numticks(self, *args, **kwargs): return 8


class _Callbacks:
    def __init__(self): self.callbacks = []
    def connect(self, *args, **kwargs): return 1
    disconnect = _noop_method("disconnect", 'self, *args, **kwargs')
    def add_callback(self, func, *args, **kwargs):
        self.callbacks.append((func, args, kwargs))
        return len(self.callbacks)
    def remove_callback(self, func):
        self.callbacks = [item for item in self.callbacks if item[0] is not func]


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

    _process = _noop_method("_process", 'self')


class _Manager:
    def __init__(self, canvas):
        self.canvas = canvas
        self.key_press_handler_id = None
    set_window_title = _noop_method("set_window_title", 'self, *args, **kwargs')
    def get_window_title(self): return ""
    destroy = _noop_method("destroy", 'self')


class _Canvas:
    """Headless canvas stand-in for code that calls draw or print_figure."""

    def __init__(self, figure):
        self.figure = figure
        self.manager = _Manager(self)
    draw = _noop_method("draw", 'self, *args, **kwargs')
    draw_idle = _noop_method("draw_idle", 'self, *args, **kwargs')
    flush_events = _noop_method("flush_events", 'self')
    get_renderer = _noop_method("get_renderer", 'self, *args, **kwargs')
    def get_width_height(self):
        w, h = self.figure.get_size_inches()
        dpi = self.figure.get_dpi()
        return int(w * dpi), int(h * dpi)
    def print_figure(self, filename, **kwargs):
        return self.figure.savefig(filename, **kwargs)
    def mpl_connect(self, *args, **kwargs): return 1
    mpl_disconnect = _noop_method("mpl_disconnect", 'self, *args, **kwargs')
    def add_callback(self, *args, **kwargs): return 1
    remove_callback = _noop_method("remove_callback", 'self, *args, **kwargs')
    def supports_blit(self): return False
    blit = _noop_method("blit", 'self, *args, **kwargs')
    restore_region = _noop_method("restore_region", 'self, *args, **kwargs')
    copy_from_bbox = _noop_method("copy_from_bbox", 'self, *args, **kwargs')
    def new_timer(self, interval=1000, callbacks=None, **kwargs):
        return _Timer(interval, callbacks, **kwargs)
    set_window_title = _noop_method("set_window_title", 'self, *args, **kwargs')
    start_event_loop = _noop_method("start_event_loop", 'self, *args, **kwargs')
    stop_event_loop = _noop_method("stop_event_loop", 'self, *args, **kwargs')


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
    x = _as_f64(x)
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
    y = _as_f64(y)
    _check_same_length(y, x)
    py = np.stack([y[i:i + nfft] * taper
                   for i in range(0, y.size - nfft + 1, step)])
    fy = np.fft.rfft(py, n=size, axis=1)
    pxy = np.mean(fx * np.conj(fy), axis=0) / norm
    return pxx, np.mean(np.abs(fy) ** 2, axis=0) / norm, pxy, freqs


# Matplotlib's `Axes.set` is `Artist.set` plus the Axes-specific aliases below,
# so an Artist property without a dedicated setter is still accepted (and, for
# the ones the renderer has no model for, recorded as an ignored shim).


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._config import rcParams
    from ._plot_helpers import _as_f64, _check_same_length, _series
