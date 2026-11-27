"""Axes decoration: text, labels, ticks, grid, legend and scales."""

import datetime
import re

import matplotvite as plt
import numpy as np
import pytest
from plt_helpers import (
    _bump,
    _over_white,
)
from png_utils import decode_png_rgba


def test_grid_defaults_and_unicode_minus(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([-1, 1], [-1, 1])
    ax.grid(True)
    assert ax.grid_color == "#b0b0b0"
    assert ax.grid_linewidth == pytest.approx(0.8)
    ax.set_xticks([-1, 0, 1])
    svg = fig.savefig(None, format="svg").decode()
    assert "−1" in svg
    # Named first so viewers rasterise the minus sign with the embedded face
    # instead of a generic fallback that may not contain U+2212.
    assert 'font-family="DejaVu Sans, sans-serif"' in svg


def test_subplots_grid(tmp_path):
    fig, axs = plt.subplots(2, 2, figsize=(4, 4))
    assert axs.shape == (2, 2)
    axs[0, 0].plot([1, 2, 3]); axs[1, 1].plot([3, 2, 1], label="b")
    axs[1, 1].legend(); axs[0, 1].set_title("empty"); axs[0, 0].set_xlim(0, 5)
    for ext in ("png", "svg"):
        fig.savefig(tmp_path / f"g.{ext}")
        assert (tmp_path / f"g.{ext}").stat().st_size > 0


def test_text_annotations(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.text(0.5, 0.5, "hi there", color="red", fontsize=14)
    plt.text(0.1, 0.9, "second", ha="center", va="top")
    svg = tmp_path / "t.svg"
    fig.savefig(svg)
    s = svg.read_text(encoding="utf-8")
    assert "hi there" in s and "second" in s
    fig.savefig(tmp_path / "t.png")
    assert (tmp_path / "t.png").stat().st_size > 0

    with pytest.raises(ValueError):
        ax.text(0, 0, "x", ha="middle")
    with pytest.raises(ValueError):
        ax.text(0, 0, "x", va="middle")


def test_text_newline_draws_separate_lines(tmp_path):
    plt.figure((4, 3))
    plt.text(0.1, 0.5, "first\nsecond\n  indented\n\ttabbed")
    p = tmp_path / "multiline.svg"
    plt.savefig(p)
    svg = p.read_text(encoding="utf-8")
    ys = {}
    for name in ("first", "second"):
        match = re.search(rf'<text x="-?\d+" y="(\d+)"[^>]*>\s*{name}', svg)
        assert match is not None
        ys[name] = int(match.group(1))
    delta = abs(ys["second"] - ys["first"])
    assert 15 <= delta <= 18  # 10 pt at 100 dpi with 1.2 line spacing
    assert "\u00a0\u00a0indented" in svg
    assert "\u00a0\u00a0\u00a0\u00a0tabbed" in svg


def test_annotate_arrow(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.annotate("peak", xy=(0.5, 0.5), xytext=(0.2, 0.8))
    plt.annotate("plain", xy=(0.1, 0.1))
    p = tmp_path / "ann.svg"
    fig.savefig(p)
    s = p.read_text(encoding="utf-8")
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
          for m in re.finditer(r'<text x="(-?\d+)"[^>]*>\s*(\w)', p.read_text(encoding="utf-8"))}
    assert 0 < xs["L"] < 400 < xs["R"] < 800


def test_text_only_figure(tmp_path):
    plt.figure()
    plt.text(0.5, 0.5, "lonely")
    plt.savefig(tmp_path / "only.svg")
    assert "lonely" in (tmp_path / "only.svg").read_text(encoding="utf-8")


def test_grid_dimensions_are_capped():
    fig = plt.figure()
    with pytest.raises(ValueError, match="too many cells"):
        fig.subplots(200, 200)
    with pytest.raises(ValueError, match="too many cells"):
        fig.subfigures(200, 200)
    with pytest.raises(ValueError, match="too many cells"):
        fig.add_gridspec(200, 200)
    with pytest.raises(ValueError, match="too many cells"):
        fig.add_subplot(200, 200, 1)
    with pytest.raises(ValueError, match="too many cells"):
        fig.subfigures().subplots(200, 200)


def test_clabel_manual_positions(tmp_path):
    x, y, z = _bump()
    plt.figure()
    cs = plt.contour(x, y, z, levels=[0.2, 0.6])
    texts = cs.clabel(fontsize=8, manual=[(-0.5, -0.5), (0.5, 0.5)])
    assert len(texts) == 2
    p = tmp_path / "manual_clabel.svg"
    plt.savefig(p)
    assert "</svg>" in p.read_text(encoding="utf-8")


def test_legend_follows_creation_order_with_bar_containers_last(tmp_path):
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar([0, 1], [1, 2], label="bars")
    ax.fill_between([0, 1], [1, 2], label="band")
    ax.plot([0, 1], [2, 1], label="line", marker="+")
    ax.scatter([0, 1], [1, 2], label="dots")
    ax.add_patch(plt.Rectangle((0, 0), 0.1, 0.1, label="patch"))
    ax.hist([0.1, 0.2], bins=1, label="hist")
    ax.legend()
    p = tmp_path / "legend_order.svg"
    fig.savefig(p)
    s = p.read_text(encoding="utf-8")
    order = [re.search(rf">\s*{name}\s*<", s).start()
             for name in ("band", "line", "dots", "patch", "hist", "bars")]
    assert order == sorted(order)


def test_legend_frame_radius_scales_with_font_size(tmp_path):
    radii = []
    for fontsize in (8, 20):
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.plot([0, 1], [0, 1], label="a")
        ax.legend(fontsize=fontsize)
        p = tmp_path / f"legend_{fontsize}.svg"
        fig.savefig(p)
        match = re.search(r'<polygon opacity="0.8" fill="#FFFFFF" points="([^"]+)"',
                          p.read_text(encoding="utf-8"))
        assert match is not None
        points = [tuple(float(v) for v in pair.split(","))
                  for pair in match.group(1).split()]
        radii.append(points[0][1] - min(y for _, y in points))
    assert radii[0] > 0 and radii[1] > radii[0]


def test_equal_aspect_draws_title_once(tmp_path):
    plt.figure((4, 3))
    plt.imshow(np.arange(12.0).reshape(3, 4))
    plt.title("Aspect title")
    p = tmp_path / "aspect_title.svg"
    plt.savefig(p)
    assert p.read_text(encoding="utf-8").count("Aspect title") == 1


def test_auto_ticks_use_the_rust_locator():
    fig, ax = plt.subplots()
    ax.set_xlim(11.2, 28.8)
    assert np.allclose(ax.get_xticks(), np.arange(12.0, 29.0, 2.0))
    ax.set_xscale("log")
    ax.set_xlim(1.0, 1000.0)
    assert np.allclose(ax.get_xticks(), [1.0, 10.0, 100.0, 1000.0])
    ax.set_xscale("log", base=2)
    ax.set_xlim(1.0, 8.0)
    assert np.allclose(ax.get_xticks(), [1.0, 2.0, 4.0, 8.0])


def test_set_aspect_tracks_adjustable():
    plt.figure((4, 3))
    ax = plt.gca()
    assert ax.get_adjustable() == "box"
    ax.axis("equal")
    assert ax.get_aspect() == 1.0 and ax.get_adjustable() == "datalim"
    ax.set_aspect("equal", adjustable="box")
    assert ax.get_adjustable() == "box"
    ax.set_aspect("auto")
    assert ax.get_aspect() is None and ax.get_adjustable() == "box"
    ax.axis("scaled")
    assert ax.get_aspect() == 1.0 and ax.get_adjustable() == "box"
    with pytest.raises(ValueError):
        ax.set_aspect("equal", adjustable="nonsense")


def test_major_locators_place_ticks(tmp_path):
    plt.rcdefaults()
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], [0.0, 3500.0])
    ax.xaxis.set_major_locator(plt.MultipleLocator(0.25))
    assert list(ax.get_xticks()) == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])
    ticks = ax._panel()["ticks"]
    assert ticks["xticks"] == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])
    ax.yaxis.set_major_locator(plt.MaxNLocator(8))
    yticks = ax._panel()["ticks"]["yticks"]
    # 0 to 3500 in 500s, as Matplotlib's AutoLocator chooses for this span.
    assert yticks == pytest.approx([0.0, 500.0, 1000.0, 1500.0, 2000.0,
                                    2500.0, 3000.0, 3500.0])
    p = tmp_path / "locators.svg"
    plt.savefig(p)
    text = p.read_text(encoding="utf-8")
    assert "0.25" in text and "3500" in text
    # The locator wins over a tick list set before it, as in Matplotlib.
    ax.set_xticks([0.5])
    ax.xaxis.set_major_locator(plt.FixedLocator([0.0, 1.0]))
    assert list(ax.get_xticks()) == [0.0, 1.0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["0", "1"]


def test_axis_major_formatter_decides_the_tick_text(tmp_path):
    plt.rcdefaults()
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0, 1, 4])
    ax.set_xticks([0, 1, 2])
    ax.xaxis.set_major_formatter(plt.FixedFormatter(["a", "b", "c"]))
    assert ax._panel()["ticks"]["xticklabels"] == ["a", "b", "c"]
    p = tmp_path / "formatter.svg"
    plt.savefig(p)
    text = p.read_text(encoding="utf-8")
    assert re.findall(r">\s*([abc])\s*<", text) == ["a", "b", "c"]
    # `Axis.set` forwards locator and formatter keywords.
    ax.yaxis.set(major_locator=plt.MultipleLocator(2), label="V")
    assert ax._panel()["ticks"]["yticks"] == pytest.approx([0.0, 2.0, 4.0])


