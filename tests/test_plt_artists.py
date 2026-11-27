"""Artist, patch, collection, path and style behaviour."""


import matplotvite as plt
import numpy as np
import pytest
from plt_helpers import (
    _FakeCollection,
    _FakeRect,
    _mean_abs_channel_diff,
    _png_colour_counts,
)
from png_utils import decode_png_rgba


def test_direct_and_svg_png_paths_preserve_every_panel():
    def render(force_svg):
        fig, axs = plt.subplots(2, 2, figsize=(6, 5))
        for i, (ax, colour) in enumerate(zip(axs.flat, ("red", "blue", "green", "orange"))):
            ax.plot([0, 1, 2], [i, i + 2, i + 1], color=colour, linewidth=3)
            ax.set_title(f"panel {i}")
        if force_svg:
            # A figure decoration makes the renderer choose the SVG path.
            fig.text(0, 0, "")
        return decode_png_rgba(fig.savefig(format="png"))

    direct = render(False)
    svg = render(True)
    assert direct[:2] == svg[:2]
    direct_counts = _png_colour_counts(direct[2])
    svg_counts = _png_colour_counts(svg[2])
    for colour in ("red", "blue", "green", "orange"):
        assert direct_counts[colour] > 20 and svg_counts[colour] > 20
    # Compare pixels, not colour totals: moving a panel by a pixel keeps the
    # totals but shifts every line, which the mean difference catches. The SVG
    # path rasterises through resvg, so edges and text differ by anti-aliasing;
    # this four-panel figure measures about 10.8 on a 0-255 scale now that every
    # tick label carries the axis-wide decimals.
    assert _mean_abs_channel_diff(direct[2], svg[2]) <= 12.0


def test_bad_path():
    plt.figure(); plt.plot([1, 2]);
    with pytest.raises(OSError):
        plt.savefig("/nonexistent/dir/x.png")


def test_compat_noops():
    plt.figure()
    plt.plot([1, 2], [2, 1])
    assert plt.show() is None and plt.draw() is None and plt.pause(0.01) is None
    plt.ion()
    plt.ioff()
    assert plt.axes() is plt.gca()


def test_gallery_path_patch_and_subfigure_shims():
    bbox = plt.mtransforms.Bbox.from_bounds(0.0, 0.0, 1.0, 1.0)
    path = plt.Path([[0.0, 0.0], [2.0, 2.0]])
    assert path.intersects_bbox(bbox)
    assert plt.Path.NUM_VERTICES_FOR_CODE[plt.Path.CURVE4] == 3
    compound = plt.Path.make_compound_path_from_polys(
        np.array([[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]]))
    assert len(compound.vertices) == 5

    ellipse = plt.Ellipse((0.0, 0.0), 4.0, 2.0, angle=30.0)
    assert len(ellipse.get_co_vertices()) == 2

    fig, ax = plt.subplots()
    pie = ax.pie([1.0, 2.0])
    assert pie.wedges[0].theta2 > pie.wedges[0].theta1
    scatter = ax.scatter([0.0, 1.0], [1.0, 0.0], c=[0.0, 1.0])
    handles, labels = scatter.legend_elements(num=2)
    assert len(handles) == len(labels) == 2
    scatter.set_urls(["https://example.com", None])
    assert scatter.get_urls()[0] == "https://example.com"
    assert scatter.cmap.name == "viridis"
    patch = plt.PathPatch(path)
    patch.sticky_edges.y.append(0)
    ax.add_patch(patch)
    ax.set_rasterization_zorder(0)
    ax.ticklabel_format(useOffset=False)
    ax.xaxis.get_minor_locator().set_params(subs=[2, 3])

    subfigs = fig.subfigures(1, 2)
    assert subfigs[0].subfigures(1, 1).figure is fig
    assert ax in fig.findobj(plt.Axes)
    annotation = ax.annotate("note", (0.5, 0.5))
    assert annotation.get_bbox_patch() is not None
    assert annotation.arrow_patch is not None
    assert [style.name for style in plt.CapStyle] == ["butt", "round", "projecting"]
    assert plt.HandlerTuple(ndivide=None) is not None


