"""plt_rs: minimal matplotlib-like API, rendered entirely in Rust."""
import numpy as np
from ._core import save

_CYCLE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
DPI = 100


class Axes:
    def __init__(self, pos):
        self.pos, self.lines = pos, []
        self.title = self.xlabel = self.ylabel = ""
        self.show_legend, self.xlim, self.ylim = False, None, None

    def plot(self, x, y=None, label="", color=None):
        if y is None:
            x, y = np.arange(len(x)), x
        c = color or _CYCLE[len(self.lines) % len(_CYCLE)]
        self.lines.append((np.ascontiguousarray(x, dtype=np.float64),
                           np.ascontiguousarray(y, dtype=np.float64), label, c))

    def set_title(self, t): self.title = t
    def set_xlabel(self, t): self.xlabel = t
    def set_ylabel(self, t): self.ylabel = t
    def set_xlim(self, lo, hi): self.xlim = (float(lo), float(hi))
    def set_ylim(self, lo, hi): self.ylim = (float(lo), float(hi))
    def legend(self): self.show_legend = True

    def _panel(self):
        return dict(pos=self.pos, series=self.lines, title=self.title, xlabel=self.xlabel,
                    ylabel=self.ylabel, legend=self.show_legend, xlim=self.xlim, ylim=self.ylim)


class Figure:
    def __init__(self, figsize=(6.4, 4.8)):
        self.figsize, self.grid, self.axes, self._cur = figsize, (1, 1), [], None

    def add_subplot(self, nrows=1, ncols=1, index=1):
        """index is 1-based, row-major (matplotlib convention)."""
        if (nrows, ncols) != self.grid:
            if self.axes:
                raise ValueError("mixed subplot grids are not supported yet")
            self.grid = (nrows, ncols)
        ax = next((a for a in self.axes if a.pos == index - 1), None) or Axes(index - 1)
        if ax not in self.axes:
            self.axes.append(ax)
        self._cur = ax
        return ax

    def subplots(self, nrows=1, ncols=1):
        axs = [self.add_subplot(nrows, ncols, i + 1) for i in range(nrows * ncols)]
        return axs[0] if len(axs) == 1 else np.array(axs, dtype=object).reshape(nrows, ncols).squeeze()

    def gca(self):
        return self._cur or self.add_subplot()

    def savefig(self, filepath):
        w, h = (round(v * DPI) for v in self.figsize)
        save(str(filepath), (w, h), self.grid, [a._panel() for a in self.axes])


_fig = None


def figure(figsize=(6.4, 4.8)):
    global _fig
    _fig = Figure(figsize)
    return _fig


def gcf(): return _fig or figure()
def gca(): return gcf().gca()
def close(*_): global _fig; _fig = None


def subplots(nrows=1, ncols=1, figsize=(6.4, 4.8)):
    fig = figure(figsize)
    return fig, fig.subplots(nrows, ncols)


def subplot(nrows, ncols, index): return gcf().add_subplot(nrows, ncols, index)
def plot(x, y=None, label="", color=None): gca().plot(x, y, label, color)
def xlabel(text): gca().set_xlabel(text)
def ylabel(text): gca().set_ylabel(text)
def title(text): gca().set_title(text)
def xlim(lo, hi): gca().set_xlim(lo, hi)
def ylim(lo, hi): gca().set_ylim(lo, hi)
def legend(): gca().legend()
def savefig(filepath): gcf().savefig(filepath)
