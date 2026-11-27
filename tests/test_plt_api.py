"""pyplot state, module namespaces and remaining public API."""

import io
import re

import matplotvite as plt
import numpy as np
import pytest


def test_file_like_name_selects_format(tmp_path):

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
    assert 'fill="#FFFFFF"' not in p.read_text(encoding="utf-8")


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


def test_axes_limits_and_bounds_track_data():
    plt.figure()
    ax = plt.gca()
    ax.plot([2, 4, 6], [10, 30, 20])
    assert ax.get_xlim() == pytest.approx((1.8, 6.2)) and ax.get_ylim() == pytest.approx((9.0, 31.0))
    assert ax.get_xbound() == ax.get_xlim() and ax.get_ybound() == ax.get_ylim()
    ax.set_xlim(0, 10)
    assert ax.get_xlim() == (0.0, 10.0)


def test_hidden_and_removed_axes_are_not_drawn(tmp_path):
    fig, axs = plt.subplots(1, 2, figsize=(8, 3))
    axs[0].plot([0, 1], [0, 1])
    axs[0].set_title("keep")
    axs[1].plot([0, 1], [1, 0])
    axs[1].set_title("gone")
    axs[1].set_visible(False)
    p = tmp_path / "hidden.svg"
    fig.savefig(p)
    s = p.read_text(encoding="utf-8")
    assert "keep" in s and "gone" not in s

    axs[1].set_visible(True)
    axs[1].remove()
    fig.savefig(p)
    assert "gone" not in p.read_text(encoding="utf-8")

    fig = plt.figure()
    plt.plot([1, 2])
    plt.gca().remove()
    fig.savefig(tmp_path / "none.png")
    assert (tmp_path / "none.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


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


def test_axes_state_accessors():
    fig, ax = plt.subplots()
    assert ax.get_autoscale_on() and ax.get_autoscalex_on() and ax.get_autoscaley_on()
    ax.set_autoscale_on(False)
    ax.set_autoscalex_on(False)
    ax.set_autoscaley_on(False)
    assert not (ax.get_autoscale_on() or ax.get_autoscalex_on() or ax.get_autoscaley_on())
    assert ax.get_navigate() is True and ax.get_navigate_mode() is None
    ax.set_navigate(False)
    assert ax.get_navigate() is False
    ax.set_gid("group")
    ax.set_url("https://example.test/plot")
    ax.set_rasterized(True)
    ax.set_animated(True)
    ax.set_anchor("SW")
    ax.set_axisbelow("line")
    ax.set_picker(5)
    ax.set_clip_box("box")
    ax.set_agg_filter("filter")
    assert ax.get_gid() == "group"
    assert ax.get_url() == "https://example.test/plot"
    assert ax.get_rasterized() is True and ax.get_animated() is True
    assert ax.get_anchor() == "SW" and ax.get_axisbelow() == "line"
    assert ax.get_picker() == 5 and ax.get_clip_box() == "box"
    assert ax.get_agg_filter() == "filter"
    assert ax.get_path_effects() == []
    assert not ax.is_transform_set()
    ax.set_transform(ax.transData)
    assert ax.is_transform_set() and ax.get_transform() is ax.transData
    assert ax.apply_aspect() is None
    line = ax.plot([0, 1], [0, 1])[0]
    assert len(ax.get_lines()) == 1 and ax.get_images() == []
    ax.xaxis_date()
    ax.yaxis_date()
    assert ax._x_date and ax._y_date
    assert ax.format_xdata(1.5) == "1.5"
    assert ax.format_ydata(2.0) == "2"
    assert ax.add_callback(lambda: None) == 1
    ax.remove_callback(None)
    ax.draw_artist(line)
    ax.set_figure(fig)
    assert ax.get_figure() is fig
    assert ax.findobj()[0] is ax
    props = ax.properties()
    assert props["gid"] == "group" and props["lines"]
    ax.update_from(ax)
    assert ax.pchanged() is None


def test_axes_autoscale_uses_stored_margins():
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0], [0.0, 1.0])
    ax.margins(0.5)
    ax.autoscale(True)
    assert ax.get_xlim() == pytest.approx((-0.5, 1.5))
    assert ax.get_ylim() == pytest.approx((-0.5, 1.5))

    ax.set_xlim(0.0, 10.0)
    ax.autoscale(False)
    ax.plot([100.0, 200.0], [100.0, 200.0])
    assert ax.get_xlim() == (0.0, 10.0)
    assert ax.get_autoscalex_on() is False

    ax.autoscale(True)
    assert ax.get_xlim() == pytest.approx((-100.0, 300.0))
    assert ax.get_autoscalex_on() is True

    ax.autoscale(tight=True)
    assert ax.get_xlim() == pytest.approx((0.0, 200.0))
    assert ax.get_xmargin() == 0.0

    ax.margins(0.2)
    ax.autoscale_view(tight=False)
    assert ax.get_xlim() == pytest.approx((-40.0, 240.0))
    with pytest.raises(ValueError):
        ax.autoscale(axis="z")


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
    s = p.read_text(encoding="utf-8").upper()
    assert "#FF0000" in s and "#0000FF" in s
    assert s.count("<POLYLINE") >= 2
    assert s.count("<RECT") >= 3  # background plus two bands
    # Reference lines and bands never move the data limits.
    assert ax.get_xlim() == (0.0, 10.0)
    assert ax.get_ylim() == (-2.0, 2.0)


