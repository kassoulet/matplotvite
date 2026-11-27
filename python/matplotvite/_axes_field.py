"""Axes mixin for images, contours, quiver and hexbin."""
import math as _math
from typing import TYPE_CHECKING

import numpy as np

from ._artists import Collection, FancyArrow, LineCollection
from ._axes_plot import _AxesMixinBase
from ._containers import _HexbinHandle, _number, _QuiverHandle, _StreamplotSet
from ._core import (
    LogNorm as _LogNorm,
)
from ._helpers import (
    _IMAGE_KWARGS,
    _MAX_BIN_CELLS,
    Table,
    _check_kwargs,
    _cmap_name,
    _looks_like_dates,
    _norm_color,
    _validate_bins,
    get_cmap,
)


class _FieldAxes(_AxesMixinBase):
    """Gridded and vector fields: images, contours, quiver and hexbin."""

    def clabel(self, *args, **kwargs):
        if args and hasattr(args[0], "clabel"):
            return args[0].clabel(*args[1:], **kwargs)
        return []

    def table(self, cellText=None, cellColours=None, **kwargs):
        """Add a table to the Axes, as `Axes.table`."""
        return Table(self, cellText=cellText, cellColours=cellColours, **kwargs)

    def spy(self, Z, precision=0, marker=None, markersize=None,
            aspect="equal", origin="upper", **kwargs):
        """Plot the sparsity pattern of an array."""
        data = np.asarray(Z)
        if precision == "present":
            mask = np.isfinite(data)
        elif precision in (None, 0):
            mask = data != 0
        else:
            mask = np.abs(data) > float(precision)
        image = self.imshow(
            mask.astype(float), cmap="binary_r", interpolation="nearest",
            aspect=aspect, origin=origin, **kwargs)
        self.set_xticks([])
        self.set_yticks([])
        return image

    def imshow(self, X, cmap=None, vmin=None, vmax=None, extent=None, origin="upper",
               interpolation=None, aspect=None, alpha=None, clim=None, norm=None,
               colorizer=None, **kwargs):
        """Draw an array as an image. `X` is 2-D (mapped through `cmap`) or
        (H, W, 3|4) RGB(A) floats in 0-1. `interpolation` accepts `none`,
        `nearest`, `antialiased`, `bilinear` or `bicubic`; `alpha` scales the
        image's opacity. When omitted, `rcParams["image.interpolation"]`
        supplies the default. `clim` and Matplotlib's extra artist kwargs are
        accepted."""
        _check_kwargs(kwargs, "imshow", _IMAGE_KWARGS)
        if clim is not None:
            vmin, vmax = clim
        if colorizer is not None:
            cmap = colorizer.cmap if colorizer.cmap is not None else cmap
            if colorizer.norm is not None:
                vmin = getattr(colorizer.norm, "vmin", vmin)
                vmax = getattr(colorizer.norm, "vmax", vmax)
        setting = (rcParams.get("image.interpolation", "nearest")
                   if interpolation is None else interpolation)
        interp = str(setting).lower()
        interp = {
            "spline16": "bicubic", "spline36": "bicubic", "hanning": "bilinear",
            "hamming": "bilinear", "hermite": "bicubic", "kaiser": "bicubic",
            "quadric": "bicubic", "catrom": "bicubic", "gaussian": "bicubic",
            "lanczos": "bicubic", "blackman": "bilinear", "sinc": "bicubic",
            "bessel": "bicubic", "mitchell": "bicubic",
        }.get(interp, interp)
        a = _as_image(X)
        if isinstance(norm, str):
            # Matplotlib accepts "log" as shorthand for a LogNorm; map it before
            # the normalisation pass, which expects an object with vmin/vmax.
            kind = norm.lower()
            if kind == "log":
                positive = a[np.isfinite(a) & (a > 0.0)] if a.ndim == 2 else np.empty(0)
                lo = vmin if vmin is not None else (
                    float(positive.min()) if positive.size else 1.0)
                hi = vmax if vmax is not None else (
                    float(positive.max()) if positive.size else float(lo) * 10.0)
                if not float(hi) > float(lo):
                    hi = float(lo) * 10.0
                norm = _LogNorm(vmin=lo, vmax=hi)
            elif kind in ("linear", "none", ""):
                norm = None
            else:
                raise NotImplementedError(f"norm={norm!r} is not supported yet")
        if norm is not None and a.ndim == 2:
            a, vmin, vmax = _norm_values(norm, a)
        h, w = a.shape[:2]
        if origin == "lower":
            a = a[::-1]
        elif origin != "upper":
            raise ValueError(f"unsupported origin: {origin!r}")
        if extent is None:
            # Matplotlib centres pixels on integer data coordinates. An upper
            # origin puts row 0 at the top, which requires a descending y axis.
            extent = (-0.5, float(w) - 0.5, -0.5, float(h) - 0.5)
            self._inverted[1] = origin == "upper"
            if origin == "upper":
                extent = (extent[0], extent[1], extent[3], extent[2])
        elif len(extent) != 4:
            raise ValueError("extent must be (left, right, bottom, top)")
        elif extent[2] > extent[3]:
            self._inverted[1] = True  # bottom > top reads as a descending y axis
        alpha_data = None
        if alpha is not None and np.ndim(alpha) > 0:
            alpha_data = np.asarray(alpha, dtype=np.float64)
            opacity = 1.0
        else:
            opacity = 1.0 if alpha is None else float(alpha)
        if alpha_data is not None:
            alpha_data = np.broadcast_to(alpha_data, a.shape[:2])
            if a.ndim == 2:
                lo = vmin if vmin is not None else float(np.nanmin(a))
                hi = vmax if vmax is not None else float(np.nanmax(a))
                span = hi - lo
                normalized = (np.zeros_like(a) if span == 0.0
                              else np.clip((a - lo) / span, 0.0, 1.0))
                a = np.dstack([get_cmap(cmap)(normalized)[..., :3], alpha_data])
            elif a.shape[2] == 3:
                a = np.dstack([a, alpha_data])
            else:
                a = a.copy()
                a[..., 3] *= alpha_data
        if interp == "auto":
            interp = "antialiased"
        if interp not in ("none", "nearest", "antialiased", "bilinear", "bicubic"):
            raise ValueError(f"unsupported interpolation: {setting!r}")
        if not np.isfinite(opacity):
            raise ValueError("alpha must be finite")
        entry = dict(data=a, cmap=_cmap_name(cmap), vmin=vmin, vmax=vmax,
                     extent=tuple(float(v) for v in extent),
                     alpha=float(np.clip(opacity, 0.0, 1.0)), interpolation=interp)
        image = AxesImage(entry, self)
        self.images.append(image)
        # matplotlib's image.aspect default is "equal".
        self.set_aspect("equal" if aspect is None else aspect)
        return image

    def pcolormesh(self, *args, cmap=None, vmin=None, vmax=None, shading="auto",
                   alpha=None, norm=None, **kwargs):
        """Quad mesh: each Z cell is filled through `cmap` via the image path.

        `X`/`Y` may be cell edges (one longer than Z's axis) or cell centres.
        """
        if len(args) == 3 and _looks_like_dates(args[0]):
            args = (self._xdate(args[0]), args[1], args[2])
        x, y, z, edges = _mesh_args(args)
        if edges:
            extent = (float(x[0]), float(x[-1]), float(y[0]), float(y[-1]))
        else:
            dx = float(x[1] - x[0]) if x.size > 1 else 1.0
            dy = float(y[1] - y[0]) if y.size > 1 else 1.0
            extent = (float(x[0]) - dx / 2, float(x[-1]) + dx / 2,
                      float(y[0]) - dy / 2, float(y[-1]) + dy / 2)
        return self.imshow(z, cmap=_cmap_name(cmap), vmin=vmin, vmax=vmax,
                           extent=extent, origin="lower", alpha=alpha, norm=norm)

    def pcolor(self, *args, **kwargs):
        return self.pcolormesh(*args, **kwargs)

    def pcolorfast(self, *args, **kwargs):
        return self.pcolormesh(*args, **kwargs)

    def hist2d(self, x, y, bins=10, range=None, density=False, weights=None,
               cmin=None, cmax=None, cmap=None, data=None, **kwargs):
        """2-D histogram rasterised through `imshow`; returns
        `(counts, xedges, yedges, image)`."""
        if data is not None:
            x = data[x] if isinstance(x, str) else x
            y = data[y] if isinstance(y, str) else y
        x = _as_f64(x)
        y = _as_f64(y)
        _check_same_length(x, y)
        bins = _validate_bins(bins, max_cells=_MAX_BIN_CELLS)
        counts, xedges, yedges = np.histogram2d(
            x, y, bins=bins, range=range, density=bool(density), weights=weights)
        image = self.imshow(counts.T, cmap=_cmap_name(cmap), vmin=cmin, vmax=cmax,
                            extent=(float(xedges[0]), float(xedges[-1]),
                                    float(yedges[0]), float(yedges[-1])),
                            origin="lower")
        self.set_aspect("auto")
        return counts, xedges, yedges, image

    def hexbin(self, x, y, C=None, gridsize=100, bins=None, xscale="linear",
               yscale="linear", extent=None, cmap=None, norm=None, vmin=None,
               vmax=None, alpha=None, linewidths=None, edgecolors="face",
               reduce_C_function=None, mincnt=None, marginals=False, data=None, **kwargs):
        """Hexagonal binning: one coloured hexagon per occupied grid cell."""
        if data is not None:
            x = data[x] if isinstance(x, str) else x
            y = data[y] if isinstance(y, str) else y
            C = data[C] if isinstance(C, str) else C
        x = _as_f64(x)
        y = _as_f64(y)
        _check_same_length(x, y)
        if x.size == 0:
            handle = Collection(colors=[])
            self.add_collection(handle)
            return handle
        nx, ny, ex0, ex1, ey0, ey1 = _hexbin_grid(gridsize, extent, x, y)
        centers, cell, valid, total, sx, sy = _hexbin_cells(
            x, y, nx, ny, ex0, ex1, ey0, ey1)
        counts = np.bincount(cell, minlength=total).astype(np.float64)
        if C is None:
            values = counts.copy()
        else:
            weights = _as_f64(C)
            if weights.size != x.size:
                raise ValueError("C must have one value per point")
            sums = np.bincount(cell, weights=weights[valid], minlength=total)
            values = np.divide(sums, counts, out=np.zeros(total), where=counts > 0)
        if mincnt is None:
            keep = np.ones(total, dtype=bool)
        else:
            keep = counts >= float(mincnt)
        if not keep.any():
            keep = counts > 0
        shown = np.flatnonzero(keep)
        if vmin is None:
            vmin = float(values[shown].min())
        if vmax is None:
            vmax = float(values[shown].max())
        if not vmax > vmin:
            vmax = vmin + 1.0
        t = np.clip((values[shown] - float(vmin)) / (float(vmax) - float(vmin)), 0.0, 1.0)
        cmap = _cmap_name(cmap)
        colors = _cmap_colors(cmap, t)
        polygon = np.array([
            [0.5, -0.5], [0.5, 0.5], [0.0, 1.0],
            [-0.5, 0.5], [-0.5, -0.5], [0.0, -1.0],
        ])
        # Build every hexagon in one array and keep the cells in a single band:
        # one dict per cell dominates hexbin's Python time and cache-key hashing.
        sel = centers[shown]
        xs = (sel[:, 0:1] + sx * polygon[:, 0]).ravel()
        ys = (sel[:, 1:2] + (sy / 3.0) * polygon[:, 1]).ravel()
        self._append_band(dict(
            x=np.ascontiguousarray(xs), y=np.ascontiguousarray(ys),
            color="#000000", alpha=None if alpha is None else float(alpha), label="",
            cells=int(shown.size),
            cell_colors="".join(c[1:] for c in colors), gid="",
        ))
        self._sticky_x += [ex0, ex1]
        self._sticky_y += [ey0, ey1]
        return _HexbinHandle(values[shown], centers[shown], colors, cmap)

    def streamplot(self, x, y, u, v, density=1, linewidth=None, color=None,
                   cmap=None, norm=None, arrowsize=1, arrowstyle="-|>",
                   minlength=0.1, maxlength=4.0, integration_direction="both",
                   broken_streamlines=True, start_points=None, num_arrows=1,
                   integration_max_step_scale=1.0,
                   integration_max_error_scale=1.0, **kwargs):
        """Draw streamlines for a 2-D vector field.

        This is a compact integrator: it seeds a regular grid (or the supplied
        `start_points`), integrates the normalised field with a midpoint step,
        and draws each streamline as a segment collection so colour can vary
        along the path.
        """
        _streamplot_check(integration_direction, integration_max_step_scale,
                          integration_max_error_scale)
        xs, ys, uu, vv, mask = _streamplot_field(x, y, u, v)
        x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
        dx = abs(xs[1] - xs[0]) if xs.size > 1 else 1.0
        dy = abs(ys[1] - ys[0]) if ys.size > 1 else 1.0
        step = 0.5 * min(dx, dy)
        max_distance = float(maxlength) * max(x1 - x0, y1 - y0, 1.0)
        max_steps = min(600, max(10, int(np.ceil(max_distance / max(step, 1e-12)))))

        seeds = _streamplot_seeds(density, start_points, xs, ys, x0, x1, y0, y1)
        trajectories = _streamplot_trajectories(
            xs, ys, uu, vv, mask, seeds, integration_direction, step,
            max_steps, max_distance, x0, x1, y0, y1)

        color_values = None
        if color is not None and not isinstance(color, str):
            candidate = np.asarray(color)
            if candidate.shape == uu.shape and candidate.dtype.kind in "iuf":
                color_values = np.asarray(candidate, dtype=float)
        if color_values is not None:
            vals = color_values[np.isfinite(color_values)]
            lo = float(vals.min()) if vals.size else 0.0
            hi = float(vals.max()) if vals.size else 1.0
            if not hi > lo:
                lo, hi = lo - 0.5, lo + 0.5
            cmap_obj = get_cmap(cmap)
            color_at = lambda px, py: cmap_obj((_streamplot_sample(color_values, xs, ys, px, py) - lo) / (hi - lo))
        else:
            uniform = _norm_color(color) if color is not None else self._next_color()
            color_at = lambda px, py: uniform

        linewidth_values = None
        if linewidth is not None and not np.isscalar(linewidth):
            candidate = np.asarray(linewidth, dtype=float)
            if candidate.shape == uu.shape:
                linewidth_values = candidate
        if linewidth_values is not None:
            widths = linewidth_values[np.isfinite(linewidth_values)]
            line_width = float(widths.mean()) if widths.size else 2.0
        else:
            line_width = 2.0 if linewidth is None else float(linewidth)

        segments, colors, shown_values = _streamplot_segments(
            trajectories, color_at, dx, dy, num_arrows, arrowsize,
            color_values, xs, ys)
        lines = LineCollection(segments, colors=colors, linewidths=line_width,
                               label=kwargs.get("label", ""))
        lines.axes = self  # type: ignore[attr-defined]
        lines._array = np.asarray(shown_values) if shown_values else None
        lines._cmap = _cmap_name(cmap) if color_values is not None else None
        if color_values is not None:
            vals = color_values[np.isfinite(color_values)]
            lines._clim = ((float(vals.min()), float(vals.max()))
                           if vals.size else None)
        self.add_collection(lines)
        arrows = Collection(colors=[])
        return _StreamplotSet(lines, arrows)

    def quiver(self, *args, U=None, V=None, C=None, color=None, angles="xy",
               scale=None, scale_units=None, units="width", width=None,
               headwidth=3.0, headlength=5.0, headaxislength=4.5, pivot="tail",
               **kwargs):
        """Vector field arrows from `quiver(U, V)` or `quiver(X, Y, U, V)`.

        `scale` and `units` set the arrow length from the finished axes box, as
        in Matplotlib; `pivot` places the arrow at its tail, middle or tip."""
        if len(args) == 2:
            ua = np.asarray(args[0], dtype=np.float64)
            va = np.asarray(args[1], dtype=np.float64)
            if ua.shape != va.shape:
                raise ValueError("U and V must have the same shape")
            if ua.ndim == 2:
                rows, cols = ua.shape
                gx, gy = np.meshgrid(np.arange(cols, dtype=float),
                                     np.arange(rows, dtype=float))
                x, y = gx.ravel(), gy.ravel()
            else:
                x = np.arange(ua.size, dtype=float)
                y = np.zeros(ua.size)
            u, v = ua.ravel(), va.ravel()
        elif len(args) >= 4:
            xa = np.asarray(self._xdate(args[0]), dtype=np.float64)
            ya = np.asarray(args[1], dtype=np.float64)
            ua = np.asarray(args[2], dtype=np.float64)
            va = np.asarray(args[3], dtype=np.float64)
            if ua.shape != va.shape:
                raise ValueError("U and V must have the same shape")
            if ua.ndim == 2:
                if (xa.ndim == 1 and ya.ndim == 1
                        and xa.size == ua.shape[1] and ya.size == ua.shape[0]):
                    xa, ya = np.meshgrid(xa, ya)
                elif xa.shape != ua.shape or ya.shape != va.shape:
                    raise ValueError("X and Y must match U's shape or one axis each")
                x, y = xa.ravel(), ya.ravel()
            else:
                x, y = xa.ravel(), ya.ravel()
            u, v = ua.ravel(), va.ravel()
            if len(args) >= 5 and C is None:
                C = args[4]
        elif len(args) == 0 and U is not None and V is not None:
            ua = np.asarray(U, dtype=np.float64)
            va = np.asarray(V, dtype=np.float64)
            if ua.shape != va.shape:
                raise ValueError("U and V must have the same shape")
            if ua.ndim == 2:
                rows, cols = ua.shape
                x, y = np.meshgrid(np.arange(cols, dtype=float),
                                   np.arange(rows, dtype=float))
                x, y = x.ravel(), y.ravel()
            else:
                x = np.arange(ua.size, dtype=float)
                y = np.zeros(ua.size)
            u, v = ua.ravel(), va.ravel()
        else:
            raise TypeError("quiver expects U, V or X, Y, U, V")
        if not (x.size == y.size == u.size == v.size):
            raise ValueError("X, Y, U and V must have the same length")
        if x.size == 0:
            raise ValueError("quiver needs at least one vector")
        if angles not in ("xy", "uv"):
            raise ValueError(f"unsupported angles: {angles!r}")
        if pivot not in ("tail", "middle", "mid", "tip"):
            raise ValueError(f"unsupported pivot: {pivot!r}")
        supported_units = ("width", "height", "dots", "inches", "x", "y", "xy")
        if units not in supported_units:
            raise ValueError(f"unsupported units: {units!r}")
        if scale_units is not None and scale_units not in supported_units:
            raise ValueError(f"unsupported scale_units: {scale_units!r}")
        if isinstance(scale, str):
            if scale != "auto":
                raise ValueError(f"unsupported scale: {scale!r}")
            scale = None
        if scale is not None:
            scale = float(scale)
            if scale == 0.0:
                raise ValueError("scale must not be zero")
        # Matplotlib sizes arrows from the axes box, so keep U/V in data units
        # and hand `scale`/`units` to the renderer.
        colors = (_line_colors(color, x.size) if color is not None
                  else [self._next_color()])
        entry = dict(x=np.ascontiguousarray(x), y=np.ascontiguousarray(y),
                     u=np.ascontiguousarray(u), v=np.ascontiguousarray(v),
                     colors=colors,
                     scale=scale, units=str(units),
                     scale_units=None if scale_units is None else str(scale_units),
                     angles=str(angles),
                     width=None if width is None else _number(width, 0.005),
                     headwidth=_number(headwidth, 3.0),
                     headlength=_number(headlength, 5.0),
                     headaxislength=_number(headaxislength, 4.5),
                     pivot="middle" if pivot == "mid" else str(pivot))
        self.arrows.append(entry)
        return _QuiverHandle(entry)

    def quiverkey(self, Q, X, Y, U, label, *, angle=0.0, coordinates="axes",
                  color=None, labelsep=0.1, labelpos="E", fontproperties=None,
                  **kwargs):
        """Draw a labelled reference arrow for a quiver, as `Axes.quiverkey`.

        `(X, Y)` and `U` follow Matplotlib's axes-fraction placement and arrow
        scaling; `labelpos` places the label to the east, west, north or south
        of the arrow. `fontproperties` and artist kwargs are accepted and
        ignored.
        """
        entry = getattr(Q, "_e", None)
        if entry is None:
            raise TypeError("quiverkey needs the handle returned by quiver")
        if coordinates != "axes":
            raise ValueError(f"unsupported quiverkey coordinates: {coordinates!r}")
        if labelpos not in ("E", "W", "N", "S"):
            raise ValueError(f"unsupported quiverkey labelpos: {labelpos!r}")
        xlo, xhi = self.get_xlim()
        ylo, yhi = self.get_ylim()
        span_x = xhi - xlo
        if span_x == 0.0:
            return None
        scale = entry.get("scale")
        if scale is None:
            mags = np.hypot(entry["u"], entry["v"])
            mean = float(mags.mean()) if mags.size else 0.0
            sn = min(max(_math.sqrt(mags.size), 8.0), 25.0)
            scale = 1.8 * mean * sn if mean > 0.0 else 1.0
        length = float(U) * span_x / float(scale)
        theta = _math.radians(float(angle))
        x0 = xlo + float(X) * span_x
        y0 = ylo + float(Y) * (yhi - ylo)
        y_ratio = (yhi - ylo) / span_x
        dx = length * _math.cos(theta)
        dy = length * _math.sin(theta) * y_ratio
        arrow_color = _norm_color(color) if color is not None else entry["colors"][0]
        width = 0.01 * abs(length) * abs(y_ratio)
        patch = FancyArrow(x0, y0, dx, dy, width=width,
                           head_width=3.0 * width, head_length=3.0 * width,
                           facecolor=arrow_color, edgecolor=arrow_color)
        self.add_patch(patch)
        gap = float(labelsep) * abs(length)
        if labelpos == "E":
            tx, ty, ha, va = x0 + dx + gap, y0 + dy, "left", "center"
        elif labelpos == "W":
            tx, ty, ha, va = x0 - gap, y0, "right", "center"
        elif labelpos == "N":
            tx, ty, ha, va = (x0 + 0.5 * dx, y0 + dy + gap * abs(y_ratio),
                              "center", "bottom")
        else:
            tx, ty, ha, va = (x0 + 0.5 * dx, y0 - gap * abs(y_ratio),
                              "center", "top")
        self.text(tx, ty, label, ha=ha, va=va, color=arrow_color)
        return None

    def contour(self, *args, levels=None, colors=None, cmap=None, linewidths=None,
                alpha=None, locator=None, **kwargs):
        """Iso-lines of a 2-D array: `contour(Z)` or `contour(X, Y, Z)`, optionally
        followed by `levels`. Matplotlib contour kwargs are accepted."""
        return self._add_contour(args, levels, colors, cmap, False, linewidths,
                                 alpha, locator)

    def contourf(self, *args, levels=None, colors=None, cmap=None, linewidths=None,
                 alpha=None, locator=None, **kwargs):
        """Filled iso-bands of a 2-D array; takes the same forms as `contour`."""
        return self._add_contour(args, levels, colors, cmap, True, linewidths,
                                 alpha, locator)

    def triplot(self, *args, **kwargs):
        """Draw the edges of an unstructured triangular grid.

        Accepts `triplot(triangulation, fmt, ...)` or `triplot(x, y, triangles,
        fmt, ...)`; a missing triangle array asks for a Delaunay triangulation.
        """
        triangulation, _, rest = _tri_args(args)
        fmt = rest[0] if rest and isinstance(rest[0], str) else None
        edges = triangulation.get_masked_triangles()
        if len(edges) == 0:
            return []
        ex, ey = [], []  # type: ignore[var-annotated]
        for a, b, c in edges:
            for i, j in ((a, b), (b, c), (c, a)):
                ex.extend((triangulation.x[i], triangulation.x[j], np.nan))
                ey.extend((triangulation.y[i], triangulation.y[j], np.nan))
        color = kwargs.pop("color", kwargs.pop("c", None))
        return self.plot(np.asarray(ex), np.asarray(ey), fmt or "-",
                         color=color, **kwargs)

    def tricontour(self, *args, levels=None, colors=None, cmap=None,
                   linewidths=None, alpha=None, **kwargs):
        """Iso-lines of data on an unstructured triangular grid."""
        triangulation, z, rest = _tri_args(args)
        if levels is None and rest:
            levels = rest[0]
        xi, yi, zi = _tri_field(triangulation, z)
        return self.contour(xi, yi, zi, levels=levels, colors=colors, cmap=cmap,
                            linewidths=linewidths, alpha=alpha, **kwargs)

    def tricontourf(self, *args, levels=None, colors=None, cmap=None,
                    linewidths=None, alpha=None, **kwargs):
        """Filled iso-bands of data on an unstructured triangular grid."""
        triangulation, z, rest = _tri_args(args)
        if levels is None and rest:
            levels = rest[0]
        xi, yi, zi = _tri_field(triangulation, z)
        return self.contourf(xi, yi, zi, levels=levels, colors=colors, cmap=cmap,
                             linewidths=linewidths, alpha=alpha, **kwargs)

    def tripcolor(self, *args, shading="flat", facecolors=None, edgecolors=None,
                  cmap=None, vmin=None, vmax=None, alpha=None, **kwargs):
        """Pseudocolour of an unstructured triangular grid."""
        triangulation, z, _ = _tri_args(args)
        if z is None and facecolors is not None:
            values = _as_f64(facecolors)
            totals = np.zeros(len(triangulation.x))
            counts = np.zeros(len(triangulation.x))
            for tri, value in zip(triangulation.get_masked_triangles(), values):
                totals[tri] += value
                counts[tri] += 1
            z = np.divide(totals, counts, out=np.full_like(totals, np.nan),
                          where=counts > 0)
        if z is None:
            raise TypeError("tripcolor expects z or facecolors")
        xi, yi, zi = _tri_field(triangulation, z, resolution=140)
        image = self.pcolormesh(xi, yi, zi, cmap=cmap, vmin=vmin, vmax=vmax,
                                shading=shading, alpha=alpha, **kwargs)
        if edgecolors is not None:
            self.triplot(triangulation, color=edgecolors)
        return image

    def _add_contour(self, args, levels, colors, cmap, filled, linewidths=None,
                     alpha=None, locator=None):
        x, y, z, levels = _contour_args(args, levels)
        levels = _levels(z, levels, allow_single=not filled, locator=locator)
        if linewidths is None:
            widths = []
        elif np.isscalar(linewidths):
            widths = [float(linewidths)]
        else:
            widths = [float(v) for v in _as_f64(linewidths)]
        if widths and len(widths) not in (1, len(levels)):
            # Matplotlib cycles the sequence across levels.
            widths = [widths[i % len(widths)] for i in range(len(levels))]
        opacity = 1.0 if alpha is None else float(alpha)
        if not np.isfinite(opacity):
            raise ValueError("alpha must be finite")
        entry = dict(x=x, y=y, z=z, levels=levels, linewidths=widths,
                     colors=_colors(colors), cmap=_cmap_name(cmap), filled=filled,
                     alpha=float(np.clip(opacity, 0.0, 1.0)))
        self.contours.append(entry)
        return ContourSet(entry, axes=self)


