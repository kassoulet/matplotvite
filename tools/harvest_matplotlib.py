"""Harvest Matplotlib's baseline-image tests into a renderable comparison gallery.

usage: python tools/harvest_matplotlib.py [--source PATH] [--out dist/mpl-corpus]

Each `@image_comparison(...)` test in Matplotlib's own test suite names a
baseline PNG that Matplotlib asserts its renderer reproduces. This tool pulls
those tests out of a Matplotlib checkout (the wheel ships the test modules but
not `baseline_images`, so an sdist or git checkout is required), rewrites each
test body into a standalone snippet, renders it with matplotvite and writes a
side-by-side gallery of baseline vs. ours plus a manifest of every case.

Exit status is 1 only when no baseline images could be found.
"""
from __future__ import annotations

import argparse
import ast
import html
import json
import pathlib
import re
import textwrap

import numpy as np
import matplotvite

# Bodies that cannot be rendered out of process: pytest fixtures, checks against
# Matplotlib internals, or interactive backends.
SKIP_RE = re.compile(r"pytest\.|check_figures_equal\(|\binput\(|themes\.|savefig\(")
IMPORT_RE = re.compile(r"^\s*(import|from)\s+(matplotlib|numpy)\b")
ASSERT_RE = re.compile(r"^\s*assert\b")


def find_tests_root(source: pathlib.Path | None) -> pathlib.Path | None:
    """Locate the `matplotlib/tests` directory inside a checkout or an sdist."""
    if source is not None:
        for candidate in (source, source / "lib/matplotlib/tests",
                          source / "matplotlib/tests",
                          *sorted(source.glob("*/lib/matplotlib/tests"))):
            if (candidate / "baseline_images").is_dir():
                return candidate
        return None
    for candidate in sorted(pathlib.Path("dist/mpl-sdist").glob("*/lib/matplotlib/tests")):
        if (candidate / "baseline_images").is_dir():
            return candidate
    return None


def _baseline_list(node: ast.AST) -> list[str] | None:
    """Evaluate a baseline list, including the `[f"x_{i}.png" for i in range(n)]` form."""
    try:
        value = ast.literal_eval(node)
    except ValueError:
        try:
            value = eval(compile(ast.Expression(node), "<baseline>", "eval"),  # noqa: S307
                         {"__builtins__": {}}, {"range": range})
        except Exception:  # noqa: BLE001 - unparseable baselines are simply skipped
            return None
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else None


def image_comparison_baselines(func: ast.FunctionDef) -> list[str] | None:
    """Baseline image names from a stacked `@image_comparison(...)` decorator."""
    for deco in func.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        name = getattr(deco.func, "id", getattr(deco.func, "attr", ""))
        if name != "image_comparison":
            continue
        for arg in deco.args:
            baselines = _baseline_list(arg)
            if baselines is not None:
                return baselines
        for keyword in deco.keywords:
            if keyword.arg == "baseline_images":
                return _baseline_list(keyword.value)
    return None


def _resolve_baseline(tests_root: pathlib.Path, stem: str, name: str) -> pathlib.Path:
    """`baseline_images` names omit extensions; prefer the PNG variant."""
    base = tests_root / "baseline_images" / stem / name
    if base.suffix:
        return base
    for suffix in (".png", ".svg", ".pdf"):
        if base.with_suffix(suffix).exists():
            return base.with_suffix(suffix)
    return base.with_suffix(".png")


def prepare_body(source: str) -> str | None:
    """Rewrite a test body into a runnable matplotvite snippet."""
    body = textwrap.dedent(source)
    if SKIP_RE.search(body):
        return None
    lines = [line for line in body.splitlines()
             if not IMPORT_RE.match(line) and not ASSERT_RE.match(line)]
    code = "\n".join(lines).strip("\n")
    if not code.strip():
        return None
    return code + "\nplt.savefig(OUT, dpi=100)\n"


