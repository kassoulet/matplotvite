"""Malformed PNG input must raise a clean error, never crash or exhaust memory."""

import struct
import zlib
from contextlib import suppress

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from matplotvite import _plotting as plotting

SIGNATURE = plotting._PNG_SIGNATURE
CLEAN_ERRORS = (ValueError, NotImplementedError)


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body)))


def _png(width, height, depth, color, raw, extra=b""):
    header = struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, 0)
    return (SIGNATURE + _chunk(b"IHDR", header) + extra
            + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b""))


@settings(max_examples=200, deadline=None)
@given(st.binary(max_size=512))
def test_random_bytes_after_the_signature(tail):
    with suppress(*CLEAN_ERRORS):
        plotting._decode_png(SIGNATURE + tail)


@settings(max_examples=200, deadline=None)
@given(
    width=st.integers(0, 2**32 - 1),
    height=st.integers(0, 2**32 - 1),
    depth=st.sampled_from([0, 1, 2, 4, 8, 16, 32]),
    color=st.integers(0, 7),
    raw=st.binary(max_size=256),
)
def test_arbitrary_headers_are_rejected_or_decoded(width, height, depth, color, raw):
    with suppress(*CLEAN_ERRORS):
        plotting._decode_png(_png(width, height, depth, color, raw))


@settings(max_examples=100, deadline=None)
@given(st.integers(0, 4), st.binary(min_size=3, max_size=3))
def test_valid_filters_round_trip_to_the_right_shape(filter_type, pixel):
    raw = bytes([filter_type]) + pixel
    image = plotting._decode_png(_png(1, 1, 8, 2, raw))
    assert image.shape == (1, 1, 3)


def test_truncated_ihdr_is_a_value_error():
    data = SIGNATURE + _chunk(b"IHDR", b"\x00\x00")
    with pytest.raises(ValueError):
        plotting._decode_png(data)
