"""Host/parasite axes used by the axisartist gallery."""

from typing import Any

from .axislines import Axes


class HostAxes(Axes):
    pass


class ParasiteAxes(Axes):
    pass


def host_subplot(*args: Any, **kwargs: Any) -> Any:
    from matplotvite import gcf

    return gcf().add_subplot(*args, **kwargs)
