import re

import numpy as np
import pytest
import matplotvite as plt
from png_utils import decode_png_rgba


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


def _mean_abs_channel_diff(a_rows, b_rows):
    """Mean |difference| over the RGB channels of two decoded PNGs."""
    total = 0
    count = 0
    for row_a, row_b in zip(a_rows, b_rows):
        for i in range(0, min(len(row_a), len(row_b)), 4):
            for channel in range(3):
                total += abs(row_a[i + channel] - row_b[i + channel])
                count += 1
    return total / max(count, 1)


def _png_colour_counts(rows):
    counts = {"red": 0, "blue": 0, "green": 0, "orange": 0, "nonwhite": 0}
    for row in rows:
        for i in range(0, len(row), 4):
            r, g, b = row[i], row[i + 1], row[i + 2]
            counts["red"] += r > 150 and g < 120 and b < 120
            counts["blue"] += b > 150 and r < 120 and g < 120
            counts["green"] += g > 100 and r < 120 and b < 120
            counts["orange"] += r > 180 and 60 < g < 180 and b < 100
            counts["nonwhite"] += min(r, g, b) < 250
    return counts


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
    # this four-panel figure measures about 6.1 on a 0-255 scale.
    assert _mean_abs_channel_diff(direct[2], svg[2]) <= 10.0


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


