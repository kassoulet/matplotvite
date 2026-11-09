"""Classify Seaborn's gallery examples against matplotvite's Matplotlib surface.

usage: python tools/harvest_seaborn.py [--source PATH] [--out dist/seaborn-gallery]

Seaborn draws through Matplotlib's internals, so an example cannot simply run
against matplotvite. Instead each script under `examples/` is parsed and every
`sns.*` and `plt.*` call is classified:

  pass         theming, palettes and plotting calls that only need API we have
  needs-api    a plotting function whose Matplotlib capability is missing
  unsupported  needs machinery outside our renderer (e.g. SciPy clustering)

The report lists the missing capability per function, which is the list to
feed back into TRACE priorities. Statuses are static capability statements:
Seaborn's own gallery images are docs build artifacts, so there is no
reference image to diff against.
"""
from __future__ import annotations

import argparse
import ast
import collections
import html
import json
import pathlib

import matplotvite

# `sns.<name>` -> Matplotlib capability it needs. `None` means theming or a
# palette helper, which only touch rcParams/colours and already map onto our
# style presets. Data helpers are not plotting calls and are ignored.
FEATURES: dict[str, str | None] = {
    "set": None, "set_theme": None, "set_style": None, "set_context": None,
    "set_palette": None, "color_palette": None, "hls_palette": None,
    "husl_palette": None, "mpl_palette": None, "cubehelix_palette": None,
    "dark_palette": None, "light_palette": None, "diverging_palette": None,
    "blend_palette": None, "xkcd_rgb": None, "crayons": None,
    "set_color_codes": None, "despine": None, "move_legend": None,
    "axes_style": None, "plotting_context": None, "reset_defaults": None,
    "reset_orig": None,
    "lineplot": "line + band with hue/style grouping",
    "scatterplot": "scatter with hue/style grouping",
    "relplot": "relational plot over a FacetGrid",
    "barplot": "bars with error bars and grouping",
    "countplot": "count bars",
    "boxplot": "box plot with categorical grouping",
    "boxenplot": "letter-value box plot",
    "violinplot": "violin bodies with grouping",
    "stripplot": "categorical jitter",
    "swarmplot": "swarm layout",
    "pointplot": "point estimates with error bars",
    "histplot": "histogram bars with stat options",
    "kdeplot": "kernel density curves (KDE)",
    "ecdfplot": "empirical CDF step plot",
    "rugplot": "rug ticks along an axis",
    "heatmap": "pcolormesh with cell annotations",
    "jointplot": "joint figure with marginal axes",
    "JointGrid": "joint figure with marginal axes",
    "PairGrid": "multi-axes grid API",
    "FacetGrid": "multi-axes grid API",
    "pairplot": "pairwise axes grid",
    "catplot": "categorical plots over a FacetGrid",
    "displot": "distribution plots over a FacetGrid",
    "lmplot": "regression over a FacetGrid (statsmodels)",
    "regplot": "linear regression fit (statsmodels)",
    "residplot": "regression residuals (statsmodels)",
}
UNSUPPORTED = {
    "clustermap": "hierarchical clustering (SciPy) and dendrogram layout",
}
# Data loading is not a plotting capability: it needs pandas plus a download.
DATA_HELPERS = {"load_dataset", "get_dataset"}
IGNORED = {"set_config", "reset_defaults"}


def find_examples_root(source: pathlib.Path | None) -> pathlib.Path | None:
    """Locate the `examples/` directory of a Seaborn checkout."""
    candidates = ([source, source / "examples"] if source is not None
                  else [pathlib.Path("dist/sns-src"), pathlib.Path("dist/sns-src/examples")])
    for candidate in candidates:
        if candidate is not None and any(candidate.glob("*.py")):
            return candidate
    return None


def calls_in(tree: ast.AST) -> tuple[list[str], list[str]]:
    """`sns.*` and `plt.*` call names used by a gallery script."""
    seaborn_calls: list[str] = []
    pyplot_calls: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and owner.id == "sns":
            if node.func.attr not in seaborn_calls:
                seaborn_calls.append(node.func.attr)
        elif isinstance(owner, ast.Name) and owner.id in ("plt", "matplotlib.pyplot"):
            pyplot_calls.append(node.func.attr)
    return seaborn_calls, sorted(set(pyplot_calls))


