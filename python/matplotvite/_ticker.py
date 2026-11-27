"""Locators, formatters, transforms and font properties."""
import datetime as _datetime
import math as _math
from typing import Any, ClassVar

import numpy as np

from . import units
from ._helpers import (
    _add_months,
    _date_from_num,
    _date_ticks,
    _date_to_num,
    _datetime_to_num,
    _noop_method,
    _norm_color,
    _state_setter,
)
from ._plot_helpers import _as_f64
from ._pyplot import subplots


class _NoopLocator:
    """Locator that deliberately produces no ticks."""

    def __init__(self, *args: Any, **kwargs: Any) -> None: pass
    def __call__(self) -> Any: return []
    def tick_values(self, vmin: Any, vmax: Any) -> Any:
        return np.array([vmin, vmax], dtype=float)
    set_params = _noop_method("set_params", 'self, **kwargs')
    set_axis = _noop_method("set_axis", 'self, axis')


NullLocator = _NoopLocator


class _Locator:
    """Base for the major locators that really place ticks.

    Matplotlib derives tick positions from the locator attached to the axis,
    so accepting `set_major_locator` without using it silently ignores the
    caller's tick choice. `_NoopLocator` stays for the locators that only
    need to be accepted, such as `LogLocator` and `NullLocator`.
    """

    axis: Any = None

    set_axis = _state_setter(
        "axis", 'axis', 'axis')
    set_params = _noop_method("set_params", 'self, **kwargs')
    def __call__(self, vmin: Any = None, vmax: Any = None) -> Any:
        if vmin is None or vmax is None:
            raise ValueError("a locator needs the axis limits")
        return self.tick_values(vmin, vmax)  # type: ignore[attr-defined]


def _locator_span(vmin: Any, vmax: Any) -> tuple[Any, Any]:
    return (vmin, vmax) if vmin <= vmax else (vmax, vmin)


def _locator_value(value: Any) -> float:
    """Drop the binary noise so 3 * 0.1 reads as 0.3."""
    return float(f"{value:.12g}")


class _MultipleLocator(_Locator):
    """Ticks at multiples of `base`, as `ticker.MultipleLocator`."""

    def __init__(self, base: Any = 1.0, offset: Any = 0.0) -> None:
        self.base, self.offset = float(base), float(offset)

    def set_params(self, base: Any = None, offset: Any = None) -> None:
        if base is not None:
            self.base = float(base)
        if offset is not None:
            self.offset = float(offset)

    def tick_values(self, vmin: Any, vmax: Any) -> Any:
        lo, hi = _locator_span(vmin, vmax)
        base = self.base if self.base > 0 else 1.0
        first = _math.ceil((lo - self.offset) / base - 1e-9) * base + self.offset
        last = _math.floor((hi - self.offset) / base + 1e-9) * base + self.offset
        count = int(round((last - first) / base)) + 1 if last >= first else 0
        return np.asarray([_locator_value(first + i * base) for i in range(count)])


class _IndexLocator(_Locator):
    """Ticks at `offset + base * i`, as `ticker.IndexLocator`."""

    def __init__(self, base: Any, offset: Any = 0.0) -> None:
        self.base, self.offset = float(base), float(offset)

    def tick_values(self, vmin: Any, vmax: Any) -> Any:
        lo, hi = _locator_span(vmin, vmax)
        if self.base <= 0:
            return np.asarray([], dtype=float)
        count = int(_math.floor((hi - self.offset) / self.base + 1e-9)) + 1
        values = [self.offset + i * self.base for i in range(max(count, 0))]
        return np.asarray([v for v in values if v >= lo - 1e-9], dtype=float)


