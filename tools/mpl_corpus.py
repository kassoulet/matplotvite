"""Build, check and diff the checked-in Matplotlib corpus metadata.

The metadata records the runnable snippet and a SHA-256 hash of every expected
baseline image for each harvested ``@image_comparison`` case. It is generated
from a Matplotlib checkout or sdist, never hand-edited, so a corpus update is a
reviewable JSON change and a render run can limit itself to changed snippets.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

SCHEMA = 1


def _sha256(path: pathlib.Path) -> str | None:
    """SHA-256 of an expected image, or None when the baseline is absent."""
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _relative_image(path: pathlib.Path, tests_root: pathlib.Path) -> str:
    try:
        return path.relative_to(tests_root).as_posix()
    except ValueError:
        return path.as_posix()


def matplotlib_version(tests_root: pathlib.Path) -> str | None:
    """Version encoded in a ``matplotlib-<version>`` sdist directory name."""
    for part in (tests_root, *tests_root.parents):
        match = re.fullmatch(r"matplotlib-(\d+\.\d+\.\d+(?:[^\s/]*)?)", part.name)
        if match:
            return match.group(1)
    return None


def case_record(case: dict[str, object],
                tests_root: pathlib.Path) -> dict[str, object]:
    """Stable metadata for one harvested case: source plus expected hashes."""
    images = []
    for value in case.get("images") or ():
        path = pathlib.Path(str(value))
        images.append({
            "path": _relative_image(path, tests_root),
            "sha256": _sha256(path),
        })
    return {
        "module": case.get("module"),
        "function": case.get("function"),
        "snippet": case.get("snippet"),
        "expected": images,
    }


def build_metadata(cases: list[dict[str, object]],
                   tests_root: pathlib.Path) -> dict[str, object]:
    """Build the checked-in corpus object from a harvest result."""
    records = {
        str(case["id"]): case_record(case, tests_root)
        for case in cases
    }
    return {
        "schema": SCHEMA,
        "matplotlib_version": matplotlib_version(tests_root),
        "cases": dict(sorted(records.items())),
    }


def write_metadata(path: pathlib.Path, metadata: dict[str, object]) -> None:
    """Write deterministic, review-friendly JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_metadata(path: pathlib.Path) -> dict[str, object]:
    """Read and minimally validate a metadata file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError(f"{path} is not corpus metadata schema {SCHEMA}")
    if not isinstance(payload.get("cases"), dict):
        raise ValueError(f"{path} has no case map")
    return payload


def diff_metadata(cases: list[dict[str, object]],
                  metadata: dict[str, object],
                  tests_root: pathlib.Path) -> dict[str, object]:
    """Compare current harvested cases with checked-in metadata.

    A case changes when its rewritten snippet or any expected-image hash changes.
    Cases absent from either side are reported separately as added or removed.
    """
    current = build_metadata(cases, tests_root)
    old_cases = metadata.get("cases") or {}
    new_cases = current["cases"]
    added = sorted(set(new_cases).difference(old_cases))
    removed = sorted(set(old_cases).difference(new_cases))
    changed = sorted(
        key for key in set(new_cases).intersection(old_cases)
        if new_cases[key] != old_cases[key]
    )
    version_changed = current["matplotlib_version"] != metadata.get("matplotlib_version")
    changed_ids = set(added).union(changed)
    return {
        "added": added,
        "changed": changed,
        "removed": removed,
        "version_changed": version_changed,
        "cases": [case for case in cases if str(case["id"]) in changed_ids],
        "clean": not (added or changed or removed or version_changed),
    }


def describe_diff(report: dict[str, object]) -> str:
    """One-line human summary of a corpus diff."""
    added = len(report["added"])
    changed = len(report["changed"])
    removed = len(report["removed"])
    version = "version changed" if report["version_changed"] else "version unchanged"
    return f"{added} added, {changed} changed, {removed} removed; {version}"
