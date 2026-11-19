"""Tests for ``pd.options.plotting.backend = "matplotvite"``."""

import matplotvite as plt
import numpy as np
import pytest


@pytest.fixture
def pandas_backend():
    pd = pytest.importorskip("pandas")
    previous = pd.options.plotting.backend
    pd.options.plotting.backend = "matplotvite"
    plt.close("all")
    try:
        yield pd
    finally:
        pd.options.plotting.backend = previous
        plt.close("all")


@pytest.fixture
def frame(pandas_backend):
    pd = pandas_backend
    return pd.DataFrame(
        {"a": [1.0, 2.0, 3.0], "b": [3.0, 1.0, 2.0]},
        index=pd.Index(["x", "y", "z"], name="cat"),
    )


def test_dataframe_line_uses_backend_defaults(frame):
    axes = frame.plot()
    assert axes is plt.gca()
    assert [line["label"] for line in axes.lines] == ["a", "b"]
    assert axes.xlabel == "cat"
    assert axes.ylabel == ""
    assert axes.show_legend is True
    assert [tick.get_text() for tick in axes.get_xticklabels()] == ["x", "y", "z"]


def test_series_line_has_no_legend_by_default(pandas_backend):
    series = pandas_backend.Series([2.0, 4.0, 3.0], name="temp",
                                   index=pandas_backend.Index(["x", "y", "z"], name="cat"))
    axes = series.plot()
    assert [line["label"] for line in axes.lines] == ["temp"]
    assert axes.xlabel == "cat"
    assert axes.show_legend is False


def test_every_supported_kind_returns_a_matplotvite_axes(frame):
    for kind in ("line", "bar", "barh", "hist", "box", "area"):
        axes = frame.plot(kind=kind)
        assert isinstance(axes, plt.Axes), kind
        plt.close("all")
    assert isinstance(frame.plot.scatter(x="a", y="b"), plt.Axes)
    plt.close("all")
    assert isinstance(frame.plot.pie(y="a"), plt.Axes)


def test_bar_and_barh_group_series_and_place_category_labels(frame):
    axes = frame.plot.bar()
    assert len(axes.bars) == 2
    assert [tick.get_text() for tick in axes.get_xticklabels()] == ["x", "y", "z"]
    assert axes.bars[0]["vertical"] is True

    plt.close("all")
    axes = frame.plot.barh()
    assert len(axes.bars) == 2
    assert [tick.get_text() for tick in axes.get_yticklabels()] == ["x", "y", "z"]
    assert axes.bars[0]["vertical"] is False
    # Pandas puts the index label on the categorical axis for horizontal bars.
    assert axes.xlabel == ""
    assert axes.ylabel == "cat"


def test_stacked_bar_uses_one_bottom_per_series(frame):
    axes = frame.plot.bar(stacked=True)
    assert len(axes.bars) == 2
    assert np.allclose(axes.bars[1]["bottom"], frame["a"].to_numpy())


def test_hist_defaults_to_frequency_and_supports_density(frame):
    axes = frame.plot.hist(bins=4)
    assert axes.ylabel == "Frequency"
    assert axes.show_legend is True
    plt.close("all")

    axes = frame.plot.hist(bins=4, density=True, alpha=0.4)
    assert axes.ylabel == "Frequency"
    assert all(bar["alpha"] == 0.4 for bar in axes.bars)


def test_box_plot_labels_each_series(frame):
    axes = frame.plot.box()
    assert len(axes.lines) >= 2
    assert [tick.get_text() for tick in axes.get_xticklabels()] == ["a", "b"]
    assert axes.show_legend is False


def test_area_stacks_bands_and_keeps_series_labels(frame):
    axes = frame.plot.area()
    assert len(axes.bands) == 2
    assert [band["label"] for band in axes.bands] == ["a", "b"]
    assert axes.xlabel == "cat"


def test_scatter_requires_and_labels_both_columns(frame):
    axes = frame.plot.scatter(x="a", y="b")
    assert axes.xlabel == "a"
    assert axes.ylabel == "b"
    assert axes.show_legend is False
    with pytest.raises(ValueError, match="scatter requires both"):
        frame.plot(kind="scatter", x="a")


def test_pie_uses_the_index_as_labels(frame):
    axes = frame.plot.pie(y="a")
    assert axes.xlabel == ""
    assert axes.ylabel == ""
    assert axes.show_legend is True


def test_datetime_index_flows_through_the_date_axis(pandas_backend):
    pd = pandas_backend
    frame = pd.DataFrame(
        {"value": [1.0, 2.0, 3.0]},
        index=pd.date_range("2023-01-01", periods=3, freq="D", name="date"),
    )
    axes = frame.plot()
    assert axes._x_date is True
    assert axes.xlabel == "date"
    assert axes._panel()["ticks"]["xticklabels"][0].startswith("2023-")


def test_categorical_index_uses_its_labels(pandas_backend):
    pd = pandas_backend
    frame = pd.DataFrame(
        {"value": [3.0, 1.0, 2.0]},
        index=pd.CategoricalIndex(["Mon", "Tue", "Wed"], name="day"),
    )
    axes = frame.plot.bar()
    assert [tick.get_text() for tick in axes.get_xticklabels()] == ["Mon", "Tue", "Wed"]


def test_multiindex_axes_are_flattened_for_display(pandas_backend):
    pd = pandas_backend
    columns = pd.MultiIndex.from_tuples([("A", "x"), ("A", "y")])
    index = pd.MultiIndex.from_tuples([("a", 1), ("b", 2), ("c", 3)],
                                      names=["letter", "n"])
    frame = pd.DataFrame([[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]],
                         index=index, columns=columns)
    axes = frame.plot()
    assert [line["label"] for line in axes.lines] == ["A / x", "A / y"]
    assert axes.xlabel == "letter / n"
    assert [tick.get_text() for tick in axes.get_xticklabels()] == ["a / 1", "b / 2", "c / 3"]


def test_style_layout_and_kwargs_pass_through(frame):
    axes = frame.plot(
        linewidth=3, marker="o", color=["red", "blue"], title="T",
        grid=True, rot=30, logy=True, xlim=(0, 4), ylim=(0.5, 5),
        legend=False,
    )
    assert [line["linewidth"] for line in axes.lines] == [3, 3]
    assert [line["marker"] for line in axes.lines] == ["o", "o"]
    assert [line["color"] for line in axes.lines] == ["#ff0000", "#0000ff"]
    assert axes.title == "T"
    assert axes.show_grid is True
    assert axes.tick_params_x["rotation"] == 30
    assert axes.get_yscale() == "log"
    assert axes.get_xlim() == (0.0, 4.0)
    # A log axis cannot include zero; the renderer clamps the bound to 1.
    assert axes.get_ylim() == (1.0, 5.0)
    assert axes.show_legend is False


def test_existing_axes_are_reused(frame):
    figure, axes = plt.subplots()
    assert frame.plot(ax=axes) is axes
    assert figure is axes.figure


def test_unknown_kind_and_subplots_fail_clearly(frame):
    with pytest.raises(ValueError, match="kind='heatmap' is not supported"):
        frame.plot(kind="heatmap")
    with pytest.raises(NotImplementedError, match="subplots=True"):
        frame.plot(subplots=True)