class _LogLocator(_Locator):
    """Ticks at powers of `base`, optionally at `subs` multiples of each power."""

    def __init__(self, base: Any = 10.0, subs: Any = (1.0,),
                 numticks: Any = None, **kwargs: Any) -> None:
        self.base = float(base)
        self.subs = subs
        self.numticks = numticks

    def set_params(self, base: Any = None, subs: Any = None,
                   numticks: Any = None) -> None:
        if base is not None:
            self.base = float(base)
        if subs is not None:
            self.subs = subs
        if numticks is not None:
            self.numticks = numticks

    def tick_values(self, vmin: Any, vmax: Any) -> Any:
        lo, hi = sorted((float(vmin), float(vmax)))
        if hi <= 0.0:
            return np.array([], dtype=float)
        lo = lo if lo > 0.0 else hi * 1e-12
        base = self.base if self.base > 1.0 else 10.0
        first = int(_math.floor(_math.log(lo, base))) - 1
        last = int(_math.ceil(_math.log(hi, base))) + 1
        subs: tuple[float, ...]
        if self.subs is None:
            subs = (1.0,)
        elif np.isscalar(self.subs):
            subs = (float(self.subs),)
        else:
            subs = tuple(float(s) for s in np.ravel(self.subs))
        values = [sub * base ** exp
                  for exp in range(first, last + 1) for sub in subs]
        values = [v for v in values if lo * (1 - 1e-9) <= v <= hi * (1 + 1e-9)]
        return np.asarray(sorted(values), dtype=float)


class _MaxNLocator(_Locator):
    """Roughly `nbins` "nice" ticks, as `ticker.MaxNLocator`."""

    _STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)

    def __init__(self, nbins: Any = None, steps: Any = None,
                 **kwargs: Any) -> None:
        self.nbins = nbins
        self.steps = tuple(float(v) for v in steps) if steps else self._STEPS

    def set_params(self, nbins: Any = None, steps: Any = None,
                   **kwargs: Any) -> None:
        if nbins is not None:
            self.nbins = nbins
        if steps is not None:
            self.steps = tuple(float(v) for v in steps)

    def tick_values(self, vmin: Any, vmax: Any) -> Any:
        lo, hi = _locator_span(vmin, vmax)
        if not hi > lo:
            return np.asarray([_locator_value(lo)])
        nbins = 9 if self.nbins in (None, "auto") else max(1, int(self.nbins))
        raw = (hi - lo) / nbins
        magnitude = 10.0 ** _math.floor(_math.log10(raw))
        step = magnitude * self.steps[-1]
        for candidate in sorted(self.steps):
            if magnitude * candidate >= raw - 1e-12:
                step = magnitude * candidate
                break
        first = _math.ceil(lo / step - 1e-9) * step
        count = int(_math.floor((hi - first) / step + 1e-9)) + 1
        return np.asarray([_locator_value(first + i * step) for i in range(max(count, 0))])


class _FixedLocator(_Locator):
    """Ticks exactly at `locs`."""

    def __init__(self, locs: Any, **kwargs: Any) -> None:
        self.locs = _as_f64(locs)

    def tick_values(self, vmin: Any, vmax: Any) -> Any: return self.locs
    def __call__(self, vmin: Any = None, vmax: Any = None) -> Any: return self.locs


class _LinearLocator(_Locator):
    """`numticks` ticks evenly spaced over the axis limits."""

    def __init__(self, numticks: Any = None, **kwargs: Any) -> None:
        self.numticks = numticks

    def set_params(self, numticks: Any = None, **kwargs: Any) -> None:
        if numticks is not None:
            self.numticks = numticks

    def tick_values(self, vmin: Any, vmax: Any) -> Any:
        num = 6 if self.numticks is None else max(2, int(self.numticks))
        return np.linspace(vmin, vmax, num)


class _NoopFormatter:
    def __init__(self, *args: Any, **kwargs: Any) -> None: self.args = args
    def __call__(self, value: Any, pos: Any = None) -> str: return str(value)
    set_axis = _noop_method("set_axis", 'self, axis')
    set_locs = _noop_method("set_locs", 'self, locs')
    create_dummy_axis = _noop_method("create_dummy_axis", 'self, **kwargs')


