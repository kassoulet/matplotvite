"""Minimal unit-conversion registry compatibility layer."""


class AxisInfo:
    """Axis label, locator and formatter hints supplied by a converter."""

    def __init__(self, majloc: object = None, minloc: object = None,
                 majfmt: object = None, minfmt: object = None,
                 label: object = None, default_limits: object = None) -> None:
        self.majloc = majloc
        self.minloc = minloc
        self.majfmt = majfmt
        self.minfmt = minfmt
        self.label = label
        self.default_limits = default_limits


class ConversionInterface:
    """Base class for converters registered in `registry`."""

    @staticmethod
    def axisinfo(unit: object, axis: object) -> None:
        return None

    @staticmethod
    def default_units(x: object, axis: object) -> None:
        return None

    @staticmethod
    def convert(obj: object, unit: object, axis: object) -> object:
        return obj


class Registry(dict[type, object]):
    """Mapping from value types to their conversion interface."""

    def get_converter(self, x: object) -> object:
        for cls in type(x).__mro__:
            converter = self.get(cls)
            if converter is not None:
                return converter
        return None


registry = Registry()


__all__ = ("AxisInfo", "ConversionInterface", "Registry", "registry")
