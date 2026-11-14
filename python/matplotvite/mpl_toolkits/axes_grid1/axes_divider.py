"""Minimal axes divider support used by the `axes_grid1` examples."""

from matplotvite import _Share


def _size_in_fraction(value, base, figure_size):
    if isinstance(value, str):
        value = value.strip()
        if value.endswith("%"):
            return float(value[:-1]) / 100.0 * base
        value = value.rstrip("in")
    inches = float(value)
    return inches / figure_size


class Divider:
    """Place axes beside or above one existing axes."""

    def __init__(self, ax):
        self._ax = ax
        self._fig = ax._fig

    def append_axes(self, position, size, pad=0.1, sharex=None, sharey=None,
                    axes_class=None, **kwargs):
        if self._fig is None:
            raise RuntimeError("append_axes needs an axes attached to a figure")
        x, y, width, height = self._ax.get_position().bounds
        fig_w, fig_h = self._fig.get_size_inches()
        pad = float(pad)
        position = str(position).lower()
        if position in ("right", "left"):
            span = _size_in_fraction(size, width, fig_w)
            gap = pad / fig_w
            if position == "right":
                rect = (x + width + gap, y, span, height)
            else:
                rect = (x - gap - span, y, span, height)
        elif position in ("top", "bottom"):
            span = _size_in_fraction(size, height, fig_h)
            gap = pad / fig_h
            if position == "top":
                rect = (x, y + height + gap, width, span)
            else:
                rect = (x, y - gap - span, width, span)
        else:
            raise ValueError(f"unsupported append position: {position!r}")
        new = self._fig.add_axes(rect)
        self._share(new, sharex=sharex, sharey=sharey)
        return new

    def _share(self, new, sharex=None, sharey=None):
        if sharex:
            group = self._ax._share_x
            if group is None:
                group = _Share()
                group.axes.append(self._ax)
                group.limits = self._ax.xlim
                self._ax._share_x = group
            new._share_x = group
            group.axes.append(new)
        if sharey:
            group = self._ax._share_y
            if group is None:
                group = _Share()
                group.axes.append(self._ax)
                group.limits = self._ax.ylim
                self._ax._share_y = group
            new._share_y = group
            group.axes.append(new)

    def add_auto_adjustable_area(self, *args, **kwargs):
        return None


def make_axes_locatable(ax):
    """Return a divider rooted at `ax`."""
    return Divider(ax)


def make_axes_area_auto_adjustable(ax, pad=0.1, use_axes=None, adjust_dirs=None):
    """Compatibility no-op: the renderer already reserves label margins."""
    return None


class HBoxDivider(Divider):
    """Horizontal divider placeholder; layout requests are accepted."""


class VBoxDivider(Divider):
    """Vertical divider placeholder; layout requests are accepted."""