class _PathEffects:
    class Normal:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass
    class SimplePatchShadow:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass
    class SimpleLineShadow:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass
    class Stroke:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass
    class PathPatchEffect:
        def __init__(self, *args: Any, **kwargs: Any) -> None: pass

    @staticmethod
    def withStroke(*args: Any, **kwargs: Any) -> "_PathEffects.Stroke":
        return _PathEffects.Stroke()

    @staticmethod
    def withTickedStroke(*args: Any, **kwargs: Any) -> "_PathEffects.Stroke":
        return _PathEffects.Stroke()

    @staticmethod
    def withSimplePatchShadow(*args: Any,
                              **kwargs: Any) -> "_PathEffects.SimplePatchShadow":
        return _PathEffects.SimplePatchShadow()


class _TransformedBbox:
    """Bbox carried through a transform; matplotvite transforms are identities."""

    def __init__(self, bbox: Any, transform: Any = None) -> None:
        self._bbox, self._transform = bbox, transform

    @property
    def x0(self) -> float: return float(self._bbox.x0)
    @property
    def y0(self) -> float: return float(self._bbox.y0)
    @property
    def x1(self) -> float: return float(self._bbox.x1)
    @property
    def y1(self) -> float: return float(self._bbox.y1)
    @property
    def width(self) -> float: return self.x1 - self.x0
    @property
    def height(self) -> float: return self.y1 - self.y0

    def get_points(self) -> Any:
        return np.asarray([[self.x0, self.y0], [self.x1, self.y1]], dtype=float)

    def transformed(self, transform: Any) -> "_TransformedBbox":
        return _TransformedBbox(self._bbox, transform)


class FontProperties:
    """`FontProperties` accepts Matplotlib's font settings; size is the one the
    renderer uses, the rest are kept for code that reads them back."""

    def __init__(self, family: Any = None, style: Any = None, variant: Any = None,
                 weight: Any = None, stretch: Any = None, size: Any = None,
                 fname: Any = None, math_fontfamily: Any = None,
                 **kwargs: Any) -> None:
        self._family, self._style, self._variant = family, style, variant
        self._weight, self._stretch, self._size = weight, stretch, size
        self._fname, self._math_fontfamily = fname, math_fontfamily

    def copy(self) -> "FontProperties":
        return FontProperties(self._family, self._style, self._variant, self._weight,
                              self._stretch, self._size, self._fname,
                              self._math_fontfamily)

    get_family = lambda self: self._family
    get_style = lambda self: self._style
    get_variant = lambda self: self._variant
    get_weight = lambda self: self._weight
    get_stretch = lambda self: self._stretch
    get_size = lambda self: self._size
    get_size_in_points = lambda self: self._size
    get_file = lambda self: self._fname
    set_family = lambda self, value: setattr(self, "_family", value)
    set_style = lambda self, value: setattr(self, "_style", value)
    set_variant = lambda self, value: setattr(self, "_variant", value)
    set_weight = lambda self, value: setattr(self, "_weight", value)
    set_stretch = lambda self, value: setattr(self, "_stretch", value)
    set_size = lambda self, value: setattr(self, "_size", value)
    set_file = lambda self, value: setattr(self, "_fname", value)


class _StyleValue(str):
    def __new__(cls, value: Any, name: Any) -> "_StyleValue":
        obj = super().__new__(cls, value)
        obj.name = name  # type: ignore[attr-defined]
        return obj


class _StyleMeta(type):
    def __iter__(cls) -> Any: return iter(cls._members())  # type: ignore[attr-defined]
    def __len__(cls) -> int: return len(cls._members())  # type: ignore[attr-defined]


class CapStyle(str, metaclass=_StyleMeta):
    butt = _StyleValue("butt", "butt")
    round = _StyleValue("round", "round")
    projecting = _StyleValue("projecting", "projecting")

    @classmethod
    def _members(cls) -> tuple[Any, ...]: return (cls.butt, cls.round, cls.projecting)

    @staticmethod
    def demo() -> None:
        _, ax = subplots(figsize=(5, 2.5))
        for row, style in enumerate(("butt", "round", "projecting")):
            line, = ax.plot([0.2, 0.8], [row, row], linewidth=12)
            line.set_solid_capstyle(style)
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(-0.5, 2.5)
        ax.set_axis_off()


