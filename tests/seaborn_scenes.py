"""Seaborn wrapper-parity scenes and reference-image generation.

These scenes model the thin Seaborn wrappers that reduce to plotting calls
matplotvite already supports: lineplot, scatterplot, barplot, histplot,
boxplot and heatmap. The scene functions accept either pyplot module, so the
committed references are rendered by Matplotlib and the tests render the same
calls through matplotvite.

The RMS tolerances absorb the remaining text-rasterizer and line-antialiasing
differences between the two renderers. They are deliberately tight enough to
catch moved or missing artists, bars, bands or annotations.

Regenerate the references after an intentional rendering change::

    .venv/bin/python tests/seaborn_scenes.py
"""

from __future__ import annotations

import argparse
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
GOLDEN_DIR = HERE / "seaborn"

# The seaborn wrapper each scene covers, kept in the manifest for reviewers.
WRAPPERS = {
    "lineplot": "sns.lineplot",
    "scatterplot": "sns.scatterplot",
    "barplot": "sns.barplot",
    "histplot": "sns.histplot",
    "boxplot": "sns.boxplot",
    "heatmap": "sns.heatmap",
}


def _figure(plt):
    figure, axes = plt.subplots(figsize=(4.8, 3.6), dpi=100)
    # matplotvite reserves fixed label margins around its panel. Match that
    # rectangle in the Matplotlib reference so the diff measures the artists,
    # not a subplot-layout offset. matplotvite accepts this as a no-op.
    figure.subplots_adjust(left=63 / 480, right=454 / 480,
                           bottom=74 / 360, top=336 / 360)
    return figure, axes


def lineplot(plt):
    figure, axes = _figure(plt)
    x = [0, 1, 2, 3, 4, 5]
    axes.fill_between(x, [0.7, 1.4, 1.8, 2.6, 2.9, 3.8],
                      [1.3, 2.2, 2.8, 3.4, 4.1, 4.8],
                      color="#4c72b0", alpha=0.25, label="95% CI")
    axes.plot(x, [1.0, 1.8, 2.3, 3.0, 3.5, 4.3], color="#4c72b0",
              linewidth=2.0, label="group A")
    axes.plot(x, [0.4, 1.0, 1.5, 1.8, 2.4, 2.9], color="#dd8452",
              linewidth=2.0, label="group B")
    axes.set_xticks(x)
    axes.set_yticks([0, 1, 2, 3, 4, 5])
    axes.set_xlim(0, 5)
    axes.set_ylim(0, 5)
    axes.set_xlabel("step")
    axes.set_ylabel("value")
    axes.legend(loc="upper left")
    return figure


def scatterplot(plt):
    figure, axes = _figure(plt)
    axes.scatter([0.2, 0.8, 1.4, 2.1, 2.7, 3.3],
                 [0.5, 1.2, 0.9, 2.0, 1.7, 2.6],
                 c="#4c72b0", s=42, label="group A")
    axes.scatter([0.4, 1.0, 1.7, 2.4, 3.0],
                 [1.4, 0.8, 1.9, 1.2, 2.2],
                 c="#dd8452", s=42, label="group B")
    axes.set_xticks([0, 1, 2, 3])
    axes.set_yticks([0, 1, 2, 3])
    axes.set_xlim(0, 3.5)
    axes.set_ylim(0, 3)
    axes.set_xlabel("x")
    axes.set_ylabel("y")
    axes.legend(loc="upper left")
    return figure


def barplot(plt):
    figure, axes = _figure(plt)
    positions = [0, 1, 2]
    axes.bar([value - 0.18 for value in positions], [3.0, 5.0, 2.0],
             width=0.34, color="#4c72b0", yerr=[0.25, 0.5, 0.3],
             label="group A")
    axes.bar([value + 0.18 for value in positions], [2.0, 4.0, 3.5],
             width=0.34, color="#dd8452", yerr=[0.2, 0.35, 0.3],
             label="group B")
    axes.set_xticks(positions, ["alpha", "beta", "gamma"])
    axes.set_yticks([0, 1, 2, 3, 4, 5, 6])
    axes.set_ylim(0, 6)
    axes.set_xlabel("category")
    axes.set_ylabel("mean")
    axes.legend(loc="upper right")
    return figure


def histplot(plt):
    figure, axes = _figure(plt)
    values = [0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 1.1, 1.2,
              1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.0, 2.1, 2.3, 2.6]
    axes.hist(values, bins=[0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
              density=True, color="#4c72b0", alpha=0.75,
              edgecolor="white", label="sample")
    axes.set_xticks([0, 0.5, 1, 1.5, 2, 2.5, 3])
    axes.set_yticks([0, 0.2, 0.4, 0.6, 0.8])
    axes.set_xlim(0, 3)
    axes.set_ylim(0, 0.8)
    axes.set_xlabel("value")
    axes.set_ylabel("density")
    axes.legend(loc="upper right")
    return figure


def boxplot(plt):
    figure, axes = _figure(plt)
    axes.boxplot([[0.2, 0.5, 0.8, 1.1, 1.4, 1.8],
                  [0.5, 0.9, 1.2, 1.5, 1.9, 2.4]],
                 tick_labels=["group A", "group B"], widths=0.5,
                 patch_artist=True,
                 boxprops={"facecolor": "#4c72b0", "edgecolor": "#333333"},
                 medianprops={"color": "#c44e52", "linewidth": 2.0})
    axes.set_yticks([0, 0.5, 1, 1.5, 2, 2.5])
    axes.set_ylim(0, 2.6)
    axes.set_ylabel("value")
    return figure


def heatmap(plt):
    figure, axes = _figure(plt)
    values = [[1.0, 2.0, 3.0, 4.0],
              [2.0, 3.0, 4.0, 5.0],
              [3.0, 4.0, 5.0, 6.0]]
    axes.imshow(values, cmap="viridis", vmin=1.0, vmax=6.0, aspect="auto")
    axes.set_xticks([0, 1, 2, 3], ["A", "B", "C", "D"])
    axes.set_yticks([0, 1, 2], ["row 1", "row 2", "row 3"])
    for row, entries in enumerate(values):
        for column, value in enumerate(entries):
            axes.text(column, row, f"{value:.0f}", ha="center", va="center",
                      color="white" if value >= 4 else "black")
    axes.set_title("annotated matrix")
    return figure


SCENES = {
    "lineplot": lineplot,
    "scatterplot": scatterplot,
    "barplot": barplot,
    "histplot": histplot,
    "boxplot": boxplot,
    "heatmap": heatmap,
}


def read_manifest(path: pathlib.Path | None = None) -> list[tuple[str, int, int, float, str]]:
    """Return ``(name, width, height, max_rms, wrapper)`` entries."""
    path = path or GOLDEN_DIR / "scenes.txt"
    scenes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, width, height, rms, wrapper = line.split()
        scenes.append((name, int(width), int(height), float(rms), wrapper))
    return scenes


def render(name: str, path: pathlib.Path) -> None:
    """Render one scene through matplotvite's pyplot facade."""
    import matplotvite

    matplotvite.close("all")
    figure = SCENES[name](matplotvite)
    figure.savefig(path, dpi=100)
    matplotvite.close("all")


def render_matplotlib(name: str, path: pathlib.Path) -> None:
    """Render one scene through Matplotlib; used to refresh the references."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.close("all")
    figure = SCENES[name](plt)
    figure.savefig(path, dpi=100)
    plt.close("all")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=GOLDEN_DIR)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, _width, _height, _rms, _wrapper in read_manifest():
        target = args.out / f"{name}.png"
        render_matplotlib(name, target)
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
