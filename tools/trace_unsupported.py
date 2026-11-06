"""Trace matplotlib test-suite API usage that plt_rs doesn't support.

usage: python tools/trace_unsupported.py <matplotlib/tests dir> [out.md]
Needs matplotlib importable (reference API only, dev tool) and plt_rs installed.
Static (AST) scan: counts `plt.X`, and `.method(...)` calls whose name is a public
pyplot / Axes / Figure method; also kwargs per call name.
"""
import ast, collections, pathlib, sys
import matplotlib.pyplot as mpl_plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import plt_rs

pub = lambda o: {n for n in dir(o) if not n.startswith("_") and callable(getattr(o, n, None))}
PYPLOT, AXES, FIGURE = pub(mpl_plt), pub(Axes), pub(Figure)
OURS_PLT, OURS_FIG = pub(plt_rs), pub(plt_rs.Figure)
# plt_rs has no Axes yet: Axes API is supported only if figure-level shortcut exists
OURS_AX = set()
SUPPORTED_KW = {"plot": {"label", "color"}, "figure": {"figsize"}, "savefig": set()}

files = sorted(pathlib.Path(sys.argv[1]).rglob("test_*.py"))
calls = collections.Counter()      # (kind, name) -> n
kw = collections.defaultdict(collections.Counter)
where = collections.defaultdict(set)
for f in files:
    try: tree = ast.parse(f.read_text())
    except SyntaxError: continue
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)): continue
        name, base = n.func.attr, n.func.value
        if isinstance(base, ast.Name) and base.id == "plt" and name in PYPLOT: kind = "pyplot"
        elif name in AXES and name in FIGURE | AXES and not (isinstance(base, ast.Name) and base.id == "plt"): kind = "Axes"
        elif name in FIGURE: kind = "Figure"
        else: continue
        calls[kind, name] += 1; where[kind, name].add(f.name)
        for k in n.keywords:
            if k.arg: kw[name][k.arg] += 1

def supported(kind, name):
    return name in {"pyplot": OURS_PLT, "Axes": OURS_AX, "Figure": OURS_FIG}[kind]

out = ["# matplotlib test-suite coverage trace", "",
       f"{len(files)} test files scanned. Static AST scan, counts are call sites.", ""]
tot = sum(calls.values()); ok = sum(c for (k, n), c in calls.items() if supported(k, n))
out += [f"Call sites supported: **{ok}/{tot}** ({100*ok//max(tot,1)}%)", ""]
for kind in ("pyplot", "Axes", "Figure"):
    rows = sorted(((c, n) for (k, n), c in calls.items() if k == kind), reverse=True)
    out += [f"## {kind}: unsupported (by call count)", "", "| calls | name | files |", "|--:|---|--:|"]
    out += [f"| {c} | `{n}` | {len(where[kind, n])} |" for c, n in rows if not supported(kind, n)]
    out += ["", f"{kind} supported: " + (", ".join(f"`{n}`" for c, n in rows if supported(kind, n)) or "none"), ""]
out += ["## Unsupported kwargs on supported calls", ""]
for name, allowed in SUPPORTED_KW.items():
    bad = [(c, k) for k, c in kw[name].items() if k not in allowed]
    if bad: out.append(f"- `{name}`: " + ", ".join(f"`{k}` ({c})" for c, k in sorted(bad, reverse=True)[:20]))
pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "TRACE.md").write_text("\n".join(out) + "\n")
print(out[3])
