"""A compact, dependency-free implementation of `matplotlib.sankey`."""
from __future__ import annotations

import numpy as np

from . import PathPatch, Polygon

_ORIENTATION_ANGLE = {-1: 1, 0: 2, 1: 3}


class Diagram:
    """One system in a Sankey diagram, mirroring `matplotlib.sankey.Diagram`."""

    def __init__(self, sankey, flows, orientations, labels, trunklength,
                 pathlengths, prior, connect):
        self.sankey = sankey
        self.flows = np.asarray(flows, dtype=float)
        n = self.flows.size
        self.angles = [None if flow == 0 else _ORIENTATION_ANGLE.get(int(o), 2)
                       for flow, o in zip(self.flows, orientations)]
        self.labels = list(labels)
        self.trunklength = float(trunklength)
        self.pathlengths = np.asarray(pathlengths, dtype=float)
        self.prior = prior
        self.connect = connect
        self.x = 0.0
        self.y = 0.0
        self.width = max(float(np.sum(self.flows[self.flows > 0])),
                         float(-np.sum(self.flows[self.flows < 0])), 0.1)
        self.tips = np.empty((n, 2), dtype=float)
        self.patch = None
        self.text = None
        self.texts = []
        self.flows_patches = []
        self._bands = []

    def _scale(self, value):
        return float(value) * self.sankey.scale

    def layout(self, x, y):
        self.x, self.y = float(x), float(y)
        half = self._scale(self.width) / 2.0
        pos_cursor = half
        neg_cursor = -half
        for i, flow in enumerate(self.flows):
            value = self._scale(flow)
            if flow > 0:
                start = pos_cursor
                pos_cursor -= value
            elif flow < 0:
                start = neg_cursor
                neg_cursor += abs(value)
            else:
                start = 0.0
            angle = self.angles[i]
            length = self._scale(self.pathlengths[i])
            if angle == 3:
                self.tips[i] = (x + self._scale(self.trunklength) / 2.0,
                                y + half + length)
            elif angle == 1:
                self.tips[i] = (x + self._scale(self.trunklength) / 2.0,
                                y - half - length)
            else:
                if flow == 0:
                    self.tips[i] = (0.0, 0.0)
                    continue
                block = abs(value)
                tip_y = y + start + np.sign(flow) * block / 2.0
                self.tips[i] = (x + self._scale(self.trunklength)
                                + (length if flow >= 0 else -length), tip_y)

    def bands(self):
        """Return the trunk and flow polygons in data coordinates."""
        length = self._scale(self.trunklength)
        half = self._scale(self.width) / 2.0
        x0, y0 = self.x, self.y
        x1 = x0 + length
        trunk = np.array([(x0, y0 - half), (x1, y0 - half),
                          (x1, y0 + half), (x0, y0 + half)])
        bands = [trunk]
        pos_cursor = half
        neg_cursor = -half
        for i, flow in enumerate(self.flows):
            value = self._scale(flow)
            if value == 0:
                continue
            angle = self.angles[i]
            path_len = self._scale(self.pathlengths[i])
            if angle == 2:
                start = pos_cursor if flow > 0 else neg_cursor
                end = start - value if flow > 0 else start - value
                if flow > 0:
                    pos_cursor -= value
                else:
                    neg_cursor += abs(value)
                tip_x = x1 + path_len if flow >= 0 else x0 - path_len
                edge = x1 if flow >= 0 else x0
                bands.append(np.array([(edge, y0 + start), (tip_x, y0 + end),
                                       (tip_x, y0 + end + abs(value)),
                                       (edge, y0 + start + abs(value))]))
            else:
                sign = 1.0 if angle == 3 else -1.0
                if flow > 0:
                    start = pos_cursor
                    pos_cursor -= value
                else:
                    start = neg_cursor
                    neg_cursor += abs(value)
                outer_x = x0 + length / 2.0 + start + abs(value) / 2.0
                inner_x = outer_x - abs(value) / 2.0
                outer = outer_x + abs(value) / 2.0
                edge_y = y0 + sign * half
                tip_y = y0 + sign * (half + path_len)
                bands.append(np.array([(inner_x, edge_y), (outer, edge_y),
                                       (outer, tip_y), (inner_x, tip_y)]))
        return bands


