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
import ast
import gzip
import html
import importlib.util
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import warnings
import textwrap

import numpy as np
import matplotvite

# Bodies that cannot be rendered out of process: pytest fixtures, checks against
# Matplotlib internals, or interactive backends.
SKIP_RE = re.compile(r"pytest\.|check_figures_equal\(|\binput\(|themes\.|savefig\(")

# Imports the renderer supplies itself or never needs: pytest is a test-only
# dependency, and bodies that use it are skipped by SKIP_RE.
STRIPPED_IMPORTS = ("matplotlib", "mpl_toolkits", "numpy", "pytest")

# The toolkit shims ship inside matplotvite so the wheel never shadows
# Matplotlib's own top-level `mpl_toolkits` namespace.
TOOLKITS_PACKAGE = "matplotvite.mpl_toolkits"

# Aliases used by Matplotlib's tests after a stripped `from numpy... import`.
NUMPY_ALIASES = {"ma": np.ma, "rand": np.random.rand, "randn": np.random.randn}

# Matplotvite namespaces that hold names the top-level `__all__` does not.
COMPAT_NAMESPACES = ("ticker", "cm", "colors", "patches", "path", "transforms",
                     "collections", "lines", "gridspec", "patheffects")


def compat_name(name: str):
    """Resolve a name from a stripped `from matplotlib.x import y` line."""
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


def _literal(node: ast.AST, default=None):
    """Evaluate a decorator argument written as a literal."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return default


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
            elif keyword.arg == "savefig_kwarg" and isinstance(value, dict):
                if value.get("dpi") is not None:
                    options["dpi"] = value["dpi"]
                options["tight"] = value.get("bbox_inches") == "tight"
    return options


def _comparison_prefix(options: dict[str, object] | None) -> str:
    """Match the test suite's figure size and style before running a body."""
    if options is None:
        return ""
    lines = ['plt.rcdefaults()', 'plt.rcParams["figure.figsize"] = (8, 6)']
    style = options.get("style")
    # Matplotlib's test suite uses `_classic_test`, which is the "classic" style
    # plus a hinting patch that only exists inside Matplotlib; render with the
    # nearest style matplotvite ships.
    if isinstance(style, str) and style == "_classic_test":
        style = "classic"
    elif isinstance(style, (list, tuple)) and "_classic_test" in style:
        style = "classic"
    if style:
        lines.append(f"plt.style.use({style!r})")
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


def prepare_example(text: str) -> str | None:
    """Rewrite a gallery script into a snippet that draws once and saves."""
    if "input(" in text:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
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
            "snippet": prepare_example(text),
        })
    return cases


# A case whose PNG has almost no ink is reported as blank, not rendered:
# Matplotlib's baseline is never empty, so such a case says nothing about
# fidelity and usually points at a silently ignored call.
BLANK_THRESHOLD = 50

# Gallery categories that cannot be judged from a still render: they need a
# GUI toolkit, an interactive backend or 3-D axes (out of scope).
OUT_OF_SCOPE_CATEGORIES = frozenset({
    "animation", "mplot3d", "user_interfaces", "widgets",
})

# Modules the harness cannot supply and that are not matplotvite's to provide:
# a GUI toolkit, the image library the gallery job installs, and real Matplotlib
# (the `units/*` examples import its test helpers).
ENVIRONMENT_MODULES = frozenset({"PIL", "gi", "wx", "matplotlib"})


def _nonwhite_pixels(path: pathlib.Path) -> int | None:
    """Sampled non-white pixel count, using the stdlib decoder in tests/."""
    try:
        from png_utils import decode_png_rgba
    except ImportError:
        helper = pathlib.Path(__file__).resolve().parents[1] / "tests" / "png_utils.py"
        spec = importlib.util.spec_from_file_location("png_utils", helper)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        decode_png_rgba = module.decode_png_rgba
    try:
        _, _, rows = decode_png_rgba(path.read_bytes())
    except Exception:  # noqa: BLE001 - an unreadable PNG is unknown, not blank
        return None
    return sum(
        min(row[i], row[i + 1], row[i + 2]) < 250
        for y, row in enumerate(rows) if y % 2 == 0
        for i in range(0, len(row), 8)
    )


