"""Tests for the Matplotlib baseline-image and gallery harvester."""

import gzip
import json
from pathlib import Path

import matplotvite

from tools.harvest_matplotlib import (_SampleDataCbook, _resolve_baseline,
                                      failure_status, find_examples_root,
                                      find_sample_data, find_tests_root, harvest,
                                      harvest_examples, harvest_examples_gallery,
                                      harvest_gallery, prepare_body,
                                      prepare_example, render)

MODULE = '''import matplotlib.pyplot as plt
import numpy as np
import pytest


@image_comparison([f"grid_{i}.png" for i in range(1, 3)], style="mpl20")
def test_grid():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [1, 0])


@pytest.mark.parametrize("n", [1, 2])
@image_comparison(baseline_images=["param"], style="mpl20")
def test_param(n):
    plt.plot([n, n])


def test_not_compared():
    plt.plot([1, 2])
'''


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "tests"
    (root / "baseline_images" / "test_demo").mkdir(parents=True)
    (root / "test_demo.py").write_text(MODULE, encoding="utf-8")
    return root


def test_harvest_reads_image_comparison_cases(tmp_path):
    cases = harvest(make_root(tmp_path))
    assert [case["id"] for case in cases] == ["test_demo/test_grid", "test_demo/test_param"]
    assert cases[0]["baselines"] == ["grid_1.png", "grid_2.png"]
    assert cases[0]["params"] == []
    assert cases[1]["params"] == ["n"]
    # The snippet drops matplotlib/numpy/pytest imports and saves the figure itself.
    assert "import matplotlib" not in cases[0]["snippet"]
    assert "pytest" not in cases[0]["snippet"]
    assert cases[0]["snippet"].endswith("plt.savefig(OUT, dpi=100)\n")


def test_harvest_includes_referenced_helpers_and_imports(tmp_path):
    root = tmp_path / "tests"
    (root / "baseline_images" / "test_demo").mkdir(parents=True)
    (root / "test_demo.py").write_text(
        "from datetime import datetime\n"
        "import matplotlib.pyplot as plt\n"
        "def helper(x):\n"
        "    return datetime(2020, 1, 1).year + x\n"
        "@image_comparison(['helper.png'])\n"
        "def test_helper():\n"
        "    plt.plot([0, helper(1)])\n", encoding="utf-8")
    case = harvest(root)[0]
    assert "def helper" in case["snippet"]
    assert "from datetime import datetime" in case["snippet"]
    assert "import matplotlib" not in case["snippet"]


def test_harvest_reads_comparison_style_dpi_and_tight(tmp_path):
    root = tmp_path / "tests"
    (root / "baseline_images" / "test_demo").mkdir(parents=True)
    (root / "test_demo.py").write_text(
        "@image_comparison(['styled.png'], style='mpl20', remove_text=True,\n"
        "                   savefig_kwarg={'dpi': 40, 'bbox_inches': 'tight'})\n"
        "def test_styled():\n"
        "    plt.plot([0, 1])\n", encoding="utf-8")
    case = harvest(root)[0]
    assert case["comparison"] == {"style": "mpl20", "dpi": 40, "remove_text": True,
                                  "tight": True, "extensions": None, "tol": None}
    snippet = case["snippet"]
    assert 'plt.rcParams["figure.figsize"] = (8, 6)' in snippet
    assert "plt.style.use('mpl20')" in snippet
    assert snippet.endswith('plt.savefig(OUT, dpi=40, bbox_inches="tight")\n')


def test_prepare_example_resolves_module_alias_imports():
    snippet = prepare_example(
        "import matplotlib.pyplot as plt\n"
        "import matplotlib.patches as mpatch\n"
        "from matplotlib import transforms as mtrans\n"
        "import matplotlib.dates as mdates\n"
        "from matplotlib import pyplot as mpl\n"
        "plt.gca().add_patch(mpatch.Circle((0, 0), 1))\n")
    # The alias assignment goes through the `matplotlib` name the renderer binds
    # to matplotvite, so no Matplotlib import is needed.
    assert "mpatch = matplotlib.patches" in snippet
    assert "mtrans = matplotlib.transforms" in snippet
    assert "mdates = matplotlib.dates" in snippet
    assert "mpl = " not in snippet.split("plt.gca()")[0].replace("mpatch", "")
    assert "import matplotlib" not in snippet