def test_grid_defaults_and_unicode_minus(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([-1, 1], [-1, 1])
    ax.grid(True)
    assert ax.grid_color == "#b0b0b0"
    assert ax.grid_linewidth == pytest.approx(0.8)
    ax.set_xticks([-1, 0, 1])
    svg = fig.savefig(None, format="svg").decode()
    assert "−1" in svg


def test_empty_figure_saves_blank(tmp_path):
    fig = plt.figure((4, 3))
    p = tmp_path / "e.png"
    fig.savefig(p)
    b = p.read_bytes()
    assert b[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(b[16:20], "big") == 400
    assert int.from_bytes(b[20:24], "big") == 300
    assert fig.savefig(None, format="svg").decode().startswith("<svg")


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

    pdf = tmp_path / "tight.pdf"
    plt.savefig(pdf, bbox_inches="tight")
    b = pdf.read_bytes()
    m = re.search(rb"MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", b)
    assert m, "missing MediaBox"
    w, h = (float(v) for v in m.groups())
    assert w < 288 and h < 216


def test_tight_pdf_with_image(tmp_path):
    plt.figure((4, 3))
    plt.imshow(np.linspace(0, 1, 100).reshape(10, 10))
    p = tmp_path / "image.pdf"
    plt.savefig(p, bbox_inches="tight")
    b = p.read_bytes()
    assert b[:5] == b"%PDF-"
    m = re.search(rb"MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", b)
    assert m, "missing MediaBox"
    w, h = (float(v) for v in m.groups())
    assert 0 < w < 288 and 0 < h < 216


def test_pdf_background_alpha_is_blended_over_white(tmp_path):
    fig = plt.figure((2, 2), facecolor=(1.0, 0.0, 0.0, 0.5))
    fig.gca().plot([0, 1], [1, 0])
    p = tmp_path / "alpha.pdf"
    fig.savefig(p)
    assert re.search(rb"1 0\.498\d* 0\.498\d* rg", p.read_bytes())


def test_large_image_with_smoothing_interpolation_renders(tmp_path):
    z = np.linspace(0, 1, 600 * 600).reshape(600, 600)
    plt.figure((3, 3))
    plt.imshow(z, cmap="gray", interpolation="bilinear")
    p = tmp_path / "large-bilinear.png"
    plt.savefig(p)
    assert p.stat().st_size > 0


def test_tight_bbox_with_colored_background(tmp_path):
    fig = plt.figure((4, 3), facecolor="red")
    fig.gca().plot([1, 2, 3])
    tight = tmp_path / "tight-red.png"
    fig.savefig(tight, bbox_inches="tight")
    assert int.from_bytes(tight.read_bytes()[16:20], "big") < 400

    # The background must not force the vector tight box back to full canvas.
    svg = tmp_path / "tight-red.svg"
    fig.savefig(svg, bbox_inches="tight")
    text = svg.read_text()
    assert 'viewBox="0 0 400 300"' not in text
    assert 'fill="#FF0000"' in text


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


def test_invalid_and_excessive_dimensions(tmp_path):
    # Defense against DoS/OOM from invalid or unbounded dimensions
    plt.figure(); plt.plot([1, 2], [3, 4])
    for bad_dpi in [-50, 0, float("nan"), float("inf")]:
        with pytest.raises(ValueError, match="dpi must be positive and finite"):
            plt.savefig(dpi=bad_dpi)

    with pytest.raises(ValueError, match="exceeds maximum allowed dimension"):
        plt.savefig(dpi=100_000)

    plt.figure(figsize=(300, 300))
    with pytest.raises(ValueError, match="total figure pixel count"):
        plt.savefig(tmp_path / "area.png")

    for bad_size in [(-1, 5), (5, 0), (float("nan"), 4), (float("inf"), 4)]:
        with pytest.raises(ValueError, match="must be positive and finite"):
            plt.figure(figsize=bad_size)

    for malformed in ["invalid", (1,), (1, 2, 3)]:
        with pytest.raises(ValueError, match="figsize must be a sequence of 2 positive numbers"):
            plt.figure(figsize=malformed)


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


def test_colormap_maps_nan_to_transparent():
    cmap = plt.get_cmap("viridis")
    assert cmap(np.nan) == (0.0, 0.0, 0.0, 0.0)
    rgba = cmap([0.0, np.nan, 1.0])
    assert np.allclose(rgba[0], cmap(0.0))
    assert np.array_equal(rgba[1], [0.0, 0.0, 0.0, 0.0])
    assert np.allclose(rgba[2], cmap(1.0))


def test_text_newline_draws_separate_lines(tmp_path):
    plt.figure((4, 3))
    plt.text(0.1, 0.5, "first\nsecond\n  indented\n\ttabbed")
    p = tmp_path / "multiline.svg"
    plt.savefig(p)
    svg = p.read_text()
    ys = {}
    for name in ("first", "second"):
        match = re.search(rf'<text x="-?\d+" y="(\d+)"[^>]*>\s*{name}', svg)
        assert match is not None
        ys[name] = int(match.group(1))
    delta = abs(ys["second"] - ys["first"])
    assert 15 <= delta <= 18  # 10 pt at 100 dpi with 1.2 line spacing
    assert "\u00a0\u00a0indented" in svg
    assert "\u00a0\u00a0\u00a0\u00a0tabbed" in svg


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
    second = plt.subplot(1, 2, 2)
    assert second in fig.axes
    plt.title("via pyplot"); ax.plot([1, 2]); plt.savefig(tmp_path / "s.svg")
    assert "via pyplot" in (tmp_path / "s.svg").read_text()


def test_subplot_three_digit_shorthand():
    # `subplot(121)` means a 1x2 grid, first cell (matplotlib's shorthand).
    fig = plt.figure()
    ax = plt.subplot(121)
    ax.plot([0, 1], [1, 0])
    plt.subplot(122).plot([0, 1], [0, 1])
    assert fig.grid == (1, 2)
    assert [a.pos for a in fig.axes] == [0, 1]


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
    # Marching-squares cells are joined into one polyline per contour rather
    # than emitting an element for every cell.
    assert 3 <= s.count("<polyline") < 30 and "</svg>" in s


def test_contourf_fills(tmp_path):
    z = np.add.outer(np.arange(20.0), np.arange(20.0))
    plt.figure((4, 3))
    cs = plt.contourf(z, levels=[0, 10, 20, 30])
    assert cs.levels == [0.0, 10.0, 20.0, 30.0]
    p = tmp_path / "cf.svg"
    plt.savefig(p)
    assert p.read_text().count("<polygon") > 10


def test_contour_linewidths_and_alpha(tmp_path):
    x, y, z = _bump()
    plt.figure((4, 3))
    plt.contour(x, y, z, levels=[0.2, 0.6], linewidths=4, alpha=0.5)
    p = tmp_path / "cw.svg"
    plt.savefig(p)
    s = p.read_text()
    assert re.search(r'stroke-width="4"', s)
    assert re.search(r'opacity="0\.5', s)

    plt.figure((4, 3))
    plt.contourf(x, y, z, levels=[0.2, 0.6], alpha=0.25)
    p2 = tmp_path / "cfa.svg"
    plt.savefig(p2)
    assert re.search(r'opacity="0\.25', p2.read_text())


def test_contour_linewidths_validation():
    z = np.add.outer(np.arange(6.0), np.arange(6.0))
    plt.figure()
    with pytest.raises(ValueError):
        plt.contour(z, levels=[1, 2, 3], linewidths=[1, 2])


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


def test_fill_between_color_does_not_advance_the_cycle():
    fig, ax = plt.subplots()
    ax.fill_between([0, 1], [0, 1], color="red")
    ax.plot([0, 1], [1, 0])
    assert ax.lines[-1]["color"] == plt.rcParams["axes.prop_cycle"].by_key()["color"][0]


def test_legend_orders_lines_before_patches_and_collections(tmp_path):
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar([0, 1], [1, 2], label="bars")
    ax.fill_between([0, 1], [1, 2], label="band")
    ax.plot([0, 1], [2, 1], label="line", marker="+")
    ax.scatter([0, 1], [1, 2], label="dots")
    ax.legend()
    p = tmp_path / "legend_order.svg"
    fig.savefig(p)
    s = p.read_text()
    order = [re.search(rf">\s*{name}\s*<", s).start()
             for name in ("line", "bars", "band", "dots")]
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
                          p.read_text())
        assert match is not None
        points = [tuple(float(v) for v in pair.split(","))
                  for pair in match.group(1).split()]
        radii.append(points[0][1] - min(y for _, y in points))
    assert radii[0] > 0 and radii[1] > radii[0]


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
    svg = p.read_text()
    assert svg.count("#808080") >= 2
    assert svg.count("#FFFFFF") >= 2


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


def test_colorbar_draws_inside_main_panel():
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.contourf(np.add.outer(np.arange(20.0), np.arange(20.0)), levels=[0, 10, 20, 30])
    fig.colorbar(label="z")
    assert fig.grid == (1, 1)
    assert ax._panel()["colorbar"] is not None


def test_equal_aspect_draws_title_once(tmp_path):
    plt.figure((4, 3))
    plt.imshow(np.arange(12.0).reshape(3, 4))
    plt.title("Aspect title")
    p = tmp_path / "aspect_title.svg"
    plt.savefig(p)
    assert p.read_text().count("Aspect title") == 1


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
    z = np.arange(16.0).reshape(4, 4)
    cs = plt.contour(z, levels=[5.0])
    assert cs.levels == [5.0]
    with pytest.raises(ValueError):
        plt.contour(z, levels=1)
    with pytest.raises(ValueError):
        plt.contourf(z, levels=[5.0])
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


def test_colorbar_from_scatter_and_scalar_mappable(tmp_path):
    fig, ax = plt.subplots(figsize=(6, 3))
    sc = ax.scatter([1, 2, 3, 4, 5], [1, 4, 9, 16, 25],
                    c=[0.0, 0.5, 1.0, 2.0, 3.0], cmap="viridis")
    assert sc.get_array().size == 5
    cb = fig.colorbar(sc, ax=ax, label="value")
    assert cb.get_label() == "value"
    assert ax._panel()["colorbar"] is not None
    p = tmp_path / "scatter_cb.svg"
    fig.savefig(p)
    assert "value" in p.read_text()

    fig, ax = plt.subplots(figsize=(6, 3))
    sm = plt.ScalarMappable(cmap="magma")
    sm.set_array([2.0, 4.0, 8.0])
    fig.colorbar(sm, ax=ax, label="standalone")
    assert ax._panel()["colorbar"][:3] == ("magma", 2.0, 8.0)

    fig, (ax, cax) = plt.subplots(1, 2, figsize=(6, 3))
    sc = ax.scatter([1, 2], [1, 2], c=[0.0, 1.0])
    fig.colorbar(sc, cax=cax)
    assert cax._panel()["colorbar"] is not None


def test_colorbar_uses_nice_ticks():
    fig, ax = plt.subplots(figsize=(6, 3))
    im = ax.imshow(np.linspace(0.0, 1.0, 100).reshape(10, 10))
    ax.set_axis_off()
    fig.colorbar(im, ax=ax)
    svg = fig.savefig(None, format="svg").decode()
    assert re.search(r">\s*0\.2\s*</text>", svg) and re.search(r">\s*0\.8\s*</text>", svg)
    assert not re.search(r">\s*0\.5\s*</text>", svg)


def test_colorbar_ticks_have_no_float_noise():
    fig, ax = plt.subplots(figsize=(5, 4))
    x = np.linspace(0, 4, 40)
    y = np.linspace(0, 3, 30)
    xx, yy = np.meshgrid(x, y)
    mesh = ax.pcolormesh(x, y, np.sin(xx) * np.cos(yy), cmap="viridis")
    fig.colorbar(mesh, ax=ax)
    svg = fig.savefig(None, format="svg").decode()
    # Accumulating the step left -5.55e-17 in the labels; multiply an index
    # instead, and prefer the 0.25 step over 0.2 for a span just under 2.
    assert "e-17" not in svg and "e+03" not in svg
    assert re.search(r">\s*0\.75\s*</text>", svg)


def test_colorbar_on_multiple_axes(tmp_path):
    fig, axs = plt.subplots(1, 2, figsize=(6, 3))
    for ax, offset in zip(axs, (0.0, 10.0)):
        im = ax.imshow(np.arange(12.0).reshape(3, 4) + offset)
        fig.colorbar(im, ax=ax, label=f"z{offset:g}")
    assert axs[0]._panel()["colorbar"] is not None
    assert axs[1]._panel()["colorbar"] is not None
    assert axs[0]._panel()["colorbar"][3] == "z0"
    assert axs[1]._panel()["colorbar"][3] == "z10"
    p = tmp_path / "multi_cb.png"
    fig.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


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


def test_imshow_alpha_and_interpolation(tmp_path):
    z = np.linspace(0, 1, 64).reshape(8, 8)
    uris = []
    for alpha in (1.0, 0.5, 0.0):
        plt.figure((3, 3))
        plt.imshow(z, cmap="gray", alpha=alpha)
        p = tmp_path / f"alpha_{alpha}.svg"
        plt.savefig(p)
        uris.append(re.search(r'href="data:image/png;base64,([^"]+)"', p.read_text()).group(1))
    assert len(set(uris)) == 3

    plt.figure((3, 3))
    plt.imshow(z, interpolation="nearest")
    p = tmp_path / "nearest.svg"
    plt.savefig(p)
    assert "image-rendering:pixelated" in p.read_text()

    plt.figure((3, 3))
    plt.imshow(z, interpolation="spline16")
    p = tmp_path / "spline16.svg"
    plt.savefig(p)
    assert p.stat().st_size > 0
    with pytest.raises(ValueError):
        plt.imshow(z, interpolation="not-a-real-filter")
    with pytest.raises(ValueError):
        plt.imshow(z, alpha=float("nan"))


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
    assert ax.get_xlim() == pytest.approx((1.8, 6.2)) and ax.get_ylim() == pytest.approx((9.0, 31.0))
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

    fig = plt.figure()
    plt.plot([1, 2])
    plt.gca().remove()
    fig.savefig(tmp_path / "none.png")
    assert (tmp_path / "none.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


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
    assert ax.get_xlim() == pytest.approx((-0.05, 1.05))
    p = tmp_path / "empty.svg"
    plt.savefig(p)
    assert "gone" not in p.read_text()


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


def test_add_axes_rectangle_is_the_plotting_area(tmp_path):
    cases = [([0.1, 0.1, 0.8, 0.8], (40, 30, 320, 240)),
             ([0.2, 0.2, 0.6, 0.6], (80, 60, 240, 180))]
    for index, (rect, expected) in enumerate(cases):
        fig = plt.figure((4, 3))
        ax = fig.add_axes(rect)
        ax.set_facecolor("red")
        ax.plot([0, 1], [0, 1])
        p = tmp_path / f"plot_area_{index}.svg"
        fig.savefig(p)
        match = re.search(
            r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" '
            r'opacity="1" fill="#FF0000"',
            p.read_text(),
        )
        assert match is not None
        x, y, w, h = (int(v) for v in match.groups())
        for actual, wanted in zip((x, y, w, h), expected):
            assert abs(actual - wanted) <= 2


def test_mpl_toolkits_inset_axes(tmp_path):
    from matplotvite.mpl_toolkits.axes_grid1.inset_locator import inset_axes, zoomed_inset_axes

    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    inset = inset_axes(ax, width="30%", height="25%", loc="upper right", borderpad=0)
    parent = ax.get_position()
    assert inset.get_position().width == pytest.approx(0.3 * parent.width)
    assert inset.get_position().height == pytest.approx(0.25 * parent.height)
    inset.plot([0, 1], [1, 0], color="red")
    assert inset in fig.get_axes()
    zoomed = zoomed_inset_axes(ax, 2, loc="lower left", borderpad=0)
    assert zoomed.get_xlim() != ax.get_xlim()
    p = tmp_path / "toolkit-inset.svg"
    fig.savefig(p)
    assert "#FF0000" in p.read_text().upper()


def test_inset_axes_png_keeps_parent_and_child_content():
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1], color="blue", linewidth=3)
    inset = ax.inset_axes([0.5, 0.5, 0.4, 0.3])
    inset.plot([0, 1], [1, 0], color="red", linewidth=3)
    width, _, rows = decode_png_rgba(fig.savefig(format="png"))
    red = blue = 0
    for row in rows:
        for x in range(0, width * 4, 4):
            r, g, b = row[x], row[x + 1], row[x + 2]
            red += r > 150 and g < 100 and b < 100
            blue += b > 150 and r < 100 and g < 120
    # Overlay panels share one document, so the parent line must survive the
    # inset's opaque background outside the inset rectangle.
    assert red > 20 and blue > 20


