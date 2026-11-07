"""Trace matplotlib test-suite API usage that plt_rs doesn't support.

usage: python tools/trace_unsupported.py <matplotlib/tests dir> [out.md] [options]

Needs matplotlib importable (reference API only, dev tool) and plt_rs installed.
Static (AST) scan: counts `plt.X`, and `.method(...)` calls whose name is a public
pyplot / Axes / Figure method; also kwargs per call name.

The supported side is introspected from plt_rs itself (module, `Axes`, `Figure`),
including accepted keyword arguments via `inspect.signature`, so the baseline
can't go stale when the wrapper grows.

options:
  --check             compare against the baseline and exit 1 on any regression
                      (drops a supported API name, or lowers the call-site count)
  --baseline PATH     baseline json (default: tools/trace_baseline.json)
  --update-baseline   rewrite the baseline json from the current tree
"""
import ast, collections, inspect, json, pathlib, sys

import matplotlib
import matplotlib.pyplot as mpl_plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import plt_rs

argv = sys.argv[1:]
check = "--check" in argv
update_baseline = "--update-baseline" in argv
baseline_path = pathlib.Path(__file__).with_name("trace_baseline.json")
positional = []
i = 0
while i < len(argv):
    if argv[i] == "--baseline" and i + 1 < len(argv):
        baseline_path, i = pathlib.Path(argv[i + 1]), i + 2
        continue
    if not argv[i].startswith("--"):
        positional.append(argv[i])
    i += 1
if not positional:
    sys.exit(__doc__.strip())


def pub(obj):
    return {n for n in dir(obj) if not n.startswith("_") and callable(getattr(obj, n, None))}


PYPLOT, AXES, FIGURE = pub(mpl_plt), pub(Axes), pub(Figure)
OURS = {"pyplot": plt_rs, "Axes": plt_rs.Axes, "Figure": plt_rs.Figure}
SUPPORTED = {kind: pub(obj) for kind, obj in OURS.items()}


def accepted_kwargs(kind, name):
    """Keyword names our callable takes; `None` means it accepts anything."""
    fn = getattr(OURS[kind], name, None)
    if fn is None:
        return set()
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return set()
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params):
        return None
    return {p.name for p in params if p.name not in ("self", "cls")}


files = sorted(pathlib.Path(positional[0]).rglob("test_*.py"))
calls = collections.Counter()  # (kind, name) -> n
kw = collections.defaultdict(collections.Counter)  # name -> kwarg -> n
where = collections.defaultdict(set)
for f in files:
    try:
        tree = ast.parse(f.read_text())
    except SyntaxError:
        continue
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        name, base = n.func.attr, n.func.value
        if isinstance(base, ast.Name) and base.id == "plt" and name in PYPLOT:
            kind = "pyplot"
        elif name in AXES:
            kind = "Axes"
        elif name in FIGURE:
            kind = "Figure"
        else:
            continue
        calls[kind, name] += 1
        where[kind, name].add(f.name)
        for k in n.keywords:
            if k.arg:
                kw[name][k.arg] += 1


def supported(kind, name):
    return name in SUPPORTED[kind]


def kwarg_ok(name, k):
    """A kwarg counts as supported if any of our implementations accepts it."""
    kinds = [kind for kind in SUPPORTED if supported(kind, name)]
    acc = [accepted_kwargs(kind, name) for kind in kinds]
    return any(a is None or k in a for a in acc)


out = [
    "# matplotlib test-suite coverage trace",
    "",
    f"{len(files)} test files scanned. Static AST scan, counts are call sites.",
    "",
]
tot = sum(calls.values())
ok = sum(c for (k, n), c in calls.items() if supported(k, n))
out += [f"Call sites supported: **{ok}/{tot}** ({100 * ok // max(tot, 1)}%)", ""]
for kind in ("pyplot", "Axes", "Figure"):
    rows = sorted(((c, n) for (k, n), c in calls.items() if k == kind), reverse=True)
    out += [f"## {kind}: unsupported (by call count)", "", "| calls | name | files |", "|--:|---|--:|"]
    out += [f"| {c} | `{n}` | {len(where[kind, n])} |" for c, n in rows if not supported(kind, n)]
    out += ["", f"{kind} supported: " + (", ".join(f"`{n}`" for c, n in rows if supported(kind, n)) or "none"), ""]

out += ["## Unsupported kwargs on supported calls", ""]
any_bad = False
for name in sorted(kw, key=lambda n: -sum(kw[n].values())):
    bad = [(c, k) for k, c in kw[name].items() if not kwarg_ok(name, k)]
    if bad:
        any_bad = True
        out.append(f"- `{name}`: " + ", ".join(f"`{k}` ({c})" for c, k in sorted(bad, reverse=True)[:20]))
if not any_bad:
    out.append("none")

if not check:
    pathlib.Path(positional[1] if len(positional) > 1 else "TRACE.md").write_text(
        "\n".join(out) + "\n"
    )
print(out[4])

supported_names = sorted(
    f"{kind}.{name}" for kind, names in SUPPORTED.items() for name in names
)
baseline = {
    "matplotlib": matplotlib.__version__,
    "files": len(files),
    "total": tot,
    "supported": ok,
    "supported_names": supported_names,
}

if update_baseline:
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
    print(f"baseline written to {baseline_path} ({ok}/{tot})")

if check:
    if not baseline_path.exists():
        sys.exit(f"no baseline at {baseline_path}; create one with --update-baseline")
    prev = json.loads(baseline_path.read_text())
    prev_names = set(prev.get("supported_names", []))
    lost = sorted(prev_names - set(supported_names))
    gained = sorted(set(supported_names) - prev_names)
    prev_ok = prev.get("supported", ok)
    print(
        f"baseline: {prev_ok}/{prev.get('total')} "
        f"(matplotlib {prev.get('matplotlib')}, {prev.get('files')} files)"
    )
    print(f"current : {ok}/{tot} (matplotlib {matplotlib.__version__}, {len(files)} files)")
    if gained:
        print(f"newly supported: {', '.join(gained[:15])}")
    if prev.get("total") not in (None, tot):
        print(f"note: call-site total moved {prev['total']} -> {tot} (matplotlib drift?)")
    if lost:
        print(
            f"coverage regression: {len(lost)} API names no longer supported: "
            + ", ".join(lost[:20]),
            file=sys.stderr,
        )
    if ok < prev_ok:
        print(
            f"coverage regression: {prev_ok} -> {ok} supported call sites",
            file=sys.stderr,
        )
    if lost or ok < prev_ok:
        sys.exit(1)
    print(f"coverage held: {ok}/{tot}")