def classify(seaborn_calls: list[str], pyplot_calls: list[str]) -> dict[str, object]:
    """Status plus the capabilities and pyplot functions that are missing."""
    plotting = [name for name in seaborn_calls if name not in DATA_HELPERS]
    missing_plt = [name for name in pyplot_calls if not hasattr(matplotvite, name)]
    hard = [name for name in plotting if name in UNSUPPORTED]
    needs = [FEATURES[name] for name in plotting
             if FEATURES.get(name) and name not in UNSUPPORTED]
    unknown = [name for name in plotting if name not in FEATURES and name not in UNSUPPORTED]
    if hard:
        status = "unsupported"
    elif needs or missing_plt or unknown:
        status = "needs-api"
    else:
        status = "pass"
    return {"status": status, "needs": sorted(set(needs)), "unknown": unknown,
            "unsupported": hard, "missing_pyplot": missing_plt}


def harvest(root: pathlib.Path) -> list[dict[str, object]]:
    """One classified record per gallery script."""
    cases: list[dict[str, object]] = []
    for script in sorted(root.glob("*.py")):
        text = script.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        docstring = ast.get_docstring(tree) or ""
        summary = next((line.strip() for line in docstring.splitlines()
                        if line.strip() and not set(line.strip()) <= {"=", "-"}), "")
        seaborn_calls, pyplot_calls = calls_in(tree)
        result = classify(seaborn_calls, pyplot_calls)
        cases.append({
            "id": script.stem,
            "path": str(script),
            "description": summary,
            "sns": seaborn_calls,
            "plt": pyplot_calls,
            "status": result["status"],
            "needs": result["needs"],
            "unknown": result["unknown"],
            "unsupported": result["unsupported"],
            "missing_pyplot": result["missing_pyplot"],
        })
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path,
                        help="Seaborn checkout or its examples/ directory")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("dist/seaborn-gallery"))
    args = parser.parse_args()

    root = find_examples_root(args.source)
    if root is None:
        print("No Seaborn examples found. Clone the repository (its gallery images "
              "are build artifacts) or pass --source.")
        return 1
    cases = harvest(root)
    write_gallery(cases, args.out)
    return 0


def write_gallery(cases: list[dict[str, object]],
                  out: pathlib.Path) -> collections.Counter[str]:
    """Write the classified gallery and manifest; return the per-status counts."""
    out.mkdir(parents=True, exist_ok=True)

    features: collections.Counter[str] = collections.Counter()
    rows: list[str] = []
    for case in cases:
        features.update(str(v) for v in case["needs"])
        detail = "; ".join([str(v) for v in case["needs"]] + [str(v) for v in case["unknown"]]
                           + [f"plt.{v} missing" for v in case["missing_pyplot"]]
                           + [str(UNSUPPORTED[v]) for v in case["unsupported"]])
        color = {"pass": "#0a0", "needs-api": "#b80", "unsupported": "#c00"}[str(case["status"])]
        rows.append(
            f"<tr><td><b>{html.escape(str(case['id']))}</b><br>"
            f"{html.escape(str(case['description']))}</td>"
            f"<td style=\"color:{color}\"><b>{case['status']}</b></td>"
            f"<td>{html.escape(detail)}</td>"
            f"<td><code>{html.escape(', '.join(str(v) for v in case['sns']))}</code></td></tr>")

    summary = collections.Counter(str(case["status"]) for case in cases)
    needs_table = "".join(
        f"<li>{html.escape(feature)} ({count} example{'s' if count != 1 else ''})</li>"
        for feature, count in features.most_common())
    (out / "index.html").write_text(
        f"<p>{len(cases)} Seaborn examples: {summary['pass']} pass, "
        f"{summary['needs-api']} needs-API, {summary['unsupported']} unsupported.</p>"
        f"<h2>Missing Matplotlib capabilities</h2><ul>{needs_table}</ul>"
        "<table border=1 cellpadding=6><tr><th>example</th><th>status</th>"
        "<th>needs</th><th>Seaborn calls</th></tr>" + "".join(rows) + "</table>",
        encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    print(f"{len(cases)} examples: {summary['pass']} pass, {summary['needs-api']} needs-API, "
          f"{summary['unsupported']} unsupported; gallery: {out / 'index.html'}")
    for feature, count in features.most_common(8):
        print(f"{count:3}  {feature}")
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
