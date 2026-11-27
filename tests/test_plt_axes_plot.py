"""Axes plot families: lines, bars, histograms, errors and fills."""

import datetime
import re

import matplotvite as plt
import numpy as np
import pytest
from png_utils import decode_png_rgba


def test_series_are_clipped_to_the_axes_limits():
    """A line outside xlim/ylim stops at the spine instead of crossing the margins."""
    plt.figure((4, 3), dpi=100)
    plt.plot([-1, 2], [-5, 10], color="red", linewidth=4)
    plt.xlim(0, 1)
    plt.ylim(0, 5)
    width, height, rows = decode_png_rgba(plt.savefig(format="png"))

    def red(x, y):
        i = x * 4
        return rows[y][i] > 170 and rows[y][i + 1] < 90 and rows[y][i + 2] < 90

    painted = [(x, y) for y in range(height) for x in range(width) if red(x, y)]
    assert painted, "the clipped line vanished entirely"
    xs = [x for x, _ in painted]
    ys = [y for _, y in painted]
    # The axes margins are about 25 px wide; an unclipped series paints into them.
    band_x, band_y = width // 20, height // 20
    assert min(xs) >= band_x and max(xs) <= width - band_x
    assert min(ys) >= band_y and max(ys) <= height - band_y


def test_constant_series(tmp_path):
    plt.figure(); plt.plot([1, 2, 3], [5, 5, 5]); plt.savefig(tmp_path / "c.png")
    assert (tmp_path / "c.png").stat().st_size > 0


def test_single_subplots_returns_axes_and_pyplot_targets_current(tmp_path):
    fig, ax = plt.subplots()
    assert isinstance(ax, plt.Axes)
    second = plt.subplot(1, 2, 2)
    assert second in fig.axes
    plt.title("via pyplot"); ax.plot([1, 2]); plt.savefig(tmp_path / "s.svg")
    assert "via pyplot" in (tmp_path / "s.svg").read_text(encoding="utf-8")


def test_subplot_three_digit_shorthand():
    # `subplot(121)` means a 1x2 grid, first cell (matplotlib's shorthand).
    fig = plt.figure()
    ax = plt.subplot(121)
    ax.plot([0, 1], [1, 0])
    plt.subplot(122).plot([0, 1], [0, 1])
    assert fig.grid == (1, 2)
    assert [a.pos for a in fig.axes] == [0, 1]


def test_errorbar_bars_and_caps(tmp_path):
    plt.figure((4, 3))
    plt.errorbar([1, 2, 3], [1, 4, 9], yerr=[0.5, 1.0, 1.5], capsize=3, label="err")
    plt.legend()
    p = tmp_path / "eb.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
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


def test_fill_between_color_does_not_advance_the_cycle():
    fig, ax = plt.subplots()
    ax.fill_between([0, 1], [0, 1], color="red")
    ax.plot([0, 1], [1, 0])
    assert ax.lines[-1]["color"] == plt.rcParams["axes.prop_cycle"].by_key()["color"][0]


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


def test_scatter_stroke_and_dot_markers(tmp_path):
    plt.figure((4, 3))
    plt.scatter([1, 2], [1, 2], marker="x", c="black")
    plt.scatter([1, 2], [2, 1], marker="+", c="red")
    plt.scatter([3], [1.5], marker=".", c="blue")
    p = tmp_path / "mk.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
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
    assert re.search(r'opacity="0\.[34]', p.read_text(encoding="utf-8"))


def test_errorbar_fmt_line_and_xerr_only(tmp_path):
    plt.figure((4, 3))
    plt.errorbar([1, 2], [1, 2], xerr=0.3, fmt="r--")
    p = tmp_path / "ebx.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
    assert s.count("<polyline") >= 3  # two bars plus the connecting line
    assert "#FF0000" in s.upper()


