"""Axes statistics: box, whisker and violin plots."""

import datetime
import re

import matplotvite as plt
import numpy as np
import pytest
from plt_helpers import (
    _axes_face_box,
    _image_box,
)
from png_utils import decode_png_rgba


def test_tight_bbox_crops_whitespace(tmp_path):
    plt.figure((4, 3)); plt.plot([1, 2, 3])
    plain, tight = tmp_path / "plain.png", tmp_path / "tight.png"
    plt.savefig(plain); plt.savefig(tight, bbox_inches="tight")
    assert int.from_bytes(tight.read_bytes()[16:20], "big") < 400

    svg = tmp_path / "tight.svg"
    plt.savefig(svg, bbox_inches="tight")
    assert 'viewBox="0 0 400 300"' not in svg.read_text(encoding="utf-8")

    pdf = tmp_path / "tight.pdf"
    plt.savefig(pdf, bbox_inches="tight")
    b = pdf.read_bytes()
    m = re.search(rb"MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", b)
    assert m, "missing MediaBox"
    w, h = (float(v) for v in m.groups())
    assert w < 288 and h < 216


def test_tight_bbox_with_colored_background(tmp_path):
    fig = plt.figure((4, 3), facecolor="red")
    fig.gca().plot([1, 2, 3])
    tight = tmp_path / "tight-red.png"
    fig.savefig(tight, bbox_inches="tight")
    assert int.from_bytes(tight.read_bytes()[16:20], "big") < 400

    # The background must not force the vector tight box back to full canvas.
    svg = tmp_path / "tight-red.svg"
    fig.savefig(svg, bbox_inches="tight")
    text = svg.read_text(encoding="utf-8")
    assert 'viewBox="0 0 400 300"' not in text
    assert 'fill="#FF0000"' in text


def test_text_bbox_draws_axes_and_figure_frames(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    text = ax.text(0.2, 0.5, "Nb KP=13743",
                   bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                             edgecolor="gray"))
    assert text.get_bbox_patch() is not None
    assert ax.texts[-1].get_bbox()["rounded"] is True
    fig.text(0.1, 0.9, "figure", bbox=dict(boxstyle="square", facecolor="white",
                                           edgecolor="gray"))
    p = tmp_path / "text-bbox.svg"
    fig.savefig(p)
    svg = p.read_text(encoding="utf-8")
    assert svg.count("#808080") >= 2
    assert svg.count("#FFFFFF") >= 2


def test_aspect_numeric_halves_the_box(tmp_path):
    plt.figure((4, 3))
    plt.imshow(np.zeros((10, 10)), aspect=2.0)
    p = tmp_path / "a2.svg"
    plt.savefig(p)
    w, h = _image_box(p)
    assert abs(w / h - 0.5) < 0.1


def test_axis_equal_bends_the_data_limits_instead_of_the_box(tmp_path):
    """`axis("equal")` fills the panel; `set_aspect` still shrinks the box."""
    def render(adjustable):
        fig = plt.figure((4, 3))
        ax = plt.gca()
        ax.set_facecolor("#00ff00")
        ax.plot([-2.8, 2.8], [-2.2, 2.2])
        ax.axis("equal")
        if adjustable is not None:
            ax.set_aspect("equal", adjustable=adjustable)
        p = tmp_path / f"{adjustable}.png"
        fig.savefig(p)
        _, _, rows = decode_png_rgba(p.read_bytes())
        return _axes_face_box(rows)

    dw, dh = render("datalim")
    bw, bh = render("box")
    assert dw > bw  # datalim keeps the wide area; box mode narrows it
    assert abs(dw / dh - 1.58) < 0.2
    assert abs(bw / bh - 1.27) < 0.12


