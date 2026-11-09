"""Keep full gallery regeneration out of the default test run.

The `gallery` tests render every harvested snippet and need checkouts that the
repository does not vendor, so they run only when asked for — `pytest -m
gallery` or `pytest --galleries`. A plain `pytest` skips them with a hint
instead of spending minutes or failing on the missing sources.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption("--galleries", action="store_true", default=False,
                     help="run the full gallery regeneration tests")


def pytest_collection_modifyitems(config, items):
    requested = "gallery" in (config.getoption("markexpr") or "") \
        or config.getoption("galleries")
    if requested:
        return
    skip = pytest.mark.skip(reason="gallery regeneration runs on demand: "
                                  "`pytest -m gallery`")
    for item in items:
        if "gallery" in item.keywords:
            item.add_marker(skip)