def test_date_formatter_and_locator(tmp_path):

    plt.rcdefaults()
    fig, ax = plt.subplots()
    days = [datetime.date(2021, 1, 1) + datetime.timedelta(days=60 * i) for i in range(6)]
    ax.plot(days, range(6))
    ax.xaxis.set(major_locator=plt.dates.AutoDateLocator(),
                 major_formatter=plt.dates.DateFormatter("%Y-%m"))
    labels = ax._panel()["ticks"]["xticklabels"]
    assert labels and all(len(label) == 7 and label[4] == "-" for label in labels)
    assert plt.dates.date2num(datetime.date(2021, 1, 1)) == pytest.approx(737791.0)
    assert plt.dates.num2date(737791.0).date() == datetime.date(2021, 1, 1)


def test_linear_locator_spreads_ticks_over_the_limits():
    plt.rcdefaults()
    fig, ax = plt.subplots()
    ax.plot([0, 10], [0, 1])
    ax.yaxis.set_major_locator(plt.LinearLocator(3))
    lo, hi = ax.get_ylim()
    assert list(ax.get_yticks()) == pytest.approx([lo, (lo + hi) / 2, hi])
    assert len(ax._panel()["ticks"]["yticks"]) == 3


def test_axes_table_builds_cells_and_renders(tmp_path):
    plt.rcdefaults()
    fig, ax = plt.subplots()
    table = ax.table(cellText=[["a", "b"]], rowLabels=["r"],
                     colLabels=["x", "y"], loc="upper left")
    cells = table.get_celld()
    assert cells[(0, 0)].get_text() == "a" and cells[(0, 1)].get_text() == "b"
    assert cells[(0, -1)].get_text() == "r" and cells[(-1, 0)].get_text() == "x"
    cells[(0, 0)].set_text_props(color="red")
    assert plt.table(cellText=[["c"]]) is not None
    out = tmp_path / "table.png"
    fig.savefig(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


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
    a, b = plain.read_text(encoding="utf-8"), off.read_text(encoding="utf-8")
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
    assert p.read_text(encoding="utf-8").startswith("<svg")


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
    ax.set_xscale("symlog", linthresh=0.5)
    assert ax.get_xscale() == "symlog"
    assert ax.symlog_linthresh_x == 0.5
    ax.set_xscale("linear")


def test_axes_hit_testing_and_cursor_formatting():
    from types import SimpleNamespace

    fig, ax = plt.subplots()
    box = ax.get_position()
    width, height = fig.get_size_inches()
    dpi = fig.get_dpi()
    center = ((box.x0 + box.x1) / 2 * width * dpi,
              (box.y0 + box.y1) / 2 * height * dpi)
    assert ax.contains_point(center)
    assert not ax.contains_point((-1.0, -1.0))
    assert ax.contains(SimpleNamespace(x=center[0], y=center[1])) == (True, {})
    assert ax.contains() == (False, {})
    assert ax.get_cursor_data(None) is None
    assert ax.format_cursor_data(3.14159) == "[3.14]"
    assert ax.format_cursor_data(None) == "[]"
    assert ax.format_coord(1.5, 2.0) == "(x, y) = (1.5, 2)"


def test_axes_margins_and_gridline_handles():
    fig, ax = plt.subplots()
    ax.plot([1, 2], [3, 4])
    assert ax.get_xmargin() == pytest.approx(0.05)
    assert ax.get_ymargin() == pytest.approx(0.05)
    assert ax.margins(0.2, 0.3) == (0.2, 0.3)
    assert ax.get_xlim() == pytest.approx((0.8, 2.2))
    assert ax.get_ylim() == pytest.approx((2.7, 4.3))
    assert ax.margins() == (0.2, 0.3)
    ax.set_xmargin(0.1)
    ax.set_ymargin(0.1)
    assert (ax.get_xmargin(), ax.get_ymargin()) == (0.1, 0.1)
    assert ax.margins(0.2) == (0.2, 0.2)
    assert ax.margins(y=0.4) == (0.2, 0.4)
    with pytest.raises(TypeError):
        ax.margins(0.1, 0.2, 0.3)
    with pytest.raises(TypeError):
        ax.margins(0.1, y=0.2)

    lines = ax.get_xgridlines()
    assert len(lines) == 2 and not lines[0].get_visible()
    ax.grid(True)
    assert lines[0].get_visible() and not lines[1].get_visible()
    lines[0].set_visible(False)
    assert not ax.show_grid
    lines[0].set_color("red")
    lines[0].set_linewidth(2)
    lines[0].set_alpha(0.5)
    assert lines[0].get_color()
    assert lines[0].get_linewidth() == 2 and lines[0].get_alpha() == 0.5
    assert len(ax.get_ygridlines()) == 2

    path = ax.get_clip_path()
    assert path.get_vertices().shape == (5, 2)
    sentinel = object()
    ax.set_clip_path(sentinel)
    assert ax.get_clip_path() is sentinel
    ax.redraw_in_frame()


def test_axes_label_outer_hides_inner_tick_labels():
    fig, axs = plt.subplots(2, 2)
    for ax in axs.ravel():
        ax.label_outer()
    flags = [(ax.hide_xticklabels, ax.hide_yticklabels) for ax in axs.ravel()]
    assert flags == [(True, False), (True, True), (False, False), (False, True)]
    plt.close(fig)


def test_axes_pie_label_formats_and_appends_texts():
    fig, ax = plt.subplots()
    pie = ax.pie([1.0, 2.0, 3.0])
    texts = ax.pie_label(pie, "{absval:g} ({frac:.0%})")
    assert [text.get_text() for text in texts] == ["1 (17%)", "2 (33%)", "3 (50%)"]
    assert pie.texts == texts
    assert plt.pie_label(pie, ["a", "b", "c"])[-1].get_text() == "c"
    with pytest.raises(ValueError, match="must match the number of wedges"):
        ax.pie_label(pie, ["only one"])
    with pytest.raises(ValueError, match="alignment must be"):
        ax.pie_label(pie, ["a", "b", "c"], alignment="bogus")
    plt.close(fig)


def test_axes_locator_params_and_ticklabel_format():
    fig, ax = plt.subplots()
    ax.plot([0.0, 1000.0], [0.0, 1.0])
    ax.locator_params(axis="x", nbins=3)
    assert ax.get_xticks().tolist() == [0.0, 500.0, 1000.0]
    ax.ticklabel_format(style="sci", scilimits=(0, 0), axis="x")
    labels = [text.get_text() for text in ax.get_xticklabels()]
    assert labels == ["0.00e+00", "5.00e+02", "1.00e+03"]
    with pytest.raises(ValueError, match="scilimits must be a sequence"):
        ax.ticklabel_format(scilimits=1)
    with pytest.raises(ValueError, match="axis must be"):
        ax.locator_params(axis="z")
    plt.close(fig)


def test_axes_relim_and_legend_state():
    fig, ax = plt.subplots()
    assert ax.get_legend() is None
    ax.plot([0.0, 1.0], [0.0, 1.0], label="line")
    ax.legend()
    assert ax.get_legend() is not None
    assert ax.get_forward_navigation_events() == "auto"
    ax.set_forward_navigation_events(False)
    assert ax.get_forward_navigation_events() is False

    ax.set_xlim(0.0, 10.0)
    assert ax.get_autoscalex_on() is False
    ax.relim()
    assert ax.get_xlim() == (0.0, 10.0)
    ax.set_xlim(0.0, 10.0, auto=True)
    ax.relim()
    assert ax.get_xlim() == pytest.approx((-0.05, 1.05))
    plt.close(fig)


def test_pyplot_wrappers_and_formatters():
    fig, ax = plt.subplots()
    spectrum, freqs, bins, image = plt.specgram(np.ones(300), Fs=None)
    assert spectrum.shape[0] == freqs.size and image is not None
    assert plt.barbs(np.zeros(2), np.zeros(2), np.ones(2), np.ones(2)) is not None
    assert len(plt.ecdf(np.array([1.0, 2.0, 3.0]))) == 3
    assert plt.figimage(np.zeros((2, 2, 3), dtype=np.uint8)) is not None
    assert plt.autoscale(True) is None
    formatter = plt.FuncFormatter(lambda value, pos: f"{value:.0f}")
    assert formatter(2.6) == "3" and formatter.format_data_short(2.6) == "3"
    with pytest.raises(TypeError):
        plt.FuncFormatter(3)
    assert plt.Normalize(0.0, 2.0)(1.0) == pytest.approx(0.5)


def test_large_tick_labels_reserve_axis_label_space(tmp_path):
    def plotting_rect(size, name):
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.set_facecolor("red")
        ax.plot([0, 1], [0, 1])
        ax.tick_params(labelsize=size)
        ax.set_xlabel("X label")
        ax.set_ylabel("Y label")
        path = tmp_path / f"labels_{name}.svg"
        fig.savefig(path)
        match = re.search(
            r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" '
            r'opacity="1" fill="#FF0000"',
            path.read_text(encoding="utf-8"),
        )
        assert match is not None
        return tuple(int(value) for value in match.groups())

    x, y, w, h = plotting_rect(10, "small")
    big_x, big_y, big_w, big_h = plotting_rect(18, "big")
    # Bigger ticks push the plot right and up; the labels no longer overlap.
    assert big_x > x
    assert big_y + big_h < y + h
    assert big_w < w
    assert big_h < h


def test_axes_grid1_anchored_artists_and_mark_inset(tmp_path):
    from matplotvite.mpl_toolkits.axes_grid1.anchored_artists import (
        AnchoredDirectionArrows,
        AnchoredDrawingArea,
        AnchoredSizeBar,
        AnchoredText,
    )
    from matplotvite.mpl_toolkits.axes_grid1.inset_locator import (
        mark_inset,
        zoomed_inset_axes,
    )

    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    before = len(ax.texts)
    text = AnchoredText("note", loc="lower left", frameon=False)
    assert ax.add_artist(text) is text
    assert len(ax.texts) == before + 1
    bar = AnchoredSizeBar(ax.transData, 0.5, "0.5", loc="lower center")
    ax.add_artist(bar)
    before = len(ax.texts)
    arrows = AnchoredDirectionArrows(ax.transAxes, "X", "Y", loc="upper left")
    ax.add_artist(arrows)
    assert len(ax.texts) == before + 4
    area = AnchoredDrawingArea(20, 20, 0, 0, loc="upper right")
    ax.add_artist(area)
    inset = zoomed_inset_axes(ax, 2)
    assert mark_inset(ax, inset) is None
    fig.savefig(tmp_path / "anchored.png")


def test_axisartist_axes_grid_and_floating_axes(tmp_path):
    from matplotvite.mpl_toolkits import axisartist
    from matplotvite.mpl_toolkits.axes_grid1 import host_subplot
    from matplotvite.mpl_toolkits.axisartist import (
        GridHelperCurveLinear,
        angle_helper,
        grid_finder,
    )

    fig = plt.figure((6, 4))
    ax = fig.add_subplot(121, axes_class=axisartist.Axes,
                         xlim=(-5, 12), ylim=(-5, 10), aspect=1)
    assert ax.get_xlim() == (-5, 12)
    assert ax.get_ylim() == (-5, 10)
    ax.axis[:].set_visible(False)
    ax.axis["x"] = ax.new_floating_axis(1, 0.5)
    ax.axis["x"].set_axisline_style("->", size=1.5)
    ax.axis["x"].label.set_text("Floating")
    ax.axis[:].major_ticks.set_tick_out(True)
    assert len(ax.axis.values()) >= 4

    helper = GridHelperCurveLinear(
        (lambda x, y: (x, y - x), lambda x, y: (x, y + x)),
        extreme_finder=angle_helper.ExtremeFinderCycle(20, 20),
        grid_locator1=angle_helper.LocatorDMS(6),
        grid_locator2=grid_finder.MaxNLocator(5),
        tick_formatter1=angle_helper.FormatterDMS())
    curvy = fig.add_subplot(122, axes_class=axisartist.Axes,
                            grid_helper=helper)
    curvy.plot([0, 1, 2], [2, 1, 3])
    curvy.axis["right"].get_helper().nth_coord_ticks = 0
    assert curvy.grid_helper is helper

    zero = fig.add_subplot(111, axes_class=axisartist.AxesZero)
    zero.axis["xzero"].set_visible(True)
    assert zero.axis["xzero"].get_visible()
    fig.savefig(tmp_path / "axisartist.png")

    fig = plt.figure()
    host = host_subplot(111, axes_class=axisartist.Axes)
    host.axis["right"].toggle(all=True)
    host.plot([0, 1], [0, 2], label="Density")
    host.legend()
    fig.savefig(tmp_path / "axisartist_host.png")


def test_small_api_gaps_for_grids_effects_and_artists(tmp_path):
    from matplotvite import colors, patheffects

    fig = plt.figure()
    gs = fig.add_gridspec(2, 2)
    axs = gs.subplots(sharex=True, sharey=True)
    assert axs.shape == (2, 2)
    assert axs[0, 0]._share_x is not None
    assert fig.dpi_scale_trans is not None

    line, = axs[0, 0].plot([0, 1], [0, 1],
                           path_effects=[patheffects.withTickedStroke()])
    line.set_dashes([2, 2, 10, 2])
    line.set_dash_capstyle("round")
    patch = plt.Rectangle((0, 0), 1, 1)
    axs[0, 0].add_patch(patch)
    assert patch.axes is axs[0, 0]
    assert patch.figure is fig
    assert patch.get_path().vertices.shape[0] >= 4
    axs[0, 0].get_xticklabels()[0].set_picker(True)
    assert axs[0, 0].legend().get_lines() == []

    norm = colors.AsinhNorm(linear_width=0.5, vmin=-2, vmax=2)
    assert float(norm(0.0)) == 0.5
    fig.savefig(tmp_path / "small_gaps.png")


def test_axes_grid1_axesgrid_host_subplot_and_divider_position(tmp_path):
    from matplotvite.mpl_toolkits.axes_grid1 import (
        AxesGrid,
        Divider,
        Size,
        host_subplot,
    )

    fig = plt.figure((6, 4))
    grid = AxesGrid(fig, 121, nrows_ncols=(2, 2), cbar_mode="edge",
                    direction="column", cbar_location="bottom")
    assert len(grid.cbar_axes) == 2
    assert [cax.orientation for cax in grid.cbar_axes] == ["bottom", "bottom"]
    image = grid[0].imshow([[0, 1], [2, 3]])
    assert grid.cbar_axes[0].colorbar(image) is not None
    grid.cbar_axes[0].axis["bottom"].set_label("Bar")
    assert grid[2].get_xlabel() == "Bar"

    divider = Divider(fig, (0, 0, 1, 1), [Size.Fixed(1.0)],
                      [Size.Fixed(1.0)], aspect=False)
    assert divider.get_position() == (0.0, 0.0, 1.0, 1.0)
    locator = divider.new_locator(nx=0, ny=0)
    assert fig.add_axes(divider.get_position(), axes_locator=locator) is not None
    fig.savefig(tmp_path / "axesgrid.png")

    fig = plt.figure()
    host = host_subplot(111)
    host.plot([0, 1], [0, 1], label="Density")
    twin = host.twin()
    assert twin is not host
    assert twin.get_ylim() == host.get_ylim()
    host.legend(labelcolor="linecolor")
    fig.savefig(tmp_path / "host_subplot.png")


def test_scale_module_exposes_matplotlib_classes():
    import matplotvite.scale as mscales
    import numpy as np

    assert mscales.get_scale_names() == [
        "asinh", "function", "functionlog", "linear", "log", "logit", "symlog"
    ]
    assert str(mscales.LogScale(None)) == "log"
    transform = mscales.LogitScale(None).get_transform()
    assert np.allclose(transform.transform([0.5]), [0.0])
    assert np.allclose(transform.inverted().transform([0.0]), [0.5])
    forward, inverse = np.exp, np.log
    func = mscales.FuncScale(None, functions=(forward, inverse)).get_transform()
    assert np.allclose(func.transform([1.0]), [np.e])


def test_function_scale_transforms_coordinates_and_keeps_labels(tmp_path):
    import numpy as np

    fig, ax = plt.subplots()
    ax.plot(np.arange(10), np.linspace(0.01, 1.0, 10))
    ax.set_yscale("function", functions=(np.sqrt, np.square))
    ax.set_yticks([0.0, 0.25, 1.0])

    panel = ax._panel()
    assert np.isfinite(panel["y"]["lim"]).all()
    assert panel["y"]["lim"][0] > 0
    assert panel["y"]["lim"][1] == pytest.approx(1.0)
    assert panel["ticks"]["yticks"] == pytest.approx([0.0, 0.5, 1.0])
    assert panel["ticks"]["yticklabels"] == ["0", "0.25", "1"]

    path = tmp_path / "function_scale.png"
    fig.savefig(path)
    assert path.stat().st_size > 0


def test_registered_custom_scale_transforms_coordinates(tmp_path):
    import matplotvite.scale as mscales
    import numpy as np

    class CubeScale(mscales.ScaleBase):
        name = "test-cube"

        def get_transform(self):
            return mscales._ScaleTransform(
                lambda values: np.asarray(values, dtype=float) ** 3,
                lambda values: np.cbrt(np.asarray(values, dtype=float)))

    mscales.register_scale(CubeScale)
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [1, 2, 3])
    ax.set_yscale("test-cube")
    ax.set_yticks([1, 2, 3])

    panel = ax._panel()
    assert panel["y"]["lim"] == pytest.approx(np.asarray(ax.get_ylim()) ** 3)
    assert panel["ticks"]["yticks"] == pytest.approx([1, 8, 27])
    assert panel["ticks"]["yticklabels"] == ["1", "2", "3"]

    path = tmp_path / "custom_scale.png"
    fig.savefig(path)
    assert path.stat().st_size > 0