def test_axes_violin_draws_from_precomputed_stats():
    fig, ax = plt.subplots()
    stats = [dict(coords=np.linspace(0.0, 1.0, 21),
                  vals=np.linspace(1.0, 0.0, 21),
                  mean=0.5, median=0.5, min=0.0, max=1.0,
                  quantiles=[0.25, 0.75])]
    out = ax.violin(stats, widths=0.5, showmeans=True, showmedians=True)
    assert set(out) == {"bodies", "cmeans", "cmaxes", "cmins", "cbars",
                        "cmedians", "cquantiles"}
    assert len(out["bodies"]) == 1 and len(out["cquantiles"]) == 2
    body = out["bodies"][0].get_paths()[0]
    assert max(body["x"]) <= 1.25 + 1e-9 and min(body["x"]) >= 0.75 - 1e-9
    assert out["bodies"][0].get_facecolor()

    horizontal = ax.violin(stats, orientation="horizontal", side="low",
                           showextrema=False)
    assert set(horizontal) == {"bodies", "cquantiles"}
    assert len(horizontal["bodies"]) == 1 and len(horizontal["cquantiles"]) == 2

    with pytest.raises(ValueError):
        ax.violin(stats, positions=[1, 2])
    with pytest.raises(ValueError):
        ax.violin(stats, widths=[0.5, 0.5])
    with pytest.raises(ValueError):
        ax.violin(stats, orientation="sideways")
    with pytest.raises(ValueError):
        ax.violin(stats, side="up")
    with pytest.raises(TypeError, match=r"np\.datetime64"):
        ax.violin(stats, positions=[np.datetime64("2020-01-01")], widths=[0.5])
    with pytest.raises(TypeError, match="timedelta"):
        ax.violin(stats, positions=[datetime.datetime(2020, 1, 1)], widths=0.75)


def test_axes_violin_accepts_datetime_coordinates():
    fig, ax = plt.subplots()
    coords = [datetime.datetime(2023, 2, 10), datetime.datetime(2023, 5, 18),
              datetime.datetime(2023, 6, 6)]
    ax.violin([dict(coords=coords, vals=[0.1, 0.5, 0.2], mean=coords[1],
                    median=coords[1], min=coords[0], max=coords[-1],
                    quantiles=coords)])
    lo, hi = ax.get_ylim()
    assert lo < hi


def test_pyplot_box_toggles_frame_state():
    fig, ax = plt.subplots()
    assert ax.get_frame_on()
    plt.box(False)
    assert ax.get_frame_on() is False
    plt.box()
    assert ax.get_frame_on() is True
    plt.box(False)
    assert ax.get_frame_on() is False


def test_axes_violin_renders_pixels():
    # A density skewed towards the low end: the body is widest at coord 2, so
    # the pixel geometry tells vertical (widest row near the bottom) from
    # horizontal (widest column near the left) without reading axis ticks.
    coords = np.linspace(0.0, 10.0, 41)
    stats = [dict(coords=coords, vals=np.exp(-((coords - 2.0) ** 2)),
                  mean=2.0, median=2.0, min=0.0, max=10.0)]

    def red_mask(fig):
        width, height, rows = decode_png_rgba(fig.savefig(format="png"))
        image = np.frombuffer(b"".join(rows), dtype=np.uint8).reshape(height, width, 4)
        red = ((image[..., 0] > 200) & (image[..., 1] < 80)
               & (image[..., 2] < 80) & (image[..., 3] > 0))
        assert red.sum() > 500, "violin body did not render"
        return image, red

    fig, ax = plt.subplots()
    ax.violin(stats, widths=0.5, facecolor="red", showextrema=False)
    image, red = red_mask(fig)
    assert np.argmax(red.sum(axis=1)) > 0.5 * image.shape[0]
    ys, xs = np.nonzero(red)
    assert xs.min() > 0 and xs.max() < image.shape[1] - 1

    fig, ax = plt.subplots()
    ax.violin(stats, widths=0.5, facecolor="red", showextrema=False,
              orientation="horizontal")
    image, red = red_mask(fig)
    assert np.argmax(red.sum(axis=0)) < 0.5 * image.shape[1]

    fig, ax = plt.subplots()
    ax.violin(stats, widths=0.5, facecolor="red", linecolor="black",
              showmedians=True, showextrema=False)
    image, red = red_mask(fig)
    ys, xs = np.nonzero(red)
    body = image[ys.min():ys.max() + 1, xs.min():xs.max() + 1, :3]
    assert ((body < 60).all(axis=2)).sum() > 5, "median line missing inside body"


