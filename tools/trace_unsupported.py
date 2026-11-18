"""Trace matplotlib test-suite API usage and classify our compatibility surface.

usage: python tools/trace_unsupported.py <matplotlib/tests dir> [out.md] [options]

Needs matplotlib importable (reference API only, dev tool) and matplotvite installed.
Static (AST) scan: counts `plt.X`, and `.method(...)` calls whose name is a public
pyplot / Axes / Figure method; also kwargs per call name.

The compatibility side is introspected from matplotvite itself (module, `Axes`,
`Figure`). A public callable is classified as:
  implemented          a real function or class;
  accepted-and-ignored a shim whose body only calls `_ignored` or returns
                       `None`/`self`, plus pyplot wrappers that delegate to one;
  missing              no such public callable.
This keeps the report honest instead of counting no-op shims as implemented.

options:
  --check             compare against the baseline and exit 1 on any regression
                      (an implemented API becomes ignored or missing, or a
                      previously available API disappears)
  --json              print the coverage counts as JSON and skip writing the report
  --baseline PATH     baseline json (default: tools/trace_baseline.json)
  --update-baseline   rewrite the baseline json from the current tree
"""
import ast
import collections
import inspect
import json
import pathlib
import sys
import textwrap

import matplotlib
import matplotlib.pyplot as mpl_plt
import matplotvite
from matplotlib.axes import Axes
from matplotlib.figure import Figure

argv = sys.argv[1:]
check = "--check" in argv
json_output = "--json" in argv
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
OURS = {"pyplot": matplotvite, "Axes": matplotvite.Axes, "Figure": matplotvite.Figure}
AVAILABLE = {kind: pub(obj) for kind, obj in OURS.items()}

_NOOP_FACTORIES = frozenset({"_LegendHandle", "_NoopContext"})
_STATUS = {}


def _function_node(fn):
    """Return the function AST for `fn`, or None for classes and builtins."""
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, TypeError, SyntaxError):
        return None
    if len(tree.body) != 1:
        return None
    node = tree.body[0]
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    return node


def _body_without_docstring(node):
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return body


def _is_noop_statement(statement):
    if isinstance(statement, ast.Pass):
        return True
    if (isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and statement.value.value is Ellipsis):
        return True
    if isinstance(statement, ast.Return):
        value = statement.value
        if value is None:
            return True
        if isinstance(value, ast.Constant) and value.value in (None, Ellipsis):
            return True
        if isinstance(value, ast.Name) and value.id == "self":
            return True
        if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id in _NOOP_FACTORIES):
            return True
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        return (isinstance(statement.value.func, ast.Name)
                and statement.value.func.id == "_ignored")
    return False


def _is_noop(node):
    body = _body_without_docstring(node)
    return bool(body) and all(_is_noop_statement(statement) for statement in body)


def _delegated_target(kind, name):
    """Resolve `plt.foo` wrappers such as `return gca().foo(...)`."""
    if kind != "pyplot":
        return None
    node = _function_node(getattr(matplotvite, name, None))
    if node is None:
        return None
    body = _body_without_docstring(node)
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return None
    call = body[0].value
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
        return None
    base = call.func.value
    if not (isinstance(base, ast.Call) and isinstance(base.func, ast.Name)):
        return None
    if base.func.id not in ("gca", "gcf"):
        return None
    target_kind = "Axes" if base.func.id == "gca" else "Figure"
    return target_kind, call.func.attr


def status(kind, name):
    """Return 'implemented', 'ignored', or 'missing' for one public callable."""
    key = (kind, name)
    if key in _STATUS:
        return _STATUS[key]
    if name not in AVAILABLE[kind]:
        result = "missing"
    else:
        target = _delegated_target(kind, name)
        if target is not None:
            result = status(*target)
        else:
            node = _function_node(getattr(OURS[kind], name))
            result = "ignored" if node is not None and _is_noop(node) else "implemented"
    _STATUS[key] = result
    return result


def accepted_kwargs(kind, name):
    """Keyword names our callable takes; `None` means it accepts anything."""
    target = _delegated_target(kind, name)
    if target is not None:
        return accepted_kwargs(*target)
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
        tree = ast.parse(f.read_text(encoding="utf-8"))
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


def rows(kind, wanted):
    return sorted(
        ((count, name) for (call_kind, name), count in calls.items()
         if call_kind == kind and status(kind, name) == wanted),
        reverse=True,
    )


def percent(value, total):
    return 100 * value // max(total, 1)


tot = sum(calls.values())
implemented = sum(c for (kind, name), c in calls.items()
                  if status(kind, name) == "implemented")
ignored = sum(c for (kind, name), c in calls.items()
              if status(kind, name) == "ignored")
missing = tot - implemented - ignored

out = [
    "# matplotlib test-suite coverage trace",
    "",
    f"{len(files)} test files scanned. Static AST scan, counts are call sites.",
    "",
    f"Call sites implemented: **{implemented}/{tot}** ({percent(implemented, tot)}%)",
    f"Call sites accepted and ignored: **{ignored}/{tot}** ({percent(ignored, tot)}%)",
    f"Call sites missing: **{missing}/{tot}** ({percent(missing, tot)}%)",
    "",
    "`implemented` produces renderer output or real state; "
    "`accepted and ignored` exists as a no-op compatibility shim; "
    "`missing` is not available.",
    "",
]

