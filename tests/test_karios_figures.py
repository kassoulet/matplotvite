"""Regression tests for the KARIOS report figures.

The figure builders live in `examples/karios_figures.py` so the generated site
and these tests render exactly the same layouts. The assertions guard against
crashes and empty renders; the final layouts are checked visually.

    python tests/test_karios_figures.py [out_dir]  # writes 01_overview.png etc.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.karios_figures import make_data, overview, shift_by_row_col


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
