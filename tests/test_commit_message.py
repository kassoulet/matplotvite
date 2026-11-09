"""Tests for the commit-message co-author check."""

from tools.check_commit_message import main, offence

CLEAN = "Add a plot family\n\nBody text.\n"


def test_clean_message_has_no_offence():
    assert offence(CLEAN) is None


def test_co_author_trailers_are_rejected_in_any_case():
    for line in ("Co-Authored-By: someone <a@b.c>",
                 "Co-authored-by: google-labs-jules[bot] <bot@example.com>",
                 "co-authored-by: x <x@y.z>",
                 "CO-AUTHORED-BY: x <x@y.z>",
                 "  Co-authored-by : x <x@y.z>"):
        assert offence(f"{CLEAN}\n{line}\n") == line.strip()


def test_comments_and_scissors_section_are_ignored():
    assert offence("# Co-Authored-By: someone <a@b.c>\n") is None
    message = ("Subject\n\n# ------------------------ >8 ------------------------\n"
               "Co-Authored-By: someone <a@b.c>\n")
    assert offence(message) is None


def test_main_reports_the_trailer(tmp_path, capsys):
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text(f"{CLEAN}\nCo-Authored-By: bot <bot@example.com>\n", encoding="utf-8")
    assert main(["check", str(message)]) == 1
    captured = capsys.readouterr()
    assert "co-author trailer" in captured.err
    assert "Co-Authored-By: bot" in captured.err

    message.write_text(CLEAN, encoding="utf-8")
    assert main(["check", str(message)]) == 0
    assert main(["check"]) == 2
