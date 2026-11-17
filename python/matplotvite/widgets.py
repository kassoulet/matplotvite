"""Headless selection widgets used by Matplotlib's widget examples.

The widgets draw into a normal axes so the PNG renderer needs no event loop.
Callbacks are accepted for API compatibility; clicks are not simulated.
"""

from __future__ import annotations

import numpy as np

from . import Circle, Rectangle


def _lookup(props, key, index, default=None):
    value = (props or {}).get(key, default)
    if isinstance(value, (list, tuple, np.ndarray)):
        return value[index % len(value)] if len(value) else default
    return value


def _grid(layout, count):
    if layout == "horizontal":
        return 1, max(count, 1)
    if layout is None or layout == "vertical":
        return max(count, 1), 1
    if isinstance(layout, (tuple, list)) and len(layout) == 2:
        return max(int(layout[0]), 1), max(int(layout[1]), 1)
    return max(int(layout), 1), 1


def _cells(layout, count):
    rows, cols = _grid(layout, count)
    for index in range(count):
        row, col = divmod(index, cols)
        x = (col + 0.5) / cols
        y = 1.0 - (row + 0.5) / rows
        yield index, x, y, rows, cols


class RadioButtons:
    """A vertical, horizontal, or gridded radio-button selector."""

    def __init__(self, ax, labels, active=0, layout=None, label_props=None,
                 radio_props=None, **kwargs):
        self.ax = ax
        self.labels = list(labels)
        self.active = int(active or 0)
        self._callbacks = []
        self._circles = []
        self._texts = []
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.set_axis_off()
        for index, x, y, rows, cols in _cells(layout, len(self.labels)):
            radius = min(0.07, 0.32 / max(rows, cols))
            if layout == "horizontal":
                x -= radius
            elif layout not in ("horizontal", None, "vertical"):
                x -= radius
            edge = _lookup(radio_props, "edgecolor", index, "black")
            face = _lookup(radio_props, "facecolor", index, "white")
            self._circles.append(ax.add_patch(Circle(
                (x, y), radius, edgecolor=edge, facecolor=face, linewidth=1.2)))
            if index == self.active:
                ax.add_patch(Circle((x, y), radius * 0.45,
                                    edgecolor=edge, facecolor=edge, linewidth=0))
            colour = _lookup(label_props, "color", index, "black")
            size = _lookup(label_props, "fontsize", index, 10)
            self._texts.append(ax.text(
                x + radius * 2.0, y, self.labels[index], color=colour,
                fontsize=size, ha="left", va="center"))

    def on_clicked(self, func):
        self._callbacks.append(func)
        return len(self._callbacks)

    def disconnect(self, cid):
        return None

    def set_active(self, index):
        self.active = int(index)

    def get_status(self):
        return [index == self.active for index in range(len(self.labels))]

    def set_label_props(self, props):
        self._label_props = props

    def set_radio_props(self, props):
        self._radio_props = props


class CheckButtons:
    """A vertical, horizontal, or gridded multi-select button group."""

    def __init__(self, ax, labels, actives=None, layout=None, label_props=None,
                 frame_props=None, check_props=None, **kwargs):
        self.ax = ax
        self.labels = list(labels)
        self.actives = list(actives) if actives is not None else [False] * len(labels)
        self._callbacks = []
        self._frames = []
        self._checks = []
        self._texts = []
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.set_axis_off()
        for index, x, y, rows, cols in _cells(layout, len(self.labels)):
            size = min(0.16, 0.55 / max(rows, cols))
            if layout == "horizontal":
                x -= size
            elif layout not in ("horizontal", None, "vertical"):
                x -= size
            if index >= len(self.actives):
                self.actives.append(False)
            edge = _lookup(frame_props, "edgecolor", index, "black")
            face = _lookup(frame_props, "facecolor", index, "white")
            self._frames.append(ax.add_patch(Rectangle(
                (x - size / 2.0, y - size / 2.0), size, size,
                edgecolor=edge, facecolor=face, linewidth=1.2)))
            if self.actives[index]:
                colour = _lookup(check_props, "color", index, "black")
                self._checks.append(ax.plot(
                    [x - size * 0.28, x - size * 0.05, x + size * 0.30],
                    [y, y - size * 0.25, y + size * 0.28],
                    color=colour, linewidth=1.6))
            colour = _lookup(label_props, "color", index, "black")
            fontsize = _lookup(label_props, "fontsize", index, 10)
            self._texts.append(ax.text(
                x + size * 0.9, y, self.labels[index], color=colour,
                fontsize=fontsize, ha="left", va="center"))

    def on_clicked(self, func):
        self._callbacks.append(func)
        return len(self._callbacks)

    def disconnect(self, cid):
        return None

    def set_active(self, index):
        if 0 <= int(index) < len(self.actives):
            self.actives[int(index)] = not self.actives[int(index)]

    def get_status(self):
        return list(self.actives)

    def set_label_props(self, props):
        self._label_props = props

    def set_frame_props(self, props):
        self._frame_props = props

    def set_check_props(self, props):
        self._check_props = props


__all__ = ("CheckButtons", "RadioButtons")
