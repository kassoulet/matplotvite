"""Tests for the Matplotlib baseline-image harvester."""

from pathlib import Path

from tools.harvest_matplotlib import _resolve_baseline, harvest, prepare_body

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
