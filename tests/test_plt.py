import re

import numpy as np
import pytest
import plt_rs as plt


def _fig():
    f = plt.figure((4, 3))
    plt.plot(np.arange(10), np.arange(10) ** 2, label="sq", color="red")
    plt.plot([1, 2, 3], label="list")  # y only
    plt.title("t"); plt.xlabel("x"); plt.ylabel("y"); plt.legend()
    return f


def test_png(tmp_path):
    p = tmp_path / "a.png"
    _fig().savefig(p)
    b = p.read_bytes()
    assert b[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(b[16:20], "big") == 400 and int.from_bytes(b[20:24], "big") == 300


def test_svg(tmp_path):
    p = tmp_path / "a.svg"
    plt.savefig(_fig() and p)
    s = p.read_text()
    assert s.startswith("<svg") and "sq" in s and "</svg>" in s


def test_constant_series(tmp_path):
    plt.figure(); plt.plot([1, 2, 3], [5, 5, 5]); plt.savefig(tmp_path / "c.png")
    assert (tmp_path / "c.png").stat().st_size > 0


def test_empty_raises(tmp_path):
    plt.figure()
    with pytest.raises(RuntimeError):
        plt.savefig(tmp_path / "e.png")


def test_bad_path():
    plt.figure(); plt.plot([1, 2]);
    with pytest.raises(RuntimeError):
        plt.savefig("/nonexistent/dir/x.png")


def test_subplots_grid(tmp_path):
    fig, axs = plt.subplots(2, 2, figsize=(4, 4))
    assert axs.shape == (2, 2)
    axs[0, 0].plot([1, 2, 3]); axs[1, 1].plot([3, 2, 1], label="b")
    axs[1, 1].legend(); axs[0, 1].set_title("empty"); axs[0, 0].set_xlim(0, 5)
    for ext in ("png", "svg"):
        fig.savefig(tmp_path / f"g.{ext}")
        assert (tmp_path / f"g.{ext}").stat().st_size > 0


def test_dpi_and_format_override(tmp_path):
    plt.figure((4, 3)); plt.plot([1, 2, 3])
    hi = tmp_path / "hi.png"
    plt.savefig(hi, dpi=200)
    b = hi.read_bytes()
    assert (int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")) == (800, 600)

    svg = tmp_path / "out.dat"
    plt.savefig(svg, format="svg")
    assert svg.read_text().startswith("<svg")


def test_tight_bbox_crops_whitespace(tmp_path):
    plt.figure((4, 3)); plt.plot([1, 2, 3])
    plain, tight = tmp_path / "plain.png", tmp_path / "tight.png"
    plt.savefig(plain); plt.savefig(tight, bbox_inches="tight")
    assert int.from_bytes(tight.read_bytes()[16:20], "big") < 400

    svg = tmp_path / "tight.svg"
    plt.savefig(svg, bbox_inches="tight")
    assert 'viewBox="0 0 400 300"' not in svg.read_text()


def test_transparent_drops_background(tmp_path):
    plt.figure((4, 3)); plt.plot([1, 2, 3])
    p = tmp_path / "t.svg"
    plt.savefig(p, transparent=True)
    assert 'fill="#FFFFFF"' not in p.read_text()


def test_bad_savefig_kwargs(tmp_path):
    plt.figure(); plt.plot([1, 2])
    for kw in ({"format": "pdf"}, {"bbox_inches": "loose"}):
        with pytest.raises(ValueError):
            plt.savefig(tmp_path / "x.png", **kw)


def test_text_annotations(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.text(0.5, 0.5, "hi there", color="red", fontsize=14)
    plt.text(0.1, 0.9, "second", ha="center", va="top")
    svg = tmp_path / "t.svg"
    fig.savefig(svg)
    s = svg.read_text()
    assert "hi there" in s and "second" in s
    fig.savefig(tmp_path / "t.png")
    assert (tmp_path / "t.png").stat().st_size > 0

    with pytest.raises(ValueError):
        ax.text(0, 0, "x", ha="middle")
    with pytest.raises(ValueError):
        ax.text(0, 0, "x", va="middle")


def test_text_stays_in_its_panel(tmp_path):
    fig, axs = plt.subplots(1, 2, figsize=(8, 3))
    axs[0].plot([0, 1], [0, 1]); axs[1].plot([0, 1], [0, 1])
    axs[0].text(0.5, 0.5, "L")
    axs[1].text(0.5, 0.5, "R")
    p = tmp_path / "panels.svg"
    fig.savefig(p)
    xs = {m.group(2): int(m.group(1))
          for m in re.finditer(r'<text x="(-?\d+)"[^>]*>\s*(\w)', p.read_text())}
    assert 0 < xs["L"] < 400 < xs["R"] < 800


def test_text_only_figure(tmp_path):
    plt.figure()
    plt.text(0.5, 0.5, "lonely")
    plt.savefig(tmp_path / "only.svg")
    assert "lonely" in (tmp_path / "only.svg").read_text()


def test_single_subplots_returns_axes_and_pyplot_targets_current(tmp_path):
    fig, ax = plt.subplots()
    assert isinstance(ax, plt.Axes)
    with pytest.raises(ValueError):
        plt.subplot(1, 2, 2)
    plt.title("via pyplot"); ax.plot([1, 2]); plt.savefig(tmp_path / "s.svg")
    assert "via pyplot" in (tmp_path / "s.svg").read_text()
