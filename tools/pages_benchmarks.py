"""Benchmark report HTML."""

from __future__ import annotations

import html

import matplotvite

from tools.pages_assets import shared_navbar
from tools.pages_common import commit_link_html, speedup_label
from tools.pages_report_styles import benchmark_css
from tools.pages_styles import shared_css


def generate_benchmarks_html(bench_data: dict[str, object]) -> str:
    """Generate benchmarks.html from benchmark data."""
    sys_info = bench_data.get("system", {})
    results = bench_data.get("results", [])

    def find(needle: str):
        return next((r for r in results if needle in str(r.get("name", ""))), None)

    png_1k = find("1,000 points") or find("1k")
    svg = find("SVG")
    cold = find("Cold CLI")

    def metric(label, result, detail=""):
        if result:
            value = f"{result['rs_ms']:.2f} ms"
            detail = f"matplotlib {result['mpl_ms']:.2f} ms"
        else:
            value = "n/a"
        return f"""
        <div class="metric-card">
          <p class="metric-label">{html.escape(label)}</p>
          <p class="metric-value">{html.escape(value)}</p>
          <p class="metric-detail">{html.escape(detail)}</p>
        </div>"""

    metric_cards = "".join(
        [
            metric("PNG, 1,000 points", png_1k),
            metric("SVG export, 1,000 points", svg),
            metric("Cold process, plot, and save", cold),
        ]
    )

    rows = []
    for result in results:
        rs_ms = float(result["rs_ms"])
        mpl_ms = float(result["mpl_ms"])
        best = max(rs_ms, mpl_ms)
        rows.append(
            f"""
        <div class="benchmark-row">
          <div>
            <span class="bench-category">{html.escape(str(result.get('category', 'Rendering')))}</span>
            <span class="bench-title">{html.escape(str(result['name']))}</span>
          </div>
          <div class="bar-pair">
            <div class="bar-track"><div class="bar-fill matplotvite" style="width:{rs_ms / best * 100:.1f}%"></div></div>
            <div class="bar-label">Matplotvite {rs_ms:.2f} ms</div>
            <div class="bar-track"><div class="bar-fill matplotlib" style="width:{mpl_ms / best * 100:.1f}%"></div></div>
            <div class="bar-label">matplotlib {mpl_ms:.2f} ms</div>
          </div>
          <div class="bench-speedup">{speedup_label(float(result['speedup']))}</div>
        </div>"""
        )
    comparison_rows = "\n".join(rows)

    table_rows = []
    for result in results:
        table_rows.append(
            f"""
          <tr>
            <td>{html.escape(str(result['name']))}</td>
            <td class="category-label">{html.escape(str(result.get('category', 'General')))}</td>
            <td class="num">{int(result.get('points', 0)):,}</td>
            <td class="num">{float(result['rs_ms']):.2f}</td>
            <td class="num">{float(result['mpl_ms']):.2f}</td>
            <td class="num">{float(result['speedup']):.1f}×</td>
          </tr>"""
        )
    table_html = "\n".join(table_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Matplotvite — Performance measurements</title>
  <meta name="description" content="Measured end-to-end latency for Matplotvite and matplotlib on static plotting workloads, with the benchmark method and environment.">
  <style>
    {shared_css()}
    {benchmark_css()}
  </style>
</head>
<body>

  {shared_navbar("benchmarks")}

  <header class="hero benchmarks-hero">
    <p class="hero-kicker">Measured performance</p>
    <h1 class="hero-title">Static rendering benchmarks</h1>
    <p class="hero-subtitle">
      End-to-end wall-clock time for data transfer, layout, rasterization or
      vector serialization, and writing the output file. Measurements compare
      Matplotvite with matplotlib's Agg backend on the same figures and data.
    </p>
    <ul class="hero-meta">
      <li>Single Linux x86_64 host</li>
      <li>Identical figure dimensions and datasets</li>
      <li>Results are machine- and load-dependent</li>
    </ul>
  </header>

  <main class="benchmarks-container">
    <div class="metric-grid">{metric_cards}
    </div>

    <section class="section-block">
      <h2 class="block-title">End-to-end latency</h2>
      <p class="block-desc">
        Each bar is the measured latency for one scenario. The speedup column
        reports the matplotlib time divided by the Matplotvite time.
      </p>
      {comparison_rows}
    </section>

    <section class="section-block">
      <h2 class="block-title">Latency versus input size</h2>
      <p class="block-desc">
        The scaling chart was rendered by Matplotvite itself. The x-axis is
        log10(points); the reference line marks 0.5 ms.
      </p>
      <figure class="scaling-figure">
        <img src="benchmark_scaling.png" alt="Latency scaling with input size">
        <figcaption class="figure-caption">Measured single-line PNG latency, from 100 to 100,000 points.</figcaption>
      </figure>
    </section>

    <section class="section-block">
      <h2 class="block-title">Benchmark matrix</h2>
      <div class="table-wrap">
        <table class="bench-table">
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Category</th>
              <th class="num">Points</th>
              <th class="num">Matplotvite (ms)</th>
              <th class="num">matplotlib (ms)</th>
              <th class="num">Ratio</th>
            </tr>
          </thead>
          <tbody>
            {table_html}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <h2 class="block-title">Implementation notes</h2>
      <p class="block-desc">
        The measurements reflect the current implementation, not a general
        guarantee. The main sources of difference are architectural:
      </p>
      <div class="implementation-list">
        <div>
          <h3>Borrowed NumPy views</h3>
          <p>PyO3 reads contiguous NumPy buffers through borrowed read-only slices instead of materializing Python lists or per-point objects.</p>
        </div>
        <div>
          <h3>Compiled drawing and layout</h3>
          <p>Coordinate mapping, tick selection, and geometry are computed in Rust rather than in Python-level artist objects.</p>
        </div>
        <div>
          <h3>Direct encoding</h3>
          <p>Raster buffers are encoded by the Rust image and PNG/WebP crates; vector output is serialized to SVG or PDF without a Pillow conversion.</p>
        </div>
        <div>
          <h3>Embedded font data</h3>
          <p>The bundled DejaVu Sans and Geist faces avoid host font discovery and fontconfig parsing during rendering.</p>
        </div>
        <div>
          <h3>Parallel subplot panels</h3>
          <p>Panels can be rendered concurrently with Rayon, and unchanged figures reuse their encoded output.</p>
        </div>
        <div>
          <h3>Small runtime surface</h3>
          <p>The extension does not import matplotlib or Pillow, which reduces process startup and memory overhead for batch jobs.</p>
        </div>
      </div>
    </section>

    <div class="environment">
      <strong>Environment</strong><br>
      OS: {html.escape(str(sys_info.get("os", "Linux")))} ({html.escape(str(sys_info.get("arch", "x86_64")))})<br>
      Python: {html.escape(str(sys_info.get("python_version", "3.x")))};
      matplotlib: {html.escape(str(sys_info.get("matplotlib_version", "3.11.2")))};
      Matplotvite: {html.escape(str(sys_info.get("matplotvite_version", matplotvite.__version__)))}<br>
      Measured: {html.escape(str(sys_info.get("timestamp", "unknown")))}<br>
      Reproduce: <code>python tools/benchmark.py</code>
    </div>
  </main>

  <footer>
    <p>Timings are single-host measurements and should be reproduced on the target system before making deployment decisions.</p>
    <p>Benchmark data: <code>tools/benchmarks_data.json</code>. Benchmark method: <code>tools/benchmark.py</code>.</p>
    {commit_link_html()}
  </footer>

</body>
</html>
"""
