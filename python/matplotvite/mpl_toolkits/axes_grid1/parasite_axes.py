"""Minimal `axes_grid1.parasite_axes` compatibility layer."""

from typing import Any

from matplotvite import Axes


class HostAxes(Axes):
    """Host axes for parasite plots; matplotvite's `twin` covers the examples."""

    pass


class ParasiteAxes(Axes):
    pass


def host_subplot(*args: Any, **kwargs: Any) -> Any:
    """Create a normal axes on the current figure."""
    from matplotvite import gcf

    return gcf().add_subplot(*args, **kwargs)


__all__ = ("HostAxes", "ParasiteAxes", "host_subplot")
