"""The Axes class: lifecycle, layout, ticks, scales and panel assembly."""
import math as _math
from typing import TYPE_CHECKING

import numpy as np

from ._artists import (
    Collection,
    Line2D,
    Patch,
    Rectangle,
    _Axis,
    _AxisAccessor,
    _AxisArtistProxy,
    _Callbacks,
    _collection_entry,
    _LocatorHandle,
    _patch_entry,
    _Spines,
)
from ._axes_decor import _DecorAxes
from ._axes_field import _FieldAxes
from ._axes_plot import _AXES_ARTIST_PROPS, _PlotAxes
from ._axes_stats import _StatsAxes
from ._containers import _font_family, _font_size, _GridLine, _LegendHandle
from ._core import (
    tick_target as _tick_target_core,
)
from ._helpers import (
    _CYCLE,
    DPI,
    Path,
    Text,
    _as_list,
    _auto_ticks,
    _Bbox,
    _CoordTransform,
    _cycle_colors,
    _date_label,
    _date_ticks,
    _date_to_num,
    _format_ticklabels,
    _ignored,
    _is_rgb,
    _logit_ticks,
    _looks_like_categories,
    _looks_like_dates,
    _margin,
    _noop_method,
    _norm_color,
    _PropCycler,
    _scale_transform_pair,
    _scale_values,
    _Share,
    _span_extent,
    _state_setter,
    _symlog_label,
    _symlog_ticks,
    _TextLabel,
    _Transform,
    _update_extent,
)