def test_ft2font_reports_face_properties():
    from matplotvite import FaceFlags, FT2Font, StyleFlags, ft2font

    font = ft2font.FT2Font("DejaVuSans-Oblique.ttf")
    assert font.num_named_instances == 0
    assert font.num_faces == 1
    assert font.scalable and font.family_name == "DejaVu Sans"
    assert font.set_charmap(0) is None
    assert isinstance(font.get_charmap(), dict)
    assert StyleFlags.ITALIC in font.style_flags
    assert StyleFlags.BOLD not in font.style_flags
    assert FaceFlags.SCALABLE in font.face_flags
    assert FT2Font is ft2font.FT2Font
    assert [flag.name for flag in StyleFlags] == ["ITALIC", "BOLD"]


def test_ft2font_names_glyphs_and_loads_characters():
    from matplotvite import Kerning, ft2font

    font = ft2font.FT2Font("DejaVuSans.ttf")
    assert font.get_glyph_name(ord("A")) == "A"
    assert font.get_glyph_name(ord("V")) == "V"
    glyph = font.load_char(ord("A"))
    assert len(glyph.bbox) == 4
    assert font.get_kerning(ord("A"), ord("V"), Kerning.DEFAULT) == 0
    assert ft2font.Kerning is Kerning


def test_plot_fmt_marker_only_and_unlabelled_scatter():
    fig, ax = plt.subplots()
    line = ax.plot([0, 1], [0, 1], "o+")[0]
    assert line.get_linestyle() == "None"
    ax.scatter([0, 1], [0, 1])
    ax.legend()
    svg = fig.savefig(None, format="svg").decode()
    assert "y0" not in svg


