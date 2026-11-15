"""Minimal unit-conversion registry compatibility layer."""


class AxisInfo:
    """Axis label, locator and formatter hints supplied by a converter."""

    def __init__(self, majloc=None, minloc=None, majfmt=None, minfmt=None,
                 label=None, default_limits=None):
        self.majloc = majloc
        self.minloc = minloc
        self.majfmt = majfmt
        self.minfmt = minfmt
        self.label = label
        self.default_limits = default_limits


class ConversionInterface:
    """Base class for converters registered in `registry`."""

    @staticmethod
    def axisinfo(unit, axis):
        return None

    @staticmethod
    def default_units(x, axis):
        return None

    @staticmethod
    def convert(obj, unit, axis):
        return obj


class Registry(dict):
    """Mapping from value types to their conversion interface."""

    def get_converter(self, x):
        for cls in type(x).__mro__:
            converter = self.get(cls)
            if converter is not None:
                return converter
        return None


registry = Registry()


__all__ = ("AxisInfo", "ConversionInterface", "Registry", "registry")
