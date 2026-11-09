"""Reject co-author trailers in commit messages.

usage: python tools/check_commit_message.py <commit-msg-file>

Runs from prek's `commit-msg` stage, so a `Co-Authored-By:` line fails the
commit before it is created. Comment lines (``#``) and everything after git's
scissors line are ignored, since git drops them from the final message.
"""
from __future__ import annotations

import pathlib
import re
import sys

TRAILER_RE = re.compile(r"^\s*co-authored-by\s*:", re.IGNORECASE)
SCISSORS_RE = re.compile(r"^# -+ >8 -+$")


def offence(message: str) -> str | None:
    """The first `Co-Authored-By:` line in a commit message, if any."""
    for line in message.splitlines():
        if SCISSORS_RE.match(line):
            return None
        if line.startswith("#"):
            continue
        if TRAILER_RE.match(line):
            return line.strip()
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_commit_message.py <commit-msg-file>", file=sys.stderr)
        return 2
    message = pathlib.Path(argv[1]).read_text(encoding="utf-8", errors="replace")
    found = offence(message)
    if found is None:
        return 0
    print(f"error: commit message contains a co-author trailer: {found}", file=sys.stderr)
    print("Remove the Co-Authored-By line and commit again.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