def test_plot_legend_still_works_with_markers(tmp_path):
    plt.figure()
    plt.plot([0, 1], [0, 1], label="marked", marker="s", linestyle=":")
    plt.legend()
    p = tmp_path / "legend.svg"
    plt.savefig(p)
    assert "marked" in p.read_text(encoding="utf-8")


def test_bar_label_places_values(tmp_path):
    plt.figure()
    ax = plt.gca()
    bars = ax.bar([1, 2, 3], [3, 1, 2])
    labels = ax.bar_label(bars, padding=3)
    assert labels == ["3", "1", "2"]
    p = tmp_path / "bl.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
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
    s = p.read_text(encoding="utf-8")
    assert "#FF0000" in s.upper()
    assert re.search(r">\s*bars\s*<", s)
    assert bars[0].get_height() == 2.0 and bars[0].get_width() == 0.8


def test_grid_draws_and_toggles(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.plot([0, 1], [0, 1])
    plain = tmp_path / "nogrid.svg"
    plt.savefig(plain)
    ax.grid(True)
    with_grid = tmp_path / "grid.svg"
    plt.savefig(with_grid)
    assert len(with_grid.read_text(encoding="utf-8")) > len(plain.read_text(encoding="utf-8"))
    assert ax.show_grid is True
    ax.grid()
    assert ax.show_grid is False
    plt.grid(True)
    assert plt.gca().show_grid is True

    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    ax.grid(True)
    major = tmp_path / "grid-major.svg"
    fig.savefig(major)
    ax.minorticks_on()
    ax.grid(True, which="both")
    both = tmp_path / "grid-both.svg"
    fig.savefig(both)
    assert ax._panel()["grid"]["minor_show"] is True
    assert (both.read_text(encoding="utf-8").upper().count("#B0B0B0")
            > major.read_text(encoding="utf-8").upper().count("#B0B0B0"))


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
    s = p.read_text(encoding="utf-8").upper()
    assert "#008000" in s and "#0000FF" in s
    # axline never moves the data limits
    assert ax.get_xlim() == (0.0, 4.0) and ax.get_ylim() == (0.0, 4.0)
    with pytest.raises(ValueError):
        ax.axline((0, 0))
    with pytest.raises(ValueError):
        ax.axline((0, 0), (1, 1), slope=2)


def test_pyplot_registry_tracks_numbered_and_labelled_figures():
    plt.close("all")
    try:
        first = plt.figure(3)
        assert first.number == 3
        assert plt.get_fignums() == [3]
        assert plt.fignum_exists(3)
        assert plt.figure(num=3) is first

        labelled = plt.figure("analysis", figsize=(3, 2))
        assert labelled.number == 4
        assert labelled.get_label() == "analysis"
        assert plt.figure("analysis") is labelled
        assert plt.gcf() is labelled

        plt.close(first)
        assert plt.get_fignums() == [4]
        assert not plt.fignum_exists(3)
        plt.close()
        assert plt.get_fignums() == []
    finally:
        plt.close("all")


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
    s = p.read_text(encoding="utf-8").upper()
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
    assert pie.read_text(encoding="utf-8").count("<polygon") >= 2

    plt.figure()
    plt.stem([1, 3, 2], linefmt="r-")

    plt.figure()
    plt.stackplot(np.arange(3.0), [1, 1, 1], [2, 2, 2])

    plt.figure()
    bars = plt.bar([1, 2], [3, 4])
    assert plt.bar_label(bars) == ["3", "4"]

    p = tmp_path / "pyplot-shims.svg"
    plt.savefig(p)
    assert p.read_text(encoding="utf-8").count("<rect") >= 3


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
    # Matplotlib applies `setp` to each artist when given a container.
    plt.setp(bars, height=4.0)
    assert plt.getp(bars, "height") == [4.0]
    with pytest.raises(AttributeError):
        plt.getp(bars[0], "nonsense")
    with pytest.raises(AttributeError):
        plt.setp(bars[0], nonsense=1)


def test_scatter_and_fill_legend(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.scatter([1, 2], [2, 1], label="dots")
    ax.fill_between([1, 2, 3], [1, 1, 1], 0, label="band")
    ax.legend()
    p = tmp_path / "legend.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
    assert re.search(r">\s*dots\s*<", s) and re.search(r">\s*band\s*<", s)


def test_datetime_x_axis_plot(tmp_path):
    from datetime import datetime, timedelta

    dates = [datetime(2020, 1, 1) + timedelta(days=30 * i) for i in range(10)]
    plt.figure((5, 3))
    plt.plot(dates, np.arange(10))
    ax = plt.gca()
    assert ax._x_date
    assert ax.get_xlim() == (737411.5, 737708.5)
    panel = ax._panel()
    labels = panel["ticks"]["xticklabels"]
    assert labels and labels[0].startswith("2020-")
    p = tmp_path / "dates.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_datetime_limits_ticks_and_time_labels():
    from datetime import datetime

    plt.figure((4, 3))
    ax = plt.gca()
    ax.set_xlim(datetime(2020, 1, 1), datetime(2020, 12, 31))
    assert ax._x_date
    labels = ax._panel()["ticks"]["xticklabels"]
    assert labels[0] == "2020-01-01" and all("2020-" in v for v in labels)

    plt.figure((4, 3))
    ax = plt.gca()
    ax.set_xticks([datetime(2020, 1, 1), datetime(2020, 7, 1)])
    panel = ax._panel()["ticks"]
    assert panel["xticks"] == [737425.0, 737607.0]
    assert panel["xticklabels"] == ["2020-01-01", "2020-07-01"]

    plt.figure((4, 3))
    plt.plot([datetime(2024, 1, 1, 0), datetime(2024, 1, 1, 6),
              datetime(2024, 1, 1, 12)], [0, 1, 0])
    labels = plt.gca()._panel()["ticks"]["xticklabels"]
    assert any("03:00" in v for v in labels)
    assert not any("03:59" in v for v in labels)


def test_categorical_x_axis(tmp_path):
    plt.figure((4, 3))
    plt.plot(["alpha", "beta", "gamma"], [1, 3, 2])
    panel = plt.gca()._panel()["ticks"]
    assert panel["xticks"] == [0.0, 1.0, 2.0]
    assert panel["xticklabels"] == ["alpha", "beta", "gamma"]
    p = tmp_path / "categories.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    plt.figure((4, 3))
    ax = plt.gca()
    ax.bar(["Mon", "Tue", "Wed"], [3, 5, 2])
    ax.scatter(["Mon", "Wed"], [1, 4])
    labels = ax._panel()["ticks"]["xticklabels"]
    assert labels == ["Mon", "Tue", "Wed"]
    p = tmp_path / "bar-categories.svg"
    plt.savefig(p)
    assert "Mon" in p.read_text(encoding="utf-8") and "Wed" in p.read_text(encoding="utf-8")


def test_mathtext_titles_labels_and_text(tmp_path):
    from matplotvite import _mathtext

    assert _mathtext("$x^2$") == "x²"
    assert _mathtext("$x^{10}$") == "x¹⁰"
    assert _mathtext("$e^{-x}$") == "e⁻ˣ"
    assert _mathtext("$A_{i-1}$") == "Aᵢ₋₁"
    # Geist has only the Unicode script digits, so it keeps the readable fallback.
    assert _mathtext("$e^{-x}$", "Geist Serif") == "e^(-x)"
    assert _mathtext("$\\alpha$ and $\\beta_1$") == "α and β₁"
    assert _mathtext("$\\sqrt{x}$") == "√x"
    assert _mathtext("plain text") == "plain text"
    assert _mathtext("price $5") == "price $5"

    plt.figure((4, 3))
    plt.plot([0, 1], [0, 1])
    plt.title("$x^2$")
    plt.xlabel("$\\alpha$")
    plt.ylabel("$\\beta_{0}$")
    plt.text(0.1, 0.5, "$\\infty$")
    plt.text(0.1, 0.3, "$e^{-x}$")
    ax = plt.gca()
    assert ax.title == "x²" and ax.xlabel == "α" and ax.ylabel == "β₀"
    p = tmp_path / "mathtext.svg"
    plt.savefig(p)
    svg = p.read_text(encoding="utf-8")
    assert "x²" in svg and "β₀" in svg and "e⁻ˣ" in svg


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
    s = p.read_text(encoding="utf-8").upper()
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
    s = p.read_text(encoding="utf-8").upper()
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
    s = p.read_text(encoding="utf-8")
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
    assert re.search(r">\s*mid\s*<", p.read_text(encoding="utf-8"))


def test_title_fontsize(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    ax.set_title("Big", fontsize=20)
    ax.set_xlabel("xx", fontsize=14)
    panel = ax._panel()
    assert panel["title_size"] == 20.0 and panel["x"]["label_size"] == 14.0
    p = tmp_path / "font.svg"
    fig.savefig(p)
    sizes = [float(v) for v in re.findall(r'font-size="([\d.]+)"', p.read_text(encoding="utf-8"))]
    assert max(sizes) > 16  # title is the largest text
    assert any(18.5 < v < 20.5 for v in sizes)  # xlabel at 14pt


def test_default_sans_font_is_dejavu():
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    ax.set_title("DejaVu Sans")
    pdf = fig.savefig(None, format="pdf")
    assert b"DejaVuSans" in pdf


def test_tick_params_accepts_auto_rotation():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.tick_params(rotation="auto")
    assert ax._tick_style_dict("x")["rotation"] == 0.0
    assert ax._tick_style_dict("y")["rotation"] == 0.0


def test_default_font_sizes_and_tick_label_handles():
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    ax.set_title("Title")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    fig.suptitle("Sup")
    panel = ax._panel()
    assert panel["title_size"] == 12.0
    assert panel["x"]["label_size"] == 10.0
    assert panel["y"]["label_size"] == 10.0
    assert fig._suptitle["size"] == 12.0
    assert ax.get_xticklabels()[0].get_fontsize() == 10.0
    assert ax.get_yticklabels()[0].get_fontsize() == 10.0
    ax.tick_params(labelsize=8)
    assert ax.get_xticklabels()[0].get_fontsize() == 8.0
    assert ax.get_yticklabels()[0].get_fontsize() == 8.0
    fig.suptitle("Big", fontsize=16)
    assert fig._suptitle["size"] == 16.0


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


def test_shared_axes_render_fewer_tick_labels():
    counts = []
    for shared in (False, True):
        fig, axs = plt.subplots(2, 2, figsize=(4, 4), sharex=shared, sharey=shared)
        for ax in axs.flat:
            ax.plot([0, 1], [0, 1])
        svg = fig.savefig(None, format="svg").decode()
        texts = re.findall(r"<text[^>]*>(.*?)</text>", svg, re.S)
        counts.append(sum(bool(text.strip()) for text in texts))
    assert counts[1] < counts[0]


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


def test_gridspec_ratios_control_cell_sizes(tmp_path):
    fig = plt.figure((6, 4))
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 2], height_ratios=[1, 3])
    top_left = fig.add_subplot(gs[0, 0])
    top_right = fig.add_subplot(gs[0, 1])
    bottom_left = fig.add_subplot(gs[1, 0])
    for ax in (top_left, top_right, bottom_left):
        ax.plot([0, 1], [0, 1])
    assert top_right.get_position().width / top_left.get_position().width == pytest.approx(2, rel=0.15)
    assert bottom_left.get_position().height / top_left.get_position().height == pytest.approx(3.5, rel=0.1)
    with pytest.raises(ValueError):
        fig.add_gridspec(2, 2, width_ratios=[1])
    fig.savefig(tmp_path / "ratios.png")


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
    assert p.read_text(encoding="utf-8").startswith("<svg")
    fig2, only = plt.subplot_mosaic([[".", "a"]])
    assert list(only) == ["a"]
    assert fig2 is plt.gcf()


def test_twinx_adds_right_axis_on_the_same_panel(tmp_path):
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 1, 2], [1, 4, 9], color="red")
    ax.set_ylabel("left", color="#c44e52")
    original = ax.get_position().bounds
    twin = ax.twinx()
    twin.plot([0, 1, 2], [100, 50, 10], color="blue")
    twin.set_ylabel("right", color="#4c72b0")
    assert twin._twin_of is ax and twin._twin == "y"
    assert twin.get_xlim() == ax.get_xlim()
    assert ax.get_position().bounds == original
    assert twin.get_position().bounds == original
    assert ax._panel()["twin_reserve"] == "y"
    assert twin._panel()["twin_reserve"] == "y"
    assert ax._panel()["y"]["label_color"] == "#c44e52"
    assert twin._panel()["y"]["label_color"] == "#4c72b0"
    assert ax._panel()["bounds"] is not None and twin._panel()["bounds"] is not None
    assert twin._panel()["ticks"]["hide_xlabels"]
    p = tmp_path / "twinx.svg"
    fig.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert "#FF0000" in s and "#0000FF" in s
    assert "#C44E52" in s and "#4C72B0" in s
    assert "right" in p.read_text(encoding="utf-8")


