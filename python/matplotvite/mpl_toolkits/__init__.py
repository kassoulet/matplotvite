"""Compatibility shims for Matplotlib toolkit imports.

They live inside matplotvite so installing the wheel never adds a top-level
``mpl_toolkits`` package that could shadow Matplotlib's namespace.
"""
