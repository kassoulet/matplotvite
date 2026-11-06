#!/usr/bin/env python3
"""Build the standalone GitHub Pages example gallery for plt_rs."""

from __future__ import annotations

import argparse
import html
from pathlib import Path
import sys

# Ensure repository root is in python path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from examples.samples import SAMPLES


def format_bytes(size: int) -> str:
    """Format file size in human readable format."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def generate_html(samples_info: list[dict[str, object]]) -> str:
    """Generate complete standalone HTML for the example gallery."""
    categories = sorted({str(s["category"]) for s in samples_info})

    # Category filter buttons
    cat_buttons = ['<button class="filter-btn active" data-filter="all">All Examples</button>']
    for cat in categories:
        cat_id = cat.lower().replace(" ", "-").replace("&", "and")
        cat_buttons.append(f'<button class="filter-btn" data-filter="{cat_id}">{html.escape(cat)}</button>')
    cat_buttons_html = "\n      ".join(cat_buttons)

    # Gallery cards
    cards = []
    for s in samples_info:
        cat_id = str(s["category"]).lower().replace(" ", "-").replace("&", "and")
        filename = str(s["filename"])
        fmt_badge = "SVG" if s["format"] == "svg" else "PNG"
        size_str = str(s["file_size"])
        code_escaped = html.escape(str(s["code"]))

        card_html = f"""
      <article class="sample-card" data-category="{cat_id}">
        <div class="card-header">
          <div class="card-title-group">
            <span class="category-tag">{html.escape(str(s["category"]))}</span>
            <h3 class="card-title">{html.escape(str(s["title"]))}</h3>
          </div>
          <div class="card-badges">
            <span class="badge badge-fmt">{fmt_badge}</span>
            <span class="badge badge-size">{size_str}</span>
          </div>
        </div>

        <p class="card-desc">{html.escape(str(s["description"]))}</p>

        <div class="preview-container">
          <a href="{filename}" target="_blank" title="Click to view full image">
            <img src="{filename}" alt="{html.escape(str(s["title"]))}" class="plot-preview" loading="lazy">
          </a>
        </div>

        <div class="code-container">
          <div class="code-header">
            <span>Python snippet</span>
            <button class="copy-btn" onclick="copySnippet(this)">Copy code</button>
          </div>
          <pre><code class="language-python">{code_escaped}</code></pre>
        </div>
      </article>"""
        cards.append(card_html)

    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>plt.rs &mdash; Fast Matplotlib-style Plotting in Rust</title>
  <meta name="description" content="Matplotlib-style static plots rendered and saved entirely in Rust (PyO3 + plotters). Zero matplotlib, zero Pillow dependency.">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
  <style>
    :root {{
      --bg: #090d16;
      --card-bg: #111827;
      --card-border: #1f2937;
      --card-hover: #283548;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --primary: #3b82f6;
      --primary-hover: #60a5fa;
      --accent: #10b981;
      --code-bg: #030712;
      --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-family);
      line-height: 1.6;
      padding-bottom: 5rem;
    }}

    a {{
      color: var(--primary);
      text-decoration: none;
      transition: color 0.2s;
    }}
    a:hover {{
      color: var(--primary-hover);
    }}

    /* Header */
    header.hero {{
      text-align: center;
      padding: 4.5rem 1.5rem 3rem;
      background: radial-gradient(circle at 50% 0%, #1e293b 0%, var(--bg) 75%);
      border-bottom: 1px solid var(--card-border);
    }}

    .hero-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.3rem 0.9rem;
      border-radius: 9999px;
      background: rgba(59, 130, 246, 0.15);
      border: 1px solid rgba(59, 130, 246, 0.35);
      color: #93c5fd;
      font-size: 0.85rem;
      font-weight: 500;
      margin-bottom: 1.25rem;
    }}

    h1.hero-title {{
      font-size: 3.25rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      margin-bottom: 1rem;
      background: linear-gradient(135deg, #ffffff 30%, #93c5fd 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    p.hero-subtitle {{
      max-width: 720px;
      margin: 0 auto 2rem;
      font-size: 1.2rem;
      color: var(--text-muted);
    }}

    .hero-cta {{
      display: flex;
      justify-content: center;
      gap: 1rem;
      flex-wrap: wrap;
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.75rem 1.4rem;
      font-size: 0.95rem;
      font-weight: 600;
      border-radius: 8px;
      transition: all 0.2s;
      cursor: pointer;
    }}
    .btn-primary {{
      background: var(--primary);
      color: #ffffff;
      border: none;
    }}
    .btn-primary:hover {{
      background: var(--primary-hover);
      transform: translateY(-1px);
    }}
    .btn-secondary {{
      background: var(--card-bg);
      color: var(--text);
      border: 1px solid var(--card-border);
    }}
    .btn-secondary:hover {{
      background: var(--card-hover);
      border-color: var(--text-muted);
    }}

    /* Quick Install */
    .quick-start {{
      max-width: 650px;
      margin: 2.5rem auto 0;
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 0.85rem 1.25rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.92rem;
      color: #e5e7eb;
    }}

    /* Features Grid */
    .features-section {{
      max-width: 1100px;
      margin: 3.5rem auto 2rem;
      padding: 0 1.5rem;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.5rem;
    }}

    .feature-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
    }}
    .feature-icon {{
      font-size: 1.6rem;
      margin-bottom: 0.75rem;
    }}
    .feature-card h4 {{
      font-size: 1.05rem;
      margin-bottom: 0.5rem;
      color: #ffffff;
    }}
    .feature-card p {{
      font-size: 0.9rem;
      color: var(--text-muted);
    }}

    /* Gallery Section */
    .gallery-section {{
      max-width: 1240px;
      margin: 3.5rem auto 0;
      padding: 0 1.5rem;
    }}

    .section-header {{
      display: flex;
      flex-direction: column;
      align-items: center;
      margin-bottom: 2rem;
      text-align: center;
    }}
    .section-title {{
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin-bottom: 0.5rem;
    }}
    .section-desc {{
      color: var(--text-muted);
      font-size: 1.05rem;
    }}

    /* Filter tabs */
    .filters {{
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
      gap: 0.6rem;
      margin-bottom: 2.5rem;
    }}
    .filter-btn {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 0.5rem 1.1rem;
      border-radius: 9999px;
      font-size: 0.88rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .filter-btn:hover {{
      color: var(--text);
      border-color: var(--text-muted);
    }}
    .filter-btn.active {{
      background: var(--primary);
      border-color: var(--primary);
      color: #ffffff;
    }}

    /* Cards Grid */
    .gallery-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
      gap: 2rem;
    }}
    @media (max-width: 640px) {{
      .gallery-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    .sample-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transition: border-color 0.2s, box-shadow 0.2s;
    }}
    .sample-card:hover {{
      border-color: var(--primary);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.45);
    }}

    .card-header {{
      padding: 1.25rem 1.25rem 0.5rem;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
    }}
    .card-title-group {{
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }}
    .category-tag {{
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #60a5fa;
    }}
    .card-title {{
      font-size: 1.25rem;
      font-weight: 700;
      color: #ffffff;
    }}

    .card-badges {{
      display: flex;
      gap: 0.4rem;
    }}
    .badge {{
      font-size: 0.75rem;
      padding: 0.2rem 0.55rem;
      border-radius: 4px;
      font-weight: 600;
    }}
    .badge-fmt {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
    }}
    .badge-size {{
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-muted);
    }}

    .card-desc {{
      padding: 0.25rem 1.25rem 1rem;
      color: var(--text-muted);
      font-size: 0.92rem;
    }}

    .preview-container {{
      background: #ffffff;
      padding: 1rem;
      display: flex;
      justify-content: center;
      align-items: center;
      border-top: 1px solid var(--card-border);
      border-bottom: 1px solid var(--card-border);
    }}
    .plot-preview {{
      width: 100%;
      height: auto;
      max-height: 380px;
      object-fit: contain;
      display: block;
      transition: transform 0.2s ease;
    }}
    .plot-preview:hover {{
      transform: scale(1.015);
    }}

    .code-container {{
      background: var(--code-bg);
      flex: 1;
      display: flex;
      flex-direction: column;
    }}
    .code-header {{
      padding: 0.5rem 1rem;
      background: rgba(255, 255, 255, 0.03);
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.8rem;
      color: var(--text-muted);
    }}
    .copy-btn {{
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #d1d5db;
      padding: 0.25rem 0.6rem;
      font-size: 0.75rem;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .copy-btn:hover {{
      background: rgba(255, 255, 255, 0.18);
      color: #ffffff;
    }}

    pre[class*="language-"] {{
      margin: 0 !important;
      padding: 1rem !important;
      font-size: 0.85rem !important;
      background: transparent !important;
      overflow-x: auto;
    }}

    /* Footer */
    footer {{
      margin-top: 5rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.9rem;
      border-top: 1px solid var(--card-border);
      padding-top: 2.5rem;
    }}
  </style>
</head>
<body>

  <header class="hero">
    <div class="hero-badge">
      <span>⚡ Built with PyO3 &amp; Plotters</span>
    </div>
    <h1 class="hero-title">plt.rs</h1>
    <p class="hero-subtitle">
      Matplotlib-compatible static plots rendered and saved entirely in Rust.
      Zero Python Matplotlib dependency. Zero Pillow dependency.
    </p>

    <div class="hero-cta">
      <a href="https://github.com/kassoulet/plt_rs" class="btn btn-primary" target="_blank" rel="noopener">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
        GitHub Repository
      </a>
      <a href="#gallery" class="btn btn-secondary">Explore Examples &darr;</a>
    </div>

    <div class="quick-start">
      <code>pip install maturin numpy &amp;&amp; maturin develop --release</code>
      <button class="copy-btn" onclick="navigator.clipboard.writeText('pip install maturin numpy && maturin develop --release')">Copy</button>
    </div>
  </header>

  <section class="features-section">
    <div class="feature-card">
      <div class="feature-icon">⚡</div>
      <h4>Lightning-Fast Rust Backend</h4>
      <p>Direct buffer manipulation and image encoding via Rust's Plotters and png crates. Native performance without Python interpreter overhead.</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">🪶</div>
      <h4>Zero Matplotlib &amp; Pillow</h4>
      <p>Python dependencies are strictly NumPy only. Keeps your environment lightweight, perfect for headless services, lambdas, and containers.</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">🔤</div>
      <h4>Embedded Geist Typography</h4>
      <p>Includes high-legibility Geist Regular, Mono, and Serif fonts compiled directly into the binary. Zero OS font configuration needed.</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">📐</div>
      <h4>Dual PNG &amp; SVG Support</h4>
      <p>Save pixel-perfect raster PNGs or resolution-independent vector SVGs simply by changing the output file extension.</p>
    </div>
  </section>

  <section class="gallery-section" id="gallery">
    <div class="section-header">
      <h2 class="section-title">Example Gallery</h2>
      <p class="section-desc">Sample plots generated purely with plt.rs &mdash; click any image to view full resolution.</p>
    </div>

    <div class="filters">
      {cat_buttons_html}
    </div>

    <div class="gallery-grid">
      {cards_html}
    </div>
  </section>

  <footer>
    <p>plt.rs &mdash; Matplotlib-compatible static plotting in Rust.</p>
    <p style="margin-top:0.4rem; font-size:0.8rem;">Deployed automatically with GitHub Actions &amp; GitHub Pages.</p>
  </footer>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
  <script>
    // Category Filtering
    document.querySelectorAll('.filter-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const filter = btn.dataset.filter;
        document.querySelectorAll('.sample-card').forEach(card => {{
          if (filter === 'all' || card.dataset.category === filter) {{
            card.style.display = 'flex';
          }} else {{
            card.style.display = 'none';
          }}
        }});
      }});
    }});

    // Copy snippet functionality
    function copySnippet(btn) {{
      const pre = btn.closest('.code-container').querySelector('code');
      navigator.clipboard.writeText(pre.innerText).then(() => {{
        const orig = btn.innerText;
        btn.innerText = 'Copied!';
        setTimeout(() => btn.innerText = orig, 1800);
      }});
    }}
  </script>
</body>
</html>
"""


def build_pages(out_dir: Path) -> None:
    """Build gallery images and index.html in out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Building example gallery in: {out_dir}")

    samples_info: list[dict[str, object]] = []

    for s in SAMPLES:
        filename = str(s["filename"])
        target_path = out_dir / filename
        print(f"  Rendering [{s['id']}] -> {filename} ...", end=" ", flush=True)

        runner = s["runner"]
        runner(str(target_path))

        size = target_path.stat().st_size
        print(f"done ({format_bytes(size)})")

        sample_info = dict(s)
        sample_info["file_size"] = format_bytes(size)
        samples_info.append(sample_info)

    # Disable Jekyll processing on GitHub Pages
    (out_dir / ".nojekyll").touch()

    # Generate index.html
    html_content = generate_html(samples_info)
    index_path = out_dir / "index.html"
    index_path.write_text(html_content, encoding="utf-8")
    print(f"Wrote gallery page -> {index_path} ({format_bytes(len(html_content.encode('utf-8')))})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate example gallery for GitHub Pages.")
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="Output directory (default: dist)")
    args = parser.parse_args()

    build_pages(args.out)


if __name__ == "__main__":
    main()