def test_twinx_left_axis_keeps_tick_density_and_label_spacing():
    x = np.linspace(0, 12, 140)
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.plot(x, 20 + 8 * np.sin(x / 2.0), color="#c44e52")
    ax.set_ylabel("Temperature (C)", color="#c44e52")
    twin = ax.twinx()
    twin.plot(x, 101 + 3 * np.cos(x / 3.0), color="#4c72b0")
    twin.set_ylabel("Pressure (kPa)", color="#4c72b0")
    svg = fig.savefig(format="svg").decode()
    labels = {t.strip() for t in re.findall(r"<text[^>]*>([^<]*)</text>", svg)}
    # 11.2 to 28.8 fits 2s, the step Matplotlib's AutoLocator picks; a 5s
    # step would leave only 15, 20 and 25 on the left axis.
    assert {"12", "14", "16", "18", "20", "22", "24", "26", "28"} <= labels
    width, _, rows = decode_png_rgba(fig.savefig(format="png"))
    cut = width // 8
    label_right = 0
    tick_left = width
    for row in rows:
        for x in range(cut):
            r, g, b = row[x * 4], row[x * 4 + 1], row[x * 4 + 2]
            if r > 150 and g < 120 and b < 120:
                label_right = max(label_right, x)
            elif max(r, g, b) < 100:
                tick_left = min(tick_left, x)
    assert label_right and tick_left < width
    # Matplotlib's 4 pt labelpad: the rotated label sits just clear of the
    # widest tick label instead of 20 px away at a fixed offset.
    assert 0 < tick_left - label_right <= 14


