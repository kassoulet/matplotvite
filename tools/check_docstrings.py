#!/usr/bin/env python3
"""Check docstring coverage of the public Matplotvite API.

The gate treats every name in ``matplotvite.__all__`` that resolves to a Python
function or class defined inside the package as public surface. Imported
helpers and compatibility shims are excluded because their docs live with the
defining module.
"""

from __future__ import annotations

import argparse
import inspect

import matplotvite as plt


def _public(kind: str) -> list[tuple[str, object]]:
    """Return public names of ``kind`` (``function`` or ``class``)."""
    predicate = inspect.isfunction if kind == "function" else inspect.isclass
    found = []
    for name in plt.__all__:
        value = getattr(plt, name)
        if predicate(value) and getattr(value, "__module__", "").startswith("matplotvite"):
            found.append((name, value))
    return found


def _documented(items: list[tuple[str, object]]) -> list[str]:
    """Return the names that have no docstring."""
    return [name for name, value in items if not inspect.getdoc(value)]


def _ratio(items: list[tuple[str, object]]) -> float:
    if not items:
        return 1.0
    return 1.0 - len(_documented(items)) / len(items)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-functions", type=float, default=1.0,
                        help="required fraction of public functions with docstrings")
    parser.add_argument("--min-classes", type=float, default=0.9,
                        help="required fraction of public classes with docstrings")
    args = parser.parse_args()

    functions = _public("function")
    classes = _public("class")
    failures = []
    for label, items, minimum in (
        ("functions", functions, args.min_functions),
        ("classes", classes, args.min_classes),
    ):
        missing = _documented(items)
        ratio = _ratio(items)
        print(f"{label}: {len(items) - len(missing)}/{len(items)} documented "
              f"({ratio:.0%}, required {minimum:.0%})")
        if missing:
            print(f"  missing: {', '.join(missing)}")
        if ratio < minimum:
            failures.append(label)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
