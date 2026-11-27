"""Anchored artist shims used by the `axes_grid1` gallery."""

from typing import Any

from matplotvite import _mathtext, rcParams

_LOCS = {
    "upper left": (0.0, 1.0, "left", "top"),
    "upper center": (0.5, 1.0, "center", "top"),
    "upper right": (1.0, 1.0, "right", "top"),
    "center left": (0.0, 0.5, "left", "center"),
    "center": (0.5, 0.5, "center", "center"),
    "center right": (1.0, 0.5, "right", "center"),
    "lower left": (0.0, 0.0, "left", "bottom"),
    "lower center": (0.5, 0.0, "center", "bottom"),
    "lower right": (1.0, 0.0, "right", "bottom"),
}


def _anchor(loc: Any, pad: Any) -> tuple[Any, Any, Any, Any]:
    x, y, ha, va = _LOCS.get(str(loc).lower(), _LOCS["upper left"])
    pad = float(pad)
    if "center" not in str(loc).lower():
        x += pad if ha == "left" else -pad if ha == "right" else 0.0
        y += pad if va == "bottom" else -pad if va == "top" else 0.0
    return x, y, ha, va


class _Box:
    """Minimal text-frame handle; styling is accepted and ignored."""

    def set_boxstyle(self, *args: Any, **kwargs: Any) -> Any:
        return self


class AnchoredText:
    """Text pinned to one corner of an axes."""

    def __init__(self, s: Any, loc: Any, *, pad: Any = 0.0, borderpad: Any = 0.5,
                 prop: Any = None, frameon: Any = True, bbox_to_anchor: Any = None,
                 bbox_transform: Any = None, **kwargs: Any) -> None:
        self.text = str(s)
        self.loc = loc
        self.pad = pad
        self.borderpad = borderpad
        self.prop = dict(prop or {})
        self.frameon = frameon
        self.bbox_to_anchor = bbox_to_anchor
        self.bbox_transform = bbox_transform
        self.kwargs = kwargs
        self.patch = _Box()

    def _add_to_axes(self, ax: Any) -> Any:
        size = self.prop.pop("size", self.kwargs.pop("fontsize", None))
        if size is None:
            size = rcParams.get("font.size", 10.0)
        self.prop.pop("path_effects", None)
        x, y, ha, va = _anchor(self.loc, self.pad)
        if self.bbox_to_anchor is not None:
            anchor = self.bbox_to_anchor
            if hasattr(anchor, "bounds"):
                anchor = anchor.bounds
            x, y = float(anchor[0]), float(anchor[1])
        return ax.text(x, y, _mathtext(self.text, self.prop.get("family")),
                       transform=ax.transAxes, ha=ha, va=va,
                       fontsize=size, **self.kwargs)

    def get_text(self) -> str:
        return self.text

    def set_text(self, s: Any) -> "AnchoredText":
        self.text = str(s)
        return self


class AnchoredDrawingArea:
    """Fixed-size drawing area anchored to an axes corner."""

    def __init__(self, width: Any, height: Any, xdescent: Any, ydescent: Any, *,
                 loc: Any = "upper left", pad: Any = 0.0, borderpad: Any = 0.5,
                 frameon: Any = True, **kwargs: Any) -> None:
        self.width = float(width)
        self.height = float(height)
        self.xdescent = float(xdescent)
        self.ydescent = float(ydescent)
        self.loc = loc
        self.pad = pad
        self.borderpad = borderpad
        self.frameon = frameon
        self.kwargs = kwargs
        self.da = _DrawingArea()

    def _add_to_axes(self, ax: Any) -> Any:
        x, y, ha, va = _anchor(self.loc, self.pad)
        # A compact marker is enough to show the anchored drawing area; the
        # stored child artists do not have a renderer-level pixel canvas.
        color = self.kwargs.get("color", "black")
        self._text = ax.text(x, y, "○", transform=ax.transAxes, ha=ha, va=va,
                             color=color, fontsize=max(self.width, self.height) * 0.7)
        return self


class _DrawingArea:
    def __init__(self) -> None:
        self.artists: list[Any] = []

    def add_artist(self, artist: Any) -> Any:
        self.artists.append(artist)
        return artist


