"""Gallery, comparison and visual-report HTML."""

from __future__ import annotations

import html
import json
import statistics
from collections import Counter
from pathlib import Path

from tools.gallery_render import format_ms
from tools.pages_assets import prism_scripts, prism_stylesheet, shared_navbar
from tools.pages_common import (
    GALLERY_PAGES,
    category_id,
    commit_link_html,
    coverage_counter_html,
    coverage_stats,
    speedup_label,
)
from tools.pages_report_styles import comparison_css
from tools.pages_styles import gallery_css, gallery_js, shared_css


def generate_gallery_html(samples_info: list[dict[str, object]],
                          coverage: dict[str, object] | None = None) -> str:
    """Generate index.html from the rendered sample metadata."""
    categories = list(dict.fromkeys(str(s["category"]) for s in samples_info))
    coverage_html = coverage_counter_html(
        coverage if coverage is not None else coverage_stats()
    )

    cat_buttons = ['<button class="filter-btn active" data-filter="all">All</button>']
    for cat in categories:
        cat_buttons.append(
            f'<button class="filter-btn" data-filter="{category_id(cat)}">'
            f"{html.escape(cat)}</button>"
        )
    cat_buttons_html = "\n        ".join(cat_buttons)

    cards = []
    for sample in samples_info:
        filename = str(sample["filename"])
        fmt = str(sample["format"]).upper()
        code_escaped = html.escape(str(sample["code"]))
        cards.append(
            f"""
      <article class="sample-card" data-category="{category_id(sample['category'])}">
        <div class="card-header">
          <div class="card-title-group">
            <span class="category-tag">{html.escape(str(sample['category']))}</span>
            <h3 class="card-title">{html.escape(str(sample['title']))}</h3>
          </div>
          <div class="card-badges">
            <span class="badge badge-fmt">{fmt}</span>
            <span class="badge">{html.escape(str(sample['file_size']))}</span>
          </div>
        </div>
        <p class="card-desc">{html.escape(str(sample['description']))}</p>
        <div class="preview-container">
          <a href="{filename}" target="_blank" rel="noopener">
            <img src="{filename}" alt="{html.escape(str(sample['title']))}"
                 class="plot-preview" loading="lazy">
          </a>
        </div>
        <div class="code-container">
          <div class="code-header">
            <span>Python</span>
            <button class="copy-btn" onclick="copySnippet(this)">Copy</button>
          </div>
          <pre><code class="language-python">{code_escaped}</code></pre>
        </div>
      </article>"""
        )
    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Matplotvite — Matplotlib-compatible plotting in Rust</title>
  <meta name="description" content="Matplotvite renders static matplotlib-style figures from Python using a Rust extension, with NumPy as the only runtime dependency.">
  {prism_stylesheet()}
  <style>
    {shared_css()}
    {gallery_css()}
  </style>
