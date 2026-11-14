"""RGB-channel axes layout used by `axes_grid1`."""

import numpy as np

__all__ = ("RGBAxes", "make_rgb_axes")


def make_rgb_axes(ax, pad=0.02):
    """Resize `ax` and add three narrow R/G/B axes along its right edge."""
    figure = ax.get_figure()
    x, y, width, height = ax.get_position().bounds
    pad = float(pad)
    channel_width = width * 0.2
    main_width = max(width - channel_width - pad, width * 0.45)
    ax.set_position((x, y, main_width, height))
    channel_x = x + main_width + pad
    gap = pad / 2.0
    channel_height = max((height - 2.0 * gap) / 3.0, height * 0.2)
    axes = []
    for index in range(3):
        bottom = y + (2 - index) * (channel_height + gap)
        child = figure.add_axes((channel_x, bottom, channel_width, channel_height))
        child._share_x = ax._share_x
        child._share_y = ax._share_y
        axes.append(child)
    return tuple(axes)


class RGBAxes:
    """A main RGB image axes with three channel axes beside it."""

    def __init__(self, fig, rect, pad=0.0, **kwargs):
        self.figure = fig
        self._ax = fig.add_axes(rect)
        self.axes_r, self.axes_g, self.axes_b = make_rgb_axes(self._ax, pad=pad)

    def __getattr__(self, name):
        return getattr(self._ax, name)

    def imshow_rgb(self, r, g, b, **kwargs):
        r, g, b = (np.asarray(value, dtype=float) for value in (r, g, b))
        rgb = np.dstack((r, g, b))
        images = (
            self.axes_r.imshow(np.dstack((r, np.zeros_like(g), np.zeros_like(b))), **kwargs),
            self.axes_g.imshow(np.dstack((np.zeros_like(r), g, np.zeros_like(b))), **kwargs),
            self.axes_b.imshow(np.dstack((np.zeros_like(r), np.zeros_like(g), b)), **kwargs),
            self._ax.imshow(rgb, **kwargs),
        )
        return images