def harvest(tests_root: pathlib.Path) -> list[dict[str, object]]:
    """Extract every image-comparison case from the test modules."""
    cases: list[dict[str, object]] = []
    for module_path in sorted(tests_root.glob("test_*.py")):
        text = module_path.read_text(encoding="utf-8")
        try:
            module = ast.parse(text)
        except SyntaxError:
            continue
        for func in module.body:
            if not isinstance(func, ast.FunctionDef):
                continue
            baselines = image_comparison_baselines(func)
            if baselines is None:
                continue
            images = [_resolve_baseline(tests_root, module_path.stem, name)
                      for name in baselines]
            source = textwrap.dedent("\n".join(
                ast.get_source_segment(text, node) or "" for node in func.body))
            cases.append({
                "id": f"{module_path.stem}/{func.name}",
                "module": module_path.name,
                "function": func.name,
                "params": [arg.arg for arg in func.args.args],
                "baselines": baselines,
                "images": [str(p) for p in images],
                "source": source,
                "snippet": prepare_body(source),
            })
    return cases


def render(snippet: str, out_path: pathlib.Path) -> str | None:
    """Render a snippet with matplotvite; return an error string or None."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    namespace = {"plt": matplotvite, "mpl": matplotvite, "np": np,
                 "OUT": str(out_path)}
    try:
        matplotvite.close("all")
        np.random.seed(0)
        exec(snippet, namespace)  # noqa: S102 - source is Matplotlib's own test suite
        if not out_path.exists():
            return "no figure saved"
        return None
    except Exception as exc:  # noqa: BLE001 - the gallery records every failure
        return f"{type(exc).__name__}: {exc}"


def metrics(baseline: pathlib.Path, ours: pathlib.Path) -> dict[str, object]:
    """RMS and visibly-different percentage against the baseline PNG."""
    from visual_compare import compare_images  # local tool, same metric as the gallery

    if not baseline.exists():
        return {"error": f"missing baseline {baseline}"}
    try:
        return compare_images(baseline, ours)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path,
                        help="Matplotlib checkout or sdist root")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("dist/mpl-corpus"))
    parser.add_argument("--json", type=pathlib.Path, dest="json_out",
                        default=pathlib.Path("dist/mpl-corpus/manifest.json"))
    args = parser.parse_args()

    tests_root = find_tests_root(args.source)
    if tests_root is None:
        print("No Matplotlib baseline images found. Point --source at a checkout or "
              "run `pip download --no-binary :all: matplotlib`; the wheel omits them.")
        return 1
    cases = harvest(tests_root)
    args.out.mkdir(parents=True, exist_ok=True)

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
        }
        baseline = pathlib.Path(str(case["images"][0]))
        if case["params"]:
            entry["error"] = "parametrised test"
        elif case["snippet"] is None:
            entry["error"] = "not standalone"
        else:
            ours = args.out / f"{slug}.png"
            error = render(str(case["snippet"]), ours)
            if error is None:
                entry["status"] = "rendered"
                rendered += 1
                entry["ours"] = str(ours)
                result = metrics(baseline, ours)
                entry.update(result)
                if result.get("error"):
                    entry["status"] = "no baseline"
            else:
                entry["status"] = "failed"
                entry["error"] = error
        rel = baseline.resolve()
        baseline_cell = (f'<img src="{html.escape(str(rel))}">' if baseline.exists()
                         else "<pre>no baseline</pre>")
        ours_cell = (f'<img src="{html.escape(slug)}.png">' if entry.get("ours")
                     else f'<pre style="color:#c00">{html.escape(str(entry["error"] or ""))}</pre>')
        score = entry.get("rms")
        rows.append(
            f"<tr><td><b>{html.escape(case_id)}</b><br>"
            f"{entry['status']}<br>rms: {'n/a' if score is None else f'{score:.3f}'}</td>"
            f"<td>{baseline_cell}</td><td>{ours_cell}</td></tr>")
        case["status"] = entry["status"]
        case["error"] = entry["error"]
        case["ours"] = entry.get("ours")
        case["shape_match"] = entry.get("shape_match")
        case["rms"] = entry.get("rms")
        case["mismatch_pct"] = entry.get("mismatch_pct")
        print(f"{case_id:44} {entry['status']:9} {entry['error'] or ''}".rstrip())

    (args.out / "index.html").write_text(
        "<table border=1 cellpadding=6><tr><th>case</th><th>matplotlib baseline</th>"
        "<th>matplotvite</th></tr>" + "".join(rows)
        + "</table><style>img{max-width:420px}</style>", encoding="utf-8")
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    statuses = [str(case["status"]) for case in cases]
    print(f"\n{len(cases)} baseline cases: {rendered} rendered, "
          f"{statuses.count('failed')} failed, {statuses.count('unsupported')} "
          f"unsupported; gallery: {args.out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
