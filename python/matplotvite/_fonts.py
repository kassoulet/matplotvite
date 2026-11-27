"""Font, style-flag and epoch compatibility shims."""
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any

import numpy as np

from ._artists import Line2D
from ._cm import _Mlab, _rgba_tuple
from ._config import _RC_DEFAULTS, _Namespace, rcParams
from ._helpers import _CYCLE, _CycleList, _date_to_num, get_cmap
from ._images import GridSpec, SubplotSpec
from ._misc import GridSpecFromSubplotSpec
from ._plot_helpers import _boxplot_stats
from ._png import _flatten, _get_sample_data
from ._projections import (
    DAILY,
    FR,
    HOURLY,
    MINUTELY,
    MO,
    MONTHLY,
    SA,
    SECONDLY,
    SU,
    TH,
    TU,
    WE,
    WEEKLY,
    YEARLY,
    _epoch,
)
from ._pyplot import gcf
from ._ticker import (
    FontProperties,
    _AutoDateFormatter,
    _AutoDateLocator,
    _ConciseDateConverter,
    _ConciseDateFormatter,
    _DateFormatter,
    _DayLocator,
    _drange,
    _HourLocator,
    _MinuteLocator,
    _MonthLocator,
    _num_to_date,
    _PathEffects,
    _RRuleLocator,
    _rrulewrapper,
    _SecondLocator,
    _YearLocator,
)


def _set_epoch(epoch: Any) -> None: _epoch["value"] = str(epoch)
def _get_epoch() -> Any: return _epoch["value"]

dates = _Namespace(
    date2num=_date_to_num, num2date=_num_to_date, DateFormatter=_DateFormatter,
    AutoDateLocator=_AutoDateLocator, AutoDateFormatter=_AutoDateFormatter,
    YearLocator=_YearLocator, MonthLocator=_MonthLocator, DayLocator=_DayLocator,
    HourLocator=_HourLocator, MinuteLocator=_MinuteLocator,
    SecondLocator=_SecondLocator, WeekdayLocator=_DayLocator,
    MicrosecondLocator=_SecondLocator, RRuleLocator=_RRuleLocator,
    rrulewrapper=_rrulewrapper, drange=_drange,
    ConciseDateFormatter=_ConciseDateFormatter,
    ConciseDateConverter=_ConciseDateConverter,
    MO=MO, TU=TU, WE=WE, TH=TH, FR=FR, SA=SA, SU=SU,
    YEARLY=YEARLY, MONTHLY=MONTHLY, WEEKLY=WEEKLY, DAILY=DAILY,
    HOURLY=HOURLY, MINUTELY=MINUTELY, SECONDLY=SECONDLY,
    _reset_epoch_test_example=lambda: None,
    set_epoch=_set_epoch, get_epoch=_get_epoch,
)
mdates = dates

cbook = _Namespace(get_sample_data=_get_sample_data, flatten=_flatten,
                   boxplot_stats=_boxplot_stats,
                   silent_list=lambda *items: list(items[0]) if items else [],
                   to_rgba=lambda color, alpha=None: _rgba_tuple(color) if alpha is None
                   else (*_rgba_tuple(color)[:3], float(alpha)))
mlab = _Mlab()


def _findfont(prop: Any = None, **kwargs: Any) -> str:
    """Return a placeholder bundled-font path.

    The renderer uses its own bundled font bytes, so resolving a real path is
    unnecessary for drawing; callers such as the logo example only inspect the
    returned name.
    """
    return "DejaVuSans.ttf"


findfont = _findfont


class _FontFlag:
    """One named FreeType style or face flag."""

    def __init__(self, name: Any) -> None:
        self.name = name

    def __repr__(self) -> str: return f"<FontFlag {self.name}>"


class _FontFlagSet:
    """The flags present on a font face, testable with `flag in font.flags`."""

    def __init__(self, names: Any) -> None:
        self._names = set(names)

    def __contains__(self, flag: Any) -> bool:
        return getattr(flag, "name", flag) in self._names

    def __iter__(self) -> Iterator[str]: return iter(self._names)


class _FontFlagsMeta(type):
    def __iter__(cls: Any) -> Iterator[Any]: return iter(cls._members())
    def __len__(cls: Any) -> int: return len(cls._members())


