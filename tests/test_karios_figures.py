"""Reproduces the two most demanding KARIOS report figures with matplotvite only.

- overview: 2 imshow + 2 scatter + 2 side colorbars + multi-line header (4 + 2 + 1 axes)
- shift by row/col: scatter + marginal bar/line/fill profiles on twin axes, legends,
  left colorbar, header

No karios / pandas / GDAL dependency: synthetic data, numpy + matplotvite only.
Meant to be dropped into matplotvite's tests (pytest) or run as a script:

    python test_karios_figures.py [out_dir]      # writes 01_overview.png, 02_dx.png

Layout is checked visually (look at the PNGs); the asserts only guard against crashes
and empty renders.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotvite as plt
import numpy as np

SIZE = 3660  # image side in px (Landsat/S2 30 m tile)
N_KP = 13_700
MON_NAME = "LC81960302017318MTI00_B4_REFRAMED_GDAL.TIF"
REF_NAME = "S2A_OPER_MSI_L1C_TL_MPS__20161018T120000_A000008_T31TFJ_B04_30m.tif"


# --------------------------------------------------------------------------- data


def make_data(seed: int = 0):
    """Two synthetic images (stride-sampled, as KARIOS does) and a KP cloud."""
    rng = np.random.default_rng(seed)
    n = 1024  # images are displayed at <= 1024 px per side
    yy, xx = np.mgrid[0:n, 0:n] / n
    base = (
        0.5
        + 0.25 * np.sin(9 * xx + 3 * yy)
        + 0.2 * np.cos(14 * yy)
        + 0.15 * rng.standard_normal((n, n))
    )
    mon = np.clip(base, 0, 1)
    mon[yy < 0.25 * xx] = 0  # black wedge, like a reframed footprint
    ref = np.clip(0.6 * base + 0.1 * rng.standard_normal((n, n)), 0, 1)
    ref[xx > 1 - 0.15 * yy] = 0

    x0 = rng.uniform(0, SIZE * 0.93, N_KP)
    y0 = rng.uniform(0, SIZE, N_KP)
    keep = y0 > 0.2 * x0  # same wedge as the monitored image
    x0, y0 = x0[keep], y0[keep]
    dx = rng.normal(-0.5, 0.35, x0.size)
    dy = rng.normal(0.2, 0.35, x0.size)
    return {
        "mon": mon,
        "ref": ref,
        "x0": x0,
        "y0": y0,
        "dx": dx,
        "dy": dy,
        "radial": np.hypot(dx, dy),
        "angle": np.degrees(np.arctan2(dy, dx)),
    }


# --------------------------------------------------------------------------- helpers


def colorbar(fig, rect, cmap, vmin, vmax, ticklocation="right", n=5):
    """Vertical colorbar drawn as a gradient imshow in its own axes."""
    ax = fig.add_axes(rect)
    grad = plt.get_cmap(cmap)(np.linspace(1, 0, 256)).reshape(256, 1, 4)
    ax.imshow(grad, extent=(0, 1, 0, 1), aspect="auto")
    ticks = np.linspace(vmin, vmax, n)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks(list((ticks - vmin) / (vmax - vmin)), [f"{t + 0.0:.3g}" for t in ticks])
    left = ticklocation == "left"
    ax.tick_params(axis="y", left=left, labelleft=left, right=not left, labelright=not left)
    return ax


def header(fig, rect, fontsize=14):
    """Two-line header on a blank axes ("\\n" is not rendered, one text per line)."""
    ax = fig.add_axes(rect)
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    step = 1.7 * fontsize / 72 / (rect[3] * fig.get_size_inches()[1])
    for i, line in enumerate((f"Monitored : {MON_NAME}", f"Reference : {REF_NAME}")):
        ax.text(0, 0.5 + step - i * step, line, fontsize=fontsize, va="top", ha="left")
    return ax


def profile(values, positions, bin_size=20):
    """Mean / count / std of `values` per bin of `positions` (numpy only)."""
    idx = (positions // bin_size).astype(int)
    idx -= idx.min()
    count = np.bincount(idx)
    ok = count > 1
    mean = np.bincount(idx, values)[ok] / count[ok]
    var = np.bincount(idx, values**2)[ok] / count[ok] - mean**2
    pos = (np.arange(count.size)[ok] + idx.min()) * bin_size + bin_size // 2
    return pos, mean, count[ok], np.sqrt(np.maximum(var, 0))


def scatter_axes(ax, d, c, cmap, vmin, vmax, title):
    ax.set_title(title)
    ax.set_xlim(0, SIZE)
    ax.set_ylim(SIZE, 0)
    ax.axis("scaled")
    ax.scatter(d["x0"], d["y0"], c=c, cmap=cmap, s=1, vmin=vmin, vmax=vmax)
    ax.grid()


# --------------------------------------------------------------------------- figures


def overview(path: Path, d=None):
    d = d or make_data()
    fig = plt.figure(figsize=(7.5 * 1.25, 7.5 * 1.2))
    fig.suptitle("Errors overview")

    header(fig, [0.05, 0.88, 0.9, 0.08])
    mon = fig.add_axes([0.05, 0.48, 0.4, 0.38])
    rad = fig.add_axes([0.5, 0.48, 0.4, 0.38])
    ref = fig.add_axes([0.05, 0.05, 0.4, 0.38])
    ang = fig.add_axes([0.5, 0.05, 0.4, 0.38])

    for ax, img, title in ((mon, d["mon"], "Monitored"), (ref, d["ref"], "Reference")):
        ax.set_title(title)
        ax.imshow(img, cmap="gray", vmin=0, vmax=1, extent=(0, SIZE, SIZE, 0))

    rmax = d["radial"].mean() + 3 * d["radial"].std()
    scatter_axes(rad, d, d["radial"], "bone_r", 0, rmax, "Radial Error (px)")
    scatter_axes(ang, d, d["angle"], "twilight_shifted", -180, 180, "Angle error (deg), East direction CC")
    colorbar(fig, [0.925, 0.48, 0.015, 0.38], "bone_r", 0, rmax)
    colorbar(fig, [0.925, 0.05, 0.015, 0.38], "twilight_shifted", -180, 180)

    fig.savefig(str(path), dpi=100)
    plt.close(fig)


def shift_by_row_col(path: Path, direction="dx", d=None, bin_size=20):
    d = d or make_data()
    v = d[direction]
    fig = plt.figure(figsize=(12, 12))
    fig.suptitle(f"{direction} pixel shift Mean and STD by row/col (1 row/col = {bin_size}px)")

    # [left, bottom, width, height] cells: header, col profile, scatter, row profile
    header(fig, [0.15, 0.85, 0.8, 0.08])
    ax_col = fig.add_axes([0.15, 0.68, 0.64, 0.12])
    ax_sc = fig.add_axes([0.15, 0.05, 0.64, 0.58])
    ax_row = fig.add_axes([0.82, 0.05, 0.13, 0.58])
    ax_col.set_xlim(0, SIZE)
    ax_row.set_ylim(SIZE, 0)
    ax_col.tick_params(axis="x", labelbottom=False)
    ax_row.tick_params(axis="y", labelleft=False)

    # scatter + left colorbar
    vmin, vmax = v.mean() - 3 * v.std(), v.mean() + 3 * v.std()
    scatter_axes(ax_sc, d, v, "Spectral", vmin, vmax, f"{direction} pixels shifts")
    ax_sc.legend(loc="upper left", title=f"Nb KP={v.size}")
    colorbar(fig, [0.15 - 0.12 * 0.64, 0.05, 0.03 * 0.64, 0.58], "Spectral", vmin, vmax, "left")

    # column profile: KP count bars + mean line + std band on a twin axis
    pos, mean, nb, std = profile(v, d["x0"], bin_size)
    err = std * np.sqrt(1 / pos.size + (pos - pos.mean()) ** 2 / np.sum((pos - pos.mean()) ** 2))
    lim = np.floor(np.abs(mean).max()) + 1
    ax_col.set_ylim(0, nb.max())
    ax_col.bar(pos, nb, width=bin_size, color="grey", alpha=0.2, label="KP per col")
    ax_col.legend(loc="upper right")
    twin = ax_col.twinx()
    twin.set_ylim(-lim, lim)
    twin.plot(pos, mean, label=f"Mean {direction} by col")
    twin.fill_between(pos, mean - err, mean + err, alpha=0.3, label="std")
    twin.legend(loc="upper left")
    twin.axhline(0, color="grey", linewidth=1, linestyle="--")
    twin.tick_params(axis="y", left=True, labelleft=True, right=False, labelright=False)
    ax_col.tick_params(axis="y", left=False, labelleft=False, right=True, labelright=True)
    ax_col.grid(axis="x")

    # row profile: same, rotated (barh / twiny / fill_betweenx)
    pos, mean, nb, std = profile(v, d["y0"], bin_size)
    err = std * np.sqrt(1 / pos.size + (pos - pos.mean()) ** 2 / np.sum((pos - pos.mean()) ** 2))
    lim = np.floor(np.abs(mean).max()) + 1
    ax_row.set_xlim(0, nb.max())
    ax_row.barh(pos, nb, height=bin_size, color="grey", alpha=0.2, label="KP per row")
    ax_row.legend(loc="lower right")
    twin = ax_row.twiny()
    twin.set_xlim(-lim, lim)
    twin.plot(mean, pos, label=f"Mean {direction} by row")
    twin.fill_betweenx(pos, mean - err, mean + err, alpha=0.3, label="std")
    twin.legend(loc="upper right")
    twin.axvline(0, color="grey", linewidth=1, linestyle="--")
    twin.tick_params(axis="x", top=True, labeltop=True, bottom=False, labelbottom=False)
    ax_row.tick_params(axis="x", top=False, labeltop=False, bottom=True, labelbottom=True)
    ax_row.grid(axis="y")

    fig.savefig(str(path), dpi=100)
    plt.close(fig)


# --------------------------------------------------------------------------- tests


def _check_png(path: Path):
    head = path.read_bytes()[:8]
    assert head == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    assert path.stat().st_size > 50_000, f"{path} is suspiciously small (empty render?)"


def test_overview(tmp_path):
    overview(tmp_path / "01_overview.png")
    _check_png(tmp_path / "01_overview.png")


def test_shift_by_row_col_dx(tmp_path):
    shift_by_row_col(tmp_path / "02_dx.png", "dx")
    _check_png(tmp_path / "02_dx.png")


def test_shift_by_row_col_dy(tmp_path):
    shift_by_row_col(tmp_path / "03_dy.png", "dy")
    _check_png(tmp_path / "03_dy.png")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    data = make_data()
    overview(out / "01_overview.png", data)
    shift_by_row_col(out / "02_dx.png", "dx", data)
    shift_by_row_col(out / "03_dy.png", "dy", data)
    for p in sorted(out.glob("0[123]_*.png")):
        _check_png(p)
        print(p, f"{p.stat().st_size / 1e3:.0f} kB")
