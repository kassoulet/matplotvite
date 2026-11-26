#!/usr/bin/env python3
"""Turn an OpenSSF Scorecard SARIF file into a readable report.

The Scorecard action only writes SARIF for code scanning, which is not meant
for people to read. This prints a Markdown summary for the workflow run and
writes a self-contained `index.html` for the uploaded artifact.

A check with no SARIF result either met the Scorecard policy or was
inconclusive; SARIF cannot tell those apart, so the page says so.
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import urllib.parse
from typing import Any

SCORE = re.compile(r"score is (-?\d+)")
TRAILER = "\nClick Remediation section below"
SEVERITY = {"error": "high", "warning": "medium", "recommendation": "low"}
VIEWER = "https://securityscorecards.dev/viewer/?uri=github.com/"


def _text(value: object, key: str = "text") -> str:
    return str((value or {}).get(key, "")) if isinstance(value, dict) else ""


def _safe_url(url: object) -> str:
    value = str(url or "")
    return value if urllib.parse.urlsplit(value).scheme in ("", "http", "https") else ""


def _score(message: str) -> int | None:
    match = SCORE.search(message)
    return int(match.group(1)) if match else None


def _reason(message: str) -> str:
    reason = message.split(TRAILER, 1)[0]
    match = SCORE.search(reason)
    if match:
        reason = reason[match.end():].lstrip(": \n")
    return reason.strip()


def _location(result: dict) -> str:
    locations = result.get("locations") or []
    if not locations:
        return ""
    physical = (locations[0].get("physicalLocation") or {})
    path = urllib.parse.unquote(
        _text(physical.get("artifactLocation"), "uri")) or "repository"
    line = (physical.get("region") or {}).get("startLine")
    return f"{path}:{line}" if line else path


def load_checks(path: pathlib.Path) -> list[dict[str, Any]]:
    """Return one entry per check, merging the SARIF runs."""
    sarif = json.loads(path.read_text(encoding="utf-8"))
    checks: dict[str, dict[str, Any]] = {}
    for run in sarif.get("runs") or []:
        rules = ((run.get("tool") or {}).get("driver") or {}).get("rules") or []
        results = run.get("results") or []
        for index, rule in enumerate(rules):
            rule_id = str(rule.get("id") or rule.get("name") or index)
            check = checks.setdefault(rule_id, {
                "name": str(rule.get("name") or rule_id),
                "description": _text(rule.get("fullDescription")),
                "url": _safe_url(rule.get("helpUri")),
                "severity": str((rule.get("properties") or {}).get(
                    "problem.severity", "")),
                "help": _text(rule.get("help"), "markdown")
                or _text(rule.get("fullDescription")),
                "findings": [],
            })
            check["findings"].extend(
                result for result in results
                if result.get("ruleId") == rule_id
                or result.get("ruleIndex") == index)
    for check in checks.values():
        findings = check["findings"]
        messages = [_reason(_text(f.get("message"))) for f in findings]
        check["score"] = _score(_text(findings[0].get("message"))) if findings else None
        check["reasons"] = messages
        check["locations"] = [_location(f) for f in findings]
    return list(checks.values())


def _repo_link(repository: str) -> str:
    return f"https://github.com/{repository}" if repository else ""


def _commit_link(repository: str, commit: str) -> str:
    return f"{_repo_link(repository)}/commit/{commit}" if repository and commit else ""


def render_markdown(checks: list[dict[str, Any]], repository: str,
                    commit: str) -> str:
    alerting = [check for check in checks if check["findings"]]
    findings = sum(len(check["findings"]) for check in alerting)
    lines = ["## OpenSSF Scorecard", ""]
    source = _repo_link(repository)
    if source and commit:
        source = f"[{repository}@{commit[:7]}]({_commit_link(repository, commit)})"
    summary = (f"{len(checks)} checks ran; {len(alerting)} reported "
               f"{findings} finding{'' if findings == 1 else 's'}")
    if source:
        summary = f"{source}: {summary}"
    lines.append(summary + ".")
    if repository:
        viewer = f"{VIEWER}{repository}"
        lines.append("")
        lines.append(f"[Open the full scored report]({viewer}).")
    lines.append("")
    if not alerting:
        lines.append("No check reported an alert.")
        return "\n".join(lines) + "\n"

    lines.extend([
        "| Check | Score | Severity | Finding |",
        "| --- | ---: | --- | --- |",
    ])
    for check in alerting:
        name = str(check["name"])
        if check["url"]:
            name = f"[{name}]({check['url']})"
        reason = str(check["reasons"][0]).splitlines()[0]
        if len(reason) > 160:
            reason = reason[:157] + "..."
        locations = [loc for loc in check["locations"] if loc]
        if locations:
            extra = len(locations) - 1
            where = f"`{locations[0]}`"
            reason = f"{reason} ({where}{f', +{extra} more' if extra else ''})"
        score = check["score"]
        lines.append("| " + " | ".join([
            name.replace("|", "\\|"),
            "inconclusive" if score in (None, -1) else str(score),
            html.escape(str(check["severity"]) or "unknown"),
            reason.replace("|", "\\|"),
        ]) + " |")
    lines.extend(["", "Checks without a row raised no alert; they passed the policy, "
                      "were annotated, or were inconclusive."])
    return "\n".join(lines) + "\n"


def render_html(checks: list[dict[str, Any]], repository: str,
                commit: str) -> str:
    alerting = [check for check in checks if check["findings"]]
    findings = sum(len(check["findings"]) for check in alerting)
    viewer = f"{VIEWER}{repository}" if repository else ""
    meta = []
    if repository:
        meta.append(f"<a href=\"{html.escape(_repo_link(repository))}\">"
                    f"{html.escape(repository)}</a>")
    if repository and commit:
        meta.append(f"<a href=\"{html.escape(_commit_link(repository, commit))}\">"
                    f"<code>{html.escape(commit[:12])}</code></a>")
    if viewer:
        meta.append(f"<a href=\"{html.escape(viewer)}\">Scorecard viewer</a>")

    rows = []
    for check in checks:
        name = html.escape(str(check["name"]))
        if check["url"]:
            name = f"<a href=\"{html.escape(str(check['url']))}\">{name}</a>"
        has_findings = bool(check["findings"])
        status = ('<span class="pill alert">Alerts</span>' if has_findings
                  else '<span class="pill clear">No alerts</span>')
        score = check["score"]
        score_cell = ("inconclusive" if score == -1 else str(score)
                      if score is not None else "&mdash;")
        rows.append(
            f"<tr><td>{name}</td><td>{status}</td>"
            f"<td class=\"num\">{score_cell}</td>"
            f"<td class=\"num\">{len(check['findings'])}</td></tr>")

    details = []
    for check in alerting:
        severity = str(check["severity"] or "unknown")
        css = SEVERITY.get(severity, "unknown")
        score = check["score"]
        count = len(check["findings"])
        heading = (f"<span class=\"pill {css}\">{html.escape(severity.title())}"
                   f"</span> {html.escape(str(check['name']))}")
        if score not in (None, -1):
            heading += f" <span class=\"muted\">score {score}</span>"
        items = []
        for reason, location in zip(check["reasons"], check["locations"]):
            where = (f"<p class=\"location\">{html.escape(str(location))}</p>"
                     if location else "")
            items.append(f"<li><p>{html.escape(str(reason))}</p>{where}</li>")
        docs = (f"<p><a href=\"{html.escape(str(check['url']))}\">"
                "Check documentation</a></p>" if check["url"] else "")
        help_text = (f"<details><summary>Remediation</summary>"
                     f"<pre>{html.escape(str(check['help']))}</pre></details>"
                     if check["help"] else "")
        details.append(
            f"<details><summary>{heading} <span class=\"muted\">"
            f"({count} finding{'' if count == 1 else 's'})</span></summary>"
            f"<p>{html.escape(str(check['description']))}</p>"
            f"<ul class=\"findings\">{''.join(items)}</ul>{docs}{help_text}"
            "</details>")

    body = "\n".join(details) or "<p>No check reported an alert.</p>"
    row_html = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenSSF Scorecard report</title>
<style>
:root {{ color-scheme: light dark; --muted: #667085; --line: #d0d5dd; }}
body {{ margin: 0; font: 16px/1.5 system-ui, sans-serif; }}
main {{ max-width: 60rem; margin: 0 auto; padding: 2rem 1rem; }}
h1 {{ margin: 0 0 .25rem; font-size: 1.8rem; }}
.meta, .muted {{ color: var(--muted); }}
.meta {{ margin: 0 0 1.5rem; display: flex; gap: 1rem; flex-wrap: wrap; }}
.stats {{ display: flex; gap: 2rem; list-style: none; padding: 0; margin: 0 0 1.5rem; }}
.stats strong {{ display: block; font-size: 1.6rem; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; }}
th, td {{ padding: .45rem .6rem; border-bottom: 1px solid var(--line); text-align: left; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.pill {{ display: inline-block; padding: .1rem .5rem; border-radius: 999px;
  font-size: .8rem; font-weight: 600; border: 1px solid currentColor; }}
.alert, .high {{ color: #b42318; }} .medium {{ color: #b54708; }}
.low {{ color: #175cd3; }} .clear {{ color: #067647; }}
details {{ padding: .6rem 0; border-bottom: 1px solid var(--line); }}
summary {{ cursor: pointer; }}
.findings {{ padding-left: 1.2rem; }}
.location {{ color: var(--muted); font-family: ui-monospace, monospace; font-size: .85rem; }}
pre {{ white-space: pre-wrap; font-size: .85rem; padding: .75rem; border: 1px solid var(--line); }}
a {{ color: #175cd3; }}
</style>
</head>
<body>
<main>
<h1>OpenSSF Scorecard</h1>
<p class="meta">{' '.join(meta)}</p>
<ul class="stats">
<li><strong>{len(checks)}</strong> checks</li>
<li><strong>{len(alerting)}</strong> with alerts</li>
<li><strong>{findings}</strong> finding{'' if findings == 1 else 's'}</li>
</ul>
<table>
<thead><tr><th scope="col">Check</th><th scope="col">Status</th>
<th scope="col" class="num">Score</th><th scope="col" class="num">Findings</th></tr></thead>
<tbody>
{row_html}
</tbody>
</table>
<h2>Alert details</h2>
{body}
<p class="muted">Checks without alerts raised no SARIF result; they passed the
policy, were annotated, or were inconclusive.</p>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sarif", type=pathlib.Path,
                        help="results.sarif written by the Scorecard action")
    parser.add_argument("--out", type=pathlib.Path,
                        default=pathlib.Path("dist/scorecard"),
                        help="directory for index.html (default: dist/scorecard)")
    parser.add_argument("--repository", default="",
                        help="owner/name, used for the viewer and commit links")
    parser.add_argument("--commit", default="",
                        help="analysed commit SHA, linked when given")
    args = parser.parse_args()

    checks = load_checks(args.sarif)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.html").write_text(
        render_html(checks, args.repository, args.commit), encoding="utf-8")
    print(render_markdown(checks, args.repository, args.commit), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
