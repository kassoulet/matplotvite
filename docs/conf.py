"""Sphinx configuration for the Matplotvite API reference."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

project = "Matplotvite"
author = "Gautier Portet"
copyright = "2026, Gautier Portet"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = True

html_theme = "alabaster"
html_title = "Matplotvite API"
exclude_patterns = ["_build"]
