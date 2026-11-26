"""Tests for the readable OpenSSF Scorecard report."""

import json
import sys

import pytest

from tools.scorecard_report import main as scorecard_report

COMMIT = "a" * 40


def _rule(rule_id, name, severity="error", **extra):
    return {
        "id": rule_id,
        "name": name,
        "helpUri": f"https://example.test/checks#{name.lower()}",
        "fullDescription": {"text": f"Description for {name}"},
        "help": {"markdown": f"**Remediation**: fix {name}"},
        "properties": {"problem.severity": severity},
        **extra,
    }


def _sarif(results):
    return {
        "version": "2.1.0",
        "runs": [{
            "automationDetails": {"id": f"online-scm/supply-chain/{COMMIT}-date"},
            "tool": {"driver": {"name": "Scorecard", "rules": [
                _rule("DangerousWorkflowID", "Dangerous-Workflow"),
                _rule("PinnedDependenciesID", "Pinned-Dependencies",
                      severity="warning"),
            ]}},
            "results": results,
        }],
    }


RESULT = {
    "ruleId": "DangerousWorkflowID",
    "ruleIndex": 0,
    "message": {"text": "score is 7: 2 dangerous workflow patterns detected\n"
                        "Click Remediation section below for further help"},
    "locations": [{"physicalLocation": {
        "artifactLocation": {"uri": ".github/workflows/ci.yml"},
        "region": {"startLine": 22},
    }}],
}


def _write(tmp_path, results):
    path = tmp_path / "results.sarif"
    path.write_text(json.dumps(_sarif(results)), encoding="utf-8")
    return path


def test_report_writes_html_and_markdown_summary(tmp_path, monkeypatch, capsys):
    sarif = _write(tmp_path, [RESULT])
    monkeypatch.setattr(sys, "argv", [
        "scorecard_report", str(sarif), "--out", str(tmp_path / "out"),
        "--repository", "owner/project", "--commit", COMMIT])
    assert scorecard_report() == 0

    markdown = capsys.readouterr().out
    assert "2 checks ran; 1 reported 1 finding" in markdown
    assert "[Dangerous-Workflow](https://example.test/checks#dangerous-workflow)" in markdown
    assert "| 7 | error | 2 dangerous workflow patterns detected " \
           "(`.github/workflows/ci.yml:22`) |" in markdown
    assert "Pinned-Dependencies" not in markdown
    assert "Checks without a row raised no alert" in markdown

    page = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "OpenSSF Scorecard" in page
    assert "Dangerous-Workflow" in page
    assert "Pinned-Dependencies" in page
    assert "No alerts" in page
    assert "score 7" in page
    assert ".github/workflows/ci.yml:22" in page
    assert "fix Dangerous-Workflow" in page
    assert "https://securityscorecards.dev/viewer/?uri=github.com/owner/project" in page
    assert f"https://github.com/owner/project/commit/{COMMIT}" in page


def test_report_handles_clean_run(tmp_path, monkeypatch, capsys):
    sarif = _write(tmp_path, [])
    monkeypatch.setattr(sys, "argv", [
        "scorecard_report", str(sarif), "--out", str(tmp_path / "out")])
    assert scorecard_report() == 0

    markdown = capsys.readouterr().out
    assert "No check reported an alert." in markdown
    assert "| Check |" not in markdown

    page = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert page.count("No alerts") == 2
    assert "No check reported an alert." in page


def test_report_escapes_untrusted_sarif_text(tmp_path, monkeypatch, capsys):
    result = json.loads(json.dumps(RESULT))
    result["message"]["text"] = "score is 3: <script>alert(1)</script>"
    result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] = (
        "javascript:alert(1)")
    sarif = _write(tmp_path, [result])
    sarif.write_text(sarif.read_text(encoding="utf-8").replace(
        "https://example.test/checks#dangerous-workflow", "javascript:alert(2)"),
        encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "scorecard_report", str(sarif), "--out", str(tmp_path / "out")])
    assert scorecard_report() == 0
    page = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert 'href="javascript:' not in page


def test_report_rejects_a_missing_sarif(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "scorecard_report", str(tmp_path / "absent.sarif"),
        "--out", str(tmp_path / "out")])
    with pytest.raises(FileNotFoundError):
        scorecard_report()