def _hexbin_grid(gridsize, extent, x, y):
    """Validated `(nx, ny, ex0, ex1, ey0, ey1)` of one hexbin call."""
    gridsize = _validate_bins(gridsize, name="gridsize")
    if isinstance(gridsize, (tuple, list, np.ndarray)):
        nx, ny = (max(int(v), 1) for v in np.asarray(gridsize).ravel()[:2])
    else:
        nx = max(int(gridsize), 1)
        ny = None
    if extent is None:
        extent = (float(x.min()), float(x.max()), float(y.min()), float(y.max()))
    ex0, ex1, ey0, ey1 = (float(v) for v in extent)
    if ex1 <= ex0:
        ex0, ex1 = ex0 - 0.5, ex1 + 0.5
    if ey1 <= ey0:
        ey0, ey1 = ey0 - 0.5, ey1 + 0.5
    if ny is None:
        ny = max(int(nx / np.sqrt(3.0)), 1)
    ny = max(int(ny), 1)
    if nx * ny > _MAX_BIN_CELLS // 2:
        raise ValueError(
            f"gridsize=({nx}, {ny}) creates too many hexagons "
            f"({nx * ny} > {_MAX_BIN_CELLS // 2})"
        )
    return nx, ny, ex0, ex1, ey0, ey1


