"""Scale shims and renderer transforms must be one implementation."""

import numpy as np
import pytest
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
