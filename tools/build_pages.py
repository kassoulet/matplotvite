#!/usr/bin/env python3
"""Build the static documentation and benchmark site for matplotvite."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable
import html
import importlib.util
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# The in-tree sources are only a fallback: when a matplotvite is installed (the
# wheel test job installs one) it must win, because the checkout has no compiled
# extension to import from `python/`.
if importlib.util.find_spec("matplotvite") is None and str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))


def _check_compiled_extension():
    """Refuse to let an in-tree extension silently shadow a newer Rust build."""
    extensions = [
        path
        for pattern in ("_core*.so", "_core*.pyd", "_core*.dylib")
        for path in (ROOT / "python" / "matplotvite").glob(pattern)
    ]
    if not extensions:
        return
    newest_input = max(
        [
            path
            for path in [ROOT / "Cargo.toml", ROOT / "Cargo.lock",
                         *list((ROOT / "src").rglob("*.rs")),
                         *list((ROOT / "assets").rglob("*"))]
            if path.is_file()
        ],
        key=lambda path: path.stat().st_mtime,
        default=None,
    )
    if newest_input is None:
        return
    newest_mtime = max(path.stat().st_mtime for path in extensions)
    if newest_mtime < newest_input.stat().st_mtime:
        raise SystemExit(
            "stale compiled extension in python/matplotvite; run "
            "`maturin develop --release` before building pages"
        )


if __name__ == "__main__":
    _check_compiled_extension()

import numpy as np
import matplotvite
from examples.samples import SAMPLES


def format_bytes(size: int) -> str:
    """Format a file size in binary units."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


def category_id(category: object) -> str:
    """Return the stable HTML filter identifier for a sample category."""
    return str(category).lower().replace(" ", "-").replace("&", "and")


def speedup_label(ratio: float) -> str:
    """Express a matplotlib/Matplotvite ratio in plain language."""
    if ratio >= 1.0:
        return f"{ratio:.1f}× faster"
    return f"{1.0 / ratio:.1f}× slower"


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


PRISM_VERSION = "1.29.0"
# Subresource Integrity digests for the exact cdnjs files the site loads.
# Regenerate with: curl -sSL <url> | openssl dgst -sha384 -binary | base64
PRISM_SRI = {
    "theme": "sha384-wFjoQjtV1y5jVHbt0p35Ui8aV8GVpEZkyF99OXWqP/eNJDU93D3Ugxkoyh6Y2I4A",
    "core": "sha384-06z5D//U/xpvxZHuUz92xBvq3DqBBFi7Up53HRrbV7Jlv7Yvh/MZ7oenfUe9iCEt",
    "python": "sha384-WJdEkJKrbsqw0evQ4GB6mlsKe5cGTxBOw4KAEIa52ZLB7DDpliGkwdme/HMa5n1m",
}


def prism_stylesheet() -> str:
    """Return the Prism stylesheet tag with a pinned version and SRI digest.

    The pages load third-party CSS and JavaScript from a CDN. SRI makes the
    browser reject a modified file, so a compromised CDN cannot run code or
    restyle the published documentation.
    """
    base = f"https://cdnjs.cloudflare.com/ajax/libs/prism/{PRISM_VERSION}"
    return (
        f'<link rel="stylesheet" href="{base}/themes/prism-tomorrow.min.css" '
        f'integrity="{PRISM_SRI["theme"]}" crossorigin="anonymous">'
    )


def prism_scripts() -> str:
    """Return the Prism core and Python grammar scripts with SRI digests."""
    base = f"https://cdnjs.cloudflare.com/ajax/libs/prism/{PRISM_VERSION}"
    return (
        f'<script src="{base}/prism.min.js" '
        f'integrity="{PRISM_SRI["core"]}" crossorigin="anonymous"></script>\n'
        f'  <script src="{base}/components/prism-python.min.js" '
        f'integrity="{PRISM_SRI["python"]}" crossorigin="anonymous"></script>'
    )


