#!/usr/bin/env python3
"""Benchmark suite comparing matplotvite against matplotlib."""

from __future__ import annotations

import argparse
from importlib.util import find_spec
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
# The in-tree sources are only a fallback: when a matplotvite is installed (the
# wheel test job installs one) it must win, because the checkout has no compiled
# extension to import from `python/`.
if find_spec("matplotvite") is None and str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

import numpy as np
import matplotvite as rs_plt

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
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "python")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "bench_cold.png"
        save = f"plt.savefig({str(out)!r})"
        code_rs = f"import numpy as np, matplotvite as plt; x = np.linspace(0, 10, 1000); plt.plot(x, np.sin(x)); {save}"
        code_mpl = f"import numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; x = np.linspace(0, 10, 1000); plt.plot(x, np.sin(x)); {save}"

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

    # 6. Additional plot types
    def compare(category: str, name: str, points: int, fn_rs, fn_mpl, iters: int = iters_fast):
        t_rs = measure_callable(fn_rs, iters=iters)
        t_mpl = measure_callable(fn_mpl, iters=iters)
        results.append({
            "category": category,
            "name": name,
            "points": points,
            "rs_ms": round(t_rs, 2),
            "mpl_ms": round(t_mpl, 2),
            "speedup": round(t_mpl / t_rs, 1) if t_rs > 0 else 0,
        })

    with tempfile.TemporaryDirectory() as tmp:
        stat_rs = os.path.join(tmp, "stat_rs.png")
        stat_mpl = os.path.join(tmp, "stat_mpl.png")
        p_rs_pdf = os.path.join(tmp, "rs.pdf")
        p_mpl_pdf = os.path.join(tmp, "mpl.pdf")

        rng = np.random.default_rng(42)
        scatter_x = rng.normal(size=5_000)
        scatter_y = 0.5 * scatter_x + rng.normal(size=5_000)

        def fn_rs_scatter():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.scatter(scatter_x, scatter_y, s=8, c=scatter_x,
                           cmap="viridis", alpha=0.7)
            rs_plt.title("Scatter")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_scatter():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.scatter(scatter_x, scatter_y, s=8, c=scatter_x,
                            cmap="viridis", alpha=0.7)
            mpl_plt.title("Scatter")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Statistical", "Scatter (5,000 points, PNG)", 5_000,
                fn_rs_scatter, fn_mpl_scatter)

        categories = [f"item {i}" for i in range(20)]
        bar_values = rng.uniform(1.0, 10.0, len(categories))

        def fn_rs_bar():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.bar(categories, bar_values, color="#4c72b0")
            rs_plt.title("Bars")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_bar():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.bar(categories, bar_values, color="#4c72b0")
            mpl_plt.title("Bars")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Categorical", "Bar chart (20 categories, PNG)", 20,
                fn_rs_bar, fn_mpl_bar)

        samples = rng.normal(size=5_000)

        def fn_rs_hist():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.hist(samples, bins=40, density=True, color="#55a868")
            rs_plt.title("Histogram")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_hist():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.hist(samples, bins=40, density=True, color="#55a868")
            mpl_plt.title("Histogram")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Statistical", "Histogram (5,000 samples, PNG)", 5_000,
                fn_rs_hist, fn_mpl_hist)

        groups = [rng.normal(i * 0.4, 1.0, 200) for i in range(5)]

        def fn_rs_box():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.boxplot(groups, patch_artist=True)
            rs_plt.title("Box plots")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_box():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.boxplot(groups, patch_artist=True)
            mpl_plt.title("Box plots")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Statistical", "Box plots (5 groups, PNG)", 1_000,
                fn_rs_box, fn_mpl_box)

        def fn_rs_violin():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.violinplot(groups, showmeans=True, showmedians=True)
            rs_plt.title("Violin plots")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_violin():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.violinplot(groups, showmeans=True, showmedians=True)
            mpl_plt.title("Violin plots")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Statistical", "Violin plots (5 groups, PNG)", 1_000,
                fn_rs_violin, fn_mpl_violin)

        grid_axis = np.linspace(-3, 3, 160)
        grid_z = np.exp(-(grid_axis[None, :] ** 2 + grid_axis[:, None] ** 2))
        grid_x, grid_y = np.meshgrid(grid_axis, grid_axis)

        def fn_rs_contour():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.contourf(grid_axis, grid_axis, grid_z, levels=12,
                            cmap="viridis")
            rs_plt.title("Contours")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_contour():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.contourf(grid_axis, grid_axis, grid_z, levels=12,
                             cmap="viridis")
            mpl_plt.title("Contours")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Gridded", "Filled contours (160x160, PNG)", 25_600,
                fn_rs_contour, fn_mpl_contour)

        image_z = np.sin(grid_x * 2.0) * np.cos(grid_y * 1.5)

        def fn_rs_image():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.imshow(image_z, cmap="magma", aspect="auto")
            rs_plt.title("Image")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_image():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.imshow(image_z, cmap="magma", aspect="auto")
            mpl_plt.title("Image")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Gridded", "Image heatmap (160x160, PNG)", 25_600,
                fn_rs_image, fn_mpl_image)

        def fn_rs_mesh():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.pcolormesh(grid_axis, grid_axis, image_z, cmap="magma")
            rs_plt.title("Quad mesh")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_mesh():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.pcolormesh(grid_axis, grid_axis, image_z, cmap="magma")
            mpl_plt.title("Quad mesh")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Gridded", "Quad mesh (160x160, PNG)", 25_600,
                fn_rs_mesh, fn_mpl_mesh)

        def fn_rs_hist2d():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.hist2d(scatter_x, scatter_y, bins=32, cmap="viridis")
            rs_plt.title("2-D histogram")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_hist2d():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.hist2d(scatter_x, scatter_y, bins=32, cmap="viridis")
            mpl_plt.title("2-D histogram")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Gridded", "2-D histogram (5,000 points, PNG)", 5_000,
                fn_rs_hist2d, fn_mpl_hist2d)

        def fn_rs_hexbin():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.hexbin(scatter_x, scatter_y, gridsize=30, cmap="magma")
            rs_plt.title("Hexagonal bins")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_hexbin():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.hexbin(scatter_x, scatter_y, gridsize=30, cmap="magma")
            mpl_plt.title("Hexagonal bins")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Gridded", "Hexagonal bins (5,000 points, PNG)", 5_000,
                fn_rs_hexbin, fn_mpl_hexbin)

        quiver_axis = np.linspace(-2, 2, 24)
        quiver_x, quiver_y = np.meshgrid(quiver_axis, quiver_axis)

        def fn_rs_quiver():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.quiver(quiver_x, quiver_y, -quiver_y, quiver_x,
                          color="#1f77b4")
            rs_plt.axis("equal")
            rs_plt.title("Vector field")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_quiver():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.quiver(quiver_x, quiver_y, -quiver_y, quiver_x,
                           color="#1f77b4")
            mpl_plt.axis("equal")
            mpl_plt.title("Vector field")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Gridded", "Vector field (24x24, PNG)", 576,
                fn_rs_quiver, fn_mpl_quiver)

        from datetime import datetime, timedelta
        dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(365)]
        daily = np.cumsum(rng.normal(0.0, 0.5, len(dates)))

        def fn_rs_dates():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.plot(dates, daily, color="#4c72b0")
            rs_plt.title("Daily values")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_dates():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.plot(dates, daily, color="#4c72b0")
            mpl_plt.title("Daily values")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Data types", "Datetime axis (365 points, PNG)", 365,
                fn_rs_dates, fn_mpl_dates)

        def fn_rs_pdf():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.plot(x_sub, y_sub, color="#c44e52")
            rs_plt.title("PDF export")
            rs_plt.savefig(p_rs_pdf)
            rs_plt.close()

        def fn_mpl_pdf():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.plot(x_sub, y_sub, color="#c44e52")
            mpl_plt.title("PDF export")
            mpl_plt.savefig(p_mpl_pdf)
            mpl_plt.close("all")

        compare("Vector Output", "Vector PDF Export (1,000 pts, PDF)", 1_000,
                fn_rs_pdf, fn_mpl_pdf)

        # Dense lines stress the vector writer; filled bands stress the
        # rasteriser, so each gets its own scaling point.
        big_x = np.linspace(0, 10, 100_000)
        big_y = np.sin(big_x)
        big_rs_svg = os.path.join(tmp, "big_rs.svg")
        big_mpl_svg = os.path.join(tmp, "big_mpl.svg")

        def fn_rs_big_svg():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.plot(big_x, big_y)
            rs_plt.savefig(big_rs_svg)
            rs_plt.close()

        def fn_mpl_big_svg():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.plot(big_x, big_y)
            mpl_plt.savefig(big_mpl_svg)
            mpl_plt.close("all")

        compare("Vector Output", "Single Line (100,000 points, SVG)", 100_000,
                fn_rs_big_svg, fn_mpl_big_svg, iters=iters_heavy)

        def fn_rs_contour_lines():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.contour(grid_axis, grid_axis, grid_z, levels=12,
                           cmap="viridis")
            rs_plt.title("Contour lines")
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_contour_lines():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.contour(grid_axis, grid_axis, grid_z, levels=12,
                            cmap="viridis")
            mpl_plt.title("Contour lines")
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Gridded", "Contour lines (160x160, 12 levels, PNG)", 25_600,
                fn_rs_contour_lines, fn_mpl_contour_lines)

        scatter_big_x = rng.normal(size=50_000)
        scatter_big_y = 0.5 * scatter_big_x + rng.normal(size=50_000)

        def fn_rs_scatter_big():
            rs_plt.figure(figsize=(6.4, 4.8))
            rs_plt.scatter(scatter_big_x, scatter_big_y, s=4, alpha=0.6)
            rs_plt.savefig(stat_rs)
            rs_plt.close()

        def fn_mpl_scatter_big():
            mpl_plt.figure(figsize=(6.4, 4.8))
            mpl_plt.scatter(scatter_big_x, scatter_big_y, s=4, alpha=0.6)
            mpl_plt.savefig(stat_mpl)
            mpl_plt.close("all")

        compare("Statistical", "Scatter (50,000 points, PNG)", 50_000,
                fn_rs_scatter_big, fn_mpl_scatter_big, iters=iters_heavy)

        cached_rs = os.path.join(tmp, "cached_rs.png")
        cached_mpl = os.path.join(tmp, "cached_mpl.png")
        rs_fig = rs_plt.figure(figsize=(6.4, 4.8))
        rs_plt.plot(x_sub, y_sub, label="sin")
        rs_plt.legend()
        rs_fig.savefig(cached_rs)
        mpl_fig = mpl_plt.figure(figsize=(6.4, 4.8))
        mpl_plt.plot(x_sub, y_sub, label="sin")
        mpl_plt.legend()
        mpl_fig.savefig(cached_mpl)

        t_rs = measure_callable(lambda: rs_fig.savefig(cached_rs), iters=iters_fast)
        t_mpl = measure_callable(lambda: mpl_fig.savefig(cached_mpl), iters=iters_fast)
        mpl_plt.close("all")
        results.append({
            "category": "Repeated Output",
            "name": "Repeated savefig (unchanged figure, PNG)",
            "points": 1_000,
            "rs_ms": round(t_rs, 2),
            "mpl_ms": round(t_mpl, 2),
            "speedup": round(t_mpl / t_rs, 1) if t_rs > 0 else 0,
        })

    # System metadata
    system_info = {
        "os": platform.system(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "matplotlib_version": matplotlib.__version__,
        "matplotvite_version": "0.6.1-dev",
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
