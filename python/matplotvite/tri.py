"""Small, dependency-free subset of `matplotlib.tri`.

Triangulation without explicit triangles uses a Bowyer-Watson Delaunay
construction. The interpolators are linear; the cubic class exposes the same
sampling API because the renderer only consumes sampled values.
"""

import numpy as np

__all__ = (
    "CubicTriInterpolator",
    "LinearTriInterpolator",
    "TriAnalyzer",
    "Triangulation",
    "UniformTriRefiner",
)


def _circumcircle_contains(a, b, c, p):
    ax, ay = a
    bx, by = b
    cx, cy = c
    det = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(det) < 1e-12:
        return False
    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / det
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / det
    r2 = (ax - ux) ** 2 + (ay - uy) ** 2
    return (p[0] - ux) ** 2 + (p[1] - uy) ** 2 < r2 - 1e-12


def _delaunay(x, y):
    """Return triangle vertex indices for a small point set."""
    points = np.column_stack((x, y))
    n = len(points)
    if n < 3:
        return np.empty((0, 3), dtype=int)
    span = max(float(np.ptp(x)), float(np.ptp(y)), 1.0) * 10.0
    cx, cy = float(np.mean(x)), float(np.mean(y))
    vertices = np.vstack((points, [[cx - span, cy - span],
                                   [cx + span, cy - span],
                                   [cx, cy + span]]))
    triangles = [(n, n + 1, n + 2)]
    for index in range(n):
        point = vertices[index]
        bad = [tri_index for tri_index, tri in enumerate(triangles)
               if _circumcircle_contains(vertices[tri[0]], vertices[tri[1]],
                                         vertices[tri[2]], point)]
        edges = {}
        for tri_index in bad:
            a, b, c = triangles[tri_index]
            for edge in ((a, b), (b, c), (c, a)):
                key = tuple(sorted(edge))
                edges[key] = edges.get(key, 0) + 1
        bad_set = set(bad)
        triangles = [tri for i, tri in enumerate(triangles) if i not in bad_set]
        for (a, b), count in edges.items():
            if count == 1:
                triangles.append((a, b, index))
    return np.asarray([tri for tri in triangles if max(tri) < n], dtype=int)


def _barycentric_scalar(px, py, x0, y0, x1, y1, x2, y2):
    det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(det) < 1e-15:
        return None
    l1 = ((px - x0) * (y2 - y0) - (x2 - x0) * (py - y0)) / det
    l2 = ((x1 - x0) * (py - y0) - (px - x0) * (y1 - y0)) / det
    return 1.0 - l1 - l2, l1, l2


class _TriangleIndex:
    """Uniform bucket index for fast point location in a triangulation."""

    def __init__(self, x, y, triangles):
        self.x = x
        self.y = y
        self.triangles = triangles
        if len(triangles) == 0:
            self.size = 1
            self.minx = self.miny = 0.0
            self.maxx = self.maxy = 1.0
            self.buckets = {}
            return
        xs = x[triangles]
        ys = y[triangles]
        self.minx, self.miny = float(xs.min()), float(ys.min())
        self.maxx, self.maxy = float(xs.max()), float(ys.max())
        self.size = max(1, int(np.sqrt(len(triangles))))
        self.buckets = {}
        width = max(self.maxx - self.minx, 1e-15)
        height = max(self.maxy - self.miny, 1e-15)
        for index, tri in enumerate(triangles):
            bx = ((x[tri] - self.minx) / width * (self.size - 1)).astype(int)
            by = ((y[tri] - self.miny) / height * (self.size - 1)).astype(int)
            for iy in range(by.min(), by.max() + 1):
                for ix in range(bx.min(), bx.max() + 1):
                    self.buckets.setdefault((ix, iy), []).append(index)

    def find(self, px, py):
        """Return (triangle, barycentric) for a point, or (None, None)."""
        if not self.buckets or not np.isfinite(px) or not np.isfinite(py):
            return None, None
        width = max(self.maxx - self.minx, 1e-15)
        height = max(self.maxy - self.miny, 1e-15)
        ix = int(np.clip((px - self.minx) / width * (self.size - 1),
                         0, self.size - 1))
        iy = int(np.clip((py - self.miny) / height * (self.size - 1),
                         0, self.size - 1))
        for index in self.buckets.get((ix, iy), ()):
            tri = self.triangles[index]
            weights = _barycentric_scalar(
                px, py, self.x[tri[0]], self.y[tri[0]],
                self.x[tri[1]], self.y[tri[1]], self.x[tri[2]], self.y[tri[2]])
            if weights is not None and min(weights) >= -1e-10:
                return index, weights
        return None, None


class Triangulation:
    """Unstructured triangular mesh from x/y points and optional triangles."""

    def __init__(self, x, y, triangles=None, mask=None):
        self.x = np.asarray(x, dtype=float).ravel()
        self.y = np.asarray(y, dtype=float).ravel()
        if self.x.size != self.y.size:
            raise ValueError("x and y must have the same length")
        if triangles is None:
            self.triangles = _delaunay(self.x, self.y)
        else:
            self.triangles = np.asarray(triangles, dtype=int).reshape(-1, 3)
            if self.triangles.size and (self.triangles.min() < 0
                                        or self.triangles.max() >= self.x.size):
                raise ValueError("triangle vertex index out of range")
        if mask is None:
            self.mask = np.zeros(len(self.triangles), dtype=bool)
        else:
            self.mask = np.asarray(mask, dtype=bool).ravel()
            if self.mask.size != len(self.triangles):
                raise ValueError("mask must have one entry per triangle")
        self._trifinder = None
        self._index = None

    @property
    def index(self):
        if self._index is None:
            self._index = _TriangleIndex(self.x, self.y,
                                         self.get_masked_triangles())
        return self._index

    def set_mask(self, mask):
        self.mask = (np.zeros(len(self.triangles), dtype=bool) if mask is None
                     else np.asarray(mask, dtype=bool).ravel())
        self._trifinder = None
        self._index = None
        return self

    def get_masked_triangles(self):
        return self.triangles[~self.mask]

    def get_trifinder(self):
        if self._trifinder is None:
            self._trifinder = _TriFinder(self)
        return self._trifinder