def shared_navbar(current_page: str) -> str:
    """Generate the shared top navigation bar."""
    gallery_active = " active" if current_page == "gallery" else ""
    comparison_active = " active" if current_page == "comparison" else ""
    benchmarks_active = " active" if current_page == "benchmarks" else ""
    galleries_active = " active" if current_page == "galleries" else ""
    return f"""
  <nav class="topnav">
    <div class="nav-container">
      <a href="index.html" class="nav-logo">Matplotvite<span class="logo-version">0.6</span></a>
      <div class="nav-links">
        <a href="index.html" class="nav-link{gallery_active}">Examples</a>
        <a href="galleries.html" class="nav-link{galleries_active}">Galleries</a>
        <a href="comparison.html" class="nav-link{comparison_active}">Comparison</a>
        <a href="benchmarks.html" class="nav-link{benchmarks_active}">Performance</a>
        <a href="https://github.com/kassoulet/matplotvite" class="nav-link nav-external" target="_blank" rel="noopener">Source</a>
        <a href="https://github.com/kassoulet/matplotvite#readme" class="nav-link nav-external" target="_blank" rel="noopener">Documentation</a>
      </div>
    </div>
  </nav>"""


def commit_link_html() -> str:
    """Name the commit the pages were built from, so a deployed page can be traced back."""
    try:
        full = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        # Building from an unpacked sdist has no repository to ask.
        return ""
    if not full:
        return ""
    short = full[:7]
    suffix = " with uncommitted changes" if dirty else ""
    return (
        f'<p>Built from commit <a href="https://github.com/kassoulet/matplotvite/commit/{full}">'
        f"<code>{short}</code></a>{suffix}.</p>"
    )


def shared_css() -> str:
    """Return the common stylesheet."""
    return """
    @font-face {
      font-family: "Geist";
      src: url("assets/fonts/Geist-Regular.ttf") format("truetype");
      font-weight: 400;
      font-style: normal;
      font-display: swap;
    }
    @font-face {
      font-family: "Geist Serif";
      src: url("assets/fonts/GeistSerif-Regular.ttf") format("truetype");
      font-weight: 400;
      font-style: normal;
      font-display: swap;
    }
    @font-face {
      font-family: "Geist Mono";
      src: url("assets/fonts/GeistMono-Regular.ttf") format("truetype");
      font-weight: 400;
      font-style: normal;
      font-display: swap;
    }

    :root {
      color-scheme: light dark;
      --page: #f7f8fa;
      --surface: #ffffff;
      --surface-muted: #f0f3f7;
      --border: #d8dee8;
      --border-strong: #b9c3d1;
      --text: #172033;
      --muted: #5d6b7e;
      --accent: #1f4e79;
      --accent-hover: #163b5c;
      --accent-soft: #e7eef5;
      --code-bg: #111827;
      --code-text: #e5e7eb;
      --sans: "Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      --serif: "Geist Serif", "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
      --mono: "Geist Mono", "SFMono-Regular", ui-monospace, Menlo, Consolas, "Liberation Mono", monospace;
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --page: #101318;
        --surface: #171b22;
        --surface-muted: #1e232c;
        --border: #2b323e;
        --border-strong: #3c4655;
        --text: #e5e9ef;
        --muted: #a1acba;
        --accent: #78a9d4;
        --accent-hover: #9bc2e2;
        --accent-soft: #1b2a38;
        --code-bg: #0b0e13;
        --code-text: #e5e7eb;
      }
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    html { scroll-behavior: smooth; }

    body {
      background: var(--page);
      color: var(--text);
      font-family: var(--sans);
      line-height: 1.65;
      -webkit-font-smoothing: antialiased;
    }

    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; text-underline-offset: 3px; }

    code, pre { font-family: var(--mono); }

    .topnav {
      background: var(--page);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .nav-container {
      max-width: 1180px;
      margin: 0 auto;
      padding: 0.9rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1.5rem;
    }
    .nav-logo {
      color: var(--text);
      font-family: var(--serif);
      font-size: 1.3rem;
      font-weight: 600;
      letter-spacing: -0.01em;
    }
    .nav-logo:hover { text-decoration: none; }
    .logo-version {
      display: inline-block;
      margin-left: 0.5rem;
      padding: 0.08rem 0.35rem;
      border: 1px solid var(--border-strong);
      border-radius: 3px;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.65rem;
      font-weight: 500;
      vertical-align: 0.15em;
    }
    .nav-links {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 1.35rem;
    }
    .nav-link {
      color: var(--muted);
      font-size: 0.9rem;
      font-weight: 500;
    }
    .nav-link:hover, .nav-link.active { color: var(--text); text-decoration: none; }
    .nav-link.active { box-shadow: inset 0 -2px 0 var(--accent); }
    .nav-external::after { content: " ↗"; font-size: 0.8em; color: var(--muted); }

    .hero {
      max-width: 1180px;
      margin: 0 auto;
      padding: 4.25rem 1.5rem 3rem;
      border-bottom: 1px solid var(--border);
    }
    .hero-kicker {
      color: var(--accent);
      font-family: var(--mono);
      font-size: 0.78rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 1rem;
    }
    h1.hero-title {
      max-width: 900px;
      color: var(--text);
      font-family: var(--serif);
      font-size: clamp(2.35rem, 5vw, 3.45rem);
      font-weight: 500;
      letter-spacing: -0.025em;
      line-height: 1.12;
      margin-bottom: 1.2rem;
    }
    p.hero-subtitle {
      max-width: 790px;
      color: var(--muted);
      font-size: 1.1rem;
      margin-bottom: 1.6rem;
    }
    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 1.4rem;
      color: var(--muted);
      font-size: 0.86rem;
      list-style: none;
      margin-bottom: 1.9rem;
    }
    .hero-meta li::before {
      content: "—";
      color: var(--border-strong);
      margin-right: 0.55rem;
    }
    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.8rem;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      padding: 0.62rem 1.05rem;
      border: 1px solid var(--border-strong);
      border-radius: 4px;
      font-size: 0.88rem;
      font-weight: 600;
      line-height: 1.2;
    }
    .btn:hover { text-decoration: none; }
    .btn-primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #ffffff;
    }
    .btn-primary:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
    .btn-secondary { background: var(--surface); color: var(--text); }
    .btn-secondary:hover { border-color: var(--accent); color: var(--accent); }

    main { max-width: 1180px; margin: 0 auto; padding: 0 1.5rem; }

    footer {
      max-width: 1180px;
      margin: 5rem auto 0;
      padding: 2rem 1.5rem 3rem;
      border-top: 1px solid var(--border);
      color: var(--muted);
      font-size: 0.84rem;
    }
    footer p + p { margin-top: 0.35rem; }
    """


