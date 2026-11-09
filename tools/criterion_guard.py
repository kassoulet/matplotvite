#!/usr/bin/env python3
"""Fail when a Criterion output-stage benchmark exceeds its time budget."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def load_estimates(root: Path) -> dict[str, float]:
    """Map `group/benchmark` ids to Criterion's median point estimate (ns)."""
    estimates: dict[str, float] = {}
    for path in root.rglob("new/estimates.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        estimate = data.get("median") or data.get("mean") or {}
        value = estimate.get("point_estimate")
        if isinstance(value, (int, float)) and value > 0:
            key = path.parent.parent.relative_to(root).as_posix()
            estimates[key] = float(value)
    return estimates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("current", type=Path, help="target/criterion directory")
    parser.add_argument("baseline", type=Path, help="checked-in criterion baseline JSON")
    parser.add_argument("--max-slowdown", type=float, default=25.0,
                        help="allowed slowdown percentage (default: 25)")
    parser.add_argument("--write", action="store_true",
                        help="write current estimates as the baseline and exit")
    args = parser.parse_args()

    current = load_estimates(args.current)
    if not current:
        print(f"no Criterion estimates under {args.current}", file=sys.stderr)
        return 1
    if args.write:
        args.baseline.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {len(current)} estimates to {args.baseline}")
        return 0

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    failures: list[str] = []
    for name, now in sorted(current.items()):
        before = baseline.get(name)
        if not isinstance(before, (int, float)) or before <= 0:
            print(f"warning: no baseline for {name}", file=sys.stderr)
            continue
        slowdown = (now - before) / before * 100.0
        status = "FAIL" if slowdown > args.max_slowdown else "ok"
        print(f"{status}: {name} ({before / 1e6:.2f} ms -> {now / 1e6:.2f} ms, "
              f"{slowdown:+.1f}%)")
        if slowdown > args.max_slowdown:
            failures.append(name)
    if failures:
        print(f"\n{len(failures)} Criterion benchmark(s) exceeded the "
              f"{args.max_slowdown:.0f}% slowdown budget.", file=sys.stderr)
        return 1
    print(f"\nAll Criterion benchmarks are within the {args.max_slowdown:.0f}% budget.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