class AnchoredDirectionArrows:
    """Two perpendicular direction arrows pinned to an axes corner."""

    def __init__(self, transform: Any, main_direction: Any, cross_direction: Any,
                 loc: Any = "upper left", *, pad: Any = 0.0, borderpad: Any = 0.0,
                 sep_x: float = 0.06, sep_y: float = 0.05, arrow_props: Any = None,
                 text_props: Any = None, angle: float = 0.0,
                 aspect_ratio: float = 1.0, length: float = 0.15,
                 color: Any = "k", fontproperties: Any = None,
                 **kwargs: Any) -> None:
        self.transform = transform
        self.main_direction = str(main_direction)
        self.cross_direction = str(cross_direction)
        self.loc = loc
        self.pad = pad
        self.sep_x = float(sep_x)
        self.sep_y = float(sep_y)
        self.angle = float(angle)
        self.aspect_ratio = float(aspect_ratio)
        self.length = float(length)
        self.color = color
        self.fontproperties = fontproperties
        self.arrow_props = dict(arrow_props or {})
        self.text_props = dict(text_props or {})
        self.kwargs = kwargs

    def _add_to_axes(self, ax: Any) -> Any:
        x, y, ha, va = _anchor(self.loc, self.pad)
        size = None if self.fontproperties is None else self.fontproperties.get_size()
        family = None if self.fontproperties is None else self.fontproperties.get_family()
        style = dict(transform=ax.transAxes, color=self.color, ha=ha, va=va,
                     rotation=self.angle, fontsize=size or rcParams.get("font.size", 10.0))
        if family:
            style["fontfamily"] = family
        # Arrow glyphs keep the anchored-direction cue visible without a new
        # renderer artist type; the labels carry the caller's text.
        self._main_arrow = ax.text(x, y, "→", **style)
        self._cross_arrow = ax.text(x, y - self.sep_y, "↑", **style)
        self._main_label = ax.text(x + self.sep_x, y, _mathtext(self.main_direction),
                                   **{**style, "rotation": 0})
        self._cross_label = ax.text(x + self.sep_x, y - self.sep_y,
                                    _mathtext(self.cross_direction),
                                    **{**style, "rotation": 0})
        return self


class AnchoredSizeBar:
    """A horizontal scale bar pinned to one side of an axes."""

    def __init__(self, transform: Any, size: Any, label: Any, loc: Any, *,
                 pad: Any = 0.1, borderpad: Any = 0.5, sep: Any = 5,
                 frameon: Any = True, size_vertical: Any = 0,
                 color: Any = "black", **kwargs: Any) -> None:
        self.transform = transform
        self.size = float(size)
        self.label = str(label)
        self.loc = loc
        self.pad = pad
        self.borderpad = borderpad
        self.sep = sep
        self.frameon = frameon
        self.size_vertical = float(size_vertical)
        self.color = color
        self.kwargs = kwargs

    def _add_to_axes(self, ax: Any) -> Any:
        x0, x1 = sorted(ax.get_xlim())
        y0, y1 = sorted(ax.get_ylim())
        span = x1 - x0
        if span <= 0:
            return self
        loc = str(self.loc).lower()
        xc = x0 + span / 2.0
        if "upper" in loc:
            y = y1 - (y1 - y0) * max(float(self.pad), 0.0)
        else:
            y = y0 + (y1 - y0) * max(float(self.pad), 0.0)
        half = self.size / 2.0
        ax.plot([xc - half, xc + half], [y, y], color=self.color,
                linewidth=3, solid_capstyle="butt")
        ax.text(xc, y + (y1 - y0) * 0.02, _mathtext(self.label), ha="center",
                va="bottom", fontsize=self.kwargs.get("fontsize",
                                                      rcParams.get("font.size", 10.0)))
        return self


class TextArea:
    """Plain text box used by offset-box layouts."""

    def __init__(self, s: Any, textprops: Any = None,
                 multilinebaseline: Any = False) -> None:
        self._text = str(s)
        self.textprops = dict(textprops or {})
        self.multilinebaseline = multilinebaseline

    def get_text(self) -> str: return self._text
    def set_text(self, s: Any) -> "TextArea": self._text = str(s); return self

    def _add_to_axes(self, ax: Any) -> Any:
        props = dict(self.textprops)
        props.setdefault("transform", ax.transAxes)
        props.setdefault("ha", "left")
        props.setdefault("va", "top")
        ax.text(0.02, 0.98, self._text, **props)
        return self


class PaddedBox:
    """A child offset box with padding; the renderer has no frame model."""

    def __init__(self, child: Any, pad: Any = 0.0, draw_frame: Any = False,
                 patch_attrs: Any = None, **kwargs: Any) -> None:
        self.child = child
        self.pad = float(pad)
        self.draw_frame = bool(draw_frame)
        self.patch_attrs = dict(patch_attrs or {})
        self.kwargs = kwargs

    def get_children(self) -> list[Any]: return [self.child] if self.child is not None else []

    def _add_to_axes(self, ax: Any) -> Any:
        if self.child is not None:
            if hasattr(self.child, "_add_to_axes"):
                self.child._add_to_axes(ax)
            else:
                ax.add_artist(self.child)
        return self


class DrawingArea:
    """A fixed-size box of arbitrary artists."""

    def __init__(self, width: Any, height: Any, xdescent: Any = 0,
                 ydescent: Any = 0, clip: Any = False) -> None:
        self.width = float(width)
        self.height = float(height)
        self.xdescent = float(xdescent)
        self.ydescent = float(ydescent)
        self.clip = bool(clip)
        self.artists: list[Any] = []

    def add_artist(self, artist: Any) -> Any:
        self.artists.append(artist)
        return artist

    def get_children(self) -> list[Any]: return list(self.artists)

    def _add_to_axes(self, ax: Any) -> Any:
        for artist in self.artists:
            if hasattr(artist, "_add_to_axes"):
                artist._add_to_axes(ax)
            else:
                ax.add_artist(artist)
        return self


