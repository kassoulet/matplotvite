"""Axes field artists: images, contours, vector fields and colorbars."""

import io
import os
import re

import matplotvite as plt
import numpy as np
import pytest
from plt_helpers import (
    _bump,
    _image_box,
    _ink_width,
    _write_png,
)
from png_utils import decode_png_rgba


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


def test_large_image_with_smoothing_interpolation_renders(tmp_path):
    z = np.linspace(0, 1, 600 * 600).reshape(600, 600)
    plt.figure((3, 3))
    plt.imshow(z, cmap="gray", interpolation="bilinear")
    p = tmp_path / "large-bilinear.png"
    plt.savefig(p)
    assert p.stat().st_size > 0


def test_imshow_renders(tmp_path):
    plt.figure((4, 3))
    plt.imshow(np.linspace(0, 1, 100).reshape(10, 10))
    svg = tmp_path / "im.svg"
    plt.savefig(svg)
    s = svg.read_text(encoding="utf-8")
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


def test_imshow_rgb_handle_and_errors(tmp_path):
    plt.figure((4, 3))
    ax = plt.gca()
    ax.imshow(np.random.rand(8, 8, 3), extent=(-1, 1, -1, 1))
    im = ax.imshow(np.zeros((4, 4)))
    assert ax.images[-1] is im
    assert im.get_array().shape == (4, 4)
    im.set_clim(0, 1)
    im.set_data(np.ones((4, 4)))
    im.set_cmap("gray")
    im.set(data=np.zeros((3, 3)), extent=(-2, 2, -3, 3), clim=(1, 2))
    assert im.get_array().shape == (3, 3)
    assert im.get_extent() == (-2.0, 2.0, -3.0, 3.0)
    assert im.get_clim() == (1, 2)
    with pytest.raises(ValueError):
        ax.imshow(np.zeros((2, 2, 2)))
    with pytest.raises(ValueError):
        ax.imshow(np.zeros((2, 2)), origin="middle")
    plt.savefig(tmp_path / "rgb.png")
    assert (tmp_path / "rgb.png").stat().st_size > 0


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


def test_contour_lines(tmp_path):
    x, y, z = _bump()
    plt.figure((4, 3))
    cs = plt.contour(x, y, z, levels=[0.1, 0.5, 0.9])
    assert cs.levels == [0.1, 0.5, 0.9]
    p = tmp_path / "c.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
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
    assert p.read_text(encoding="utf-8").count("<polygon") > 10


def test_contourset_explicit_paths(tmp_path):
    lines = [[[[0, 0], [0, 4]]], [[[2, 0], [1, 2], [1, 3]]]]
    plt.figure()
    cs = plt.ContourSet(plt.gca(), [0, 1, 2], lines, cmap="cool", linewidths=3)
    assert cs.levels == [0.0, 1.0, 2.0]
    assert cs.get_paths()[0].get_vertices().shape == (2, 2)

    outer = [[0, 0], [3, 0], [3, 3], [0, 3]]
    hole = [[1, 1], [1, 2], [2, 2], [2, 1]]
    codes = [[plt.Path.MOVETO, plt.Path.LINETO, plt.Path.LINETO,
              plt.Path.LINETO, plt.Path.MOVETO, plt.Path.LINETO,
              plt.Path.LINETO, plt.Path.LINETO]]
    plt.figure()
    cs = plt.ContourSet(plt.gca(), [0, 1], [[outer + hole]], [[codes]], filled=True)
    plt.colorbar(cs)
    p = tmp_path / "manual_contour.svg"
    plt.savefig(p)
    assert p.read_text(encoding="utf-8").count("<polygon") >= 2


def test_contour_linewidths_and_alpha(tmp_path):
    x, y, z = _bump()
    plt.figure((4, 3))
    plt.contour(x, y, z, levels=[0.2, 0.6], linewidths=4, alpha=0.5)
    p = tmp_path / "cw.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
    assert re.search(r'stroke-width="4"', s)
    assert re.search(r'opacity="0\.5', s)

    plt.figure((4, 3))
    plt.contourf(x, y, z, levels=[0.2, 0.6], alpha=0.25)
    p2 = tmp_path / "cfa.svg"
    plt.savefig(p2)
    assert re.search(r'opacity="0\.25', p2.read_text(encoding="utf-8"))


def test_contour_linewidths_cycle_across_levels():
    z = np.add.outer(np.arange(6.0), np.arange(6.0))
    plt.figure()
    cs = plt.contour(z, levels=[1, 2, 3], linewidths=[1, 2])
    # Matplotlib cycles a short linewidth sequence across the levels.
    assert plt.gca().contours[-1]["linewidths"] == [1.0, 2.0, 1.0]
    assert cs.levels == [1.0, 2.0, 3.0]


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


def test_colorbar_strip(tmp_path):
    plt.figure((6, 3))
    plt.contourf(np.add.outer(np.arange(20.0), np.arange(20.0)), levels=[0, 10, 20, 30])
    cb = plt.colorbar(label="z")
    cb.set_label("height")
    p = tmp_path / "cb.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
    assert "height" in s
    assert s.count("<rect") + s.count("<polygon") > 60


def test_colorbar_draws_inside_main_panel():
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.contourf(np.add.outer(np.arange(20.0), np.arange(20.0)), levels=[0, 10, 20, 30])
    fig.colorbar(label="z")
    assert fig.grid == (1, 1)
    assert ax._panel()["colorbar"] is not None


def test_scatter_sizes_and_cmap(tmp_path):
    plt.figure((4, 3))
    plt.scatter([1, 2, 3], [1, 4, 9], s=[20, 60, 120], c=[0.0, 0.5, 1.0], marker="s")
    p = tmp_path / "sc.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
    assert s.count("<rect") >= 4 and "</svg>" in s


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
    assert cs2.get_cmap().name == "viridis"
    cs2.set_cmap("gray")
    assert cs2.get_cmap().name == "gray"
    plt.savefig(tmp_path / "c5.png")
    assert (tmp_path / "c5.png").stat().st_size > 0