class StyleFlags(metaclass=_FontFlagsMeta):
    """`ft2font.StyleFlags`: the font's style bits."""

    ITALIC = _FontFlag("ITALIC")
    BOLD = _FontFlag("BOLD")

    @classmethod
    def _members(cls: Any) -> tuple[Any, ...]: return (cls.ITALIC, cls.BOLD)


class FaceFlags(metaclass=_FontFlagsMeta):
    """`ft2font.FaceFlags`: the capabilities of a font face."""

    SCALABLE = _FontFlag("SCALABLE")
    FIXED_SIZES = _FontFlag("FIXED_SIZES")
    FIXED_WIDTH = _FontFlag("FIXED_WIDTH")
    SFNT = _FontFlag("SFNT")
    HORIZONTAL = _FontFlag("HORIZONTAL")
    VERTICAL = _FontFlag("VERTICAL")
    KERNING = _FontFlag("KERNING")
    FAST_GLYPHS = _FontFlag("FAST_GLYPHS")
    MULTIPLE_MASTERS = _FontFlag("MULTIPLE_MASTERS")
    GLYPH_NAMES = _FontFlag("GLYPH_NAMES")
    EXTERNAL_STREAM = _FontFlag("EXTERNAL_STREAM")
    HINTER = _FontFlag("HINTER")

    @classmethod
    def _members(cls: Any) -> tuple[Any, ...]:
        return tuple(getattr(cls, name) for name in (
            "SCALABLE", "FIXED_SIZES", "FIXED_WIDTH", "SFNT", "HORIZONTAL",
            "VERTICAL", "KERNING", "FAST_GLYPHS", "MULTIPLE_MASTERS",
            "GLYPH_NAMES", "EXTERNAL_STREAM", "HINTER"))


class Kerning:
    """Kerning modes accepted by `FT2Font.get_kerning`."""

    DEFAULT = 0
    UNFITTED = 1
    UNSCALED = 2


class _FT2Glyph:
    """Glyph metrics returned by the font-inspection shim."""

    def __init__(self, glyph_index: Any) -> None:
        self.glyph_index = int(glyph_index)
        self.bbox = (0, 0, 600, 700)
        self.width = self.horiAdvance = 600
        self.height = self.horiBearingY = 700
        self.horiBearingX = 0


class FT2Font:
    """Small font-inspection stand-in backed by the bundled DejaVu metrics."""

    def __init__(self, filename: Any) -> None:
        self.fname = str(filename)
        name = self.fname.lower()
        self.num_faces = 1
        self.num_named_instances = 0
        self.num_glyphs = 0x2400
        self.num_fixed_sizes = 0
        self.family_name = "DejaVu Sans"
        self.style_name = ("Bold" if "bold" in name else
                           "Oblique" if "oblique" in name or "italic" in name
                           else "Book")
        self.postscript_name = "DejaVuSans"
        self.scalable = True
        self.bbox = (-1021, -463, 1793, 1233)
        self.units_per_EM = 2048
        self.ascender = 1901
        self.descender = -483
        self.height = 2384
        self.max_advance_width = 3838
        self.max_advance_height = 2384
        self.underline_position = -175
        self.underline_thickness = 90
        styles = []
        if "oblique" in name or "italic" in name:
            styles.append("ITALIC")
        if "bold" in name:
            styles.append("BOLD")
        self.style_flags = _FontFlagSet(styles)
        self.face_flags = _FontFlagSet((
            "SCALABLE", "SFNT", "HORIZONTAL", "KERNING", "GLYPH_NAMES"))
        self._charmap = 0
        self._size = (12.0, 72.0)

    def set_charmap(self, charmap: Any) -> None:
        """Select a character map; the bundled font only has one."""
        self._charmap = int(charmap)

    def set_size(self, size: Any, dpi: Any = 72) -> None:
        self._size = (float(size), float(dpi))

    def get_charmap(self) -> dict[int, int]:
        return {code: code for code in range(0x20, 0x100)}

    def get_name_index(self, name: Any) -> int:
        """Index of a named font table entry; the stand-in has none."""
        return 0

    def get_glyph_name(self, glyph_index: Any) -> str:
        index = int(glyph_index)
        if 0x20 <= index <= 0x7E:
            return chr(index)
        return f"uni{index:04X}"

    def load_char(self, charcode: Any) -> _FT2Glyph:
        return _FT2Glyph(charcode)

    def get_kerning(self, left: Any, right: Any,
                    mode: Any = Kerning.DEFAULT) -> int:
        """The bundled metrics shim has no kerning table."""
        return 0