def test_inset_axes_is_placed_in_axes_fraction(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    inset = ax.inset_axes([0.5, 0.5, 0.4, 0.3])
    inset.plot([0, 1], [1, 0], color="red")
    parent, child = ax.get_position(), inset.get_position()
    assert child.x0 == pytest.approx(parent.x0 + 0.5 * parent.width)
    assert child.y0 == pytest.approx(parent.y0 + 0.5 * parent.height)
    assert inset in fig.get_axes()
    p = tmp_path / "inset.svg"
    fig.savefig(p)
    assert "#FF0000" in p.read_text().upper()


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
    # Repeated data sets are valid; a dangling numeric third arg is not.
    assert len(plt.plot([1], [2], [3], [4])) == 2
    with pytest.raises(TypeError):
        plt.plot([1], [2], [3])


def test_plot_fmt_marker_only_and_unlabelled_scatter():
    fig, ax = plt.subplots()
    line = ax.plot([0, 1], [0, 1], "o+")[0]
    assert line.get_linestyle() == "None"
    ax.scatter([0, 1], [0, 1])
    ax.legend()
    svg = fig.savefig(None, format="svg").decode()
    assert "y0" not in svg


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
    assert ax.get_xlim() == pytest.approx((0.9, 3.1))
    assert ax.get_ylim() == pytest.approx((0.75, 6.25))


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


def test_excessive_binning_is_rejected():
    plt.figure()
    with pytest.raises(ValueError, match="bins=5000 exceeds maximum"):
        plt.hist([1, 2], bins=5000)
    with pytest.raises(ValueError, match="too many bins"):
        plt.hist2d([1, 2], [1, 2], bins=[3000, 3000])
    with pytest.raises(ValueError, match="too many hexagons"):
        plt.hexbin([1, 2], [1, 2], gridsize=(2000, 2000))


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
    s = p.read_text().upper()
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
    assert "#000000" in p.read_text().upper()


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
    assert "#FF0000" in p.read_text().upper()
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
    circles = [line for line in p.read_text().splitlines() if "<circle" in line]
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
    s = p.read_text().upper()
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
    assert p.read_text().upper().count("<POLYGON") >= 1
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


def test_hist2d_counts_edges_and_image(tmp_path):
    rng = np.random.default_rng(5)
    x, y = rng.random(200), rng.random(200)
    plt.figure()
    ax = plt.gca()
    counts, xedges, yedges, image = ax.hist2d(x, y, bins=[4, 3], cmap="gray")
    assert counts.shape == (4, 3)
    assert len(xedges) == 5 and len(yedges) == 4
    assert counts.sum() == 200
    assert image.get_array().shape == (3, 4)
    assert ax.get_aspect() is None
    p = tmp_path / "hist2d.svg"
    plt.savefig(p)
    assert '<image' in p.read_text() and "data:image/png;base64," in p.read_text()
    plt.savefig(tmp_path / "hist2d.png")
    assert (tmp_path / "hist2d.png").stat().st_size > 0
    with pytest.raises(ValueError):
        ax.hist2d([1, 2], [1])


def test_hexbin_cells_and_mincnt(tmp_path):
    rng = np.random.default_rng(6)
    x, y = rng.random(60), rng.random(60)
    plt.figure()
    ax = plt.gca()
    coll = ax.hexbin(x, y, gridsize=5, cmap="gray", mincnt=0)
    assert coll.get_array().size == coll.get_offsets().shape[0] > 0
    assert np.any(coll.get_array() > 0)
    assert len(coll.get_facecolor()) == coll.get_array().size
    occupied = ax.hexbin(x, y, gridsize=5, cmap="gray", mincnt=1)
    assert np.all(occupied.get_array() >= 1)
    p = tmp_path / "hexbin.svg"
    plt.savefig(p)
    assert p.read_text().upper().count("<POLYGON") >= coll.get_array().size
    with pytest.raises(ValueError):
        ax.hexbin([1, 2], [1])
    with pytest.raises(ValueError):
        ax.hexbin([1, 2], [1, 2], C=[1])


def test_hexbin_default_keeps_empty_cells_and_pyplot_shims(tmp_path):
    rng = np.random.default_rng(7)
    x, y = rng.random(30), rng.random(30)
    plt.figure()
    coll = plt.hexbin(x, y, gridsize=6)
    assert np.any(coll.get_array() == 0)
    plt.figure()
    counts, *_ = plt.hist2d(x, y, bins=3)
    assert counts.sum() == 30
    p = tmp_path / "hex_shims.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_quiver_arrows_and_extents(tmp_path):
    plt.figure()
    ax = plt.gca()
    q = ax.quiver([0, 1], [0, 0], [1, 1], [1, -1],
                  color=["red", "green"], pivot="tail")
    assert q.get_offsets().shape == (2, 2)
    assert np.allclose(q.get_U(), [1, 1]) and np.allclose(q.get_V(), [1, -1])
    assert ax.get_xlim() == pytest.approx((-0.1, 2.1))
    assert ax.get_ylim() == pytest.approx((-1.1, 1.1))
    p = tmp_path / "quiver.svg"
    plt.savefig(p)
    s = p.read_text().upper()
    assert s.count("<POLYGON") >= 2  # arrow heads
    assert s.count("<POLYLINE") >= 2  # arrow shafts
    assert "#FF0000" in s and "#008000" in s


def test_quiver_forms_scale_and_validation(tmp_path):
    plt.figure()
    ax = plt.gca()
    grid = ax.quiver(np.ones((2, 3)), np.zeros((2, 3)))
    assert grid.get_offsets().shape == (6, 2)
    scaled = ax.quiver([0], [0], [2], [1], scale=2, pivot="tip", angles="uv")
    assert np.allclose(scaled.get_U(), [1.0]) and np.allclose(scaled.get_V(), [0.5])
    assert np.allclose(scaled.get_offsets(), [[-1.0, -0.5]])
    plt.figure()
    q = plt.quiver(U=[1, 2], V=[0, 1], scale="auto")
    assert q.get_offsets().shape == (2, 2)
    p = tmp_path / "quiver2.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(ValueError):
        ax.quiver([0, 1], [0, 1], [1], [1])
    with pytest.raises(ValueError):
        ax.quiver([0], [0], [1], [1], angles="radians")
    with pytest.raises(ValueError):
        ax.quiver([0], [0], [1], [1], pivot="nose")
    with pytest.raises(ValueError):
        ax.quiver([0], [0], [1], [1], scale=0)
    with pytest.raises(TypeError):
        ax.quiver([0])


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
    assert re.search(r">\s*100\s*<", s), "decade tick label missing"
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
    from matplotvite import _norm_color

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


def test_colormap_registry_and_get_cmap():
    names = plt.colormaps()
    assert len(names) == 182 and len(set(names)) == 182
    for name in ("viridis", "viridis_r", "plasma", "inferno", "magma", "cividis",
                 "coolwarm", "jet", "tab10", "Blues", "twilight_shifted_r"):
        assert name in names
    cmap = plt.get_cmap("viridis")
    assert cmap.N == 256 and len(cmap.colors) == 256
    rgba = cmap(0.5)
    assert len(rgba) == 4
    assert np.allclose(rgba, (0.129, 0.569, 0.549, 1.0), atol=0.01)
    assert cmap([[0.0, 0.5], [1.0, 0.25]]).shape == (2, 2, 4)
    assert all(isinstance(v, int) for v in cmap(0.5, bytes=True))
    assert np.allclose(plt.get_cmap("viridis_r")(0.0), cmap(1.0))
    assert plt.cm.viridis(0.25) == cmap(0.25)
    assert plt.cm.get_cmap("Blues").name == "Blues"
    assert plt.get_cmap("viridis", 8).N == 8
    assert np.allclose(plt.get_cmap("viridis", 8)(1.0), cmap(1.0), atol=0.01)
    with pytest.raises(ValueError):
        plt.get_cmap("not-a-colormap")
    with pytest.raises(AttributeError):
        plt.cm.not_a_colormap


def test_all_colormaps_map_and_render():
    for name in plt.colormaps():
        rgba = plt.get_cmap(name)(np.linspace(0.0, 1.0, 5))
        assert rgba.shape == (5, 4)
        assert np.all(rgba >= 0.0) and np.all(rgba <= 1.0)
        plt.figure((1.5, 1.5))
        plt.imshow(np.linspace(0.0, 1.0, 4).reshape(2, 2), cmap=name)
        assert plt.savefig(format="png")[:8] == b"\x89PNG\r\n\x1a\n"


def test_colormaps_across_artists_and_rc_default(tmp_path):
    plt.rcdefaults()
    plt.set_cmap("plasma")
    assert plt.rcParams["image.cmap"] == "plasma"
    plt.figure((3, 2))
    image = plt.imshow(np.zeros((2, 2)))
    assert image.get_cmap() == "plasma"
    plt.set_cmap(plt.get_cmap("magma"))
    plt.figure((3, 2))
    assert plt.imshow(np.zeros((2, 2))).get_cmap() == "magma"
    plt.figure((3, 2))
    ax = plt.gca()
    ax.scatter([0, 1], [0, 1], c=[0.0, 1.0], cmap="coolwarm")
    ax.contour([0, 1], [0, 1], [[0.0, 1.0], [1.0, 0.0]], cmap="jet")
    ax.contourf([0, 1], [0, 1], [[0.0, 1.0], [1.0, 0.0]], cmap="Blues")
    ax.pcolormesh(np.arange(3.0), np.arange(3.0), np.zeros((2, 2)), cmap="tab10")
    ax.hexbin([0.1, 0.2], [0.1, 0.2], gridsize=2, cmap="inferno", mincnt=0)
    ax.hist2d([0.1, 0.2], [0.1, 0.2], bins=2, cmap="viridis_r")
    p = tmp_path / "all-cmaps.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(ValueError):
        plt.imshow(np.zeros((2, 2)), cmap="not-a-colormap")
    with pytest.raises(ValueError):
        ax.scatter([0], [0], c=[0.0], cmap="not-a-colormap")
    with pytest.raises(ValueError):
        ax.contour([0, 1], [0, 1], [[0.0, 1.0], [1.0, 0.0]], cmap="not-a-colormap")
    plt.rcdefaults()


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
    assert "Mon" in p.read_text() and "Wed" in p.read_text()


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


def test_mathtext_titles_labels_and_text(tmp_path):
    from matplotvite import _mathtext

    assert _mathtext("$x^2$") == "x²"
    assert _mathtext("$x^{10}$") == "x¹⁰"
    assert _mathtext("$e^{-x}$") == "e^(-x)"
    assert _mathtext("$A_{i-1}$") == "A_(i-1)"
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
    svg = p.read_text()
    assert "x²" in svg and "β₀" in svg and "e^(-x)" in svg


def test_unchanged_figure_reuses_encoded_bytes(monkeypatch):
    calls = []
    original = plt._render

    def counting(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(plt, "_render", counting)
    fig = plt.figure((3, 2))
    plt.plot([0, 1], [1, 0])
    first = fig.savefig(format="png")
    second = fig.savefig(format="png")
    assert first == second and len(calls) == 1
    plt.title("changed")
    fig.savefig(format="png")
    assert len(calls) == 2


def test_webp_output(tmp_path):
    plt.figure((3, 2))
    plt.plot([0, 1], [1, 0])
    data = plt.savefig(format="webp")
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    p = tmp_path / "plot.webp"
    plt.savefig(p)
    assert p.read_bytes()[:4] == b"RIFF"
    with pytest.raises(ValueError):
        plt.savefig(format="gif")


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
    assert any(18.5 < v < 20.5 for v in sizes)  # xlabel at 14pt


def test_default_sans_font_is_dejavu():
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    ax.set_title("DejaVu Sans")
    pdf = fig.savefig(None, format="pdf")
    assert b"DejaVuSans" in pdf


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


def test_subplots_squeeze_false_keeps_array():
    fig, axs = plt.subplots(1, 1, squeeze=False)
    assert axs.shape == (1, 1)
    assert axs[0, 0].get_figure() is fig


class _FakeRect:
    def __init__(self, x, y, w, h, face="red", edge="black", lw=2.0, alpha=1.0):
        self._v = (x, y, w, h)
        self._face, self._edge, self._lw, self._alpha = face, edge, lw, alpha

    def get_x(self): return self._v[0]
    def get_y(self): return self._v[1]
    def get_width(self): return self._v[2]
    def get_height(self): return self._v[3]
    def get_facecolor(self): return self._face
    def get_edgecolor(self): return self._edge
    def get_linewidth(self): return self._lw
    def get_alpha(self): return self._alpha
    def get_label(self): return ""


class _FakeCollection:
    def __init__(self, offsets, colors, sizes):
        self._offsets, self._colors, self._sizes = offsets, colors, sizes

    def get_offsets(self): return np.asarray(self._offsets, dtype=float)
    def get_facecolor(self): return np.asarray(self._colors, dtype=float)
    def get_sizes(self): return np.asarray(self._sizes, dtype=float)
    def get_alpha(self): return 1.0
    def get_marker(self): return "o"
    def get_label(self): return ""


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
    assert ax._panel()["ylabel_color"] == "#c44e52"
    assert twin._panel()["ylabel_color"] == "#4c72b0"
    assert ax._panel()["bounds"] is not None and twin._panel()["bounds"] is not None
    assert twin._panel()["ticks"]["hide_xlabels"]
    p = tmp_path / "twinx.svg"
    fig.savefig(p)
    s = p.read_text().upper()
    assert "#FF0000" in s and "#0000FF" in s
    assert "#C44E52" in s and "#4C72B0" in s
    assert "right" in p.read_text()


def test_twinx_png_keeps_primary_and_twin_axes():
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 1, 2], [1, 4, 9], color="red", linewidth=4)
    twin = ax.twinx()
    twin.plot([0, 1, 2], [9, 4, 1], color="blue", linewidth=4)
    width, height, rows = decode_png_rgba(fig.savefig(format="png"))
    assert (width, height) == (500, 400)
    red = blue = dark_left = 0
    for y, row in enumerate(rows):
        for x in range(0, width * 4, 4):
            r, g, b = row[x], row[x + 1], row[x + 2]
            red += r > 160 and g < 100 and b < 100
            blue += b > 160 and r < 100 and g < 100
            if x < width // 5 * 4 and r < 100 and g < 100 and b < 100:
                dark_left += 1
    assert red > 20 and blue > 20
    assert dark_left > 20


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


