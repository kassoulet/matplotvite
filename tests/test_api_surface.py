"""Checks for the declared public API and deprecation helper."""

import ast
from pathlib import Path

import matplotvite as plt
import pytest


def _stub_public_names():
    stub = Path(plt.__file__).with_name("__init__.pyi")
    tree = ast.parse(stub.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {name for name in names if not name.startswith("_")}


def test_all_exports_are_unique_and_resolve():
    assert len(plt.__all__) == len(set(plt.__all__))
    missing = sorted(name for name in plt.__all__ if not hasattr(plt, name))
    assert not missing, f"names in __all__ are not importable: {missing}"


def test_public_stub_names_are_exported():
    missing = sorted(_stub_public_names() - set(plt.__all__))
    assert not missing, f"public stub names missing from __all__: {missing}"


def test_all_exports_have_stubs():
    exported = {name for name in plt.__all__ if not name.startswith("_")}
    missing = sorted(exported - _stub_public_names())
    assert not missing, f"public exports missing from the stub: {missing}"


def test_exported_callables_have_stubs():
    callables = {
        name for name in plt.__all__
        if callable(getattr(plt, name, None))
    }
    missing = sorted(callables - _stub_public_names())
    assert not missing, f"exported callables missing from the stub: {missing}"


def test_lazy_delegated_callables_are_discoverable():
    """`__getattr__` names must also show up in `dir()`, as tools inspect it."""
    from matplotvite import _plotting

    excluded = {"Any", "ClassVar", "contextmanager"}
    missing = sorted(
        name for name in dir(_plotting)
        if not name.startswith("_")
        and name not in excluded
        and callable(getattr(_plotting, name, None))
        and name not in dir(plt)
    )
    assert not missing, f"delegated callables hidden from dir(): {missing}"
    for name in ("Line2D", "Text", "CirclePolygon", "figaspect", "tricontour"):
        assert name in dir(plt)


def test_deprecated_helper_emits_future_warning():
    with pytest.warns(FutureWarning) as caught:
        plt._deprecated("old_api", since="0.7", alternative="new_api", removal="0.8")
    assert str(caught[0].message) == (
        "old_api is deprecated since 0.7; use new_api instead. "
        "It will be removed in 0.8."
    )
