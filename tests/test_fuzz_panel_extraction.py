"""Smoke the Python-enabled fuzz harness for the PyO3 extraction boundary."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "fuzz" / "python" / "fuzz_panel_extraction.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("fuzz_panel_extraction", HARNESS)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_seed_payload_reaches_the_renderer():
    harness = _load_harness()
    payload = harness.seed_payload()
    assert payload["size"] == (640, 480)
    assert payload["grid"] == (1, 1)
    assert payload["panels"][0]["series"]
    assert harness._core.render(
        payload["size"], payload["grid"], payload["panels"], payload["options"]
    )[:8] == b"\x89PNG\r\n\x1a\n"


def test_mutations_survive_the_extraction_boundary():
    harness = _load_harness()
    # Malformed records must raise ordinary Python exceptions; a panic would
    # escape as PanicException and fail this test.
    for seed in range(120):
        data = bytes((seed * 37 + index * 11) % 256 for index in range(64))
        harness.check(data)


def test_mutation_is_deterministic():
    harness = _load_harness()
    seed = harness.seed_payload()
    data = bytes(range(64))
    first = harness.mutate(seed, data)
    second = harness.mutate(seed, data)
    assert first.keys() == second.keys()
    assert first["size"] == second["size"]
    # Panel records hold NumPy arrays, so compare their structural repr.
    assert repr(first["panels"]) == repr(second["panels"])
    assert repr(first["options"]) == repr(second["options"])


def test_harness_requires_atheris_only_in_that_mode():
    harness = _load_harness()
    if importlib.util.find_spec("atheris") is None:
        with pytest.raises(ModuleNotFoundError):
            harness._atheris_main()