</head>
<body>

  {shared_navbar("gallery")}

  <header class="hero">
    <p class="hero-kicker">Python plotting · Rust rendering path</p>
    <h1 class="hero-title">Static matplotlib-style figures, native renderer</h1>
    <p class="hero-subtitle">
      Matplotvite maps NumPy arrays and dataframes to a fast Rust renderer and
      writes PNG, SVG, PDF, or WebP output. The public API follows matplotlib's
      pyplot and object-oriented interfaces where practical.
    </p>
    <ul class="hero-meta">
      <li>NumPy is the only runtime dependency</li>
      <li>Python 3.9+ stable-ABI wheels (glibc/musl, macOS, Windows)</li>
      <li>Figures can be written to a path, a file object, or returned as bytes</li>
    </ul>
    <div class="hero-actions">
      <a href="#gallery" class="btn btn-primary">Browse examples</a>
      <a href="karios.html" class="btn btn-secondary">KARIOS reports</a>
      <a href="comparison.html" class="btn btn-secondary">Compare backends</a>
      <a href="benchmarks.html" class="btn btn-secondary">Performance measurements</a>
    </div>
    <div class="quick-start">
      <code>maturin develop --release</code>
      <button class="copy-btn" onclick="navigator.clipboard.writeText('maturin develop --release')">Copy</button>
    </div>
  </header>

  <main>
    <section class="design-section">
      <p class="side-heading">Design notes</p>
      <div class="design-notes">
        <div class="design-note">
          <h3>Compiled rendering path</h3>
          <p>Coordinate transforms, axis layout, text shaping, and image encoding run in Rust. Python is used for the plotting interface and array input.</p>
        </div>
        <div class="design-note">
          <h3>Minimal runtime surface</h3>
          <p>The wheel depends on NumPy only. It does not import matplotlib, Pillow, or a system graphics stack such as Cairo or Pango.</p>
        </div>
        <div class="design-note">
          <h3>Static output formats</h3>
          <p>PNG and lossless WebP are rasterized directly. SVG preserves vector paths, and PDF keeps text selectable rather than embedding a raster image.</p>
        </div>
        <div class="design-note">
          <h3>Embedded typography</h3>
          <p>The Geist sans, serif, and mono faces are compiled into the extension, so output does not depend on fontconfig or host font discovery.</p>
        </div>
        <div class="design-note">
          <h3>Panel parallelism and caching</h3>
          <p>Subplot panels render concurrently with Rayon, and repeated saves of an unchanged figure reuse the encoded bytes.</p>
        </div>
        <div class="design-note">
          <h3>Compatibility scope</h3>
          <p>The API covers common static plotting calls. It is not a complete matplotlib implementation; implemented, accepted-and-ignored, and missing call sites are tracked in TRACE.md.</p>
        </div>
      </div>
    </section>

    <section class="coverage-section">
      <div class="coverage-aside">
        <p class="side-heading">Coverage</p>
        {coverage_html}
      </div>
      <table class="coverage-table">
        <thead>
          <tr><th>Area</th><th>Examples in this gallery</th></tr>
        </thead>
        <tbody>
          <tr><td>Line plots</td><td>plot, step, stairs, fill_between, fill_betweenx, axhline, axvline, axis spans, explicit limits</td></tr>
          <tr><td>Statistics</td><td>scatter, errorbar, histogram, boxplot, violinplot, stem, eventplot, broken_barh</td></tr>
          <tr><td>Categorical data</td><td>bar, barh, bar_label, pie, stackplot, string categories</td></tr>
          <tr><td>Gridded data</td><td>imshow, contour, contourf, pcolormesh, hist2d, hexbin, quiver, colorbar</td></tr>
          <tr><td>Layout</td><td>subplots, subplot, GridSpec, subplot_mosaic, twinx/twiny, suptitle</td></tr>
          <tr><td>Data types</td><td>datetime and datetime64, pandas DataFrames and Series, categorical axes</td></tr>
          <tr><td>Axes and text</td><td>ticks and rotation, tick_params, grid, legends, text, annotate, mathtext, log scales</td></tr>
          <tr><td>Styling and output</td><td>182 colormap names, style contexts, rcParams, PNG, SVG, PDF, WebP</td></tr>
        </tbody>
      </table>
    </section>

    <section class="gallery-section" id="gallery">
      <div class="section-header">
        <div>
          <h2 class="section-title">Examples</h2>
          <p class="section-desc">Each figure is generated by the Python source shown below it.</p>
        </div>
        <p class="section-desc">Select a category to narrow the gallery. The full source is included so the output can be reproduced directly.</p>
      </div>
      <div class="filters">
        {cat_buttons_html}
      </div>
      <div class="gallery-grid">
        {cards_html}
      </div>
    </section>
  </main>

  <footer>
    <p>Matplotvite is dual-licensed under MIT or Apache-2.0. Source and issue tracker: <a href="https://github.com/kassoulet/matplotvite">github.com/kassoulet/matplotvite</a>.</p>
    <p>Gallery generated by <code>tools/build_pages.py</code>; figures rendered by Matplotvite.</p>
    {commit_link_html()}
  </footer>

  {prism_scripts()}
  <script>
    {gallery_js()}
  </script>
