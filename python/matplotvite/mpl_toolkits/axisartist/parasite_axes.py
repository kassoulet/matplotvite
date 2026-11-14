"""Host/parasite axes used by the axisartist gallery."""

from .axislines import Axes


class HostAxes(Axes):
    pass


class ParasiteAxes(Axes):
    pass


def host_subplot(*args, **kwargs):
    from matplotvite import gcf

    return gcf().add_subplot(*args, **kwargs)