def test_excessive_binning_is_rejected():
    plt.figure()
    with pytest.raises(ValueError, match="bins=5000 exceeds maximum"):
        plt.hist([1, 2], bins=5000)
    with pytest.raises(ValueError, match="too many bins"):
        plt.hist2d([1, 2], [1, 2], bins=[3000, 3000])
    with pytest.raises(ValueError, match="too many hexagons"):
        plt.hexbin([1, 2], [1, 2], gridsize=(2000, 2000))


def test_hlines_vlines(tmp_path):
    plt.figure()
    ax = plt.gca()
    ax.hlines([1, 2], 0, 3, colors=["red", "blue"], linestyles=["--", ":"])
    ax.vlines([0.5, 1.5], 0, 3, colors="green")
    p = tmp_path / "hl.svg"
    plt.savefig(p)
    s = p.read_text(encoding="utf-8").upper()
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
    s = p.read_text(encoding="utf-8")
    assert "#FF0000" in s.upper()
    assert re.search(r">\s*100\s*<", s), "decade tick label missing"
    plt.figure()
    ax = plt.gca()
    ax.loglog(x, 1.0 / x, base=10)
    assert ax.get_xscale() == "log" and ax.get_yscale() == "log"
    q = tmp_path / "log2.svg"
    plt.savefig(q)
    assert re.search(r">\s*0\.1\s*<", q.read_text(encoding="utf-8"))
    plt.figure()
    plt.semilogx(x, x)
    plt.xscale("log")
    assert plt.gca().get_xscale() == "log"
    ax.set_xscale("symlog")
    assert ax.get_xscale() == "symlog"
    ax.set_xscale("log")
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


def test_log_base_two(tmp_path):
    x = np.array([1.0, 2.0, 4.0, 8.0])
    plt.figure()
    ax = plt.gca()
    ax.set_xscale("log", base=2)
    ax.plot(x, [2, 4, 8, 16])
    p = tmp_path / "logbase.svg"
    plt.savefig(p)
    assert re.search(r">\s*(2|4|8)\s*<", p.read_text(encoding="utf-8"))


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
    assert "#663399" in p.read_text(encoding="utf-8").upper()


def test_non_finite_data_gets_finite_limits(tmp_path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0.0, np.nan, 1.0], [0.0, np.inf, 1.0])
    assert all(np.isfinite(v) for v in (*ax.get_xlim(), *ax.get_ylim()))
    p = tmp_path / "nan.png"
    fig.savefig(p)
    assert p.stat().st_size > 0