def test_auto_and_twin_axes_report_the_ticks_they_draw():
    x = np.linspace(0, 12, 140)
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.plot(x, 20 + 8 * np.sin(x / 2.0))
    twin = ax.twinx()
    twin.plot(x, 101 + 3 * np.cos(x / 3.0))
    drawn = {t.strip() for t in re.findall(
        r"<text[^>]*>([^<]*)</text>", fig.savefig(format="svg").decode())}
    # 11.2 to 28.8 fits nine labels in 2s, 97.7 to 104.3 seven in 1s, and the
    # automatic x axis seven in 2s: round locator values, not a linspace.
    assert [f"{v:g}" for v in ax.get_yticks()] == [
        "12", "14", "16", "18", "20", "22", "24", "26", "28"]
    assert [f"{v:g}" for v in twin.get_yticks()] == [
        "98", "99", "100", "101", "102", "103", "104"]
    assert list(ax.get_xticks()) == pytest.approx([0, 2, 4, 6, 8, 10, 12])
    # Every reported tick is drawn, so the accessor cannot drift from the SVG.
    assert {f"{v:g}" for v in ax.get_yticks()} <= drawn
    assert {f"{v:g}" for v in twin.get_yticks()} <= drawn
    assert {f"{v:g}" for v in ax.get_xticks()} <= drawn


def test_direct_and_svg_png_paths_rasterise_the_same_ticks():
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 1, 2, 3, 4], [-2, 1, 4, 9, 16])
    ax.set_title("t")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True)
    direct = decode_png_rgba(fig.savefig(format="png"))
    # A transparent background is not eligible for the direct bitmap path, so
    # this is the same panel drawn into an SVG document and rasterised by resvg.
    svg = decode_png_rgba(fig.savefig(format="png", transparent=True))
    assert direct[:2] == svg[:2]
    assert any(row[i + 3] < 255 for row in svg[2] for i in range(0, len(row), 4))
    worst = differing = total = 0
    for row_a, row_b in zip(_over_white(direct[2]), _over_white(svg[2])):
        for x in range(len(row_a)):
            total += 1
            diff = max(abs(row_a[x][k] - row_b[x][k]) for k in range(3))
            worst = max(worst, diff)
            differing += diff > 32
    # The manual ticks, their labels and the gridlines land on the same pixels
    # in both renderers; only anti-aliasing separates them.
    assert differing == 0 and total > 100_000
    assert worst <= 8


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
    assert re.search(r">\s*Figure title\s*<", p.read_text(encoding="utf-8"))
    assert fig.savefig(None, format="png")[:8] == b"\x89PNG\r\n\x1a\n"
    plt.suptitle("pyplot title")
    assert plt.gcf()._suptitle["text"] == "pyplot title"


def test_figure_text_needs_no_axes_and_is_not_clipped(tmp_path):
    fig = plt.figure()
    fig.text(0.5, 0.5, "figure text", ha="center", va="center", fontsize=16, color="red")
    p = tmp_path / "figtext.svg"
    fig.savefig(p)
    assert re.search(r">\s*figure text\s*<", p.read_text(encoding="utf-8"))
    # It sits above the panels, spanning the grid rather than one cell.
    fig2, _ = plt.subplots(1, 2)
    fig2.text(0.5, 0.95, "across panels", ha="center")
    p2 = tmp_path / "figtext_grid.svg"
    fig2.savefig(p2)
    assert "across panels" in p2.read_text(encoding="utf-8")
    # Text properties the renderer cannot draw yet are accepted, but a typo is not.
    fig2.text(0.1, 0.1, "rotated", rotation=45, usetex=False)
    with pytest.raises(TypeError):
        fig2.text(0.1, 0.1, "bad", nonsense=1)
    plt.figtext(0.5, 0.5, "pyplot helper")
    assert plt.gcf()._figure_texts[-1][2] == "pyplot helper"


