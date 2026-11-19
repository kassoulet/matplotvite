#!/usr/bin/env python3
"""Fuzz the PyO3 panel extraction path with a live Python runtime.

`fuzz/fuzz_targets/panel_render.rs` drives the public Rust builder, but the
Python facade hands the renderer a tree of dicts that PyO3 extracts into
`Panel`, `Series`, `Scatter`, array views and the option records. Those
`FromPyObject` implementations only exist with an initialized interpreter, so
they are fuzzed here instead: a real figure is captured at the `_core.render`
boundary, mutated, and fed back through the extension.

Run with atheris for coverage-guided fuzzing::

    python fuzz/python/fuzz_panel_extraction.py --atheris

or without it for a deterministic mutation run (the mode CI's tests use)::

    python fuzz/python/fuzz_panel_extraction.py --iterations 2000
"""

from __future__ import annotations

import argparse
import copy
import random
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotvite
from matplotvite import _core

# Values that extract cleanly as numbers but are awkward for layout and drawing.
_NUMBERS = (
    0.0,
    -0.0,
    1.0,
    -1.0,
    1e-308,
    1e308,
    float("nan"),
    float("inf"),
    float("-inf"),
    9.223372036854776e18,
)


def seed_payload() -> dict[str, Any]:
    """Capture the arguments of one real `savefig` at the PyO3 boundary."""
    captured: dict[str, Any] = {}
    original = matplotvite._render

    def spy(size, grid, panels, options):
        captured["size"] = size
        captured["grid"] = grid
        captured["panels"] = panels
        captured["options"] = options
        return b""

    matplotvite._render = spy
    try:
        figure, axes = matplotvite.subplots()
        axes.plot([0.0, 1.0, 2.0], [1.0, 4.0, 2.0], label="line")
        axes.scatter([0.25, 1.5], [2.0, 3.0], c=[0.0, 1.0])
        axes.set_title("seed")
        figure.savefig(format="png")
    finally:
        matplotvite._render = original
    # Deep-copy so a mutated payload never aliases a live artist record.
    return copy.deepcopy(captured)


def _paths(value: Any, prefix: tuple[Any, ...] = ()) -> Iterator[tuple[Any, ...]]:
    """Yield every container path in a nested dict/list tree."""
    yield prefix
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _paths(item, (*prefix, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _paths(item, (*prefix, index))


def _replace(root: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    """Return `root` with the value at `path` replaced."""
    if not path:
        return replacement
    cursor = root
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement
    return root


def _numeric_payload(rng: random.Random, depth: int) -> Any:
    """A value an array extraction may accept, or one it must reject."""
    choice = rng.randrange(6)
    if choice == 0:
        return [_NUMBERS[rng.randrange(len(_NUMBERS))] for _ in range(rng.randrange(4))]
    if choice == 1:
        return [[_NUMBERS[rng.randrange(len(_NUMBERS))] for _ in range(2)]
                for _ in range(rng.randrange(4))]
    if choice == 2:
        return rng.choice([None, True, False, "", "nan", [], {}])
    if choice == 3:
        return rng.randrange(-(1 << 63), 1 << 63)
    return _NUMBERS[rng.randrange(len(_NUMBERS))]


def mutate(payload: dict[str, Any], data: bytes) -> dict[str, Any]:
    """Apply `data` to the captured payload, touching one nested value per byte."""
    rng = random.Random(int.from_bytes(data[:16].ljust(16, b"\0"), "little"))
    result = copy.deepcopy(payload)
    # Keep the four top-level arguments containers so the call always reaches
    # `_core.render`; mutations only target their contents.
    structural = {(), ("size",), ("grid",), ("panels",), ("options",)}
    # One to four mutations keeps most of the payload valid so extraction and
    # rendering both run instead of failing on the first bad key. Paths are
    # recollected after each mutation because a replacement can remove subtrees.
    for _ in range(1 + (data[0] % 4 if data else 0)):
        paths = [path for path in _paths(result) if path not in structural]
        if not paths:
            break
        path = paths[rng.randrange(len(paths))]
        result = _replace(result, path, _numeric_payload(rng, len(path)))
    result["size"] = (16 + data[1] % 224, 16 + data[2] % 224)
    result["grid"] = (1, 1)
    panels = result["panels"]
    result["panels"] = ([panel for panel in panels if isinstance(panel, dict)]
                        if isinstance(panels, list) else [])
    return result


def check(data: bytes) -> None:
    """Feed mutated records through the real `_core.render` extraction."""
    payload = mutate(seed_payload(), data)
    try:
        _core.render(payload["size"], payload["grid"], payload["panels"],
                     payload["options"])
    except (TypeError, ValueError, OverflowError, KeyError, IndexError,
            ZeroDivisionError, MemoryError, RuntimeError):
        # Malformed input is the point: PyO3 must turn it into a Python
        # exception, not abort the process or corrupt memory.
        return
    except BaseException:
        # PanicException and friends are findings, so surface them.
        raise


def _atheris_main() -> None:
    import atheris

    with atheris.instrument_imports():
        atheris.Setup(sys.argv, check)
    atheris.Fuzz()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--atheris", action="store_true",
                        help="run coverage-guided fuzzing through atheris")
    parser.add_argument("--iterations", type=int, default=1000,
                        help="mutation iterations when atheris is not used")
    parser.add_argument("--seed", type=int, default=0, help="base RNG seed")
    args = parser.parse_args(argv)

    if args.atheris:
        _atheris_main()
        return 0

    rng = random.Random(args.seed)
    for index in range(args.iterations):
        payload = bytes(rng.randrange(256) for _ in range(64))
        check(payload)
        if (index + 1) % 250 == 0:
            print(f"  {index + 1} mutations", file=sys.stderr)
    print(f"Fuzzed the PyO3 panel extraction path {args.iterations} times.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