def _hexbin_cells(x, y, nx, ny, ex0, ex1, ey0, ey1):
    """Lattice centres, occupied cells and cell size of a hexbin grid."""
    sx = (ex1 - ex0) / nx
    sy = (ey1 - ey0) / ny
    nx1, ny1 = nx + 1, ny + 1
    nx2, ny2 = nx, ny
    # Two interleaved rectangular grids form a triangular lattice. The
    # nearest of their centres gives the hexagonal Voronoi cell for a point.
    centers = np.column_stack([
        np.concatenate([
            np.repeat(np.arange(nx1), ny1),
            np.repeat(np.arange(nx2) + 0.5, ny2),
        ]) * sx + ex0,
        np.concatenate([
            np.tile(np.arange(ny1), nx1),
            np.tile(np.arange(ny2), nx2) + 0.5,
        ]) * sy + ey0,
    ])
    ix = (x - ex0) / sx
    iy = (y - ey0) / sy
    ix1 = np.rint(ix).astype(int)
    iy1 = np.rint(iy).astype(int)
    ix2 = np.floor(ix).astype(int)
    iy2 = np.floor(iy).astype(int)
    valid1 = (ix1 >= 0) & (ix1 < nx1) & (iy1 >= 0) & (iy1 < ny1)
    valid2 = (ix2 >= 0) & (ix2 < nx2) & (iy2 >= 0) & (iy2 < ny2)
    d1 = (ix - ix1) ** 2 + 3.0 * (iy - iy1) ** 2
    d2 = (ix - ix2 - 0.5) ** 2 + 3.0 * (iy - iy2 - 0.5) ** 2
    use1 = valid1 & (~valid2 | (d1 <= d2))
    valid = valid1 | valid2
    cell = np.where(use1, ix1 * ny1 + iy1, nx1 * ny1 + ix2 * ny2 + iy2)
    return centers, cell[valid], valid, nx1 * ny1 + nx2 * ny2, sx, sy


