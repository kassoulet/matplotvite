"""Axes dividers used by the `axes_grid1` examples.

Dividers calculate figure-fraction rectangles from a list of `axes_size`
objects.  Matplotlib applies the locator at draw time; matplotvite stores the
axis positions immediately because the renderer reads them from `Axes`.
"""

from matplotvite import Axes, _Share

from . import axes_size as Size


def _size_in_fraction(value, base, figure_size):
    if isinstance(value, str):
        value = value.strip()
        if value.endswith("%"):
            return float(value[:-1]) / 100.0 * base
        value = value.rstrip("in")
    inches = float(value)
    return inches / figure_size


def _pad_in_fraction(value, base, figure_size):
    if isinstance(value, str) and value.strip().endswith("%"):
        return float(value.strip()[:-1]) / 100.0 * base
    return float(value) / figure_size


def _subplot_rect(fig, nrows, ncols, index):
    """Approximate Matplotlib's default subplot cell for a 3-digit spec."""
    left, right, bottom, top = 0.125, 0.9, 0.11, 0.88
    wspace, hspace = 0.2, 0.2
    cell_w = (right - left) / (ncols + (ncols - 1) * wspace)
    cell_h = (top - bottom) / (nrows + (nrows - 1) * hspace)
    row, col = divmod(int(index) - 1, ncols)
    x = left + col * cell_w * (1.0 + wspace)
    y = bottom + (nrows - 1 - row) * cell_h * (1.0 + hspace)
    return x, y, cell_w, cell_h


class _Locator:
    """One rectangle in a divider's size grid."""

    def __init__(self, divider, nx, ny, nx1, ny1):
        self.divider = divider
        self.nx, self.ny = int(nx), int(ny)
        self.nx1 = self.nx if nx1 is None else int(nx1)
        self.ny1 = self.ny if ny1 is None else int(ny1)
        self.axes = None

    def __call__(self, ax):
        return self.apply(ax)

    def apply(self, ax):
        self.axes = ax
        if self not in self.divider._locators:
            self.divider._locators.append(self)
        self.divider._layout()
        return self

    def get_position(self, ax=None):
        if ax is not None:
            self.apply(ax)
        return self.divider._rect_for(self)


class Divider:
    """Place axes from horizontal and vertical size lists."""

    def __init__(self, ax_or_fig, rect=None, horizontal=None, vertical=None,
                 aspect=False, anchor="C", **kwargs):
        if isinstance(ax_or_fig, Axes) and rect is None:
            self._ax = ax_or_fig
            self._fig = ax_or_fig._fig
            self._mode = "append"
            return
        self._ax = None
        self._mode = "grid"
        self._fig = ax_or_fig
        if rect is None:
            rect = (0.0, 0.0, 1.0, 1.0)
        elif isinstance(rect, int):
            digits = [int(v) for v in str(rect)]
            if len(digits) == 3:
                rect = _subplot_rect(self._fig, *digits)
            else:
                raise ValueError(f"unsupported subplot spec: {rect!r}")
        self._rect = tuple(float(v) for v in rect)
        self._horizontal = list(horizontal or ())
        self._vertical = list(vertical or ())
        self._aspect = bool(aspect)
        self._locators = []

    # -- locatable-axes API -------------------------------------------------
    def append_axes(self, position, size, pad=0.1, sharex=None, sharey=None,
                    axes_class=None, **kwargs):
        if self._fig is None:
            raise RuntimeError("append_axes needs an axes attached to a figure")
        x, y, width, height = self._ax.get_position().bounds
        fig_w, fig_h = self._fig.get_size_inches()
        position = str(position).lower()
        if position in ("right", "left"):
            span = _size_in_fraction(size, width, fig_w)
            gap = _pad_in_fraction(pad, width, fig_w)
            if position == "right":
                rect = (x + width + gap, y, span, height)
            else:
                rect = (x - gap - span, y, span, height)
        elif position in ("top", "bottom"):
            span = _size_in_fraction(size, height, fig_h)
            gap = _pad_in_fraction(pad, height, fig_h)
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

    # -- grid-divider API ---------------------------------------------------
    def new_locator(self, nx=0, ny=0, nx1=None, ny1=None):
        locator = _Locator(self, nx, ny, nx1, ny1)
        self._locators.append(locator)
        return locator

    def set_horizontal(self, sizes):
        self._horizontal = list(sizes)
        self._layout()

    def set_vertical(self, sizes):
        self._vertical = list(sizes)
        self._layout()

    def set_aspect(self, aspect):
        self._aspect = bool(aspect)
        self._layout()

    def get_aspect(self):
        return self._aspect

    def get_position(self):
        return self._rect

    def _resolve(self, sizes, available):
        if not sizes:
            return [available]
        values = []
        scaled = []
        for index, size in enumerate(sizes):
            if isinstance(size, Size.Scaled):
                values.append(None)
                scaled.append(index)
            elif isinstance(size, Size.Fraction):
                values.append(size.get_size() * available)
            else:
                values.append(float(size.get_size()))
        base = sum(v for v in values if v is not None)
        remaining = max(available - base, 0.0)
        weight = sum(float(sizes[i].get_size()) for i in scaled)
        for index in scaled:
            values[index] = remaining * float(sizes[index].get_size()) / weight if weight else 0.0
        total = sum(values)
        if total > available > 0:
            values = [v * available / total for v in values]
        return values

    def _layout(self):
        if self._mode != "grid" or not self._locators:
            return
        fig_w, fig_h = (float(v) for v in self._fig.get_size_inches())
        avail_w, avail_h = self._rect[2] * fig_w, self._rect[3] * fig_h
        widths = self._resolve(self._horizontal, avail_w)
        heights = self._resolve(self._vertical, avail_h)
        total_w, total_h = sum(widths), sum(heights)
        if total_w <= 0 or total_h <= 0:
            return
        for locator in self._locators:
            if locator.axes is None:
                continue
            x0 = self._rect[0] + self._rect[2] * sum(widths[:locator.nx]) / total_w
            x1 = self._rect[0] + self._rect[2] * sum(widths[:locator.nx1 + 1]) / total_w
            y0 = self._rect[1] + self._rect[3] * sum(heights[:locator.ny]) / total_h
            y1 = self._rect[1] + self._rect[3] * sum(heights[:locator.ny1 + 1]) / total_h
            locator.axes.set_position((x0, y0, x1 - x0, y1 - y0))

    def _rect_for(self, locator):
        ax = locator.axes
        return ax.get_position().bounds if ax is not None else self._rect


