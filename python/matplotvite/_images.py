"""Image, contour and colorbar artists."""
import math as _math
from typing import TYPE_CHECKING

import numpy as np

from ._artists import Patch, _LocatorHandle
from ._core import (
    Normalize as _Normalize,
)
from ._helpers import (
    Path,
    _Bbox,
    _cmap_name,
    _ignored,
    _noop_method,
    _norm_color,
    _share_axes,
    _TextLabel,
    _Transform,
    _validate_grid_shape,
    get_cmap,
)
from ._plot_helpers import (
    _as_f64,
    _as_image,
    _contour_label_colour,
    _contour_label_text,
    _contour_segments,
    _path_subpaths,
    _point_segment_distance,
    _polygon_area_sign,
)


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
        levels = [float(v) for v in _as_f64(levels)]
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
        rgb = _as_f64(get_cmap(self._e["cmap"])(t))[:3]
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

    add_label_near = _noop_method("add_label_near", 'self, x, y, inline=True, inline_spacing=5, transform=None')

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
                level_kinds = (self._manual_kinds[index]  # type: ignore[index]
                               if index < len(self._manual_kinds) else None)  # type: ignore[arg-type]
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

    draw = _noop_method("draw", 'self, renderer=None')


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
        self._x = _as_f64(x)
        self._y = _as_f64(y)
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
    draw = _noop_method("draw", 'self, renderer=None')
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
    set_rasterized = _noop_method(
        "set_rasterized", 'self, value', warn='AxesImage.set_rasterized')
    set_agg_filter = _noop_method(
        "set_agg_filter", 'self, value', warn='AxesImage.set_agg_filter')
    def remove(self):
        if self.axes is not None:
            self.axes.images[:] = [image for image in self.axes.images
                                   if image is not self]
        return None
    set_path_effects = _noop_method(
        "set_path_effects", 'self, value', warn='AxesImage.set_path_effects')
    set_url = _noop_method(
        "set_url", 'self, value', warn='AxesImage.set_url')
    set_gid = _noop_method(
        "set_gid", 'self, value', warn='AxesImage.set_gid')
    set_zorder = _noop_method(
        "set_zorder", 'self, value', warn='AxesImage.set_zorder')
    set_clip_on = _noop_method(
        "set_clip_on", 'self, value', warn='AxesImage.set_clip_on')
    set_clip_path = _noop_method(
        "set_clip_path", 'self, *args, **kwargs', warn='AxesImage.set_clip_path')
    set_transform = _noop_method(
        "set_transform", 'self, value', warn='AxesImage.set_transform')
    set_visible = _noop_method(
        "set_visible", 'self, value', warn='AxesImage.set_visible')
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

    tight_layout = _noop_method("tight_layout", 'self, *args, **kwargs')

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

    set_tick_params = _noop_method("set_tick_params", 'self, *args, **kwargs')
    tick_right = _noop_method("tick_right", 'self')
    tick_left = _noop_method("tick_left", 'self')
    set_label_text = _noop_method("set_label_text", 'self, *args, **kwargs')
    set_label_position = _noop_method("set_label_position", 'self, position')
    set_ticks_position = _noop_method("set_ticks_position", 'self, position')
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
    set_visible = _noop_method("set_visible", 'self, value')
    set_axis_off = _noop_method("set_axis_off", 'self')
    set_ylabel = _noop_method("set_ylabel", 'self, *args, **kwargs')
    set_xlabel = _noop_method("set_xlabel", 'self, *args, **kwargs')
    set_title = _noop_method("set_title", 'self, *args, **kwargs')
    tick_params = _noop_method("tick_params", 'self, *args, **kwargs')
    set_yticks = _noop_method("set_yticks", 'self, *args, **kwargs')
    set_xticks = _noop_method("set_xticks", 'self, *args, **kwargs')
    set_yticklabels = _noop_method("set_yticklabels", 'self, *args, **kwargs')
    set_xticklabels = _noop_method("set_xticklabels", 'self, *args, **kwargs')
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
            candidate = _as_f64(low)
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
        bounds = _as_f64(boundaries)
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
            values_arr = _as_f64(bounds)
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
    add_lines = _noop_method("add_lines", 'self, *args, **kwargs')
    minorticks_on = _noop_method("minorticks_on", 'self')
    minorticks_off = _noop_method("minorticks_off", 'self')
    set_ticks = _noop_method("set_ticks", 'self, *args, **kwargs')
    set_ticklabels = _noop_method("set_ticklabels", 'self, *args, **kwargs')
    set_clim = _noop_method("set_clim", 'self, *args, **kwargs')
    update_normal = _noop_method("update_normal", 'self, *args, **kwargs')


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._config import rcParams
