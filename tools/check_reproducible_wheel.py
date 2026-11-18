#!/usr/bin/env python3
"""Compare two wheel build directories for byte-for-byte reproducibility."""

import argparse
import hashlib
import pathlib
import sys


def _wheel(directory: pathlib.Path) -> pathlib.Path:
    wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        sys.exit(f"expected exactly one wheel in {directory}, found {len(wheels)}")
    return wheels[0]


def _digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=pathlib.Path)
    parser.add_argument("second", type=pathlib.Path)
    args = parser.parse_args()

    first, second = _wheel(args.first), _wheel(args.second)
    if first.name != second.name:
        sys.exit(f"wheel names differ: {first.name!r} != {second.name!r}")
    first_hash, second_hash = _digest(first), _digest(second)
    if first_hash != second_hash:
        sys.exit(
            f"wheels are not reproducible: {first.name}\n"
            f"  {first_hash}\n  {second_hash}"
        )
    print(f"reproducible {first.name} {first_hash}")


if __name__ == "__main__":
    main()
