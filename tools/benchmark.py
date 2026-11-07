#!/usr/bin/env python3
"""Benchmark suite comparing plt_rs against matplotlib."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

import numpy as np
import plt_rs as rs_plt

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as mpl_plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def measure_callable(fn, iters: int = 25, warmup: int = 3) -> float:
    """Measure average execution time of a callable in milliseconds."""
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    return (time.perf_counter() - t0) / iters * 1000.0


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

        # 1. Scaling points (100, 1k, 10k, 100k)
        scales = [
            ("100 points", 100, iters_fast),
            ("1,000 points", 1_000, iters_fast),
            ("10,000 points", 10_000, iters_fast),
            ("100,000 points", 100_000, iters_heavy),
        ]

        for label, n, iters in scales:
            x = np.linspace(0, 10, n)
            y = np.sin(x)

            def fn_rs(x=x, y=y):
                rs_plt.figure(figsize=(6.4, 4.8))
                rs_plt.plot(x, y, label="sin", color="red")
                rs_plt.title("Scaling")
                rs_plt.xlabel("x")
                rs_plt.ylabel("y")
                rs_plt.legend()
                rs_plt.savefig(p_rs_png)
                rs_plt.close()

            def fn_mpl(x=x, y=y):
                mpl_plt.figure(figsize=(6.4, 4.8))
                mpl_plt.plot(x, y, label="sin", color="red")
                mpl_plt.title("Scaling")
                mpl_plt.xlabel("x")
                mpl_plt.ylabel("y")
                mpl_plt.legend()
                mpl_plt.savefig(p_mpl_png)
                mpl_plt.close("all")

            t_rs = measure_callable(fn_rs, iters=iters)
            t_mpl = measure_callable(fn_mpl, iters=iters)
            results.append({
                "category": "Data Scaling",
                "name": f"Single Line ({label}, PNG)",
                "points": n,
                "rs_ms": round(t_rs, 2),
                "mpl_ms": round(t_mpl, 2),
                "speedup": round(t_mpl / t_rs, 1) if t_rs > 0 else 0,
            })

        # 2. Multi-series (5 lines x 2,000 pts)
        x_multi = np.linspace(0, 10, 2000)
        lines = [np.sin(x_multi + i * 0.5) for i in range(5)]

        def fn_rs_multi():
            rs_plt.figure(figsize=(6.4, 4.8))
            for i, line in enumerate(lines):
                rs_plt.plot(x_multi, line, label=f"Series {i}")
            rs_plt.title("Multi-Series")
            rs_plt.legend()
            rs_plt.savefig(p_rs_png)
            rs_plt.close()

        def fn_mpl_multi():
            mpl_plt.figure(figsize=(6.4, 4.8))
            for i, line in enumerate(lines):
                mpl_plt.plot(x_multi, line, label=f"Series {i}")
            mpl_plt.title("Multi-Series")
            mpl_plt.legend()
            mpl_plt.savefig(p_mpl_png)
            mpl_plt.close("all")

        t_rs = measure_callable(fn_rs_multi, iters=iters_fast)
        t_mpl = measure_callable(fn_mpl_multi, iters=iters_fast)
        results.append({
            "category": "Complex Layouts",
            "name": "Multi-Series (5 lines x 2,000 pts, PNG)",
            "points": 10_000,
            "rs_ms": round(t_rs, 2),
            "mpl_ms": round(t_mpl, 2),
            "speedup": round(t_mpl / t_rs, 1) if t_rs > 0 else 0,
        })

        # 3. Subplots 2x2 grid
        x_sub = np.linspace(0, 10, 1000)
        y_sub = np.sin(x_sub)

        def fn_rs_sub():
            fig, axs = rs_plt.subplots(2, 2, figsize=(8.0, 6.0))
            for i in range(2):
                for j in range(2):
                    axs[i, j].plot(x_sub, y_sub, color="blue")
                    axs[i, j].set_title(f"Subplot {i},{j}")
            fig.savefig(p_rs_png)
            rs_plt.close()

        def fn_mpl_sub():
            fig, axs = mpl_plt.subplots(2, 2, figsize=(8.0, 6.0))
            for i in range(2):
                for j in range(2):
                    axs[i, j].plot(x_sub, y_sub, color="blue")
                    axs[i, j].set_title(f"Subplot {i},{j}")
            fig.savefig(p_mpl_png)
            mpl_plt.close("all")

        t_rs = measure_callable(fn_rs_sub, iters=iters_fast)
        t_mpl = measure_callable(fn_mpl_sub, iters=iters_fast)
        results.append({
            "category": "Complex Layouts",
            "name": "Subplots (2x2 grid, PNG)",
            "points": 4_000,
            "rs_ms": round(t_rs, 2),
            "mpl_ms": round(t_mpl, 2),
            "speedup": round(t_mpl / t_rs, 1) if t_rs > 0 else 0,
        })

        # 4. SVG export
        def fn_rs_svg():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.plot(x_sub, y_sub, label="sin", color="red")
            rs_plt.title("SVG Export")
            rs_plt.legend()
            rs_plt.savefig(p_rs_svg)
            rs_plt.close()

        def fn_mpl_svg():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.plot(x_sub, y_sub, label="sin", color="red")
            mpl_plt.title("SVG Export")
            mpl_plt.legend()
            mpl_plt.savefig(p_mpl_svg)
            mpl_plt.close("all")

        t_rs = measure_callable(fn_rs_svg, iters=iters_fast)
        t_mpl = measure_callable(fn_mpl_svg, iters=iters_fast)
        results.append({
            "category": "Vector Output",
            "name": "Vector SVG Export (1,000 pts, SVG)",
            "points": 1_000,
            "rs_ms": round(t_rs, 2),
            "mpl_ms": round(t_mpl, 2),
            "speedup": round(t_mpl / t_rs, 1) if t_rs > 0 else 0,
        })

    # 5. Cold process startup & execution
    env = dict(**os.environ, PYTHONPATH=str(ROOT / "python"))

    code_rs = "import numpy as np, plt_rs as plt; x = np.linspace(0, 10, 1000); plt.plot(x, np.sin(x)); plt.savefig('/tmp/bench_cold.png')"
    code_mpl = "import numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; x = np.linspace(0, 10, 1000); plt.plot(x, np.sin(x)); plt.savefig('/tmp/bench_cold.png')"

    def run_cold(code: str) -> float:
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-c", code], env=env, check=True, capture_output=True)
        return (time.perf_counter() - t0) * 1000.0

    cold_iters = 3 if quick else 6
    t_cold_rs = min(run_cold(code_rs) for _ in range(cold_iters))
    t_cold_mpl = min(run_cold(code_mpl) for _ in range(cold_iters))

    results.append({
        "category": "Startup & Process",
        "name": "Cold CLI Execution (Process start + plot + save)",
        "points": 1_000,
        "rs_ms": round(t_cold_rs, 1),
        "mpl_ms": round(t_cold_mpl, 1),
        "speedup": round(t_cold_mpl / t_cold_rs, 1) if t_cold_rs > 0 else 0,
    })

    # Clean up tmp file
    try:
        os.remove("/tmp/bench_cold.png")
    except OSError:
        pass

    # System metadata
    system_info = {
        "os": platform.system(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "matplotlib_version": matplotlib.__version__,
        "plt_rs_version": "0.1.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

    return {
        "system": system_info,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark plt_rs against matplotlib")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "benchmarks.json", help="Output JSON path")
    parser.add_argument("--quick", action="store_true", help="Run with fewer iterations for fast testing")
    args = parser.parse_args()

    print("Running plt.rs vs matplotlib benchmarks...")
    data = run_benchmarks(quick=args.quick)

    print("\nBenchmark Results:")
    print("-" * 78)
    print(f"{'Benchmark Name':<42} | {'plt.rs':>9} | {'matplotlib':>10} | {'Speedup':>8}")
    print("-" * 78)
    for r in data["results"]:
        print(f"{r['name']:<42} | {r['rs_ms']:>6.2f} ms | {r['mpl_ms']:>7.2f} ms | {r['speedup']:>7.1f}x")
    print("-" * 78)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote results to: {args.out}")


if __name__ == "__main__":
    main()
