"""Axes mixin for text, labels, legends and grid styling."""
from typing import TYPE_CHECKING, Any

import numpy as np

from ._artists import FancyArrow
from ._axes_plot import _AxesMixinBase
from ._containers import _family_override, _font_family, _font_size, _LegendHandle
from ._helpers import (
    _LEGEND_KWARGS,
    _check_kwargs,
    _mathtext,
    _norm_color,
    _normalize_legend_loc,
    _text_props,
    _TextArt,
    _TextEntry,
)


class _DecorAxes(_AxesMixinBase):
    """Labels, annotation, legends and axis decoration."""

    def arrow(self, x: Any, y: Any, dx: Any, dy: Any, **kwargs: Any) -> Any:
        """Add a data-space `FancyArrow` and return the patch."""
        patch = FancyArrow(x, y, dx, dy, **kwargs)
        self.add_patch(patch)
        return patch

    def text(self, x: Any, y: Any, s: Any, fontdict: Any = None,
             offset: tuple[float, float] = (0.0, 0.0),
             **kwargs: Any) -> _TextArt:
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

    def annotate(self, text: Any, xy: Any, xytext: Any = None,
                 arrowprops: Any = None, color: Any = None,
                 fontsize: Any = None, **kwargs: Any) -> _TextArt:
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
        art.arrow_patch = _TextArt()  # type: ignore[attr-defined]
        return art

    def set_title(self, t: Any, fontsize: Any = None, **kwargs: Any) -> None:
        family = _family_override(kwargs)
        self.title = _mathtext(t, family)
        self.title_size = self._size_or(fontsize, "axes.titlesize")
        self.title_family = family

    def set_xlabel(self, t: Any, fontsize: Any = None, **kwargs: Any) -> None:
        family = _family_override(kwargs)
        self.xlabel = _mathtext(t, family)
        self.xlabel_size = self._size_or(fontsize, "axes.labelsize")
        self.xlabel_family = family
        if "color" in kwargs or "labelcolor" in kwargs:
            self.xlabel_color = _norm_color(kwargs.get("color", kwargs.get("labelcolor")))

    def set_ylabel(self, t: Any, fontsize: Any = None, **kwargs: Any) -> None:
        family = _family_override(kwargs)
        self.ylabel = _mathtext(t, family)
        self.ylabel_size = self._size_or(fontsize, "axes.labelsize")
        self.ylabel_family = family
        if "color" in kwargs or "labelcolor" in kwargs:
            self.ylabel_color = _norm_color(kwargs.get("color", kwargs.get("labelcolor")))

    @staticmethod
    def _size_or(value: Any, key: str) -> float:
        return _font_size(value, rcParams.get(key, rcParams.get("font.size", 10.0)))

    def legend(self, *args: Any, loc: Any = None, ncol: Any = None,
               ncols: Any = None, frameon: Any = None, fontsize: Any = None,
               title: Any = None, title_fontsize: Any = None,
               bbox_to_anchor: Any = None, handles: Any = None,
               labels: Any = None, fontfamily: Any = None,
               **kwargs: Any) -> _LegendHandle:
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

    def grid(self, visible: Any = None, which: str = "major", axis: str = "both",
             **kwargs: Any) -> None:
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
                        float(kwargs.get("linewidth", kwargs.get("lw"))))  # type: ignore[arg-type]
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

    def tick_params(self, axis: str = "both", **kwargs: Any) -> None:
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


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._config import rcParams
    from ._plot_helpers import _as_f64
