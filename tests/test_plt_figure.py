"""Figure lifecycle, subplot layout and output formats."""

import io
import re
import struct
import zlib

import matplotvite as plt
import numpy as np
import pytest
from plt_helpers import (
    _fig,
)
from png_utils import decode_png_rgba


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
    s = p.read_text(encoding="utf-8")
    assert s.startswith("<svg") and "sq" in s and "</svg>" in s


def test_empty_figure_saves_blank(tmp_path):
    fig = plt.figure((4, 3))
    p = tmp_path / "e.png"
    fig.savefig(p)
    b = p.read_bytes()
    assert b[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(b[16:20], "big") == 400
    assert int.from_bytes(b[20:24], "big") == 300
    assert fig.savefig(None, format="svg").decode().startswith("<svg")


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
    assert svg.read_text(encoding="utf-8").startswith("<svg")


def test_pdf_background_alpha_is_blended_over_white(tmp_path):
    fig = plt.figure((2, 2), facecolor=(1.0, 0.0, 0.0, 0.5))
    fig.gca().plot([0, 1], [1, 0])
    p = tmp_path / "alpha.pdf"
    fig.savefig(p)
    assert re.search(rb"1 0\.498\d* 0\.498\d* rg", p.read_bytes())


def test_bad_savefig_kwargs(tmp_path):
    plt.figure(); plt.plot([1, 2])
    # format="pdf" is now supported; only bbox_inches="loose" should raise
    with pytest.raises(ValueError):
        plt.savefig(tmp_path / "x.png", bbox_inches="loose")


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


def test_axes_clear_empties_the_figure(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.plot([1, 2], [2, 1])
    ax.text(0, 0, "gone")
    ax.clear()
    assert ax.get_xlim() == pytest.approx((-0.05, 1.05))
    p = tmp_path / "empty.svg"
    plt.savefig(p)
    assert "gone" not in p.read_text(encoding="utf-8")


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


def test_figure_state_accessors(tmp_path):
    fig = plt.figure((4, 3))
    ax = fig.add_axes([0.1, 0.1, 0.8, 0.8])
    assert fig.get_figwidth() == 4.0 and fig.get_figheight() == 3.0
    fig.set_figwidth(5)
    fig.set_figheight(2.5)
    assert fig.get_size_inches() == pytest.approx((5.0, 2.5))
    assert fig.get_linewidth() == 0.0
    fig.set_linewidth(2.0)
    assert fig.get_linewidth() == 2.0
    with pytest.raises(ValueError):
        fig.set_linewidth(-1)
    fig.set_edgecolor("red")
    assert fig.get_edgecolor()
    fig.suptitle("Top")
    fig.supxlabel("X")
    fig.supylabel("Y")
    assert fig.get_suptitle() == "Top"
    assert fig.get_supxlabel() == "X" and fig.get_supylabel() == "Y"
    assert fig.get_constrained_layout_pads() == (None, None, None, None)
    assert fig.sca(ax) is ax
    fig.set_dpi(120)
    assert fig.get_dpi() == 120
    p = tmp_path / "state.png"
    fig.savefig(p)
    b = p.read_bytes()
    assert (int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")) == (600, 300)

    other = fig.add_axes([0.0, 0.0, 0.5, 0.5])
    fig.delaxes(other)
    assert other not in fig.get_axes()
    fig.clf()
    assert fig.get_axes() == [] and fig.get_suptitle() == ""
    assert fig.get_supxlabel() == "" and fig.get_supylabel() == ""


def test_mpl_toolkits_inset_axes(tmp_path):
    from matplotvite.mpl_toolkits.axes_grid1.inset_locator import (
        inset_axes,
        zoomed_inset_axes,
    )

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
    assert "#FF0000" in p.read_text(encoding="utf-8").upper()


def test_pdfpages_writes_multiple_pages(tmp_path):
    from matplotvite.backends.backend_pdf import PdfPages

    path = tmp_path / "multipage.pdf"
    with PdfPages(path) as pdf:
        for index in range(2):
            fig, ax = plt.subplots(figsize=(3, 2))
            ax.plot([0, 1], [index, index + 1])
            pdf.savefig(fig)
            plt.close(fig)
        pdf.attach_note("a note")
        pdf.infodict()["Title"] = "Two pages"
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"/Count 2" in data


def test_savefig_eps_writes_postscript(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    path = tmp_path / "figure.eps"
    fig.savefig(path, dpi=150)
    data = path.read_bytes()
    assert data.startswith(b"%!PS-Adobe-3.0 EPSF-3.0\n")
    assert b"%%BoundingBox: 0 0 " in data
    assert b"showpage" in data
    assert data.rstrip().endswith(b"%%EOF")


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
    assert "#FF0000" in p.read_text(encoding="utf-8").upper()


def test_rc_figure_figsize_sets_new_figures():
    plt.rcdefaults()
    try:
        plt.rcParams["figure.figsize"] = (8, 6)
        assert plt.figure().get_size_inches() == pytest.approx((8.0, 6.0))
        fig, _ = plt.subplots()
        assert fig.get_size_inches() == pytest.approx((8.0, 6.0))
        # An explicit figsize still wins over the rcParam, as in Matplotlib.
        assert plt.figure(figsize=(3, 2)).get_size_inches() == pytest.approx((3.0, 2.0))
    finally:
        plt.rcdefaults()


def test_fractional_dpi_truncates_figure_pixels():
    plt.figure(figsize=(6.4, 4.8))
    png = plt.savefig(format="png", dpi=72)
    assert int.from_bytes(png[16:20], "big") == 460
    assert int.from_bytes(png[20:24], "big") == 345
    plt.close("all")


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


def test_twinx_png_keeps_primary_and_twin_axes():
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 1, 2], [1, 4, 9], color="red", linewidth=4)
    twin = ax.twinx()
    twin.plot([0, 1, 2], [9, 4, 1], color="blue", linewidth=4)
    width, height, rows = decode_png_rgba(fig.savefig(format="png"))
    assert (width, height) == (500, 400)
    red = blue = dark_left = 0
    for _y, row in enumerate(rows):
        for x in range(0, width * 4, 4):
            r, g, b = row[x], row[x + 1], row[x + 2]
            red += r > 160 and g < 100 and b < 100
            blue += b > 160 and r < 100 and g < 100
            if x < width // 5 * 4 and r < 100 and g < 100 and b < 100:
                dark_left += 1
    assert red > 20 and blue > 20
    assert dark_left > 20


def test_figure_and_savefig_colors_and_bytes(tmp_path):

    fig = plt.figure((4, 3), dpi=72, facecolor="red", edgecolor="blue")
    fig.gca().plot([0, 1], [0, 1])
    p = tmp_path / "bg.svg"
    fig.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
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


def test_figure_accepts_number_and_positional_figsize():
    plt.close("all")
    first = plt.figure(1)
    assert first.number == 1
    assert first.get_size_inches() == pytest.approx((6.4, 4.8))
    second = plt.figure(2, (4, 3))
    assert second.number == 2 and second.get_size_inches() == pytest.approx((4, 3))
    third = plt.figure(3, figsize=(5, 4))
    assert third.number == 3 and third.get_size_inches() == pytest.approx((5, 4))
    assert plt.figure(1) is first
    plt.close("all")


def test_savefig_accepts_pad_inches(tmp_path):
    """Matplotlib callers pass pad_inches=0 with bbox_inches='tight'."""
    plt.figure()
    plt.plot([0, 1], [1, 0])
    target = tmp_path / "tight.png"
    plt.savefig(target, bbox_inches="tight", pad_inches=0)
    assert target.stat().st_size > 0


def test_decode_png_rejects_decompression_bomb():

    from matplotvite import _plotting as p

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body)))

    header = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
    data = (p._PNG_SIGNATURE + header
            + chunk(b"IDAT", zlib.compress(b"\x00" * 10**7)) + chunk(b"IEND", b""))
    with pytest.raises(ValueError):
        p._decode_png(data)