font_manager = _Namespace(FontProperties=FontProperties, findfont=_findfont,
                          fontManager=_Namespace(addfont=lambda path: None))
ft2font = _Namespace(FT2Font=FT2Font, Kerning=Kerning,
                     StyleFlags=StyleFlags, FaceFlags=FaceFlags)
gridspec = _Namespace(GridSpec=GridSpec, SubplotSpec=SubplotSpec,
                      GridSpecFromSubplotSpec=GridSpecFromSubplotSpec)
lines = _Namespace(Line2D=Line2D)
patheffects = _PathEffects()
path_effects = patheffects
class _ColorSequences(dict[str, list[str]]):
    """`matplotlib.color_sequences`: named colour lists, looked up by name."""

    def __missing__(self, key: str) -> list[str]:
        raise KeyError(key)


def _colormap_sequence(name: str) -> list[str]:
    cmap = get_cmap(name)
    rows = np.asarray(cmap.colors)[::-1] if cmap.name.endswith("_r") else np.asarray(cmap.colors)
    return [f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"
            for r, g, b in rows]


_PETROFF = ["#3f90da", "#ffa90e", "#bd1f01", "#94a4a2", "#832db6",
            "#a96b59", "#e76300", "#b9ac70", "#717581", "#92dadd"]
color_sequences = _ColorSequences(
    tableau=list(_CYCLE), petroff=_PETROFF[:6], petroff6=_PETROFF[:6],
    petroff8=_PETROFF[:8], petroff10=list(_PETROFF))
for _sequence in ("tab10", "tab20", "tab20b", "tab20c", "Pastel1", "Pastel2",
                  "Paired", "Accent", "Dark2", "Set1", "Set2", "Set3", "okabe_ito"):
    with suppress(ValueError):
        color_sequences[_sequence] = _colormap_sequence(_sequence)


def rc(group: Any = None, **kwargs: Any) -> None:
    """Record rc settings. `rc("lines", linewidth=2)` maps to `lines.linewidth`."""
    if group is None or isinstance(group, dict):
        rcParams.update(group or kwargs)
        return None
    for key, value in kwargs.items():
        rcParams[f"{group}.{key}"] = value
    return None


@contextmanager
def rc_context(rc: Any = None, fname: Any = None) -> Iterator[Any]:
    """Apply rc overrides for the duration of the block, then restore them."""
    saved = dict(rcParams)
    if rc is not None:
        rcParams.update(rc)
    try:
        yield rcParams
    finally:
        rcParams.clear()
        rcParams.update(saved)


def rcdefaults() -> None:
    """Restore `rcParams` to the built-in defaults."""
    rcParams.clear()
    rcParams.update(_RC_DEFAULTS)