def test_contour_explicit_colors_are_used(tmp_path):
    x, y, z = _bump()
    plt.figure((4, 3))
    plt.contour(x, y, z, levels=[0.2, 0.6], colors=["red", "blue"])
    p = tmp_path / "colors.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
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
    s = p.read_text(encoding="utf-8")
    assert "amp" in s
    # min/mid/max tick labels come from the level range (plotters pads with
    # newlines), and the whole axis keeps one decimal so 0 and 1 are not mixed
    # with 0.2.
    assert re.search(r">\s*0\.0\s*</text>", s) and re.search(r">\s*1\.0\s*</text>", s)


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
    assert "value" in p.read_text(encoding="utf-8")

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


def test_imshow_per_pixel_alpha_and_nonuniform_image():
    fig, ax = plt.subplots()
    alpha = np.array([[0.0, 0.5], [1.0, 0.25]])
    image = ax.imshow(np.arange(4.0).reshape(2, 2), alpha=alpha)
    assert image.get_array().shape == (2, 2, 4)
    assert np.allclose(image.get_array()[..., 3], alpha)

    nonuniform = plt.NonUniformImage(ax, extent=(-1.0, 1.0, -1.0, 1.0),
                                     cmap="Purples")
    nonuniform.set_data([-1.0, 0.0, 1.0], [-1.0, 0.0, 1.0], np.arange(9.0).reshape(3, 3))
    rendered = ax.add_image(nonuniform)
    assert isinstance(rendered, plt.AxesImage)
    assert rendered.get_extent() == (-1.0, 1.0, -1.0, 1.0)
    assert fig is not None


def test_streamgraph_and_horizontal_stairs():
    fig, ax = plt.subplots()
    ax.stackplot([0.0, 1.0, 2.0], [1.0, 1.0, 1.0], [1.0, 2.0, 1.0],
                 baseline="wiggle")
    low, high = ax.get_ylim()
    assert low < 0.0 < high

    fig2, ax2 = plt.subplots()
    line = ax2.stairs([1.0, 2.0, 3.0], range(4), orientation="horizontal",
                      fill=True)
    assert line is None
    patch = plt.StepPatch([1.0, 2.0], [0.0, 1.0, 2.0])
    assert patch.get_xy().shape == (6, 2)
    assert fig is not None and fig2 is not None


def test_colorizer_and_contour_linestyle_shims():
    fig, ax = plt.subplots()
    norm = plt.colors.Normalize(vmin=0.0, vmax=1.0)
    colorizer = plt.colorizer.Colorizer(norm=norm, cmap="viridis")
    assert colorizer.norm is norm
    image = ax.imshow(np.arange(9.0).reshape(3, 3), colorizer=colorizer)
    assert image.get_clim() == (0.0, 1.0)
    contour = ax.contour(np.arange(9.0).reshape(3, 3), levels=[2.0, 5.0])
    contour.set_linestyle("solid")
    assert contour.get_linestyle() == "solid"
    assert fig is not None


def test_colorbar_exposes_formatted_tick_labels():
    fig, ax = plt.subplots()
    image = ax.imshow(np.arange(12.0).reshape(3, 4))
    cbar = fig.colorbar(image, ticks=[-1, 0, 1],
                        format=plt.FixedFormatter(["< -1", "0", "> 1"]))
    labels = cbar.ax.get_yticklabels()
    assert [label.get_text() for label in labels] == ["< -1", "0", "> 1"]
    labels[0].set_verticalalignment("top")
    assert cbar.ax.get_yticks() == [-1, 0, 1]


