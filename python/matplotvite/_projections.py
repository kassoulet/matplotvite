"""Polar, 3D and geographic projections."""
import numpy as np

from ._artists import Circle, Polygon, RegularPolygon
from ._axes import Axes
from ._cm import _AxisModule
from ._config import _Namespace, rcParams
from ._containers import _BarContainer, _font_family
from ._helpers import Path, _noop_method
from ._plot_helpers import _as_f64, _bar_colors, _fill, _series
from ._ticker import (
    _AutoDateFormatter,
    _AutoDateLocator,
    _ConciseDateConverter,
    _ConciseDateFormatter,
    _DateFormatter,
    _DayLocator,
    _drange,
    _EngFormatter,
    _FixedFormatter,
    _FixedLocator,
    _HourLocator,
    _IndexLocator,
    _LinearLocator,
    _LogLocator,
    _MaxNLocator,
    _MinuteLocator,
    _MonthLocator,
    _MultipleLocator,
    _NoopFormatter,
    _NoopLocator,
    _PercentFormatter,
    _RRuleLocator,
    _rrulewrapper,
    _SecondLocator,
    _YearLocator,
)


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

    set_minor_locator = _noop_method("set_minor_locator", 'self, locator')
    set_major_locator = _noop_method("set_major_locator", 'self, locator')
    set_ticks_position = _noop_method("set_ticks_position", 'self, position')
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
    def _gen_axes_spines(self): return {}  # noqa: V105 (Matplotlib hook, called by name)

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
            args = list(args)  # type: ignore[assignment]
            while i < len(args):
                if isinstance(args[i], str) or i + 1 >= len(args):
                    values.append(args[i])
                    i += 1
                    continue
                x = _as_f64(args[i])
                y = _as_f64(args[i + 1])
                if x.size and (x[0] != x[-1] or y[0] != y[-1]):
                    x, y = np.append(x, x[0]), np.append(y, y[0])
                values.extend((x, y))
                i += 2
            args = values  # type: ignore[assignment]
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
        theta = _as_f64(theta)
        radius = _as_f64(radius)
        if theta.size != radius.size:
            theta, radius = np.broadcast_arrays(theta, radius)
            theta, radius = theta.ravel(), radius.ravel()
        limits = self._polar_theta_limits()
        if limits is None:
            return [(theta, radius)]
        lo, hi = limits
        inside = (theta >= lo - 1e-12) & (theta <= hi + 1e-12)
        segments, current_t, current_r = [], [], []  # type: ignore[var-annotated]

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
        wedges = []  # type: ignore[var-annotated]
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
            values = _as_f64(bottom)
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
        radii = [float(v) for v in _as_f64(radii)]
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
        angles = [float(v) for v in _as_f64(angles)]
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
        lines, texts = [], []  # type: ignore[var-annotated]

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
            values = _as_f64(bottom)
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
