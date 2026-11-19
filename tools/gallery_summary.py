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
STATUS_ORDER = ("rendered", "blank", "pass", "no baseline", "needs-api",
                "harvester-gap", "bug", "failed", "unsupported")
REASONS = ("out_of_scope", "harvester", "needs_api", "bug")


def load_counts(path: pathlib.Path) -> tuple[collections.Counter[str], int,
                                             collections.Counter[str], int]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError(f"{path} does not contain a gallery manifest list")
    statuses = collections.Counter(str(case["status"]) for case in cases)
    reasons = collections.Counter(
        str(case["reason"]) for case in cases if case.get("reason"))
    ignored = sum(int(case.get("ignored", 0) or 0) for case in cases)
    return statuses, len(cases), reasons, ignored


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
    total_ignored = 0
    reason_rows = []
    for title, directory in GALLERIES:
        counts, cases, reasons, ignored = load_counts(
            args.out / directory / "manifest.json")
        seen.update(counts)
        total += cases
        total_ignored += ignored
        rows.append((title, directory, counts, cases, ignored))
        if reasons:
            reason_rows.append((title, reasons))

    columns = [status for status in STATUS_ORDER if status in seen]
    columns += sorted(seen.difference(STATUS_ORDER))
    header = ["Gallery", "Cases", "Ignored calls", *columns, "HTML"]
    lines = ["## Comparison galleries", "",
             "| " + " | ".join(header) + " |",
             "| " + " | ".join(["---"] + ["---:"] * (len(header) - 1)) + " |"]
    for title, directory, counts, cases, ignored in rows:
        cells = [title, str(cases), str(ignored),
                 *(str(counts[status]) for status in columns),
                 f"`{directory}/index.html`"]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    if reason_rows:
        lines.append("### Failure reasons")
        lines.append("")
        lines.append("| Gallery | Out of scope | Harvester | Needs API | Bug |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for title, reasons in reason_rows:
            lines.append("| " + " | ".join(
                [title, *(str(reasons[name]) for name in REASONS)]) + " |")
        lines.append("")

    if args.artifact_url:
        lines.append(f"[Download the galleries artifact]({args.artifact_url}) "
                     "to browse the HTML files in the table.")
        lines.append("")
    lines.append(f"{total} cases across {len(rows)} galleries; "
                 f"{total_ignored} accepted calls were ignored. Rendered/pass "
                 "counts are an upper bound rather than proof of visual parity.")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
