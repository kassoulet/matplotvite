"""Checks that the source distribution contains only build-required files."""

import importlib.util
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _build_sdist(tmp_path: Path) -> Path:
    if importlib.util.find_spec("maturin") is None:
        pytest.skip("maturin is not installed")
    subprocess.run(
        [sys.executable, "-m", "maturin", "sdist", "--out", str(tmp_path)],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    archives = list(tmp_path.glob("*.tar.gz"))
    assert len(archives) == 1, archives
    return archives[0]


def test_sdist_is_buildable_and_excludes_development_trees(tmp_path):
    archive = _build_sdist(tmp_path)
    with tarfile.open(archive) as tar:
        names = [name.split("/", 1)[1] for name in tar.getnames() if "/" in name]
        dirs = {name.split("/", 1)[0] for name in names}

        for required in (
            "Cargo.toml",
            "Cargo.lock",
            "pyproject.toml",
            "src/fonts.rs",
            "python/matplotvite/__init__.py",
            "assets/fonts/DejaVuSans.ttf",
            "assets/fonts/DejaVuSans-Bold.ttf",
            "assets/fonts/GeistSerif-Regular.ttf",
            "assets/fonts/GeistMono-Regular.ttf",
            "assets/fonts/LICENSE_DEJAVU.txt",
            "assets/fonts/LICENSE_GEIST_OFL.txt",
        ):
            assert required in names, required

        assert not dirs & {"benches", "tools", ".github", ".jules", ".freebuff"}
        assert "review.md" not in names
