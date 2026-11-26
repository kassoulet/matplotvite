"""Scenes shared by the Python and Rust golden-image tests.

Each scene is a small figure built only from API calls the native Rust builder
also supports. ``tests/golden/scenes.txt`` names the scenes and their tolerance;
``tests/test_golden_images.py`` and ``tests/golden.rs`` render the same names and
compare against the committed PNGs, so the two front ends cannot drift.

Regenerate the goldens after an intentional rendering change::

    .venv/bin/python tests/golden_scenes.py
"""

from __future__ import annotations

import argparse
import pathlib

import matplotvite as plt
import numpy as np

GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"


def scene_line_legend() -> plt.Figure:
    fig = plt.Figure(figsize=(4.8, 3.6), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4], label="quadratic")
    ax.plot([0, 1, 2], [1, 0, 1], color="#d62728", label="wave")
    ax.set_title("Line and legend")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_xticks([0, 0.5, 1, 1.5, 2])
    ax.set_yticks([0, 1, 2, 3, 4])
    ax.grid(True, alpha=0.4)
    ax.legend(loc="upper left")
    return fig


def scene_bars_scatter() -> plt.Figure:
    fig = plt.Figure(figsize=(4.8, 3.6), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    ax.bar([0, 1, 2], [3, 5, 2], color="#2ca02c", label="counts")
    ax.scatter([0.2, 1.2, 2.2], [4, 2, 3], c="#ff7f0e", label="points")
    ax.set_xticks([0, 1, 2], ["alpha", "beta", "gamma"], rotation=30)
    ax.set_ylim(0, 6)
    ax.legend()
    ax.set_title("Bars and scatter")
    return fig


def scene_image_colorbar() -> plt.Figure:
    fig = plt.Figure(figsize=(4.8, 3.6), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    image = ax.imshow(np.arange(12).reshape(3, 4), cmap="magma", vmin=0, vmax=11)
    ax.set_xticks([0, 1, 2, 3])
    ax.set_yticks([0, 1, 2])
    fig.colorbar(image)
    return fig


def scene_fill_annotate() -> plt.Figure:
    fig = plt.Figure(figsize=(4.8, 3.6), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    x = [0, 1, 2, 3]
    ax.fill_between(x, [0, 0, 0, 0], [1, 2, 1.5, 2], color="#9467bd",
                    alpha=0.3, label="band")
    ax.plot(x, [0.5, 1, 0.8, 1.2], color="#1f77b4", label="mean")
    ax.text(0.2, 1.8, "band", fontsize=11)
    ax.annotate("peak", (1, 2), xytext=(1.8, 2.3))
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 2.5)
    ax.set_xticks([0, 1, 2, 3])
    ax.set_yticks([0, 0.5, 1, 1.5, 2, 2.5])
    ax.legend(loc="lower right")
    return fig


def scene_violin() -> plt.Figure:
    coords = np.linspace(0.0, 4.0, 41)
    wide = np.exp(-((coords - 2.0) / 0.9) ** 2)
    narrow = np.exp(-((coords - 1.6) / 0.5) ** 2)
    fig = plt.Figure(figsize=(4.8, 3.6), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    ax.violin(
        [
            {"coords": coords, "vals": wide, "min": 0.0, "max": 4.0,
             "mean": 2.0, "median": 2.0},
            {"coords": coords, "vals": narrow, "min": 0.0, "max": 4.0,
             "mean": 1.6, "median": 1.6},
        ],
        positions=[1.0, 2.0],
        widths=[0.8, 0.8],
    )
    ax.set_xticks([1.0, 2.0], ["alpha", "beta"])
    ax.set_yticks([0.0, 1.0, 2.0, 3.0, 4.0])
    ax.set_title("Violin plots")
    return fig


def scene_autoscale_margins() -> plt.Figure:
    fig = plt.Figure(figsize=(4.8, 3.6), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0.0, 1.0, 2.0, 3.0], [1.0, 3.0, 2.0, 4.0], color="#1f77b4")
    ax.margins(x=0.25, y=0.4)
    ax.set_xticks([-1.0, 0.0, 1.0, 2.0, 3.0, 4.0])
    ax.set_yticks([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    ax.set_title("Autoscaled margins")
    return fig


SCENES = {
    "line_legend": scene_line_legend,
    "bars_scatter": scene_bars_scatter,
    "image_colorbar": scene_image_colorbar,
    "fill_annotate": scene_fill_annotate,
    "violin": scene_violin,
    "autoscale_margins": scene_autoscale_margins,
}


def read_manifest(path: pathlib.Path | None = None) -> list[tuple[str, int, int, float]]:
    """Return ``(name, width, height, max_rms)`` entries from the manifest."""
    path = path or GOLDEN_DIR / "scenes.txt"
    scenes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, width, height, rms = line.split()
        scenes.append((name, int(width), int(height), float(rms)))
    return scenes


def render(name: str, path: pathlib.Path) -> None:
    """Render one shared scene with the Python facade."""
    SCENES[name]().savefig(path, dpi=100)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=GOLDEN_DIR)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, _width, _height, _rms in read_manifest():
        target = args.out / f"{name}.png"
        render(name, target)
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