def test_figure_text_needs_no_axes_and_is_not_clipped(tmp_path):
    fig = plt.figure()
    fig.text(0.5, 0.5, "figure text", ha="center", va="center", fontsize=16, color="red")
    p = tmp_path / "figtext.svg"
    fig.savefig(p)
    assert re.search(r">\s*figure text\s*<", p.read_text())
    # It sits above the panels, spanning the grid rather than one cell.
    fig2, _ = plt.subplots(1, 2)
    fig2.text(0.5, 0.95, "across panels", ha="center")
    p2 = tmp_path / "figtext_grid.svg"
    fig2.savefig(p2)
    assert "across panels" in p2.read_text()
    # Text properties the renderer cannot draw yet are accepted, but a typo is not.
    fig2.text(0.1, 0.1, "rotated", rotation=45, usetex=False)
    with pytest.raises(TypeError):
        fig2.text(0.1, 0.1, "bad", nonsense=1)
    plt.figtext(0.5, 0.5, "pyplot helper")
    assert plt.gcf()._figure_texts[-1][2] == "pyplot helper"


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


def test_savefig_hashes_panel_arrays_once(monkeypatch):
    array_ids = []
    original = plt._hash_value

    def counting_hash(hasher, value):
        if isinstance(value, np.ndarray):
            array_ids.append(id(value))
        return original(hasher, value)

    monkeypatch.setattr(plt, "_hash_value", counting_hash)
    plt.figure()
    plt.plot(np.arange(100.0), np.arange(100.0) ** 2)
    plt.savefig(None, format="svg")
    # The figure key reuses the per-panel digest; it must not walk the same
    # series array a second time.
    assert array_ids and len(array_ids) == len(set(array_ids))


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