def coverage_stats() -> dict[str, object]:
    """Return the matplotlib test-suite coverage counts shown on the site.

    The reports in `TRACE.md` and `tools/trace_baseline.json` are kept in sync by
    CI. When the pinned matplotlib is installed its tests are rescanned live, so
    the site shows current coverage; otherwise the baseline is reused.
    """
    stats: dict[str, object] = {}
    spec = importlib.util.find_spec("matplotlib")
    tests_dir = Path(spec.origin).parent / "tests" if spec and spec.origin else None
    if tests_dir is not None and tests_dir.is_dir():
        scanned = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "trace_unsupported.py"),
             str(tests_dir), "--json"],
            capture_output=True, text=True,
        )
        if scanned.returncode == 0:
            try:
                stats = json.loads(scanned.stdout)
            except json.JSONDecodeError:
                stats = {}
    if not stats:
        stats = json.loads(
            (ROOT / "tools" / "trace_baseline.json").read_text(encoding="utf-8")
        )
    stats["percent"] = 100 * int(stats["supported"]) // max(int(stats["total"]), 1)
    return stats


def coverage_counter_html(coverage: dict[str, object]) -> str:
    """Render the live coverage statistic beside the gallery coverage table."""
    supported = int(coverage["supported"])
    total = int(coverage["total"])
    files = int(coverage["files"])
    version = html.escape(str(coverage["matplotlib"]))
    percent = int(coverage["percent"])
    return f"""
      <div class="coverage-counter">
        <p class="coverage-percent">{percent}<span>%</span></p>
        <p class="coverage-count">{supported:,} / {total:,} call sites</p>
        <div class="coverage-meter" aria-hidden="true"><span style="width: {percent}%"></span></div>
        <p class="coverage-source">Static scan of {files} matplotlib {version} test files. The CI trace job re-runs this check and fails on any drop.</p>
      </div>"""