class JoinStyle(str, metaclass=_StyleMeta):
    miter = _StyleValue("miter", "miter")
    round = _StyleValue("round", "round")
    bevel = _StyleValue("bevel", "bevel")

    @classmethod
    def _members(cls) -> tuple[Any, ...]: return (cls.miter, cls.round, cls.bevel)

    @staticmethod
    def demo() -> None:
        _, ax = subplots(figsize=(5, 2.5))
        for row, style in enumerate(("miter", "round", "bevel")):
            line, = ax.plot([0.1, 0.4, 0.7], [row, row + 0.8, row], linewidth=12)
            line.set_solid_joinstyle(style)
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(-0.5, 2.8)
        ax.set_axis_off()


def same_color(*colors: Any) -> bool:
    """True when every colour argument normalises to the same value."""
    return len({_norm_color(c) for c in colors}) == 1


def _num_to_date(value: Any, tz: Any = None) -> _datetime.datetime:
    return _date_from_num(float(value))


class _DateFormatter:
    """Format a date number with `strftime`; `fmt` is Matplotlib's format."""

    def __init__(self, fmt: Any = "%Y-%m-%d", tz: Any = None) -> None:
        self.fmt, self.tz = str(fmt), tz

    def __call__(self, x: Any, pos: Any = None) -> str:
        return _date_from_num(float(x)).strftime(self.fmt)

    set_tzinfo = _state_setter(
        "tz", 'tz', 'tz')
    def get_offset(self) -> str: return ""


class _AutoDateFormatter:
    """Date formatter that chooses a readable format from the tick value."""

    def __init__(self, locator: Any = None, tz: Any = None, formats: Any = None,
                 offset_formats: Any = None, zero_formats: Any = None,
                 show_offset: Any = True) -> None:
        self.locator = locator
        self.tz = tz
        self.formats = formats
        self.offset_formats = offset_formats
        self.zero_formats = zero_formats
        self.show_offset = show_offset

    def __call__(self, x: Any, pos: Any = None) -> str:
        dt = _date_from_num(float(x))
        if dt.hour or dt.minute or dt.second or dt.microsecond:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d")

    def format_ticks(self, values: Any) -> list[str]:
        return [self(value, i) for i, value in enumerate(values)]

    def get_offset(self) -> str: return ""
    set_axis = _state_setter(
        "axis", 'axis', 'axis')


class _ConciseDateFormatter:
    """Date formatter that picks a compact unit based on the tick's resolution."""

    _DEFAULT_FORMATS: ClassVar[tuple[str, ...]] = (
        "%Y", "%b", "%d", "%H:%M", "%H:%M", "%S.%f")

    def __init__(self, locator: Any = None, tz: Any = None, formats: Any = None,
                 offset_formats: Any = None, zero_formats: Any = None,
                 show_offset: Any = True) -> None:
        self.locator = locator
        self.tz = tz
        self.formats = list(formats or self._DEFAULT_FORMATS)
        self.zero_formats = list(zero_formats or ["", *self.formats[:-1]])
        self.offset_formats = list(offset_formats or [""] * 6)
        self.show_offset = show_offset

    def __call__(self, x: Any, pos: Any = None) -> str:
        dt = _date_from_num(float(x))
        if dt.microsecond or dt.second:
            level = 5
        elif dt.minute:
            level = 4
        elif dt.hour:
            level = 3
        elif dt.day != 1:
            level = 2
        elif dt.month != 1:
            level = 1
        else:
            level = 0
        fmt = self.formats[min(level, len(self.formats) - 1)]
        return dt.strftime(fmt)

    def format_ticks(self, values: Any) -> list[str]:
        return [self(value, i) for i, value in enumerate(values)]

    def format_data(self, value: Any) -> str: return self(value)
    def format_data_short(self, value: Any) -> str: return self(value)
    def get_offset(self) -> str: return ""
    set_axis = _state_setter(
        "axis", 'axis', 'axis')
    set_tzinfo = _state_setter(
        "tz", 'tz', 'tz')


