"""Harvest Matplotlib tests and gallery examples into renderable snippets."""

from __future__ import annotations

import ast
import html
import pathlib
import re
import textwrap

import matplotvite
import numpy as np

SKIP_RE = re.compile(r"pytest\.|check_figures_equal\(|\binput\(|themes\.|savefig\(")

# Imports the renderer supplies itself or never needs: pytest is a test-only
# dependency, and bodies that use it are skipped by SKIP_RE.
STRIPPED_IMPORTS = ("matplotlib", "mpl_toolkits", "numpy", "pytest", "cycler")

# The toolkit shims ship inside matplotvite so the wheel never shadows
# Matplotlib's own top-level `mpl_toolkits` namespace.
TOOLKITS_PACKAGE = "matplotvite.mpl_toolkits"

# Aliases used by Matplotlib's tests after a stripped `from numpy... import`.
NUMPY_ALIASES = {"ma": np.ma, "rand": np.random.rand, "randn": np.random.randn,
                 "multivariate_normal": np.random.multivariate_normal}

# Matplotvite namespaces that hold names the top-level `__all__` does not.
COMPAT_NAMESPACES = ("ticker", "cm", "colors", "patches", "path", "transforms",
                     "collections", "lines", "gridspec", "patheffects",
                     "offsetbox", "tri", "scale", "projections", "spines")


def compat_name(name: str):
    """Resolve a name from a stripped `from matplotlib.x import y` line."""
    if hasattr(matplotvite, name):
        return getattr(matplotvite, name)
    for module_name in COMPAT_NAMESPACES:
        module = getattr(matplotvite, module_name, None)
        if module is not None and hasattr(module, name):
            return getattr(module, name)
    return None


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


_BASELINE_NODES = (
    ast.Expression, ast.ListComp, ast.comprehension, ast.Name, ast.Load, ast.Store,
    ast.Call, ast.Constant, ast.JoinedStr, ast.FormattedValue, ast.BinOp, ast.Add,
    ast.Mult, ast.Mod, ast.List, ast.Tuple,
)


def _safe_baseline_expr(node: ast.AST) -> bool:
    """Accept only list comprehensions over a small `range(...)` of literals."""
    for child in ast.walk(node):
        if not isinstance(child, _BASELINE_NODES):
            return False
        if isinstance(child, ast.Call):
            if not (isinstance(child.func, ast.Name) and child.func.id == "range"
                    and not child.keywords):
                return False
            for arg in child.args:
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, int)
                        and abs(arg.value) <= 10_000):
                    return False
    return True


def _baseline_list(node: ast.AST) -> list[str] | None:
    """Evaluate a baseline list, including the `[f"x_{i}.png" for i in range(n)]` form."""
    try:
        value = ast.literal_eval(node)
    except ValueError:
        if not _safe_baseline_expr(node):
            return None
        try:
            value = eval(  # nosec
                         compile(ast.Expression(node), "<baseline>", "eval"),
                         {"__builtins__": {}}, {"range": range})
        except Exception:
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


def _literal(node: ast.AST, default=None):
    """Evaluate a decorator argument written as a literal."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return default


_UNSET = object()


def _literal_dict(node: ast.AST) -> dict[str, object] | None:
    """Evaluate a literal dict, including the `dict(dpi=200)` spelling."""
    if isinstance(node, ast.Dict):
        out: dict[str, object] = {}
        for key, value in zip(node.keys, node.values):
            name = _literal(key, _UNSET)
            item = _literal(value, _UNSET)
            if not isinstance(name, str) or item is _UNSET:
                return None
            out[name] = item
        return out
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "dict" and not node.args):
        out = {}
        for keyword in node.keywords:
            item = _literal(keyword.value, _UNSET)
            if keyword.arg is None or item is _UNSET:
                return None
            out[keyword.arg] = item
        return out
    return None


def image_comparison_options(func: ast.FunctionDef) -> dict[str, object]:
    """Style, dpi and layout settings from an `@image_comparison` decorator.

    Matplotlib's decorator drives the test style, the figure size and the
    savefig arguments, so a snippet rendered without them compares a different
    picture from the baseline.
    """
    options: dict[str, object] = {
        "style": None, "dpi": 100, "remove_text": False, "tight": False,
        "extensions": None, "tol": None,
    }
    for deco in func.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        name = getattr(deco.func, "id", getattr(deco.func, "attr", ""))
        if name != "image_comparison":
            continue
        for keyword in deco.keywords:
            if keyword.arg is None:
                continue
            value = _literal(keyword.value, None)
            if keyword.arg == "style":
                options["style"] = value
            elif keyword.arg == "remove_text":
                options["remove_text"] = bool(value)
            elif keyword.arg == "extensions":
                options["extensions"] = value
            elif keyword.arg == "tol":
                options["tol"] = value
            elif keyword.arg == "savefig_kwarg":
                savefig = _literal_dict(keyword.value)
                if savefig is not None:
                    if savefig.get("dpi") is not None:
                        options["dpi"] = savefig["dpi"]
                    options["tight"] = savefig.get("bbox_inches") == "tight"
    return options


def _comparison_prefix(options: dict[str, object] | None) -> str:
    """Match the test suite's figure size and style before running a body."""
    if options is None:
        return ""
    lines = ['plt.rcdefaults()']
    style = options.get("style")
    # Matplotlib's test suite uses `_classic_test`, which is the "classic" style
    # plus a hinting patch that only exists inside Matplotlib; render with the
    # nearest style matplotvite ships. Only classic uses the 8x6 test figure:
    # default and mpl20 baselines are the 6.4x4.8 rc default.
    if isinstance(style, str) and style == "_classic_test":
        style = "classic"
    elif isinstance(style, (list, tuple)) and "_classic_test" in style:
        style = "classic"
    if style:
        lines.append(f"plt.style.use({style!r})")
    if style == "classic":
        lines.append('plt.rcParams["figure.figsize"] = (8, 6)')
    return "\n".join(lines) + "\n"