def gallery_css() -> str:
    """Return styles specific to the example gallery."""
    return """
    .quick-start {
      max-width: 720px;
      margin-top: 1.8rem;
      padding: 0.8rem 1rem;
      background: var(--code-bg);
      border: 1px solid #263244;
      border-radius: 5px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      color: var(--code-text);
      font-family: var(--mono);
      font-size: 0.82rem;
    }
    .quick-start code { white-space: nowrap; overflow-x: auto; }

    .copy-btn {
      flex: none;
      padding: 0.25rem 0.55rem;
      background: #1f2937;
      border: 1px solid #374151;
      border-radius: 3px;
      color: #d1d5db;
      font-family: var(--sans);
      font-size: 0.72rem;
      cursor: pointer;
    }
    .copy-btn:hover { border-color: #6b7280; color: #ffffff; }

    .design-section {
      display: grid;
      grid-template-columns: 240px minmax(0, 1fr);
      gap: 2.5rem;
      padding: 3rem 0;
      border-bottom: 1px solid var(--border);
    }
    .side-heading {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.09em;
      text-transform: uppercase;
    }
    .design-notes {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1.5rem 2.5rem;
    }
    .design-note h3 {
      color: var(--text);
      font-size: 0.98rem;
      font-weight: 650;
      margin-bottom: 0.3rem;
    }
    .design-note p {
      color: var(--muted);
      font-size: 0.9rem;
    }

    .coverage-section {
      display: grid;
      grid-template-columns: 240px minmax(0, 1fr);
      gap: 2.5rem;
      padding: 3rem 0;
      border-bottom: 1px solid var(--border);
    }
    .coverage-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.86rem;
    }
    .coverage-table th,
    .coverage-table td {
      padding: 0.65rem 0.75rem;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }
    .coverage-table th {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.71rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .coverage-table td:first-child {
      width: 170px;
      color: var(--text);
      font-weight: 600;
    }
    .coverage-table td:last-child { color: var(--muted); }

    .coverage-counter { margin-top: 0.5rem; }
    .coverage-percent {
      color: var(--text);
      font-family: var(--serif);
      font-size: 2.3rem;
      line-height: 1.1;
    }
    .coverage-percent span { color: var(--muted); font-size: 1.2rem; }
    .coverage-count {
      margin-top: 0.25rem;
      color: var(--text);
      font-family: var(--mono);
      font-size: 0.74rem;
    }
    .coverage-meter {
      margin-top: 0.7rem;
      height: 4px;
      background: var(--border);
      border-radius: 2px;
      overflow: hidden;
    }
    .coverage-meter span { display: block; height: 100%; background: var(--accent); }
    .coverage-source {
      margin-top: 0.7rem;
      color: var(--muted);
      font-size: 0.78rem;
      line-height: 1.45;
    }

    .gallery-section { padding: 3rem 0 0; }
    .section-header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 2rem;
      margin-bottom: 1.6rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border);
    }
    .section-title {
      color: var(--text);
      font-family: var(--serif);
      font-size: 2rem;
      font-weight: 500;
      letter-spacing: -0.02em;
      line-height: 1.2;
    }
    .section-desc {
      max-width: 560px;
      color: var(--muted);
      font-size: 0.88rem;
      text-align: right;
    }

    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin-bottom: 2rem;
    }
    .filter-btn {
      padding: 0.34rem 0.7rem;
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--muted);
      font-family: var(--sans);
      font-size: 0.8rem;
      cursor: pointer;
    }
    .filter-btn:hover { border-color: var(--border-strong); color: var(--text); }
    .filter-btn.active {
      background: var(--accent);
      border-color: var(--accent);
      color: #ffffff;
    }

    .gallery-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
      gap: 1.5rem;
    }
    @media (max-width: 700px) {
      .gallery-grid,
      .design-notes { grid-template-columns: 1fr; }
      .design-section,
      .coverage-section { grid-template-columns: 1fr; gap: 1rem; }
      .section-header { align-items: flex-start; flex-direction: column; }
      .section-desc { text-align: left; }
    }

    .sample-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 5px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .card-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;
      padding: 1rem 1.1rem 0.45rem;
    }
    .card-title-group { min-width: 0; }
    .category-tag {
      display: block;
      margin-bottom: 0.15rem;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.67rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .card-title {
      color: var(--text);
      font-size: 1.05rem;
      font-weight: 650;
      line-height: 1.3;
    }
    .card-badges { display: flex; flex: none; gap: 0.3rem; }
    .badge {
      padding: 0.12rem 0.38rem;
      border: 1px solid var(--border);
      border-radius: 3px;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.65rem;
    }
    .badge-fmt { color: var(--accent); border-color: #c7d6e4; background: var(--accent-soft); }

    .card-desc {
      padding: 0 1.1rem 0.9rem;
      color: var(--muted);
      font-size: 0.86rem;
    }
    .preview-container {
      background: #ffffff;
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0.75rem;
    }
    .plot-preview {
      display: block;
      width: 100%;
      height: auto;
      max-height: 390px;
      object-fit: contain;
    }
    .code-container {
      background: var(--code-bg);
      display: flex;
      flex: 1;
      flex-direction: column;
    }
    .code-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.42rem 0.8rem;
      border-bottom: 1px solid #263244;
      color: #9ca3af;
      font-size: 0.7rem;
      font-family: var(--mono);
    }
    .code-header .copy-btn { background: transparent; }
    pre[class*="language-"] {
      margin: 0 !important;
      padding: 0.9rem 1rem !important;
      background: transparent !important;
      font-size: 0.78rem !important;
      line-height: 1.55 !important;
      overflow-x: auto;
    }
    """


