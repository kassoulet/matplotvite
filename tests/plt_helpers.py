"""Shared helpers for the split `test_plt_*` modules."""

import re
import struct
import zlib

import matplotvite as plt
import numpy as np
from png_utils import decode_png_rgba


def _fig():
    f = plt.figure((4, 3))
    plt.plot(np.arange(10), np.arange(10) ** 2, label="sq", color="red")
    plt.plot([1, 2, 3], label="list")  # y only
    plt.title("t"); plt.xlabel("x"); plt.ylabel("y"); plt.legend()
    return f


def _mean_abs_channel_diff(a_rows, b_rows):
    """Mean |difference| over the RGB channels of two decoded PNGs."""
    total = 0
    count = 0
    for row_a, row_b in zip(a_rows, b_rows):
        for i in range(0, min(len(row_a), len(row_b)), 4):
            for channel in range(3):
                total += abs(row_a[i + channel] - row_b[i + channel])
                count += 1
    return total / max(count, 1)


def _png_colour_counts(rows):
    counts = {"red": 0, "blue": 0, "green": 0, "orange": 0, "nonwhite": 0}
    for row in rows:
        for i in range(0, len(row), 4):
            r, g, b = row[i], row[i + 1], row[i + 2]
            counts["red"] += r > 150 and g < 120 and b < 120
            counts["blue"] += b > 150 and r < 120 and g < 120
            counts["green"] += g > 100 and r < 120 and b < 120
            counts["orange"] += r > 180 and 60 < g < 180 and b < 100
            counts["nonwhite"] += min(r, g, b) < 250
    return counts


def _image_box(svg_path):
    m = re.search(r'<image x="[-\d]+" y="[-\d]+" width="(\d+)" height="(\d+)"',
                  svg_path.read_text(encoding="utf-8"))
    return int(m.group(1)), int(m.group(2))


def _bump(n=30):
    x = np.linspace(-2, 2, n)
    y = np.linspace(-2, 2, n)
    return x, y, np.exp(-(x[None, :] ** 2 + y[:, None] ** 2))


def _axes_face_box(rows):
    """Bounding box of the axes face colour in a decoded PNG."""
    xs, ys = [], []
    for y, row in enumerate(rows):
        for i in range(0, len(row), 4):
            r, g, b = row[i], row[i + 1], row[i + 2]
            if g > 140 and r < 110 and b < 110:
                xs.append(i // 4)
                ys.append(y)
    assert xs and ys
    return max(xs) - min(xs), max(ys) - min(ys)


def _ink_width(path):
    _, _, rows = decode_png_rgba(path.read_bytes())
    cols = [i // 4 for row in rows for i in range(0, len(row), 4)
            if min(row[i], row[i + 1], row[i + 2]) < 250]
    return max(cols) - min(cols)


class _FakeRect:
    def __init__(self, x, y, w, h, face="red", edge="black", lw=2.0, alpha=1.0):
        self._v = (x, y, w, h)
        self._face, self._edge, self._lw, self._alpha = face, edge, lw, alpha

    def get_x(self): return self._v[0]
    def get_y(self): return self._v[1]
    def get_width(self): return self._v[2]
    def get_height(self): return self._v[3]
    def get_facecolor(self): return self._face
    def get_edgecolor(self): return self._edge
    def get_linewidth(self): return self._lw
    def get_alpha(self): return self._alpha
    def get_label(self): return ""


class _FakeCollection:
    def __init__(self, offsets, colors, sizes):
        self._offsets, self._colors, self._sizes = offsets, colors, sizes

    def get_offsets(self): return np.asarray(self._offsets, dtype=float)
    def get_facecolor(self): return np.asarray(self._colors, dtype=float)
    def get_sizes(self): return np.asarray(self._sizes, dtype=float)
    def get_alpha(self): return 1.0
    def get_marker(self): return "o"
    def get_label(self): return ""


def _over_white(rows):
    """Composite RGBA rows over white so a transparent render can be compared."""
    out = []
    for row in rows:
        px = []
        for i in range(0, len(row), 4):
            alpha = row[i + 3] / 255.0
            px.append([min(255.0, row[i + k] * alpha + 255.0 * (1 - alpha))
                       for k in range(3)])
        out.append(px)
    return out


def _png_chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def _pack_png_samples(samples, depth):
    """Pack one scanline at a PNG bit depth, including sub-byte depths."""
    if depth == 8:
        return bytes(samples)
    if depth == 16:
        return b"".join(struct.pack(">H", int(value)) for value in samples)
    packed = bytearray()
    per_byte = 8 // depth
    for start in range(0, len(samples), per_byte):
        byte = 0
        for offset, value in enumerate(samples[start:start + per_byte]):
            byte |= (int(value) & ((1 << depth) - 1)) << (8 - depth * (offset + 1))
        packed.append(byte)
    return bytes(packed)


def _write_png(path, width, height, depth, color, rows, palette=None,
               transparency=None):
    chunks = [_png_chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, 0))]
    if palette is not None:
        chunks.append(_png_chunk(b"PLTE", palette))
    if transparency is not None:
        chunks.append(_png_chunk(b"tRNS", transparency))
    raw = b"".join(b"\x00" + _pack_png_samples(row, depth) for row in rows)
    chunks.append(_png_chunk(b"IDAT", zlib.compress(raw)))
    chunks.append(_png_chunk(b"IEND", b""))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"".join(chunks))
