"""Figure, subfigures and the figure-level artists."""
import hashlib as _hashlib
import math as _math
import os
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from ._artists import Patch, Rectangle, _Callbacks, _Canvas, _LayoutEngine, _SubplotPars
from ._axes import Axes
from ._containers import _family_override, _font_family, _font_size, _LegendHandle
from ._core import (
    render as _render,
)
from ._helpers import (
    _COMPRESSIONS,
    _MAX_CANVAS_AREA,
    _MAX_CANVAS_DIM,
    _MAX_FIGIMAGE_BYTES,
    _MAX_FIGIMAGE_DIM,
    _MAX_FIGIMAGE_PIXELS,
    DPI,
    _apply_axes_options,
    _Bbox,
    _cmap_name,
    _CoordTransform,
    _deprecated,
    _FigureImage,
    _ignored,
    _mathtext,
    _noop_method,
    _norm_color,
    _output_format,
    _share_axes,
    _text_props,
    _TextArt,
    _Transform,
    _validate_dimension,
    _validate_figsize,
    _validate_grid_shape,
    _validate_savefig_mapping,
)
from ._images import (
    Colorbar,
    ContourSet,
    GridSpec,
    SubplotSpec,
    _resolve_colorbar_extendfrac,
)
from ._plot_helpers import (
    _as_f64,
    _as_image,
    _figimage_payload_estimate,
    _hash_value,
    _panel_cache_key,
)