</body>
</html>
"""

def generate_comparison_html(samples_info: list[dict[str, object]], mpl_available: bool) -> str:
    """Generate comparison.html from the Matplotvite and matplotlib renders."""
    timed = [
        sample
        for sample in samples_info
        if sample.get("mpl_filename") and sample.get("rs_ms") and sample.get("mpl_ms")
    ]

    cards = []
    for sample in samples_info:
        filename = str(sample["filename"])
        mpl_filename = sample.get("mpl_filename")
        title = html.escape(str(sample["title"]))
        code_escaped = html.escape(str(sample["code"]))
        rs_ms = float(sample.get("rs_ms") or 0.0)
        mpl_ms = float(sample.get("mpl_ms") or 0.0)
        left_label = "Matplotvite" + (f" · {format_ms(rs_ms)}" if rs_ms else "")
        speedup_html = ""
        if mpl_filename:
            mpl_src = f"comparison/{html.escape(str(mpl_filename))}"
            right_pane = (
                f'<a href="{mpl_src}" target="_blank" rel="noopener">'
                f'<img src="{mpl_src}" alt="matplotlib render of {title}" loading="lazy"></a>'
            )
            right_label = "matplotlib · Agg" + (f" · {format_ms(mpl_ms)}" if mpl_ms else "")
            if rs_ms and mpl_ms:
                speedup_html = (
                    f'<span class="comparison-speedup">{speedup_label(mpl_ms / rs_ms)}</span>'
                )
        elif not mpl_available:
            right_pane = '<p class="comparison-missing">matplotlib is not installed in this build.</p>'
            right_label = "matplotlib · unavailable"
        else:
            right_pane = '<p class="comparison-missing">This snippet uses an output format or dependency that the comparison build could not render with matplotlib.</p>'
            right_label = "matplotlib · skipped"
        cards.append(
            f"""
      <article class="comparison-card">
        <div class="comparison-head">
          <div>
            <span class="comparison-category">{html.escape(str(sample['category']))}</span>
            <h3 class="comparison-title">{title}</h3>
          </div>
          <div class="comparison-meta">
            <span class="badge badge-fmt">{str(sample['format']).upper()}</span>
            {speedup_html}
          </div>
        </div>
        <div class="comparison-pair">
          <div class="comparison-pane">
            <div class="comparison-label"><span>{left_label}</span><span>{html.escape(str(sample['file_size']))}</span></div>
            <a href="{filename}" target="_blank" rel="noopener"><img src="{filename}" alt="Matplotvite render of {title}" loading="lazy"></a>
          </div>
          <div class="comparison-pane">
            <div class="comparison-label"><span>{right_label}</span></div>
            {right_pane}
          </div>
        </div>
        <details>
          <summary>Python source</summary>
          <pre><code class="language-python">{code_escaped}</code></pre>
        </details>
      </article>"""
        )
    cards_html = "\n".join(cards)

    timing_note = ""
    if timed:
        median_ratio = statistics.median(
            float(sample["mpl_ms"]) / float(sample["rs_ms"]) for sample in timed
        )
        timing_note = (
            f" Timings are the best of three wall-clock runs per backend, covering figure "
            f"construction through writing the file in the same process; across the "
            f"{len(timed)} snippets both backends completed, the median Matplotvite render is "
            f"{speedup_label(median_ratio)} than matplotlib."
        )

    mpl_note = (
        "Matplotlib renders in this gallery use the Agg backend and its default DejaVu Sans font. "
        "Matplotvite renders use the same embedded DejaVu Sans face, though antialiasing and "
        "layout can still differ when the call sequence is identical."
        if mpl_available
        else "matplotlib is not installed in this build; the comparison column is unavailable."
    )
    mpl_note += timing_note

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Matplotvite — Backend comparison</title>
  <meta name="description" content="The same Python plotting snippets rendered by Matplotvite and by matplotlib's Agg backend, with measured render times.">
  {prism_stylesheet()}
  <style>
    {shared_css()}
    {comparison_css()}
  </style>
</head>
<body>

  {shared_navbar("comparison")}

  <header class="hero">
    <p class="hero-kicker">Backend comparison</p>
    <h1 class="hero-title">The same snippet, two renderers</h1>
    <p class="hero-subtitle">
      Each example below executes the source shown in the gallery once with Matplotvite and
      once with matplotlib's Agg backend. The images are not normalized or retouched.
    </p>
    <ul class="hero-meta">
      <li>Identical call sequence</li>
      <li>Shared embedded DejaVu Sans default</li>
      <li>Per-snippet timings, best of three runs</li>
      <li>Differences in antialiasing and layout are expected</li>
    </ul>
  </header>

  <main>
    <section class="comparison-section">
      <p class="comparison-note">{html.escape(mpl_note)}</p>
      <div class="comparison-grid">
        {cards_html}
      </div>
    </section>
  </main>

  <footer>
    <p>Both columns execute the same Plot API calls; only the imported pyplot module differs.</p>
    <p>Timings include data setup, layout, encoding, and writing the output file. Click either image to open it full size.</p>
    <p>Source: <code>examples/samples.py</code>. Matplotvite variant runs in-process; matplotlib uses Agg.</p>
    {commit_link_html()}
  </footer>

  {prism_scripts()}
</body>
</html>
"""


