"""Tests verifying that every gallery example executes and is covered by tests."""

import numpy as np
import pytest
from examples.samples import SAMPLES
import matplotvite


def _skip_missing_dependency(sample):
    requires = sample.get("requires")
    if requires:
        pytest.importorskip(requires)


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_sample_runner_execution(sample, tmp_path):
    """Verify that each sample's runner produces a valid image file."""
    _skip_missing_dependency(sample)
    filename = sample["filename"]
    out_file = tmp_path / filename

    runner = sample["runner"]
    runner(str(out_file))

    assert out_file.exists(), f"Sample {sample['id']} did not produce {filename}"
    assert out_file.stat().st_size > 0, f"Sample {sample['id']} produced an empty file"

    if sample["format"] == "png":
        header = out_file.read_bytes()[:8]
        assert header == b"\x89PNG\r\n\x1a\n", f"Invalid PNG magic bytes for {filename}"
    elif sample["format"] == "svg":
        content = out_file.read_text(encoding="utf-8").strip()
        assert content.startswith("<svg"), f"SVG does not start with <svg: {filename}"
        assert content.endswith("</svg>"), f"SVG does not end with </svg>: {filename}"
    elif sample["format"] == "webp":
        header = out_file.read_bytes()[:12]
        assert header[:4] == b"RIFF" and header[8:12] == b"WEBP"


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_sample_code_snippet_execution(sample, tmp_path):
    """Verify that the exact copy-pasteable code snippet executes successfully."""
    _skip_missing_dependency(sample)
    filename = f"snippet_{sample['filename']}"
    out_file = tmp_path / filename

    code = sample["code"]
    scope = {"np": np, "plt": matplotvite, "matplotvite": matplotvite}
    code_mod = code.replace(f'"{sample["filename"]}"', f'"{out_file.as_posix()}"')
    exec(code_mod, scope)

    assert out_file.exists(), f"Snippet execution did not produce {filename}"
    assert out_file.stat().st_size > 0, f"Snippet produced an empty file {filename}"


def test_samples_metadata_integrity():
    """Verify uniqueness and completeness of sample definitions."""
    ids = [s["id"] for s in SAMPLES]
    filenames = [s["filename"] for s in SAMPLES]

    assert len(ids) == len(set(ids)), "Duplicate sample IDs found"
    assert len(filenames) == len(set(filenames)), "Duplicate filenames found"

    for sample in SAMPLES:
        assert sample["title"], f"Missing title in {sample['id']}"
        assert sample["category"], f"Missing category in {sample['id']}"
        assert sample["description"], f"Missing description in {sample['id']}"
        assert sample["format"] in ("png", "svg", "webp"), (
            f"Unknown format in {sample['id']}"
        )
        assert sample["filename"].endswith(f".{sample['format']}")
        assert sample["filename"] in sample["code"]
        assert sample.get("requires") in (None, "pandas")


# Every supported feature group must have a rendered example. The sample tests
# above execute each one, so this map also serves as the feature test matrix.
FEATURE_SAMPLES = {
    "line": "trigonometric_waves",
    "line_styles": "line_styles_markers",
    "step": "step_stairs",
    "stairs": "step_stairs",
    "fill_between": "fill_regions",
    "fill_betweenx": "fill_regions",
    "reference_lines": "fill_regions",
    "implicit_x": "discrete_signal",
    "axis_limits": "custom_limits",
    "scatter": "scatter_errorbar",
    "errorbar": "scatter_errorbar",
    "histogram": "histogram_density",
    "boxplot": "box_violin",
    "violinplot": "box_violin",
    "bar": "bar_labels",
    "barh": "bar_labels",
    "bar_label": "bar_labels",
    "pie": "pie_chart",
    "stackplot": "stackplot",
    "stem": "stem_signal",
    "eventplot": "event_timeline",
    "broken_barh": "broken_barh",
    "contourf": "contours_colorbar",
    "imshow": "imshow_heatmap",
    "pcolormesh": "pcolormesh",
    "hist2d": "hist2d_hexbin",
    "hexbin": "hexbin_density",
    "quiver": "quiver_field",
    "annotate": "annotations_mathtext",
    "mathtext": "annotations_mathtext",
    "text": "annotations_mathtext",
    "ticks": "ticks_grid_legend",
    "grid": "ticks_grid_legend",
    "legend": "ticks_grid_legend",
    "log_scale": "log_scales",
    "subplots": "subplots_grid",
    "subplot": "side_by_side",
    "gridspec": "gridspec_layout",
    "subplot_mosaic": "mosaic_layout",
    "twinx": "twin_axes",
    "datetime": "datetime_axis",
    "categorical": "categorical_axis",
    "pandas": "pandas_frame",
    "colormaps": "colormap_reference",
    "style": "style_context",
    "svg": "svg_export",
    "webp": "webp_export",
}


def test_gallery_covers_every_feature_group():
    """Fail when a supported feature loses its gallery example."""
    sample_ids = {sample["id"] for sample in SAMPLES}
    missing = {
        feature: sample_id
        for feature, sample_id in FEATURE_SAMPLES.items()
        if sample_id not in sample_ids
    }
    assert not missing, f"Missing gallery examples: {missing}"
