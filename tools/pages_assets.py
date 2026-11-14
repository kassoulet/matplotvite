"""Static CSS, JavaScript and shared markup for the generated site.

The page generator supplies the data and page bodies; this module owns the
repeated visual shell so page-specific code does not carry hundreds of lines of
CSS and CDN boilerplate.
"""

from __future__ import annotations

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
    .coverage-status {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.55rem 1rem;
      margin-top: 1.1rem;
      padding: 0;
      list-style: none;
    }
    .coverage-status li { display: flex; flex-direction: column; }
    .coverage-status-count {
      color: var(--text);
      font-family: var(--mono);
      font-size: 1.15rem;
      font-weight: 600;
    }
    .coverage-status-label {
      color: var(--muted);
      font-size: 0.72rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
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