def test_svg_text_is_escaped():
    plt.figure((4, 3))
    payload = '</text><image href="file:///etc/passwd"/>'
    plt.plot([0, 1], [0, 1], label=payload)
    plt.title(f'<script>alert("title")</script>{payload}')
    plt.xlabel('a & b')
    plt.xticks([0, 1], [payload, "safe"])
    plt.legend()
    svg = plt.savefig(None, format="svg").decode()
    assert "<script" not in svg.lower()
    assert "<image" not in svg.lower()
    assert "&lt;/text&gt;" in svg
    assert "&lt;" in svg and "&amp;" in svg


def test_gallery_animation_gridspec_and_numeric_inputs():
    from datetime import datetime

    class UnitValue:
        def __init__(self, value):
            self._value = value

    class TaggedValue:
        def __init__(self, value):
            self.value = value

    fig = plt.figure()
    timer = fig.canvas.new_timer(interval=25)
    assert timer.interval == 25
    assert timer.add_callback(lambda: None) == 1
    timer.start()
    timer.stop()

    gs = fig.add_gridspec(1, 2)
    right = gs[1]
    assert right.rows == (0, 0) and right.cols == (1, 1)
    nested = right.subgridspec(2, 2)
    assert nested[3].rows == (1, 1) and nested[3].cols == (1, 1)

    ax = fig.add_subplot(gs[0])
    ax.plot([0, 1], [None, 2])
    ax.plot([UnitValue(0), UnitValue(1)], [TaggedValue(0), TaggedValue(1)])
    ax.bar([UnitValue(0), UnitValue(1)], [UnitValue(2), UnitValue(3)])
    ax.bar([1, 2], [1, 2],
           color=np.array([[1, 0, 0, 1], [0, 0, 1, 1]], dtype=float))
    ax.set_xlim([-1, 2])
    ax.set_ylim([-2, 3])
    ax.axhline(datetime(2024, 1, 2))
    ax.axhspan(datetime(2024, 1, 1), datetime(2024, 1, 3))
    assert len(ax.get_position()) == 4

    text = ax.text(0, 0, "text")
    assert text.set_path_effects([]) is text
    assert text.get_bbox_patch().set_path_effects([]) is not None
    assert fig.text(0.5, 0.5, "figure").set_path_effects([]) is not None

    other = plt.figure()
    added = plt.Axes(other, [0.1, 0.1, 0.5, 0.5])
    assert other.add_axes(added) is added
    assert other.axes[-1] is added


def test_gallery_subfigures_have_independent_grids():
    fig = plt.figure()
    left, right = fig.subfigures(1, 2)
    ax_left = left.subplots()
    axs_right = right.subplots(2, 2)
    assert ax_left.get_position()[0] < axs_right[0, 0].get_position()[0]
    assert axs_right[0, 0].get_position()[1] > axs_right[1, 0].get_position()[1]
    left.suptitle("left")
    assert left.get_zorder() == 0


def test_gallery_mixed_subplots_and_text_accessors():
    fig = plt.figure()
    bottom = fig.add_subplot(2, 1, 2)
    top_left = fig.add_subplot(2, 2, 1)
    assert bottom.get_position()[1] < top_left.get_position()[1]

    bottom.text(0.25, 0.5, "label")
    label = bottom.texts[-1]
    assert label.get_position() == (0.25, 0.5)
    assert label.get_text() == "label"
    assert callable(bottom.axis)


def test_gallery_subplot2grid_and_gridspec_updates():
    fig = plt.figure()
    wide = plt.subplot2grid((3, 3), (0, 0), colspan=2)
    tall = fig.subplot2grid((3, 3), (1, 2), rowspan=2)
    assert wide.get_position()[2] > tall.get_position()[2]

    fig.axes[0].set_forward_navigation_events(False)
    assert fig.axes[0].get_forward_navigation_events() is False

    gs = fig.add_gridspec(3, 1)
    gs.update(top=0.8)
    assert gs.top == 0.8
    gs.tight_layout(fig)


def test_polar_projection_projects_data_and_draws_labels(tmp_path):
    fig, ax = plt.subplots(subplot_kw={"projection": "polar"})
    line, = ax.plot([0.0, np.pi / 2], [1.0, 2.0])
    assert line.get_xdata().tolist() == [0.0, np.pi / 2]
    ax.set_thetagrids([0.0, 90.0], ["east", "north"])
    ax.set_rgrids([0.5, 1.0])
    svg = fig.savefig(format="svg").decode()
    assert "east" in svg and "north" in svg
    assert "0.5" in svg


def test_explicit_legend_labels_replace_internal_labels(tmp_path):
    fig, ax = plt.subplots()
    ax.fill([0, 1, 0], [0, 0, 1], color="red", label="_nolegend_")
    ax.legend(["Factor"])
    svg = fig.savefig(format="svg").decode()
    assert "Factor" in svg
    assert "_nolegend_" not in svg