def test_images_have_sticky_edges_and_no_default_resampling():
    plt.figure()
    ax = plt.gca()
    ax.imshow(np.zeros((3, 4)))
    assert ax.get_xlim() == (-0.5, 3.5) and ax.get_ylim() == (2.5, -0.5)
    assert ax.yaxis_inverted()
    assert ax.images[0]["interpolation"] == "nearest"
    ax.plot([0, 10], [0, 1])
    assert ax.get_xlim() == pytest.approx((-0.5, 10.525))


def test_image_interpolation_rc_default(tmp_path):
    old = plt.rcParams["image.interpolation"]
    try:
        plt.rcParams["image.interpolation"] = "antialiased"
        fig = plt.figure((3, 3))
        ax = fig.gca()
        ax.imshow(np.linspace(0, 1, 64).reshape(8, 8), cmap="gray")
        assert ax.images[0]["interpolation"] == "antialiased"
        p = tmp_path / "smooth.svg"
        fig.savefig(p)
        assert "image-rendering:pixelated" not in p.read_text()
    finally:
        plt.rcParams["image.interpolation"] = old


def test_imshow_origin_and_explicit_extent():
    plt.figure()
    ax = plt.gca()
    ax.imshow(np.zeros((3, 4)), origin="lower")
    assert ax.get_xlim() == (-0.5, 3.5) and ax.get_ylim() == (-0.5, 2.5)
    assert not ax.yaxis_inverted()

    plt.figure()
    ax = plt.gca()
    ax.imshow(np.zeros((3, 4)), extent=(-2, 2, -1, 1))
    assert ax.get_xlim() == (-2.0, 2.0) and ax.get_ylim() == (-1.0, 1.0)

    ax.set_ylim(10, 0)
    assert ax.get_ylim() == (10.0, 0.0) and ax.yaxis_inverted()
    ax.set_ylim(0, 10)
    assert ax.get_ylim() == (0.0, 10.0) and not ax.yaxis_inverted()