def _streamplot_check(direction, max_step_scale, max_error_scale):
    """Validate the streamplot integration options."""
    if max_step_scale <= 0:
        raise ValueError("The value of integration_max_step_scale must be > 0")
    if max_error_scale <= 0:
        raise ValueError("The value of integration_max_error_scale must be > 0")
    if direction not in ("forward", "backward", "both"):
        raise ValueError(f"unsupported integration_direction: {direction!r}")


def _streamplot_seeds(density, start_points, xs, ys, x0, x1, y0, y1):
    """The seed points streamlines start from: explicit or a regular grid."""
    if start_points is not None:
        seeds = np.asarray(start_points, dtype=float)
        if seeds.ndim == 1:
            seeds = seeds.reshape(1, -1)
        if seeds.shape[0] == 2 and seeds.shape[1] != 2:
            seeds = seeds.T
        return seeds[:, :2]
    dens = _as_f64(density)
    if dens.size == 1:
        dens = np.repeat(dens, 2)
    nx = max(2, int(round((xs.size - 1) / 10.0 * dens[0])))
    ny = max(2, int(round((ys.size - 1) / 10.0 * dens[1])))
    return np.array([[sx, sy] for sy in np.linspace(y0, y1, ny)
                     for sx in np.linspace(x0, x1, nx)])


