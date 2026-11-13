"""Tests for the Seaborn gallery classifier."""

import json
from pathlib import Path

from tools.harvest_seaborn import (calls_in, classify, find_examples_root,
                                   harvest, write_gallery)


def test_theming_only_example_passes():
    result = classify(["set_theme", "load_dataset", "despine", "color_palette"],
                      ["subplots", "tight_layout"])
    assert result["status"] == "pass"
    assert result["needs"] == []


def test_plotting_function_reports_the_missing_capability():
    result = classify(["set_theme", "lineplot"], [])
    assert result["status"] == "needs-api"
    assert result["needs"] == ["line + band with hue/style grouping"]


def test_scipy_backed_function_is_unsupported():
    assert classify(["clustermap"], [])["status"] == "unsupported"


def test_missing_pyplot_function_needs_api():
    assert classify(["set_theme"], ["not_a_real_function"])["status"] == "needs-api"


def test_harvest_reads_each_script(tmp_path: Path):
    (tmp_path / "band.py").write_text(
        '"""A band\n=======\n"""\nimport seaborn as sns\n'
        'sns.set_theme()\nsns.lineplot(x="x", y="y")\n',
        encoding="utf-8")
    (tmp_path / "table.py").write_text("import seaborn as sns\nsns.clustermap()\n",
                                       encoding="utf-8")
    cases = {case["id"]: case for case in harvest(tmp_path)}
    assert cases["band"]["status"] == "needs-api"
    assert cases["band"]["description"] == "A band"
    assert cases["table"]["status"] == "unsupported"


def test_calls_in_collects_seaborn_and_pyplot_names(tmp_path: Path):
    import ast

    tree = ast.parse("import seaborn as sns\nimport matplotlib.pyplot as plt\n"
                     "sns.set_theme()\nsns.lineplot(x=[1])\nplt.subplots()\nplt.subplots()\n")
    sns_calls, plt_calls = calls_in(tree)
    assert sns_calls == ["set_theme", "lineplot"]
    assert plt_calls == ["subplots"]


def test_find_examples_root_accepts_the_checkout_or_examples_dir(tmp_path: Path):
    examples = tmp_path / "sns" / "examples"
    examples.mkdir(parents=True)
    (examples / "demo.py").write_text("import seaborn as sns\n", encoding="utf-8")
    assert find_examples_root(tmp_path / "sns") == examples
    assert find_examples_root(examples) == examples
    assert find_examples_root(tmp_path / "nothing") is None


def test_write_gallery_ranks_capabilities(tmp_path: Path):
    cases = []
    for name, script in (("theme", "sns.set_theme()\n"),
                         ("band", "sns.lineplot(x=[1], y=[1])\n"),
                         ("table", "sns.clustermap()\n")):
        path = tmp_path / f"{name}.py"
        path.write_text(script, encoding="utf-8")
        cases.extend(harvest(tmp_path))
        path.unlink()
    counts = write_gallery(cases, tmp_path / "gallery")
    assert counts == {"pass": 1, "needs-api": 1, "unsupported": 1}
    index = (tmp_path / "gallery" / "index.html").read_text(encoding="utf-8")
    assert "3 Seaborn examples: 1 pass, 1 needs-API, 1 unsupported" in index
    assert "line + band with hue/style grouping (1 example)" in index
    assert "hierarchical clustering" in index
    manifest = json.loads((tmp_path / "gallery" / "manifest.json").read_text(encoding="utf-8"))
    assert [case["status"] for case in manifest] == ["pass", "needs-api", "unsupported"]