def failure_status(error: str | None) -> str:
    """Bucket a failed render: harvester gap, missing API or bug.

    A `NameError` for a name matplotvite already exposes is the harvester's
    fault (the import line was stripped); any other undefined name, a missing
    attribute or an unimplemented option needs API work; the rest is a bug in
    a feature matplotvite claims to support.
    """
    if not error:
        return "failed"
    kind, _, detail = error.partition(":")
    if kind == "ModuleNotFoundError":
        # Only a module the harness failed to supply is a harvester gap. A
        # missing matplotvite shim is API work, and a GUI toolkit, Pillow or
        # real Matplotlib belongs to the environment, not to either.
        match = re.search(r"No module named '([^']+)'", detail)
        root = (match.group(1) if match else "").split(".")[0]
        if root in ENVIRONMENT_MODULES:
            return "unsupported"
        if root in ("matplotvite", "mpl_toolkits"):
            return "needs-api"
        return "harvester-gap"
    if kind == "NameError":
        match = re.search(r"name '([^']+)' is not defined", detail)
        name = match.group(1) if match else ""
        if name and (name in NUMPY_ALIASES or compat_name(name) is not None):
            return "harvester-gap"
        return "needs-api"
    if kind in ("AttributeError", "ImportError", "NotImplementedError"):
        return "needs-api"
    return "bug"


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
                "snippet": prepare_body(source, options),
            })
    return cases


class _SampleDataCbook:
    """`cbook` backed by the Matplotlib checkout's bundled sample data."""

    def __init__(self, root: pathlib.Path): self._root = root.resolve()

    def get_sample_data(self, fname, asfileobj=True, np_load=False):
        path = pathlib.Path(str(fname))
        candidate = path if path.is_absolute() else self._root / path
        if not candidate.exists():
            raise FileNotFoundError(f"no sample data {fname!r} in {self._root}")
        if np_load or candidate.suffix.lower() in (".npz", ".npy"):
            return np.load(candidate, allow_pickle=False)
        if candidate.suffix.lower() == ".gz":
            return gzip.open(candidate, "rb")
        return open(candidate, "rb") if asfileobj else str(candidate)


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


