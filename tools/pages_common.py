"""Shared page metadata, coverage counters and gallery status breakdowns."""

from __future__ import annotations

import html
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent

def category_id(category: object) -> str:
    """Return the stable HTML filter identifier for a sample category."""
    return str(category).lower().replace(" ", "-").replace("&", "and")

def speedup_label(ratio: float) -> str:
    """Express a matplotlib/Matplotvite ratio in plain language."""
    if ratio >= 1.0:
        return f"{ratio:.1f}× faster"
    return f"{1.0 / ratio:.1f}× slower"

def commit_link_html() -> str:
    """Name the commit the pages were built from, so a deployed page can be traced back."""
    try:
        full = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        # Building from an unpacked sdist has no repository to ask.
        return ""
    if not full:
        return ""
    short = full[:7]
    suffix = " with uncommitted changes" if dirty else ""
    return (
        f'<p>Built from commit <a href="https://github.com/kassoulet/matplotvite/commit/{full}">'
        f"<code>{short}</code></a>{suffix}.</p>"
    )

GALLERY_STATUS_BUCKETS = {
    # A case counts as covered when matplotvite produced its image.
    "covered": ("rendered", "pass", "no baseline"),
    "needs-api": ("needs-api",),
    # Blank renders, crashes and harvester-side gaps all failed to produce a figure.
    "failed": ("failed", "bug", "blank", "harvester-gap"),
    "unsupported": ("unsupported",),
}

def gallery_status_breakdown(out_dir: Path) -> dict[str, int]:
    """Group comparison-gallery case statuses into the four coverage outcomes."""
    counts: Counter[str] = Counter()
    for _, directory, _ in GALLERY_PAGES:
        manifest = out_dir / directory / "manifest.json"
        if manifest.exists():
            cases = json.loads(manifest.read_text(encoding="utf-8"))
            counts.update(str(case.get("status")) for case in cases)
    if not counts:
        return {}
    breakdown = {
        bucket: sum(counts[status] for status in statuses)
        for bucket, statuses in GALLERY_STATUS_BUCKETS.items()
    }
    breakdown["cases"] = sum(breakdown.values())
    breakdown["other"] = sum(counts.values()) - breakdown["cases"]
    return breakdown

def coverage_stats(out_dir: Path | None = None) -> dict[str, object]:
    """Return the matplotlib test-suite coverage counts shown on the site.

    The reports in `TRACE.md` and `tools/trace_baseline.json` are kept in sync by
    CI. When the pinned matplotlib is installed its tests are rescanned live, so
    the site shows current coverage; otherwise the baseline is reused. With
    `out_dir`, the comparison galleries generated there are summarised by status.
    """
    stats: dict[str, object] = {}
    spec = importlib.util.find_spec("matplotlib")
    tests_dir = Path(spec.origin).parent / "tests" if spec and spec.origin else None
    if tests_dir is not None and tests_dir.is_dir():
        scanned = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "trace_unsupported.py"),
             str(tests_dir), "--json"],
            capture_output=True, text=True,
        )
        if scanned.returncode == 0:
            try:
                stats = json.loads(scanned.stdout)
            except json.JSONDecodeError:
                stats = {}
    if not stats:
        stats = json.loads(
            (ROOT / "tools" / "trace_baseline.json").read_text(encoding="utf-8")
        )
    implemented = int(stats.get("implemented", stats["supported"]))
    stats["percent"] = 100 * implemented // max(int(stats["total"]), 1)
    if out_dir is not None:
        breakdown = gallery_status_breakdown(out_dir)
        if breakdown:
            stats["galleries"] = breakdown
    return stats

def coverage_counter_html(coverage: dict[str, object]) -> str:
    """Render the live coverage statistic beside the gallery coverage table."""
    implemented = int(coverage.get("implemented", coverage["supported"]))
    ignored = int(coverage.get("accepted_ignored", 0))
    total = int(coverage["total"])
    files = int(coverage["files"])
    version = html.escape(str(coverage["matplotlib"]))
    percent = int(coverage["percent"])
    ignored_note = (f" {ignored:,} more are accepted but ignored." if ignored else "")
    return f"""
      <div class="coverage-counter">
        <p class="coverage-percent">{percent}<span>%</span></p>
        <p class="coverage-count">{implemented:,} / {total:,} call sites implemented</p>
        <div class="coverage-meter" aria-hidden="true"><span style="width: {percent}%"></span></div>
        <p class="coverage-source">Static scan of {files} matplotlib {version} test files.{ignored_note} The CI trace job re-runs this check and fails on any drop.</p>
        {gallery_breakdown_html(coverage.get("galleries"))}
      </div>"""

def gallery_breakdown_html(breakdown: object) -> str:
    """List the comparison-gallery outcomes under the call-site counter."""
    if not isinstance(breakdown, dict) or not breakdown.get("cases"):
        return ""
    labels = (
        ("covered", "covered"),
        ("needs-api", "needs API"),
        ("failed", "failed"),
        ("unsupported", "unsupported"),
    )
    cases = int(breakdown["cases"])
    covered = int(breakdown["covered"])
    items = "".join(
        f'<li><span class="coverage-status-count">{int(breakdown[key]):,}</span>'
        f'<span class="coverage-status-label">{label}</span></li>'
        for key, label in labels
    )
    other = int(breakdown.get("other", 0))
    extra = f" and {other:,} with another status" if other else ""
    return f"""
        <ul class="coverage-status">{items}</ul>
        <p class="coverage-source">{cases:,} comparison-gallery cases, {100 * covered // cases}% covered{extra}. A case needs API when the call exists in matplotlib but not here; it failed when matplotvite could not render it.</p>"""


class GalleryPage(NamedTuple):
    """One generated comparison gallery shown on the galleries page."""

    title: str
    directory: str
    description: str

GALLERY_PAGES = (
    GalleryPage("Matplotlib baseline images", "mpl-corpus",
                "Matplotlib's own image-comparison tests, rendered beside their reference PNGs."),
    GalleryPage("Matplotlib gallery examples", "mpl-examples",
                "Every script in Matplotlib's gallery, classified by whether it renders and why it does not."),
    GalleryPage("Seaborn gallery", "seaborn-gallery",
                "Seaborn examples classified against the Matplotlib API surface matplotvite exposes."),
)