class VPacker:
    """Vertical packer; children are added in order by the axes adapter."""

    def __init__(self, children: Any = (), align: Any = "left", pad: Any = 0,
                 sep: Any = 0, mode: Any = "fixed", **kwargs: Any) -> None:
        self.children = list(children)
        self.align = align
        self.pad = pad
        self.sep = sep
        self.mode = mode
        self.kwargs = kwargs

    def _add_to_axes(self, ax: Any) -> Any:
        for child in self.children:
            if hasattr(child, "_add_to_axes"):
                child._add_to_axes(ax)
            else:
                ax.add_artist(child)
        return self


class HPacker(VPacker):
    pass


class OffsetImage:
    """Image container for annotations; the array is retained for callers."""

    def __init__(self, arr: Any, zoom: Any = 1, cmap: Any = None, norm: Any = None,
                 interpolation: Any = None, origin: Any = None,
                 filternorm: Any = True, filterrad: Any = 4.0,
                 resample: Any = False, dpi_cor: Any = True,
                 **kwargs: Any) -> None:
        self._arr = arr
        self.zoom = float(zoom)
        self.cmap = cmap
        self.image = _NamespaceLike(arr=arr, axes=None)

    def get_data(self) -> Any: return self._arr

    def _add_to_axes(self, ax: Any) -> Any:
        self.image.axes = ax  # type: ignore[attr-defined]
        return self


class _NamespaceLike:
    def __init__(self, **kwargs: Any) -> None: self.__dict__.update(kwargs)


class AuxTransformBox:
    """Container for artists drawn in an auxiliary transform."""

    def __init__(self, aux_transform: Any = None, **kwargs: Any) -> None:
        self.aux_transform = aux_transform
        self.artists: list[Any] = []

    def add_artist(self, artist: Any) -> Any:
        self.artists.append(artist)
        return artist

    def get_children(self) -> list[Any]: return list(self.artists)

    def _add_to_axes(self, ax: Any) -> Any:
        for artist in self.artists:
            if hasattr(artist, "_add_to_axes"):
                artist._add_to_axes(ax)
            else:
                ax.add_artist(artist)
        return self


class AnchoredOffsetbox:
    """Offset box pinned to an axes corner."""

    def __init__(self, loc: Any, child: Any = None, pad: Any = 0.4,
                 borderpad: Any = 0.5, frameon: Any = True,
                 bbox_to_anchor: Any = None, bbox_transform: Any = None,
                 **kwargs: Any) -> None:
        self.loc = loc
        self.child = child
        self.pad = pad
        self.borderpad = borderpad
        self.frameon = frameon
        self.bbox_to_anchor = bbox_to_anchor
        self.bbox_transform = bbox_transform
        self.kwargs = kwargs
        self.patch = _Box()

    def _add_to_axes(self, ax: Any) -> Any:
        if self.child is not None:
            if hasattr(self.child, "_add_to_axes"):
                self.child._add_to_axes(ax)
            else:
                ax.add_artist(self.child)
        return self


class AnnotationBbox:
    """Place an offset box at a point on the axes."""

    def __init__(self, offsetbox: Any, xy: Any, xybox: Any = None,
                 xycoords: Any = "data", boxcoords: Any = None,
                 frameon: Any = True, box_alignment: Any = (0.5, 0.5),
                 **kwargs: Any) -> None:
        self.offsetbox = offsetbox
        self.xy = xy
        self.xybox = xybox
        self.xycoords = xycoords
        self.boxcoords = boxcoords
        self.frameon = frameon
        self.box_alignment = box_alignment
        self.kwargs = kwargs

    def _add_to_axes(self, ax: Any) -> Any:
        if hasattr(self.offsetbox, "_add_to_axes"):
            self.offsetbox._add_to_axes(ax)
        return self


class Shadow:
    """Decorative shadow wrapper; the wrapped patch carries the drawing."""

    def __init__(self, patch: Any, ox: Any, oy: Any, **kwargs: Any) -> None:
        self.patch = patch
        self.ox = float(ox)
        self.oy = float(oy)
        self.kwargs = kwargs

    def draw(self, renderer: Any = None) -> None: return None

    def set_gid(self, gid: Any) -> None: self._gid = gid

    def get_gid(self) -> Any: return getattr(self, "_gid", None)

    def set_zorder(self, zorder: Any) -> None: self._zorder = zorder

    def get_zorder(self) -> Any: return getattr(self, "_zorder", 1)

    def get_visible(self) -> bool: return True

    def _add_to_axes(self, ax: Any) -> Any:
        # The underlying patch is already added by the offset box.
        return self


__all__ = (
    "AnchoredDirectionArrows",
    "AnchoredDrawingArea",
    "AnchoredOffsetbox",
    "AnchoredSizeBar",
    "AnchoredText",
    "AnnotationBbox",
    "AuxTransformBox",
    "DrawingArea",
    "HPacker",
    "OffsetImage",
    "PaddedBox",
    "Shadow",
    "TextArea",
    "VPacker",
)
