"""Regenerate the full comparison galleries from local checkouts.

Excluded from the default run by tests/conftest.py: a full pass renders over a
thousand snippets and needs sources that the repository does not vendor. Run
with `pytest -m gallery` (or `pytest --galleries`), and fetch the sources first:

  pip download --no-binary :all: --no-deps matplotlib==3.11.2 -d dist/sdist
  mkdir -p dist/mpl-sdist && tar -xzf dist/sdist/matplotlib-3.11.2.tar.gz -C dist/mpl-sdist
  git clone --depth 1 --filter=blob:none --sparse -b v3.11.2 \\
      https://github.com/matplotlib/matplotlib dist/mpl-src
  git -C dist/mpl-src sparse-checkout set galleries/examples
  git clone --depth 1 --filter=blob:none --sparse \\
      https://github.com/mwaskom/seaborn dist/sns-src
  git -C dist/sns-src sparse-checkout set examples
"""

import json
import pathlib

import pytest

from tools.harvest_matplotlib import (find_examples_root, find_tests_root,
                                      harvest_examples_gallery, harvest_gallery)
from tools.harvest_seaborn import find_examples_root as find_seaborn_examples
from tools.harvest_seaborn import harvest as harvest_seaborn
from tools.harvest_seaborn import write_gallery

pytestmark = pytest.mark.gallery

MPL_SRC = pathlib.Path("dist/mpl-src")
SNS_SRC = pathlib.Path("dist/sns-src")


def test_regenerate_baseline_gallery(tmp_path):
    tests_root = find_tests_root(None)
    if tests_root is None:
        pytest.skip("no Matplotlib baseline images under dist/mpl-sdist; see this "
                    "module's docstring for the download command")
    out = tmp_path / "mpl-corpus"
    counts = harvest_gallery(tests_root, out, out / "manifest.json")
    assert counts["cases"] > 400
    assert counts["rendered"] > 0
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "<table" in index
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == counts["cases"]


def test_regenerate_examples_gallery(tmp_path):
    if find_examples_root(MPL_SRC) is None:
        pytest.skip(f"no Matplotlib gallery examples under {MPL_SRC}; see this "
                    "module's docstring for the sparse-checkout command")
    out = tmp_path / "mpl-examples"
    assert harvest_examples_gallery(MPL_SRC, out, out / "manifest.json") == 0
    cases = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(cases) > 400
    assert any(case["status"] == "rendered" for case in cases)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "examples rendered" in index


def test_regenerate_seaborn_gallery(tmp_path):
    examples = find_seaborn_examples(SNS_SRC)
    if examples is None:
        pytest.skip(f"no Seaborn examples under {SNS_SRC}; see this module's "
                    "docstring for the sparse-checkout command")
    cases = harvest_seaborn(examples)
    counts = write_gallery(cases, tmp_path)
    assert sum(counts.values()) == len(cases) > 0
    assert (tmp_path / "manifest.json").exists()
    assert "<table" in (tmp_path / "index.html").read_text(encoding="utf-8")