class Figure:
    """A figure holding one or more axes plus figure-level artists."""
    def __init__(self, figsize: Any = None, dpi: Any = None,
                 facecolor: Any = None, edgecolor: Any = None) -> None:
        if figsize is None:
            figsize = rcParams.get("figure.figsize", (6.4, 4.8))
        self.figsize = _validate_figsize(figsize)
        self.number: Optional[int] = None
        self.grid: tuple[int, int] = (1, 1)
        self.axes: list[Any] = []
        self._cur: Any = None
        self._colorbar: Any = None
        self.dpi = _validate_dimension(
            dpi if dpi is not None else rcParams.get("figure.dpi", DPI), "dpi"
        )
        self.facecolor = _norm_color(
            facecolor if facecolor is not None else rcParams.get("figure.facecolor"))
        self.edgecolor = _norm_color(edgecolor)
        self._linewidth = 0.0
        self._suptitle: Any = None
        self._supxlabel = ""
        self._supylabel = ""
        self._figure_texts: list[Any] = []
        self._figure_images: list[Any] = []
        self.artists: list[Any] = []
        self.patches: list[Any] = []
        self._render_cache: Any = None
        self.transFigure = _CoordTransform("figure")
        self.transSubfigure = self.transFigure
        self.canvas = _Canvas(self)
        self.layout_engine = _LayoutEngine()
        self.subplotpars = _SubplotPars()
        self.patch = Rectangle((0, 0), 1, 1, transform=self.transFigure,
                               facecolor=self.get_facecolor())
        self._gridspec: Any = None
        self._label = ""
        self.callbacks = _Callbacks()

    def suptitle(self, t, x=0.5, y=0.98, fontsize=None, **kwargs):
        """Draw a figure-level title above the panel grid."""
        size = _font_size(fontsize, rcParams.get("figure.titlesize", 12.0))
        family = _family_override(kwargs)
        self._suptitle = dict(text=_mathtext(t, family), raw=str(t), size=size,
                              x=float(x), y=float(y), family=family)
        return None

    def supxlabel(self, t, x=0.5, y=0.01, fontsize=None, **kwargs):
        """Draw a figure-level x label below the panel grid."""
        self._supxlabel = str(t)
        kwargs.setdefault("ha", "center")
        kwargs.setdefault("va", "bottom")
        return self.text(x, y, t, fontsize=fontsize, **kwargs)

    def supylabel(self, t, x=0.02, y=0.5, fontsize=None, **kwargs):
        """Draw a figure-level y label left of the panel grid."""
        self._supylabel = str(t)
        kwargs.setdefault("ha", "center")
        kwargs.setdefault("va", "bottom")
        kwargs.setdefault("rotation", 90)
        return self.text(x, y, t, fontsize=fontsize, **kwargs)

    align_xlabels = _noop_method("align_xlabels", 'self, axs=None')
    align_ylabels = _noop_method("align_ylabels", 'self, axs=None')
    align_titles = _noop_method("align_titles", 'self, axs=None')
    align_labels = _noop_method("align_labels", 'self, axs=None')

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
            nrows, remainder = divmod(nrows, 100)
            ncols, index = divmod(remainder, 10)
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
        cells = {}  # type: ignore[var-annotated]
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

    def subplots(self, nrows: Any = 1, ncols: Any = 1, *, sharex: Any = False,
                 sharey: Any = False, squeeze: Any = True, subplot_kw: Any = None,
                 gridspec_kw: Any = None) -> Any:
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

    def gca(self) -> Any:
        return self._cur or self.add_subplot()

    def add_axes(self, rect: Any = None, **kwargs: Any) -> Any:
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

    draw_without_rendering = _noop_method("draw_without_rendering", 'self')
    draw = _noop_method("draw", 'self, *args, **kwargs')

    # Layout requests are accepted but ignored: panels always fill their gridspec
    # cells, so there are no margins to negotiate.
    tight_layout = _noop_method("tight_layout", 'self, **kwargs')
    subplots_adjust = _noop_method("subplots_adjust", 'self, *args, **kwargs')
    def set_layout_engine(self, engine=None, **kwargs):
        self.layout_engine = (engine if isinstance(engine, _LayoutEngine)
                              else _LayoutEngine(engine))

    def get_layout_engine(self): return getattr(self, "layout_engine", None)
    def get_axes(self): return list(self.axes)
    def get_dpi(self): return self.dpi or DPI
    def get_figwidth(self): return self.figsize[0]
    def get_figheight(self): return self.figsize[1]
    def get_linewidth(self): return self._linewidth
    def get_suptitle(self): return self._suptitle["raw"] if self._suptitle else ""
    def get_supxlabel(self): return self._supxlabel
    def get_supylabel(self): return self._supylabel

    def set_figwidth(self, width, forward=True):
        self.figsize = (_validate_dimension(width, "figwidth"), self.figsize[1])

    def set_figheight(self, height, forward=True):
        self.figsize = (self.figsize[0], _validate_dimension(height, "figheight"))

    def set_linewidth(self, width):
        value = float(width)
        if not _math.isfinite(value) or value < 0.0:
            raise ValueError(f"linewidth must be finite and non-negative, got {width!r}")
        self._linewidth = value

    def set_dpi(self, value):
        self.dpi = _validate_dimension(value, "dpi")

    def get_constrained_layout_pads(self, which=None, **kwargs):
        return (None, None, None, None)

    def sca(self, ax):
        if ax not in self.axes:
            raise ValueError("Axes has not been added yet")
        self._cur = ax
        return ax

    def clf(self, keep_observers=False):
        """Clear every axes and figure-level artist, keeping the figure itself."""
        for ax in self.axes:
            ax._fig = None
        self.axes.clear()
        self._cur = None
        self._colorbar = None
        self._suptitle = None
        self._supxlabel = self._supylabel = ""
        self._figure_texts = []
        self._figure_images = []
        self.artists = []
        self.patches = []
        self._render_cache = None

    def delaxes(self, ax):
        if ax in self.axes:
            self.axes.remove(ax)
            if self._cur is ax:
                self._cur = None
            ax._fig = None

    @property
    def dpi_scale_trans(self): return _Transform()
    def get_facecolor(self): return self.facecolor or "white"
    def get_edgecolor(self): return self.edgecolor
    def get_size_inches(self): return self.figsize
    def get_label(self) -> str: return self._label
    def set_label(self, label: Any) -> "Figure": self._label = str(label); return self

    def set_facecolor(self, color):
        self.facecolor = _norm_color(color)
        if getattr(self, "patch", None) is not None:
            self.patch.set_facecolor(self.facecolor)
        return self

    def set_edgecolor(self, color):
        self.edgecolor = _norm_color(color)
        if getattr(self, "patch", None) is not None:
            self.patch.set_edgecolor(self.edgecolor)
        return self

    show = _noop_method("show", 'self, warn=True')

    waitforbuttonpress = _noop_method("waitforbuttonpress", 'self, timeout=-1')

    ginput = _noop_method(
        "ginput", 'self, n=1, timeout=30, show_clicks=True, mouse_add=1, mouse_pick=2, mouse_pop=3, mouse_stop=4', warn='Figure.ginput')

    def pick(self, mouseevent):
        """Dispatch a pick event to every axes, as `Figure.pick`."""
        return [artist for ax in self.axes for artist in ax.pick(mouseevent)]

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

    get_tightbbox = _noop_method("get_tightbbox", 'self, renderer=None, *args, **kwargs')
    set_tight_layout = _noop_method("set_tight_layout", 'self, value')
    def get_tight_layout(self): return False
    set_constrained_layout = _noop_method("set_constrained_layout", 'self, value')
    def get_constrained_layout(self): return False
    set_constrained_layout_pads = _noop_method("set_constrained_layout_pads", 'self, **kwargs')

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


    def savefig(self, fname: Any = None, format: Any = None, dpi: Any = None,
                bbox_inches: Any = None, transparent: Any = None,
                facecolor: Any = None, edgecolor: Any = None,
                compression: Any = None, pad_inches: Any = None,
                metadata: Any = None, pil_kwargs: Any = None,
                **kwargs: Any) -> Any:
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
        fmt, dpi, transparent, compression = _savefig_request(
            fname, format, dpi, bbox_inches, transparent, compression,
            metadata, pil_kwargs, self.dpi or DPI)
        w, h = _canvas_pixels(self.figsize, dpi)
        panels = self._render_panels(dpi, transparent)
        options = self._savefig_options(fmt, dpi, bbox_inches, transparent,
                                        compression, facecolor, edgecolor)
        data = self._encode((w, h), panels, options)
        return _write_output(fname, data)

    def _render_panels(self, dpi, transparent):
        """Panel payloads for one save, already stamped with the render dpi."""
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
        return panels

    def _savefig_options(self, fmt, dpi, bbox_inches, transparent, compression,
                         facecolor, edgecolor):
        """Renderer options for one save; they are part of the cache key."""
        return {
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

    def _encode(self, size, panels, options):
        """Encode the figure, reusing the last bytes when nothing changed.

        The key covers both the panel payload and every render option, so any
        edit invalidates it.
        """
        panel_keys = [panel.get("cache_key", "") for panel in panels]
        try:
            if any(not panel_key for panel_key in panel_keys):
                raise TypeError("panel data is not hashable")
            hasher = _hashlib.blake2b(digest_size=16)
            _hash_value(hasher, (size, self.grid, panel_keys, options))
            key = hasher.digest()
        except (TypeError, ValueError):
            key = None
        if key is not None and self._render_cache is not None and self._render_cache[0] == key:
            return self._render_cache[1]
        data = _render(size, self.grid, panels, options)
        if key is not None:
            self._render_cache = (key, data)
        return data


def _savefig_request(fname, format, dpi, bbox_inches, transparent, compression,
                     metadata, pil_kwargs, default_dpi):
    """Validate savefig's output request: `(fmt, dpi, transparent, compression)`."""
    if transparent is None:
        transparent = bool(rcParams.get("savefig.transparent", False))
    metadata = _validate_savefig_mapping(metadata, "metadata")
    pil_kwargs = _validate_savefig_mapping(pil_kwargs, "pil_kwargs")
    if metadata:
        _ignored("savefig(metadata=...)")
    if pil_kwargs:
        _ignored("savefig(pil_kwargs=...)")
    dpi = _validate_dimension(dpi if dpi is not None else default_dpi, "dpi")
    if compression is not None:
        compression = str(compression).lower()
        if compression not in _COMPRESSIONS:
            raise ValueError(
                f"unsupported compression: {compression!r} "
                "(use 'fast', 'default', or 'best')"
            )
    if bbox_inches not in (None, "tight"):
        raise ValueError(f"unsupported bbox_inches: {bbox_inches!r} (use 'tight')")
    return _output_format(fname, format), dpi, transparent, compression


def _canvas_pixels(figsize, dpi):
    """Pixel size for `figsize` at `dpi`, with the renderer's canvas limits."""
    # Matplotlib truncates fractional pixels here (`int(width * dpi)`), matching
    # its canvas; rounding made 6.4x4.8 in at 72 dpi 461x346 instead of 460x345.
    rw, rh = (int(v * dpi) for v in figsize)
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
    return rw, rh


def _write_output(fname, data):
    """Return the encoded bytes, or write them to a path or file-like object."""
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
_figures: dict[int, Figure] = {}


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._cm import _norm_values
    from ._config import rcParams
    from ._projections import PolarAxes, _get_projection_class