class _ConciseDateConverter:
    """Units converter that installs the concise date locator and formatter."""

    def __init__(self, formats: Any = None, zero_formats: Any = None,
                 offset_formats: Any = None) -> None:
        self.formats = formats
        self.zero_formats = zero_formats
        self.offset_formats = offset_formats

    def axisinfo(self, unit: Any, axis: Any) -> Any:
        locator = _AutoDateLocator()
        formatter = _ConciseDateFormatter(
            locator, formats=self.formats, zero_formats=self.zero_formats,
            offset_formats=self.offset_formats)
        return units.AxisInfo(majloc=locator, majfmt=formatter)

    default_units = _noop_method("default_units", 'self, x, axis')

    def convert(self, value: Any, unit: Any, axis: Any) -> Any:
        return _date_to_num(value)


class _AutoDateLocator:
    """Calendar-aware locator on the date-number axis."""

    def __init__(self, *args: Any, **kwargs: Any) -> None: pass

    def tick_values(self, vmin: Any, vmax: Any) -> Any:
        ticks, _ = _date_ticks(float(vmin), float(vmax))
        return np.asarray(ticks, dtype=float)

    def __call__(self, vmin: Any, vmax: Any) -> Any:
        return self.tick_values(vmin, vmax)
    set_axis = _state_setter(
        "axis", 'axis', 'axis')


class _rrulewrapper:
    """Store recurrence-rule arguments; date ticks use the calendar fallback."""

    def __init__(self, freq: Any, **kwargs: Any) -> None:
        self.freq = freq
        self.kwargs = kwargs