def test_figure_accepts_number_and_positional_figsize():
    assert plt.figure(1).get_size_inches() == pytest.approx((6.4, 4.8))
    assert plt.figure(1, (4, 3)).get_size_inches() == pytest.approx((4, 3))
    assert plt.figure(2, figsize=(5, 4)).get_size_inches() == pytest.approx((5, 4))


def test_quiver_broadcasts_coordinate_axes(tmp_path):
    x, y = np.arange(3.0), np.arange(2.0)
    u, v = np.meshgrid(x, y)
    plt.figure()
    plt.quiver(x, y, u, v)
    p = tmp_path / "quiver.png"
    plt.savefig(p)
    assert p.stat().st_size > 0


def test_violinplot_accepts_per_dataset_quantiles(tmp_path):
    plt.figure()
    plt.violinplot([np.arange(10.0), np.arange(10.0)[::-1]],
                   positions=[1, 2], quantiles=[[0.1], [0.9]])
    p = tmp_path / "violin.png"
    plt.savefig(p)
    assert p.stat().st_size > 0


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


def test_ignored_shim_warns_once():
    label = plt.figure().gca().xaxis.label
    with pytest.warns(RuntimeWarning, match="accepted but ignored"):
        label.set_wrap(True)


def test_hist2d_rejects_oversized_edge_arrays():
    with pytest.raises(ValueError, match="too many edges"):
        plt.hist2d([0, 1], [0, 1], bins=[np.arange(100_002), np.arange(3)])


