"""Tests for the Seaborn gallery classifier."""

from pathlib import Path

from tools.harvest_seaborn import classify, harvest


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
