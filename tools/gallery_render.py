#!/usr/bin/env python3
"""Render the gallery, comparison and benchmark assets for the static site.

This module owns everything that needs a live plotting backend: running the
sample snippets, timing them, rendering the matplotlib comparisons, the scaling
chart and the KARIOS figures. It writes `samples.json` beside the images, so
`tools/build_pages.py` can build the HTML from that data without importing
matplotlib or re-rendering anything.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# The in-tree sources are only a fallback: when a matplotvite is installed (the
# wheel test job installs one) it must win, because the checkout has no compiled
# extension to import from `python/`.
if importlib.util.find_spec("matplotvite") is None and str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

import matplotvite
import numpy as np

from examples.karios_figures import make_data, overview, shift_by_row_col
from examples.samples import SAMPLES

try:
    from tools import snippet_runner as _snippet_runner
except ModuleNotFoundError:  # `python tools/gallery_render.py`
    import snippet_runner as _snippet_runner

SAMPLES_FILE = "samples.json"

# The page templates need these fields; callables and import requirements stay
# in Python and are deliberately not serialised.
SAMPLE_FIELDS = (
    "id",
    "title",
    "description",
    "category",
    "filename",
    "format",
    "code",
    "file_size",
    "rs_ms",
    "mpl_filename",
    "mpl_ms",
)


def format_bytes(size: int) -> str:
    """Format a file size in binary units."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


def format_ms(milliseconds: float) -> str:
    """Format a wall-clock duration with a readable number of digits."""
    if milliseconds < 10.0:
        return f"{milliseconds:.2f} ms"
    return f"{milliseconds:.1f} ms"


def measure_render_ms(render: Callable[[], None], repeats: int = 3) -> float:
    """Return the fastest of `repeats` wall-clock renders, in milliseconds."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        render()
        best = min(best, (time.perf_counter() - start) * 1000.0)
    return best


def render_matplotlib_sample(sample: dict[str, object], out_path: Path) -> None:
    """Execute a gallery snippet with matplotlib's Agg backend."""
    import matplotlib

    matplotlib.use("Agg")
    filename = str(sample["filename"])
    code = str(sample["code"]).replace(
        "import matplotvite as plt", "import matplotlib.pyplot as plt"
    )
    code = code.replace(f'"{filename}"', f'"{out_path.as_posix()}"')
    code += "\nplt.close('all')\n"
    # Timings need the snippet in this process, without a child startup cost.
    _snippet_runner.execute(code, {})


def render_scaling_chart(out_path: Path, results: list[dict[str, object]]) -> None:
    """Render the latency-scaling chart with matplotvite itself."""
    scaling = [r for r in results if r.get("category") == "Data Scaling"]
    points = np.array([r["points"] for r in scaling], dtype=np.float64)
    latencies = np.array([r["rs_ms"] for r in scaling], dtype=np.float64)

    matplotvite.figure(figsize=(7.8, 4.4))
    matplotvite.plot(
        np.log10(points),
        latencies,
        label="Matplotvite latency",
        color="#1f4e79",
        marker="o",
        markersize=4,
    )
    matplotvite.plot(
        np.log10(points),
        [0.44, 0.44, 0.44, 0.44],
        label="0.5 ms reference",
        color="#8a97a8",
        linestyle="--",
        linewidth=1.0,
    )
    matplotvite.title("Latency scaling with input size")
    matplotvite.xlabel("log10(points)")
    matplotvite.ylabel("Time to disk (ms)")
    matplotvite.grid(True, linestyle=":", alpha=0.4)
    matplotvite.legend(frameon=False, loc="upper left")
    matplotvite.savefig(str(out_path))
    matplotvite.close()


def _sample_record(sample: dict[str, object]) -> dict[str, object]:
    """Keep only the JSON-serialisable metadata the HTML templates read."""
    return {key: sample[key] for key in SAMPLE_FIELDS if key in sample}