def _comparison_suffix(options: dict[str, object] | None) -> str:
    """Save at the baseline dpi, honouring `savefig_kwarg={"bbox_inches": ...}`."""
    options = options or {}
    args = [f"dpi={options.get('dpi', 100)!r}"]
    if options.get("tight"):
        args.append('bbox_inches="tight"')
    return f"\nplt.savefig(OUT, {', '.join(args)})\n"


def find_examples_root(source: pathlib.Path) -> pathlib.Path | None:
    """Locate the gallery examples directory in a Matplotlib checkout."""
    for candidate in (source / "galleries/examples", source / "examples", source):
        if any(candidate.glob("*/*.py")):
            return candidate
    return None


def _alias_assignment(target: str, module: str) -> ast.Expr:
    """`target = matplotlib.<module>`, or `target = plt` for pyplot.

    The namespace binds `matplotlib` to matplotvite, so the assignment keeps a
    stripped module alias (`mpatch`, `transforms`, `mdates`, ...) usable without
    importing Matplotlib; an alias matplotvite has no module for raises an
    AttributeError, which `failure_status` counts as a missing API.
    """
    value = (ast.Name(id="plt", ctx=ast.Load()) if module == "pyplot"
             else ast.Attribute(value=ast.Name(id="matplotlib", ctx=ast.Load()),
                                attr=module, ctx=ast.Load()))
    return ast.Assign(targets=[ast.Name(id=target, ctx=ast.Store())], value=value)


def _toolkit_import(alias: ast.alias) -> ast.Assign:
    """`import matplotlib` line that binds a toolkit submodule to its alias."""
    suffix = alias.name.split(".", 1)[1] if "." in alias.name else ""
    target = alias.asname or alias.name.split(".")[0]
    return ast.parse(
        f"import {TOOLKITS_PACKAGE}{'.' + suffix if suffix else ''} as {target}").body[0]


class _ExampleStripper(ast.NodeTransformer):
    """Drop Matplotlib/NumPy imports and the interactive tail of a gallery script."""

    def visit_Import(self, node: ast.Import):
        kept, emitted = [], []
        for alias in node.names:
            module = alias.name.split(".")
            if module[0] == "mpl_toolkits":
                emitted.append(_toolkit_import(alias))
            elif module[0] not in STRIPPED_IMPORTS:
                kept.append(alias)
            elif (alias.asname and alias.asname not in ("plt", "mpl")
                  and len(module) > 1 and module[1] != "pyplot"):
                emitted.append(_alias_assignment(alias.asname, module[1]))
        nodes = ([ast.Import(names=kept)] if kept else []) + emitted
        return nodes or None

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        if module.split(".")[0] == "mpl_toolkits":
            rewritten = f"{TOOLKITS_PACKAGE}{'.' + module.split('.', 1)[1] if '.' in module else ''}"
            return ast.ImportFrom(module=rewritten, names=node.names, level=0)
        if module.split(".")[0] not in STRIPPED_IMPORTS:
            return node
        if module != "matplotlib":
            return None
        emitted = [_alias_assignment(alias.asname or alias.name, alias.name)
                   for alias in node.names
                   if (alias.asname or alias.name) not in ("plt", "mpl")]
        return emitted or None

    def visit_If(self, node: ast.If):
        if "__main__" in ast.unparse(node.test):
            return None
        return self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr):
        call = ast.unparse(node)
        if re.match(r"(plt|mpl|matplotlib\.pyplot)\.(show|pause|draw|close)\(", call):
            return None
        return node


