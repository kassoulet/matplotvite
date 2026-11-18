"""Contract test between the Python panel payload and the Rust model."""

import re
from pathlib import Path

import matplotvite as plt

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src" / "model.rs"


def _rust_fields(struct: str) -> set[str]:
    source = MODEL.read_text(encoding="utf-8")
    marker = f"pub(crate) struct {struct} {{"
    assert marker in source, f"missing Rust struct {struct}"
    body = source.split(marker, 1)[1].split("\n}", 1)[0]
    fields = set()
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith(("//", "#[")):
            continue
        match = re.match(r"(?:pub(?:\([^)]*\))?\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
        if match:
            fields.add(match.group(1))
    assert fields, f"could not parse fields for {struct}"
    return fields


def test_panel_payload_matches_rust_model():
    fig, ax = plt.subplots()
    try:
        panel = dict(ax._panel())
    finally:
        plt.close(fig)
    # Figure.savefig adds the fingerprint immediately before rendering.
    panel["cache_key"] = ""

    assert set(panel) == _rust_fields("Panel")
    assert set(panel["legend"]) == _rust_fields("Legend")
    assert set(panel["grid"]) == _rust_fields("Grid")
    assert set(panel["ticks"]) == _rust_fields("Ticks")
