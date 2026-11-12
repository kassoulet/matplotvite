#!/usr/bin/env python3
"""Write a Markdown summary of the comparison galleries for a CI job summary.

Reads the three `manifest.json` files written by the harvest tools and prints a
table of per-status counts plus the gallery HTML paths, so a CI run shows the
results without downloading the uploaded artifact.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib

GALLERIES = (
    ("Matplotlib baseline images", "mpl-corpus"),
    ("Matplotlib gallery examples", "mpl-examples"),
    ("Seaborn examples", "seaborn-gallery"),
)
STATUS_ORDER = ("rendered", "blank", "pass", "failed", "no baseline", "needs-api",
                "unsupported")


def load_counts(path: pathlib.Path) -> tuple[collections.Counter[str], int]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError(f"{path} does not contain a gallery manifest list")
    return collections.Counter(str(case["status"]) for case in cases), len(cases)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("dist"),
                        help="directory holding the three galleries (default: dist)")
    parser.add_argument("--artifact-url", default="",
                        help="URL of the uploaded galleries artifact, linked when given")
    args = parser.parse_args()

    rows = []
    seen: set[str] = set()
    total = 0
    for title, directory in GALLERIES:
        counts, cases = load_counts(args.out / directory / "manifest.json")
        seen.update(counts)
        total += cases
        rows.append((title, directory, counts, cases))

    columns = [status for status in STATUS_ORDER if status in seen]
    columns += sorted(seen.difference(STATUS_ORDER))
    header = ["Gallery", "Cases", *columns, "HTML"]
    lines = ["## Comparison galleries", "",
             "| " + " | ".join(header) + " |",
             "| " + " | ".join(["---"] + ["---:"] * (len(header) - 1)) + " |"]
    for title, directory, counts, cases in rows:
        cells = [title, str(cases), *(str(counts[status]) for status in columns),
                 f"`{directory}/index.html`"]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    if args.artifact_url:
        lines.append(f"[Download the galleries artifact]({args.artifact_url}) "
                     "to browse the HTML files in the table.")
        lines.append("")
    lines.append(f"{total} cases across {len(rows)} galleries.")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
