"""Tests for the CI job summary of the harvested galleries."""

import json
import sys

import pytest

from tools.gallery_summary import main as gallery_summary

MANIFESTS = {
    "mpl-corpus": [{"status": "rendered"}, {"status": "rendered"},
                   {"status": "failed"}, {"status": "unsupported"},
                   {"status": "no baseline"}],
    "mpl-examples": [{"status": "rendered"}, {"status": "failed"}],
    "seaborn-gallery": [{"status": "needs-api"}, {"status": "pass"}],
}


def test_summary_counts_each_gallery_and_links_the_artifact(tmp_path, monkeypatch, capsys):
    for directory, cases in MANIFESTS.items():
        gallery = tmp_path / directory
        gallery.mkdir()
        (gallery / "manifest.json").write_text(json.dumps(cases), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "gallery_summary", "--out", str(tmp_path),
        "--artifact-url", "https://example.test/artifact"])
    assert gallery_summary() == 0
    out = capsys.readouterr().out

    assert "## Comparison galleries" in out
    assert "| Matplotlib baseline images | 5 | 2 | 0 | 1 | 1 | 0 | 1 |" in out
    assert "| Matplotlib gallery examples | 2 | 1 | 0 | 1 | 0 | 0 | 0 |" in out
    assert "| Seaborn examples | 2 | 0 | 1 | 0 | 0 | 1 | 0 |" in out
    assert "`mpl-corpus/index.html`" in out
    assert "[Download the galleries artifact](https://example.test/artifact)" in out
    assert "9 cases across 3 galleries." in out


def test_summary_rejects_a_missing_gallery(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["gallery_summary", "--out", str(tmp_path)])
    with pytest.raises(FileNotFoundError):
        gallery_summary()
