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


__all__ = ("AnchoredDirectionArrows", "AnchoredDrawingArea", "AnchoredSizeBar",
           "AnchoredText")
