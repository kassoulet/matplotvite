"""KARIOS figure page HTML."""

from __future__ import annotations

from pathlib import Path

from tools.pages_assets import shared_navbar
from tools.pages_common import commit_link_html
from tools.pages_styles import shared_css


def generate_karios_html() -> str:
    """Generate karios.html for the synthetic KARIOS report figures."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Matplotvite — KARIOS report figures</title>
  <meta name="description" content="Demanding KARIOS report layouts rendered by Matplotvite with synthetic data.">
  <style>
    {shared_css()}
    .karios-main {{ padding-top: 0; }}
    .karios-note {{
      max-width: 850px;
      margin: 1.75rem 0 0;
      padding: 0.9rem 1rem;
      background: var(--surface-muted);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--muted);
      font-size: 0.86rem;
    }}
    .karios-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1.5rem;
      padding: 2rem 0 0;
    }}
    .karios-card {{
      margin: 0;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 5px;
      overflow: hidden;
    }}
    .karios-card.overview {{ grid-column: 1 / -1; }}
    .karios-card img {{
      display: block;
      width: 100%;
      height: auto;
      max-height: 780px;
      object-fit: contain;
      background: #ffffff;
      border-bottom: 1px solid var(--border);
    }}
    .karios-card figcaption {{ padding: 1rem 1.1rem 1.2rem; }}
    .karios-card h2 {{
      color: var(--text);
      font-family: var(--serif);
      font-size: 1.35rem;
      font-weight: 500;
      margin-bottom: 0.3rem;
    }}
    .karios-card p {{ color: var(--muted); font-size: 0.88rem; }}
    .karios-details {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1.5rem 2rem;
      padding: 2.5rem 0 0;
    }}
    .karios-details h3 {{
      color: var(--text);
      font-size: 0.95rem;
      font-weight: 650;
      margin-bottom: 0.2rem;
    }}
    .karios-details p {{ color: var(--muted); font-size: 0.84rem; }}
    @media (max-width: 800px) {{
      .karios-grid, .karios-details {{ grid-template-columns: 1fr; }}
      .karios-card.overview {{ grid-column: auto; }}
    }}
  </style>
</head>
<body>

  {shared_navbar("karios")}

  <header class="hero">
    <p class="hero-kicker">Real-world report layouts</p>
    <h1 class="hero-title">KARIOS error reports</h1>
    <p class="hero-subtitle">
      Three demanding report figures rendered with synthetic data by Matplotvite,
      without karios, pandas or GDAL. They exercise image panels, scatter
      colorbars, twin axes, marginal profiles and multi-line headers.
    </p>
    <ul class="hero-meta">
      <li>2 images and 2 scatter panels</li>
      <li>Twin-axis row/column profiles</li>
      <li>13,700 synthetic keypoints</li>
    </ul>
    <div class="hero-actions">
      <a href="index.html" class="btn btn-primary">Browse examples</a>
      <a href="comparison.html" class="btn btn-secondary">Compare backends</a>
    </div>
  </header>

  <main class="karios-main">
    <p class="karios-note">
      The data is synthetic and deterministic. The page and the regression tests
      call the same builders in <code>examples/karios_figures.py</code>, so a
      layout change cannot silently diverge between the two.
    </p>

    <section class="karios-grid" aria-label="KARIOS report figures">
      <figure class="karios-card overview">
        <a href="karios/01_overview.png" target="_blank" rel="noopener">
          <img src="karios/01_overview.png" alt="KARIOS errors overview with two image panels, radial and angle scatter panels, and two colorbars" loading="lazy">
        </a>
        <figcaption>
          <h2>Errors overview</h2>
          <p>Two monitored/reference images, radial and angular error scatters, two side colorbars and a two-line report header.</p>
        </figcaption>
      </figure>

      <figure class="karios-card">
        <a href="karios/02_dx.png" target="_blank" rel="noopener">
          <img src="karios/02_dx.png" alt="KARIOS dx shift scatter with column and row profiles" loading="lazy">
        </a>
        <figcaption>
          <h2>dx shift by row/column</h2>
          <p>Per-keypoint dx shifts with a left colorbar, column counts and mean/std on a twin y axis, and the rotated row profile.</p>
        </figcaption>
      </figure>

      <figure class="karios-card">
        <a href="karios/03_dy.png" target="_blank" rel="noopener">
          <img src="karios/03_dy.png" alt="KARIOS dy shift scatter with column and row profiles" loading="lazy">
        </a>
        <figcaption>
          <h2>dy shift by row/column</h2>
          <p>The same marginal layout for the dy component, including count bars, standard-deviation bands and zero references.</p>
        </figcaption>
      </figure>
    </section>

    <section class="karios-details">
      <div>
        <h3>Colorbars</h3>
        <p>Gradient strips sit beside the images and scatter panels with matched limits and tick labels.</p>
      </div>
      <div>
        <h3>Profiles</h3>
        <p>Binned counts, means and standard deviations share the row/column axes through twinx and twiny.</p>
      </div>
      <div>
        <h3>Layout</h3>
        <p>Explicit add_axes rectangles preserve the narrow marginal panels that ordinary subplot grids cannot express.</p>
      </div>
    </section>
  </main>

  <footer>
    <p>Figures are generated by <code>python tools/build_pages.py</code> from <code>examples/karios_figures.py</code>.</p>
    {commit_link_html()}
  </footer>

</body>
</html>
"""

def write_karios_page(out_dir: Path) -> Path:
    """Write karios.html for the figures rendered by the render step."""
    path = out_dir / "karios.html"
    path.write_text(generate_karios_html(), encoding="utf-8")
    return path
