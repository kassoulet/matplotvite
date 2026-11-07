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
    assert "#D62728" in s and "#1F77B4" in s


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
    assert "#D62728" in s.upper()


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
    ax.set_xscale("linear")
    with pytest.raises(NotImplementedError):
        ax.set_xscale("log")
    with pytest.raises(NotImplementedError):
        ax.set_yscale("log")


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
    assert "#D62728" in s and "#1F77B4" in s


def test_plot_fmt_string(tmp_path):
    plt.figure()
    plt.plot([0, 1, 2], [2, 1, 0], "g--")
    p = tmp_path / "fmt.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert "#2CA02C" in s and s.count("<POLYLINE") > 3


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
