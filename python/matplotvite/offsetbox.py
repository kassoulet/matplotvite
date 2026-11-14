"""Anchored artist shims used by the `axes_grid1` gallery."""

from matplotvite import rcParams

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


class AnchoredText:
    """Text pinned to one corner of an axes."""

    def __init__(self, s, loc, *, pad=0.0, borderpad=0.5, prop=None,
                 frameon=True, **kwargs):
        self.text = str(s)
        self.loc = loc
        self.pad = pad
        self.borderpad = borderpad
        self.prop = dict(prop or {})
        self.frameon = frameon
        self.kwargs = kwargs

    def _add_to_axes(self, ax):
        size = self.prop.pop("size", self.kwargs.pop("fontsize", None))
        if size is None:
            size = rcParams.get("font.size", 10.0)
        self.prop.pop("path_effects", None)
        x, y, ha, va = _anchor(self.loc, self.pad)
        return ax.text(x, y, self.text, transform=ax.transAxes, ha=ha, va=va,
                       fontsize=size, **self.kwargs)

    def get_text(self):
        return self.text

    def set_text(self, s):
        self.text = str(s)
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
        ax.text(xc, y + (y1 - y0) * 0.02, self.label, ha="center",
                va="bottom", fontsize=self.kwargs.get("fontsize",
                                                      rcParams.get("font.size", 10.0)))
        return self


__all__ = ("AnchoredSizeBar", "AnchoredText")
