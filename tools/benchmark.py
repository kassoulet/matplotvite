#!/usr/bin/env python3
"""Benchmark suite comparing matplotvite against matplotlib."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import time
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# The in-tree sources are only a fallback: when a matplotvite is installed (the
# wheel test job installs one) it must win, because the checkout has no compiled
# extension to import from `python/`.
if find_spec("matplotvite") is None and str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

import matplotvite as rs_plt

try:
    import matplotlib
    matplotlib.use("Agg")
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

from tools.benchmark_cases import (
    cold_startup,
    measure_callable,
    multi_series,
    plot_types,
    scaling,
    subplot_grid,
    svg_export,
)

__all__ = ["measure_callable", "run_benchmarks"]


def run_benchmarks(quick: bool = False) -> dict[str, object]:
    """Run full benchmark matrix."""
    if not HAS_MPL:
        raise RuntimeError("matplotlib is required to run the comparison benchmark suite")

    iters_fast = 10 if quick else 30
    iters_heavy = 5 if quick else 12

    results: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory() as tmp:
        p_rs_png = os.path.join(tmp, "rs.png")
        p_mpl_png = os.path.join(tmp, "mpl.png")
        p_rs_svg = os.path.join(tmp, "rs.svg")
        p_mpl_svg = os.path.join(tmp, "mpl.svg")

        paths = {"rs_png": p_rs_png, "mpl_png": p_mpl_png,
                 "rs_svg": p_rs_svg, "mpl_svg": p_mpl_svg}
        scaling(results, paths, iters_fast, iters_heavy)
        multi_series(results, paths, iters_fast, iters_heavy)
        subplot_grid(results, paths, iters_fast, iters_heavy)
        svg_export(results, paths, iters_fast, iters_heavy)

    cold_startup(results, quick)
    plot_types(results, iters_fast, iters_heavy, quick)

    # System metadata
    system_info = {
        "os": platform.system(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "matplotlib_version": matplotlib.__version__,
        "matplotvite_version": rs_plt.__version__,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

    return {
        "system": system_info,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark matplotvite against matplotlib")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "benchmarks.json", help="Output JSON path")
    parser.add_argument("--quick", action="store_true", help="Run with fewer iterations for fast testing")
    args = parser.parse_args()

    print("Running Matplotvite vs matplotlib benchmarks...")
    data = run_benchmarks(quick=args.quick)

    print("\nBenchmark Results:")
    print("-" * 78)
    print(f"{'Benchmark Name':<42} | {'Matplotvite':>9} | {'matplotlib':>10} | {'Speedup':>8}")
    print("-" * 78)
    for r in data["results"]:
        print(f"{r['name']:<42} | {r['rs_ms']:>6.2f} ms | {r['mpl_ms']:>7.2f} ms | {r['speedup']:>7.1f}x")
    print("-" * 78)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote results to: {args.out}")


if __name__ == "__main__":
    main()
