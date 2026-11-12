"""Tests for the pixel metric used by the benchmark and corpus galleries."""

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402 - backend must be set first

pytest.importorskip("pypdfium2")
pytest.importorskip("cairosvg")

import matplotvite  # noqa: E402

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


def test_svg_output_is_compared_against_matplotlib_svg(tmp_path):
    """Matplotvite's SVG export is rasterised and measured against Matplotlib's."""
    figure, axes = plt.subplots(figsize=(6.4, 4.8))
    axes.plot([0, 1, 2], [3, 1, 2])
    axes.set_title("svg comparison")
    figure.savefig(tmp_path / "mpl.svg", format="svg")
    plt.close(figure)

    figure, axes = matplotvite.subplots(figsize=(6.4, 4.8))
    axes.plot([0, 1, 2], [3, 1, 2])
    axes.set_title("svg comparison")
    figure.savefig(tmp_path / "rs.svg", format="svg")
    matplotvite.close("all")

    result = compare_images(tmp_path / "mpl.svg", tmp_path / "rs.svg")
    assert result["shape_match"] is True
    assert result["rms"] < 0.2


def test_svg_comparison_page_lists_both_exports(tmp_path):
    """The pages build turns the SVG metrics into a standalone comparison page."""
    import json

    from tools.build_pages import generate_galleries_html, generate_svg_comparison_html

    gallery_dir = tmp_path / "visual-svg"
    gallery_dir.mkdir()
    (gallery_dir / "metrics.json").write_text(json.dumps({
        "lines": {"shape_match": True, "rms": 0.1, "mismatch_pct": 2.0},
        "broken": {"error": "TypeError: nope"},
    }), encoding="utf-8")
    (gallery_dir / "lines.mpl.svg").write_text("<svg/>", encoding="utf-8")
    (gallery_dir / "lines.rs.svg").write_text("<svg/>", encoding="utf-8")

    page = generate_svg_comparison_html(tmp_path)
    assert page is not None
    assert "visual-svg/lines.mpl.svg" in page
    assert "visual-svg/lines.rs.svg" in page
    assert "rms 0.100" in page
    assert "TypeError: nope" in page
    assert "svg-comparison.html" in generate_galleries_html(tmp_path)

    assert generate_svg_comparison_html(tmp_path / "missing") is None


def test_gallery_samples_are_comparison_cases():
    """The example gallery's snippets run against either library via OUT."""
    from tools.visual_compare import gallery_cases

    cases = gallery_cases()
    code = cases["gallery_trigonometric_waves"]
    assert "import matplotvite" not in code
    assert 'plt.savefig("trigonometric_waves.png")' not in code
    assert "plt.savefig(OUT)" in code
    assert "gallery_broken_barh" in cases
