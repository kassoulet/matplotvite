"""Small `axes_grid1.ImageGrid` compatibility layer."""

import numpy as np

from matplotvite import _share_axes


def _subplot_bounds(fig, rect):
    if isinstance(rect, (tuple, list, np.ndarray)):
        if len(rect) != 4:
            raise ValueError("rect must be (left, bottom, width, height)")
        return tuple(float(value) for value in rect)
    if not isinstance(rect, int):
        raise TypeError("rect must be a subplot number or a 4-tuple")
    rows, rest = divmod(rect, 100)
    cols, index = divmod(rest, 10)
    if rows < 1 or cols < 1 or index < 1:
        raise ValueError(f"invalid subplot spec: {rect}")
    row, col = divmod(index - 1, cols)
    gs = fig.add_gridspec(rows, cols)
    return gs._bounds((row, row), (col, col))


class _CbarHandle:
    """Colorbar request attached to an ImageGrid cell.

    Matplotvite draws the bar inside the owning axes' right margin, so no
    separate narrow axes is needed.
    """

    def __init__(self, fig, owner):
        self._fig = fig
        self._owner = owner

    def colorbar(self, mappable=None, **kwargs):
        return self._fig.colorbar(mappable, ax=self._owner, **kwargs)

    def tick_params(self, *args, **kwargs):
        return None

    def set_label(self, *args, **kwargs):
        return None


class ImageGrid:
    """Arrange a fixed grid of axes in one subplot rectangle."""

    def __init__(self, fig, rect, nrows_ncols=(1, 1), axes_pad=0.02,
                 share_all=False, aspect=True, label_mode="L", cbar_mode=None,
                 cbar_location="right", cbar_size="5%", cbar_pad=None,
                 cbar_set_cax=True, direction="row", **kwargs):
        nrows, ncols = (int(value) for value in nrows_ncols)
        if nrows < 1 or ncols < 1:
            raise ValueError("nrows_ncols must be positive")
        pad = axes_pad if isinstance(axes_pad, (tuple, list)) else (axes_pad, axes_pad)
        pad_w, pad_h = (float(value) for value in pad)
        fig_w, fig_h = fig.get_size_inches()
        pad_x = pad_w / fig_w
        pad_y = pad_h / fig_h
        left, bottom, width, height = _subplot_bounds(fig, rect)
        cell_w = (width - pad_x * (ncols - 1)) / ncols
        cell_h = (height - pad_y * (nrows - 1)) / nrows
        if cell_w <= 0 or cell_h <= 0:
            raise ValueError("axes_pad leaves no room for the grid")
        self._axes = []
        for r in range(nrows):
            for c in range(ncols):
                if direction == "column":
                    r, c = c, r
                x = left + c * (cell_w + pad_x)
                y = bottom + (nrows - 1 - r) * (cell_h + pad_y)
                ax = fig.add_axes((x, y, cell_w, cell_h))
                ax.pos = len(self._axes)
                self._axes.append(ax)
                if direction == "column":
                    r, c = c, r
        self.axes_all = self._axes
        self.axes_row = [self._axes[r * ncols:(r + 1) * ncols] for r in range(nrows)]
        self.axes_column = [
            [self._axes[r * ncols + c] for r in range(nrows)] for c in range(ncols)
        ]
        self.axes_llc = self._axes[(nrows - 1) * ncols]
        self.cbar_axes = []
        if cbar_mode in ("single", "each"):
            count = 1 if cbar_mode == "single" else len(self._axes)
            for i in range(count):
                owner = self._axes[min(i, len(self._axes) - 1)]
                handle = _CbarHandle(fig, owner)
                self.cbar_axes.append(handle)
                if cbar_set_cax:
                    if cbar_mode == "single":
                        for ax in self._axes:
                            ax.cax = handle
                    else:
                        owner.cax = handle
        if share_all:
            _share_axes(self._axes, (nrows, ncols), True, True)

    def __len__(self):
        return len(self._axes)

    def __iter__(self):
        return iter(self._axes)

    def __getitem__(self, index):
        if isinstance(index, tuple):
            row, col = index
            return self.axes_row[row][col]
        return self._axes[index]
