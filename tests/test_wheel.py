"""Smoke tests for an installed wheel, run after `pip install dist/*.whl`."""

import importlib
import io
from importlib import metadata
from pathlib import Path

import numpy as np
import pytest
import matplotvite as plt
from matplotvite import _core


def _extension_path() -> Path:
    return Path(_core.__file__)


def test_package_exposes_its_version():
    assert plt.__version__ == "0.5.0"


def test_compiled_extension_is_installed():
    path = _extension_path()
    assert path.is_file(), f"compiled extension missing: {path}"
    assert path.stat().st_size > 0
    assert path.suffix in {".so", ".pyd"}, f"unexpected extension: {path}"


def test_type_marker_and_stub_are_installed():
    package = _extension_path().parent
    assert (package / "py.typed").is_file()
    assert (package / "__init__.pyi").is_file()


def test_toolkit_shim_is_scoped_inside_matplotvite():
    package = Path(plt.__file__).parent
    assert (package / "mpl_toolkits/axes_grid1/inset_locator.py").is_file()
    # Editable installs only expose their dist-info here, not the wheel's file
    # list; the wheel-test job checks this half against a real install.
    files = [str(path) for path in metadata.files("matplotvite")]
    if "matplotvite/__init__.py" in files:
        assert not any(path.startswith("mpl_toolkits/") for path in files)


def test_bundled_font_licences_are_installed():
    files = [str(path) for path in metadata.files("matplotvite")]
    if "matplotvite/__init__.py" not in files:
        pytest.skip("editable installs do not expose the wheel's licence list")
    assert any(path.endswith("LICENSE_DEJAVU.txt") for path in files)
    assert any(path.endswith("LICENSE_GEIST_OFL.txt") for path in files)


def test_matplotlib_toolkit_namespace_is_not_shadowed():
    # Matplotlib is not a wheel-test dependency, so only check coexistence
    # when it is already installed.
    pytest.importorskip("matplotlib")
    mplot3d = importlib.import_module("mpl_toolkits.mplot3d")
    assert mplot3d.__file__


def test_installed_wheel_renders_every_format():
    plt.figure((3, 2), dpi=100)
    try:
        plt.plot(np.arange(10), np.arange(10) ** 2, label="square")
        plt.title("wheel")
        plt.legend()

        png = plt.savefig(format="png")
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert int.from_bytes(png[16:20], "big") == 300
        assert int.from_bytes(png[20:24], "big") == 200

        svg = plt.savefig(format="svg")
        assert svg.startswith(b"<svg") and b"</svg>" in svg

        pdf = plt.savefig(format="pdf")
        assert pdf.startswith(b"%PDF-") and len(pdf) > 1000

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png")
        assert buffer.getvalue() == png
    finally:
        plt.close()