def test_errorbar_negative_errors_are_absolute(tmp_path):
    out = []
    for i, err in enumerate(([0.5, 1.0], [-0.5, -1.0])):
        plt.figure((4, 3))
        plt.errorbar([1, 2], [3, 4], yerr=err)
        p = tmp_path / f"eb{i}.svg"
        plt.savefig(p)
        out.append(p.read_text(encoding="utf-8"))
    assert out[0] == out[1]


def test_mixed_subplots_render(tmp_path):
    fig, axs = plt.subplots(1, 2, figsize=(8, 3))
    x = np.linspace(-2, 2, 20)
    axs[0].contourf(x, x, np.exp(-(x[None, :] ** 2 + x[:, None] ** 2)), levels=4)
    axs[1].scatter(x, x ** 2, s=25, c=x)
    axs[1].errorbar(x, x ** 2, yerr=0.5, fmt="")
    p = tmp_path / "mix.png"
    fig.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_matplotlib_compat_module_namespaces():
    assert plt.transforms.Affine2D is plt.Affine2D
    assert plt.transforms.Bbox is plt.Bbox
    assert plt.path.Path is plt.Path
    assert plt.cbook.flatten([[1], [2, [3]]]) == [1, 2, 3]
    assert plt.font_manager.FontProperties(size=12).get_size() == 12
    assert plt.CapStyle.round == "round" and plt.JoinStyle.miter == "miter"
    assert plt.same_color("red", "#ff0000")
    assert plt.dates.YearLocator is not None and plt.ticker.FixedFormatter is plt.FixedFormatter


def test_fill_draws_a_polygon_per_xy_group(tmp_path):
    plt.rcdefaults()
    fig, ax = plt.subplots()
    ax.fill([0, 1, 2], [0, 1, 0], [0, 1, 2], [2, 3, 2])
    # Matplotlib treats each x, y pair as its own polygon with the next cycle colour.
    assert len(ax.bands) == 2
    assert ax.bands[0]["color"] != ax.bands[1]["color"]
    ax.fill([0, 1], [0, 1], "red")
    assert len(ax.bands) == 3 and ax.bands[2]["color"] == "#ff0000"
    with pytest.raises(TypeError):
        ax.fill([0, 1], [0, 1], [2, 3])
    p = tmp_path / "fill-groups.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_pyplot_backend_registry_and_sca():
    fig, ax = plt.subplots()
    assert plt.get_backend() == "agg"
    plt.switch_backend("svg")
    assert plt.get_backend() == "svg"
    plt.switch_backend("agg")
    labels = plt.get_figlabels()
    assert fig.get_label() in labels
    other = plt.figure()
    assert len(plt.get_figlabels()) == len(labels) + 1
    plt.sca(ax)
    assert plt.gcf() is fig
    assert plt.gcf().gca() is ax
    plt.close(other)
    with pytest.raises(ValueError):
        plt.sca(object())


def test_add_axes_rectangle_is_the_plotting_area(tmp_path):
    cases = [([0.1, 0.1, 0.8, 0.8], (40, 30, 320, 240), False),
             ([0.2, 0.2, 0.6, 0.6], (80, 60, 240, 180), False),
             # A title sits above the axes box, like matplotlib, rather than
             # taking a caption band out of it.
             ([0.1, 0.1, 0.8, 0.8], (40, 30, 320, 240), True)]
    for index, (rect, expected, titled) in enumerate(cases):
        fig = plt.figure((4, 3))
        ax = fig.add_axes(rect)
        ax.set_facecolor("red")
        ax.plot([0, 1], [0, 1])
        if titled:
            ax.set_title("Title")
        p = tmp_path / f"plot_area_{index}.svg"
        fig.savefig(p)
        match = re.search(
            r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" '
            r'opacity="1" fill="#FF0000"',
            p.read_text(encoding="utf-8"),
        )
        assert match is not None
        x, y, w, h = (int(v) for v in match.groups())
        for actual, wanted in zip((x, y, w, h), expected):
            assert abs(actual - wanted) <= 2


