"""Tests verifying that all sample use cases in examples/samples.py execute correctly."""

from pathlib import Path
import numpy as np
import pytest
from examples.samples import SAMPLES
import plt_rs


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_sample_runner_execution(sample, tmp_path):
    """Verify that each sample's runner function produces a valid image file."""
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


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_sample_code_snippet_execution(sample, tmp_path):
    """Verify that the exact copy-pasteable code snippet in the sample executes successfully."""
    filename = f"snippet_{sample['filename']}"
    out_file = tmp_path / filename

    code = sample["code"]
    # Replace savefig target with out_file
    scope = {"np": np, "plt": plt_rs, "plt_rs": plt_rs}
    # Execute snippet with filename redirected to our tmp path
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
        assert sample["format"] in ("png", "svg"), f"Unknown format in {sample['id']}"
