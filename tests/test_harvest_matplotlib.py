"""Tests for the Matplotlib baseline-image and gallery harvester."""

import json
from pathlib import Path

import matplotvite

from tools.harvest_matplotlib import (_resolve_baseline, find_examples_root,
                                      find_tests_root, harvest, harvest_examples,
                                      harvest_gallery, prepare_body,
                                      prepare_example, render)

MODULE = '''import matplotlib.pyplot as plt
import numpy as np


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
    # The snippet drops matplotlib/numpy imports and saves the figure itself.
    assert "import matplotlib" not in cases[0]["snippet"]
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


def test_prepare_body_skips_unrenderable_bodies():
    cleaned = prepare_body("    import matplotlib.pyplot as plt\n    plt.plot([1])\n")
    assert cleaned.startswith("plt.plot([1])")
    assert cleaned.endswith("plt.savefig(OUT, dpi=100)\n")
    for body in ("    plt.savefig('x.png')\n",
                 "    pytest.raises(ValueError, plt.plot)\n",
                 "    assert True\n"):
        assert prepare_body(body) is None


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
    assert counts == {"cases": 2, "rendered": 1, "failed": 0, "unsupported": 1}
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