def test_data_mapping_resolves_string_arguments():
    fig, ax = plt.subplots()
    ax.plot("x", "y", data={"x": [0, 1], "y": [1, 2]})
    assert ax.lines
    ax.bar("a", "b", data={"a": 0, "b": 1})
    ax.step("x", "y", data={"x": [0, 1], "y": [1, 2]})
    ax.imshow("image", data={"image": [[0.0, 1.0], [1.0, 0.0]]})


def test_ignored_shim_warns_once():
    label = plt.figure().gca().xaxis.label
    with pytest.warns(RuntimeWarning, match="accepted but ignored"):
        label.set_wrap(True)


def test_geographic_projections_render_their_frames(tmp_path):
    for projection in ("aitoff", "hammer", "lambert", "mollweide"):
        fig, ax = plt.subplots(subplot_kw={"projection": projection})
        ax.grid(True)
        ax.set_title(projection.title())
        out = tmp_path / f"{projection}.png"
        fig.savefig(out)
        assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_signal_processing_axes_methods(tmp_path):
    plt.rcdefaults()
    rng = np.random.default_rng(0)
    x = rng.normal(size=512)
    y = rng.normal(size=512)
    fig, axs = plt.subplots(3, 3, figsize=(10, 8))
    coh, freqs = axs[0, 0].cohere(x, y, NFFT=64, Fs=100)
    assert coh.shape == freqs.shape and 0.0 <= coh.min() <= coh.max() <= 1.0
    psd, freqs = axs[0, 1].psd(x, NFFT=64, Fs=100)
    assert psd.shape == freqs.shape
    csd, freqs = axs[0, 2].csd(x, y, NFFT=64, Fs=100)
    assert csd.shape == freqs.shape
    magnitude, freqs, _ = axs[1, 0].magnitude_spectrum(x, Fs=100)
    assert magnitude.shape == freqs.shape
    phase, freqs, _ = axs[1, 1].phase_spectrum(x, Fs=100)
    assert phase.shape == freqs.shape
    angle, freqs, _ = axs[1, 2].angle_spectrum(x, Fs=100)
    assert angle.shape == freqs.shape
    lags, corr, _, _ = axs[2, 0].xcorr(x, y, maxlags=20, normed=True)
    assert lags.shape == corr.shape == (41,)
    axs[2, 1].acorr(x, maxlags=20, usevlines=False)
    ecdf_x, ecdf_y, _ = axs[2, 2].ecdf(x)
    assert ecdf_x.shape == ecdf_y.shape and ecdf_y[-1] == 1.0
    out = tmp_path / "signal_methods.png"
    fig.savefig(out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_from_levels_and_colors_builds_a_discrete_norm():
    cmap, norm = plt.colors.from_levels_and_colors(
        [0, 1, 2, 3], ["red", "green", "blue"])
    assert cmap.colors == ["#ff0000", "#008000", "#0000ff"]
    extended = plt.colors.ListedColormap(
        ["red", "green"], over="#595959", under="#bfbfbf")
    assert extended._over == "#595959" and extended._under == "#bfbfbf"
    assert norm([0.5, 1.5, 2.5]).tolist() == [0, 1, 2]
    plt.rcdefaults()
    plt.figure()
    plt.pcolormesh(np.array([[0.5, 1.5], [2.5, 0.5]]), cmap=cmap, norm=norm)
    assert plt.gca().images[0].get_clim()[0] == 0.0


def test_axes_arrow_adds_a_fancy_arrow(tmp_path):
    """`Axes.arrow` returns the data-space patch it added."""
    fig, ax = plt.subplots()
    arrow = ax.arrow(0.1, 0.2, 0.5, 0.3, width=0.02,
                     head_width=0.08, length_includes_head=True)
    assert arrow in ax.patches
    assert arrow.get_xy().shape[0] == 7
    fig.savefig(tmp_path / "arrow.png")


def test_asinh_scale_renders_with_linear_width(tmp_path):
    """Asinh axes accept Matplotlib's linear_width option."""
    fig, ax = plt.subplots()
    ax.plot([-1, 0, 1], [-100, 0, 100])
    ax.set_yscale("asinh", linear_width=0.5)
    assert ax.get_yscale() == "asinh"
    fig.savefig(tmp_path / "asinh.png")