def render(snippet: str, out_path: pathlib.Path,
           extra_path: pathlib.Path | None = None,
           ignored: list[str] | None = None,
           sample_data: pathlib.Path | None = None) -> str | None:
    """Render a snippet with matplotvite; return an error string or None.

    When `ignored` is provided, append the names of compatibility shims that
    accepted arguments without affecting the rendered output.
    """
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from matplotlib import cbook as mpl_cbook
    except Exception:  # noqa: BLE001 - gallery tests may run without Matplotlib
        mpl_cbook = None
    try:
        from matplotlib.testing import _gen_multi_font_text as mpl_font_text
    except Exception:  # noqa: BLE001
        mpl_font_text = None
    try:
        from matplotlib import animation as mpl_animation
    except Exception:  # noqa: BLE001
        mpl_animation = None
    try:
        from matplotlib import tri as mpl_tri
    except Exception:  # noqa: BLE001
        mpl_tri = None
    try:
        from matplotlib.testing import jpl_units as mpl_units
    except Exception:  # noqa: BLE001
        mpl_units = None
    try:
        from matplotlib.projections.polar import PolarAxes as mpl_polar_axes
    except Exception:  # noqa: BLE001
        mpl_polar_axes = None

    mpl_helpers = {name: value for name, value in (
        ("animation", mpl_animation), ("tri", mpl_tri), ("mtri", mpl_tri),
        ("units", mpl_units), ("PolarAxes", mpl_polar_axes),
        ("Triangulation", getattr(mpl_tri, "Triangulation", None)),
    ) if value is not None}

    class _MplProxy:
        def __getattr__(self, name):
            if name == "cbook" and mpl_cbook is not None:
                return mpl_cbook
            if name in mpl_helpers:
                return mpl_helpers[name]
            return getattr(matplotvite, name)

    sample_cbook = (_SampleDataCbook(sample_data)
                    if mpl_cbook is None and sample_data is not None else None)
    if sample_cbook is not None:
        mpl_helpers["cbook"] = sample_cbook
    mpl_namespace = (_MplProxy() if (mpl_cbook is not None or sample_cbook is not None)
                     else matplotvite)
    namespace = {"plt": matplotvite, "mpl": mpl_namespace, "matplotlib": mpl_namespace,
                 "np": np, "OUT": str(out_path)}
    namespace.update(mpl_helpers)
    # Imports such as `from matplotlib.patches import Circle` are stripped from
    # gallery snippets, so expose the compatibility classes as bare names.
    namespace.update({name: getattr(matplotvite, name)
                      for name in sorted(getattr(matplotvite, "__all__", ()), key=str)
                      if hasattr(matplotvite, name)})
    namespace.update({
        "assert_array_almost_equal": np.testing.assert_array_almost_equal,
        "assert_array_equal": np.testing.assert_array_equal,
        "matplotvite": matplotvite,
    })
    # Imports are stripped from the snippets, so resolve the names they would
    # have bound: `MaxNLocator`, `TABLEAU_COLORS`, `rand`, `ma`, ... otherwise
    # the case fails with a NameError that hides whether the API exists.
    try:
        needed = _loaded_names(ast.parse(snippet))
    except SyntaxError:
        needed = set()
    for name in needed - set(namespace):
        if name in NUMPY_ALIASES:
            namespace[name] = NUMPY_ALIASES[name]
            continue
        value = compat_name(name)
        if value is not None:
            namespace[name] = value
    cbook_namespace = mpl_cbook if mpl_cbook is not None else sample_cbook
    if cbook_namespace is not None:
        namespace["cbook"] = cbook_namespace
        namespace["get_sample_data"] = cbook_namespace.get_sample_data
    if mpl_font_text is not None:
        namespace["_gen_multi_font_text"] = mpl_font_text
    ignored_calls = getattr(matplotvite, "_IGNORED_CALLS", None)
    # Resolve helper paths before the scratch-directory change.
    added_path = str(extra_path.resolve()) if extra_path is not None else None
    # Run inside a scratch directory: some examples write their own PNGs next to
    # the script's current directory.
    with tempfile.TemporaryDirectory() as scratch:
        previous = pathlib.Path.cwd()
        try:
            os.chdir(scratch)
            if added_path is not None:
                sys.path.insert(0, added_path)
            matplotvite.close("all")
            # Each case starts from Matplotlib's defaults, not the previous case's
            # rcParams edits.
            matplotvite.rcdefaults()
            if ignored_calls is not None:
                ignored_calls.clear()
            np.random.seed(0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                exec(snippet, namespace)  # noqa: S102 - source is Matplotlib's own test suite
            if not out_path.exists():
                return "no figure saved"
            return None
        except Exception as exc:  # noqa: BLE001 - the gallery records every failure
            return f"{type(exc).__name__}: {exc}"
        finally:
            if ignored is not None and ignored_calls is not None:
                ignored.extend(ignored_calls)
            if added_path is not None:
                sys.path.remove(added_path)
            os.chdir(previous)


def metrics(baseline: pathlib.Path, ours: pathlib.Path) -> dict[str, object]:
    """RMS and visibly-different percentage against the baseline PNG.

    The comparison reads PNGs through Matplotlib, which the renderer itself does
    not need; without it the gallery still renders and records why the metric is
    unavailable.
    """
    if not baseline.exists():
        return {"error": f"missing baseline {baseline}"}
    try:  # same metric as the gallery tool; importable both as a script and as a package
        try:
            from visual_compare import compare_images
        except ModuleNotFoundError:
            from tools.visual_compare import compare_images
        return compare_images(baseline, ours)
    except Exception as exc:  # noqa: BLE001 - a missing matplotlib or bad PNG is data, not a crash
        return {"error": f"{type(exc).__name__}: {exc}"}


def harvest_gallery(tests_root: pathlib.Path, out: pathlib.Path,
                    manifest_path: pathlib.Path) -> dict[str, int]:
    """Render every baseline case and write the side-by-side gallery."""
    cases = harvest(tests_root)
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
            error = render(str(case["snippet"]), ours, ignored=ignored)
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
            f"{entry['status']}<br>rms: {'n/a' if score is None else f'{score:.3f}'}</td>"
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
        + "</table><style>img{max-width:420px}</style>", encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    statuses = [str(case["status"]) for case in cases]
    print(f"\n{len(cases)} baseline cases: {rendered} rendered, "
          f"{statuses.count('blank')} blank, {statuses.count('failed')} failed, "
          f"{statuses.count('unsupported')} unsupported; gallery: {out / 'index.html'}")
    return {"cases": len(cases), "rendered": rendered,
            "blank": statuses.count("blank"),
            "failed": statuses.count("failed"),
            "unsupported": statuses.count("unsupported")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path,
                        help="Matplotlib checkout or sdist root")
    parser.add_argument("--examples", type=pathlib.Path,
                        help="render the gallery scripts under this checkout instead")
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--json", type=pathlib.Path, dest="json_out", default=None)
    args = parser.parse_args()
    default_out = "dist/mpl-examples" if args.examples else "dist/mpl-corpus"
    args.out = args.out or pathlib.Path(default_out)
    args.json_out = args.json_out or args.out / "manifest.json"
    if args.examples:
        return harvest_examples_gallery(args.examples, args.out, args.json_out)

    tests_root = find_tests_root(args.source)
    if tests_root is None:
        print("No Matplotlib baseline images found. Point --source at a checkout or "
              "run `pip download --no-binary :all: matplotlib`; the wheel omits them.")
        return 1
    harvest_gallery(tests_root, args.out, args.json_out)
    return 0


def harvest_examples_gallery(source: pathlib.Path, out: pathlib.Path,
                             manifest_path: pathlib.Path) -> int:
    """Render every gallery example and report the ones our API cannot express."""
    examples_root = find_examples_root(source)
    if examples_root is None:
        print(f"No gallery examples found under {source}.")
        return 1
    cases = harvest_examples(examples_root)
    sample_data = find_sample_data(source)
    out.mkdir(parents=True, exist_ok=True)
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
        elif case["category"] in OUT_OF_SCOPE_CATEGORIES:
            entry["status"] = "unsupported"
            entry["error"] = f"{case['category']} is out of scope"
        else:
            ours = out / f"{slug}.png"
            ignored: list[str] = []
            entry["error"] = render(str(case["snippet"]), ours,
                                    pathlib.Path(str(case["path"])).parent,
                                    ignored=ignored, sample_data=sample_data)
            entry["ignored"] = len(ignored)
            entry["status"] = ("rendered" if entry["error"] is None
                               else failure_status(str(entry["error"])))
            if entry["error"] is None:
                entry["ours"] = str(ours)
                entry["nonwhite"] = _nonwhite_pixels(ours)
                if entry["nonwhite"] is not None and entry["nonwhite"] < BLANK_THRESHOLD:
                    entry["status"] = "blank"
        counts = statuses.setdefault(str(case["category"]), [0, 0])
        counts[0] += 1
        counts[1] += entry["status"] == "rendered"
        view = (f'<img src="{html.escape(slug)}.png">' if entry.get("ours")
                else f'<pre style="color:#c00">{html.escape(str(entry["error"]))}</pre>')
        rows.append(
            f"<tr><td>{html.escape(str(case['category']))}<br>"
            f"<b>{html.escape(str(case['id']))}</b><br>"
            f"{html.escape(str(case['description']))}</td>"
            f"<td>{view}</td><td>{entry['status']}</td></tr>")
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
    (out / "index.html").write_text(
        f"<p>{rendered}/{len(cases)} examples rendered, {blank} blank, "
        f"{unsupported} unsupported, {needs_api} needs API, {gaps} harvester "
        f"gaps, {bugs} bugs</p><ul>{summary}</ul>"
        "<table border=1 cellpadding=6><tr><th>example</th><th>matplotvite</th>"
        "<th>status</th></tr>" + "".join(rows)
        + "</table><style>img{max-width:420px}</style>", encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    print(f"\n{rendered}/{len(cases)} gallery examples rendered, {blank} blank, "
          f"{unsupported} unsupported, {needs_api} needs API, {gaps} harvester "
          f"gaps, {bugs} bugs; gallery: {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