def _streamplot_trajectories(xs, ys, uu, vv, mask, seeds, direction, step,
                             max_steps, max_distance, x0, x1, y0, y1):
    """Integrate the normalised field from every seed inside the grid."""
    sampler = _streamplot_sampler(xs, ys, uu, vv, mask)

    def field(px, py):
        ux, vy = sampler(px, py)
        speed = _math.hypot(ux, vy)
        if not np.isfinite(speed) or speed <= 1e-12:
            return None
        return ux / speed, vy / speed

    def advance(px, py, sign):
        first = field(px, py)
        if first is None:
            return None
        mx = px + sign * step * 0.5 * first[0]
        my = py + sign * step * 0.5 * first[1]
        mid = field(mx, my)
        if mid is None:
            return None
        return px + sign * step * mid[0], py + sign * step * mid[1]

    def trace(sx, sy, sign):
        points = [(float(sx), float(sy))]
        px, py, travelled = float(sx), float(sy), 0.0
        for _ in range(max_steps):
            nxt = advance(px, py, sign)
            if nxt is None:
                break
            nxv, nyv = nxt
            if not (x0 - step <= nxv <= x1 + step and y0 - step <= nyv <= y1 + step):
                break
            travelled += _math.hypot(nxv - px, nyv - py)
            if travelled > max_distance:
                break
            points.append((nxv, nyv))
            px, py = nxv, nyv
        return points

    trajectories = []
    for sx, sy in seeds:
        if not (x0 <= sx <= x1 and y0 <= sy <= y1):
            continue
        if direction == "forward":
            pts = trace(sx, sy, 1)
        elif direction == "backward":
            pts = trace(sx, sy, -1)
        else:
            back = trace(sx, sy, -1)[1:]
            pts = list(reversed(back)) + trace(sx, sy, 1)
        if len(pts) >= 2:
            trajectories.append(np.asarray(pts, dtype=float))
    return trajectories