_STYLE_PRESETS = {
    # Matplotlib's test-suite style; it is the current default look.
    "mpl20": {},
    "dark_background": {
        "figure.facecolor": "#000000", "axes.facecolor": "#000000",
        "axes.edgecolor": "#ffffff", "text.color": "#dddddd",
        "axes.labelcolor": "#dddddd", "xtick.color": "#dddddd",
        "ytick.color": "#dddddd", "grid.color": "#555555",
        "axes.prop_cycle": ["#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3",
                            "#fdb462", "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd"],
    },
    "ggplot": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#e5e5e5",
        "axes.edgecolor": "#ffffff", "text.color": "#555555",
        "axes.labelcolor": "#555555", "xtick.color": "#555555",
        "ytick.color": "#555555", "grid.color": "#ffffff",
        "axes.prop_cycle": ["#e24a33", "#348abd", "#988ed5", "#777777", "#fbc15e",
                            "#8eba42", "#ffb5b8"],
    },
    "seaborn-v0_8": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#eaeaf2",
        "axes.edgecolor": "#ffffff", "text.color": "#262626",
        "axes.labelcolor": "#262626", "xtick.color": "#262626",
        "ytick.color": "#262626", "grid.color": "#ffffff",
        "axes.prop_cycle": ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3",
                            "#937860", "#da8bc3", "#8c8c8c", "#ccb974", "#64b5cd"],
    },
    "seaborn": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#eaeaf2",
        "axes.edgecolor": "#ffffff", "text.color": "#262626",
        "axes.labelcolor": "#262626", "xtick.color": "#262626",
        "ytick.color": "#262626", "grid.color": "#ffffff",
    },
    "bmh": {
        "figure.facecolor": "#eeeeee", "axes.facecolor": "#eeeeee",
        "axes.edgecolor": "#bcbcbc", "text.color": "#262626",
        "axes.labelcolor": "#262626", "xtick.color": "#262626",
        "ytick.color": "#262626", "grid.color": "#ffffff",
    },
    "fivethirtyeight": {
        "figure.facecolor": "#f0f0f0", "axes.facecolor": "#f0f0f0",
        "axes.edgecolor": "#f0f0f0", "text.color": "#262626",
        "axes.labelcolor": "#262626", "xtick.color": "#262626",
        "ytick.color": "#262626", "grid.color": "#cbcbcb",
        "axes.prop_cycle": ["#008fd5", "#fc4f30", "#e5ae38", "#6d904f", "#8b8b8b"],
    },
    "grayscale": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#ffffff",
        "axes.edgecolor": "#000000", "text.color": "#000000",
        "axes.labelcolor": "#000000", "xtick.color": "#000000",
        "ytick.color": "#000000", "grid.color": "#b0b0b0",
        "axes.prop_cycle": ["#000000", "#555555", "#aaaaaa", "#dddddd"],
    },
    "Solarize_Light2": {
        "figure.facecolor": "#fdf6e3", "axes.facecolor": "#eee8d5",
        "axes.edgecolor": "#93a1a1", "text.color": "#073642",
        "axes.labelcolor": "#073642", "xtick.color": "#073642",
        "ytick.color": "#073642", "grid.color": "#93a1a1",
        "axes.prop_cycle": ["#268bd2", "#2aa198", "#859900", "#b58900", "#cb4b16",
                            "#dc322f", "#d33682", "#6c71c4"],
    },
    "classic": {
        "figure.facecolor": "#ffffff", "axes.facecolor": "#ffffff",
        "axes.edgecolor": "#000000", "text.color": "#000000",
        "axes.labelcolor": "#000000", "xtick.color": "#000000",
        "ytick.color": "#000000", "grid.color": "#b0b0b0",
        "axes.prop_cycle": ["#0000ff", "#00ff00", "#ff0000", "#00ffff",
                            "#ff00ff", "#ffff00", "#000000"],
    },
}
for _petroff_style in ("petroff6", "petroff8", "petroff10"):
    _STYLE_PRESETS[_petroff_style] = {
        "axes.prop_cycle": list(color_sequences[_petroff_style])}


def _style_rc(style: Any) -> dict[str, Any]:
    """Merge a preset name, a list of names or a dict into one rc mapping."""
    if isinstance(style, dict):
        merged = dict(style)
        if isinstance(merged.get("axes.prop_cycle"), list):
            merged["axes.prop_cycle"] = _CycleList(merged["axes.prop_cycle"])
        return merged
    if isinstance(style, (list, tuple)):
        merged = {}
        for item in style:
            merged.update(_style_rc(item))
        return merged
    name = str(style)
    if name == "default":
        return dict(_RC_DEFAULTS)
    if name not in _STYLE_PRESETS:
        raise ValueError(f"style not found: {name!r}")
    return _style_rc(_STYLE_PRESETS[name])


class _StyleLibrary:
    """The `plt.style` namespace: presets, `use`, and `context`."""

    available = sorted(["default", *_STYLE_PRESETS], key=str)
    library = _STYLE_PRESETS

    def use(self, style: Any) -> None:
        if isinstance(style, str) and style == "default":
            rcdefaults()
        else:
            rcParams.update(_style_rc(style))

    def context(self, style: Any) -> Any:
        return rc_context(_style_rc(style))


style = _StyleLibrary()


def savefig(fname: Any = None, format: Any = None, dpi: Any = None,
            bbox_inches: Any = None, transparent: Any = None,
            facecolor: Any = None, edgecolor: Any = None,
            compression: Any = None, pad_inches: Any = None,
            metadata: Any = None, pil_kwargs: Any = None,
            **kwargs: Any) -> Any:
    """Save the current figure, inferring the format from the filename."""
    return gcf().savefig(fname, format=format, dpi=dpi, bbox_inches=bbox_inches,
                         transparent=transparent, facecolor=facecolor, edgecolor=edgecolor,
                         compression=compression, pad_inches=pad_inches,
                         metadata=metadata, pil_kwargs=pil_kwargs, **kwargs)