class _RRuleLocator(_AutoDateLocator):
    """Recurrence-rule locator, backed by the calendar locator."""

    def __init__(self, rule: Any = None, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.rule = rule


def _drange(dstart: Any, dend: Any, delta: Any) -> list[Any]:
    """Inclusive sequence of dates from `dstart` to `dend` by `delta`."""
    out = []
    current = dstart
    while current <= dend:
        out.append(current)
        current = current + delta
    return out


class _CalendarLocator:
    """Ticks aligned to a calendar unit: years, months, days or smaller.

    `interval` steps by that many units; `bymonth`/`bymonthday` accept
    Matplotlib's arguments but only the first value is honoured.
    """

    unit = "day"

    def __init__(self, interval: Any = 1, bymonth: Any = None,
                 bymonthday: Any = None, **kwargs: Any) -> None:
        if isinstance(interval, (list, tuple, range, np.ndarray)):
            self.byhour = list(interval)
            interval = 1
        self.interval = max(int(interval), 1)
        self.bymonth = (list(bymonth) if isinstance(bymonth, (list, tuple))
                        else ([bymonth] if bymonth is not None else None))
        self.bymonthday = (list(bymonthday) if isinstance(bymonthday, (list, tuple))
                           else ([bymonthday] if bymonthday is not None else None))

    set_axis = _state_setter(
        "axis", 'axis', 'axis')

    def tick_values(self, vmin: Any, vmax: Any) -> Any:
        vmin, vmax = float(vmin), float(vmax)
        if not (np.isfinite(vmin) and np.isfinite(vmax)) or vmax <= vmin:
            return np.asarray([vmin], dtype=float)
        if self.unit in ("year", "month"):
            ticks = self._calendar_ticks(vmin, vmax)
        else:
            step = {"day": 1.0, "hour": 1.0 / 24.0, "minute": 1.0 / 1440.0,
                    "second": 1.0 / 86400.0}[self.unit] * self.interval
            first = _math.ceil(vmin / step - 1e-9) * step
            ticks = [first + i * step for i in range(50) if first + i * step <= vmax + 1e-9]
        return np.asarray(ticks, dtype=float)

    def __call__(self, vmin: Any, vmax: Any) -> Any:
        return self.tick_values(vmin, vmax)

    def _calendar_ticks(self, vmin: Any, vmax: Any) -> list[Any]:
        start = _date_from_num(vmin)
        if self.unit == "year":
            month = (self.bymonth or [1])[0]
            day = (self.bymonthday or [1])[0]
            year = start.year if (start.month, start.day) <= (month, day) else start.year + 1
            step, ticks = self.interval, []
            for i in range(60):
                year += step if i else 0
                try:
                    current = _datetime.datetime(year, month, day)
                except ValueError:
                    break
                value = _datetime_to_num(current)
                if value > vmax + 1e-9:
                    break
                ticks.append(value)
            return ticks
        month = (self.bymonth or [start.month])[0]
        current = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if self.bymonth is None and current.month != month:
            current = current.replace(month=month)
        ticks = []
        for _ in range(60):
            value = _datetime_to_num(current)
            if value > vmax + 1e-9:
                break
            if value >= vmin - 1e-9:
                ticks.append(value)
            current = _add_months(current, self.interval)
        return ticks


class _YearLocator(_CalendarLocator):
    unit = "year"


class _MonthLocator(_CalendarLocator):
    unit = "month"


class _DayLocator(_CalendarLocator):
    unit = "day"


class _HourLocator(_CalendarLocator):
    unit = "hour"


class _MinuteLocator(_CalendarLocator):
    unit = "minute"


class _SecondLocator(_CalendarLocator):
    unit = "second"


class _PercentFormatter:
    """Format a value as a percentage of `xmax`."""

    def __init__(self, xmax: Any = 100, decimals: Any = None,
                 symbol: Any = "%", is_latex: Any = False) -> None:
        self.xmax = float(xmax)
        self.decimals = decimals
        self.symbol = symbol
        self.is_latex = is_latex

    def __call__(self, x: Any, pos: Any = None) -> str:
        if self.xmax == 0:
            return ""
        value = float(x) / self.xmax * 100.0
        decimals = self.decimals
        if decimals is None:
            decimals = 0 if abs(value - round(value)) < 1e-9 else 1
        return f"{value:.{decimals}f}{self.symbol}"

    set_axis = _noop_method("set_axis", 'self, axis')


class _EngFormatter:
    """Format values with SI prefixes, as Matplotlib's EngFormatter."""

    _PREFIXES = (("", 0), ("k", 3), ("M", 6), ("G", 9), ("T", 12),
                 ("P", 15), ("E", 18), ("Z", 21), ("Y", 24))

    def __init__(self, unit: Any = "", places: Any = None, sep: Any = " ",
                 format: Any = None, **kwargs: Any) -> None:
        self.unit = str(unit)
        self.places = places
        self.sep = str(sep)
        self.format = format

    def __call__(self, x: Any, pos: Any = None) -> str:
        value = float(x)
        if value == 0 or not np.isfinite(value):
            return f"0{self.sep}{self.unit}" if self.unit else "0"
        sign = "-" if value < 0 else ""
        magnitude = abs(value)
        exponent = int(np.floor(np.log10(magnitude) / 3.0) * 3)
        exponent = max(-24, min(24, exponent))
        prefix = ""
        for text, power in self._PREFIXES:
            if exponent == power:
                prefix = text
                break
        else:
            if exponent < 0:
                prefix = ("m", "\u03bc", "n", "p", "f", "a", "z", "y")[
                    min(7, (-exponent // 3) - 1)]
        scaled = magnitude / (10.0 ** exponent)
        places = self.places
        if places is None:
            places = 0 if abs(scaled - round(scaled)) < 1e-9 else 1
        number = f"{scaled:.{places}f}"
        return f"{sign}{number}{self.sep}{prefix}{self.unit}"

    set_axis = _noop_method("set_axis", 'self, axis')


class _FixedFormatter:
    """Formatter that returns `seq[pos]`, as Matplotlib's FixedFormatter."""

    def __init__(self, seq: Any) -> None: self.seq = list(seq)

    def __call__(self, x: Any, pos: Any = None) -> Any:
        if pos is None or not 0 <= int(pos) < len(self.seq):
            raise IndexError("FixedFormatter position out of range")
        return self.seq[int(pos)]

    set_axis = _noop_method("set_axis", 'self, axis')


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
