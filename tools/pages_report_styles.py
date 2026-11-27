"""CSS for the comparison and benchmark reports."""

from __future__ import annotations


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