def test_render_uses_module_alias_imports(tmp_path):
    out = tmp_path / "out.png"
    snippet = prepare_example(
        "import matplotlib.pyplot as plt\n"
        "import matplotlib.patches as mpatch\n"
        "plt.gca().add_patch(mpatch.Circle((0.5, 0.5), 0.4))\n")
    assert render(snippet, out) is None
    assert out.exists()


def test_prepare_example_rewrites_toolkit_imports_to_the_scoped_shim():
    # The wheel deliberately ships no top-level `mpl_toolkits`, so a harvested
    # snippet must import the shim inside matplotvite.
    snippet = prepare_example(
        "import matplotlib.pyplot as plt\n"
        "from mpl_toolkits.axes_grid1 import make_axes_locatable\n"
        "import mpl_toolkits.axes_grid1.inset_locator as loc\n"
        "fig, ax = plt.subplots()\n")
    assert ("from matplotvite.mpl_toolkits.axes_grid1 import "
            "make_axes_locatable") in snippet
    assert "import matplotvite.mpl_toolkits.axes_grid1.inset_locator as loc" in snippet
    assert "import mpl_toolkits" not in snippet


def test_prepare_example_renders_a_toolkit_inset(tmp_path):
    out = tmp_path / "out.png"
    snippet = prepare_example(
        "import matplotlib.pyplot as plt\n"
        "from mpl_toolkits.axes_grid1.inset_locator import inset_axes\n"
        "fig, ax = plt.subplots()\n"
        "ax.plot([0, 1], [1, 0])\n"
        "inset_axes(ax, width='30%', height='30%', loc='upper left')\n")
    assert render(snippet, out) is None
    assert out.exists()


def test_sample_data_is_resolved_from_the_sdist(tmp_path):
    import numpy as np

    root = tmp_path / "matplotlib-9.9" / "lib" / "matplotlib" / "mpl-data" / "sample_data"
    root.mkdir(parents=True)
    np.save(root / "array.npy", np.arange(6).reshape(2, 3))
    np.savez(root / "arrays.npz", values=np.arange(3))
    with gzip.open(root / "raw.dat.gz", "wb") as handle:
        handle.write(np.arange(4, dtype=np.uint16).tobytes())

    assert find_sample_data(tmp_path) == root.resolve()
    cbook = _SampleDataCbook(root)
    assert cbook.get_sample_data("array.npy").tolist() == [[0, 1, 2], [3, 4, 5]]
    assert cbook.get_sample_data("arrays.npz")["values"].tolist() == [0, 1, 2]
    # `.gz` sample data is decompressed, as Matplotlib's open_file_cm does.
    with cbook.get_sample_data("raw.dat.gz") as handle:
        assert np.frombuffer(handle.read(), np.uint16).tolist() == [0, 1, 2, 3]


def test_prepare_body_skips_unrenderable_bodies():
    cleaned = prepare_body("    import matplotlib.pyplot as plt\n    plt.plot([1])\n")
    assert cleaned.startswith("plt.plot([1])")
    assert cleaned.endswith("plt.savefig(OUT, dpi=100)\n")
    for body in ("    plt.savefig('x.png')\n",
                 "    pytest.raises(ValueError, plt.plot)\n",
                 "    assert True\n"):
        assert prepare_body(body) is None


def test_prepare_body_drops_test_only_imports():
    cleaned = prepare_body(
        "    import pytest\n"
        "    from pytest import raises\n"
        "    plt.plot([1])\n")
    assert cleaned.startswith("plt.plot([1])")
    assert "pytest" not in cleaned


def test_resolve_baseline_fills_in_png_suffix(tmp_path):
    root = make_root(tmp_path)
    image = root / "baseline_images" / "test_demo" / "param.png"
    image.touch()
    assert _resolve_baseline(root, "test_demo", "param") == image
    assert _resolve_baseline(root, "test_demo", "grid_1.png").name == "grid_1.png"


def test_find_tests_root_accepts_a_checkout_or_the_tests_directory(tmp_path):
    root = make_root(tmp_path)
    assert find_tests_root(root) == root
    # An sdist keeps them under `matplotlib-<version>/lib/matplotlib/tests`.
    nested = (tmp_path / "sdist" / "matplotlib-3.11.2" / "lib" / "matplotlib"
              / "tests" / "baseline_images")
    nested.mkdir(parents=True)
    assert find_tests_root(tmp_path / "sdist") == nested.parent
    assert find_tests_root(tmp_path / "nowhere") is None


def test_find_examples_root_prefers_the_gallery_directory(tmp_path):
    checkout = tmp_path / "mpl"
    lines = checkout / "galleries" / "examples" / "lines"
    lines.mkdir(parents=True)
    (lines / "demo.py").write_text("import matplotlib.pyplot as plt\n", encoding="utf-8")
    assert find_examples_root(checkout) == checkout / "galleries" / "examples"
    assert find_examples_root(tmp_path) is None


