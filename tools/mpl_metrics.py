"""Pixel metrics and failure classification for harvested renders."""

from __future__ import annotations

import importlib.util
import pathlib
import re

try:
    from tools.mpl_harvest import NUMPY_ALIASES, compat_name
except ModuleNotFoundError:  # `python tools/harvest_matplotlib.py`
    from mpl_harvest import NUMPY_ALIASES, compat_name

BLANK_THRESHOLD = 50

# Gallery categories that cannot be judged from a still render: they need a

ENVIRONMENT_MODULES = frozenset({"PIL", "gi", "wx", "matplotlib"})

# Examples that import a GUI toolkit are interactive by nature. Detect them

METRIC_CONVERTERS = {
    "PIL": ("Pillow", "EPS"),
    "pypdfium2": ("pypdfium2", "PDF"),
    "cairosvg": ("cairosvg", "SVG"),
}


def report_missing_metrics_converters() -> list[str]:
    """Name the converters whose absence leaves vector baselines unscored."""
    missing = []
    for module, (package, kind) in METRIC_CONVERTERS.items():
        if importlib.util.find_spec(module) is None:
            print(f"Note: {package} is not installed; {kind} baselines get no pixel metric.")
            missing.append(package)
    return missing


def _nonwhite_pixels(path: pathlib.Path) -> int | None:
    """Sampled non-white pixel count, using the stdlib decoder in tests/."""
    try:
        from png_utils import decode_png_rgba
    except ImportError:
        helper = pathlib.Path(__file__).resolve().parents[1] / "tests" / "png_utils.py"
        spec = importlib.util.spec_from_file_location("png_utils", helper)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        decode_png_rgba = module.decode_png_rgba
    try:
        _, _, rows = decode_png_rgba(path.read_bytes())
    except Exception:
        return None
    return sum(
        min(row[i], row[i + 1], row[i + 2]) < 250
        for y, row in enumerate(rows) if y % 2 == 0
        for i in range(0, len(row), 8)
    )


FAILURE_REASONS = {
    "needs-api": "needs_api",
    "harvester-gap": "harvester",
    "bug": "bug",
    "unsupported": "out_of_scope",
}


def failure_status(error: str | None) -> str:
    """Bucket a failed render: harvester gap, missing API or bug.

    A `NameError` for a name matplotvite already exposes is the harvester's
    fault (the import line was stripped); any other undefined name, a missing
    attribute or an unimplemented option needs API work; the rest is a bug in
    a feature matplotvite claims to support.
    """
    if not error:
        return "failed"
    kind, _, detail = error.partition(":")
    if kind == "ModuleNotFoundError":
        # Only a module the harness failed to supply is a harvester gap. A
        # missing matplotvite shim is API work, and a GUI toolkit, Pillow or
        # real Matplotlib belongs to the environment, not to either.
        match = re.search(r"No module named '([^']+)'", detail)
        root = (match.group(1) if match else "").split(".")[0]
        if root in ENVIRONMENT_MODULES:
            return "unsupported"
        if root in ("matplotvite", "mpl_toolkits"):
            return "needs-api"
        return "harvester-gap"
    if kind == "NameError":
        match = re.search(r"name '([^']+)' is not defined", detail)
        name = match.group(1) if match else ""
        if name and (name in NUMPY_ALIASES or compat_name(name) is not None):
            return "harvester-gap"
        return "needs-api"
    if kind in ("AttributeError", "ImportError", "NotImplementedError"):
        return "needs-api"
    return "bug"

def metrics(baseline: pathlib.Path, ours: pathlib.Path) -> dict[str, object]:
    """RMS and visibly-different percentage against the baseline PNG.

    The comparison reads PNGs through Matplotlib, which the renderer itself does
    not need; without it the gallery still renders and records why the metric is
    unavailable.
    """
    if not baseline.exists():
        return {"error": f"missing baseline {baseline}"}
    try:  # same metric as the gallery tool; importable both as a script and as a package
        try:
            from visual_compare import compare_images
        except ModuleNotFoundError:
            from tools.visual_compare import compare_images
        return compare_images(baseline, ours)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