def test_colorbar_axes_accept_scale_and_limits(tmp_path):
    fig, axs = plt.subplots(1, 2)
    pc0 = axs[0].pcolormesh(np.arange(100).reshape(10, 10) + 1)
    cb0 = fig.colorbar(pc0, ax=axs[0])
    cb0.ax.set_yscale("log")
    assert cb0.ax.get_yscale() == "log"
    assert cb0.ax.get_ylim() == (1.0, 100.0)
    panel0 = axs[0]._panel()
    assert panel0["colorbar"][4] is True
    assert panel0["colorbar"][5] is None

    pc1 = axs[1].pcolormesh(np.arange(100).reshape(10, 10) + 1)
    cb1 = fig.colorbar(pc1, ax=axs[1])
    cb1.ax.set_ylim(20, 90)
    assert cb1.ax.get_ylim() == (20.0, 90.0)
    panel1 = axs[1]._panel()
    assert panel1["colorbar"][4] is False
    assert panel1["colorbar"][5] == (20.0, 90.0)

    out = tmp_path / "colorbar-scale-limits.png"
    fig.savefig(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_horizontal_colorbar_scale_limits_and_extensions(tmp_path):
    fig, ax = plt.subplots(figsize=(5, 2))
    image = ax.imshow(np.arange(100.0).reshape(10, 10) + 1)
    cbar = fig.colorbar(image, orientation="horizontal", extend="both")
    cbar.ax.set_xscale("log")
    cbar.ax.set_xlim(20, 90)
    assert cbar.ax.get_xscale() == "log"
    assert cbar.ax.get_xlim() == (20.0, 90.0)
    panel = ax._panel()
    assert panel["colorbar"][4] is True
    assert panel["colorbar"][5] == (20.0, 90.0)
    assert panel["colorbar"][7:] == ("horizontal", "both", False, 0.05)

    fig2, ax2 = plt.subplots(figsize=(5, 2))
    image2 = ax2.imshow(np.arange(100.0).reshape(10, 10) + 1)
    cbar2 = fig2.colorbar(image2, orientation="horizontal", extend="both",
                          extendrect=True, extendfrac=0.2)
    assert ax2._panel()["colorbar"][7:] == ("horizontal", "both", True, 0.2)
    out = tmp_path / "horizontal-colorbar.png"
    fig2.savefig(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert cbar2.ax.get_xlim() == (1.0, 100.0)


def test_axes_facecolor_accepts_rgb_tuples(tmp_path):
    fig, ax = plt.subplots()
    ax.set_facecolor((0, 0, 0))
    assert ax.get_facecolor() == (0, 0, 0)
    ax.set_facecolor((0, 0.5, 0, 1))
    assert ax.get_facecolor() == (0, 0.5, 0, 1)
    ax.set_facecolor((1, 0, 0, 0.5))
    assert ax.get_facecolor() == (1, 0, 0, 0.5)
    fig.savefig(tmp_path / "facecolor.png")


def test_standalone_colorbar_constructor_and_dividers(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 2))
    cmap = plt.get_cmap("viridis")
    norm = plt.colors.BoundaryNorm([0, 1, 2, 3, 4], 4, extend="both")
    cb = plt.Colorbar(ax, cmap=cmap, norm=norm, orientation="horizontal",
                      drawedges=True)
    ax.set_xlim(1.1, 2.9)
    segments = np.asarray(cb.dividers.get_segments())
    assert segments.shape == (3, 2, 2)
    assert np.allclose(segments[:, 0, 0], [1.1, 2.0, 2.9])
    assert ax._panel()["colorbar"][:3] == ("viridis", 0.0, 4.0)
    assert plt.mcolorbar.ColorbarBase is plt.Colorbar
    fig.savefig(tmp_path / "standalone-colorbar.png")


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


def test_imshow_vmin_changes_pixels(tmp_path):
    z = np.linspace(0, 1, 64).reshape(8, 8)
    uris = []
    for vmin in (0.0, 0.5):
        plt.figure((3, 3))
        plt.imshow(z, vmin=vmin, vmax=1.0, cmap="gray")
        p = tmp_path / f"im_{vmin}.svg"
        plt.savefig(p)
        uris.append(re.search(r'href="data:image/png;base64,([^"]+)"', p.read_text(encoding="utf-8")).group(1))
    assert uris[0] != uris[1]


def test_antialiased_interpolation_resamples_shrunk_images():
    # A one-pixel checkerboard shrunk more than 3x must turn into grey; nearest
    # sampling keeps only the original black and white.
    z = (np.indices((1000, 1000)).sum(axis=0) % 2).astype(float)
    blended = []
    for interpolation in ("nearest", "antialiased"):
        plt.figure((3, 3))
        plt.imshow(z, cmap="gray", interpolation=interpolation)
        plt.axis("off")
        width, height, rows = decode_png_rgba(plt.savefig(format="png"))
        blended.append(sum(
            40 < rows[y][x * 4] < 215
            for y in range(height // 4, 3 * height // 4)
            for x in range(width // 4, 3 * width // 4)))
    assert blended[1] > blended[0] + 20


def test_imshow_alpha_and_interpolation(tmp_path):
    z = np.linspace(0, 1, 64).reshape(8, 8)
    uris = []
    for alpha in (1.0, 0.5, 0.0):
        plt.figure((3, 3))
        plt.imshow(z, cmap="gray", alpha=alpha)
        p = tmp_path / f"alpha_{alpha}.svg"
        plt.savefig(p)
        uris.append(re.search(r'href="data:image/png;base64,([^"]+)"', p.read_text(encoding="utf-8")).group(1))
    assert len(set(uris)) == 3

    plt.figure((3, 3))
    plt.imshow(z, interpolation="nearest")
    p = tmp_path / "nearest.svg"
    plt.savefig(p)
    assert "image-rendering:pixelated" in p.read_text(encoding="utf-8")

    plt.figure((3, 3))
    plt.imshow(z, interpolation="spline16")
    p = tmp_path / "spline16.svg"
    plt.savefig(p)
    assert p.stat().st_size > 0
    with pytest.raises(ValueError):
        plt.imshow(z, interpolation="not-a-real-filter")
    with pytest.raises(ValueError):
        plt.imshow(z, alpha=float("nan"))


def test_module_level_matshow_xkcd_and_data_path():
    plt.rcdefaults()
    plt.figure((4, 3))
    plt.matshow(np.arange(6).reshape(2, 3))
    ax = plt.gca()
    assert ax.get_xlim() == (-0.5, 2.5)
    assert ax.get_ylim() == (1.5, -0.5)
    # `with plt.xkcd():` must work even though the sketch style is a no-op.
    with plt.xkcd() as context:
        assert context is not None
    assert os.path.isdir(plt.get_data_path())
    assert ax.twin(object) is not ax


def test_axes_spy_returns_an_image_handle(tmp_path):
    plt.rcdefaults()
    fig, axs = plt.subplots(1, 2)
    x = np.eye(5)
    image = axs[0].spy(x, markersize=5)
    assert image in axs[0].images
    assert len(axs[0].get_xticks()) == 0 and len(axs[0].get_yticks()) == 0
    axs[1].spy(x, precision=0.1)
    plt.spy(x)
    assert plt.gca().images
    out = tmp_path / "spy.png"
    fig.savefig(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_pyplot_imsave_png_roundtrip():
    data = np.array([[0.0, 0.5], [1.0, 0.25]])
    buf = io.BytesIO()
    plt.imsave(buf, data, format="png", cmap="viridis")
    decoded = plt.imread(io.BytesIO(buf.getvalue()))
    assert decoded.shape == (2, 2, 4)
    assert np.allclose(decoded[..., 3], 1.0)
    assert not np.allclose(decoded[0, 0, :3], decoded[1, 0, :3])

    rgb = np.array([[[255, 0, 0], [0, 255, 0]]], dtype=np.uint8)
    buf = io.BytesIO()
    plt.imsave(buf, rgb, format="png")
    decoded = plt.imread(io.BytesIO(buf.getvalue()))
    assert decoded.shape == (1, 2, 3)
    assert np.allclose(decoded[0, 0], [1.0, 0.0, 0.0])

    flipped = np.array([[0.0, 1.0], [0.5, 0.25]])
    buf = io.BytesIO()
    plt.imsave(buf, flipped, format="png", origin="lower")
    decoded = plt.imread(io.BytesIO(buf.getvalue()))
    assert not np.allclose(decoded[0, 0], decoded[0, 1])
    with pytest.raises(ValueError):
        plt.imsave(io.BytesIO(), np.zeros((2, 2, 2)), format="png")

    for fmt in ("pdf", "svg", "eps"):
        target = io.BytesIO()
        plt.imsave(target, np.array([[0.0, 1.0]]), format=fmt)
        assert target.getvalue()


def test_imsave_png_writes_exact_pixels():
    gray = np.array([[0, 255], [64, 128]], dtype=np.uint8)
    rgba = np.dstack([gray, gray, gray, np.full_like(gray, 255)])
    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    decoded = np.round(plt.imread(io.BytesIO(buf.getvalue())) * 255).astype(np.uint8)
    assert np.array_equal(decoded, rgba)

    values = np.array([[0.0, 0.5], [0.25, 1.0]])
    expected = np.round(
        plt.get_cmap("gray")(values) * 255).astype(np.uint8)
    buf = io.BytesIO()
    plt.imsave(buf, values, format="png", cmap="gray", vmin=0.0, vmax=1.0)
    decoded = np.round(plt.imread(io.BytesIO(buf.getvalue())) * 255).astype(np.uint8)
    assert np.array_equal(decoded, expected)

    buf = io.BytesIO()
    plt.imsave(buf, values, format="png", cmap="gray", vmin=0.0, vmax=1.0,
               origin="lower")
    flipped = np.round(plt.imread(io.BytesIO(buf.getvalue())) * 255).astype(np.uint8)
    assert np.array_equal(flipped, expected[::-1])


def test_pyplot_imsave_pillow_formats(tmp_path):
    pytest.importorskip("PIL")
    exact = np.array([[[255, 0, 0, 255], [0, 0, 255, 128]]], dtype=np.uint8)
    target = tmp_path / "image.tiff"
    plt.imsave(target, exact, format="tiff")
    decoded = np.round(plt.imread(target) * 255).astype(np.uint8)
    assert np.array_equal(decoded, exact)

    target = tmp_path / "image.jpg"
    plt.imsave(target, np.broadcast_to(np.array([200, 30, 40], np.uint8),
                                       (8, 8, 3)), format="jpg")
    decoded = plt.imread(target)
    assert decoded.shape == (8, 8, 3)
    mean = decoded.reshape(-1, 3).mean(axis=0) * 255
    assert mean[0] > 180 and mean[1] < 60 and mean[2] < 70


def test_axes_quiverkey_draws_an_arrow_and_label():
    fig, ax = plt.subplots()
    quiver = ax.quiver([0.0, 1.0], [0.0, 1.0], [1.0, 0.0], [0.0, 1.0])
    assert ax.quiverkey(quiver, 0.5, 0.9, 1.0, "1 m/s") is None
    assert len(ax.patches) == 1
    assert [text.get_text() for text in ax.texts] == ["1 m/s"]
    with pytest.raises(TypeError):
        ax.quiverkey(object(), 0.5, 0.9, 1.0, "bad")
    plt.close(fig)


def test_axes_get_cursor_data_reads_images():
    fig, ax = plt.subplots()
    ax.imshow(np.arange(12).reshape(3, 4))

    class Inside:
        xdata, ydata = 1.0, 1.0

    class Outside:
        xdata, ydata = 99.0, 99.0

    assert ax.get_cursor_data(Inside()) == 5.0
    assert ax.get_cursor_data(Outside()) is None
    plt.close(fig)


def test_figimage_places_rgb_pixels_at_figure_offsets():
    fig = plt.figure((0.4, 0.3), dpi=100)
    image = np.zeros((4, 5, 3))
    image[:] = (1.0, 0.0, 0.0)
    image[0] = (0.0, 1.0, 0.0)
    artist = fig.figimage(image, xo=10, yo=6, origin="lower")
    assert artist.get_array().shape == (4, 5, 3)

    width, height, rows = decode_png_rgba(fig.savefig(format="png"))
    assert (width, height) == (40, 30)

    def pixel(x, y):
        offset = x * 4
        return tuple(rows[y][offset:offset + 3])

    # Six pixels up from the bottom, the original first row is at the bottom
    # of the placed image because origin="lower" flips it for SVG's top-left
    # coordinate system.
    assert pixel(12, height - 6 - 1) == (0, 255, 0)
    assert pixel(12, height - 6 - 4) == (255, 0, 0)
    assert pixel(5, 5) == (255, 255, 255)


def test_figimage_rejects_oversized_dimensions_pixels_and_payload(monkeypatch):
    fig = plt.figure((0.4, 0.3), dpi=100)
    image = np.zeros((10, 10, 3))

    monkeypatch.setattr(plt, "_MAX_FIGIMAGE_DIM", 8)
    with pytest.raises(ValueError, match="exceed maximum allowed dimension"):
        fig.figimage(image)

    monkeypatch.setattr(plt, "_MAX_FIGIMAGE_DIM", 100)
    monkeypatch.setattr(plt, "_MAX_FIGIMAGE_PIXELS", 50)
    with pytest.raises(ValueError, match="pixel count"):
        fig.figimage(image)

    monkeypatch.setattr(plt, "_MAX_FIGIMAGE_PIXELS", 1_000)
    monkeypatch.setattr(plt, "_MAX_FIGIMAGE_BYTES", 100)
    with pytest.raises(ValueError, match="embedded base64 payload"):
        fig.figimage(image)


def test_axes_grid1_imagegrid_and_locatable_divider(tmp_path):
    from matplotvite.mpl_toolkits.axes_grid1 import ImageGrid, make_axes_locatable

    image = np.arange(100).reshape(10, 10)
    fig = plt.figure((4, 4))
    grid = ImageGrid(fig, 111, nrows_ncols=(2, 2), axes_pad=0.1)
    assert len(grid) == 4 and grid.axes_llc is grid[2]
    boxes = [ax.get_position().bounds for ax in grid]
    assert boxes[0][2] > 0.3 and boxes[1][0] > boxes[0][0]
    for ax in grid:
        ax.imshow(image)
    fig.savefig(tmp_path / "imagegrid.png")

    fig, ax = plt.subplots(figsize=(4, 4))
    divider = make_axes_locatable(ax)
    top = divider.append_axes("top", 1.0, pad=0.1, sharex=ax)
    right = divider.append_axes("right", 1.0, pad=0.1, sharey=ax)
    assert top.get_position().y0 > ax.get_position().y1
    assert right.get_position().x0 > ax.get_position().x1
    top.hist(np.linspace(0, 1, 20), bins=5)
    right.hist(np.linspace(0, 1, 20), bins=5, orientation="horizontal")
    fig.savefig(tmp_path / "locatable.png")


def test_axes_grid1_rgb_axes(tmp_path):
    from matplotvite.mpl_toolkits.axes_grid1.axes_rgb import RGBAxes, make_rgb_axes

    fig = plt.figure((4, 3))
    rgb = RGBAxes(fig, [0.05, 0.05, 0.9, 0.9], pad=0.02)
    red = np.linspace(0, 1, 16).reshape(4, 4)
    images = rgb.imshow_rgb(red, red[::-1], red.T)
    assert len(images) == 4 and len(fig.axes) == 4

    fig, ax = plt.subplots(figsize=(4, 3))
    channels = make_rgb_axes(ax, pad=0.02)
    assert len(channels) == 3
    assert ax.get_position().width < 0.8
    fig.savefig(tmp_path / "rgb_axes.png")


def test_triangulation_and_interpolation():
    from matplotvite import tri

    x = np.array([0.0, 1.0, 0.0, 0.0, 0.5])
    y = np.array([0.0, 0.0, 1.0, 0.5, 0.25])
    triangulation = tri.Triangulation(x, y)
    assert len(triangulation.triangles) >= 4
    assert triangulation.get_trifinder()(0.2, 0.2) >= 0
    assert triangulation.get_trifinder()(2.0, 2.0) == -1

    triangulation.set_mask(np.zeros(len(triangulation.triangles), dtype=bool))
    z = 2.0 * x + 3.0 * y + 1.0
    interp = tri.LinearTriInterpolator(triangulation, z)
    assert interp(0.2, 0.2) == pytest.approx(2.0 * 0.2 + 3.0 * 0.2 + 1.0)
    assert np.isnan(interp(2.0, 2.0))

    refined, z_refined = tri.UniformTriRefiner(triangulation).refine_field(z, subdiv=1)
    assert len(refined.triangles) == 4 * len(triangulation.triangles)
    assert np.allclose(2.0 * refined.x + 3.0 * refined.y + 1.0, z_refined)
    assert not tri.TriAnalyzer(triangulation).get_flat_tri_mask().any()


def test_tri_axes_and_pyplot_helpers(tmp_path):
    from matplotvite import tri

    x = np.array([0.0, 1.0, 0.0, 1.0])
    y = np.array([0.0, 0.0, 1.0, 1.0])
    z = np.array([0.0, 1.0, 1.0, 2.0])
    triangles = np.array([[0, 1, 2], [1, 3, 2]])
    triangulation = tri.Triangulation(x, y, triangles)

    fig, ax = plt.subplots()
    lines = ax.triplot(triangulation, "bo-")
    assert len(lines) == 1
    contour = ax.tricontour(triangulation, z, levels=3)
    assert len(contour.levels) == 3
    filled = ax.tricontourf(triangulation, z, levels=3)
    artists, labels = filled.legend_elements(str_format="{:2.1f}".format)
    assert len(artists) == len(labels) == 3
    image = ax.tripcolor(triangulation, z, shading="gouraud")
    assert image is not None
    ax.tricontour(x, y, triangles, z)
    ax.tripcolor(x, y, triangles, z)
    fig.savefig(tmp_path / "tri.png")

    plt.figure((4, 3))
    plt.triplot(triangulation)
    plt.tricontour(triangulation, z)
    plt.tricontourf(triangulation, z)
    plt.tripcolor(triangulation, z)
    plt.savefig(tmp_path / "tri-pyplot.png")


def test_streamplot_colors_masks_arrows_and_colorbar(tmp_path):
    w = 3
    Y, X = np.mgrid[-w:w:20j, -w:w:20j]
    U = -1 - X**2 + Y
    V = 1 + X - Y**2
    fig, ax = plt.subplots()
    stream = ax.streamplot(X, Y, U, V, color=U, linewidth=2, cmap="autumn",
                           density=0.7, num_arrows=3)
    assert stream.lines.get_segments()
    assert stream.lines.get_array() is not None
    cbar = fig.colorbar(stream.lines)
    assert cbar.ax is not None

    masked = np.ma.array(U, mask=np.zeros(U.shape, dtype=bool))
    masked.mask[5:10, 5:10] = True
    ax.streamplot(X, Y, masked, V, color="r", start_points=[[-1, 0]],
                  integration_direction="backward")
    fig.savefig(tmp_path / "streamplot.png")

    with np.testing.assert_raises_regex(ValueError, "equally spaced"):
        ax.streamplot([0, 1, 3], [0, 1], np.ones((2, 3)), np.zeros((2, 3)))


def test_lightsource_hillshade_blends_and_rgb_hsv():
    from matplotvite import LightSource

    y, x = np.mgrid[-2:2:40j, -2:2:50j]
    z = np.sin(x) * np.cos(y)
    ls = LightSource(azdeg=315, altdeg=45)
    shade = ls.hillshade(z, vert_exag=2, dx=0.1, dy=0.1)
    assert shade.shape == z.shape
    assert 0.0 <= shade.min() <= shade.max() <= 1.0
    assert np.allclose(np.linalg.norm(ls.direction), 1.0)

    shaded = ls.shade(z, plt.colormaps["copper"], vmin=-1, vmax=1)
    assert shaded.shape == (*z.shape, 4)
    for mode in ("hsv", "overlay", "soft"):
        blended = ls.shade_rgb(np.ones((*z.shape, 3)), z, blend_mode=mode)
        assert blended.shape == (*z.shape, 3)

    rgb = np.stack([x, y, np.full_like(x, 0.5)], axis=-1)
    hsv = plt.rgb_to_hsv(rgb)
    assert np.allclose(plt.hsv_to_rgb(hsv), rgb, atol=1e-12)


def test_pcolormesh_renders_image(tmp_path):
    rng = np.random.default_rng(3)
    x = np.linspace(0, 1, 5)
    y = np.linspace(0, 1, 5)
    z = rng.random((4, 4))
    plt.figure((4, 3))
    plt.pcolormesh(x, y, z, cmap="gray")
    p = tmp_path / "pm.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8")
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
        uris.append(re.search(r'href="data:image/png;base64,([^"]+)"', p.read_text(encoding="utf-8")).group(1))
    assert uris[0] != uris[1]


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
    assert '<image' in p.read_text(encoding="utf-8") and "data:image/png;base64," in p.read_text(encoding="utf-8")
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
    assert p.read_text(encoding="utf-8").upper().count("<POLYGON") >= coll.get_array().size
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
    q = ax.quiver([0, 1], [1, 3], [1, 1], [1, -1],
                  color=["red", "green"], pivot="tail")
    assert q.get_offsets().shape == (2, 2)
    assert np.allclose(q.get_U(), [1, 1]) and np.allclose(q.get_V(), [1, -1])
    # Matplotlib autoscales on the arrow tails; arrows may leave the limits.
    assert ax.get_xlim() == pytest.approx((-0.05, 1.05))
    assert ax.get_ylim() == pytest.approx((0.9, 3.1))
    p = tmp_path / "quiver.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
    assert s.count("<POLYGON") >= 2  # one filled arrow each
    assert "#FF0000" in s and "#008000" in s


def test_quiver_forms_scale_and_validation(tmp_path):
    plt.figure()
    ax = plt.gca()
    grid = ax.quiver(np.ones((2, 3)), np.zeros((2, 3)))
    assert grid.get_offsets().shape == (6, 2)
    scaled = ax.quiver([0], [0], [2], [1], scale=2, pivot="tip", angles="uv")
    # U/V stay in data units; the renderer applies `scale` in pixels.
    assert np.allclose(scaled.get_U(), [2.0]) and np.allclose(scaled.get_V(), [1.0])
    assert np.allclose(scaled.get_offsets(), [[0.0, 0.0]])
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
    with pytest.raises(ValueError):
        ax.quiver([0], [0], [1], [1], units="furlongs")
    with pytest.raises(ValueError):
        ax.quiver([0], [0], [1], [1], scale_units="furlongs")
    with pytest.raises(TypeError):
        ax.quiver([0])


def test_quiver_length_is_measured_in_axes_widths(tmp_path):
    lengths = []
    for scale in (4, 8):
        plt.figure()
        ax = plt.gca()
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(-1, 1)
        ax.quiver([0.0], [0.0], [1.0], [0.0], scale=scale, units="width")
        p = tmp_path / f"quiver_scale_{scale}.png"
        plt.savefig(p)
        lengths.append(_ink_width(p))
    # scale divides the length in axes widths, so doubling it halves the arrow.
    assert lengths[0] / lengths[1] == pytest.approx(2.0, rel=0.08)


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
    # matplotlib.cm re-exports the colors module.
    assert plt.cm.colors is plt.colors
    assert plt.cm.colors.Normalize(vmin=0, vmax=2).vmax == 2
    assert plt.get_cmap("viridis", 8).N == 8
    assert np.allclose(plt.get_cmap("viridis", 8)(1.0), cmap(1.0), atol=0.01)
    with pytest.raises(ValueError):
        plt.get_cmap("not-a-colormap")
    with pytest.raises(AttributeError):
        _ = plt.cm.not_a_colormap


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
    # `get_cmap` returns a colormap object, as Matplotlib's does.
    assert image.get_cmap().name == "plasma"
    plt.set_cmap(plt.get_cmap("magma"))
    plt.figure((3, 2))
    assert plt.imshow(np.zeros((2, 2))).get_cmap().name == "magma"
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


def test_rgb_tuples_work_across_artists(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1], color=(1, 0, 0))
    ax.bar([0], [1], color=(0, 0, 1))
    ax.scatter([0], [1], c=(0, 1, 0))
    p = tmp_path / "tuples.svg"
    fig.savefig(p)
    svg = p.read_text(encoding="utf-8").upper()
    assert "#FF0000" in svg and "#0000FF" in svg and "#00FF00" in svg

    with pytest.raises(ValueError):
        ax.plot([0, 1], [0, 1], color="not-a-colour")
    with pytest.raises(ValueError):
        plt.figure(facecolor="#gggggg")


def test_module_level_clabel_labels_contours():
    fig, ax = plt.subplots()
    cs = ax.contour([[0.0, 1.0], [1.0, 0.0]], levels=[0.5])
    assert plt.clabel(cs, levels=[0.5])


def test_images_have_sticky_edges_and_no_default_resampling():
    plt.figure()
    ax = plt.gca()
    ax.imshow(np.zeros((3, 4)))
    assert ax.get_xlim() == (-0.5, 3.5) and ax.get_ylim() == (2.5, -0.5)
    assert ax.yaxis_inverted()
    assert ax.images[0].get_interpolation() == "nearest"
    ax.plot([0, 10], [0, 1])
    assert ax.get_xlim() == pytest.approx((-0.5, 10.525))


def test_image_interpolation_rc_default(tmp_path):
    old = plt.rcParams["image.interpolation"]
    try:
        plt.rcParams["image.interpolation"] = "antialiased"
        fig = plt.figure((3, 3))
        ax = fig.gca()
        ax.imshow(np.linspace(0, 1, 64).reshape(8, 8), cmap="gray")
        assert ax.images[0].get_interpolation() == "antialiased"
        p = tmp_path / "smooth.svg"
        fig.savefig(p)
        assert "image-rendering:pixelated" not in p.read_text(encoding="utf-8")
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


def test_quiver_broadcasts_coordinate_axes(tmp_path):
    x, y = np.arange(3.0), np.arange(2.0)
    u, v = np.meshgrid(x, y)
    plt.figure()
    plt.quiver(x, y, u, v)
    p = tmp_path / "quiver.png"
    plt.savefig(p)
    assert p.stat().st_size > 0


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


def test_contour_accepts_a_contourset_and_set_linewidth(tmp_path):
    plt.rcdefaults()
    z = np.add.outer(np.arange(8.0), np.arange(8.0))
    fig, ax = plt.subplots()
    first = ax.contour(z, levels=[2, 5, 8])
    second = ax.contour(first, levels=first.levels[::2], colors="k")
    assert second.levels == [2.0, 8.0]
    first.set_linewidth([0.5, 1.0, 2.0])
    assert first.get_linewidths() == [0.5, 1.0, 2.0]
    p = tmp_path / "contour.svg"
    plt.savefig(p)
    assert p.stat().st_size > 0


def test_custom_colormaps_from_a_list_and_channel_tables():
    plt.rcdefaults()
    listed = plt.colors.LinearSegmentedColormap.from_list(
        "test_list", ["#ff0000", "#00ff00", "#0000ff"], N=16)
    assert listed.name == "test_list" and listed.N == 16
    channels = {"red": ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
                "green": ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
                "blue": ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))}
    table = plt.colors.LinearSegmentedColormap("test_table", channels, N=8)
    assert table.N == 8
    assert tuple(np.asarray(table(1.0)).ravel()[:3]) == pytest.approx((1.0, 0.0, 0.0))
    plt.colormaps.register(table)
    plt.figure()
    plt.imshow(np.linspace(0, 1, 64).reshape(8, 8), cmap=table)
    assert plt.gca().images[0].get_cmap().name == "test_table"


def test_norms_change_the_image_mapping(tmp_path):
    plt.rcdefaults()
    data = np.array([[1.0, 10.0], [100.0, 1000.0]])
    log = plt.colors.LogNorm(vmin=1.0, vmax=1000.0)
    assert log(10.0) == pytest.approx(1 / 3, abs=1e-9)
    assert log(1000.0) == pytest.approx(1.0)
    assert log.inverse(1 / 3) == pytest.approx(10.0)

    power = plt.colors.PowerNorm(2.0, vmin=0.0, vmax=2.0)
    assert power(1.0) == pytest.approx(0.25)

    symlog = plt.colors.SymLogNorm(linthresh=1.0, vmin=-100.0, vmax=100.0)
    assert symlog(0.0) == pytest.approx(0.5)
    assert symlog(100.0) == pytest.approx(1.0)

    plt.figure()
    image = plt.imshow(data, cmap="viridis", origin="lower", norm=log)
    # The norm is folded into the data, so the renderer sees a 0-1 range.
    assert image._e["vmin"] == 0.0 and image._e["vmax"] == 1.0
    # imshow stores rows bottom-up for a lower origin.
    assert np.allclose(image._e["data"], np.flipud([[0.0, 1 / 3], [2 / 3, 1.0]]))
    p = tmp_path / "lognorm.png"
    plt.savefig(p)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_clabel_labels_contours(tmp_path):
    plt.rcdefaults()
    X, Y = np.meshgrid(np.linspace(-2, 2, 40), np.linspace(-2, 2, 40))
    Z = np.exp(-(X ** 2 + Y ** 2))
    figure, axes = plt.subplots()
    contours = axes.contour(X, Y, Z, levels=5)
    handles = contours.clabel(fmt="%1.2f")
    texts = [t[2] for t in axes.texts]
    assert texts == ["0.25", "0.50", "0.75", "0.99"]
    assert len(handles) == len(texts)
    assert all(isinstance(t[9], float) for t in axes.texts)
    p = tmp_path / "clabel.svg"
    figure.savefig(p)
    assert "0.75" in p.read_text(encoding="utf-8")
    # Manual placement with no positions falls back to automatic labels.
    assert len(contours.clabel(manual=True)) == len(handles)


def test_axes_image_artist_constructor():
    """Subclasses can build an AxesImage before filling it with set_array."""
    from matplotvite import AxesImage

    fig, ax = plt.subplots()

    class RibbonImage(AxesImage):
        def __init__(self, axes, extent, **kwargs):
            super().__init__(axes, extent=extent, interpolation="bicubic", **kwargs)
            self.set_transform(ax.transData)

    image = RibbonImage(ax, extent=(0, 1, 0, 1))
    assert image.get_array() is None
    assert image.get_extent() == (0.0, 1.0, 0.0, 1.0)
    image.set_array(np.zeros((2, 2, 4)))
    assert image.get_array().shape == (2, 2, 4)
    image.draw()
    fig.savefig(None, format="png")


@pytest.mark.parametrize(
    "name,depth,color,rows,palette,transparency,expected",
    [
        pytest.param("gray-1", 1, 0, [[0, 1], [1, 0]], None, None,
                     [[0, 1], [1, 0]], id="gray-1"),
        pytest.param("gray-2", 2, 0, [[0, 1], [2, 3]], None, None,
                     [[0, 1 / 3], [2 / 3, 1]], id="gray-2"),
        pytest.param("gray-4", 4, 0, [[0, 5], [10, 15]], None, None,
                     [[0, 5 / 15], [10 / 15, 1]], id="gray-4"),
        pytest.param("gray-8", 8, 0, [[0, 64], [128, 255]], None, None,
                     [[0, 64 / 255], [128 / 255, 1]], id="gray-8"),
        pytest.param("gray-16", 16, 0, [[0, 16384], [32768, 65535]], None, None,
                     [[0, 16384 / 65535], [32768 / 65535, 1]], id="gray-16"),
        pytest.param(
            "rgb-8", 8, 2,
            [[255, 0, 0, 0, 255, 0], [0, 0, 255, 255, 255, 0]], None, None,
            [[[1, 0, 0], [0, 1, 0]], [[0, 0, 1], [1, 1, 0]]], id="rgb-8"),
        pytest.param(
            "rgb-16", 16, 2,
            [[65535, 0, 0, 0, 65535, 0], [0, 0, 65535, 65535, 65535, 0]],
            None, None,
            [[[1, 0, 0], [0, 1, 0]], [[0, 0, 1], [1, 1, 0]]], id="rgb-16"),
        pytest.param(
            "palette-1", 1, 3, [[0, 1], [1, 0]],
            bytes([255, 0, 0, 0, 255, 0]), None,
            [[[1, 0, 0], [0, 1, 0]], [[0, 1, 0], [1, 0, 0]]], id="palette-1"),
        pytest.param(
            "palette-2", 2, 3, [[0, 1], [2, 0]],
            bytes([255, 0, 0, 0, 255, 0, 0, 0, 255]), None,
            [[[1, 0, 0], [0, 1, 0]], [[0, 0, 1], [1, 0, 0]]], id="palette-2"),
        pytest.param(
            "palette-4", 4, 3, [[0, 1], [2, 0]],
            bytes([255, 0, 0, 0, 255, 0, 0, 0, 255]), None,
            [[[1, 0, 0], [0, 1, 0]], [[0, 0, 1], [1, 0, 0]]], id="palette-4"),
        pytest.param(
            "palette-8", 8, 3, [[0, 1], [2, 0]],
            bytes([255, 0, 0, 0, 255, 0, 0, 0, 255]), None,
            [[[1, 0, 0], [0, 1, 0]], [[0, 0, 1], [1, 0, 0]]], id="palette-8"),
        pytest.param(
            "palette-trns", 8, 3, [[0, 1], [1, 0]],
            bytes([255, 0, 0, 0, 255, 0]), bytes([255, 128]),
            [[[1, 0, 0, 1], [0, 1, 0, 128 / 255]],
             [[0, 1, 0, 128 / 255], [1, 0, 0, 1]]], id="palette-trns"),
        pytest.param(
            "gray-alpha-8", 8, 4, [[0, 255, 128, 64], [128, 255, 0, 64]],
            None, None,
            [[[0, 0, 0, 1], [128 / 255, 128 / 255, 128 / 255, 64 / 255]],
             [[128 / 255, 128 / 255, 128 / 255, 1],
              [0, 0, 0, 64 / 255]]], id="gray-alpha-8"),
        pytest.param(
            "gray-alpha-16", 16, 4,
            [[0, 65535, 16384, 32768], [32768, 65535, 0, 16384]], None, None,
            [[[0, 0, 0, 1],
              [16384 / 65535, 16384 / 65535, 16384 / 65535, 32768 / 65535]],
             [[32768 / 65535, 32768 / 65535, 32768 / 65535, 1],
              [0, 0, 0, 16384 / 65535]]], id="gray-alpha-16"),
        pytest.param(
            "rgba-8", 8, 6,
            [[255, 0, 0, 255, 0, 255, 0, 128], [0, 0, 255, 0, 255, 255, 0, 255]],
            None, None,
            [[[1, 0, 0, 1], [0, 1, 0, 128 / 255]],
             [[0, 0, 1, 0], [1, 1, 0, 1]]], id="rgba-8"),
        pytest.param(
            "rgba-16", 16, 6,
            [[65535, 0, 0, 65535, 0, 65535, 0, 32768],
             [0, 0, 65535, 0, 65535, 65535, 0, 65535]],
            None, None,
            [[[1, 0, 0, 1], [0, 1, 0, 32768 / 65535]],
             [[0, 0, 1, 0], [1, 1, 0, 1]]], id="rgba-16"),
    ],
)
def test_imread_decodes_png_formats(tmp_path, name, depth, color, rows, palette,
                                    transparency, expected):
    """`imread` covers PNG colour types and every standard bit depth."""
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    path = tmp_path / f"{name}.png"
    _write_png(path, len(rows[0]) // channels, len(rows), depth, color, rows,
               palette=palette, transparency=transparency)
    np.testing.assert_allclose(plt.imread(path), np.asarray(expected, dtype=float))


def test_imread_decodes_png_without_pillow(tmp_path):
    """`imread` reads the PNGs the renderer writes without an image library."""
    path = tmp_path / "readback.png"
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.imshow(np.array([[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                        [[0.0, 0.0, 1.0], [1.0, 1.0, 0.0]]]))
    fig.savefig(path)

    data = plt.imread(path)
    assert data.shape == (200, 200, 4)
    assert data.dtype == np.float64
    assert 0.0 <= data.min() <= data.max() <= 1.0
    assert np.allclose(data[..., 3], 1.0)
    with path.open("rb") as stream:
        assert plt.imread(stream).shape == data.shape
