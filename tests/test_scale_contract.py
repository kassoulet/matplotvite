"""Scale shims and renderer transforms must be one implementation."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from matplotvite import _core
from matplotvite import scale as mscales


def test_symlog_transform_matches_rust_and_matplotlib():
    values = np.array([-1000.0, -1.0, -0.25, 0.0, 0.25, 1.0, 1000.0])
    transform = mscales.SymmetricalLogScale(
        None, base=10.0, linthresh=1.0, linscale=1.0
    ).get_transform()
    expected = _core.symlog(values, 1.0, 10.0, 1.0)

    assert np.allclose(transform.transform(values), expected)
    assert np.allclose(expected[2:5], values[2:5] * (1.0 / 0.9))
    assert expected[-1] == pytest.approx(1.0 / 0.9 + 3.0)
    assert np.allclose(transform.inverted().transform(expected), values)


def test_logit_transform_matches_rust_and_clips_endpoints():
    values = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    transform = mscales.LogitScale(None).get_transform()
    expected = _core.logit(values)

    assert np.allclose(transform.transform(values), expected)
    assert expected[0] == -1000.0
    assert expected[-1] == 1000.0
    assert np.allclose(transform.inverted().transform(expected), values)


def test_asinh_transform_matches_rust_and_honours_the_width():
    values = np.array([-100.0, -2.0, 0.0, 2.0, 100.0])
    transform = mscales.AsinhScale(None, linear_width=2.0).get_transform()
    expected = _core.asinh(values, 2.0)

    assert np.allclose(transform.transform(values), expected)
    assert expected[3] == pytest.approx(2.0 * np.arcsinh(1.0))
    assert np.allclose(transform.inverted().transform(expected), values)


@settings(max_examples=40, deadline=None)
@given(
    value=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
    linthresh=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False),
    base=st.floats(min_value=1.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    linscale=st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_symlog_round_trips_arbitrary_finite_values(value, linthresh, base, linscale):
    original = np.array([value])
    restored = _core.symlog_inverse(
        _core.symlog(original, linthresh, base, linscale), linthresh, base, linscale
    )

    assert np.allclose(restored, original, rtol=1e-7, atol=1e-9)


@settings(max_examples=40, deadline=None)
@given(value=st.floats(min_value=1e-6, max_value=1 - 1e-6, allow_nan=False, allow_infinity=False))
def test_logit_round_trips_arbitrary_probabilities(value):
    original = np.array([value])
    restored = _core.logit_inverse(_core.logit(original))

    assert np.allclose(restored, original, rtol=1e-8, atol=1e-10)


@settings(max_examples=40, deadline=None)
@given(
    value=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
    width=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_asinh_round_trips_arbitrary_values(value, width):
    original = np.array([value])
    restored = _core.asinh_inverse(_core.asinh(original, width), width)

    assert np.allclose(restored, original, rtol=1e-8, atol=1e-9)


@settings(max_examples=40, deadline=None)
@given(
    lo=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    span=st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False),
    target=st.integers(min_value=3, max_value=8),
)
def test_auto_ticks_are_sorted_and_inside_the_requested_range(lo, span, target):
    hi = lo + span
    ticks = _core.auto_ticks(lo, hi, False, 10.0, target)

    assert ticks == sorted(ticks)
    assert len(ticks) <= target + 2
    assert all(lo - span * 1e-9 <= tick <= hi + span * 1e-9 for tick in ticks)
