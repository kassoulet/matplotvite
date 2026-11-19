"""Tests for checked-in Matplotlib corpus metadata and change-only rendering."""

import hashlib
import json
import sys
from pathlib import Path

import matplotvite

from tools.harvest_matplotlib import harvest, harvest_gallery, main
from tools.mpl_corpus import (
    build_metadata,
    describe_diff,
    diff_metadata,
    read_metadata,
    write_metadata,
)

MODULE = '''import matplotlib.pyplot as plt


@image_comparison(["first.png"])
def test_first():
    plt.plot([0, 1], [1, 0])


@image_comparison(["second.png"])
def test_second():
    plt.plot([0, 1], [0, 1])
'''


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "matplotlib-9.9.9" / "lib" / "matplotlib" / "tests"
    images = root / "baseline_images" / "test_demo"
    images.mkdir(parents=True)
    (root / "test_demo.py").write_text(MODULE, encoding="utf-8")
    for name in ("first.png", "second.png"):
        matplotvite.close("all")
        matplotvite.plot([0, 1], [1, 0])
        matplotvite.savefig(images / name)
    matplotvite.close("all")
    return root


def test_build_metadata_records_snippets_hashes_and_version(tmp_path):
    root = make_root(tmp_path)
    metadata = build_metadata(harvest(root), root)
    assert metadata["schema"] == 1
    assert metadata["matplotlib_version"] == "9.9.9"
    record = metadata["cases"]["test_demo/test_first"]
    assert "plt.plot([0, 1], [1, 0])" in record["snippet"]
    expected = record["expected"][0]
    assert expected["path"] == "baseline_images/test_demo/first.png"
    assert expected["sha256"] == hashlib.sha256(
        (root / expected["path"]).read_bytes()).hexdigest()


def test_metadata_round_trip_is_deterministic(tmp_path):
    root = make_root(tmp_path)
    metadata = build_metadata(harvest(root), root)
    path = tmp_path / "corpus.json"
    write_metadata(path, metadata)
    assert read_metadata(path) == metadata
    original = path.read_text(encoding="utf-8")
    write_metadata(path, read_metadata(path))
    assert path.read_text(encoding="utf-8") == original


def test_diff_detects_changed_added_and_removed_cases(tmp_path):
    root = make_root(tmp_path)
    cases = harvest(root)
    old = build_metadata(cases, root)
    assert diff_metadata(cases, old, root)["clean"]

    (root / "baseline_images" / "test_demo" / "first.png").write_bytes(b"new image")
    report = diff_metadata(cases, old, root)
    assert report["changed"] == ["test_demo/test_first"]
    assert [case["id"] for case in report["cases"]] == ["test_demo/test_first"]
    assert describe_diff(report) == "0 added, 1 changed, 0 removed; version unchanged"

    module = root / "test_demo.py"
    module.write_text(MODULE.replace("test_second", "test_third"), encoding="utf-8")
    report = diff_metadata(harvest(root), old, root)
    assert report["added"] == ["test_demo/test_third"]
    assert report["removed"] == ["test_demo/test_second"]
    assert not report["clean"]


def test_cli_writes_and_checks_metadata(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    metadata = tmp_path / "corpus.json"
    monkeypatch.setattr(sys, "argv", [
        "harvest_matplotlib.py", "--source", str(root.parents[3]),
        "--write-metadata", str(metadata),
    ])
    assert main() == 0
    assert read_metadata(metadata)["cases"]

    monkeypatch.setattr(sys, "argv", [
        "harvest_matplotlib.py", "--source", str(root.parents[3]),
        "--check-metadata", str(metadata),
    ])
    assert main() == 0

    (root / "test_demo.py").write_text(MODULE.replace("test_first", "test_changed"),
                                       encoding="utf-8")
    assert main() == 1


def test_harvest_gallery_renders_only_changed_snippets(tmp_path):
    root = make_root(tmp_path)
    cases = harvest(root)
    metadata = tmp_path / "corpus.json"
    write_metadata(metadata, build_metadata(cases, root))

    module = root / "test_demo.py"
    module.write_text(
        MODULE.replace("plt.plot([0, 1], [0, 1])",
                       "plt.plot([0, 1], [0, 1])\n    plt.title('changed')"),
        encoding="utf-8")
    out = tmp_path / "gallery"
    counts = harvest_gallery(root, out, out / "manifest.json",
                             changed_from=metadata)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert counts["cases"] == 1
    assert [case["id"] for case in manifest] == ["test_demo/test_second"]
