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


@pytest.mark.parametrize("compression", ["fast", "default", "best"])
def test_png_compression(tmp_path, compression):
    p = tmp_path / f"{compression}.png"
    _fig()
    plt.savefig(p, compression=compression)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_png_compression_invalid(tmp_path):
    with pytest.raises(ValueError):
        _fig().savefig(tmp_path / "bad.png", compression="tiny")
    with pytest.raises(ValueError):
        _fig().savefig(tmp_path / "bad.svg", compression="fast")


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
    with pytest.raises(OSError):
        plt.savefig("/nonexistent/dir/x.png")


def test_subplots_grid(tmp_path):
    fig, axs = plt.subplots(2, 2, figsize=(4, 4))
    assert axs.shape == (2, 2)
    axs[0, 0].plot([1, 2, 3]); axs[1, 1].plot([3, 2, 1], label="b")
    axs[1, 1].legend(); axs[0, 1].set_title("empty"); axs[0, 0].set_xlim(0, 5)
    for ext in ("png", "svg"):
        fig.savefig(tmp_path / f"g.{ext}")
        assert (tmp_path / f"g.{ext}").stat().st_size > 0


def test_pdf(tmp_path):
    fig = plt.figure((4, 3)); plt.plot([1, 2, 3], [1, 4, 9]); plt.title("pdf")
    # Extension inference and an explicit format must both produce a real PDF
    # (not a PNG with a .pdf suffix), sized from the figure in inches.
    for name, kw in (("inferred.pdf", {}), ("explicit.pdf", {"format": "pdf"})):
        p = tmp_path / name
        fig.savefig(p, **kw)
        b = p.read_bytes()
        assert b[:5] == b"%PDF-" and b.rstrip().endswith(b"%%EOF")
        m = re.search(rb"MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", b)
        assert m, "missing MediaBox"
        w, h = (float(v) for v in m.groups())
        assert abs(w - 288) < 0.5 and abs(h - 216) < 0.5


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


def test_tight_bbox_with_colored_background(tmp_path):
    fig = plt.figure((4, 3), facecolor="red")
    fig.gca().plot([1, 2, 3])
    tight = tmp_path / "tight-red.png"
    fig.savefig(tight, bbox_inches="tight")
    assert int.from_bytes(tight.read_bytes()[16:20], "big") < 400


def test_file_like_name_selects_format(tmp_path):
    import io

    class NamedBuffer(io.BytesIO):
        name = "figure.svg"

    fig = plt.figure((4, 3)); fig.gca().plot([1, 2, 3])
    buf = NamedBuffer()
    fig.savefig(buf)
    assert buf.getvalue().startswith(b"<svg")


def test_transparent_drops_background(tmp_path):
    plt.figure((4, 3)); plt.plot([1, 2, 3])
    p = tmp_path / "t.svg"
    plt.savefig(p, transparent=True)
    assert 'fill="#FFFFFF"' not in p.read_text()


def test_bad_savefig_kwargs(tmp_path):
    plt.figure(); plt.plot([1, 2])
    # format="pdf" is now supported; only bbox_inches="loose" should raise
    with pytest.raises(ValueError):
        plt.savefig(tmp_path / "x.png", bbox_inches="loose")


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


def test_imshow_renders(tmp_path):
    plt.figure((4, 3))
    plt.imshow(np.linspace(0, 1, 100).reshape(10, 10))
    svg = tmp_path / "im.svg"
    plt.savefig(svg)
    s = svg.read_text()
    assert "<image" in s and "data:image/png;base64," in s
    plt.savefig(tmp_path / "im.png")
    assert (tmp_path / "im.png").stat().st_size > 0


def test_imshow_rgb_handle_and_errors(tmp_path):
    plt.figure((4, 3))
    ax = plt.gca()
    ax.imshow(np.random.rand(8, 8, 3), extent=(-1, 1, -1, 1))
    im = ax.imshow(np.zeros((4, 4)))
    assert im.get_array().shape == (4, 4)
    im.set_clim(0, 1)
    im.set_data(np.ones((4, 4)))
    im.set_cmap("gray")
    with pytest.raises(ValueError):
        ax.imshow(np.zeros((2, 2, 2)))
    with pytest.raises(ValueError):
        ax.imshow(np.zeros((2, 2)), origin="middle")
    plt.savefig(tmp_path / "rgb.png")
    assert (tmp_path / "rgb.png").stat().st_size > 0


def _image_box(svg_path):
    m = re.search(r'<image x="[-\d]+" y="[-\d]+" width="(\d+)" height="(\d+)"',
                  svg_path.read_text())
    return int(m.group(1)), int(m.group(2))


def test_imshow_equal_aspect_squares_pixels(tmp_path):
    plt.figure((4, 3))
    plt.imshow(np.zeros((10, 20)))  # 20 wide x 10 tall data
    p = tmp_path / "eq.svg"
    plt.savefig(p)
    w, h = _image_box(p)
    assert abs(w / h - 2.0) < 0.15


def test_imshow_aspect_auto_and_set_aspect(tmp_path):
    plt.figure((4, 3))
    plt.imshow(np.zeros((10, 20)), aspect="auto")
    p = tmp_path / "auto.svg"
    plt.savefig(p)
    w, h = _image_box(p)
    assert w / h < 1.8  # fills the panel instead of squaring the data

    plt.figure((4, 3))
    ax = plt.gca()
    ax.imshow(np.zeros((10, 20)), aspect="auto")
    assert ax.get_aspect() is None
    ax.set_aspect("equal")
    p2 = tmp_path / "set.svg"
    plt.savefig(p2)
    w2, h2 = _image_box(p2)
    assert abs(w2 / h2 - 2.0) < 0.15

    with pytest.raises(ValueError):
        ax.set_aspect("square")
    with pytest.raises(ValueError):
        ax.set_aspect(-1)