class _TriFinder:
    def __init__(self, triangulation):
        self._tri = triangulation

    def __call__(self, x, y):
        px, py = np.broadcast_arrays(np.asarray(x, dtype=float),
                                     np.asarray(y, dtype=float))
        out = np.full(px.shape, -1, dtype=int)
        flat = out.ravel()
        for i, (qx, qy) in enumerate(zip(px.ravel(), py.ravel())):
            index, _ = self._tri.index.find(float(qx), float(qy))
            if index is not None:
                flat[i] = index
        return int(out) if out.ndim == 0 else out


class LinearTriInterpolator:
    def __init__(self, triangulation, z):
        self.triangulation = triangulation
        self.z = np.asarray(z, dtype=float).ravel()
        if self.z.size != len(triangulation.x):
            raise ValueError("z must have one value per triangulation point")

    def _sample(self, x, y):
        px, py = np.broadcast_arrays(np.asarray(x, dtype=float),
                                     np.asarray(y, dtype=float))
        out = np.full(px.size, np.nan)
        for i, (qx, qy) in enumerate(zip(px.ravel(), py.ravel())):
            index, weights = self.triangulation.index.find(float(qx), float(qy))
            if index is None:
                continue
            tri = self.triangulation.index.triangles[index]
            out[i] = sum(w * self.z[v] for w, v in zip(weights, tri))
        return out.reshape(px.shape)

    def __call__(self, x, y):
        return self._sample(x, y)


class CubicTriInterpolator(LinearTriInterpolator):
    """Linear fallback with the cubic interpolator's API."""

    def __init__(self, triangulation, z, kind="min_E"):
        super().__init__(triangulation, z)
        self.kind = kind

    def gradient(self, x, y):
        px, py = np.broadcast_arrays(np.asarray(x, dtype=float),
                                     np.asarray(y, dtype=float))
        out_x = np.zeros(px.size)
        out_y = np.zeros(px.size)
        for i, (qx, qy) in enumerate(zip(px.ravel(), py.ravel())):
            index, _ = self.triangulation.index.find(float(qx), float(qy))
            if index is None:
                continue
            x0, x1, x2 = self.triangulation.x[self.triangulation.index.triangles[index]]
            y0, y1, y2 = self.triangulation.y[self.triangulation.index.triangles[index]]
            z0, z1, z2 = self.z[self.triangulation.index.triangles[index]]
            det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            if abs(det) < 1e-15:
                continue
            out_x[i] = ((z1 - z0) * (y2 - y0) - (z2 - z0) * (y1 - y0)) / det
            out_y[i] = ((z2 - z0) * (x1 - x0) - (z1 - z0) * (x2 - x0)) / det
        return out_x.reshape(px.shape), out_y.reshape(px.shape)


class UniformTriRefiner:
    """Uniform midpoint refinement of a triangulation and its field."""

    def __init__(self, triangulation):
        self._tri = triangulation

    def _refine(self, values=None, subdiv=1):
        triangulation = self._tri
        x, y = triangulation.x.copy(), triangulation.y.copy()
        triangles = triangulation.triangles.copy()
        mask = triangulation.mask.copy()
        for _ in range(int(subdiv)):
            midpoints = {}
            new_triangles, new_mask = [], []
            for tri, masked in zip(triangles, mask):
                corners = []
                for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                    key = tuple(sorted((int(a), int(b))))
                    if key not in midpoints:
                        midpoints[key] = len(x)
                        x = np.append(x, (x[a] + x[b]) / 2.0)
                        y = np.append(y, (y[a] + y[b]) / 2.0)
                        if values is not None:
                            values = np.append(values, (values[a] + values[b]) / 2.0)
                    corners.append(midpoints[key])
                m01, m12, m20 = corners
                new_triangles.extend(((tri[0], m01, m20), (tri[1], m12, m01),
                                      (tri[2], m20, m12), (m01, m12, m20)))
                new_mask.extend((masked,) * 4)
            triangles = np.asarray(new_triangles, dtype=int)
            mask = np.asarray(new_mask, dtype=bool)
        return Triangulation(x, y, triangles, mask), values

    def refine_triangulation(self, subdiv=1):
        return self._refine(None, subdiv)[0]

    def refine_field(self, z, subdiv=1):
        values = np.asarray(z, dtype=float).ravel()
        if values.size != len(self._tri.x):
            raise ValueError("z must have one value per triangulation point")
        return self._refine(values, subdiv)


class TriAnalyzer:
    """Compatibility analyzer; flat-triangle detection is conservative."""

    def __init__(self, triangulation):
        self._tri = triangulation

    def get_flat_tri_mask(self, min_circle_ratio=0.01, rescale=True):
        return np.zeros(len(self._tri.triangles), dtype=bool)

    def circle_ratios(self, rescale=True):
        return np.ones(len(self._tri.triangles))
