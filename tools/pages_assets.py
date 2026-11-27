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
    karios_active = " active" if current_page == "karios" else ""
    comparison_active = " active" if current_page == "comparison" else ""
    benchmarks_active = " active" if current_page == "benchmarks" else ""
    galleries_active = " active" if current_page == "galleries" else ""
    api_active = " active" if current_page == "api" else ""
    return f"""
  <nav class="topnav">
    <div class="nav-container">
      <a href="index.html" class="nav-logo">Matplotvite<span class="logo-version">0.6</span></a>
      <div class="nav-links">
        <a href="index.html" class="nav-link{gallery_active}">Examples</a>
        <a href="galleries.html" class="nav-link{galleries_active}">Galleries</a>
        <a href="api/index.html" class="nav-link{api_active}">API</a>
        <a href="karios.html" class="nav-link{karios_active}">KARIOS</a>
        <a href="comparison.html" class="nav-link{comparison_active}">Comparison</a>
        <a href="benchmarks.html" class="nav-link{benchmarks_active}">Performance</a>
        <a href="https://github.com/kassoulet/matplotvite" class="nav-link nav-external" target="_blank" rel="noopener">Source</a>
        <a href="https://github.com/kassoulet/matplotvite#readme" class="nav-link nav-external" target="_blank" rel="noopener">Documentation</a>
      </div>
    </div>
  </nav>"""