def test_prepare_body_removes_multiline_asserts():
    cleaned = prepare_body(
        "    plt.plot([0, 1])\n"
        "    assert plt.gca().get_xlim() == (0, 1), (\n"
        "        'unexpected limits')\n")
    assert cleaned.startswith("plt.plot([0, 1])")
    assert "assert" not in cleaned


def test_prepare_example_prunes_empty_blocks():
    snippet = prepare_example(
        "import matplotlib.pyplot as plt\n"
        "if True:\n"
        "    plt.show()\n"
        "plt.plot([0, 1])\n")
    assert "if" not in snippet
    assert "plt.plot([0, 1])" in snippet


def test_prepare_example_strips_imports_and_interactive_tail():
    snippet = prepare_example(
        '"""Demo gallery example."""\n'
        "import numpy as np\nimport matplotlib.pyplot as plt\n"
        "from matplotlib.patches import Circle\n"
        "fig, ax = plt.subplots()\n"
        "ax.add_patch(Circle((0, 0), radius=1))\n"
        "plt.show()\n"
        'if __name__ == "__main__":\n    plt.show()\n')
    assert "import" not in snippet
    assert "show" not in snippet
    assert snippet.endswith("plt.savefig(OUT, dpi=100)\n")
    assert prepare_example("input('press enter')") is None
    assert prepare_example("def broken(:\n") is None


def test_harvest_examples_tags_each_script_with_its_category(tmp_path):
    root = tmp_path / "examples"
    (root / "lines").mkdir(parents=True)
    (root / "lines" / "band.py").write_text(
        '"""Confidence bands.\n=================\n"""\nimport matplotlib.pyplot as plt\n'
        "plt.plot([0, 1])\n", encoding="utf-8")
    (root / "interactive.py").write_text("input()\n", encoding="utf-8")
    cases = {case["id"]: case for case in harvest_examples(root)}
    assert cases["lines/band"]["category"] == "lines"
    assert cases["lines/band"]["description"] == "Confidence bands."
    assert cases["interactive"]["category"] == "examples"
    assert cases["interactive"]["snippet"] is None
    assert "plt.plot([0, 1])" in cases["lines/band"]["snippet"]
    assert "matplotlib" not in cases["lines/band"]["snippet"]


def test_examples_gallery_marks_out_of_scope_categories(tmp_path):
    root = tmp_path / "examples"
    script = "import matplotlib.pyplot as plt\nplt.plot([0, 1], [1, 0])\n"
    for category in ("mplot3d", "widgets", "lines"):
        (root / category).mkdir(parents=True)
        (root / category / "demo.py").write_text(script, encoding="utf-8")
    out = tmp_path / "gallery"
    assert harvest_examples_gallery(root, out, out / "manifest.json") == 0
    cases = {case["id"]: case for case in json.loads(
        (out / "manifest.json").read_text(encoding="utf-8"))}
    # A still render cannot judge a GUI or 3-D example, so it must not be
    # counted as a matplotvite failure.
    assert cases["mplot3d/demo"]["status"] == "unsupported"
    assert cases["widgets/demo"]["status"] == "unsupported"
    assert cases["mplot3d/demo"]["error"] == "mplot3d is out of scope"
    assert cases["lines/demo"]["status"] == "rendered"
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "2 unsupported" in index


def test_failure_status_splits_gaps_from_missing_apis():
    assert failure_status(None) == "failed"
    # A stripped name matplotvite already exposes is the harvester's fault.
    assert failure_status(
        "NameError: name 'MaxNLocator' is not defined") == "harvester-gap"
    assert failure_status(
        "NameError: name 'streamplot' is not defined") == "needs-api"
    assert failure_status(
        "AttributeError: 'Axes' object has no attribute 'triplot'") == "needs-api"
    assert failure_status("NotImplementedError: 'symlog'") == "needs-api"
    # A missing toolkit or a local helper that imports Matplotlib is a harness
    # limitation, not a matplotvite bug.
    assert failure_status(
        "ModuleNotFoundError: No module named 'PIL'") == "harvester-gap"
    assert failure_status(
        "ImportError: cannot import name 'BboxConnector'") == "needs-api"
    assert failure_status("TypeError: fill expects (x, y)") == "bug"


