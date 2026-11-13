"""Minimal `mpl_toolkits.axes_grid1.inset_locator` compatibility layer.

The renderer has no artist-level locator objects, so this module turns the
common `inset_axes`/`zoomed_inset_axes` calls into an axes-fraction rectangle
and delegates to `Axes.inset_axes`.
"""

from matplotvite import rcParams

__all__ = ("inset_axes", "zoomed_inset_axes")

_LOCS = {
    "upper right": "upper right",
    "upper left": "upper left",
    "lower left": "lower left",
    "lower right": "lower right",
    "center left": "center left",
    "center right": "center right",
    "upper center": "upper center",
    "lower center": "lower center",
    "center": "center",
    "best": "upper right",
}


def _bounds(value):
    if hasattr(value, "bounds"):
        return tuple(float(v) for v in value.bounds)
    values = tuple(float(v) for v in value)
    if len(values) == 2:
        # A point anchor; the inset's own width/height supply the size.
        return (values[0], values[1], 0.0, 0.0)
    if len(values) != 4:
        raise ValueError("bbox_to_anchor must be a 2- or 4-tuple, or a Bbox")
    return values


def _axis_size(value, axis, parent, figure, parent_box):
    """Convert inches or a percentage into a parent-axes fraction."""
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            return float(text[:-1]) / 100.0
        value = float(text)
    inches = float(value)
    figure_size = float(figure.get_size_inches()[0 if axis == "x" else 1])
    extent = parent_box.width if axis == "x" else parent_box.height
    if figure_size <= 0.0 or extent <= 0.0:
        raise ValueError("inset_axes needs a positive figure and parent axes size")
    return inches / figure_size / extent


def _anchor_box(parent, bbox_to_anchor, bbox_transform):
    box = (0.0, 0.0, 1.0, 1.0) if bbox_to_anchor is None else _bounds(bbox_to_anchor)
    kind = getattr(bbox_transform, "kind", "axes") if bbox_transform is not None else "axes"
    if kind == "figure":
        outer = parent.get_position()
        if outer.width <= 0.0 or outer.height <= 0.0:
            raise ValueError("inset_axes needs a positive parent axes size")
        x, y, w, h = box
        box = ((x - outer.x0) / outer.width, (y - outer.y0) / outer.height,
               w / outer.width, h / outer.height)
    elif kind not in ("axes", "data"):
        raise NotImplementedError("inset_axes only supports axes/figure bounds")
    return box


def _place(anchor, width, height, loc, pad_x, pad_y):
    x, y, w, h = anchor
    loc = _LOCS.get(str(loc).lower(), "upper right")
    if "right" in loc:
        left = x + w - width - pad_x
    elif "left" in loc:
        left = x + pad_x
    else:
        left = x + (w - width) / 2.0
    if "upper" in loc:
        bottom = y + h - height - pad_y
    elif "lower" in loc:
        bottom = y + pad_y
    else:
        bottom = y + (h - height) / 2.0
    return left, bottom, width, height


def inset_axes(parent_axes, width="30%", height="30%", loc="upper right",
               bbox_to_anchor=None, bbox_transform=None, axes_class=None,
               axes_kwargs=None, borderpad=0.5, **kwargs):
    """Create a child axes using Matplotlib's width/height/location arguments."""
    figure = parent_axes.get_figure()
    parent_box = parent_axes.get_position()
    width = _axis_size(width, "x", parent_axes, figure, parent_box)
    height = _axis_size(height, "y", parent_axes, figure, parent_box)
    anchor = _anchor_box(parent_axes, bbox_to_anchor, bbox_transform)
    fontsize = float(rcParams.get("font.size", 10.0))
    fig_width, fig_height = (float(v) for v in figure.get_size_inches())
    pad_x = float(borderpad) * fontsize / 72.0 / fig_width / parent_box.width
    pad_y = float(borderpad) * fontsize / 72.0 / fig_height / parent_box.height
    child = parent_axes.inset_axes(_place(anchor, width, height, loc, pad_x, pad_y),
                                   zorder=kwargs.pop("zorder", 5))
    options = dict(axes_kwargs or {})
    options.update(kwargs)
    if options.pop("sharex", False):
        child.set_xlim(parent_axes.get_xlim())
    if options.pop("sharey", False):
        child.set_ylim(parent_axes.get_ylim())
    if "xlim" in options:
        child.set_xlim(options.pop("xlim"))
    if "ylim" in options:
        child.set_ylim(options.pop("ylim"))
    if "xlabel" in options:
        child.set_xlabel(options.pop("xlabel"))
    if "ylabel" in options:
        child.set_ylabel(options.pop("ylabel"))
    if "title" in options:
        child.set_title(options.pop("title"))
    if "facecolor" in options:
        child.set_facecolor(options.pop("facecolor"))
    # axes_class, projection and the remaining artist kwargs are accepted for
    # source compatibility; the renderer always creates its own Axes type.
    return child


def zoomed_inset_axes(parent_axes, zoom, loc="upper right", bbox_to_anchor=None,
                      bbox_transform=None, axes_class=None, borderpad=0.5,
                      **kwargs):
    """Create an inset axes showing a centred `1/zoom` portion of the parent."""
    zoom = float(zoom)
    if not zoom > 0.0:
        raise ValueError("zoom must be positive")
    child = inset_axes(parent_axes, width=f"{100.0 / zoom}%", height=f"{100.0 / zoom}%",
                       loc=loc, bbox_to_anchor=bbox_to_anchor,
                       bbox_transform=bbox_transform, axes_class=axes_class,
                       borderpad=borderpad, **kwargs)
    x0, x1 = sorted(parent_axes.get_xlim())
    y0, y1 = sorted(parent_axes.get_ylim())
    xc, yc = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    xr, yr = (x1 - x0) / (2.0 * zoom), (y1 - y0) / (2.0 * zoom)
    child.set_xlim(xc - xr, xc + xr)
    child.set_ylim(yc - yr, yc + yr)
    return child