# Gallery scripts often put all plotting under `if __name__ == "__main__"`.
# Keep that body when it is safe to execute once; drop it when it would block
# the harvester on a GUI loop, a timer or a child process.
_BLOCKING_MAIN = re.compile(
    r"\b(?:multiprocessing|subprocess|socket|threading|mp|input|time\.sleep|"
    r"FuncAnimation|Timer)\b"
)


class _UnwrapMain(ast.NodeTransformer):
    """Inline a `__main__` guard so gallery scripts keep their plotting code."""

    def visit_If(self, node: ast.If):
        node = self.generic_visit(node)
        if "__main__" in ast.unparse(node.test):
            if _BLOCKING_MAIN.search(ast.unparse(node)):
                return None
            return node.body
        return node


class _PruneEmpty(ast.NodeTransformer):
    """Remove compound statements whose bodies were stripped away."""

    def visit_If(self, node: ast.If):
        node = self.generic_visit(node)
        if not node.body:
            return node.orelse or None
        return node

    def _visit_block(self, node):
        node = self.generic_visit(node)
        return node if node.body else None

    visit_For = _visit_block
    visit_AsyncFor = _visit_block
    visit_While = _visit_block
    visit_With = _visit_block
    visit_AsyncWith = _visit_block
    visit_FunctionDef = _visit_block
    visit_AsyncFunctionDef = _visit_block
    visit_ClassDef = _visit_block


def source_details(source: object) -> str:
    """Collapsible original script for a comparison-gallery row."""
    if not source:
        return ""
    return (
        "<details><summary>Source</summary><pre class=\"source\">"
        f"{html.escape(str(source))}</pre></details>"
    )


def prepare_example(text: str) -> str | None:
    """Rewrite a gallery script into a snippet that draws once and saves."""
    if "input(" in text:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    tree = _UnwrapMain().visit(tree)
    tree = _ExampleStripper().visit(tree)
    tree = _PruneEmpty().visit(tree)
    code = ast.unparse(ast.fix_missing_locations(tree)).strip("\n")
    if not code:
        return None
    return code + "\nplt.savefig(OUT, dpi=100)\n"


def harvest_examples(examples_root: pathlib.Path) -> list[dict[str, object]]:
    """One case per example script, tagged with its gallery category."""
    cases: list[dict[str, object]] = []
    for script in sorted(examples_root.rglob("*.py")):
        relative = script.relative_to(examples_root)
        text = script.read_text(encoding="utf-8")
        try:
            docstring = ast.get_docstring(ast.parse(text)) or ""
        except SyntaxError:
            docstring = ""
        summary = next((line.strip() for line in docstring.splitlines() if line.strip()), "")
        cases.append({
            "id": relative.with_suffix("").as_posix(),
            "category": relative.parts[0] if len(relative.parts) > 1 else "examples",
            "path": str(script),
            "description": summary,
            "source": text,
            "snippet": prepare_example(text),
        })
    return cases


# A case whose PNG has almost no ink is reported as blank, not rendered:
# Matplotlib's baseline is never empty, so such a case says nothing about

OUT_OF_SCOPE_CATEGORIES = frozenset({
    "animation", "mplot3d", "user_interfaces", "widgets",
})

# Modules the harness cannot supply and that are not matplotvite's to provide:

GUI_MODULES = ("gi", "wx")

# Vector baselines need an optional converter before a pixel metric exists, so
# local runs state which ones are missing instead of silently scoring n/a.
METRIC_CONVERTERS = {
    "PIL": ("Pillow", "EPS"),
    "pypdfium2": ("pypdfium2", "PDF"),
    "cairosvg": ("cairosvg", "SVG"),
}


def requires_gui(source: str | None) -> bool:
    """Whether an example imports a GUI toolkit that the harness cannot drive."""
    if not source:
        return False
    return any(
        re.search(rf"^\s*(?:import|from)\s+{module}\b", source, re.MULTILINE)
        for module in GUI_MODULES
    )


