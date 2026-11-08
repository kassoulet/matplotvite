#!/usr/bin/env python3
"""Fail when a benchmark is more than a set percentage slower than its baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def load(path: Path) -> dict[str, dict[str, float]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("results", data)
    if not isinstance(rows, list):
        raise ValueError(f"{path} does not contain a benchmark result list")
    return {row["name"]: row for row in rows if "name" in row}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("current", type=Path, help="fresh benchmark JSON")
    parser.add_argument("baseline", type=Path, help="checked-in baseline JSON")
    parser.add_argument("--max-slowdown", type=float, default=20.0,
                        help="allowed slowdown percentage (default: 20)")
    parser.add_argument("--metric", choices=("speedup", "rs"), default="speedup",
                        help="speedup compares Matplotvite/matplotlib; rs compares wall time")
    parser.add_argument("--strict", action="store_true",
                        help="also fail when a benchmark has no baseline entry")
    args = parser.parse_args()

    current = load(args.current)
    baseline = load(args.baseline)
    failures: list[str] = []
    for name, row in current.items():
        base = baseline.get(name)
        if base is None:
            message = f"no baseline for {name!r}"
            if args.strict:
                failures.append(message)
            else:
                print(f"warning: {message}", file=sys.stderr)
            continue
        if args.metric == "speedup":
            before = float(base.get("speedup", 0.0))
            now = float(row.get("speedup", 0.0))
            if before <= 0 or now <= 0:
                continue
            slowdown = (before - now) / before * 100.0
            detail = f"speedup {before:.2f}x -> {now:.2f}x"
        else:
            before = float(base.get("rs_ms", 0.0))
            now = float(row.get("rs_ms", 0.0))
            if before <= 0 or now <= 0:
                continue
            slowdown = (now - before) / before * 100.0
            detail = f"wall time {before:.2f} ms -> {now:.2f} ms"
        status = "FAIL" if slowdown > args.max_slowdown else "ok"
        print(f"{status}: {name} ({detail}, {slowdown:+.1f}%)")
        if slowdown > args.max_slowdown:
            failures.append(name)

    if failures:
        print(f"\n{len(failures)} benchmark(s) exceeded the "
              f"{args.max_slowdown:.0f}% slowdown budget.", file=sys.stderr)
        return 1
    print(f"\nAll benchmarks are within the {args.max_slowdown:.0f}% budget.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
