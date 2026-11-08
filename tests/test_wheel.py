"""Smoke tests for an installed wheel, run after `pip install dist/*.whl`."""

import io
from pathlib import Path

import numpy as np
import matplotvite as plt
from matplotvite import _core


def _extension_path() -> Path:
    return Path(_core.__file__)


def test_package_exposes_its_version():
    assert plt.__version__ == "0.1.0"


def test_compiled_extension_is_installed():
    path = _extension_path()
    assert path.is_file(), f"compiled extension missing: {path}"
    assert path.stat().st_size > 0
    assert path.suffix in {".so", ".pyd"}, f"unexpected extension: {path}"


def test_type_marker_and_stub_are_installed():
    package = _extension_path().parent
    assert (package / "py.typed").is_file()
    assert (package / "__init__.pyi").is_file()


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