def _resolve_baseline(tests_root: pathlib.Path, stem: str, name: str) -> pathlib.Path:
    """`baseline_images` names omit extensions; prefer the PNG variant."""
    base = tests_root / "baseline_images" / stem / name
    if base.suffix:
        return base
    for suffix in (".png", ".svg", ".pdf"):
        if base.with_suffix(suffix).exists():
            return base.with_suffix(suffix)
    return base.with_suffix(".png")


class _BodyStripper(_ExampleStripper):
    """Remove imports, interactive calls and assertions from a test body."""

    def visit_Assert(self, node: ast.Assert):
        return None


def prepare_body(source: str, options: dict[str, object] | None = None) -> str | None:
    """Rewrite a test body into a runnable matplotvite snippet."""
    body = textwrap.dedent(source)
    if SKIP_RE.search(body):
        return None
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return None
    tree = _BodyStripper().visit(tree)
    tree = _drop_unused_aliases(tree)
    tree = _PruneEmpty().visit(tree)
    code = ast.unparse(ast.fix_missing_locations(tree)).strip("\n")
    if not code:
        return None
    return _comparison_prefix(options) + code + _comparison_suffix(options)


def _loaded_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node)
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def _drop_unused_aliases(tree: ast.Module) -> ast.Module:
    """Remove `alias = matplotlib.<module>` lines whose alias the body never uses.

    Matplotlib's test modules import several submodules at module scope that a
    given test does not touch; keeping those assignments would turn an unused
    import into a misleading "module has no attribute" failure.
    """
    used = _loaded_names(tree)
    kept = []
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id in ("matplotlib", "mpl")
                and node.targets[0].id not in used):
            continue
        if isinstance(node, ast.Import):
            node.names = [alias for alias in node.names
                          if (alias.asname or alias.name.split(".")[0]) in used]
            if not node.names:
                continue
        if isinstance(node, ast.ImportFrom):
            node.names = [alias for alias in node.names
                          if (alias.asname or alias.name) in used]
            if not node.names:
                continue
        kept.append(node)
    tree.body = kept
    return tree


def _module_context(module: ast.Module, text: str, func: ast.FunctionDef) -> str:
    """Imports and referenced helper definitions for one test function.

    Test bodies often call a module-level helper such as `example_plot`; without
    that helper the snippet fails with a misleading NameError instead of exposing
    a real renderer gap. Keep the module imports as well so stdlib names such as
    `datetime` remain available. Matplotlib/NumPy imports are stripped later by
    `prepare_body`, which leaves the compatibility namespace in charge.
    """
    imports: list[str] = []
    definitions: dict[str, ast.AST] = {}
    for node in module.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            source = ast.get_source_segment(text, node)
            if source:
                imports.append(source)
        elif (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
              and not node.name.startswith("test_") and not node.decorator_list):
            definitions[node.name] = node

    needed: set[str] = set()
    pending = _loaded_names(func)
    while pending:
        name = pending.pop()
        helper = definitions.get(name)
        if helper is not None and name not in needed:
            needed.add(name)
            pending |= _loaded_names(helper)
    helpers = [ast.get_source_segment(text, definitions[name]) or ""
               for name in sorted(needed, key=lambda n: definitions[n].lineno)]
    return "\n\n".join(part for part in imports + helpers if part)


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
            options = image_comparison_options(func)
            images = [_resolve_baseline(tests_root, module_path.stem, name)
                      for name in baselines]
            body = textwrap.dedent("\n".join(
                ast.get_source_segment(text, node) or "" for node in func.body))
            context = _module_context(module, text, func)
            source = "\n\n".join(part for part in (context, body) if part)
            cases.append({
                "id": f"{module_path.stem}/{func.name}",
                "module": module_path.name,
                "function": func.name,
                "params": [arg.arg for arg in func.args.args],
                "baselines": baselines,
                "images": [str(p) for p in images],
                "comparison": options,
                "source": source,
                "file": str(module_path.resolve()),
                "snippet": prepare_body(source, options),
            })
    return cases


def find_sample_data(source: pathlib.Path) -> pathlib.Path | None:
    """Locate `mpl-data/sample_data` in a checkout or an unpacked sdist."""
    candidates = [source / "lib/matplotlib/mpl-data/sample_data",
                  source / "mpl-data/sample_data",
                  *sorted(source.glob("*/lib/matplotlib/mpl-data/sample_data")),
                  *sorted(pathlib.Path("dist/mpl-sdist").glob(
                      "*/lib/matplotlib/mpl-data/sample_data"))]
    for candidate in candidates:
        if candidate.is_dir():
            # Resolve now: snippets run from a scratch working directory.
            return candidate.resolve()
    return None
