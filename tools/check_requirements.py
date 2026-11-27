#!/usr/bin/env python3
"""Check the hash-pinned requirement files against their `.in` sources.

Every `.in` file is compiled with `uv pip compile --universal --generate-hashes`
for the Python floor named on its `# python-floor:` line, and the committed
`.txt` must be byte-identical to that output. Editing a pin by hand or bumping
a dependency without refreshing the hashes therefore fails here instead of
silently weakening the install.

Run with `--write` to refresh the files after a deliberate change.
"""
import argparse
import difflib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / ".github" / "requirements"
FLOOR = re.compile(r"^# python-floor: (\d+\.\d+)\s*$", re.MULTILINE)


def floor_of(source: Path) -> str:
    """The oldest interpreter the compiled file has to support."""
    match = FLOOR.search(source.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"{source.name}: add a '# python-floor: X.Y' line")
    return match.group(1)


def compile_source(uv: str, source: Path, out: Path) -> None:
    """Write the hash-pinned resolution of `source` to `out`."""
    subprocess.run(
        [
            uv, "pip", "compile", "--universal", "--generate-hashes",
            "--no-header", "--python-version", floor_of(source),
            source.name, "-o", str(out),
        ],
        cwd=REQUIREMENTS,
        check=True,
        capture_output=True,
        text=True,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write", action="store_true", help="refresh the .txt files in place")
    args = parser.parse_args(argv)

    uv = shutil.which("uv")
    if uv is None:
        print("uv is required to check the pins: pip install uv", file=sys.stderr)
        return 1

    sources = sorted(REQUIREMENTS.glob("*.in"))
    targets = {source.with_suffix(".txt") for source in sources}
    orphans = sorted(set(REQUIREMENTS.glob("*.txt")) - targets)
    if orphans:
        for orphan in orphans:
            print(f"{orphan.relative_to(ROOT)} has no .in source", file=sys.stderr)
        return 1

    stale: list[tuple[Path, Path, str]] = []
    with tempfile.TemporaryDirectory() as tmp:
        for source in sources:
            target = source.with_suffix(".txt")
            compiled = Path(tmp) / target.name
            try:
                compile_source(uv, source, compiled)
            except subprocess.CalledProcessError as exc:
                print(f"{source.name}: uv pip compile failed\n{exc.stderr}",
                      file=sys.stderr)
                return 1
            wanted = compiled.read_text(encoding="utf-8")
            if args.write:
                target.write_text(wanted, encoding="utf-8")
                print(f"wrote {target.relative_to(ROOT)}")
            elif not target.exists() or target.read_text(encoding="utf-8") != wanted:
                stale.append((source, target, wanted))

    if args.write:
        return 0

    for source, target, wanted in stale:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        name = target.relative_to(ROOT)
        sys.stdout.writelines(difflib.unified_diff(
            current.splitlines(keepends=True),
            wanted.splitlines(keepends=True),
            fromfile=f"{name} (committed)",
            tofile=f"{name} (from {source.name})",
        ))
    if stale:
        print("the pinned requirements are stale; run "
              "`python tools/check_requirements.py --write`", file=sys.stderr)
        return 1

    print(f"requirements: {len(sources)} files match their .in sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