def test_annotate_arrow(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.annotate("peak", xy=(0.5, 0.5), xytext=(0.2, 0.8))
    plt.annotate("plain", xy=(0.1, 0.1))
    p = tmp_path / "ann.svg"
    fig.savefig(p)
    s = p.read_text()
    assert "peak" in s and "plain" in s
    assert "<polygon" in s  # arrow head


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


def _bump(n=30):
    x = np.linspace(-2, 2, n)
    y = np.linspace(-2, 2, n)
    return x, y, np.exp(-(x[None, :] ** 2 + y[:, None] ** 2))


def test_contour_lines(tmp_path):
    x, y, z = _bump()
    plt.figure((4, 3))
    cs = plt.contour(x, y, z, levels=[0.1, 0.5, 0.9])
    assert cs.levels == [0.1, 0.5, 0.9]
    p = tmp_path / "c.svg"
    plt.savefig(p)
    s = p.read_text()
    assert s.count("<polyline") >= 30 and "</svg>" in s


def test_contourf_fills(tmp_path):
    z = np.add.outer(np.arange(20.0), np.arange(20.0))
    plt.figure((4, 3))
    cs = plt.contourf(z, levels=[0, 10, 20, 30])
    assert cs.levels == [0.0, 10.0, 20.0, 30.0]
    p = tmp_path / "cf.svg"
    plt.savefig(p)
    assert p.read_text().count("<polygon") > 10


def test_contour_meshgrid_png(tmp_path):
    X, Y = np.meshgrid(np.linspace(-1, 1, 12), np.linspace(-1, 1, 12))
    plt.figure()
    plt.contour(X, Y, X * Y, cmap="viridis")
    p = tmp_path / "cm.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_contour_rejects_non_grids():
    plt.figure()
    with pytest.raises(ValueError):
        plt.contour(np.arange(5.0))
    with pytest.raises(ValueError):
        plt.contour(np.arange(3.0), np.arange(3.0), np.zeros((4, 4)))
    X, Y = np.meshgrid(np.arange(4.0), np.arange(4.0))
    with pytest.raises(NotImplementedError):
        plt.contour(X + Y, Y, np.zeros((4, 4)) + 1.0, levels=[0.0, 1.0])


def test_errorbar_bars_and_caps(tmp_path):
    plt.figure((4, 3))
    plt.errorbar([1, 2, 3], [1, 4, 9], yerr=[0.5, 1.0, 1.5], capsize=3, label="err")
    plt.legend()
    p = tmp_path / "eb.svg"
    plt.savefig(p)
    s = p.read_text()
    assert "err" in s
    assert s.count("<polyline") >= 9


def test_errorbar_asymmetric_xerr_png(tmp_path):
    plt.figure()
    plt.errorbar([1, 2], [3, 4], yerr=[[0.1, 0.2], [0.3, 0.4]], xerr=0.2, ecolor="red", fmt="o")
    p = tmp_path / "eb2.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_errorbar_rejects_bad_yerr():
    plt.figure()
    with pytest.raises(ValueError):
        plt.errorbar([1, 2], [3, 4], yerr=[1, 2, 3])


def test_colorbar_strip(tmp_path):
    plt.figure((6, 3))
    plt.contourf(np.add.outer(np.arange(20.0), np.arange(20.0)), levels=[0, 10, 20, 30])
    cb = plt.colorbar(label="z")
    cb.set_label("height")
    p = tmp_path / "cb.svg"
    plt.savefig(p)
    s = p.read_text()
    assert "height" in s
    assert s.count("<rect") + s.count("<polygon") > 60


def test_scatter_sizes_and_cmap(tmp_path):
    plt.figure((4, 3))
    plt.scatter([1, 2, 3], [1, 4, 9], s=[20, 60, 120], c=[0.0, 0.5, 1.0], marker="s")
    p = tmp_path / "sc.svg"
    plt.savefig(p)
    s = p.read_text()
    assert s.count("<rect") >= 4 and "</svg>" in s


def test_scatter_colors_and_markers(tmp_path):
    plt.figure()
    plt.scatter([0, 1, 2], [0, 1, 4], c=["red", "green", "blue"], marker="^", alpha=0.6)
    p = tmp_path / "sc2.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_scatter_rejects_bad_sizes():
    plt.figure()
    with pytest.raises(ValueError):
        plt.scatter([1, 2], [1, 2], s=[1, 2, 3])


def test_compat_noops():
    plt.figure()
    plt.plot([1, 2], [2, 1])
    assert plt.show() is None and plt.draw() is None and plt.pause(0.01) is None
    plt.ion()
    plt.ioff()
    assert plt.axes() is plt.gca()


def test_colorbar_needs_mappable():
    plt.figure()
    plt.plot([1, 2], [3, 4])
    with pytest.raises(ValueError):
        plt.colorbar()


def test_contour_default_and_int_levels(tmp_path):
    x, y, z = _bump()
    plt.figure((4, 3))
    cs = plt.contour(x, y, z)
    assert len(cs.levels) == 7 and cs.levels == sorted(cs.levels)
    cs.set_clim(0.0, 1.0)  # accepted no-op
    plt.savefig(tmp_path / "c7.png")

    plt.figure((4, 3))
    cs2 = plt.contourf(z, levels=5)
    assert len(cs2.levels) == 5
    assert cs2.get_cmap() == "viridis"
    cs2.set_cmap("gray")
    assert cs2.get_cmap() == "gray"
    plt.savefig(tmp_path / "c5.png")
    assert (tmp_path / "c5.png").stat().st_size > 0


def test_contour_explicit_colors_are_used(tmp_path):
    x, y, z = _bump()
    plt.figure((4, 3))
    plt.contour(x, y, z, levels=[0.2, 0.6], colors=["red", "blue"])
    p = tmp_path / "colors.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s and "#0000FF" in s


def test_contour_levels_validation():
    plt.figure()
    z = np.zeros((4, 4)) + 1.0
    with pytest.raises(ValueError):
        plt.contour(z, levels=1)
    with pytest.raises(ValueError):
        plt.contour(z, levels=[0.5])
    with pytest.raises(ValueError):
        plt.contour([0.0, 1.0], [0.0, 1.0], np.zeros((4, 4)))


def test_colorbar_from_explicit_mappable(tmp_path):
    x, y, z = _bump()
    fig, ax = plt.subplots(figsize=(6, 3))
    cs = ax.contourf(x, y, z, levels=[0.0, 0.5, 1.0])
    cb = fig.colorbar(cs, ax=ax, label="amp")
    assert cb.get_label() == "amp"
    p = tmp_path / "cbm.svg"
    fig.savefig(p)
    s = p.read_text()
    assert "amp" in s
    # min/mid/max tick labels come from the level range (plotters pads with newlines)
    assert re.search(r">\s*0\s*</text>", s) and re.search(r">\s*1\s*</text>", s)


def test_colorbar_rejects_multiple_axes():
    fig, axs = plt.subplots(1, 2, figsize=(6, 3))
    axs[0].plot([1, 2])
    axs[1].plot([2, 1])
    with pytest.raises(NotImplementedError):
        fig.colorbar()


def test_scatter_stroke_and_dot_markers(tmp_path):
    plt.figure((4, 3))
    plt.scatter([1, 2], [1, 2], marker="x", c="black")
    plt.scatter([1, 2], [2, 1], marker="+", c="red")
    plt.scatter([3], [1.5], marker=".", c="blue")
    p = tmp_path / "mk.svg"
    plt.savefig(p)
    s = p.read_text()
    assert s.count("<polyline") >= 4 and s.count("<circle") >= 1


def test_scatter_single_value_c_and_negative_sizes(tmp_path):
    plt.figure()
    plt.scatter([1, 2, 3], [3, 2, 1], c=0.5, s=-4)
    plt.savefig(tmp_path / "sc3.png")
    assert (tmp_path / "sc3.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_scatter_rejects_bad_c():
    plt.figure()
    with pytest.raises(ValueError):
        plt.scatter([1, 2], [1, 2], c=["red", "green", "blue"])


def test_scatter_alpha_reaches_the_svg(tmp_path):
    plt.figure()
    plt.scatter([1], [1], alpha=0.4)
    p = tmp_path / "alpha.svg"
    plt.savefig(p)
    assert re.search(r'opacity="0\.[34]', p.read_text())


def test_errorbar_fmt_line_and_xerr_only(tmp_path):
    plt.figure((4, 3))
    plt.errorbar([1, 2], [1, 2], xerr=0.3, fmt="r--")
    p = tmp_path / "ebx.svg"
    plt.savefig(p)
    s = p.read_text()
    assert s.count("<polyline") >= 3  # two bars plus the connecting line
    assert "#FF0000" in s.upper()


def test_errorbar_negative_errors_are_absolute(tmp_path):
    out = []
    for i, err in enumerate(([0.5, 1.0], [-0.5, -1.0])):
        plt.figure((4, 3))
        plt.errorbar([1, 2], [3, 4], yerr=err)
        p = tmp_path / f"eb{i}.svg"
        plt.savefig(p)
        out.append(p.read_text())
    assert out[0] == out[1]


def test_imshow_vmin_changes_pixels(tmp_path):
    z = np.linspace(0, 1, 64).reshape(8, 8)
    uris = []
    for vmin in (0.0, 0.5):
        plt.figure((3, 3))
        plt.imshow(z, vmin=vmin, vmax=1.0, cmap="gray")
        p = tmp_path / f"im_{vmin}.svg"
        plt.savefig(p)
        uris.append(re.search(r'href="data:image/png;base64,([^"]+)"', p.read_text()).group(1))
    assert uris[0] != uris[1]


def test_aspect_numeric_halves_the_box(tmp_path):
    plt.figure((4, 3))
    plt.imshow(np.zeros((10, 10)), aspect=2.0)
    p = tmp_path / "a2.svg"
    plt.savefig(p)
    w, h = _image_box(p)
    assert abs(w / h - 0.5) < 0.1


def test_mixed_subplots_render(tmp_path):
    fig, axs = plt.subplots(1, 2, figsize=(8, 3))
    x = np.linspace(-2, 2, 20)
    axs[0].contourf(x, x, np.exp(-(x[None, :] ** 2 + x[:, None] ** 2)), levels=4)
    axs[1].scatter(x, x ** 2, s=25, c=x)
    axs[1].errorbar(x, x ** 2, yerr=0.5, fmt="")
    p = tmp_path / "mix.png"
    fig.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_axes_position_and_window_extent():
    fig, axs = plt.subplots(2, 2, figsize=(8, 6))
    b = axs[0, 1].get_position()
    assert abs(b.x0 - 0.5) < 1e-9 and abs(b.width - 0.5) < 1e-9
    assert abs(b.y0 - 0.5) < 1e-9 and abs(b.height - 0.5) < 1e-9
    assert b.bounds == (b.x0, b.y0, b.width, b.height)
    px = axs[1, 1].get_window_extent()
    assert px.width > 300 and px.height > 200
    assert axs[0, 0].get_tightbbox().bounds == axs[0, 0].get_window_extent().bounds
    assert axs[0, 0].get_figure() is fig


def test_axes_limits_and_bounds_track_data():
    plt.figure()
    ax = plt.gca()
    ax.plot([2, 4, 6], [10, 30, 20])
    assert ax.get_xlim() == (2.0, 6.0) and ax.get_ylim() == (10.0, 30.0)
    assert ax.get_xbound() == ax.get_xlim() and ax.get_ybound() == ax.get_ylim()
    ax.set_xlim(0, 10)
    assert ax.get_xlim() == (0.0, 10.0)


def test_axes_set_dispatch(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.plot([0, 1], [0, 1])
    ax.set(xlim=(0, 5), ylim=(-1, 3), xlabel="t", ylabel="v", title="T",
           xticks=[0, 2.5, 5], yticks=[-1, 1, 3], aspect="auto")
    assert ax.get_xlim() == (0.0, 5.0) and ax.get_ylim() == (-1.0, 3.0)
    assert ax.get_xlabel() == "t" and ax.get_ylabel() == "v" and ax.get_title() == "T"
    assert list(ax.get_xticks()) == [0.0, 2.5, 5.0]
    p = tmp_path / "set.svg"
    plt.savefig(p)
    s = p.read_text()
    assert "T" in s and "t" in s and "v" in s
    with pytest.raises(AttributeError):
        ax.set(nonexistent=1)


def test_axes_tick_labels_are_text_like():
    plt.figure()
    ax = plt.gca()
    ax.plot([0, 1], [0, 1])
    ax.set_xticks([0.0, 1.0], labels=["lo", "hi"])
    labels = ax.get_xticklabels()
    assert [t.get_text() for t in labels] == ["lo", "hi"]
    labels[0].set_text("start")
    labels[0].set_visible(False)
    assert labels[0].get_text() == "start" and labels[0].get_visible() is False
    assert len(ax.get_yticks()) == 6


def test_hidden_and_removed_axes_are_not_drawn(tmp_path):
    fig, axs = plt.subplots(1, 2, figsize=(8, 3))
    axs[0].plot([0, 1], [0, 1])
    axs[0].set_title("keep")
    axs[1].plot([0, 1], [1, 0])
    axs[1].set_title("gone")
    axs[1].set_visible(False)
    p = tmp_path / "hidden.svg"
    fig.savefig(p)
    s = p.read_text()
    assert "keep" in s and "gone" not in s

    axs[1].set_visible(True)
    axs[1].remove()
    fig.savefig(p)
    assert "gone" not in p.read_text()

    plt.figure()
    plt.plot([1, 2])
    plt.gca().remove()
    with pytest.raises(RuntimeError):
        plt.savefig(tmp_path / "none.png")


def test_axis_off_hides_ticks_but_keeps_plot(tmp_path):
    plt.figure((4, 3))
    plt.plot([0, 1], [0, 1])
    plt.title("visible title")
    plain = tmp_path / "on.svg"
    plt.savefig(plain)
    ax = plt.gca()
    ax.set_axis_off()
    off = tmp_path / "off.svg"
    plt.savefig(off)
    a, b = plain.read_text(), off.read_text()
    assert "visible title" in b
    assert a.count("<text") > b.count("<text")
    ax.set_axis_on()
    ax.axis("off")
    assert ax._axis_off is True
    ax.axis("on")
    assert ax._axis_off is False
    ax.axis("equal")
    assert ax.get_aspect() == 1.0
    ax.axis("auto")
    assert ax.get_aspect() is None
    ax.axis([0, 2, -1, 1])
    assert ax.get_xlim() == (0.0, 2.0) and ax.get_ylim() == (-1.0, 1.0)


def test_pyplot_axis_dispatches_to_current_axes(tmp_path):
    plt.figure()
    plt.plot([0, 1], [0, 1])
    plt.axis("off")
    assert plt.gca()._axis_off is True
    plt.axis([0, 2, -1, 1])
    assert plt.gca().get_xlim() == (0.0, 2.0)
    assert plt.gca().get_ylim() == (-1.0, 1.0)
    p = tmp_path / "pyplot-axis.svg"
    plt.savefig(p)
    assert p.read_text().startswith("<svg")


def test_axes_inversion_and_rendering(tmp_path):
    plt.figure((4, 3))
    ax = plt.gca()
    ax.plot([0, 1, 2], [0, 1, 4])
    assert not ax.xaxis_inverted()
    ax.invert_xaxis()
    assert ax.xaxis_inverted()
    ax.invert_yaxis()
    assert ax.yaxis_inverted()
    p = tmp_path / "inv.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    ax.invert_xaxis()
    ax.invert_yaxis()
    assert not ax.xaxis_inverted() and not ax.yaxis_inverted()


def test_axes_artists_transform_and_noops():
    plt.figure()
    ax = plt.gca()
    ax.plot([0, 1], [0, 1])
    mark = object()
    assert ax.add_artist(mark) is mark
    assert ax.add_patch(object()) is not None
    assert ax.add_collection(object()) is not None
    assert ax.add_line(object()) is not None
    assert len(ax.get_children()) >= 5
    assert ax.get_transform().transform([[1.0, 2.0]])[0].tolist() == [1.0, 2.0]
    assert ax.get_transform().inverted() is not None
    assert ax.update() is None and ax.draw() is None
    assert ax.margins(0.1) is None and ax.autoscale() is None
    assert ax.set_clip_on(False) is None and ax.set_path_effects([]) is None


def test_axes_facecolor_alpha_label_zorder():
    plt.figure()
    ax = plt.gca()
    ax.set_facecolor("red")
    assert ax.get_facecolor() == "red"
    ax.set_alpha(0.5)
    assert ax.get_alpha() == 0.5
    ax.set_label("mine")
    assert ax.get_label() == "mine"
    ax.set_zorder(3)
    assert ax.get_zorder() == 3
    assert ax.get_xscale() == "linear" and ax.get_yscale() == "linear"
    ax.set_xscale("log")
    assert ax.get_xscale() == "log"
    ax.set_yscale("log")
    assert ax.get_yscale() == "log"
    ax.set_xscale("linear")
    ax.set_yscale("linear")
    with pytest.raises(NotImplementedError):
        ax.set_xscale("symlog")


def test_axes_clear_empties_the_figure(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.plot([1, 2], [2, 1])
    ax.text(0, 0, "gone")
    ax.clear()
    assert ax.get_xlim() == (0.0, 1.0)
    with pytest.raises(RuntimeError):
        plt.savefig(tmp_path / "empty.png")


def test_figure_introspection_and_add_axes(tmp_path):
    fig = plt.figure((5, 4))
    assert fig.get_size_inches() == (5, 4)
    assert fig.get_dpi() == plt.DPI
    assert fig.draw_without_rendering() is None and fig.draw() is None
    ax = fig.add_axes([0.1, 0.1, 0.8, 0.8])
    assert isinstance(ax, plt.Axes) and fig.get_axes() == [ax]
    assert ax.get_position().bounds == (0.1, 0.1, 0.8, 0.8)
    ax.plot([0, 1], [1, 0])
    fig.set_size_inches(6, 3)
    p = tmp_path / "fa.png"
    fig.savefig(p)
    b = p.read_bytes()
    assert (int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")) == (600, 300)


def test_plot_linestyles_and_width(tmp_path):
    plt.figure((4, 3))
    plt.plot([0, 1, 2], [0, 1, 0], linestyle="--", linewidth=5)
    p = tmp_path / "dash.svg"
    plt.savefig(p)
    s = p.read_text()
    assert 'stroke-width="5"' in s
    assert s.count("<polyline") > 5  # the dash pattern splits the line


def test_plot_markers_and_colors(tmp_path):
    plt.figure((4, 3))
    plt.plot([0, 1], [0, 1], marker="o", markersize=10, markerfacecolor="red")
    plt.plot([0, 1], [1, 0], marker="x", markeredgecolor="blue")
    p = tmp_path / "markers.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert s.count("<CIRCLE") >= 2
    assert "#FF0000" in s and "#0000FF" in s


def test_plot_fmt_string(tmp_path):
    plt.figure()
    plt.plot([0, 1, 2], [2, 1, 0], "g--")
    p = tmp_path / "fmt.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#008000" in s and s.count("<POLYLINE") > 3


def test_plot_alpha_and_bad_drawstyle(tmp_path):
    plt.figure()
    plt.plot([0, 1], [0, 1], alpha=0.3)
    p = tmp_path / "alpha.svg"
    plt.savefig(p)
    assert re.search(r'opacity="0\.[23]', p.read_text())
    with pytest.raises(ValueError):
        plt.plot([0, 1], [0, 1], drawstyle="steps-middle")
    with pytest.raises(TypeError):
        plt.plot([1], [2], [3], [4])


def test_plot_step_drawstyles(tmp_path):
    for style in ("steps-pre", "steps-post"):
        plt.figure()
        plt.plot([0, 1, 2], [0, 2, 1], drawstyle=style)
        p = tmp_path / f"{style}.png"
        plt.savefig(p)
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_plot_legend_still_works_with_markers(tmp_path):
    plt.figure()
    plt.plot([0, 1], [0, 1], label="marked", marker="s", linestyle=":")
    plt.legend()
    p = tmp_path / "legend.svg"
    plt.savefig(p)
    assert "marked" in p.read_text()


def test_pcolormesh_renders_image(tmp_path):
    rng = np.random.default_rng(3)
    x = np.linspace(0, 1, 5)
    y = np.linspace(0, 1, 5)
    z = rng.random((4, 4))
    plt.figure((4, 3))
    plt.pcolormesh(x, y, z, cmap="gray")
    p = tmp_path / "pm.svg"
    plt.savefig(p)
    s = p.read_text()
    assert "<image" in s and "data:image/png;base64," in s
    assert plt.gca().get_aspect() == 1.0
    w, h = _image_box(p)
    assert abs(w / h - 1.0) < 0.1  # square cells keep a square box


def test_pcolormesh_defaults_and_validation(tmp_path):
    plt.figure()
    plt.pcolormesh(np.random.default_rng(1).random((3, 5)))
    plt.savefig(tmp_path / "pm2.png")
    assert (tmp_path / "pm2.png").stat().st_size > 0
    with pytest.raises(ValueError):
        plt.pcolormesh(np.zeros(4))
    with pytest.raises(ValueError):
        plt.pcolormesh(np.arange(3.0), np.arange(3.0), np.zeros((4, 4)))
    with pytest.raises(TypeError):
        plt.pcolormesh()


def test_pcolormesh_centres_and_pcolor_alias(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.pcolormesh(np.arange(3.0), np.arange(2.0), np.zeros((2, 3)), cmap="gray")
    plt.figure()
    plt.pcolor(np.zeros((3, 3)) + 0.5)
    plt.savefig(tmp_path / "pc.png")
    assert (tmp_path / "pc.png").stat().st_size > 0


def test_pcolormesh_vmin_changes_cells(tmp_path):
    z = np.linspace(0, 1, 9).reshape(3, 3)
    uris = []
    for vmin in (0.0, 0.5):
        plt.figure((3, 3))
        plt.pcolormesh(z, vmin=vmin, vmax=1.0, cmap="gray")
        p = tmp_path / f"pm_{vmin}.svg"
        plt.savefig(p)
        uris.append(re.search(r'href="data:image/png;base64,([^"]+)"', p.read_text()).group(1))
    assert uris[0] != uris[1]


def test_bar_renders_rectangles(tmp_path):
    plt.figure((4, 3))
    plt.bar([1, 2, 3], [3, 1, 2], width=0.5, color="red", edgecolor="black")
    p = tmp_path / "bar.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert s.count("<RECT") >= 4  # background plus one per bar
    assert "#FF0000" in s


def test_barh_and_per_bar_colors(tmp_path):
    plt.figure()
    plt.barh([1, 2], [3, 4], height=0.4, color=["red", "green"])
    p = tmp_path / "barh.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_bar_yerr_and_validation(tmp_path):
    plt.figure()
    plt.bar([1, 2], [3, 4], yerr=0.5, capsize=0)
    p = tmp_path / "bar_err.svg"
    plt.savefig(p)
    assert p.read_text().count("<polyline") >= 2
    with pytest.raises(ValueError):
        plt.bar([1, 2], [1, 2], align="middle")
    with pytest.raises(ValueError):
        plt.bar([1, 2], [1, 2, 3])


def test_bar_updates_limits():
    plt.figure()
    ax = plt.gca()
    ax.bar([2], [5], width=2, bottom=1)
    assert ax.get_xlim() == (1.0, 3.0)
    assert ax.get_ylim() == (1.0, 6.0)


def test_fill_between_polygon(tmp_path):
    x = np.linspace(0, 2 * np.pi, 25)
    plt.figure()
    plt.fill_between(x, np.sin(x), 0.5, color="tab:blue", alpha=0.35)
    p = tmp_path / "fb.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert s.count("<POLYGON") >= 1
    assert "#1F77B4" in s
    lo, hi = plt.gca().get_ylim()
    assert lo <= 0.5 and hi >= 1.0
    assert len(re.findall(r'<polygon[^>]*points="', p.read_text())) == 1


def test_fill_between_where_splits_runs(tmp_path):
    x = np.arange(10.0)
    plt.figure()
    plt.fill_between(x, x, 0, where=(x > 2) & (x < 6), color="red")
    p = tmp_path / "fbw.svg"
    plt.savefig(p)
    pts = re.findall(r'<polygon[^>]*points="([^"]+)"', p.read_text())
    assert len(pts) == 1
    assert len(pts[0].split()) == 6  # x = 3, 4, 5 forward, then the three back
    with pytest.raises(ValueError):
        plt.fill_between(x, x, 0, where=np.ones(3, dtype=bool))


def test_fill_and_fill_betweenx(tmp_path):
    plt.figure()
    plt.fill([0, 1, 1, 0], [0, 0, 1, 1], color="green")
    plt.figure()
    plt.fill_betweenx([1, 2, 3], [0, 0.5, 0], 1.5, color="red")
    p = tmp_path / "fills.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(TypeError):
        plt.fill([0, 1], [0, 1], 3)


def test_axhline_vline_spans(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.set_xlim(0, 10)
    ax.set_ylim(-2, 2)
    ax.axhline(1, color="red", linestyle="--")
    ax.axvline(5, color="blue")
    ax.axhspan(-1, 0, color="grey", alpha=0.5)
    ax.axvspan(2, 3, color="pink", alpha=0.4)
    p = tmp_path / "refs.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s and "#0000FF" in s
    assert s.count("<POLYLINE") >= 2
    assert s.count("<RECT") >= 3  # background plus two bands
    # Reference lines and bands never move the data limits.
    assert ax.get_xlim() == (0.0, 10.0)
    assert ax.get_ylim() == (-2.0, 2.0)


def test_hist_counts_and_edges(tmp_path):
    rng = np.random.default_rng(7)
    data = rng.normal(size=200)
    plt.figure()
    counts, edges, handles = plt.hist(data, bins=8, color="#ff7f0e")
    assert counts.sum() == 200
    assert len(edges) == 9 and len(handles) == 8
    assert np.allclose(np.diff(edges), edges[1] - edges[0])
    p = tmp_path / "hist.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert s.count("<RECT") >= 9  # background plus one per bin
    assert "#FF7F0E" in s


def test_hist_orientation_density_and_validation(tmp_path):
    rng = np.random.default_rng(11)
    data = rng.random(100)
    plt.figure()
    counts, edges, _ = plt.hist(data, bins=5, density=True)
    assert np.isclose(counts.sum() * (edges[1] - edges[0]), 1.0)
    plt.figure()
    ax = plt.gca()
    ax.hist(data, bins=4, orientation="horizontal", cumulative=True, color="green")
    p = tmp_path / "histh.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(NotImplementedError):
        plt.hist(data, histtype="barstacked")


def test_bar_label_places_values(tmp_path):
    plt.figure()
    ax = plt.gca()
    bars = ax.bar([1, 2, 3], [3, 1, 2])
    labels = ax.bar_label(bars, padding=3)
    assert labels == ["3", "1", "2"]
    p = tmp_path / "bl.svg"
    plt.savefig(p)
    s = p.read_text()
    for value in ("3", "1", "2"):
        assert re.search(rf">\s*{value}\s*<", s)
    with pytest.raises(ValueError):
        ax.bar_label(bars, labels=["a"])
    with pytest.raises(ValueError):
        ax.bar_label(bars, label_type="middle")


def test_bar_label_centre_and_horizontal(tmp_path):
    plt.figure()
    ax = plt.gca()
    bars = ax.bar([1, 2], [4, 5], color="green")
    assert ax.bar_label(bars, label_type="center", fmt="%.1f") == ["4.0", "5.0"]
    plt.figure()
    ax = plt.gca()
    hbars = ax.barh([1, 2], [7, 8], color="red")
    assert ax.bar_label(hbars, labels=["seven", "eight"]) == ["seven", "eight"]
    p = tmp_path / "bl2.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_bar_handle_facecolor_and_legend(tmp_path):
    plt.figure()
    ax = plt.gca()
    bars = ax.bar([1], [2], label="bars")
    bars[0].set_facecolor("red")
    bars[0].set_alpha(0.5)
    ax.legend()
    p = tmp_path / "bl3.svg"
    plt.savefig(p)
    s = p.read_text()
    assert "#FF0000" in s.upper()
    assert re.search(r">\s*bars\s*<", s)
    assert bars[0].get_height() == 2.0 and bars[0].get_width() == 0.8


def test_step_and_stairs(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.step([0, 1, 2, 3], [1, 2, 0, 3], where="post", color="red")
    ax.step([0, 1, 2, 3], [1, 2, 0, 3], where="mid", label="mid")
    ax.step([0, 1, 2, 3], [1, 2, 0, 3], where="pre", label="pre")
    ax.stairs([1, 2, 1], edges=[0, 1, 2, 3], fill=True, color="green")
    # Every `where` style must register a line (mid is its own polyline).
    assert [line["drawstyle"] for line in ax.lines[:3]] == [
        "steps-post", "steps-post", "steps-pre"]
    p = tmp_path / "step.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert s.count("<POLYGON") >= 1
    with pytest.raises(ValueError):
        ax.step([0, 1], [0, 1], where="sideways")
    with pytest.raises(ValueError):
        ax.stairs([1, 2], edges=[0, 1])


def test_layout_noops_and_in_layout():
    fig = plt.figure()
    ax = plt.gca()
    assert fig.tight_layout() is None
    assert fig.subplots_adjust(left=0.1, right=0.9) is None
    assert plt.tight_layout() is None
    assert ax.tight_layout() is None
    ax.set_in_layout(False)
    assert ax.get_in_layout() is False
    assert ax.get_layout_engine() is None


def test_hlines_vlines(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.hlines([1, 2], 0, 3, colors=["red", "blue"], linestyles=["--", ":"])
    ax.vlines([0.5, 1.5], 0, 3, colors="green")
    p = tmp_path / "hl.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s and "#0000FF" in s and "#008000" in s
    assert s.count("<POLYLINE") >= 3
    lo, hi = ax.get_xlim()
    assert lo <= 0.0 and hi >= 3.0
    with pytest.raises(ValueError):
        ax.hlines([1, 2], 0, 3, colors=["red"])
    with pytest.raises(ValueError):
        ax.vlines([1], 0, 1, linestyles=["-", "--"])


def test_log_scales(tmp_path):
    x = np.logspace(0, 3, 20)
    plt.figure()
    ax = plt.gca()
    ax.semilogy(x, x ** 2, color="red")
    assert ax.get_yscale() == "log" and ax.get_xscale() == "linear"
    p = tmp_path / "log.svg"
    plt.savefig(p)
    s = p.read_text()
    assert "#FF0000" in s.upper()
    assert re.search(r">\s*10\s*<", s), "decade tick label missing"
    plt.figure()
    ax = plt.gca()
    ax.loglog(x, 1.0 / x, base=10)
    assert ax.get_xscale() == "log" and ax.get_yscale() == "log"
    q = tmp_path / "log2.svg"
    plt.savefig(q)
    assert re.search(r">\s*0\.1\s*<", q.read_text())
    plt.figure()
    plt.semilogx(x, x)
    plt.xscale("log")
    assert plt.gca().get_xscale() == "log"
    with pytest.raises(NotImplementedError):
        ax.set_xscale("symlog")
    ax.set_yscale("linear")
    assert ax.get_yscale() == "linear"


def test_log_scale_ignores_non_positive(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.set_yscale("log")
    ax.plot([0, 1, 2, 3], [0, 1, 10, 100])
    lo, hi = ax.get_ylim()
    assert lo > 0 and hi >= 100
    p = tmp_path / "logn.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_grid_draws_and_toggles(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.plot([0, 1], [0, 1])
    plain = tmp_path / "nogrid.svg"
    plt.savefig(plain)
    ax.grid(True)
    with_grid = tmp_path / "grid.svg"
    plt.savefig(with_grid)
    assert len(with_grid.read_text()) > len(plain.read_text())
    assert ax.show_grid is True
    ax.grid()
    assert ax.show_grid is False
    plt.grid(True)
    assert plt.gca().show_grid is True


def test_tick_params_and_axline(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 4)
    assert ax.tick_params(axis="x", labelsize=8, color="red") is None
    assert ax.tick_params_box["labelsize"] == 8
    ax.axline((0, 0), slope=1, color="green")
    ax.axline((2, 0), (2, 3), color="blue")
    p = tmp_path / "axline.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#008000" in s and "#0000FF" in s
    # axline never moves the data limits
    assert ax.get_xlim() == (0.0, 4.0) and ax.get_ylim() == (0.0, 4.0)
    with pytest.raises(ValueError):
        ax.axline((0, 0))
    with pytest.raises(ValueError):
        ax.axline((0, 0), (1, 1), slope=2)


def test_rc_shims():
    plt.rc("lines", linewidth=4)
    assert plt.rcParams["lines.linewidth"] == 4
    with plt.rc_context({"lines.linewidth": 9}):
        assert plt.rcParams["lines.linewidth"] == 9
    assert plt.rcParams["lines.linewidth"] == 4
    assert plt.rc({"figure.dpi": 72}) is None
    assert plt.rcParams["figure.dpi"] == 72
    fig = plt.figure((2, 1))
    fig.gca().plot([0, 1], [0, 1])
    assert fig.get_dpi() == 72
    png = fig.savefig(format="png")
    assert int.from_bytes(png[16:20], "big") == 144
    plt.rcdefaults()
    assert plt.rcParams["lines.linewidth"] == 1.5
    assert plt.rcParams["figure.dpi"] == 100.0


def test_stem_plot(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.stem([1, 3, 2], linefmt="r-", markerfmt="bo", basefmt="-")
    p = tmp_path / "stem.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s and "#0000FF" in s
    assert s.count("<CIRCLE") >= 3
    with pytest.raises(ValueError):
        ax.stem([1, 2], [1])
    ax.stem([1], [2], orientation="horizontal")
    with pytest.raises(ValueError):
        ax.stem([1], orientation="sideways")
    with pytest.raises(TypeError):
        ax.stem([1], [2], [3])


def test_pie_wedges_labels(tmp_path):
    plt.figure()
    ax = plt.gca()
    wedges, texts, autotexts = ax.pie([3, 1, 1], labels=["a", "b", "c"],
                                      autopct="%1.0f%%",
                                      colors=["red", "green", "blue"])
    assert len(wedges) == 3 and len(texts) == 3 and len(autotexts) == 3
    assert autotexts[0].get_text() == "60%"
    assert texts[1].get_text() == "b"
    p = tmp_path / "pie.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s and "#008000" in s
    assert s.count("<POLYGON") >= 3
    assert ax.get_xlim() == (-1.25, 1.25)
    with pytest.raises(ValueError):
        ax.pie([1, -1])
    with pytest.raises(ValueError):
        ax.pie([0, 0])


def test_pyplot_stem_pie_stackplot_and_bar_label(tmp_path):
    plt.figure()
    wedges, texts, autotexts = plt.pie([2, 1], labels=["a", "b"], autopct="%1.0f%%")
    assert len(wedges) == len(texts) == len(autotexts) == 2
    pie = tmp_path / "pyplot-pie.svg"
    plt.savefig(pie)
    assert pie.read_text().count("<polygon") >= 2

    plt.figure()
    plt.stem([1, 3, 2], linefmt="r-")

    plt.figure()
    plt.stackplot(np.arange(3.0), [1, 1, 1], [2, 2, 2])

    plt.figure()
    bars = plt.bar([1, 2], [3, 4])
    assert plt.bar_label(bars) == ["3", "4"]

    p = tmp_path / "pyplot-shims.svg"
    plt.savefig(p)
    assert p.read_text().count("<rect") >= 3


def test_stackplot_layers(tmp_path):
    x = np.arange(4.0)
    plt.figure()
    ax = plt.gca()
    ax.stackplot(x, [1, 1, 1, 1], [1, 2, 1, 2], colors=["red", "green"])
    p = tmp_path / "stack.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s and "#008000" in s
    assert s.count("<POLYGON") >= 2
    ax.stackplot(x, [1, 1, 1, 1], baseline="sym")
    with pytest.raises(NotImplementedError):
        ax.stackplot(x, [1, 1, 1, 1], baseline="wiggle")
    with pytest.raises(ValueError):
        ax.stackplot(x, [1, 2])


def test_eventplot_and_broken_barh(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.eventplot([[0.5, 1.5], [1.0]], colors=["red", "green"], linelengths=0.8)
    ax.broken_barh([(0, 1), (2, 0.5)], (2, 0.5), colors="blue")
    p = tmp_path / "events.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s and "#008000" in s and "#0000FF" in s
    assert s.count("<POLYLINE") >= 3
    assert s.count("<RECT") >= 3  # background plus two bars
    lo, hi = ax.get_ylim()
    assert lo <= 0.5 and hi >= 2.5
    with pytest.raises(ValueError):
        ax.eventplot([[1]], orientation="diagonal")


def test_minorticks_setp_getp():
    plt.figure()
    ax = plt.gca()
    ax.minorticks_on()
    assert ax.minor_ticks is True
    ax.minorticks_off()
    assert ax.minor_ticks is False
    bars = ax.bar([1], [2])
    assert plt.getp(bars[0], "height") == 2.0
    assert plt.setp(bars[0], height=3.0) is None
    assert plt.getp(bars[0], "height") == 3.0
    plt.setp(bars[0], facecolor="red")
    assert plt.getp(bars[0], "facecolor") == ["red"]
    assert plt.getp(bars[0], "height", "width") == [3.0, 0.8]
    with pytest.raises(AttributeError):
        plt.getp(bars[0], "nonsense")
    with pytest.raises(AttributeError):
        plt.setp(bars[0], nonsense=1)


def test_log_base_two(tmp_path):
    x = np.array([1.0, 2.0, 4.0, 8.0])
    plt.figure()
    ax = plt.gca()
    ax.set_xscale("log", base=2)
    ax.plot(x, [2, 4, 8, 16])
    p = tmp_path / "logbase.svg"
    plt.savefig(p)
    assert re.search(r">\s*(2|4|8)\s*<", p.read_text())


def test_scatter_and_fill_legend(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.scatter([1, 2], [2, 1], label="dots")
    ax.fill_between([1, 2, 3], [1, 1, 1], 0, label="band")
    ax.legend()
    p = tmp_path / "legend.svg"
    plt.savefig(p)
    s = p.read_text()
    assert re.search(r">\s*dots\s*<", s) and re.search(r">\s*band\s*<", s)


def test_errorbar_markers_and_stem_horizontal(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.errorbar([1, 2], [1, 2], yerr=0.2, fmt="ro")
    ax.stem([1, 2], [3, 4], orientation="horizontal")
    p = tmp_path / "em.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert s.count("<CIRCLE") >= 4  # two errorbar markers plus two stem markers
    with pytest.raises(ValueError):
        ax.stem([1], orientation="diagonal")


def test_line_widths_and_broken_barh_style(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.hlines([1], 0, 2, linewidths=4, colors="red")
    ax.eventplot([[1]], linewidths=5, colors="green")
    ax.broken_barh([(0, 1)], (2, 1), colors="blue", edgecolor="red", alpha=0.5)
    p = tmp_path / "lw.svg"
    plt.savefig(p)
    s = p.read_text()
    assert 'stroke-width="4"' in s and 'stroke-width="5"' in s


def test_hist_step_and_bottom(tmp_path):
    plt.figure()
    ax = plt.gca()
    counts, edges, _ = ax.hist(np.arange(20.0), bins=5, histtype="stepfilled",
                               color="red")
    assert counts.sum() == 20 and len(edges) == 6
    filled = tmp_path / "hfilled.svg"
    plt.savefig(filled)
    assert "<POLYGON" in filled.read_text().upper()
    plt.figure()
    ax = plt.gca()
    ax.hist(np.arange(20.0), bins=5, histtype="step", color="green", bottom=2)
    stepped = tmp_path / "hstep.svg"
    plt.savefig(stepped)
    assert "<POLYLINE" in stepped.read_text().upper()
    assert "#008000" in stepped.read_text().upper()
    plt.figure()
    ax = plt.gca()
    ax.hist(np.arange(5.0), bins=5, bottom=1.0)
    bottomed = tmp_path / "hbottom.svg"
    plt.savefig(bottomed)
    assert "<RECT" in bottomed.read_text().upper()  # bars are rectangles
    lo, _ = ax.get_ylim()
    assert 0.5 < lo < 1.5  # bars offset by bottom=1.0


def test_stackplot_sym_baseline(tmp_path):
    x = np.arange(3.0)
    plt.figure()
    ax = plt.gca()
    ax.stackplot(x, [1, 1, 1], [2, 2, 2], colors=["red", "green"], baseline="sym")
    lo, hi = ax.get_ylim()
    assert lo < 0 < hi
    p = tmp_path / "sym.svg"
    plt.savefig(p)
    assert "<POLYGON" in p.read_text().upper()
    with pytest.raises(NotImplementedError):
        ax.stackplot(x, [1, 1, 1], baseline="wiggle")


def test_css_colors_and_color_specs(tmp_path):
    from plt_rs import _norm_color

    assert _norm_color("rebeccapurple") == "#663399"
    assert _norm_color("r") == "#ff0000"
    assert _norm_color("#ABC") == "#aabbcc"
    assert _norm_color((1, 0, 0)) == "#ff0000"
    assert _norm_color((0, 0, 0, 0.5)) == "#00000080"
    assert _norm_color("0.5") == "#808080"
    assert _norm_color("none") == "none"
    with pytest.raises(ValueError):
        _norm_color((1, 2, 3))
    with pytest.raises(ValueError):
        _norm_color("#gggggg")
    with pytest.raises(ValueError):
        _norm_color("not-a-colour")
    plt.figure((4, 3))
    plt.plot([0, 1], [0, 1], color="rebeccapurple")
    p = tmp_path / "css.svg"
    plt.savefig(p)
    assert "#663399" in p.read_text().upper()


def test_rgb_tuples_work_across_artists(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1], color=(1, 0, 0))
    ax.bar([0], [1], color=(0, 0, 1))
    ax.scatter([0], [1], c=(0, 1, 0))
    p = tmp_path / "tuples.svg"
    fig.savefig(p)
    svg = p.read_text().upper()
    assert "#FF0000" in svg and "#0000FF" in svg and "#00FF00" in svg

    with pytest.raises(ValueError):
        ax.plot([0, 1], [0, 1], color="not-a-colour")
    with pytest.raises(ValueError):
        plt.figure(facecolor="#gggggg")


def test_non_finite_data_gets_finite_limits(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0.0, np.nan, 1.0], [0.0, np.inf, 1.0])
    assert all(np.isfinite(v) for v in (*ax.get_xlim(), *ax.get_ylim()))
    p = tmp_path / "nan.png"
    fig.savefig(p)
    assert p.stat().st_size > 0


def test_xticks_labels_rotation_and_tick_params(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1, 2], [0, 1, 0])
    ax.set_xticks([0, 1, 2], ["a", "b", "c"], rotation=90, fontsize=8, color="red")
    ax.set_yticks([0, 1], ["lo", "hi"])
    ax.tick_params(axis="y", labelsize=9, color="blue")
    assert ax.get_xticks().tolist() == [0.0, 1.0, 2.0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["a", "b", "c"]
    panel = ax._panel()
    assert panel["ticks"]["xstyle"]["rotation"] == 90.0
    assert panel["ticks"]["xstyle"]["labelsize"] == 8.0
    assert panel["ticks"]["ystyle"]["labelsize"] == 9.0
    assert panel["ticks"]["ystyle"]["color"] == "#0000ff"
    assert panel["ticks"]["ystyle"]["labelcolor"] == "#0000ff"
    p = tmp_path / "ticks.svg"
    fig.savefig(p)
    s = p.read_text().upper()
    assert re.search(r">\s*A\s*<", s) and re.search(r">\s*LO\s*<", s)
    assert "#FF0000" in s


def test_grid_style_and_axis(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    ax.grid(True, color="red", linewidth=2, alpha=0.3, linestyle="--", axis="x")
    panel = ax._panel()["grid"]
    assert panel["show"] and panel["axis"] == "x"
    assert panel["linestyle"] == "--"
    p = tmp_path / "grid.svg"
    fig.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s
    assert "<POLYLINE" in s  # dashed manual gridlines


def test_custom_legend_layout(tmp_path):
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot([0, 1], [0, 1], label="one")
    ax.plot([0, 1], [1, 0], label="two")
    ax.plot([0, 1], [0.5, 0.5], label="three")
    ax.legend(ncol=2, title="key", loc="upper left", frameon=False, fontsize=9)
    p = tmp_path / "legend.svg"
    fig.savefig(p)
    s = p.read_text()
    assert re.search(r">\s*key\s*<", s) and re.search(r">\s*one\s*<", s)
    assert re.search(r">\s*three\s*<", s)
    assert s.upper().count("<POLYLINE") >= 3


def test_text_transforms_resolve(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.text(0.5, 0.5, "mid", transform=ax.transAxes, ha="center", va="center")
    x, y = ax._panel()["texts"][0][:2]
    assert x == pytest.approx(5.0) and y == pytest.approx(5.0)
    p = tmp_path / "text.svg"
    fig.savefig(p)
    assert re.search(r">\s*mid\s*<", p.read_text())


def test_title_fontsize(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    ax.set_title("Big", fontsize=20)
    ax.set_xlabel("xx", fontsize=14)
    panel = ax._panel()
    assert panel["title_size"] == 20.0 and panel["xlabel_size"] == 14.0
    p = tmp_path / "font.svg"
    fig.savefig(p)
    sizes = [float(v) for v in re.findall(r'font-size="([\d.]+)"', p.read_text())]
    assert max(sizes) > 16  # title is the largest text
    assert any(10.5 < v < 12 for v in sizes)  # xlabel at 14pt


def test_subplots_share_limits_and_hide_inner_labels(tmp_path):
    fig, axs = plt.subplots(2, 2, figsize=(4, 4), sharex=True, sharey=True)
    axs[0, 0].plot([0, 10], [0, 10])
    axs[1, 1].plot([5, 6], [50, 60])
    assert axs[0, 1].get_xlim() == axs[1, 1].get_xlim()
    assert axs[0, 0].get_ylim() == axs[1, 1].get_ylim()
    axs[1, 0].set_xlim(0, 20)
    assert axs[0, 1].get_xlim() == (0.0, 20.0)
    assert axs[0, 0].hide_xticklabels and axs[0, 1].hide_xticklabels
    assert axs[0, 1].hide_yticklabels and axs[1, 1].hide_yticklabels
    assert not axs[1, 1].hide_xticklabels and not axs[0, 0].hide_yticklabels
    p = tmp_path / "shared.png"
    fig.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_subplots_squeeze_false_keeps_array():
    fig, axs = plt.subplots(1, 1, squeeze=False)
    assert axs.shape == (1, 1)
    assert axs[0, 0].get_figure() is fig


def test_window_extent_accounts_for_labels_and_title():
    fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
    ax.plot([0, 1], [0, 1])
    bare = ax.get_window_extent()
    ax.set_ylabel("values")
    ax.set_xlabel("time")
    labelled = ax.get_window_extent()
    assert labelled.x0 < bare.x0 and labelled.y0 < bare.y0
    ax.set_title("A title", fontsize=20)
    titled = ax.get_window_extent()
    assert titled.y1 > labelled.y1
    assert titled.width >= labelled.width
    ax.axis("off")
    bare_axes = ax.get_window_extent()
    assert bare_axes.width < titled.width and bare_axes.height < titled.height


def test_gridspec_spans_multiple_cells(tmp_path):
    fig = plt.figure((5, 4))
    gs = fig.add_gridspec(2, 3)
    top = fig.add_subplot(gs[0, :])
    left = fig.add_subplot(gs[1, 0])
    right = fig.add_subplot(gs[1, 1:])
    top.plot([0, 1], [0, 1])
    left.bar([0, 1], [2, 3])
    right.scatter([0, 1], [1, 0])
    assert isinstance(gs, plt.GridSpec) and gs.get_geometry() == (2, 3)
    btop, bleft, bright = (ax._panel()["bounds"] for ax in (top, left, right))
    assert btop[2] > bleft[2] * 2
    assert bright[0] > bleft[0]
    assert top.get_position().width > left.get_position().width
    p = tmp_path / "gridspec.png"
    fig.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_subplot_mosaic_labels_and_empty_cells(tmp_path):
    fig, axes = plt.subplot_mosaic([["left", "right"], ["left", "bottom"]], figsize=(4, 4))
    assert set(axes) == {"left", "right", "bottom"}
    assert axes["left"].get_position().height > axes["right"].get_position().height
    axes["left"].plot([0, 1], [0, 1])
    axes["right"].plot([0, 1], [1, 0])
    p = tmp_path / "mosaic.svg"
    fig.savefig(p)
    assert p.read_text().startswith("<svg")
    fig2, only = plt.subplot_mosaic([[".", "a"]])
    assert list(only) == ["a"]
    assert fig2 is plt.gcf()


def test_pyplot_subplot_accepts_subplotspec():
    fig = plt.figure()
    gs = fig.add_gridspec(1, 2)
    ax = plt.subplot(gs[0, 1])
    assert ax.get_figure() is fig
    assert ax.get_position().x0 > 0.4


def test_twinx_adds_right_axis_on_the_same_panel(tmp_path):
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 1, 2], [1, 4, 9], color="red")
    ax.set_ylabel("left")
    original = ax.get_position().bounds
    twin = ax.twinx()
    twin.plot([0, 1, 2], [100, 50, 10], color="blue")
    twin.set_ylabel("right")
    assert twin._twin_of is ax and twin._twin == "y"
    assert twin.get_xlim() == ax.get_xlim()
    assert ax.get_position().x1 < original[0] + original[2]
    assert twin.get_position().bounds == original
    assert ax._panel()["bounds"] is not None and twin._panel()["bounds"] is not None
    assert twin._panel()["ticks"]["hide_xlabels"]
    p = tmp_path / "twinx.svg"
    fig.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s and "#0000FF" in s
    assert "right" in p.read_text()


def test_twiny_adds_top_axis_on_the_same_panel(tmp_path):
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 1, 2], [10, 20, 30])
    twin = ax.twiny()
    twin.plot([100, 200, 300], [0, 1, 2], color="green")
    twin.set_xlabel("top")
    assert twin._twin == "x" and twin.get_ylim() == ax.get_ylim()
    assert twin._panel()["ticks"]["hide_ylabels"]
    p = tmp_path / "twiny.png"
    fig.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_set_prop_cycle_controls_default_colors(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.set_prop_cycle(color=["red", "green"])
    ax.plot([0, 1], [0, 1])
    ax.plot([0, 1], [1, 0])
    assert ax.lines[0]["color"] == "#ff0000"
    assert ax.lines[1]["color"] == "#008000"
    ax.scatter([0.5], [0.5])
    assert ax.scatter_pts[0]["colors"] == ["#ff0000"]  # the cycle wraps
    assert ax.get_prop_cycle().by_key()["color"] == ["#ff0000", "#008000"]
    ax.set_prop_cycle(["blue"])
    assert ax.get_prop_cycle().by_key() == {"color": ["#0000ff"]}
    ax.bar([0], [1])
    assert ax.bars[-1]["colors"] == ["#0000ff"]
    p = tmp_path / "cycle.svg"
    fig.savefig(p)
    assert "#FF0000" in p.read_text().upper()
    assert "#008000" in p.read_text().upper()
    with pytest.raises(ValueError):
        ax.set_prop_cycle()


def test_style_presets_and_context(tmp_path):
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    svg = fig.savefig(None, format="svg").decode().lower()
    assert "#000000" in svg and "#dddddd" in svg
    assert plt.rcParams["axes.facecolor"] == "#000000"
    with plt.style.context("ggplot"):
        assert plt.rcParams["axes.facecolor"] == "#e5e5e5"
        assert plt.rcParams["text.color"] == "#555555"
    assert plt.rcParams["axes.facecolor"] == "#000000"
    plt.style.use(["ggplot", {"lines.linewidth": 3}])
    assert plt.rcParams["lines.linewidth"] == 3
    assert "seaborn-v0_8" in plt.style.available
    with pytest.raises(ValueError):
        plt.style.use("missing")
    plt.rcdefaults()


def test_suptitle_renders_above_the_grid(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    fig.suptitle("Figure title", fontsize=16)
    p = tmp_path / "suptitle.svg"
    fig.savefig(p)
    assert re.search(r">\s*Figure title\s*<", p.read_text())
    assert fig.savefig(None, format="png")[:8] == b"\x89PNG\r\n\x1a\n"
    plt.suptitle("pyplot title")
    assert plt.gcf()._suptitle["text"] == "pyplot title"


def test_figure_and_savefig_colors_and_bytes(tmp_path):
    import io

    fig = plt.figure((4, 3), dpi=72, facecolor="red", edgecolor="blue")
    fig.gca().plot([0, 1], [0, 1])
    p = tmp_path / "bg.svg"
    fig.savefig(p)
    s = p.read_text().upper()
    assert 'FILL="#FF0000"' in s
    assert 'STROKE="#0000FF"' in s
    data = fig.savefig(None, format="png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    buf = io.BytesIO()
    fig.savefig(buf, format="svg")
    assert buf.getvalue().startswith(b"<svg")