def test_axes_grid1_size_divider_and_hbox_divider(tmp_path):
    from matplotvite.mpl_toolkits.axes_grid1 import Divider, HBoxDivider, Size

    fig = plt.figure((4, 4))
    rect = (0.1, 0.1, 0.8, 0.8)
    div = Divider(fig, rect, [Size.Fixed(1), Size.Fixed(0.5), Size.Fixed(1.5)],
                  [Size.Fixed(1), Size.Fixed(0.5)], aspect=False)
    left = fig.add_axes(rect, axes_locator=div.new_locator(nx=0, ny=0))
    right = fig.add_axes(rect, axes_locator=div.new_locator(nx=2, ny=0))
    assert left.get_position().x0 < right.get_position().x0
    assert left.get_position().y0 == right.get_position().y0
    fig.savefig(tmp_path / "divider.png")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(4, 3))
    ax1.imshow(np.arange(20).reshape(4, 5))
    ax2.imshow(np.arange(20).reshape(5, 4))
    hbox = HBoxDivider(fig, 111,
                       horizontal=[Size.AxesX(ax1), Size.Fixed(0.5), Size.AxesX(ax2)],
                       vertical=[Size.AxesY(ax1), Size.Scaled(1), Size.AxesY(ax2)])
    ax1.set_axes_locator(hbox.new_locator(0))
    ax2.set_axes_locator(hbox.new_locator(2))
    first, second = ax1.get_position(), ax2.get_position()
    assert abs(first.height - second.height) < 1e-6
    assert first.width > second.width
    fig.savefig(tmp_path / "hbox.png")


def test_bbox_connector_shims():
    from matplotvite.mpl_toolkits.axes_grid1.inset_locator import (
        BboxConnector,
        BboxConnectorPatch,
        BboxPatch,
    )

    fig, ax = plt.subplots()
    first = plt.Bbox.from_extents(0.0, 0.0, 1.0, 1.0)
    second = plt.Bbox.from_extents(2.0, 2.0, 4.0, 3.0)
    connector = BboxConnector(first, second, loc1=1, loc2=2)
    assert connector.get_xy().shape == (2, 2)
    area = BboxConnectorPatch(first, second, loc1a=1, loc2a=1, loc1b=3, loc2b=3)
    assert area.get_xy().shape == (4, 2)
    patch = BboxPatch(second)
    assert patch.get_width() == 2.0 and patch.get_height() == 1.0
    ax.add_patch(patch)
    assert fig is not None


def test_cbook_boxplot_stats_feed_bxp(tmp_path):
    import numpy as np
    from matplotvite import cbook

    stats = cbook.boxplot_stats(np.array([[0, 10, 20], [1, 11, 21],
                                          [2, 12, 22], [3, 13, 23],
                                          [100, 14, 24]]), labels=["A", "B", "C"])
    assert [item["label"] for item in stats] == ["A", "B", "C"]
    assert stats[0]["med"] == pytest.approx(2.0)
    assert stats[0]["fliers"] == [100.0]

    fig, ax = plt.subplots()
    ax.bxp(stats)
    path = tmp_path / "bxp_stats.png"
    fig.savefig(path)
    assert path.stat().st_size > 0


def test_boxplot_stats_and_labels(tmp_path):
    data = [np.arange(10.0), np.arange(5.0) * 2.0]
    plt.figure()
    ax = plt.gca()
    result = ax.boxplot(data, labels=["a", "b"], patch_artist=True, showmeans=True)
    assert set(result) == {"boxes", "medians", "whiskers", "caps", "fliers", "means"}
    assert len(result["boxes"]) == 2
    assert len(result["medians"]) == 2
    assert len(result["whiskers"]) == 4 and len(result["caps"]) == 4
    assert result["medians"][0].get_ydata()[0] == np.median(data[0])
    assert result["means"][1].get_ydata()[0] == np.mean(data[1])
    assert [t.get_text() for t in ax.get_xticklabels()] == ["a", "b"]
    p = tmp_path / "box.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert s.count("<POLYLINE") >= 5  # median, two whiskers and two caps
    assert "#FF7F0E" in s


def test_boxplot_uses_matplotlib_style_defaults(tmp_path):
    plt.figure()
    ax = plt.gca()
    result = ax.boxplot([[1.0, 2.0, 3.0, 4.0, 5.0]], patch_artist=True)
    # Filled with C0 but edged, whiskered and capped in black, as Matplotlib.
    assert result["boxes"][0].get_facecolor() == [plt._CYCLE[0]]
    assert result["boxes"][0].get_edgecolor() == "#000000"
    cap = result["caps"][0]
    xs = cap.get_xdata()
    assert xs.max() - xs.min() == pytest.approx(0.25)  # half the 0.5 box width
    p = tmp_path / "box_style.svg"
    plt.savefig(p)
    assert "#000000" in p.read_text(encoding="utf-8").upper()


