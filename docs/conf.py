"""Sphinx configuration for the Matplotvite API reference."""

from __future__ import annotations

# Autodoc imports the installed package: a source checkout has no compiled
# `_core` extension, so putting `python/` on sys.path would shadow the wheel and
# make the build fail in CI. `pip install -e .` or `maturin develop` covers
# local builds.
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
