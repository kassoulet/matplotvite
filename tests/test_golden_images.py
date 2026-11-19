"""Golden-image parity between the Python facade and the native Rust builder.

Both this test and ``tests/golden.rs`` render the scenes listed in
``tests/golden/scenes.txt`` and compare against the committed PNGs. A rendering
change that only updates one front end therefore fails one of the two suites.
"""

from __future__ import annotations

import pathlib

import golden_scenes
import pytest

from tools.visual_compare import compare_images

GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"
SCENES = golden_scenes.read_manifest()


@pytest.mark.parametrize("name,width,height,max_rms", SCENES, ids=[s[0] for s in SCENES])
def test_python_matches_golden(name, width, height, max_rms, tmp_path):
    golden = GOLDEN_DIR / f"{name}.png"
    assert golden.exists(), f"missing golden {golden}; run tests/golden_scenes.py"
    rendered = tmp_path / f"{name}.png"
    golden_scenes.render(name, rendered)

    metrics = compare_images(golden, rendered)
    assert metrics["shape_match"], f"{name}: rendered size differs from the golden"
    assert metrics["rms"] <= max_rms, (
        f"{name}: rms {metrics['rms']} > {max_rms}; "
        "regenerate the golden if the change is intentional"
    )

    from png_utils import decode_png_rgba

    assert decode_png_rgba(golden.read_bytes())[:2] == (width, height)