def test_boxplot_horizontal_notch_and_fliers(tmp_path):
    data = [np.array([0.0, 1.0, 2.0, 3.0, 100.0]), np.array([2.0, 3.0, 4.0, 5.0, 6.0])]
    plt.figure()
    ax = plt.gca()
    result = ax.boxplot(data, orientation="horizontal", notch=True, sym="r+")
    assert result["fliers"][0] is not None and result["fliers"][1] is None
    assert len(result["boxes"][0].get_xdata()) == 13  # notched outline
    assert ax.get_yticklabels()[0].get_text() == "1"
    p = tmp_path / "boxh.svg"
    plt.savefig(p)
    assert "#FF0000" in p.read_text(encoding="utf-8").upper()
    with pytest.raises(ValueError):
        ax.boxplot(data, orientation="diagonal")
    with pytest.raises(ValueError):
        ax.boxplot([])


def test_boxplot_single_and_hidden_parts(tmp_path):
    plt.figure()
    result = plt.boxplot([1, 2, 3, 4], showfliers=False, showcaps=False,
                         showbox=False, autorange=True)
    assert result["fliers"] == [None]
    assert result["boxes"] == [] and result["caps"] == []
    assert result["medians"][0].get_ydata()[0] == 2.5
    p = tmp_path / "boxsingle.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_boxplot_draws_default_outliers(tmp_path):
    data = [np.array([0.0, 1.0, 2.0, 3.0, 4.0, 100.0])]
    plt.figure()
    ax = plt.gca()
    result = ax.boxplot(data)
    # `sym=None` means the default flier, not "hide them".
    assert result["fliers"][0] is not None
    assert np.allclose(result["fliers"][0].get_ydata(), [100.0])
    assert ax.get_ylim()[1] > 100.0
    hidden = ax.boxplot(data, sym="")
    assert hidden["fliers"] == [None]
    off = ax.boxplot(data, showfliers=False)
    assert off["fliers"] == [None]
    p = tmp_path / "box_fliers.svg"
    plt.savefig(p)
    # Matplotlib's default flier is a hollow circle with a black 1 pt edge.
    circles = [line for line in p.read_text(encoding="utf-8").splitlines() if "<circle" in line]
    assert circles and all('fill="none"' in line.lower() for line in circles)


def test_violinplot_bodies_and_stats(tmp_path):
    rng = np.random.default_rng(3)
    data = [rng.normal(size=80), rng.normal(2.0, 0.5, size=60)]
    plt.figure()
    ax = plt.gca()
    result = ax.violinplot(data, positions=[2.0, 4.0], widths=[0.8, 0.4],
                           showmeans=True, showmedians=True)
    assert set(result) == {"bodies", "cmeans", "cmaxes", "cmins", "cbars"}
    assert len(result["bodies"]) == 2
    assert len(result["cmins"]) == len(result["cmaxes"]) == len(result["cbars"]) == 2
    assert result["bodies"][0].get_facecolor() == plt._CYCLE[0]
    p = tmp_path / "violin.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert s.count("<POLYGON") >= 2
    assert s.count("<POLYLINE") >= 6


def test_violinplot_uses_one_body_colour_and_body_lines(tmp_path):
    plt.figure()
    ax = plt.gca()
    result = ax.violinplot([np.linspace(0, 1, 10), np.linspace(0, 2, 10)])
    assert [b.get_facecolor() for b in result["bodies"]] == [plt._CYCLE[0]] * 2
    assert result["bodies"][0].get_alpha() == pytest.approx(0.3)
    for handle in (result["cmaxes"][0], result["cmins"][1], result["cbars"][0]):
        assert handle.get_color() == plt._CYCLE[0]
    p = tmp_path / "violin_style.png"
    plt.savefig(p)
    assert p.stat().st_size > 0


