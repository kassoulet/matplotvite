#!/usr/bin/env python3
"""Run the security checks required before pushing and in CI.

The checks are intentionally dependency-audit focused:
  * cargo audit   - RustSec advisories against Cargo.lock
  * bandit        - static analysis of the shipped Python package
  * pip-audit     - known vulnerabilities in the installed Python packages

Pre-push installs Bandit and pip-audit through prek. CI installs the same
tools explicitly. cargo-audit must be available on the developer's PATH:
`cargo install cargo-audit --locked`.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def has_cargo_audit() -> bool:
    try:
        subprocess.run(
            ["cargo", "audit", "--version"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def main() -> int:
    if not has_cargo_audit():
        print(
            "cargo-audit is required for the security scan; install it with "
            "`cargo install cargo-audit --locked`.",
            file=sys.stderr,
        )
        return 1

    run(["cargo", "audit"])
    run([sys.executable, "-m", "bandit", "-q", "-r", "python/matplotvite"])
    run([sys.executable, "-m", "pip_audit"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