class Sankey:
    """Create Sankey flow diagrams, following matplotlib's public API."""

    def __init__(self, ax=None, scale=1.0, offset=0.15, head_angle=100,
                 tolerance=1e-6, **kwargs):
        gap = kwargs.pop("gap", 0.25)
        radius = kwargs.pop("radius", 0.1)
        if gap < 0:
            raise ValueError("'gap' is negative")
        if radius < 0:
            raise ValueError("'radius' is negative")
        if radius > gap:
            raise ValueError("'radius' is greater than 'gap'")
        if head_angle < 0:
            raise ValueError("'head_angle' is negative")
        if tolerance < 0:
            raise ValueError("'tolerance' is negative")
        self.ax = ax
        self.scale = float(scale)
        self.offset = float(offset)
        self.head_angle = float(head_angle)
        self.tolerance = float(tolerance)
        self.gap = float(gap)
        self.radius = float(radius)
        self.unit = kwargs.pop("unit", "")
        self.format = kwargs.pop("format", None)
        self.diagrams = []
        if "flows" in kwargs:
            self.add(**kwargs)

    def _axes(self):
        if self.ax is None:
            from . import gca
            self.ax = gca()
        return self.ax

    def _value_text(self, flow):
        value = abs(float(flow))
        fmt = self.format
        if callable(fmt):
            text = fmt(value)
        elif isinstance(fmt, str) and "%" in fmt:
            text = fmt % value
        elif fmt is None:
            text = f"{value:g}"
        else:
            text = str(fmt)
        if self.unit:
            text = f"{text} {self.unit}"
        return text

    def add(self, flows=None, orientations=None, labels="", trunklength=1.0,
            pathlengths=0.25, prior=None, connect=(0, 0), rotation=0, **kwargs):
        if flows is None:
            flows = [1]
        flows = np.asarray(flows, dtype=float).reshape(-1)
        n = flows.size
        if trunklength < 0:
            raise ValueError("'trunklength' is negative")
        if orientations is None:
            orientations = np.ones(n, dtype=int)
        elif np.isscalar(orientations):
            orientations = np.full(n, int(orientations))
        else:
            orientations = np.asarray(orientations, dtype=int).reshape(-1)
            if orientations.size == 1:
                orientations = np.full(n, orientations[0])
            if orientations.size != n:
                raise ValueError(
                    f"The shapes of 'flows' {flows.shape} and 'orientations' "
                    f"{orientations.shape} do not match.")
        if np.any(~np.isin(orientations, (-1, 0, 1))):
            raise ValueError("The value of orientations is not 1, 0, or -1.")

        if labels is None:
            labels = [""] * n
        elif isinstance(labels, str):
            labels = [labels] * n
        else:
            labels = list(labels)
            if len(labels) == 1:
                labels = labels * n
        if len(labels) != n:
            raise ValueError(
                f"The shapes of 'flows' {flows.shape} and 'labels' "
                f"{np.asarray(labels).shape} do not match.")

        if np.isscalar(pathlengths):
            pathlengths = np.full(n, float(pathlengths))
        else:
            pathlengths = np.asarray(pathlengths, dtype=float).reshape(-1)
            if pathlengths.size != n:
                raise ValueError("The lengths of 'flows' and 'pathlengths' do not match.")

        if prior is not None:
            if int(prior) < 0:
                raise ValueError("The index of the prior diagram is negative")
            if int(prior) >= len(self.diagrams):
                raise ValueError(f"The index of the prior diagram is {prior}")
            previous = self.diagrams[int(prior)]
            if connect is not None and len(connect) == 2:
                if connect[0] < 0 or connect[1] < 0:
                    raise ValueError("At least one of the connection indices is negative.")
                if connect[0] >= previous.flows.size:
                    raise ValueError("The connection index to the source diagram is out of range.")
                if connect[1] >= n:
                    raise ValueError("The connection index to this diagram is out of range.")
                connected = self.scale * (previous.flows[connect[0]] + flows[connect[1]])
                if abs(connected) > self.tolerance:
                    raise ValueError("The scaled sum of the connected flows is not zero.")
            if connect is not None and (not isinstance(connect, (tuple, list))
                                        or len(connect) != 2):
                raise ValueError("connect must be a (flow, flow) pair")

        diagram = Diagram(self, flows, orientations, labels, trunklength,
                          pathlengths, prior, connect)
        ax = self._axes()
        index = len(self.diagrams)
        x = index * (float(trunklength) * self.scale + self.gap + self.radius + 1.5)
        y = 0.0
        if prior is not None:
            previous = self.diagrams[int(prior)]
            x = previous.x + self.scale * previous.trunklength + self.gap
            y = previous.y
        diagram.layout(x, y)

        patches = diagram.bands()
        patchlabel = kwargs.pop("patchlabel", "")
        trunk = PathPatch(
            [(p[0], p[1]) for p in patches[0]], closed=True,
            facecolor=kwargs.pop("facecolor", kwargs.pop("fc", None)) or ax._next_color(),
            edgecolor=kwargs.pop("edgecolor", kwargs.pop("ec", None)),
            label=kwargs.pop("label", patchlabel),
            **kwargs)
        ax.add_patch(trunk)
        diagram.patch = trunk
        for band in patches[1:]:
            patch = Polygon(band, closed=True, facecolor=trunk.get_facecolor(),
                            edgecolor=trunk.get_edgecolor(), alpha=trunk.get_alpha())
            ax.add_patch(patch)
            diagram.flows_patches.append(patch)
            diagram._bands.append(patch)

        lx = x + self.scale * float(trunklength) / 2.0
        diagram.text = ax.text(lx, y, patchlabel, ha="center", va="center")
        for i, flow in enumerate(flows):
            text = self._value_text(flow) if flow else ""
            if labels[i]:
                text = f"{labels[i]}\n{text}" if text else labels[i]
            dx, dy = diagram.tips[i]
            diagram.texts.append(ax.text(dx, dy, text, ha="center", va="center"))
        self.diagrams.append(diagram)
        return diagram

    def finish(self):
        self._axes()
        try:
            self.ax.autoscale_view()
        except AttributeError:
            pass
        return self.diagrams