class Axes(_PlotAxes, _StatsAxes, _FieldAxes, _DecorAxes):
    """Matplotlib-style axes: plotting calls and axis configuration for one panel."""
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
        self.legend_labels = None  # type: ignore[assignment]
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
        self._autoscale_on = True
        self._autoscalex_on = True
        self._autoscaley_on = True
        self._navigate = True
        self._navigate_mode = None
        self._animated = False
        self._rasterized = False
        self._gid = None
        self._url = None
        self._picker = None
        self._sketch = (None, None, None)
        self._clip_box = None
        self._agg_filter = None
        self._path_effects = []
        self._anchor = "C"
        self._axisbelow = rcParams.get("axes.axisbelow", "line")
        self._transform = None
        self._transform_set = False
        self._xmargin = float(rcParams.get("axes.xmargin", 0.05))  # type: ignore[arg-type]
        self._ymargin = float(rcParams.get("axes.ymargin", 0.05))  # type: ignore[arg-type]
        self._tight_x = self._tight_y = False
        self._frame_on = True
        self._clip_path = None
        self._pan_start = None
        self._forward_navigation_events = "auto"
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
        self.axis = _AxisAccessor(self)  # type: ignore[method-assign]
        self.patches = []
        self.collections = []
        self.callbacks = _Callbacks()
        self._box_aspect = None
        self._axes_locator = None
        # Custom projections (Hammer, geo, ...) initialise their transform
        # graph here; base axes have no such method.
        if hasattr(self, "_set_lim_and_transforms"):
            self._set_lim_and_transforms()

    _set_lim_and_transforms = _noop_method("_set_lim_and_transforms", 'self')

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

    def set_forward_navigation_events(self, visible):
        """Store whether navigation events pass through this axes."""
        self._forward_navigation_events = visible
        return None

    def get_forward_navigation_events(self):
        """The stored navigation-event policy, `"auto"` by default."""
        return self._forward_navigation_events
    def set_navigate(self, visible): self._navigate = bool(visible)
    def get_navigate(self): return self._navigate
    def get_navigate_mode(self): return self._navigate_mode

    def get_aspect(self): return self.aspect

    # -- introspection / compatibility surface --------------------------------
    draw = _noop_method("draw", 'self, *args, **kwargs')

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
            fraction=0.0 if self._tight_x else self._xmargin,
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
            fraction=0.0 if self._tight_y else self._ymargin,
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

    set_facecolor = _state_setter(
        "facecolor", 'color', 'color')
    def get_alpha(self): return self.alpha
    def set_alpha(self, alpha): self.alpha = None if alpha is None else float(alpha)

    def get_transform(self): return self._transform or _Transform()

    def set_transform(self, transform):
        self._transform = transform
        self._transform_set = True
        return self

    def is_transform_set(self): return self._transform_set
    apply_aspect = _noop_method("apply_aspect", 'self, position=None')
    set_figure = _state_setter(
        "_fig", 'figure', 'figure')
    def get_lines(self): return [Line2D(entry) for entry in self.lines]
    def get_images(self): return list(self.images)
    set_gid = _state_setter(
        "_gid", 'gid', 'gid')
    def get_gid(self): return self._gid
    set_url = _state_setter(
        "_url", 'url', 'url')
    def get_url(self): return self._url
    def set_rasterized(self, value): self._rasterized = bool(value)
    def get_rasterized(self): return self._rasterized
    def set_sketch_params(self, scale=None, length=None, randomness=None):
        self._sketch = (scale, length, randomness)
    set_picker = _state_setter(
        "_picker", 'value', 'value')
    def get_picker(self): return self._picker
    set_clip_box = _state_setter(
        "_clip_box", 'box', 'box')
    def get_clip_box(self): return self._clip_box
    set_agg_filter = _state_setter(
        "_agg_filter", 'value', 'value')
    def get_agg_filter(self): return self._agg_filter
    def get_path_effects(self): return list(self._path_effects)
    def set_animated(self, value): self._animated = bool(value)
    def get_animated(self): return self._animated
    def get_anchor(self): return self._anchor
    set_axisbelow = _state_setter(
        "_axisbelow", 'value', 'value')
    def get_axisbelow(self): return self._axisbelow
    def add_callback(self, func, *args, **kwargs):
        return self.callbacks.add_callback(func, *args, **kwargs)
    def remove_callback(self, func): self.callbacks.remove_callback(func)

    def draw_artist(self, artist):
        renderer = self._fig.canvas.get_renderer() if self._fig is not None else None
        draw = getattr(artist, "draw", None)
        if draw is not None:
            draw(renderer)

    def xaxis_date(self, tz=None): self._x_date = True
    def yaxis_date(self, tz=None): self._y_date = True

    def format_xdata(self, x):
        formatter = self.xaxis.get_major_formatter()
        if formatter is not None and hasattr(formatter, "format_data_short"):
            return formatter.format_data_short(x)
        return f"{x:g}"

    def format_ydata(self, y):
        formatter = self.yaxis.get_major_formatter()
        if formatter is not None and hasattr(formatter, "format_data_short"):
            return formatter.format_data_short(y)
        return f"{y:g}"

    def format_coord(self, x, y):
        """Human-readable data coordinates for pointer readouts."""
        return f"(x, y) = ({self.format_xdata(x)}, {self.format_ydata(y)})"

    def format_cursor_data(self, data):
        """Format one data value the way Matplotlib's status bar does."""
        try:
            return f"[{data:0.3g}]"
        except (TypeError, ValueError):
            return "[]"

    def get_cursor_data(self, event):
        """The image value under `event`, or None when no image is hit."""
        x = getattr(event, "xdata", None)
        y = getattr(event, "ydata", None)
        if x is None or y is None:
            return None
        for image in reversed(self.images):
            extent = image.get_extent()
            data = image.get_array()
            if extent is None or data is None:
                continue
            left, right, bottom, top = (float(v) for v in extent)
            if not (min(left, right) <= x <= max(left, right)
                    and min(bottom, top) <= y <= max(bottom, top)):
                continue
            rows, cols = np.asarray(data).shape[:2]
            if rows == 0 or cols == 0:
                continue
            col = int((x - left) / (right - left) * cols) if right != left else 0
            row = int((y - top) / (bottom - top) * rows) if top != bottom else 0
            col = min(max(col, 0), cols - 1)
            row = min(max(row, 0), rows - 1)
            return np.asarray(data)[row, col]
        return None

    def _axes_display_bbox(self):
        if self._fig is None:
            return _Bbox(0.0, 0.0, 1.0, 1.0)
        box = self.get_position()
        width, height = self._fig.figsize
        dpi = self._fig.get_dpi()
        return _Bbox(box.x0 * width * dpi, box.y0 * height * dpi,
                     box.x1 * width * dpi, box.y1 * height * dpi)

    def contains_point(self, point):
        x, y = point
        return self._axes_display_bbox().contains(x, y)

    def contains(self, mouseevent=None):
        if mouseevent is None:
            return False, {}
        return self.contains_point((mouseevent.x, mouseevent.y)), {}

    def update_from(self, other):
        for name in ("_autoscale_on", "_autoscalex_on", "_autoscaley_on",
                     "_navigate", "_navigate_mode", "_animated", "_rasterized",
                     "_gid", "_url", "_picker", "_sketch", "_clip_box",
                     "_agg_filter", "_path_effects", "_anchor", "_axisbelow",
                     "_transform", "_transform_set"):
            if hasattr(other, name):
                setattr(self, name, getattr(other, name))

    def properties(self):
        """Current public state, mirroring `Artist.properties()`."""
        return {
            "adjustable": self.get_adjustable(),
            "agg_filter": self.get_agg_filter(),
            "alpha": self.get_alpha(),
            "anchor": self.get_anchor(),
            "animated": self.get_animated(),
            "aspect": self.get_aspect(),
            "autoscale_on": self.get_autoscale_on(),
            "autoscalex_on": self.get_autoscalex_on(),
            "autoscaley_on": self.get_autoscaley_on(),
            "axisbelow": self.get_axisbelow(),
            "box_aspect": self.get_box_aspect(),
            "facecolor": self.get_facecolor(),
            "figure": self._fig,
            "frame_on": self.get_frame_on(),
            "gid": self.get_gid(),
            "images": self.get_images(),
            "label": self.get_label(),
            "lines": self.get_lines(),
            "navigate": self.get_navigate(),
            "navigate_mode": self.get_navigate_mode(),
            "path_effects": self.get_path_effects(),
            "picker": self.get_picker(),
            "position": self.get_position(),
            "rasterized": self.get_rasterized(),
            "title": self.get_title(),
            "url": self.get_url(),
            "visible": self.get_visible(),
            "xlabel": self.get_xlabel(),
            "xlim": self.get_xlim(),
            "xscale": self.get_xscale(),
            "ylabel": self.get_ylabel(),
            "ylim": self.get_ylim(),
            "yscale": self.get_yscale(),
            "zorder": self.get_zorder(),
        }

    pchanged = _noop_method("pchanged", 'self')

    def findobj(self, match=None, include_self=True):
        candidates = ([self] if include_self else []) + [
            *self.get_lines(), *self.images, *self.patches, *self.collections,
            *self.texts, *self.artists,
        ]
        if match is None:
            return candidates
        if isinstance(match, type):
            return [item for item in candidates if isinstance(item, match)]
        return [item for item in candidates if match(item)]

    @property
    def bbox(self): return self.get_window_extent()

    @property
    def viewLim(self):
        x0, x1 = self.get_xlim()
        y0, y1 = self.get_ylim()
        return _Bbox(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def get_xticklines(self): return []
    def get_yticklines(self): return []
    def get_legend(self):
        """The legend handle when a legend is shown, otherwise None."""
        return _LegendHandle() if self.show_legend else None
    def get_legend_handles_labels(self):
        handles, labels = [], []
        for entry in self.lines:
            if entry.get("label"):
                handles.append(Line2D(entry))
                labels.append(entry["label"])
        return handles, labels











    set_rorigin = _noop_method("set_rorigin", 'self, value')
    set_rlabel_position = _noop_method("set_rlabel_position", 'self, value')
    set_thetalim = _noop_method("set_thetalim", 'self, *args, **kwargs')
    set_theta_zero_location = _noop_method("set_theta_zero_location", 'self, loc, offset=0.0')
    set_theta_offset = _noop_method("set_theta_offset", 'self, offset')
    set_thetamin = _noop_method("set_thetamin", 'self, value')
    set_thetamax = _noop_method("set_thetamax", 'self, value')
    def pie_label(self, container, labels, *, distance=0.6, textprops=None,
                  rotate=False, alignment="auto"):
        """Label the wedges of a `pie` container, as Matplotlib 3.11.

        `labels` is a sequence of strings or a format string using the
        `absval` and `frac` placeholders. When `rotate` is true each label
        follows its wedge; `alignment` is `"center"`, `"outer"` or `"auto"`.
        """
        if alignment not in ("center", "outer", "auto"):
            raise ValueError(
                f"alignment must be 'center', 'outer' or 'auto', not {alignment!r}")
        if alignment == "auto":
            alignment = "outer" if distance > 1 else "center"
        wedges = list(container.wedges)
        if isinstance(labels, str):
            labels = [labels.format(absval=absval, frac=frac) for absval, frac in
                      zip(container.values, container.fracs)]
        elif len(wedges) != len(labels):
            raise ValueError(
                f"The number of labels ({len(labels)}) must match the number "
                f"of wedges ({len(wedges)})")
        props = dict(textprops or {})
        texts = []
        for wedge, label in zip(wedges, labels):
            theta = 2.0 * _math.pi * 0.5 * (wedge.theta1 + wedge.theta2) / 360.0
            xt = wedge.center[0] + float(distance) * wedge.r * _math.cos(theta)
            yt = wedge.center[1] + float(distance) * wedge.r * _math.sin(theta)
            ha = ("left" if xt > 0 else "right") if alignment == "outer" else "center"
            va = "center"
            rotation = 0.0
            if rotate:
                if alignment == "outer":
                    va = "bottom" if yt > 0 else "top"
                rotation = float(np.rad2deg(theta)) + (0.0 if xt > 0 else 180.0)
            item_props = dict(props)
            item_props.setdefault("ha", ha)
            item_props.setdefault("va", va)
            item_props.setdefault("rotation", rotation)
            texts.append(self.text(xt, yt, label, **item_props))
        container.add_texts(texts)
        return texts

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
    set_box_aspect = _state_setter(
        "_box_aspect", 'aspect, **kwargs', 'aspect')
    def get_box_aspect(self): return self._box_aspect
    def set_axes_locator(self, locator):
        self._axes_locator = locator
        if locator is not None and hasattr(locator, "apply"):
            locator.apply(self)
        return self
    def get_axes_locator(self): return self._axes_locator
    def set_autoscale_on(self, value): self._autoscale_on = bool(value)
    def get_autoscale_on(self): return self._autoscale_on
    def set_autoscalex_on(self, value): self._autoscalex_on = bool(value)
    def get_autoscalex_on(self): return self._autoscalex_on
    def set_autoscaley_on(self, value): self._autoscaley_on = bool(value)
    def get_autoscaley_on(self): return self._autoscaley_on
    def set_frame_on(self, value): self._frame_on = bool(value)
    def set_xmargin(self, value): self._xmargin = float(value)
    def set_ymargin(self, value): self._ymargin = float(value)

    def margins(self, *margins, x=None, y=None, tight=True):
        """Set the autoscale margins and return the current `(x, y)` values.

        One positional value applies to both axes; two set x and y. The
        margins feed `get_xlim`/`get_ylim` the next time they autoscale.
        """
        if len(margins) > 2:
            raise TypeError("margins() takes at most 2 positional arguments")
        if margins:
            if x is not None or y is not None:
                raise TypeError("Cannot pass both positional and keyword arguments")
            if len(margins) == 1:
                x = y = margins[0]
            else:
                x, y = margins
        if x is not None:
            self._xmargin = float(x)
        if y is not None:
            self._ymargin = float(y)
        return (self._xmargin, self._ymargin)

    def get_xmargin(self): return self._xmargin
    def get_ymargin(self): return self._ymargin
    def get_frame_on(self): return self._frame_on
    def label_outer(self, remove_inner_ticks=False):
        """Hide tick labels on non-outer axes of a subplot grid.

        x labels stay on the last row and y labels on the first column. Inner
        tick marks are kept (`remove_inner_ticks` only changes labels here).
        """
        spec = self.get_subplotspec()
        self.hide_xticklabels = spec is None or not spec.is_last_row()
        self.hide_yticklabels = spec is None or not spec.is_first_col()
        self._label_outer = True
        return None

    def locator_params(self, axis="both", tight=None, **kwargs):
        """Configure the major locator's tick budget (`nbins`, `steps`, ...).

        Installs a `MaxNLocator` on axes that do not have an explicit locator.
        """
        if axis not in ("both", "x", "y"):
            raise ValueError(f"axis must be 'both', 'x', or 'y', not {axis!r}")
        for name in (("x", "y") if axis == "both" else (axis,)):
            axis_obj = self.xaxis if name == "x" else self.yaxis
            locator = axis_obj.get_major_locator()
            if isinstance(locator, _LocatorHandle):
                locator = _MaxNLocator()
                axis_obj.set_major_locator(locator)
            if hasattr(locator, "set_params"):
                locator.set_params(**kwargs)
        return None
    set_rmax = _noop_method("set_rmax", 'self, value')
    set_rmin = _noop_method("set_rmin", 'self, value')
    set_rlim = _noop_method("set_rlim", 'self, *args, **kwargs')
    secondary_xaxis = _noop_method(
        "secondary_xaxis", 'self, *args, **kwargs', warn='Axes.secondary_xaxis', returns_self=True)
    secondary_yaxis = _noop_method(
        "secondary_yaxis", 'self, *args, **kwargs', warn='Axes.secondary_yaxis', returns_self=True)
    def get_aux_axes(self, *args, **kwargs): return self

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
    update = _noop_method("update", 'self, *args, **kwargs')

    def get_label(self): return self.label
    def set_label(self, label): self.label = str(label)
    def get_zorder(self): return self.zorder
    def set_zorder(self, zorder): self.zorder = int(zorder)

    # Accepted for compatibility; custom artists are not rendered yet.
    def set_clip_path(self, path, transform=None):
        self._clip_path = path
        return None
    def get_clip_path(self):
        """The stored clip path, or the axes rectangle in data coordinates."""
        if self._clip_path is not None:
            return self._clip_path
        (x0, x1), (y0, y1) = self.get_xlim(), self.get_ylim()
        vertices = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]],
                            dtype=float)
        codes = np.array([Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO,
                          Path.CLOSEPOLY], dtype=np.uint8)
        return Path(vertices, codes)
    set_clip_on = _noop_method("set_clip_on", 'self, clip')
    set_path_effects = _noop_method("set_path_effects", 'self, effects')
    def get_xgridlines(self):
        """Major and minor x gridline handles, as Matplotlib returns."""
        return [_GridLine(self, "x", "major"), _GridLine(self, "x", "minor")]
    def get_ygridlines(self):
        """Major and minor y gridline handles, as Matplotlib returns."""
        return [_GridLine(self, "y", "major"), _GridLine(self, "y", "minor")]
    redraw_in_frame = _noop_method("redraw_in_frame", 'self')
    def pick(self, mouseevent):
        """Dispatch a pick event to children that implement `pick`."""
        picked = []
        for artist in self.get_children():
            if artist is self:
                continue
            handler = getattr(artist, "pick", None)
            if handler is not None and handler(mouseevent):
                picked.append(artist)
        return picked
    def start_pan(self, x, y, button=None):
        """Record the anchor for a pan gesture in display coordinates."""
        self._pan_start = dict(x=float(x), y=float(y), button=button,
                               xlim=self.get_xlim(), ylim=self.get_ylim())
    def end_pan(self):
        self._pan_start = None
    def drag_pan(self, button, key, x, y):
        """Shift the view by the display-space drag since `start_pan`."""
        start = self._pan_start
        if start is None:
            return None
        box = self._axes_display_bbox()
        width, height = box.x1 - box.x0, box.y1 - box.y0
        if width <= 0.0 or height <= 0.0:
            return None
        (xmin, xmax), (ymin, ymax) = start["xlim"], start["ylim"]
        dx = (float(x) - start["x"]) / width * (xmax - xmin)
        dy = (float(y) - start["y"]) / height * (ymax - ymin)
        self.set_xlim(xmin - dx, xmax - dx)
        self.set_ylim(ymin - dy, ymax - dy)
        return None
    def relim(self, visible_only=True):
        """Recompute the data limits from the current artists.

        Matplotvite derives extents from the artists on every access, so this
        only drops explicit limits on axes that still autoscale, mirroring the
        `relim` + redraw cycle.
        """
        for name in ("x", "y"):
            if not getattr(self, f"_autoscale{name}_on"):
                continue
            group = getattr(self, f"_share_{name}")
            if group is not None:
                group.limits = None
            setattr(self, f"{name}lim", None)
        return None

    def autoscale(self, enable=True, axis="both", tight=None):
        """Autoscale the view to the data, honoring the stored margins.

        `enable=True` re-enables autoscaling and recomputes the view from the
        data plus `margins`; `False` freezes the current view; `None` leaves
        the flags alone. `tight=True` zeroes the margins first, as Matplotlib
        does.
        """
        if axis not in ("both", "x", "y"):
            raise ValueError(f"axis must be 'both', 'x', or 'y', got {axis!r}")
        targets = ("x", "y") if axis == "both" else (axis,)
        for name in targets:
            if enable is not None:
                setattr(self, f"_autoscale{name}_on", bool(enable))
            if tight:
                setattr(self, f"_{name}margin", 0.0)
            group = getattr(self, f"_share_{name}")
            if getattr(self, f"_autoscale{name}_on"):
                if group is not None:
                    group.limits = None
                setattr(self, f"{name}lim", None)
            else:
                fixed = self.get_xlim() if name == "x" else self.get_ylim()
                if group is not None:
                    group.limits = fixed
                setattr(self, f"{name}lim", fixed)
        self.autoscale_view(tight=tight, scalex="x" in targets, scaley="y" in targets)
        return None

    def autoscale_view(self, tight=None, scalex=True, scaley=True):
        """Recompute the view from the data for every autoscaled axis."""
        for name, enabled in (("x", scalex), ("y", scaley)):
            if not enabled:
                continue
            if tight is not None:
                setattr(self, f"_tight_{name}", bool(tight))
            if not getattr(self, f"_autoscale{name}_on"):
                continue
            group = getattr(self, f"_share_{name}")
            if group is not None:
                group.limits = None
            setattr(self, f"{name}lim", None)
        return None

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
        self.legend_labels = None  # type: ignore[assignment]
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
            ticks = _as_f64(locator.tick_values(lo, hi))
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
            labels = _logit_ticks(*self.get_xlim(), self.logit_one_half,  # type: ignore[call-arg]
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
            labels = _logit_ticks(*self.get_ylim(), self.logit_one_half,  # type: ignore[call-arg]
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
            cls = _SCALES.get(name)  # type: ignore[assignment]
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
































    def set_xlim(self, left=None, right=None, **kwargs):
        """Set the x limits; accepts `left`/`right` or Matplotlib's `xmin`/`xmax`.

        `auto` turns x autoscaling on (`True`), off (`False`, the default), or
        leaves it unchanged (`None`), as Matplotlib does.
        """
        auto = kwargs.pop("auto", False)
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
        if auto is not None:
            self._autoscalex_on = bool(auto)
        self._inverted[0] = float(values[0]) > float(values[1])
        if self._share_x is not None:
            self._share_x.limits = limits
        return self.get_xlim()

    def set_ylim(self, bottom=None, top=None, **kwargs):
        """Set the y limits; accepts `bottom`/`top` or `ymin`/`ymax`.

        `auto` behaves like `set_xlim(auto=...)`.
        """
        auto = kwargs.pop("auto", False)
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
        if auto is not None:
            self._autoscaley_on = bool(auto)
        self._inverted[1] = float(values[0]) > float(values[1])
        if self._share_y is not None:
            self._share_y.limits = limits
        return self.get_ylim()


    def minorticks_on(self): self.minor_ticks = True
    def minorticks_off(self): self.minor_ticks = False
    def ticklabel_format(self, *, axis="both", style=None, scilimits=None,
                         useOffset=None, useLocale=None, useMathText=None):
        """Switch an axis between plain and scientific tick labels.

        `style` is `'plain'`, `'sci'` or None; `scilimits` must be a pair of
        exponents, as Matplotlib requires. The formatter writes each label in
        the requested style; there is no separate offset text yet.
        """
        if axis not in ("both", "x", "y"):
            raise ValueError(f"axis must be 'both', 'x', or 'y', not {axis!r}")
        if scilimits is not None and (
                not isinstance(scilimits, (tuple, list)) or len(scilimits) != 2):
            raise ValueError("scilimits must be a sequence of 2 integers")
        formatter = _ScalarFormatter(style=style, scilimits=scilimits,
                                     useOffset=useOffset, useLocale=useLocale,
                                     useMathText=useMathText)
        for name in (("x", "y") if axis == "both" else (axis,)):
            (self.xaxis if name == "x" else self.yaxis).set_major_formatter(formatter)
        return None
    def set_rasterization_zorder(self, zorder):
        self._rasterization_zorder = None if zorder is None else float(zorder)













    # Layout requests are accepted but ignored: every panel is drawn at its fixed
    # gridspec cell, so there is nothing to negotiate.
    tight_layout = _noop_method("tight_layout", 'self, **kwargs')
    subplots_adjust = _noop_method("subplots_adjust", 'self, **kwargs')
    set_layout_engine = _state_setter(
        "layout_engine", 'engine=None, **kwargs', 'engine')
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

    def _panel_series(self, x0, x1, y0, y1):
        """Resolve reference lines, spans, bands and polar geometry."""
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
        return series, bars, bands, polar_texts

    def _panel_ticks(self, x0, x1, y0, y1):
        """Resolve explicit, locator, date, category and scale-specific ticks."""
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
        return xticks, xticklabels, yticks, yticklabels

    def _panel(self, dpi=None):
        (x0, x1), (y0, y1) = self._limits()
        series, bars, bands, polar_texts = self._panel_series(x0, x1, y0, y1)
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
        font = float(rcParams.get("font.size", 10.0))  # type: ignore[arg-type]
        legend_font = (float(self.legend_fontsize) if self.legend_fontsize is not None
                       else float(rcParams.get("legend.fontsize", font)))  # type: ignore[arg-type]
        legend_title = (float(self.legend_title_fontsize)
                        if self.legend_title_fontsize is not None else legend_font * 1.1)
        xticks, xticklabels, yticks, yticklabels = self._panel_ticks(
            x0, x1, y0, y1)
        for payload in [*series, *bars, *bands]:
            payload.pop("_seq", None)
            payload.pop("_container", None)
        x_axis = dict(lim=(x0, x1), log=self.xscale == "log",
                      symlog=self.xscale == "symlog", logit=self.xscale == "logit",
                      asinh=self.xscale == "asinh",
                      symlog_linthresh=float(self.symlog_linthresh_x),
                      asinh_linear_width=float(self.asinh_linear_width_x),
                      label=self.xlabel, label_size=self.xlabel_size,
                      label_color=self.xlabel_color, label_family=self.xlabel_family)
        y_axis = dict(lim=(y0, y1), log=self.yscale == "log",
                      symlog=self.yscale == "symlog", logit=self.yscale == "logit",
                      asinh=self.yscale == "asinh",
                      symlog_linthresh=float(self.symlog_linthresh_y),
                      asinh_linear_width=float(self.asinh_linear_width_y),
                      label=self.ylabel, label_size=self.ylabel_size,
                      label_color=self.ylabel_color, label_family=self.ylabel_family)
        panel = dict(pos=self.pos, series=series, texts=texts, title=self.title,
                    font_family=_font_family(),
                    title_family=self.title_family,
                    dpi=float(self._fig.dpi if self._fig is not None else DPI),
                    title_size=self.title_size,
                    x=x_axis, y=y_axis,
                    legend=dict(show=self.show_legend, loc=self.legend_loc,
                                ncol=self.legend_ncol, frameon=self.legend_frameon,
                                fontsize=legend_font, family=self.legend_family or _font_family(),
                                title=self.legend_title,
                                title_fontsize=legend_title, anchor=self.legend_anchor,
                                labels=list(self.legend_labels or []),
                                order=self._legend_order()),
                    annotations=self.annotations,
                    aspect=self.aspect,
                    aspect_datalim=self._adjustable == "datalim",
                    contours=contours,
                    errors=self.errors,
                    bars=bars,
                    bands=bands,
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
                    patches=patches, collections=collections,
                    images=[(im._e["data"], im._e["cmap"], im._e["vmin"],
                             im._e["vmax"], im._e["extent"], True,
                             im._e["alpha"], im._e["interpolation"])
                            for im in self.images])
        return self._apply_axis_scales(panel)

    def _scale_panel_points(self, panel, fx, fy, scale):
        """Map ticks, series, bars, bands and scatter through custom scales."""
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

    def _scale_panel_geometry(self, panel, fx, fy, scale):
        """Map vector arrows and error-bar extents through custom scales."""
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

    def _scale_panel_artists(self, panel, fx, fy, scale, scalar, points):
        """Map contours, images, text, annotations, patches and collections."""
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

    def _scale_panel_limits(self, panel, fx, fy, scale):
        """Reproject limits, falling back to the scaled artist extents."""
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
            panel["x"]["lim"] = scaled_limits(fx, panel["x"]["lim"], "x")
        if fy is not None:
            panel["y"]["lim"] = scaled_limits(fy, panel["y"]["lim"], "y")

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

        self._scale_panel_points(panel, fx, fy, scale)
        self._scale_panel_geometry(panel, fx, fy, scale)
        self._scale_panel_artists(panel, fx, fy, scale, scalar, points)
        self._scale_panel_limits(panel, fx, fy, scale)
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
        font = float(rcParams.get("font.size", 10.0))  # type: ignore[arg-type]
        default = rcParams.get(f"{axis}tick.labelsize", font)
        rotation = style.get("rotation", 0.0)
        rotation = 0.0 if rotation == "auto" else float(rotation)
        return dict(labelsize=_font_size(style.get("labelsize"), default),
                    length=float(style.get("length", 3.5)),
                    width=float(style.get("width", 1.0)),
                    color=_norm_color(style.get("labelcolor")),
                    labelcolor=_norm_color(style.get("labelcolor")),
                    rotation=rotation)


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._config import _Namespace, rcParams
    from ._images import AxesImage, GridSpec, NonUniformImage, SubplotSpec
    from ._plot_helpers import _as_f64, _log_bounds, _norm_aspect, _series
    from ._pyplot import _ScalarFormatter
    from ._ticker import _MaxNLocator