priority = sorted(
    (
        (count, kind, name, len(where[kind, name]))
        for (kind, name), count in calls.items()
        if status(kind, name) == "missing"
    ),
    reverse=True,
)[:25]
out += [
    "## Priority gaps",
    "",
    "Missing call sites sorted by how often matplotlib's own tests use them.",
    "",
    "| calls | API | files |",
    "|--:|---|---:|",
]
out += [f"| {count} | `{kind}.{name}` | {files} |" for count, kind, name, files in priority]
out += [""]

for kind in ("pyplot", "Axes", "Figure"):
    out += [f"## {kind}: implemented", ""]
    implemented_names = [name for _, name in rows(kind, "implemented")]
    out += [", ".join(f"`{name}`" for name in implemented_names) or "none", ""]

    out += [f"## {kind}: accepted and ignored", ""]
    ignored_rows = rows(kind, "ignored")
    if ignored_rows:
        out += ["| calls | name | files |", "|--:|---|--:|"]
        out += [f"| {count} | `{name}` | {len(where[kind, name])} |"
                for count, name in ignored_rows]
    else:
        out += ["none"]
    out += [""]

    out += [f"## {kind}: missing", ""]
    missing_rows = rows(kind, "missing")
    if missing_rows:
        out += ["| calls | name | files |", "|--:|---|--:|"]
        out += [f"| {count} | `{name}` | {len(where[kind, name])} |"
                for count, name in missing_rows]
    else:
        out += ["none"]
    out += [""]

out += ["## Unsupported kwargs on implemented calls", ""]
any_bad = False
for name in sorted(kw, key=lambda n: -sum(kw[n].values())):
    kinds = [kind for kind in AVAILABLE if status(kind, name) == "implemented"]
    if not kinds:
        continue
    bad = []
    for k, count in kw[name].items():
        accepted = [accepted_kwargs(kind, name) for kind in kinds]
        if not any(value is None or k in value for value in accepted):
            bad.append((count, k))
    if bad:
        any_bad = True
        out.append(f"- `{name}`: " + ", ".join(
            f"`{k}` ({count})" for count, k in sorted(bad, reverse=True)[:20]))
if not any_bad:
    out.append("none")

if not check and not json_output:
    pathlib.Path(positional[1] if len(positional) > 1 else "TRACE.md").write_text(
        "\n".join(out) + "\n"
    )
if not json_output:
    print(f"implemented {implemented}/{tot}, accepted and ignored {ignored}/{tot}, "
          f"missing {missing}/{tot}")

implemented_names = sorted(
    f"{kind}.{name}" for kind, names in AVAILABLE.items()
    for name in names if status(kind, name) == "implemented"
)
ignored_names = sorted(
    f"{kind}.{name}" for kind, names in AVAILABLE.items()
    for name in names if status(kind, name) == "ignored"
)
supported_names = sorted(set(implemented_names) | set(ignored_names))
baseline = {
    "matplotlib": matplotlib.__version__,
    "files": len(files),
    "total": tot,
    "implemented": implemented,
    "accepted_ignored": ignored,
    "missing": missing,
    # `supported` remains the number of call sites whose API exists, including
    # accepted-and-ignored shims. New consumers should use `implemented`.
    "supported": implemented + ignored,
    "implemented_names": implemented_names,
    "ignored_names": ignored_names,
    "supported_names": supported_names,
}

if json_output:
    print(json.dumps({
        key: baseline[key] for key in
        ("matplotlib", "files", "total", "implemented", "accepted_ignored",
         "missing", "supported")
    }))
    sys.exit(0)

if update_baseline:
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
    print(f"baseline written to {baseline_path} ({implemented}/{tot} implemented)")

if check:
    if not baseline_path.exists():
        sys.exit(f"no baseline at {baseline_path}; create one with --update-baseline")
    prev = json.loads(baseline_path.read_text(encoding="utf-8"))
    prev_implemented_names = set(
        prev.get("implemented_names", prev.get("supported_names", []))
    )
    prev_ignored_names = set(prev.get("ignored_names", []))
    lost_implemented = sorted(prev_implemented_names - set(implemented_names))
    gained_implemented = sorted(set(implemented_names) - prev_implemented_names)
    lost_ignored = sorted(
        prev_ignored_names - set(ignored_names) - set(implemented_names)
    )
    prev_implemented = prev.get("implemented", prev.get("supported", implemented))
    print(
        f"baseline: implemented {prev_implemented}/{prev.get('total')} "
        f"(matplotlib {prev.get('matplotlib')}, {prev.get('files')} files)"
    )
    print(
        f"current : implemented {implemented}/{tot}, accepted and ignored "
        f"{ignored}/{tot}, missing {missing}/{tot} "
        f"(matplotlib {matplotlib.__version__}, {len(files)} files)"
    )
    if gained_implemented:
        print(f"newly implemented: {', '.join(gained_implemented[:15])}")
    if prev.get("total") not in (None, tot):
        print(f"note: call-site total moved {prev['total']} -> {tot} (matplotlib drift?)")
    if lost_implemented:
        print(
            f"coverage regression: {len(lost_implemented)} implemented APIs became "
            "ignored or missing: " + ", ".join(lost_implemented[:20]),
            file=sys.stderr,
        )
    if lost_ignored:
        print(
            f"coverage regression: {len(lost_ignored)} accepted-and-ignored APIs "
            "are no longer available: " + ", ".join(lost_ignored[:20]),
            file=sys.stderr,
        )
    if implemented < prev_implemented:
        print(
            f"coverage regression: {prev_implemented} -> {implemented} implemented "
            "call sites",
            file=sys.stderr,
        )
    if lost_implemented or lost_ignored or implemented < prev_implemented:
        sys.exit(1)
    print(f"coverage held: {implemented}/{tot} implemented")