SVG_COMPARISON_DIR = "visual-svg"

def generate_svg_comparison_html(out_dir: Path) -> str | None:
    """Build svg-comparison.html from `visual_compare.py --format svg`.

    Returns None when the SVG comparison has not been generated, so a plain
    `--galleries-only` run without the extra step keeps working.
    """
    metrics_path = out_dir / SVG_COMPARISON_DIR / "metrics.json"
    if not metrics_path.exists():
        return None
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    rows = []
    for name in sorted(metrics):
        result = metrics[name]
        rms = result.get("rms")
        pct = result.get("mismatch_pct")
        detail = "n/a" if rms is None else f"rms {float(rms):.3f}"
        if pct is not None:
            detail += f" · {float(pct):.1f}% different"

        def cell(filename: str, error: object, case_name: str = name) -> str:
            path = out_dir / SVG_COMPARISON_DIR / filename
            if path.exists():
                src = f"{SVG_COMPARISON_DIR}/{html.escape(filename)}"
                return f'<img src="{src}" alt="{html.escape(case_name)}" loading="lazy">'
            return f'<pre class="error">{html.escape(str(error or "not rendered"))}</pre>'

        rows.append(
            f"<tr><td class=\"case\"><b>{html.escape(name)}</b>"
            f"<span>{html.escape(detail)}</span></td>"
            f"<td>{cell(f'{name}.mpl.svg', result.get('error'))}</td>"
            f"<td>{cell(f'{name}.rs.svg', result.get('error'))}</td></tr>")

    failures = sum(1 for result in metrics.values() if result.get("error"))
    rms_values = [float(result["rms"]) for result in metrics.values()
                  if result.get("rms") is not None]
    median = sorted(rms_values)[len(rms_values) // 2] if rms_values else None
    summary = f"{len(metrics)} cases · {failures} failures"
    if median is not None:
        summary += f" · median rms {median:.3f}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Matplotvite — SVG comparison</title>
  <meta name="description" content="Matplotvite and Matplotlib SVG output for the same snippets.">
  <style>
    {shared_css()}
    .svg-hero {{ padding-bottom: 1rem; }}
    .svg-summary {{ font-family: var(--mono); font-size: 0.8rem; color: var(--muted); }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border-bottom: 1px solid var(--border); padding: 0.65rem; text-align: left; vertical-align: top; }}
    th {{ font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }}
    td.case {{ font-family: var(--mono); font-size: 0.78rem; white-space: nowrap; width: 1%; }}
    td.case span {{ display: block; color: var(--muted); }}
    td img {{ display: block; width: 100%; max-width: 460px; height: auto; background: #fff; border: 1px solid var(--border); }}
    .error {{ color: #b00020; white-space: pre-wrap; max-width: 46ch; font-size: 0.78rem; }}
  </style>
</head>
<body>
  {shared_navbar("galleries")}
  <header class="hero svg-hero">
    <p class="hero-kicker">Generated by CI</p>
    <h1 class="hero-title">SVG output compared</h1>
    <p class="hero-subtitle">
      The same snippet runs against both libraries and each side is the SVG file
      that library wrote. The pair is rasterised to a common size before the RMS
      and differing-pixel share are measured.
    </p>
    <p class="svg-summary">{html.escape(summary)}</p>
  </header>
  <main>
    <table>
      <thead><tr><th>case</th><th>matplotlib SVG</th><th>matplotvite SVG</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </main>
  <footer>
    <p>Produced by <code>tools/visual_compare.py --format svg</code> during the Pages build.</p>
    {commit_link_html()}
  </footer>
</body>
</html>
"""

def generate_galleries_html(out_dir: Path) -> str:
    """Build the landing page for the CI-generated comparison galleries."""
    cards = []
    svg_metrics_path = out_dir / SVG_COMPARISON_DIR / "metrics.json"
    if svg_metrics_path.exists():
        svg_metrics = json.loads(svg_metrics_path.read_text(encoding="utf-8"))
        svg_failures = sum(1 for result in svg_metrics.values() if result.get("error"))
        cards.append(
            f"""
      <article class="gallery-card">
        <span class="gallery-kicker">Exporter comparison</span>
        <h2>SVG output</h2>
        <p>The same snippets exported to SVG by Matplotlib and matplotvite, then measured side by side.</p>
        <p class="gallery-meta">{len(svg_metrics)} cases · {svg_failures} failures</p>
        <a class="btn btn-primary" href="svg-comparison.html">Open page</a>
      </article>"""
        )
    for title, directory, description in GALLERY_PAGES:
        manifest = out_dir / directory / "manifest.json"
        if manifest.exists():
            cases = json.loads(manifest.read_text(encoding="utf-8"))
            counts = Counter(str(case.get("status")) for case in cases)
            details = " · ".join(f"{counts[name]} {name}" for name in
                                 ("rendered", "pass", "failed", "needs-api", "unsupported")
                                 if counts[name])
            if not details:
                details = f"{len(cases)} cases"
            action = (f'<a class="btn btn-primary" href="{html.escape(directory)}/index.html">'
                      'Open gallery</a>')
            meta = f"{len(cases)} cases · {details}"
        else:
            action = '<span class="gallery-missing">Not generated in this build.</span>'
            meta = "No manifest found"
        cards.append(
            f"""
      <article class="gallery-card">
        <span class="gallery-kicker">Comparison gallery</span>
        <h2>{html.escape(title)}</h2>
        <p>{html.escape(description)}</p>
        <p class="gallery-meta">{html.escape(meta)}</p>
        {action}
      </article>"""
        )
    cards_html = "\n".join(cards)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Matplotvite — Comparison galleries</title>
  <meta name="description" content="Generated Matplotlib baseline, Matplotlib example, and Seaborn comparison galleries.">
  <style>
    {shared_css()}
    .galleries-hero {{ padding-bottom: 2rem; }}
    .gallery-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.25rem; padding: 2.5rem 0 0; }}
    .gallery-card {{ display: flex; flex-direction: column; gap: 0.65rem; padding: 1.25rem; background: var(--surface); border: 1px solid var(--border); border-radius: 5px; }}
    .gallery-card h2 {{ font-family: var(--serif); font-size: 1.45rem; font-weight: 500; line-height: 1.2; }}
    .gallery-card p {{ color: var(--muted); font-size: 0.9rem; }}
    .gallery-kicker {{ color: var(--accent); font-family: var(--mono); font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; }}
    .gallery-meta {{ font-family: var(--mono); font-size: 0.74rem !important; }}
    .gallery-card .btn {{ align-self: flex-start; margin-top: auto; }}
    .gallery-missing {{ color: var(--muted); font-size: 0.82rem; }}
  </style>
</head>
<body>
  {shared_navbar("galleries")}
  <header class="hero galleries-hero">
    <p class="hero-kicker">Generated by CI</p>
    <h1 class="hero-title">Comparison galleries</h1>
    <p class="hero-subtitle">
      These pages are rebuilt from the pinned Matplotlib and Seaborn sources on
      every Pages deployment. They are the API-gap work queue, not curated examples.
    </p>
  </header>
  <main>
    <section class="gallery-grid">{cards_html}
    </section>
  </main>
  <footer>
    <p>Generated by the <code>galleries</code> CI job and deployed with the static site.</p>
    {commit_link_html()}
  </footer>
</body>
</html>
"""