def test_polar_grid_setters_accept_matplotlib_arguments(tmp_path):
    plt.rcdefaults()
    fig, ax = plt.subplots(subplot_kw={"projection": "polar"})
    ax.set_rticks([0.5, 1.0])
    ax.set_rlabel_position(-22.5)
    ax.set_theta_zero_location("N", offset=10)
    ax.set_thetamin(0)
    ax.set_thetamax(180)
    ax.set_rgrids([0.25, 0.75], fmt="%.2f")
    ax.set_thetagrids([0, 90], labels=["east", "north"])
    panel = ax._panel()
    assert panel["ticks"]["yticks"] == [0.25, 0.75]
    assert panel["ticks"]["yticklabels"] == ["0.25", "0.75"]
    assert panel["ticks"]["xticklabels"] == ["east", "north"]
    plt.polar([0.0, 1.0], [1.0, 2.0])
    line, = ax.plot(np.float64(1.0), np.int64(2))
    assert line.get_xdata().tolist() == [1.0]
    assert line.get_ydata().tolist() == [2.0]
    out = tmp_path / "polar_grids.png"
    fig.savefig(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_get_subplotspec_reports_the_grid_cell():
    plt.rcdefaults()
    fig, axs = plt.subplots(2, 2)
    spec = axs[1, 0].get_subplotspec()
    assert spec.rows == (1, 1) and spec.cols == (0, 0)
    assert spec.get_position(fig) is not None
    gs = fig.add_gridspec(1, 3)
    ax = fig.add_subplot(gs[1])
    spec = ax.get_subplotspec()
    assert spec.cols == (1, 1) and spec.gridspec is gs
    assert spec.get_gridspec() is gs
    assert spec.is_first_row() and spec.is_last_row()
    assert not spec.is_first_col() and not spec.is_last_col()
    assert axs[0, 0].get_subplotspec().is_first_row()
    assert axs[1, 1].get_subplotspec().is_last_col()


def test_figure_level_x_and_y_labels_and_alignment(tmp_path):
    plt.rcdefaults()
    fig, axs = plt.subplots(2, 2)
    for ax in axs.flat:
        ax.plot([0, 1], [0, 1])
        ax.set_xlabel("x")
        ax.set_ylabel("y")
    fig.align_labels()
    fig.supxlabel("Shared x")
    fig.supylabel("Shared y")
    assert len(fig._figure_texts) == 2
    out = tmp_path / "figure_labels.png"
    fig.savefig(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_symlog_scale_renders_symmetric_decade_ticks(tmp_path):
    plt.rcdefaults()
    figure, axes = plt.subplots()
    axes.set_yscale("symlog", linthresh=1)
    axes.set_xscale("symlog", linthresh=1)
    axes.plot([-1000, -10, -1, 0, 1, 10, 1000],
              [-1000, -10, -1, 0, 1, 10, 1000])
    panel = axes._panel()
    assert panel["y"]["symlog"] is True and panel["y"]["symlog_linthresh"] == 1.0
    assert panel["ticks"]["yticklabels"] == ["−1000", "−100", "−10", "−1", "0",
                                            "1", "10", "100", "1000"]
    assert axes.get_yscale() == "symlog"
    p = tmp_path / "symlog.svg"
    figure.savefig(p)
    assert "−1000" in p.read_text(encoding="utf-8")


def test_text_rotation_applies_to_axes_and_figure_text(tmp_path):
    plt.rcdefaults()
    figure, axes = plt.subplots()
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)
    axes.text(0.5, 0.5, "upright", rotation=90)
    figure.text(0.2, 0.1, "sideways", rotation="vertical")
    assert axes.texts[0].get_rotation() == 90.0
    p = tmp_path / "rotated.svg"
    figure.savefig(p)
    svg = p.read_text(encoding="utf-8")
    assert "upright" in svg and "sideways" in svg
    assert svg.count('transform="rotate(90') == 2


def test_font_family_selection_and_overrides(tmp_path):
    """rcParams picks the bundled face; artist keywords override it."""
    plt.rcParams["font.family"] = ["serif"]
    try:
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        ax.set_title("serif title")
        svg = fig.savefig(None, format="svg").decode()
        assert 'font-family="Geist Serif"' in svg
        fig.savefig(tmp_path / "serif.png")

        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        ax.set_title("mono title", fontfamily="monospace")
        ax.set_xlabel("x label", fontfamily="DejaVu Sans")
        ax.text(0.5, 0.5, "note", fontfamily="DejaVu Sans")
        fig.text(0.5, 0.02, "foot", fontfamily="DejaVu Sans")
        fig.suptitle("sup", fontfamily="DejaVu Sans")
        svg = fig.savefig(None, format="svg").decode()
        assert 'font-family="Geist Mono"' in svg
        assert 'font-family="DejaVu Sans, sans-serif"' in svg
        fig.savefig(tmp_path / "overrides.png")
    finally:
        plt.rcParams["font.family"] = ["sans-serif"]


def test_log_locator_places_decade_and_subsidiary_ticks():
    plt.rcdefaults()
    fig, ax = plt.subplots()
    locator = plt.ticker.LogLocator(base=10)
    assert list(locator.tick_values(1, 1000)) == pytest.approx([1, 10, 100, 1000])
    subs = plt.ticker.LogLocator(base=10, subs=(1.0, 2.0))
    assert list(subs.tick_values(1, 20)) == pytest.approx([1, 2, 10, 20])
    ax.set_yscale("log")
    ax.set_ylim(1, 1000)
    ax.yaxis.set_major_locator(locator)
    assert list(ax.get_yticks()) == pytest.approx([1, 10, 100, 1000])


def test_textpath_is_a_renderable_path(tmp_path):
    """TextPath behaves like a Path, including copy and deepcopy semantics."""
    import copy

    from matplotvite import PathPatch, TextPath

    path = TextPath((0, 0), "!?", size=150)
    assert path.get_extents().width > 0
    assert copy.copy(path).vertices is path.vertices
    assert copy.deepcopy(path).vertices is not path.vertices
    assert (copy.deepcopy(path).vertices == path.vertices).all()

    plt.figure()
    plt.gca().add_patch(PathPatch(path, facecolor="C0"))
    plt.savefig(tmp_path / "textpath.png")


def test_sankey_diagram_labels_and_validation(tmp_path):
    """Sankey exposes diagrams, flow labels and Matplotlib's argument errors."""
    from matplotvite import Sankey

    sankey = Sankey(flows=[0.25], labels=["First"], orientations=[-1])
    assert sankey.diagrams[0].texts[0].get_text() == "First\n0.25"
    with pytest.raises(ValueError, match="'gap' is negative"):
        Sankey(gap=-1)
    with pytest.raises(ValueError, match=r"The shapes of 'flows'"):
        Sankey(flows=[1, -1], orientations=[-1, 0, 1])

    plt.figure()
    diagram = Sankey(flows=[0.5, -0.25, -0.25],
                     labels=["in", "out", "out"],
                     orientations=[1, -1, -1]).finish()[0]
    diagram.texts[-1].set_color("r")
    diagram.patch.set_hatch("/")
    plt.savefig(tmp_path / "sankey.png")


def test_logit_scale_uses_probability_ticks(tmp_path):
    """Logit axes expose odds-spaced probability ticks and render them."""
    fig, ax = plt.subplots()
    ax.plot([-4, 0, 4], [0.02, 0.5, 0.98])
    ax.set_yscale("logit")
    ax.set_ylim(1e-5, 1 - 1e-5)
    ticks = ax.get_yticks()
    assert ticks[0] == pytest.approx(1e-5)
    assert 0.5 in ticks
    labels = [t.get_text() for t in ax.get_yticklabels()]
    assert "1/2" in labels
    assert "10⁻⁵" in labels
    assert "1−10⁻⁵" in labels
    fig.savefig(tmp_path / "logit.png")


def test_custom_projection_spines_and_axis_names():
    """Projection subclasses can build spines and name axis classes."""
    from matplotvite import axis as maxis
    from matplotvite import spines as mspines

    fig, ax = plt.subplots()
    spine = mspines.Spine.linear_spine(ax, "bottom")
    spine.register_axis(maxis.XAxis(ax))
    assert spine.spine_type == "bottom"
    assert spine.get_path().vertices.shape == (2, 2)
    circle = mspines.Spine.circular_spine(ax, (0.5, 0.5), 0.5)
    assert circle.get_path().vertices.shape == (65, 2)
    ax.spines["bottom"] = spine
    assert ax.spines["bottom"] is spine
    assert isinstance(maxis.XTick(ax, 0.0), maxis.XTick)


def test_concise_date_formatter_and_converter():
    """Concise date ticks choose compact labels and install a date locator."""

    from matplotvite import dates

    value = dates.date2num(datetime.datetime(2005, 2, 4, 11, 30))
    formatter = dates.ConciseDateFormatter()
    assert formatter(value) == "11:30"
    assert formatter(dates.date2num(datetime.datetime(2005, 2, 4))) == "04"
    assert formatter(dates.date2num(datetime.datetime(2005, 3, 1))) == "Mar"

    fig, ax = plt.subplots()
    info = dates.ConciseDateConverter().axisinfo(None, ax.xaxis)
    assert isinstance(info.majloc, dates.AutoDateLocator)
    assert isinstance(info.majfmt, dates.ConciseDateFormatter)


def test_percent_and_engineering_tick_formatters(tmp_path):
    """Percent and SI-prefix formatters produce compact tick labels."""
    assert plt.PercentFormatter(xmax=5)(1.0) == "20%"
    assert plt.PercentFormatter(xmax=1, decimals=1)(0.125) == "12.5%"
    assert plt.EngFormatter(unit="Hz")(1500.0) == "1.5 kHz"
    assert plt.EngFormatter(places=0)(1_000_000.0) == "1 M"

    fig, ax = plt.subplots()
    ax.xaxis.set_major_formatter("{x} km")
    ax.plot([0, 1], [0, 1])
    fig.savefig(tmp_path / "formatters.png")


def test_date_locator_helpers_and_epoch():
    """Date helpers cover recurrence fallbacks, ranges and the epoch shim."""

    from matplotvite import dates

    start = datetime.datetime(2000, 3, 2)
    values = dates.drange(start, start + datetime.timedelta(hours=12),
                          datetime.timedelta(hours=6))
    assert len(values) == 3
    rule = dates.rrulewrapper(dates.YEARLY, interval=5)
    locator = dates.RRuleLocator(rule)
    assert locator.tick_values(
        dates.date2num(start),
        dates.date2num(start + datetime.timedelta(days=365))).size > 0
    formatter = dates.AutoDateFormatter(locator)
    assert formatter(dates.date2num(start)) == "2000-03-02"
    dates.set_epoch("2000-01-01")
    assert dates.get_epoch() == "2000-01-01"
    dates.set_epoch("1970-01-01")