def test_matplotlib_namespace_and_cycler_shims():
    assert plt.rcParams["axes.prop_cycle"].by_key()["color"]
    assert plt.colors.to_rgb("red") == (1.0, 0.0, 0.0)
    assert plt.mpatches.ArrowStyle.CurveFilledB() is not None
    assert plt.gridspec.GridSpecFromSubplotSpec(1, 1) is not None
    assert plt.mticker.NullLocator() is not None
    assert plt.mtransforms.offset_copy(None) is not None
    assert plt.path_effects.withStroke(linewidth=1) is not None
    line = plt.Line2D([0, 1], [1, 0])
    line.set_path_effects([plt.path_effects.withStroke()])
    assert line.get_zorder() == 2


def test_colormap_registry_and_spine_selections():
    names = plt.colormaps()
    assert "viridis" in names
    assert plt.colormaps["viridis"].name == "viridis"
    assert plt.colormaps["viridis"].resampled(8).N == 8

    fig, ax = plt.subplots()
    ax.spines[:].set_visible(False)
    assert not ax.spines["left"].get_visible()
    ax.spines[["top", "right"]].set_visible(True)
    assert ax.spines["top"].get_visible()
    ax.axis["x"].set_axis_direction("left")
    assert ax.axis["x"].label is not None

    gs = plt.gridspec.GridSpec(2, 2)
    assert len(list(gs)) == 4

    fig2, axs = plt.subplots(1, 2)
    image = axs[0].imshow([[1, 2], [3, 4]])
    fig2.colorbar(image, ax=axs)
    assert fig2.axes[0]._colorbar is not None


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
    assert fig.axes[0].get_forward_navigation_events() == "auto"

    gs = fig.add_gridspec(3, 1)
    gs.update(top=0.8)
    assert gs.top == 0.8
    gs.tight_layout(fig)
