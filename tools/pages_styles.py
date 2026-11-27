"""CSS and JavaScript for the generated pages."""

from __future__ import annotations


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
