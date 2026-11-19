"""Pixel-diff coverage for the Seaborn wrappers expressible with our API.

The references under ``tests/seaborn`` are rendered by Matplotlib from the same
scene calls defined in ``tests/seaborn_scenes.py``. The tests render those calls
through matplotvite and compare the RGBA pixels, so a change to lines, bands,
scatter, bars, histograms, boxes, images or annotations is caught even though
Seaborn itself is not a test dependency.
"""

from __future__ import annotations

import pathlib

import pytest
import seaborn_scenes
from png_utils import decode_png_rgba

GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "seaborn"
SCENES = seaborn_scenes.read_manifest()


def _pixels(path: pathlib.Path) -> tuple[int, int, bytes]:
    width, height, rows = decode_png_rgba(path.read_bytes())
    return width, height, b"".join(bytes(row) for row in rows)


def _rms(left: bytes, right: bytes) -> float:
    total = sum((a - b) ** 2 for a, b in zip(left, right))
    return (total / len(left)) ** 0.5


@pytest.mark.parametrize("name,width,height,max_rms,wrapper", SCENES,
                         ids=[scene[0] for scene in SCENES])
def test_matplotvite_matches_the_seaborn_wrapper_reference(
        name, width, height, max_rms, wrapper, tmp_path):
    assert wrapper.startswith("sns.")
    golden = GOLDEN_DIR / f"{name}.png"
    assert golden.exists(), f"missing reference {golden}; run tests/seaborn_scenes.py"
    rendered = tmp_path / f"{name}.png"
    seaborn_scenes.render(name, rendered)

    expected_width, expected_height, expected = _pixels(golden)
    actual_width, actual_height, actual = _pixels(rendered)
    assert (expected_width, expected_height) == (width, height)
    assert (actual_width, actual_height) == (width, height)
    error = _rms(expected, actual)
    assert error <= max_rms, (
        f"{name} ({wrapper}): rms {error:.3f} > {max_rms}; "
        "regenerate the reference if the change is intentional"
    )
