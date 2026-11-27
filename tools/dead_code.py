#!/usr/bin/env python3
"""Report dead code with vulture, without flagging the Matplotlib-shaped API.

The package mirrors Matplotlib, so public functions, methods and keyword
arguments look unused by design. Only private (`_name`) functions, classes,
methods and imports are checked there; `tools/` is checked in full. Mark an
intentional exception with `# noqa`.
"""

from __future__ import annotations

import pathlib
import sys

from vulture import Vulture

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRIVATE_KINDS = {"function", "class", "method", "import"}


def scan(path: pathlib.Path) -> Vulture:
    vulture = Vulture()
    vulture.scavenge([str(path)])
    return vulture


def main() -> int:
    findings = list(scan(ROOT / "tools").get_unused_code(min_confidence=60))
    findings.extend(
        item for item in scan(ROOT / "python" / "matplotvite").get_unused_code(min_confidence=60)
        if item.typ in PRIVATE_KINDS and item.name.startswith("_")
        and not item.name.startswith("__"))
    for item in findings:
        print(f"{item.filename}:{item.first_lineno}: unused {item.typ} "
              f"'{item.name}'", file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