def test_violinplot_bodies_have_no_outline_unless_asked(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.violinplot([np.linspace(0, 1, 10)], showextrema=False)
    plain = tmp_path / "violin_plain.svg"
    plt.savefig(plain)

    plt.figure()
    ax = plt.gca()
    ax.violinplot([np.linspace(0, 1, 10)], showextrema=False, edgecolor="red")
    outlined = tmp_path / "violin_outline.svg"
    plt.savefig(outlined)

    bodies = [
        line for line in plain.read_text(encoding="utf-8").splitlines()
        if "<polygon" in line
    ]
    assert bodies and all("stroke" not in line for line in bodies)
    assert any(
        "<polyline" in line.lower() and "#ff0000" in line.lower()
        for line in outlined.read_text(encoding="utf-8").splitlines()
    )


def test_violinplot_body_stays_within_the_data_range(tmp_path):
    data = [np.array([-2.7, -1.0, 0.2, 1.1, 2.4, 3.0, 4.8, 6.3])]
    plt.figure()
    ax = plt.gca()
    result = ax.violinplot(data)
    lo, hi = float(data[0].min()), float(data[0].max())
    ys = result["bodies"][0].get_paths()[0]["y"]
    assert ys.min() >= lo - 1e-9 and ys.max() <= hi + 1e-9
    margin = 0.05 * (hi - lo)
    y0, y1 = ax.get_ylim()
    assert lo - margin <= y0 and y1 <= hi + margin
    p = tmp_path / "violin_range.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_violinplot_horizontal_side_and_validation(tmp_path):
    data = [np.array([1.0, 2.0, 3.0, 4.0, 5.0])]
    plt.figure()
    ax = plt.gca()
    result = ax.violinplot(data, orientation="horizontal", side="low",
                           quantiles=[25, 75], bw_method=0.4)
    assert len(result["cquantiles"]) == 2
    assert result["bodies"][0].get_paths()[0]["x"].size > 2
    p = tmp_path / "violinh.svg"
    plt.savefig(p)
    assert p.read_text(encoding="utf-8").upper().count("<POLYGON") >= 1
    with pytest.raises(ValueError):
        ax.violinplot(data, side="middle")
    with pytest.raises(ValueError):
        ax.violinplot(data, orientation="diagonal")
    with pytest.raises(ValueError):
        ax.violinplot([[]])


def test_pyplot_violinplot_shim(tmp_path):
    plt.figure()
    result = plt.violinplot([1.0, 2.0, 3.0], showextrema=False)
    assert result["cmins"] == [] and len(result["bodies"]) == 1
    p = tmp_path / "violin_shim.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_violinplot_accepts_per_dataset_quantiles(tmp_path):
    plt.figure()
    plt.violinplot([np.arange(10.0), np.arange(10.0)[::-1]],
                   positions=[1, 2], quantiles=[[0.1], [0.9]])
    p = tmp_path / "violin.png"
    plt.savefig(p)
    assert p.stat().st_size > 0


def test_bxp_accepts_precomputed_statistics(tmp_path):
    stats = [dict(med=1.0, q1=0.5, q3=1.5, whislo=0.0, whishi=2.0,
                  fliers=[3.0], mean=1.1, label="A")]
    fig, ax = plt.subplots()
    result = ax.bxp(stats, showmeans=True)
    assert len(result["boxes"]) == 1
    assert len(result["medians"]) == 1
    p = tmp_path / "bxp.png"
    fig.savefig(p)
    assert p.stat().st_size > 0


def test_patch_boxstyle_and_artist_set(tmp_path):
    """Artist code calls BoxStyle(...) and patch.set(...)/line.set(...)."""
    style = plt.patches.BoxStyle("Round", pad=0.02)
    assert style is not None
    patch = plt.Rectangle((0, 0), 1, 1)
    patch.set(color="red", lw=3)
    assert patch.get_linewidth() == 3
    assert patch.get_color() == "#ff0000"
    plt.figure()
    line, = plt.plot([0, 1], [1, 0])
    line.set(color="blue", lw=2, ls="--")
    assert line.get_linewidth() == 2
    plt.savefig(tmp_path / "artist_set.png")


def test_offsetbox_containers_accept_artists(tmp_path):
    """Anchored offset boxes can hold text, drawing areas and image boxes."""
    from matplotvite import (
        AnchoredOffsetbox,
        AnnotationBbox,
        Circle,
        DrawingArea,
        OffsetImage,
        TextArea,
        VPacker,
    )

    fig, ax = plt.subplots()
    area = DrawingArea(40, 20)
    area.add_artist(Circle((10, 10), 5, facecolor="C0"))
    box = AnchoredOffsetbox(child=VPacker(children=[TextArea("label"), area]),
                            loc="upper left")
    box.patch.set_boxstyle("round,pad=0.,rounding_size=0.2")
    ax.add_artist(box)
    image = OffsetImage(np.zeros((2, 2)), zoom=2)
    image.image.axes = ax
    ax.add_artist(AnnotationBbox(image, xy=(0.5, 0.5), xybox=(10, 10)))
    fig.savefig(tmp_path / "offsetbox.png")