def test_svg_gid_after_creation_and_pie_wedges():
    import xml.etree.ElementTree as ET

    from matplotvite.offsetbox import Shadow

    fig, ax = plt.subplots()
    line, = ax.plot([0, 1], [0, 1])
    line.set_gid("moved-line")
    pie = ax.pie([1, 2, 3])
    pie.wedges[1].set_gid("wedge")
    shadow = Shadow(pie.wedges[1], -0.01, -0.01)
    shadow.set_gid("wedge-shadow")
    ax.add_patch(shadow)
    _, ids = ET.XMLID(fig.savefig(None, format="svg"))
    assert ids["moved-line"].tag.endswith("g")
    assert ids["wedge"].tag.endswith("g")
    assert ids["wedge-shadow"].tag.endswith("g")


def test_plot_linestyles_and_width(tmp_path):
    plt.figure((4, 3))
    plt.plot([0, 1, 2], [0, 1, 0], linestyle="--", linewidth=5)
    p = tmp_path / "dash.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
    assert 'stroke-width="5"' in s
    assert s.count("<polyline") > 5  # the dash pattern splits the line


def test_plot_markers_and_colors(tmp_path):
    plt.figure((4, 3))
    plt.plot([0, 1], [0, 1], marker="o", markersize=10, markerfacecolor="red")
    plt.plot([0, 1], [1, 0], marker="x", markeredgecolor="blue")
    p = tmp_path / "markers.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert s.count("<CIRCLE") >= 2
    assert "#FF0000" in s and "#0000FF" in s


def test_plot_fmt_string(tmp_path):
    plt.figure()
    plt.plot([0, 1, 2], [2, 1, 0], "g--")
    p = tmp_path / "fmt.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert "#008000" in s and s.count("<POLYLINE") > 3


