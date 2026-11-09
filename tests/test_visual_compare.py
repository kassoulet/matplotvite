"""Tests for the pixel metric used by the benchmark and corpus galleries."""

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402 - backend must be set first

pytest.importorskip("pypdfium2")
pytest.importorskip("cairosvg")

from tools.visual_compare import compare_images  # noqa: E402


def test_vector_baselines_are_rasterised_at_the_rendered_size(tmp_path):
    """PDF/SVG baselines become comparable PNGs instead of an imread error."""
    figure, axes = plt.subplots(figsize=(6.4, 4.8))
    axes.plot([0, 1, 2], [3, 1, 2])
    ours = tmp_path / "ours.png"
    figure.savefig(ours, dpi=100)
    plt.close(figure)

    for suffix in (".pdf", ".svg"):
        baseline = tmp_path / f"baseline{suffix}"
        figure, axes = plt.subplots(figsize=(6.4, 4.8))
        axes.plot([0, 1, 2], [3, 1, 2])
        figure.savefig(baseline, dpi=100)
        plt.close(figure)

        result = compare_images(baseline, ours)
        assert result["shape_match"] is True
        assert result["rms"] < 0.2
        assert result["mismatch_pct"] is not None
