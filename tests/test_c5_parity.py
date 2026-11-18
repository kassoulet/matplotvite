"""Matplotlib signature and validation parity checks for C5."""

import inspect

import matplotvite as plt
import pytest


def test_plot_rejects_mismatched_lengths():
    fig, ax = plt.subplots()
    with pytest.raises(ValueError, match="x and y must have same first dimension"):
        ax.plot([0, 1, 2], [0, 1])
    plt.close(fig)


def test_plot_rejects_unknown_linestyle():
    fig, ax = plt.subplots()
    with pytest.raises(ValueError, match="not a valid value for ls"):
        ax.plot([0, 1], linestyle="bogus")
    plt.close(fig)


def test_hist_invalid_histtype_is_a_value_error():
    fig, ax = plt.subplots()
    with pytest.raises(ValueError, match="not a valid value for histtype"):
        ax.hist([1, 2, 3], histtype="bogus")
    plt.close(fig)


def test_legend_rejects_unknown_location():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], label="line")
    with pytest.raises(ValueError, match="not a valid value for loc"):
        ax.legend(loc="bogus")
    with pytest.raises(ValueError, match="integer 0-10"):
        ax.legend(loc=11)
    plt.close(fig)


def test_legend_accepts_integer_codes():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], label="line")
    ax.legend(loc=2)
    assert ax.legend_loc == "upper left"
    plt.close(fig)


def test_subplots_share_arguments_are_keyword_only():
    with pytest.raises(TypeError):
        plt.subplots(1, 1, True)
    fig = plt.figure()
    with pytest.raises(TypeError):
        fig.subplots(1, 1, True)
    plt.close(fig)


def test_subplots_grid_and_share_validation_messages():
    with pytest.raises(
            ValueError, match="Number of rows must be a positive integer, not 0"):
        plt.subplots(0, 1)
    with pytest.raises(
            ValueError, match=r"Number of rows must be a positive integer, not 1\.5"):
        plt.subplots(1.5, 1)
    with pytest.raises(
            ValueError, match="Number of rows must be a positive integer, not '2'"):
        plt.subplots("2", 1)
    with pytest.raises(ValueError, match="not a valid value for sharex"):
        plt.subplots(sharex="bogus")
    plt.close("all")


def test_subplots_forwards_subplot_and_gridspec_kw():
    fig, axs = plt.subplots(
        1, 2,
        subplot_kw={"projection": "polar"},
        gridspec_kw={"width_ratios": [1, 2]},
    )
    assert fig._gridspec.width_ratios == [1.0, 2.0]
    assert all(getattr(ax, "_polar", False) for ax in axs.ravel())
    plt.close(fig)


def test_savefig_uses_fname_and_accepts_deprecated_filepath(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    target = tmp_path / "new.svg"
    fig.savefig(target)
    assert target.exists()
    with pytest.warns(FutureWarning, match="filepath is deprecated"):
        fig.savefig(filepath=tmp_path / "old.svg")
    plt.close(fig)


def test_savefig_accepts_metadata_and_pil_kwargs():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    with pytest.warns(RuntimeWarning, match="metadata"):
        data = fig.savefig(None, format="png", metadata={"Title": "test"})
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    with pytest.warns(RuntimeWarning, match="pil_kwargs"):
        data = fig.savefig(None, format="png", pil_kwargs={"optimize": True})
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    plt.close(fig)


def test_savefig_transparent_defaults_to_rcparam():
    plt.rcdefaults()
    try:
        assert inspect.signature(
            plt.Figure.savefig).parameters["transparent"].default is None
        plt.rcParams["savefig.transparent"] = True
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        svg = fig.savefig(None, format="svg").decode()
        assert 'fill="#FFFFFF"' not in svg
        plt.close(fig)
    finally:
        plt.rcdefaults()