def gallery_js() -> str:
    """Return the gallery's small client-side interactions."""
    return """
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const filter = btn.dataset.filter;
        document.querySelectorAll('.sample-card').forEach(card => {
          card.style.display = (filter === 'all' || card.dataset.category === filter)
            ? 'flex' : 'none';
        });
      });
    });

    function copySnippet(btn) {
      const pre = btn.closest('.code-container').querySelector('code');
      navigator.clipboard.writeText(pre.innerText).then(() => {
        const original = btn.innerText;
        btn.innerText = 'Copied';
        setTimeout(() => btn.innerText = original, 1500);
      });
    }
    """


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
      <li>Python 3.9+ stable-ABI wheels</li>
      <li>Figures can be written to a path, a file object, or returned as bytes</li>
    </ul>
    <div class="hero-actions">
      <a href="#gallery" class="btn btn-primary">Browse examples</a>
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
          <p>The API covers common static plotting calls. It is not a complete matplotlib implementation; unsupported call sites are tracked in TRACE.md.</p>
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


def comparison_css() -> str:
    """Return styles specific to the backend comparison page."""
    return """
    .comparison-section { padding: 2.5rem 0 0; }
    .comparison-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1.5rem;
    }
    @media (max-width: 950px) { .comparison-grid { grid-template-columns: 1fr; } }
    .comparison-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 5px;
      overflow: hidden;
    }
    .comparison-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
      padding: 1rem 1.1rem 0.5rem;
    }
    .comparison-title { font-size: 1rem; font-weight: 650; line-height: 1.35; }
    .comparison-meta {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.3rem;
    }
    .comparison-speedup {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.68rem;
      white-space: nowrap;
    }
    .comparison-category {
      display: block;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.66rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-bottom: 0.15rem;
    }
    .comparison-pair {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1px;
      background: var(--border);
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
    }
    .comparison-pane { background: #ffffff; min-width: 0; }
    .comparison-label {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.35rem 0.55rem;
      background: var(--surface-muted);
      border-bottom: 1px solid var(--border);
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.64rem;
    }
    .comparison-pane a { display: block; cursor: zoom-in; }
    .comparison-pane img { display: block; width: 100%; height: auto; }
    .comparison-missing {
      color: var(--muted);
      font-size: 0.76rem;
      padding: 1rem;
      min-height: 9rem;
    }
    .comparison-card details {
      border-top: 1px solid var(--border);
      background: var(--code-bg);
    }
    .comparison-card summary {
      cursor: pointer;
      padding: 0.5rem 0.8rem;
      color: #cbd5e1;
      font-family: var(--mono);
      font-size: 0.7rem;
    }
    .comparison-card details pre { max-height: 22rem; overflow: auto; }
    .comparison-note {
      margin: 1.5rem 0 0;
      padding: 0.9rem 1rem;
      background: var(--surface-muted);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--muted);
      font-size: 0.82rem;
    }
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


def benchmark_css() -> str:
    """Return styles specific to the benchmark page."""
    return """
    .benchmarks-hero { border-bottom: none; padding-bottom: 1rem; }
    .benchmarks-container { padding-top: 0; }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
      margin: 1.5rem 0 3rem;
    }
    .metric-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 1rem 1.1rem;
    }
    .metric-label {
      color: var(--muted);
      font-size: 0.78rem;
      margin-bottom: 0.35rem;
    }
    .metric-value {
      color: var(--text);
      font-family: var(--serif);
      font-size: 1.65rem;
      line-height: 1.15;
    }
    .metric-detail {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.72rem;
      margin-top: 0.35rem;
    }

    .section-block {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 1.6rem;
      margin-bottom: 1.5rem;
    }
    .block-title {
      color: var(--text);
      font-family: var(--serif);
      font-size: 1.35rem;
      font-weight: 500;
      margin-bottom: 0.25rem;
    }
    .block-desc {
      color: var(--muted);
      font-size: 0.86rem;
      margin-bottom: 1.4rem;
    }

    .benchmark-row {
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr) 110px;
      gap: 1.25rem;
      align-items: center;
      padding: 0.9rem 0;
      border-top: 1px solid var(--border);
    }
    .benchmark-row:first-of-type { border-top: none; }
    .bench-category {
      display: block;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.66rem;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .bench-title { color: var(--text); font-size: 0.86rem; font-weight: 600; }
    .bar-pair { display: grid; gap: 0.22rem; }
    .bar-track {
      height: 14px;
      background: var(--surface-muted);
      border-radius: 2px;
      overflow: hidden;
    }
    .bar-fill { height: 100%; border-radius: 2px; }
    .bar-fill.matplotvite { background: var(--accent); }
    .bar-fill.matplotlib { background: #a8b3c2; }
    .bar-label {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.68rem;
      line-height: 1.35;
    }
    .bench-speedup {
      color: var(--text);
      font-family: var(--mono);
      font-size: 0.75rem;
      text-align: right;
    }
    @media (max-width: 820px) {
      .benchmark-row { grid-template-columns: 1fr; gap: 0.5rem; }
      .bench-speedup { text-align: left; }
    }

    .table-wrap { overflow-x: auto; }
    table.bench-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.82rem;
    }
    table.bench-table th {
      padding: 0.6rem 0.75rem;
      border-bottom: 1px solid var(--border-strong);
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-align: left;
      text-transform: uppercase;
    }
    table.bench-table td {
      padding: 0.65rem 0.75rem;
      border-bottom: 1px solid var(--border);
    }
    table.bench-table tr:last-child td { border-bottom: none; }
    table.bench-table td.num { font-family: var(--mono); text-align: right; white-space: nowrap; }
    .category-label { color: var(--muted); font-size: 0.78rem; }

    .scaling-figure { margin: 0.5rem 0 0; text-align: center; }
    .scaling-figure img {
      max-width: 100%;
      height: auto;
      border: 1px solid var(--border);
      border-radius: 3px;
      background: #ffffff;
    }
    .figure-caption {
      margin-top: 0.65rem;
      color: var(--muted);
      font-size: 0.76rem;
    }

    .implementation-list {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1.1rem 2rem;
      margin-top: 1rem;
    }
    .implementation-list h3 {
      color: var(--text);
      font-size: 0.92rem;
      font-weight: 650;
      margin-bottom: 0.25rem;
    }
    .implementation-list p { color: var(--muted); font-size: 0.84rem; }

    .environment {
      padding: 1rem 1.1rem;
      background: var(--surface-muted);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.74rem;
      line-height: 1.75;
    }
    """


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
      Matplotvite: {html.escape(str(sys_info.get("matplotvite_version", "0.6.0")))}<br>
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
    exec(code, {})


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


GALLERY_PAGES = (
    ("Matplotlib baseline images", "mpl-corpus",
     "Matplotlib's own image-comparison tests, rendered beside their reference PNGs."),
    ("Matplotlib gallery examples", "mpl-examples",
     "Every script in Matplotlib's gallery, classified by whether it renders and why it does not."),
    ("Seaborn gallery", "seaborn-gallery",
     "Seaborn examples classified against the Matplotlib API surface matplotvite exposes."),
)


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

        def cell(filename: str, error: object) -> str:
            path = out_dir / SVG_COMPARISON_DIR / filename
            if path.exists():
                src = f"{SVG_COMPARISON_DIR}/{html.escape(filename)}"
                return f'<img src="{src}" alt="{html.escape(name)}" loading="lazy">'
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


def write_galleries_page(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_page = generate_svg_comparison_html(out_dir)
    if svg_page is not None:
        svg_path = out_dir / "svg-comparison.html"
        svg_path.write_text(svg_page, encoding="utf-8")
        print(f"Wrote SVG comparison page -> {svg_path}")
    path = out_dir / "galleries.html"
    body = generate_galleries_html(out_dir)
    path.write_text(body, encoding="utf-8")
    return path


def build_pages(out_dir: Path) -> None:
    """Render gallery images and write both HTML pages into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    font_dir = out_dir / "assets" / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    for font_name in (
        "Geist-Regular.ttf",
        "GeistSerif-Regular.ttf",
        "GeistMono-Regular.ttf",
        "LICENSE_GEIST_OFL.txt",
    ):
        shutil.copyfile(ROOT / "assets" / "fonts" / font_name, font_dir / font_name)
    print(f"Building example gallery and benchmark site in: {out_dir}")

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
            lambda: (sample["runner"](str(target_path)), matplotvite.close())
        )
        print(f"done ({format_bytes(size)}, {format_ms(rs_ms)})")

        info = dict(sample)
        info["file_size"] = format_bytes(size)
        info["rs_ms"] = rs_ms
        samples_info.append(info)

    (out_dir / ".nojekyll").touch()

    gallery_html = generate_gallery_html(samples_info)
    index_path = out_dir / "index.html"
    index_path.write_text(gallery_html, encoding="utf-8")
    gallery_size = format_bytes(len(gallery_html.encode("utf-8")))
    print(f"Wrote gallery page -> {index_path} ({gallery_size})")

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
                lambda: render_matplotlib_sample(sample, target)
            )
            sample["mpl_filename"] = mpl_filename
            print(f"done ({format_ms(float(sample['mpl_ms']))})")
        except Exception as exc:  # pragma: no cover - backend-specific fallback
            sample.pop("mpl_ms", None)
            print(f"skipped ({exc})")

    comparison_html = generate_comparison_html(samples_info, mpl_available)
    comparison_path = out_dir / "comparison.html"
    comparison_path.write_text(comparison_html, encoding="utf-8")
    comparison_size = format_bytes(len(comparison_html.encode("utf-8")))
    print(f"Wrote comparison page -> {comparison_path} ({comparison_size})")

    bench_data_path = ROOT / "tools" / "benchmarks_data.json"
    if bench_data_path.exists():
        bench_data = json.loads(bench_data_path.read_text(encoding="utf-8"))
    else:
        bench_data = {"system": {}, "results": []}

    scaling_chart_path = out_dir / "benchmark_scaling.png"
    render_scaling_chart(scaling_chart_path, bench_data.get("results", []))
    print(f"Wrote scaling chart -> {scaling_chart_path}")

    benchmarks_html = generate_benchmarks_html(bench_data)
    bench_path = out_dir / "benchmarks.html"
    bench_path.write_text(benchmarks_html, encoding="utf-8")
    print(f"Wrote benchmarks page -> {bench_path} ({format_bytes(len(benchmarks_html.encode('utf-8')))})")

    galleries_path = write_galleries_page(out_dir)
    print(f"Wrote galleries page -> {galleries_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Matplotvite example gallery and benchmark site.")
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="Output directory (default: dist)")
    parser.add_argument("--galleries-only", action="store_true",
                        help="Only refresh galleries.html from existing manifests")
    args = parser.parse_args()
    if args.galleries_only:
        print(f"Wrote galleries page -> {write_galleries_page(args.out)}")
    else:
        build_pages(args.out)


if __name__ == "__main__":
    main()
