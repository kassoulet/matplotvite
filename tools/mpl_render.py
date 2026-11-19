"""Render harvested snippets with matplotvite or matplotlib."""

from __future__ import annotations

import ast
import gzip
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import warnings

import matplotvite
import numpy as np

try:
    from tools.mpl_harvest import NUMPY_ALIASES, _loaded_names, compat_name
except ModuleNotFoundError:  # `python tools/harvest_matplotlib.py`
    from mpl_harvest import NUMPY_ALIASES, _loaded_names, compat_name

class _SampleDataCbook:
    """`cbook` backed by the Matplotlib checkout's bundled sample data."""

    def __init__(self, root: pathlib.Path): self._root = root.resolve()

    def boxplot_stats(self, *args, **kwargs):
        return matplotvite.cbook.boxplot_stats(*args, **kwargs)

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



def _fallback_multi_font_text():
    """A local approximation of Matplotlib's multi-font test payload."""
    accents = "".join(chr(code) for code in range(0xC5, 0x180))
    text = (
        "There are basic characters\n"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz\n"
        "0123456789\n"
        f"and accented characters\n{accents}\nin between!"
    )
    return ["DejaVu Sans"], text


def _render_snippet_in_process(snippet: str, out_path: pathlib.Path,
           extra_path: pathlib.Path | None = None,
           ignored: list[str] | None = None,
           sample_data: pathlib.Path | None = None,
           filename: pathlib.Path | None = None) -> str | None:
    """Render a snippet with matplotvite; return an error string or None.

    When `ignored` is provided, append the names of compatibility shims that
    accepted arguments without affecting the rendered output.
    """
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from matplotlib import cbook as mpl_cbook
    except Exception:
        mpl_cbook = None
    try:
        from matplotlib.testing import _gen_multi_font_text as mpl_font_text
    except Exception:
        mpl_font_text = None
    try:
        from matplotlib import animation as mpl_animation
    except Exception:
        mpl_animation = None
    try:
        from matplotlib.testing import jpl_units as mpl_units
    except Exception:
        mpl_units = None
    try:
        # `import PIL` alone does not expose the Image submodule on all
        # Pillow versions; load it so gallery snippets can use PIL.Image.
        from PIL import Image as _pil_image
    except Exception:
        _pil_image = None
    try:
        from matplotlib.projections.polar import PolarAxes as mpl_polar_axes
    except Exception:
        mpl_polar_axes = None

    mpl_helpers = {name: value for name, value in (
        ("animation", mpl_animation), ("jpl_units", mpl_units),
        ("PolarAxes", mpl_polar_axes),
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
    if sample_data is not None and mpl_namespace is not matplotvite:
        mpl_namespace.get_data_path = lambda: str(sample_data.parent)
    namespace = {"plt": matplotvite, "mpl": mpl_namespace, "matplotlib": mpl_namespace,
                 "np": np, "OUT": str(out_path)}
    if filename is not None:
        # Some tests locate fixtures relative to their own module; point
        # `__file__` at the harvested source rather than the scratch script.
        namespace["__file__"] = str(filename.resolve())
    namespace.update(mpl_helpers)
    # Imports such as `from matplotlib.patches import Circle` are stripped from
    # gallery snippets, so expose the compatibility classes as bare names.
    namespace.update({name: getattr(matplotvite, name)
                      for name in sorted(getattr(matplotvite, "__all__", ()), key=str)
                      if hasattr(matplotvite, name)})
    def remove_ticks_and_titles(fig):
        """Test helper used by colourizer snippets."""
        for ax in fig.axes:
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title("")
            ax.set_xlabel("")
            ax.set_ylabel("")

    def get_ax():
        """The headless `matplotlib.testing.widgets.get_ax` helper."""
        _fig, ax = matplotvite.subplots(1, 1)
        ax.plot([0, 200], [0, 200])
        ax.set_aspect(1.0)
        return ax

    def noop(*args, **kwargs):
        return None

    namespace.update({
        "assert_array_almost_equal": np.testing.assert_array_almost_equal,
        "assert_array_almost_equal_nulp": np.testing.assert_array_almost_equal_nulp,
        "assert_array_equal": np.testing.assert_array_equal,
        "remove_ticks_and_titles": remove_ticks_and_titles,
        "get_ax": get_ax,
        "noop": noop,
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
    if sample_data is not None:
        # `get_data_path()` is often used as `Path(get_data_path(),
        # "sample_data", ...)`; point it at the checkout's mpl-data directory.
        namespace["get_data_path"] = lambda: str(sample_data.parent)
    namespace["_gen_multi_font_text"] = (mpl_font_text
                                         or _fallback_multi_font_text)
    ignored_calls = getattr(matplotvite, "_IGNORED_CALLS", None)
    # Resolve helper paths before the scratch-directory change.
    added_path = str(extra_path.resolve()) if extra_path is not None else None
    # Run inside a scratch directory: some examples write their own PNGs next to
    # the script's current directory.
    with tempfile.TemporaryDirectory() as scratch:
        previous = pathlib.Path.cwd()
        previous_argv = list(sys.argv)
        try:
            os.chdir(scratch)
            # Examples with an argparse tail expect to see no command-line
            # arguments, as when the gallery script is run without options.
            sys.argv = ["snippet.py"]
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
                # The child process is timeout-bound and isolated from the harvest;
                # snippets are pinned Matplotlib source, never downloaded input.
                exec(snippet, namespace)  # nosec
            if not out_path.exists():
                return "no figure saved"
            return None
        except SystemExit as exc:
            # Some examples (argparse helpers, for instance) exit the process;
            # that must fail one case, not abort the whole gallery run.
            return f"SystemExit: {exc.code}"
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        finally:
            if ignored is not None and ignored_calls is not None:
                ignored.extend(ignored_calls)
            if added_path is not None:
                sys.path.remove(added_path)
            sys.argv = previous_argv
            os.chdir(previous)


# Gallery snippets run in a child interpreter, matching the reference renderer:
# a hung or crashing test cannot take down the harvest, and its rcParams, cwd,
# sys.path and imported modules are discarded with the process.
SNIPPET_TIMEOUT = 90
ROOT = pathlib.Path(__file__).resolve().parent.parent

_CHILD_DRIVER = r'''
import json
import pathlib
import sys

from tools.harvest_matplotlib import _render_snippet_in_process

snippet_path, out_path, extra, sample_data, filename, result_path = sys.argv[1:7]
ignored = []
error = _render_snippet_in_process(
    pathlib.Path(snippet_path).read_text(encoding="utf-8"),
    pathlib.Path(out_path),
    pathlib.Path(extra) if extra else None,
    ignored,
    pathlib.Path(sample_data) if sample_data else None,
    pathlib.Path(filename) if filename else None,
)
pathlib.Path(result_path).write_text(
    json.dumps({"error": error, "ignored": ignored}), encoding="utf-8"
)
'''


def render(snippet: str, out_path: pathlib.Path,
           extra_path: pathlib.Path | None = None,
           ignored: list[str] | None = None,
           sample_data: pathlib.Path | None = None,
           filename: pathlib.Path | None = None) -> str | None:
    """Render a snippet in an isolated interpreter; return an error or None."""
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="matplotvite-snippet-") as scratch:
        scratch = pathlib.Path(scratch)
        snippet_path = scratch / "snippet.py"
        result_path = scratch / "result.json"
        snippet_path.write_text(snippet, encoding="utf-8")
        command = [
            sys.executable, "-c", _CHILD_DRIVER,
            str(snippet_path), str(out_path),
            str(extra_path.resolve()) if extra_path is not None else "",
            str(sample_data.resolve()) if sample_data is not None else "",
            str(filename.resolve()) if filename is not None else "",
            str(result_path),
        ]
        env = dict(os.environ, MPLBACKEND="Agg")
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(ROOT), env.get("PYTHONPATH", "")) if part)
        try:
            result = subprocess.run(
                command,
                cwd=scratch,
                env=env,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=SNIPPET_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            out_path.unlink(missing_ok=True)
            return f"TimeoutError: render did not finish in {SNIPPET_TIMEOUT}s"
        if result.returncode != 0 or not result_path.exists():
            out_path.unlink(missing_ok=True)
            stderr = result.stderr.strip().splitlines()
            return (stderr[-1] if stderr
                    else f"render exited with status {result.returncode}")
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            out_path.unlink(missing_ok=True)
            return f"invalid render result: {exc}"
        if ignored is not None:
            ignored.extend(payload.get("ignored") or ())
        return payload.get("error")


# Run each example in its own interpreter: gallery scripts set rcParams,
# register styles and close figures in ways that would leak between cases. The
# driver saves every figure the script produces, so examples that only call
# show() (the usual ending) still yield a reference PNG.
MATPLOTLIB_DRIVER = r'''
import pathlib
import runpy
import sys

script, out, extra = sys.argv[1:4]
out = pathlib.Path(out)
# Examples such as font_table.py parse argv; mimic `python script.py`.
sys.argv = [script]
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

if extra:
    sys.path.insert(0, str(pathlib.Path(extra).resolve()))

_orig_savefig = Figure.savefig
_copying = [False]


def _save(fig, fname, *args, **kwargs):
    result = _orig_savefig(fig, fname, *args, **kwargs)
    if not _copying[0]:
        _copying[0] = True
        try:
            _orig_savefig(fig, out, dpi=100)
        finally:
            _copying[0] = False
    return result


Figure.savefig = lambda self, fname, *args, **kwargs: _save(
    self, fname, *args, **kwargs)


def _show(*args, **kwargs):
    for num in list(plt.get_fignums()):
        _save(plt.figure(num), out)


plt.show = _show
plt.pause = lambda *args, **kwargs: None
try:
    runpy.run_path(script, run_name="__main__")
finally:
    if not out.exists() and plt.get_fignums():
        _save(plt.figure(plt.get_fignums()[-1]), out)
'''


def render_matplotlib(script: pathlib.Path, out_path: pathlib.Path,
                      extra_path: pathlib.Path | None = None) -> str | None:
    """Render an unmodified gallery script with matplotlib's Agg backend.

    Returns an error string or None. The script runs in a child interpreter in
    a scratch directory so its rcParams, figures and relative writes cannot
    leak into the next case.
    """
    if importlib.util.find_spec("matplotlib") is None:
        return "matplotlib is not installed"
    script = pathlib.Path(script).resolve()
    out_path = out_path.resolve()
    extra_path = (pathlib.Path(extra_path).resolve()
                  if extra_path is not None else None)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        command = [
            sys.executable, "-c", MATPLOTLIB_DRIVER, str(script), str(out_path),
            str(extra_path) if extra_path is not None else "",
        ]
        env = dict(os.environ, MPLBACKEND="Agg")
        try:
            result = subprocess.run(
                command,
                cwd=scratch,
                env=env,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=90,
                check=False,
            )
        except subprocess.TimeoutExpired:
            out_path.unlink(missing_ok=True)
            return "TimeoutError: matplotlib render did not finish in 90s"
        if result.returncode != 0:
            # A script can save a partial figure before raising (usetex runs,
            # for instance); the case is an error, so do not keep it.
            out_path.unlink(missing_ok=True)
            stderr = result.stderr.strip().splitlines()
            return (stderr[-1] if stderr
                    else f"matplotlib exited with status {result.returncode}")
        if not out_path.exists():
            return "no figure saved"
    return None
