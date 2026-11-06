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


def test_single_subplots_returns_axes_and_pyplot_targets_current(tmp_path):
    fig, ax = plt.subplots()
    assert isinstance(ax, plt.Axes)
    with pytest.raises(ValueError):
        plt.subplot(1, 2, 2)
    plt.title("via pyplot"); ax.plot([1, 2]); plt.savefig(tmp_path / "s.svg")
    assert "via pyplot" in (tmp_path / "s.svg").read_text()