def test_projection_compatibility(tmp_path):
    from matplotvite.mpl_toolkits.mplot3d import Axes3D

    fig = plt.figure()
    ax3 = fig.add_subplot(projection="3d")
    assert isinstance(ax3, plt.Axes3D) and Axes3D is plt.Axes3D
    ax3.set_box_aspect((2, 1, 1))
    ax3.set_zlim3d(0, 3)
    assert ax3.get_zlim3d() == (0.0, 3.0)
    collection = plt.mcollections.PolyCollection([[[0, 0], [0, 1], [1, 1]]])
    ax3.add_collection3d(collection, zs=[0], zdir="y")

    skew = fig.add_subplot(projection="skewx")
    skew.axvline(0)

    polar = fig.add_axes([0.1, 0.1, 0.5, 0.5], polar=True)
    assert isinstance(polar, plt.PolarAxes)
    polar.set_theta_direction("clockwise")
    polar.set_rscale("log")
    polar.set_rlim(1, 1000)
    assert polar.get_rscale() == "log"
    polar.xaxis.get_major_locator().base.set_params(steps=[1, 2, 5])

    out = tmp_path / "projections.png"
    fig.savefig(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_path_helpers_and_event_collection_roundtrip(tmp_path):
    path = plt.Path.unit_rectangle().deepcopy()
    path.vertices *= 2.0
    compound = plt.Path.make_compound_path(path, plt.Path.unit_circle())
    assert len(compound.vertices) == len(path.vertices) + 65
    assert len(compound.codes) == len(compound.vertices)
    transformed = plt.mpath.TransformedPath(compound, plt.mtransforms.Affine2D())
    assert transformed.get_path() is compound

    coll = plt.mcollections.EventCollection(
        [0.0, 1.0], orientation="horizontal", color=[1, 0, 0, 1], linewidth=2)
    assert np.array_equal(coll.get_color(), [1, 0, 0, 1])
    assert all(np.array_equal(c, [1, 0, 0, 1]) for c in coll.get_colors())
    coll.add_positions([2.0])
    assert np.array_equal(coll.get_positions(), [0.0, 1.0, 2.0])
    coll.set(linestyle="dashed", linewidth=5)
    assert coll.get_linewidth() == 5.0
    coll.set_color([0, 1, 1, 1])
    assert np.array_equal(coll.get_color(), [0, 1, 1, 1])

    fig, ax = plt.subplots()
    ax.add_collection(coll)
    fig.add_artist(plt.Rectangle((0, 0), 1, 1), clip=True)
    fig.savefig(tmp_path / "path-event.png")


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
    s = p.read_text(encoding="utf-8")
    assert "T" in s and "t" in s and "v" in s
    with pytest.raises(AttributeError):
        ax.set(nonexistent=1)


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
    assert ax.margins(0.1) == (0.1, 0.1) and ax.autoscale() is None
    assert ax.set_clip_on(False) is None and ax.set_path_effects([]) is None


def test_axes_pan_and_pick_dispatch():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    before = ax.get_xlim()
    ax.start_pan(100, 100, 1)
    ax.drag_pan(1, None, 200, 100)
    ax.end_pan()
    assert ax.get_xlim()[0] < before[0]
    dragged = ax.get_xlim()
    ax.drag_pan(1, None, 300, 100)
    assert ax.get_xlim() == dragged
    assert ax.pick(None) == []


def test_figure_interactive_stubs_and_pick():
    fig, ax = plt.subplots()
    assert fig.show() is None
    assert fig.waitforbuttonpress() is None
    with pytest.warns(RuntimeWarning, match="ginput"):
        assert fig.ginput() is None
    assert fig.pick(None) == []


def test_axes_set_accepts_artist_properties():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.set(label="main", zorder=2, gid="axes", path_effects=[], rasterized=True)
    assert fig is not None


def test_svg_emits_gids_for_lines_and_patches():
    import xml.etree.ElementTree as ET

    fig, ax = plt.subplots()
    ax.plot([0, 1], [1, 0], gid="line-one")
    ax.add_patch(plt.Rectangle((0.2, 0.2), 0.3, 0.3, gid="rect-one"))
    _, ids = ET.XMLID(fig.savefig(None, format="svg"))
    assert ids["line-one"].tag.endswith("g")
    assert ids["rect-one"].tag.endswith("g")


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
    assert fig.get_layout_engine() is not None
    fig.get_layout_engine().set(hspace=0.15)
    fig.set_layout_engine("constrained")
    assert fig.get_layout_engine().name == "constrained"


def test_m16_api_compatibility():
    cmap = plt.get_cmap("viridis")
    copied = cmap.copy()
    assert copied.name == cmap.name
    copied.set_bad("red")
    copied.set_under("blue")
    copied.set_over("green")

    norm = plt.mcolors.TwoSlopeNorm(vcenter=0.0, vmin=-2.0, vmax=2.0)
    assert norm(-2.0) == pytest.approx(0.0)
    assert norm(0.0) == pytest.approx(0.5)
    assert norm(2.0) == pytest.approx(1.0)

    fig, ax = plt.subplots()
    assert ax.xaxis.axes is ax and ax.yaxis.axes is ax
    old = plt.rcParams["text.parse_math"]
    try:
        plt.rcParams["text.parse_math"] = False
        ax.set_title("$x^2$")
        assert ax.get_title() == "$x^2$"
    finally:
        plt.rcParams["text.parse_math"] = old


def test_datetime64_and_date_inputs_across_artists(tmp_path):
    from datetime import date, datetime

    dates = np.array(["2021-03-01", "2021-04-01", "2021-05-01"], dtype="datetime64[D]")
    plt.figure((4, 3))
    ax = plt.gca()
    ax.scatter(dates, [1, 4, 9])
    ax.bar(dates, [1, 2, 3], alpha=0.5)
    ax.axvline(datetime(2021, 3, 15))
    ax.axvspan(datetime(2021, 3, 20), datetime(2021, 4, 10), alpha=0.2)
    ax.fill_between(dates, [1, 2, 3], 0, alpha=0.2)
    ax.pcolormesh([datetime(2021, 3, 1), datetime(2021, 4, 1), datetime(2021, 5, 1)],
                  [0, 1, 2], np.zeros((2, 2)))
    ax.text(datetime(2021, 3, 1), 1, "start")
    assert ax._x_date
    labels = ax._panel()["ticks"]["xticklabels"]
    assert labels and labels[0].startswith("2021-")
    p = tmp_path / "date-artists.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    lo, hi = plt.gca().get_xlim()
    assert lo <= date(2021, 3, 1).toordinal() <= hi
    assert lo <= date(2021, 5, 1).toordinal() <= hi


def test_add_patch_renders_and_expands_limits(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    rect = _FakeRect(2, 3, 4, 5)
    assert ax.add_patch(rect) is rect
    assert ax.get_xlim()[1] >= 6 and ax.get_ylim()[1] >= 8
    panel = ax._panel()
    assert panel["patches"][0]["kind"] == "rect"
    svg = fig.savefig(None, format="svg").decode().upper()
    assert "#FF0000" in svg
    p = tmp_path / "patch.png"
    fig.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_add_collection_renders_offsets(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    coll = _FakeCollection([[0, 1], [2, 3]], [(0, 0, 1, 1), (1, 0, 0, 1)], [25, 100])
    assert ax.add_collection(coll) is coll
    assert ax._panel()["collections"][0]["points"] == [0.0, 1.0, 2.0, 3.0]
    assert ax.get_xlim()[1] >= 2 and ax.get_ylim()[1] >= 3
    svg = fig.savefig(None, format="svg").decode().upper()
    assert "#0000FF" in svg and "#FF0000" in svg


def test_dense_collection_uses_raster_layer_only_for_raster_output(tmp_path):
    rng = np.random.default_rng(11)
    offsets = rng.normal(size=(5000, 2))
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.add_collection(_FakeCollection(offsets, [(0, 0, 1, 1)], [16]))
    png = fig.savefig(None, format="png")
    svg = fig.savefig(None, format="svg")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    # SVG stays vector, and the raster PNG must not reuse its cached fragment.
    assert svg.lower().count(b"<circle") >= 5000
    assert len(png) * 4 < len(svg)


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
    assert "#FF0000" in p.read_text(encoding="utf-8").upper()
    assert "#008000" in p.read_text(encoding="utf-8").upper()
    with pytest.raises(ValueError):
        ax.set_prop_cycle()


def test_patch_classes_and_axes_compatibility_shims(tmp_path):
    fig, ax = plt.subplots()
    for patch in (plt.Rectangle((0, 0), 1, 2, facecolor="red"),
                  plt.Circle((2, 3), 1, facecolor="blue"),
                  plt.Ellipse((4, 5), 2, 1, angle=30),
                  plt.Polygon([[0, 0], [1, 1], [0, 1]])):
        ax.add_patch(patch)
    ax.set_xlim(right=10)
    ax.set_ylim(top=10)
    assert ax.get_xlim()[1] == 10 and ax.get_ylim()[1] == 10
    ax.spines["top"].set_visible(False)
    ax.xaxis.set_label_text("x")
    ax.text(0.5, 0.5, "note", rotation=45, size="large", va="center_baseline")
    assert ax.get_xlabel() == "x"
    assert ax.get_figure(root=True) is fig
    assert fig.canvas.get_width_height()[0] > 0
    fig.canvas.draw()
    p = tmp_path / "patches.png"
    fig.savefig(p)
    assert p.stat().st_size > 0


def test_path_codes_and_regular_shapes():
    assert plt.Path.MOVETO == 1 and plt.Path.CLOSEPOLY == 79
    assert len(plt.Path.unit_regular_star(5).vertices) == 10
    assert len(plt.Path.unit_regular_polygon(6).vertices) == 6
    assert len(plt.Path.unit_circle().vertices) == 65


def test_collection_and_connection_patch_shims(tmp_path):
    fig, ax = plt.subplots()
    ax.add_collection(plt.mcollections.LineCollection(
        [[(0, 0), (1, 1)], [(0, 1), (1, 0)]], colors=["red", "blue"]))
    ax.add_collection(plt.PolyCollection([[(0, 0), (1, 0), (0, 1)]]))
    ax.add_collection(plt.PatchCollection([plt.Rectangle((0, 0), 1, 1)]))
    ax.add_collection(plt.EventCollection([0.2, 0.8]))
    ax.add_patch(plt.mpatches.ConnectionPatch((0, 0), (1, 1)))
    p = tmp_path / "collections.png"
    fig.savefig(p)
    assert p.stat().st_size > 0


def test_arrow_patch_and_ellipse_collection_render(tmp_path):
    plt.rcdefaults()
    fig, ax = plt.subplots()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    arrow = plt.patches.Arrow(1, 1, 4, 0, width=0.5, color="black")
    pts = arrow.get_xy()
    assert pts.shape[1] == 2 and np.ptp(pts[:, 0]) == pytest.approx(4.0)
    ax.add_patch(arrow)
    ellipses = plt.collections.EllipseCollection(
        [2.0, 1.0], [1.0, 2.0], [0.0, 45.0], units="xy",
        offsets=[[7, 7], [7, 3]], facecolor="red")
    assert len(ellipses.get_segments()) == 2
    ax.add_collection(ellipses)
    p = tmp_path / "arrow.png"
    fig.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
