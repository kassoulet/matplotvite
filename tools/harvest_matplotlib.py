"""Harvest Matplotlib's own tests and gallery examples into comparison galleries.

usage:
  python tools/harvest_matplotlib.py [--source PATH] [--out dist/mpl-corpus]
  python tools/harvest_matplotlib.py --examples PATH [--out dist/mpl-examples]

In the default mode, each `@image_comparison(...)` test in Matplotlib's test
suite names a baseline PNG that Matplotlib asserts its renderer reproduces. The
tool pulls those tests out of a Matplotlib checkout (the wheel ships the test
modules but not `baseline_images`, so an sdist or git checkout is required),
rewrites each test body into a standalone snippet, renders it with matplotvite
and writes a side-by-side gallery of baseline vs. ours plus a manifest.

With `--examples`, every script under `galleries/examples` (or `examples`) is
rewritten the same way, tagged with its gallery category and rendered into a
gallery whose failures are the API gap list. Exit status is 1 only when there
is nothing to harvest.
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import pathlib
import shutil
from concurrent.futures import ThreadPoolExecutor

try:
    from tools.mpl_harvest import (
        COMPAT_NAMESPACES,
        GUI_MODULES,
        NUMPY_ALIASES,
        OUT_OF_SCOPE_CATEGORIES,
        SKIP_RE,
        STRIPPED_IMPORTS,
        TOOLKITS_PACKAGE,
        _resolve_baseline,
        compat_name,
        find_examples_root,
        find_sample_data,
        find_tests_root,
        harvest,
        harvest_examples,
        image_comparison_baselines,
        image_comparison_options,
        prepare_body,
        prepare_example,
        requires_gui,
        source_details,
    )
    from tools.mpl_metrics import (
        BLANK_THRESHOLD,
        ENVIRONMENT_MODULES,
        FAILURE_REASONS,
        METRIC_CONVERTERS,
        _nonwhite_pixels,
        failure_status,
        metrics,
        report_missing_metrics_converters,
    )
    from tools.mpl_render import (
        SNIPPET_TIMEOUT,
        _fallback_multi_font_text,
        _render_snippet_in_process,
        _SampleDataCbook,
        render,
        render_matplotlib,
    )
except ModuleNotFoundError:  # `python tools/harvest_matplotlib.py`
    from mpl_harvest import (
        COMPAT_NAMESPACES,
        GUI_MODULES,
        NUMPY_ALIASES,
        OUT_OF_SCOPE_CATEGORIES,
        SKIP_RE,
        STRIPPED_IMPORTS,
        TOOLKITS_PACKAGE,
        _resolve_baseline,
        compat_name,
        find_examples_root,
        find_sample_data,
        find_tests_root,
        harvest,
        harvest_examples,
        image_comparison_baselines,
        image_comparison_options,
        prepare_body,
        prepare_example,
        requires_gui,
        source_details,
    )
    from mpl_metrics import (
        BLANK_THRESHOLD,
        ENVIRONMENT_MODULES,
        FAILURE_REASONS,
        METRIC_CONVERTERS,
        _nonwhite_pixels,
        failure_status,
        metrics,
        report_missing_metrics_converters,
    )
    from mpl_render import (
        SNIPPET_TIMEOUT,
        _fallback_multi_font_text,
        _render_snippet_in_process,
        _SampleDataCbook,
        render,
        render_matplotlib,
    )

__all__ = [
    "BLANK_THRESHOLD",
    "COMPAT_NAMESPACES",
    "ENVIRONMENT_MODULES",
    "FAILURE_REASONS",
    "GUI_MODULES",
    "METRIC_CONVERTERS",
    "NUMPY_ALIASES",
    "OUT_OF_SCOPE_CATEGORIES",
    "SKIP_RE",
    "SNIPPET_TIMEOUT",
    "STRIPPED_IMPORTS",
    "TOOLKITS_PACKAGE",
    "_SampleDataCbook",
    "_fallback_multi_font_text",
    "_nonwhite_pixels",
    "_render_snippet_in_process",
    "_resolve_baseline",
    "compat_name",
    "failure_status",
    "find_examples_root",
    "find_sample_data",
    "find_tests_root",
    "harvest",
    "harvest_examples",
    "harvest_examples_gallery",
    "harvest_gallery",
    "image_comparison_baselines",
    "image_comparison_options",
    "main",
    "metrics",
    "prepare_body",
    "prepare_example",
    "render",
    "render_matplotlib",
    "report_missing_metrics_converters",
    "requires_gui",
    "source_details",
]


def _sample_cases(cases: list[dict[str, object]],
                  limit: int | None) -> list[dict[str, object]]:
    """Evenly sample a gallery while keeping its input order."""
    if limit is None or limit <= 0 or len(cases) <= limit:
        return cases
    step = len(cases) / limit
    return [cases[min(len(cases) - 1, int(index * step))] for index in range(limit)]


def harvest_gallery(tests_root: pathlib.Path, out: pathlib.Path,
                    manifest_path: pathlib.Path,
                    limit: int | None = None) -> dict[str, int]:
    """Render every baseline case and write the side-by-side gallery."""
    report_missing_metrics_converters()
    cases = _sample_cases(harvest(tests_root), limit)
    sample_data = find_sample_data(tests_root.parent)
    out.mkdir(parents=True, exist_ok=True)

    rows: list[str] = []
    rendered = 0
    for case in cases:
        case_id = str(case["id"])
        slug = case_id.replace("/", "_")
        entry: dict[str, object] = {
            "id": case_id,
            "module": case["module"],
            "function": case["function"],
            "baselines": case["baselines"],
            "images": case["images"],
            "status": "unsupported",
            "error": None,
            "ignored": 0,
            "comparison": case.get("comparison"),
        }
        baseline = pathlib.Path(str(case["images"][0]))
        if case["params"]:
            entry["error"] = "parametrised test"
        elif case["snippet"] is None:
            entry["error"] = "not standalone"
        else:
            ours = out / f"{slug}.png"
            ignored: list[str] = []
            filename = pathlib.Path(str(case["file"])) if case.get("file") else None
            error = render(str(case["snippet"]), ours, ignored=ignored,
                           sample_data=sample_data, filename=filename)
            entry["ignored"] = len(ignored)
            if error is None:
                entry["ours"] = str(ours)
                nonwhite = _nonwhite_pixels(ours)
                entry["nonwhite"] = nonwhite
                if nonwhite is not None and nonwhite < BLANK_THRESHOLD:
                    entry["status"] = "blank"
                    entry["error"] = "blank render"
                else:
                    entry["status"] = "rendered"
                    rendered += 1
                    if baseline.exists():
                        result = metrics(baseline, ours)
                        metric_error = result.pop("error", None)
                        entry.update(result)
                        if metric_error is not None:
                            # Rendering succeeded; only the pixel comparison is unavailable.
                            entry["metrics_error"] = metric_error
                    else:
                        entry["status"] = "no baseline"
                        entry["error"] = f"missing baseline {baseline}"
            else:
                entry["status"] = "failed"
                entry["error"] = error
        if baseline.exists():
            # Copy the reference next to the gallery so the HTML stays browsable
            # when the directory is moved or published as a CI artifact.
            view = out / f"baseline_{slug}{baseline.suffix or '.png'}"
            shutil.copyfile(baseline, view)
            baseline_cell = f'<img src="{html.escape(view.name)}">'
        else:
            baseline_cell = "<pre>no baseline</pre>"
        ours_cell = (f'<img src="{html.escape(slug)}.png">' if entry.get("ours")
                     else f'<pre style="color:#c00">{html.escape(str(entry["error"] or ""))}</pre>')
        score = entry.get("rms")
        rows.append(
            f"<tr><td><b>{html.escape(case_id)}</b><br>"
            f"{entry['status']}<br>rms: {'n/a' if score is None else f'{score:.3f}'}"
            f"{source_details(case.get('source'))}</td>"
            f"<td>{baseline_cell}</td><td>{ours_cell}</td></tr>")
        case["status"] = entry["status"]
        case["error"] = entry["error"]
        case["ignored"] = entry["ignored"]
        case["ours"] = entry.get("ours")
        case["nonwhite"] = entry.get("nonwhite")
        case["shape_match"] = entry.get("shape_match")
        case["rms"] = entry.get("rms")
        case["mismatch_pct"] = entry.get("mismatch_pct")
        case["metrics_error"] = entry.get("metrics_error")
        print(f"{case_id:44} {entry['status']:9} {entry['error'] or ''}".rstrip())

    (out / "index.html").write_text(
        "<table border=1 cellpadding=6><tr><th>case</th><th>matplotlib baseline</th>"
        "<th>matplotvite</th></tr>" + "".join(rows)
        + "</table><style>img{max-width:420px}"
        "details.source pre,.source{max-height:24rem;overflow:auto;"
        "background:#f6f8fa;padding:.5rem;font-size:.8rem}</style>",
        encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    statuses = [str(case["status"]) for case in cases]
    ignored_total = sum(int(case.get("ignored", 0) or 0) for case in cases)
    print(f"\n{len(cases)} baseline cases: {rendered} rendered, "
          f"{statuses.count('blank')} blank, {statuses.count('failed')} failed, "
          f"{statuses.count('unsupported')} unsupported, {ignored_total} ignored "
          f"calls; gallery: {out / 'index.html'}")
    return {"cases": len(cases), "rendered": rendered,
            "blank": statuses.count("blank"),
            "failed": statuses.count("failed"),
            "unsupported": statuses.count("unsupported"),
            "ignored": ignored_total}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path,
                        help="Matplotlib checkout or sdist root")
    parser.add_argument("--examples", type=pathlib.Path,
                        help="render the gallery scripts under this checkout instead")
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--no-reference", action="store_true",
                        help="with --examples, skip rendering the Matplotlib reference images (CI speed-up)")
    parser.add_argument("--limit", type=int, default=None,
                        help="render an evenly spaced subset of this many cases")
    parser.add_argument("--json", type=pathlib.Path, dest="json_out", default=None)
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    default_out = "dist/mpl-examples" if args.examples else "dist/mpl-corpus"
    args.out = args.out or pathlib.Path(default_out)
    args.json_out = args.json_out or args.out / "manifest.json"
    if args.examples:
        return harvest_examples_gallery(args.examples, args.out, args.json_out,
                                        references=not args.no_reference,
                                        limit=args.limit)

    tests_root = find_tests_root(args.source)
    if tests_root is None:
        print("No Matplotlib baseline images found. Point --source at a checkout or "
              "run `pip download --no-binary :all: matplotlib`; the wheel omits them.")
        return 1
    harvest_gallery(tests_root, args.out, args.json_out, limit=args.limit)
    return 0


def harvest_examples_gallery(source: pathlib.Path, out: pathlib.Path,
                             manifest_path: pathlib.Path,
                             references: bool = True,
                             limit: int | None = None) -> int:
    """Render every gallery example and report the ones our API cannot express."""
    examples_root = find_examples_root(source)
    if examples_root is None:
        print(f"No gallery examples found under {source}.")
        return 1
    cases = _sample_cases(harvest_examples(examples_root), limit)
    sample_data = find_sample_data(source)
    out.mkdir(parents=True, exist_ok=True)
    # Render the untouched scripts with matplotlib first, in parallel child
    # interpreters, so the gallery can show the reference beside our render.
    # Drop references from an earlier run; a case that no longer renders or
    # moved category would otherwise leave an orphan image behind.
    for stale in out.glob("*-matplotlib.png"):
        stale.unlink()
    mpl_available = importlib.util.find_spec("matplotlib") is not None
    refs: dict[str, tuple[str, str | None]] = {}
    if mpl_available and references:
        renderable = [
            case for case in cases
            if case["snippet"] is not None
            and case["category"] not in OUT_OF_SCOPE_CATEGORIES
            and not requires_gui(str(case.get("source", "")))
        ]

        def render_reference(case: dict[str, object]) -> tuple[str, str, str | None]:
            slug = str(case["id"]).replace("/", "_")
            path = out / f"{slug}-matplotlib.png"
            try:
                error = render_matplotlib(str(case["path"]), path,
                                          pathlib.Path(str(case["path"])).parent)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            return slug, str(path), error

        workers = min(4, os.cpu_count() or 1)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for slug, path, error in pool.map(render_reference, renderable):
                refs[slug] = (path, error)
    rows: list[str] = []
    statuses: dict[str, list[int]] = {}
    for case in cases:
        slug = str(case["id"]).replace("/", "_")
        entry = dict(case)
        entry["error"] = None
        entry["ignored"] = 0
        if case["snippet"] is None:
            entry["status"] = "unsupported"
            entry["error"] = "interactive or unparseable"
            entry["reason"] = "out_of_scope"
        elif case["category"] in OUT_OF_SCOPE_CATEGORIES:
            entry["status"] = "unsupported"
            entry["error"] = f"{case['category']} is out of scope"
            entry["reason"] = "out_of_scope"
        elif requires_gui(str(case.get("source", ""))):
            entry["status"] = "unsupported"
            entry["error"] = "requires a GUI toolkit"
            entry["reason"] = "out_of_scope"
        else:
            ours = out / f"{slug}.png"
            ignored: list[str] = []
            entry["error"] = render(str(case["snippet"]), ours,
                                    pathlib.Path(str(case["path"])).parent,
                                    ignored=ignored, sample_data=sample_data)
            entry["ignored"] = len(ignored)
            entry["status"] = ("rendered" if entry["error"] is None
                               else failure_status(str(entry["error"])))
            entry["reason"] = FAILURE_REASONS.get(str(entry["status"]))
            if entry["error"] is None:
                entry["ours"] = str(ours)
                entry["nonwhite"] = _nonwhite_pixels(ours)
                if entry["nonwhite"] is not None and entry["nonwhite"] < BLANK_THRESHOLD:
                    entry["status"] = "blank"
                    entry["reason"] = "bug"
        if case["snippet"] is not None and case["category"] not in OUT_OF_SCOPE_CATEGORIES:
            reference = refs.get(slug)
            if reference is None:
                entry["matplotlib_error"] = ("reference skipped" if mpl_available
                                             else "matplotlib is not installed")
            elif reference[1] is None:
                entry["matplotlib"] = reference[0]
            else:
                entry["matplotlib_error"] = reference[1]
        counts = statuses.setdefault(str(case["category"]), [0, 0])
        counts[0] += 1
        counts[1] += entry["status"] == "rendered"
        view = (f'<img src="{html.escape(slug)}.png">' if entry.get("ours")
                else f'<pre style="color:#c00">{html.escape(str(entry["error"]))}</pre>')
        if entry.get("matplotlib"):
            mpl_view = (f'<img src="{html.escape(pathlib.Path(str(entry["matplotlib"])).name)}">')
        elif entry.get("matplotlib_error"):
            mpl_view = (f'<pre style="color:#c00">'
                        f'{html.escape(str(entry["matplotlib_error"]))}</pre>')
        else:
            mpl_view = "—"
        rows.append(
            f"<tr><td>{html.escape(str(case['category']))}<br>"
            f"<b>{html.escape(str(case['id']))}</b><br>"
            f"{html.escape(str(case['description']))}"
            f"{source_details(case.get('source'))}</td>"
            f"<td>{view}</td><td>{mpl_view}</td><td>{entry['status']}</td></tr>")
        entry.pop("source", None)
        case.clear()
        case.update(entry)
        print(f"{case['id']:60} {entry['status']:9} {entry['error'] or ''}".rstrip())

    summary = "".join(
        f"<li>{html.escape(name)}: {ok}/{total} rendered</li>"
        for name, (total, ok) in sorted(statuses.items()))
    def count(status: str) -> int:
        return sum(case["status"] == status for case in cases)

    rendered, blank = count("rendered"), count("blank")
    unsupported = count("unsupported")
    needs_api, gaps, bugs = (count("needs-api"), count("harvester-gap"),
                             count("bug"))
    ignored = sum(int(case.get("ignored", 0) or 0) for case in cases)
    reasons = {name: sum(case.get("reason") == name for case in cases)
               for name in ("out_of_scope", "harvester", "needs_api", "bug")}
    (out / "index.html").write_text(
        f"<p>{rendered}/{len(cases)} examples rendered, {blank} blank, "
        f"{unsupported} unsupported, {needs_api} needs API, {gaps} harvester "
        f"gaps, {bugs} bugs, {ignored} ignored calls; reasons: "
        f"{reasons['out_of_scope']} out of scope, "
        f"{reasons['harvester']} harvester, {reasons['needs_api']} needs API, "
        f"{reasons['bug']} bugs</p><ul>{summary}</ul>"
        "<table border=1 cellpadding=6><tr><th>example</th><th>matplotvite</th>"
        "<th>matplotlib</th><th>status</th></tr>" + "".join(rows)
        + "</table><style>img{max-width:420px}"
        "details.source pre,.source{max-height:24rem;overflow:auto;"
        "background:#f6f8fa;padding:.5rem;font-size:.8rem}</style>",
        encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    print(f"\n{rendered}/{len(cases)} gallery examples rendered, {blank} blank, "
          f"{unsupported} unsupported, {needs_api} needs API, {gaps} harvester "
          f"gaps, {bugs} bugs, {ignored} ignored calls; reasons: "
          f"{reasons['out_of_scope']} out of scope, "
          f"{reasons['harvester']} harvester, {reasons['needs_api']} needs API, "
          f"{reasons['bug']} bugs; gallery: {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
