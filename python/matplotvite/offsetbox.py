"""Anchored artist shims used by the `axes_grid1` gallery."""

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


def _anchor(loc, pad):
    x, y, ha, va = _LOCS.get(str(loc).lower(), _LOCS["upper left"])
    pad = float(pad)
    if "center" not in str(loc).lower():
        x += pad if ha == "left" else -pad if ha == "right" else 0.0
        y += pad if va == "bottom" else -pad if va == "top" else 0.0
    return x, y, ha, va


class _Box:
    """Minimal text-frame handle; styling is accepted and ignored."""

    def set_boxstyle(self, *args, **kwargs):
        return self


class AnchoredText:
    """Text pinned to one corner of an axes."""

    def __init__(self, s, loc, *, pad=0.0, borderpad=0.5, prop=None,
                 frameon=True, bbox_to_anchor=None, bbox_transform=None,
                 **kwargs):
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

    def _add_to_axes(self, ax):
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

    def get_text(self):
        return self.text

    def set_text(self, s):
        self.text = str(s)
        return self


class AnchoredDrawingArea:
    """Fixed-size drawing area anchored to an axes corner."""

    def __init__(self, width, height, xdescent, ydescent, *, loc="upper left",
                 pad=0.0, borderpad=0.5, frameon=True, **kwargs):
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

    def _add_to_axes(self, ax):
        x, y, ha, va = _anchor(self.loc, self.pad)
        # A compact marker is enough to show the anchored drawing area; the
        # stored child artists do not have a renderer-level pixel canvas.
        color = self.kwargs.get("color", "black")
        self._text = ax.text(x, y, "○", transform=ax.transAxes, ha=ha, va=va,
                             color=color, fontsize=max(self.width, self.height) * 0.7)
        return self


class _DrawingArea:
    def __init__(self):
        self.artists = []

    def add_artist(self, artist):
        self.artists.append(artist)
        return artist


class AnchoredDirectionArrows:
    """Two perpendicular direction arrows pinned to an axes corner."""

    def __init__(self, transform, main_direction, cross_direction,
                 loc="upper left", *, pad=0.0, borderpad=0.0, sep_x=0.06,
                 sep_y=0.05, arrow_props=None, text_props=None, angle=0.0,
                 aspect_ratio=1.0, length=0.15, color="k",
                 fontproperties=None, **kwargs):
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

    def _add_to_axes(self, ax):
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

    def __init__(self, transform, size, label, loc, *, pad=0.1,
                 borderpad=0.5, sep=5, frameon=True, size_vertical=0,
                 color="black", **kwargs):
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

    def _add_to_axes(self, ax):
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

    def __init__(self, s, textprops=None, multilinebaseline=False):
        self._text = str(s)
        self.textprops = dict(textprops or {})
        self.multilinebaseline = multilinebaseline

    def get_text(self): return self._text
    def set_text(self, s): self._text = str(s); return self

    def _add_to_axes(self, ax):
        props = dict(self.textprops)
        props.setdefault("transform", ax.transAxes)
        props.setdefault("ha", "left")
        props.setdefault("va", "top")
        ax.text(0.02, 0.98, self._text, **props)
        return self


class DrawingArea:
    """A fixed-size box of arbitrary artists."""

    def __init__(self, width, height, xdescent=0, ydescent=0, clip=False):
        self.width = float(width)
        self.height = float(height)
        self.xdescent = float(xdescent)
        self.ydescent = float(ydescent)
        self.clip = bool(clip)
        self.artists = []

    def add_artist(self, artist):
        self.artists.append(artist)
        return artist

    def get_children(self): return list(self.artists)

    def _add_to_axes(self, ax):
        for artist in self.artists:
            if hasattr(artist, "_add_to_axes"):
                artist._add_to_axes(ax)
            else:
                ax.add_artist(artist)
        return self


class VPacker:
    """Vertical packer; children are added in order by the axes adapter."""

    def __init__(self, children=(), align="left", pad=0, sep=0,
                 mode="fixed", **kwargs):
        self.children = list(children)
        self.align = align
        self.pad = pad
        self.sep = sep
        self.mode = mode
        self.kwargs = kwargs

    def _add_to_axes(self, ax):
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

    def __init__(self, arr, zoom=1, cmap=None, norm=None, interpolation=None,
                 origin=None, filternorm=True, filterrad=4.0, resample=False,
                 dpi_cor=True, **kwargs):
        self._arr = arr
        self.zoom = float(zoom)
        self.cmap = cmap
        self.image = _NamespaceLike(arr=arr, axes=None)

    def get_data(self): return self._arr

    def _add_to_axes(self, ax):
        self.image.axes = ax
        return self


class _NamespaceLike:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)


class AuxTransformBox:
    """Container for artists drawn in an auxiliary transform."""

    def __init__(self, aux_transform=None, **kwargs):
        self.aux_transform = aux_transform
        self.artists = []

    def add_artist(self, artist):
        self.artists.append(artist)
        return artist

    def get_children(self): return list(self.artists)

    def _add_to_axes(self, ax):
        for artist in self.artists:
            if hasattr(artist, "_add_to_axes"):
                artist._add_to_axes(ax)
            else:
                ax.add_artist(artist)
        return self


class AnchoredOffsetbox:
    """Offset box pinned to an axes corner."""

    def __init__(self, loc, child=None, pad=0.4, borderpad=0.5, frameon=True,
                 bbox_to_anchor=None, bbox_transform=None, **kwargs):
        self.loc = loc
        self.child = child
        self.pad = pad
        self.borderpad = borderpad
        self.frameon = frameon
        self.bbox_to_anchor = bbox_to_anchor
        self.bbox_transform = bbox_transform
        self.kwargs = kwargs
        self.patch = _Box()

    def _add_to_axes(self, ax):
        if self.child is not None:
            if hasattr(self.child, "_add_to_axes"):
                self.child._add_to_axes(ax)
            else:
                ax.add_artist(self.child)
        return self


class AnnotationBbox:
    """Place an offset box at a point on the axes."""

    def __init__(self, offsetbox, xy, xybox=None, xycoords="data",
                 boxcoords=None, frameon=True, box_alignment=(0.5, 0.5), **kwargs):
        self.offsetbox = offsetbox
        self.xy = xy
        self.xybox = xybox
        self.xycoords = xycoords
        self.boxcoords = boxcoords
        self.frameon = frameon
        self.box_alignment = box_alignment
        self.kwargs = kwargs

    def _add_to_axes(self, ax):
        if hasattr(self.offsetbox, "_add_to_axes"):
            self.offsetbox._add_to_axes(ax)
        return self


class Shadow:
    """Decorative shadow wrapper; the wrapped patch carries the drawing."""

    def __init__(self, patch, ox, oy, **kwargs):
        self.patch = patch
        self.ox = float(ox)
        self.oy = float(oy)
        self.kwargs = kwargs

    def draw(self, renderer=None): return None

    def set_gid(self, gid): self._gid = gid

    def get_gid(self): return getattr(self, "_gid", None)

    def set_zorder(self, zorder): self._zorder = zorder

    def get_zorder(self): return getattr(self, "_zorder", 1)

    def get_visible(self): return True

    def _add_to_axes(self, ax):
        # The underlying patch is already added by the offset box.
        return self


__all__ = ("AnchoredDirectionArrows", "AnchoredDrawingArea", "AnchoredSizeBar",
           "AnchoredText", "AnchoredOffsetbox", "AnnotationBbox",
           "AuxTransformBox", "DrawingArea", "HPacker", "OffsetImage", "Shadow",
           "TextArea", "VPacker")