def _render_samples(out_dir: Path) -> list[dict[str, object]]:
    """Run every available sample, timing a second in-process render."""
    samples_info: list[dict[str, object]] = []
    for sample in SAMPLES:
        requires = sample.get("requires")
        if requires and importlib.util.find_spec(str(requires)) is None:
            print(f"  Skipping [{sample['id']}]: requires {requires}")
            continue

        filename = str(sample["filename"])
        target_path = out_dir / filename
        print(f"  Rendering [{sample['id']}] -> {filename} ...", end=" ", flush=True)
        sample["runner"](str(target_path))
        size = target_path.stat().st_size
        rs_ms = measure_render_ms(
            lambda sample=sample, target_path=target_path: (
                sample["runner"](str(target_path)), matplotvite.close())
        )
        print(f"done ({format_bytes(size)}, {format_ms(rs_ms)})")

        info = dict(sample)
        info["file_size"] = format_bytes(size)
        info["rs_ms"] = rs_ms
        samples_info.append(info)
    return samples_info


def _render_comparisons(samples_info: list[dict[str, object]], out_dir: Path) -> bool:
    """Render each snippet with matplotlib's Agg backend for the comparison page."""
    mpl_available = importlib.util.find_spec("matplotlib") is not None
    comparison_dir = out_dir / "comparison"
    comparison_dir.mkdir(parents=True, exist_ok=True)
    for sample in samples_info:
        sample["mpl_filename"] = None
        if not mpl_available or sample["format"] == "webp":
            continue
        suffix = Path(str(sample["filename"])).suffix
        mpl_filename = f"{Path(str(sample['filename'])).stem}-matplotlib{suffix}"
        target = comparison_dir / mpl_filename
        print(f"  Rendering matplotlib comparison [{sample['id']}] ...", end=" ", flush=True)
        try:
            render_matplotlib_sample(sample, target)
            sample["mpl_ms"] = measure_render_ms(
                lambda sample=sample, target=target: render_matplotlib_sample(sample, target)
            )
            sample["mpl_filename"] = mpl_filename
            print(f"done ({format_ms(float(sample['mpl_ms']))})")
        except Exception as exc:  # pragma: no cover - backend-specific fallback
            sample.pop("mpl_ms", None)
            print(f"skipped ({exc})")
    return mpl_available


def _render_karios(out_dir: Path) -> None:
    """Render the KARIOS report figures used by karios.html."""
    karios_dir = out_dir / "karios"
    karios_dir.mkdir(parents=True, exist_ok=True)
    data = make_data()
    print("Rendering KARIOS report figures ...")
    overview(karios_dir / "01_overview.png", data)
    shift_by_row_col(karios_dir / "02_dx.png", "dx", data)
    shift_by_row_col(karios_dir / "03_dy.png", "dy", data)


def render_gallery(out_dir: Path) -> dict[str, object]:
    """Render every site image and write `samples.json` for the HTML step."""
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Rendering gallery assets in: {out_dir}")

    samples_info = _render_samples(out_dir)
    (out_dir / ".nojekyll").touch()
    mpl_available = _render_comparisons(samples_info, out_dir)

    bench_data_path = ROOT / "tools" / "benchmarks_data.json"
    if bench_data_path.exists():
        bench_data = json.loads(bench_data_path.read_text(encoding="utf-8"))
    else:
        bench_data = {"system": {}, "results": []}

    scaling_chart_path = out_dir / "benchmark_scaling.png"
    render_scaling_chart(scaling_chart_path, bench_data.get("results", []))
    print(f"Wrote scaling chart -> {scaling_chart_path}")

    _render_karios(out_dir)

    data = {
        "samples": [_sample_record(sample) for sample in samples_info],
        "mpl_available": mpl_available,
        "benchmark": bench_data,
    }
    samples_path = out_dir / SAMPLES_FILE
    samples_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote render data -> {samples_path}")
    return data


def load_render_data(out_dir: Path) -> dict[str, object]:
    """Load the metadata written by `render_gallery`."""
    path = out_dir / SAMPLES_FILE
    if not path.exists():
        raise SystemExit(
            f"{path} is missing; run `python tools/gallery_render.py --out {out_dir}` first"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the static-site gallery assets.")
    parser.add_argument("--out", type=Path, default=ROOT / "dist",
                        help="Output directory (default: dist)")
    args = parser.parse_args(argv)
    render_gallery(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