def test_render_runs_in_a_scratch_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out" / "case.png"
    snippet = ("import pathlib\npathlib.Path('stray.png').write_text('x')\n"
               "plt.plot([0, 1], [1, 0])\nplt.savefig(OUT, dpi=100)\n")
    assert render(snippet, out) is None
    assert out.exists()
    assert not (tmp_path / "stray.png").exists()


def test_render_returns_the_failure_reason(tmp_path):
    out = tmp_path / "out.png"
    assert render("raise ValueError('boom')\n", out) == "ValueError: boom"
    assert render("plt.plot([0, 1])\n", out) == "no figure saved"


def test_render_resolves_stripped_submodule_names(tmp_path):
    out = tmp_path / "out.png"
    snippet = ("locator = MaxNLocator(3)\n"
               "cmap = LinearSegmentedColormap\n"
               "values = ma.masked_array([1, 2, 3])\n"
               "plt.plot(rand(4), color=TABLEAU_COLORS['tab:blue'])\n"
               "plt.savefig(OUT, dpi=100)\n")
    assert render(snippet, out) is None
    assert out.exists()


def test_render_records_ignored_shim_calls(tmp_path):
    out = tmp_path / "out.png"
    ignored = []
    snippet = ("plt.plot([0, 1], [1, 0])\n"
               "plt.gca().set_frame_on(False)\n"
               "plt.savefig(OUT, dpi=100)\n")
    assert render(snippet, out, ignored=ignored) is None
    assert "Axes.set_frame_on" in ignored


def test_render_exposes_local_example_modules(tmp_path, monkeypatch):
    (tmp_path / "helper.py").write_text("VALUE = 2\n", encoding="utf-8")
    out = tmp_path / "out" / "case.png"
    snippet = ("from helper import VALUE\nplt.plot([0, VALUE])\n"
               "plt.savefig(OUT, dpi=100)\n")
    monkeypatch.chdir(tmp_path)
    assert render(snippet, out, Path(".")) is None
    assert out.exists()


def test_harvest_marks_blank_renders_as_blank(tmp_path):
    root = tmp_path / "tests"
    (root / "baseline_images" / "test_demo").mkdir(parents=True)
    (root / "test_demo.py").write_text(
        "@image_comparison(['blank.png'])\n"
        "def test_blank():\n"
        "    plt.figure()\n"
        "\n"
        "@image_comparison(['drawn.png'])\n"
        "def test_drawn():\n"
        "    plt.plot([0, 1], [1, 0])\n", encoding="utf-8")
    baseline = root / "baseline_images" / "test_demo" / "drawn.png"
    matplotvite.close("all")
    matplotvite.plot([0, 1], [1, 0])
    matplotvite.savefig(baseline)
    matplotvite.close("all")
    out = tmp_path / "gallery"
    counts = harvest_gallery(root, out, out / "manifest.json")
    assert counts["blank"] == 1 and counts["rendered"] == 1
    manifest = {case["id"]: case for case in
                json.loads((out / "manifest.json").read_text(encoding="utf-8"))}
    assert manifest["test_demo/test_blank"]["status"] == "blank"
    assert manifest["test_demo/test_blank"]["nonwhite"] < 50
    assert manifest["test_demo/test_drawn"]["status"] == "rendered"


def test_harvest_gallery_writes_index_and_manifest(tmp_path):
    root = make_root(tmp_path)
    # A real baseline lets the case be measured rather than reported as missing.
    baseline = root / "baseline_images" / "test_demo" / "grid_1.png"
    matplotvite.close("all")
    matplotvite.plot([0, 1], [1, 0])
    matplotvite.savefig(baseline)
    matplotvite.close("all")

    out = tmp_path / "gallery"
    manifest_path = out / "manifest.json"
    counts = harvest_gallery(root, out, manifest_path)
    assert counts == {"cases": 2, "rendered": 1, "blank": 0, "failed": 0,
                     "unsupported": 1}
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "test_demo/test_grid" in index and "test_demo_test_grid.png" in index
    assert "parametrised test" in index
    # The baseline is copied in so the gallery is browsable away from the sdist.
    assert "baseline_test_demo_test_grid.png" in index
    assert (out / "baseline_test_demo_test_grid.png").exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rendered = {case["id"]: case for case in manifest}["test_demo/test_grid"]
    assert rendered["status"] == "rendered"
    assert rendered["ignored"] == 0
    # The pixel metric reads PNGs through Matplotlib, which the CI test jobs do
    # not install; the case still counts as rendered and explains the gap.
    if rendered.get("metrics_error") is None:
        assert rendered["mismatch_pct"] is not None