def _data_ratio(ax):
    x0, x1 = sorted(float(v) for v in ax.get_xlim())
    y0, y1 = sorted(float(v) for v in ax.get_ylim())
    if y1 == y0 or x1 == x0:
        return 1.0
    return abs((x1 - x0) / (y1 - y0))


def _area(divider):
    return divider._rect


class HBoxDivider(Divider):
    """Arrange axes in a row with equal heights and their data aspect."""

    def _layout(self):
        if self._mode != "grid" or not self._locators:
            return
        axes = [loc.axes for loc in self._locators if loc.axes is not None]
        if not axes:
            return
        x, y, w, h = _area(self)
        fixed = sum(float(s.get_size()) for s in self._horizontal
                    if not isinstance(s, Size.AxesX))
        ratios = [_data_ratio(ax) for ax in axes]
        fig_w, fig_h = (float(v) for v in self._fig.get_size_inches())
        target = (w * fig_w - fixed) / sum(ratios) if sum(ratios) else h * fig_h
        target = min(target, h * fig_h)
        total_w = sum(r * target for r in ratios) + fixed
        left = x + (w - total_w / fig_w) / 2.0
        y0 = y + (h - target / fig_h) / 2.0
        cursor = left
        for index, locator in enumerate(loc for loc in self._locators if loc.axes):
            width = ratios[index] * target
            locator.axes.set_position((cursor, y0, width / fig_w, target / fig_h))
            cursor += width / fig_w
            if index < len(axes):
                pad = [s for s in self._horizontal if not isinstance(s, Size.AxesX)]
                if index < len(pad):
                    cursor += float(pad[index].get_size()) / fig_w


class VBoxDivider(Divider):
    """Arrange axes in a column with equal widths and their data aspect."""

    def _layout(self):
        if self._mode != "grid" or not self._locators:
            return
        axes = [loc.axes for loc in self._locators if loc.axes is not None]
        if not axes:
            return
        x, y, w, h = _area(self)
        fixed = sum(float(s.get_size()) for s in self._vertical
                    if not isinstance(s, Size.AxesY))
        ratios = [_data_ratio(ax) for ax in axes]
        fig_w, fig_h = (float(v) for v in self._fig.get_size_inches())
        target = (w * fig_w)
        total_h = sum(target / r for r in ratios) + fixed
        if total_h > h * fig_h:
            target *= h * fig_h / total_h
            total_h = h * fig_h
        left = x + (w - target / fig_w) / 2.0
        top = y + h - (h - total_h / fig_h) / 2.0
        cursor = top
        pads = [s for s in self._vertical if not isinstance(s, Size.AxesY)]
        for index, locator in enumerate(loc for loc in self._locators if loc.axes):
            height = target / ratios[index]
            cursor -= height / fig_h
            locator.axes.set_position((left, cursor, target / fig_w, height / fig_h))
            if index < len(pads):
                cursor -= float(pads[index].get_size()) / fig_h


class SubplotDivider(Divider):
    """A divider placed on one subplot cell."""

    def __init__(self, fig, nrows, ncols, index, **kwargs):
        super().__init__(fig, _subplot_rect(fig, nrows, ncols, index), **kwargs)


def make_axes_locatable(ax):
    """Return a divider rooted at `ax`."""
    return Divider(ax)


def make_axes_area_auto_adjustable(ax, pad=0.1, use_axes=None, adjust_dirs=None):
    """Compatibility no-op: the renderer already reserves label margins."""
    return None