def _streamplot_segments(trajectories, color_at, dx, dy, num_arrows, arrowsize,
                         color_values, xs, ys):
    """Line segments, their colours, arrow segments and sampled field values."""
    segments, colors, shown_values = [], [], []
    arrow_segments, arrow_colors = [], []
    for pts in trajectories:
        good = np.isfinite(pts).all(axis=1)
        pts = pts[good]
        if len(pts) < 2:
            continue
        for i in range(len(pts) - 1):
            p0, p1 = pts[i], pts[i + 1]
            if np.allclose(p0, p1):
                continue
            segments.append(np.vstack([p0, p1]).ravel().tolist())
            mid = (p0 + p1) * 0.5
            colors.append(color_at(mid[0], mid[1]))
            if color_values is not None:
                shown_values.append(_streamplot_sample(color_values, xs, ys, mid[0], mid[1]))
        if num_arrows and arrowsize and arrowsize > 1e-3 and len(pts) > 2:
            count = max(1, int(num_arrows))
            for idx in np.linspace(1, len(pts) - 1, count, endpoint=False):
                i = int(np.clip(round(idx), 1, len(pts) - 1))
                tip = pts[i]
                direction = pts[i] - pts[i - 1]
                norm = _math.hypot(direction[0], direction[1])
                if not norm:
                    continue
                direction = direction / norm
                normal = np.array([-direction[1], direction[0]])
                size = 0.45 * min(dx, dy)
                left = tip - direction * size + normal * size * 0.45
                right = tip - direction * size - normal * size * 0.45
                arrow_segments.append(np.vstack([left, tip, right]).ravel().tolist())
                arrow_colors.append(color_at(tip[0], tip[1]))

    segments.extend(arrow_segments)
    colors.extend(arrow_colors)
    return segments, colors, shown_values


# Bound by `_plotting` once every module is imported: importing
# these at module scope would create cycles between the modules.
if TYPE_CHECKING:
    from ._cm import _norm_values
    from ._config import rcParams
    from ._images import AxesImage, ContourSet
    from ._plot_helpers import (
        _as_f64,
        _as_image,
        _check_same_length,
        _cmap_colors,
        _colors,
        _contour_args,
        _levels,
        _line_colors,
        _mesh_args,
        _streamplot_field,
        _streamplot_sample,
        _streamplot_sampler,
        _tri_args,
        _tri_field,
    )