def test_plot_alpha_and_bad_drawstyle(tmp_path):
    plt.figure()
    plt.plot([0, 1], [0, 1], alpha=0.3)
    p = tmp_path / "alpha.svg"
    plt.savefig(p)
    assert re.search(r'opacity="0\.[23]', p.read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        plt.plot([0, 1], [0, 1], drawstyle="steps-middle")
    # Repeated data sets are valid; a dangling numeric third arg is not.
    assert len(plt.plot([1], [2], [3], [4])) == 2
    with pytest.raises(TypeError):
        plt.plot([1], [2], [3])


def test_plot_implicit_x_uses_indices():
    fig, ax = plt.subplots()
    line = ax.plot([4, 7, 2])[0]
    assert np.asarray(line.get_xdata()).tolist() == [0.0, 1.0, 2.0]
    assert ax.get_xlim() == pytest.approx((-0.1, 2.1))
    assert ax.get_ylim() == pytest.approx((1.75, 7.25))

    fig, ax = plt.subplots()
    line = ax.plot(np.array([3, 5]), "r--")[0]
    assert np.asarray(line.get_xdata()).tolist() == [0.0, 1.0]
    assert ax.get_ylim() == pytest.approx((2.9, 5.1))


def test_plot_multiple_data_sets_and_line_handles():
    plt.figure()
    lines = plt.plot([0, 1], [1, 0], [0, 1], [0, 1], "r--")
    assert len(lines) == 2
    assert lines[1].get_color() == "#ff0000" and lines[1].get_linestyle() == "--"
    lines[0].set_color("green")
    lines[0].set_label("first")
    lines[0].set_data([0, 2], [2, 0])
    entry = plt.gca().lines[0]
    assert entry["color"] == "#008000" and entry["label"] == "first"
    assert list(entry["x"]) == [0.0, 2.0]
    # y-only plots and their fmt shorthand still produce a single handle.
    line, = plt.plot([3, 1, 2], "o")
    assert line.get_marker() == "o"


def test_plot_step_drawstyles(tmp_path):
    for style in ("steps", "steps-pre", "steps-mid", "steps-post"):
        plt.figure()
        plt.plot([0, 1, 2], [0, 2, 1], drawstyle=style)
        p = tmp_path / f"{style}.png"
        plt.savefig(p)
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_bar_renders_rectangles(tmp_path):
    plt.figure((4, 3))
    plt.bar([1, 2, 3], [3, 1, 2], width=0.5, color="red", edgecolor="black")
    p = tmp_path / "bar.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
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
    assert p.read_text(encoding="utf-8").count("<polyline") >= 2
    with pytest.raises(ValueError):
        plt.bar([1, 2], [1, 2], align="middle")
    with pytest.raises(ValueError):
        plt.bar([1, 2], [1, 2, 3])


def test_bar_updates_limits():
    plt.figure()
    ax = plt.gca()
    ax.bar([2], [5], width=2, bottom=1)
    assert ax.get_xlim() == pytest.approx((0.9, 3.1))
    # The bar baseline is a sticky edge, as in Matplotlib, so it sits on the axis.
    assert ax.get_ylim() == pytest.approx((1.0, 6.25))


def test_fill_between_polygon(tmp_path):
    x = np.linspace(0, 2 * np.pi, 25)
    plt.figure()
    plt.fill_between(x, np.sin(x), 0.5, color="tab:blue", alpha=0.35)
    p = tmp_path / "fb.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert s.count("<POLYGON") >= 1
    assert "#1F77B4" in s
    lo, hi = plt.gca().get_ylim()
    assert lo <= 0.5 and hi >= 1.0
    assert len(re.findall(r'<polygon[^>]*points="', p.read_text(encoding="utf-8"))) == 1


def test_fill_between_where_splits_runs(tmp_path):
    x = np.arange(10.0)
    plt.figure()
    plt.fill_between(x, x, 0, where=(x > 2) & (x < 6), color="red")
    p = tmp_path / "fbw.svg"
    plt.savefig(p)
    pts = re.findall(r'<polygon[^>]*points="([^"]+)"', p.read_text(encoding="utf-8"))
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
    s = p.read_text(encoding="utf-8").upper()
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
    # `barstacked` is Matplotlib's stacked-bar spelling; it draws like `bar`.
    plt.figure()
    counts, edges, _ = plt.hist([data, data * 0.5], bins=4, histtype="barstacked")
    assert len(counts) == 2 and np.all(counts[0] >= 0)


def test_step_and_stairs(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.step([0, 1, 2, 3], [1, 2, 0, 3], where="post", color="red")
    ax.step([0, 1, 2, 3], [1, 2, 0, 3], where="mid", label="mid")
    ax.step([0, 1, 2, 3], [1, 2, 0, 3], where="pre", label="pre")
    ax.stairs([1, 2, 1], edges=[0, 1, 2, 3], fill=True, color="green", alpha=0.25)
    # A filled stairs is a patch: the face takes the colour and alpha, and it
    # does not also register an outline line.
    assert len(ax.bands) == 1
    assert ax.bands[0]["color"] == "#008000"
    assert ax.bands[0]["alpha"] == 0.25
    # Every `where` style must register a line (mid is its own polyline).
    assert [line["drawstyle"] for line in ax.lines[:3]] == [
        "steps-post", "steps-post", "steps-pre"]
    p = tmp_path / "step.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert s.count("<POLYGON") >= 1
    with pytest.raises(ValueError):
        ax.step([0, 1], [0, 1], where="sideways")
    with pytest.raises(ValueError):
        ax.stairs([1, 2], edges=[0, 1])


def test_pyplot_registry_allocates_unique_numbers_from_threads():
    from concurrent.futures import ThreadPoolExecutor

    plt.close("all")
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            figures = list(pool.map(lambda _: plt.figure(), range(24)))
        numbers = sorted(figure.number for figure in figures)
        assert numbers == list(range(1, 25))
        assert plt.get_fignums() == numbers
    finally:
        plt.close("all")


def test_stem_plot(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.stem([1, 3, 2], linefmt="r-", markerfmt="bo", basefmt="-")
    p = tmp_path / "stem.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert "#FF0000" in s and "#0000FF" in s
    assert s.count("<CIRCLE") >= 3
    with pytest.raises(ValueError):
        ax.stem([1, 2], [1])
    ax.stem([1], [2], orientation="horizontal")
    with pytest.raises(ValueError):
        ax.stem([1], orientation="sideways")
    with pytest.raises(TypeError):
        ax.stem([1], [2], [3])


def test_stackplot_layers(tmp_path):
    x = np.arange(4.0)
    plt.figure()
    ax = plt.gca()
    ax.stackplot(x, [1, 1, 1, 1], [1, 2, 1, 2], colors=["red", "green"])
    p = tmp_path / "stack.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert "#FF0000" in s and "#008000" in s
    assert s.count("<POLYGON") >= 2
    # Positive stacks meet the axis at zero, like bars.
    assert ax.get_ylim()[0] == 0.0
    negative = plt.figure()
    negative.gca().stackplot(x, [-1, -1, -1, -1])
    assert negative.gca().get_ylim()[1] == 0.0
    ax.stackplot(x, [1, 1, 1, 1], baseline="sym")
    wiggle = plt.figure()
    wiggle.gca().stackplot(x, [1, 1, 1, 1], baseline="wiggle")
    lo, hi = wiggle.gca().get_ylim()
    assert lo < 0.0 < hi
    with pytest.raises(ValueError):
        ax.stackplot(x, [1, 2])


def test_eventplot_and_broken_barh(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.eventplot([[0.5, 1.5], [1.0]], colors=["red", "green"], linelengths=0.8)
    ax.broken_barh([(0, 1), (2, 0.5)], (2, 0.5), colors="blue")
    p = tmp_path / "events.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert "#FF0000" in s and "#008000" in s and "#0000FF" in s
    assert s.count("<POLYLINE") >= 3
    assert s.count("<RECT") >= 3  # background plus two bars
    lo, hi = ax.get_ylim()
    assert lo <= 0.5 and hi >= 2.5
    with pytest.raises(ValueError):
        ax.eventplot([[1]], orientation="diagonal")


def test_errorbar_markers_and_stem_horizontal(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.errorbar([1, 2], [1, 2], yerr=0.2, fmt="ro")
    ax.stem([1, 2], [3, 4], orientation="horizontal")
    p = tmp_path / "em.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
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
    s = p.read_text(encoding="utf-8")
    assert 'stroke-width="4"' in s and 'stroke-width="5"' in s


def test_hist_step_and_bottom(tmp_path):
    plt.figure()
    ax = plt.gca()
    counts, edges, _ = ax.hist(np.arange(20.0), bins=5, histtype="stepfilled",
                               color="red")
    assert counts.sum() == 20 and len(edges) == 6
    filled = tmp_path / "hfilled.svg"
    plt.savefig(filled)
    assert "<POLYGON" in filled.read_text(encoding="utf-8").upper()
    plt.figure()
    ax = plt.gca()
    ax.hist(np.arange(20.0), bins=5, histtype="step", color="green", bottom=2)
    stepped = tmp_path / "hstep.svg"
    plt.savefig(stepped)
    assert "<POLYLINE" in stepped.read_text(encoding="utf-8").upper()
    assert "#008000" in stepped.read_text(encoding="utf-8").upper()
    plt.figure()
    ax = plt.gca()
    ax.hist(np.arange(5.0), bins=5, bottom=1.0)
    bottomed = tmp_path / "hbottom.svg"
    plt.savefig(bottomed)
    assert "<RECT" in bottomed.read_text(encoding="utf-8").upper()  # bars are rectangles
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
    assert "<POLYGON" in p.read_text(encoding="utf-8").upper()
    ax.stackplot(x, [1, 1, 1], baseline="wiggle")
    lo, hi = ax.get_ylim()
    assert lo < 0.0 < hi


def test_pandas_dataframe_and_series_input():
    pd = pytest.importorskip("pandas")

    df = pd.DataFrame({"x": [1, 2, 3], "y": [3, 1, 2]})
    plt.figure()
    plt.plot(x="x", y="y", data=df)
    assert plt.gca().lines[0]["label"] == "y"
    plt.figure()
    plt.plot("x", "y", data=df)
    assert plt.gca().lines[0]["label"] == "y"
    plt.figure()
    plt.scatter("x", "y", data=df)
    assert plt.gca().scatter_pts[0]["label"] == ""

    series = pd.Series([2, 4, 3], name="temp")
    plt.figure()
    plt.plot(series)
    assert plt.gca().lines[0]["label"] == "temp"

    indexed = pd.DataFrame({"y": [3, 1, 2]},
                           index=pd.date_range("2023-01-01", periods=3, freq="D"))
    plt.figure()
    plt.plot("y", data=indexed)
    ax = plt.gca()
    assert ax._x_date
    assert ax._panel()["ticks"]["xticklabels"][0].startswith("2023-")


def test_module_level_plot_aliases_and_testing_units():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    twin = plt.twinx(ax)
    assert twin._twin_of is ax
    assert plt.FormatStrFormatter("%08.2lf")(1.25) == "00001.25"
    assert plt.testing.km == 1.0 and plt.testing.sec == 1.0
    assert plt.testing.day.convert("sec") == 86400.0
    assert float(plt.testing.Epoch("ET", dt=datetime.datetime(2009, 4, 27))) > 0.0


def test_subplots_squeeze_false_keeps_array():
    fig, axs = plt.subplots(1, 1, squeeze=False)
    assert axs.shape == (1, 1)
    assert axs[0, 0].get_figure() is fig


def test_scatter_marker_png_covers_its_points_area():
    fig, ax = plt.subplots(figsize=(1, 1), dpi=100)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.scatter([0.5], [0.5], s=4, color="blue")
    width, _, rows = decode_png_rgba(fig.savefig(format="png"))
    xs = [x for row in rows for x in range(width)
          if min(row[x * 4], row[x * 4 + 1], row[x * 4 + 2]) < 250]
    # Matplotlib draws s=4 as a 5 px disc (2 pt face plus the 1 pt face-coloured
    # edge); integer plotters circles used to render a bare 2x2 block.
    assert xs and max(xs) - min(xs) + 1 >= 4


def test_pyplot_subplot_accepts_subplotspec():
    fig = plt.figure()
    gs = fig.add_gridspec(1, 2)
    ax = plt.subplot(gs[0, 1])
    assert ax.get_figure() is fig
    assert ax.get_position().x0 > 0.4


def test_hist2d_rejects_oversized_edge_arrays():
    with pytest.raises(ValueError, match="too many edges"):
        plt.hist2d([0, 1], [0, 1], bins=[np.arange(100_002), np.arange(3)])


def test_matplotlib_namespace_and_cycler_shims():
    assert plt.rcParams["axes.prop_cycle"].by_key()["color"]
    assert plt.colors.to_rgb("red") == (1.0, 0.0, 0.0)
    assert plt.mpatches.ArrowStyle.CurveFilledB() is not None
    assert plt.gridspec.GridSpecFromSubplotSpec(1, 1) is not None
    assert plt.mticker.NullLocator() is not None
    assert plt.NullLocator() is not None
    assert plt.cycler(color=["red", "green"]).by_key()["color"] == ["red", "green"]
    assert plt.MouseEvent("motion_notify_event", plt.figure().canvas, 0, 0)._process() is None
    assert plt.gcf().canvas.manager.key_press_handler_id is None
    assert plt.mtransforms.offset_copy(None) is not None
    assert plt.path_effects.withStroke(linewidth=1) is not None
    line = plt.Line2D([0, 1], [1, 0])
    line.set_path_effects([plt.path_effects.withStroke()])
    assert line.get_zorder() == 2


def test_gallery_2d_data_and_stacked_hist():
    import datetime as dt

    fig, ax = plt.subplots()
    x, y = np.meshgrid(np.arange(3), np.arange(2))
    ax.pcolormesh(x, y, np.arange(6).reshape(2, 3))
    dates = np.array([dt.date(2020, 1, 1), dt.date(2020, 1, 2),
                      dt.date(2020, 1, 3)])
    ax.contour(dates, np.arange(3), np.arange(9).reshape(3, 3))

    ax.hist((np.arange(3), np.arange(5)), stacked=True)
    ax.plot("a", "a", "o", data={"a": [1]})
    ax.hexbin("x", "y", data={"x": [0, 1], "y": [0, 1]})
    ax.hist2d("x", "y", data={"x": [0, 1], "y": [0, 1]})
    assert ax.bars


def test_gallery_collection_and_pie_handles():
    fig, ax = plt.subplots()
    pc = plt.mcollections.PathCollection([plt.mpath.Path.unit_circle()])
    ax.add_collection(pc)
    ax.add_patch(plt.Annulus((0, 0), (0.5, 0.3), 0.1))

    pie = ax.pie([1, 2])
    assert pie.wedges and pie.texts is not None
    legend = ax.legend()
    assert legend.legendPatch is not None


def test_hist_overlays_ragged_datasets_and_barstacked(tmp_path):
    plt.rcdefaults()
    rng = np.random.default_rng(3)
    plt.figure()
    counts, edges, handles = plt.hist(
        [rng.normal(size=50), rng.normal(size=20)], bins=4)
    # Different sample sizes are drawn as overlaid histograms, one per data set.
    assert len(counts) == 2 and len(handles) == 2
    assert counts[0].sum() == 50 and counts[1].sum() == 20
    plt.figure()
    stacked, _, _ = plt.hist([rng.normal(size=10), rng.normal(size=10)],
                             bins=3, histtype="barstacked")
    assert len(stacked) == 2
    p = tmp_path / "hist.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_stem_and_specgram_return_matplotlib_containers(tmp_path):
    plt.rcdefaults()
    plt.figure()
    markerline, stemlines, baseline = plt.stem([1.0, 2.0, 0.5])
    assert markerline is not None and baseline is not None
    stemlines.set_linewidth(3)
    assert stemlines[0].get_linewidth() == 3.0
    fig, ax = plt.subplots()
    ax.plot(np.sin(np.linspace(0, 20, 512)))
    pxx, freqs, bins, image = ax.specgram(range(512), NFFT=64, Fs=100)
    assert pxx.shape == (33, 15) and freqs.shape == (33,) and bins.shape == (15,)
    assert image is not None
    p = tmp_path / "specgram.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_polar_bars_and_theta_limits_clip_to_the_wedge():
    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw={"projection": "polar"})
    ax.set_thetalim(0.0, np.pi / 2)
    bars = ax.bar([0.0, np.pi], [0.8, 0.8], width=np.pi / 2,
                  color=["red", "blue"], linewidth=0)
    assert len(bars) == 1
    assert isinstance(bars.patches[0], plt.Polygon)
    ax.plot([0.0, np.pi, 2 * np.pi], [1.0, 1.0, 1.0], color="red", linewidth=5)
    width, height, rows = decode_png_rgba(fig.savefig(format="png"))
    red = sum(rows[y][x * 4] > 150 and rows[y][x * 4 + 1] < 100
              and rows[y][x * 4 + 2] < 100
              for y in range(height) for x in range(width))
    blue = sum(rows[y][x * 4 + 2] > 120 and rows[y][x * 4] < 100
               for y in range(height) for x in range(width))
    assert red > 50
    assert blue < 5


def test_polar_bar_linewidths_accept_one_value_per_wedge(tmp_path):
    fig, ax = plt.subplots(subplot_kw={"projection": "polar"})
    bars = ax.bar([0.0, np.pi / 2], [1.0, 1.0], width=np.pi / 4,
                  color=["red", "blue"], edgecolor="black",
                  linewidth=[2, 4])
    assert [patch.get_linewidth() for patch in bars.patches] == [2.0, 4.0]
    out = tmp_path / "polar_linewidths.png"
    fig.savefig(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_categorical_y_axes_for_barh_and_broken_barh():
    plt.rcdefaults()
    fig, ax = plt.subplots()
    ax.barh({"Tom": 3, "Dick": 5, "Harry": 2}.keys(),
            [3, 5, 2])
    panel = ax._panel()
    assert panel["ticks"]["yticklabels"] == ["Tom", "Dick", "Harry"]
    fig, ax = plt.subplots()
    ax.broken_barh([(110, 10), (150, 10)], ("CPU 1", 0.4), align="center")
    assert ax._panel()["ticks"]["yticklabels"] == ["CPU 1"]


def test_eventplot_accepts_a_2d_array_and_stackplot_dict_values():
    plt.rcdefaults()
    fig, ax = plt.subplots()
    ax.eventplot(np.array([[1, 2, 3], [4, 5, 6]]))
    assert len(ax.lines) == 6
    fig, ax = plt.subplots()
    years = np.arange(4)
    ax.stackplot(years, {"a": [1, 2, 3, 4], "b": [4, 3, 2, 1]}.values(),
                 labels={"a": 1, "b": 2}.keys())
    assert len(ax.bands) == 2


def test_scatter_accepts_a_norm():
    plt.rcdefaults()
    plt.figure()
    handle = plt.scatter([0, 1], [0, 1], c=[1.0, 100.0],
                         norm=plt.colors.LogNorm(vmin=1.0, vmax=100.0))
    assert handle._e["values"].tolist() == pytest.approx([0.0, 1.0])


def test_grouped_bar_returns_one_container_per_series():
    plt.rcdefaults()
    fig, ax = plt.subplots()
    data = {"Bill Depth": (18.35, 18.43, 14.98),
            "Bill Length": (38.79, 48.83, 47.50)}
    result = ax.grouped_bar(data, tick_labels=("Adelie", "Chinstrap", "Gentoo"),
                            group_spacing=1)
    assert len(result.bar_containers) == 2
    assert [len(c) for c in result.bar_containers] == [3, 3]
    assert [c.get_label() for c in result.bar_containers] == [
        "Bill Depth", "Bill Length"]
    for container in result.bar_containers:
        ax.bar_label(container, padding=3)
    assert list(ax.get_xticks()) == pytest.approx([0.0, 1.2, 2.4])


def test_registered_unit_converter_is_used_by_plot(tmp_path):
    """Plots convert registered unit objects and apply their axis info."""
    from matplotvite import units

    class Foo:
        def __init__(self, value): self._value = value
        def value(self, unit=None): return self._value

    class FooConverter(units.ConversionInterface):
        @staticmethod
        def axisinfo(unit, axis):
            return units.AxisInfo(label="foo")

        @staticmethod
        def default_units(x, axis): return None

        @staticmethod
        def convert(obj, unit, axis):
            return [item.value(unit) for item in obj]

    units.registry[Foo] = FooConverter()
    try:
        fig, ax = plt.subplots()
        line, = ax.plot([Foo(1), Foo(2)], [3, 4])
        assert line.get_xdata().tolist() == [1.0, 2.0]
        assert ax.get_xlabel() == "foo"
        fig.savefig(tmp_path / "units.png")
    finally:
        units.registry.pop(Foo, None)
