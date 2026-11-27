"""matplotvite: minimal matplotlib-like API rendered entirely in Rust.

The implementation lives in the sibling modules below; this module binds
names they only need once called and re-exports the whole surface.
"""
# ruff: noqa: F401, I001
import copy
import datetime as _datetime
import hashlib as _hashlib
import math as _math
import os
import re as _re
import struct as _struct
import threading
import warnings
import zlib as _zlib
from contextlib import contextmanager, suppress
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

from . import tri, units
from ._colors import CSS_COLORS as _CSS_COLORS
from ._core import (
    AsinhNorm as _AsinhNorm,
)
from ._core import (
    BoundaryNorm as _BoundaryNorm,
)
from ._core import (
    Colormap,
)
from ._core import (
    LogNorm as _LogNorm,
)
from ._core import (
    Normalize as _Normalize,
)
from ._core import (
    PowerNorm as _PowerNorm,
)
from ._core import (
    SymLogNorm as _SymLogNorm,
)
from ._core import (
    TwoSlopeNorm as _TwoSlopeNorm,
)
from ._core import (
    auto_ticks as _auto_ticks_core,
)
from ._core import (
    cmap_name as _core_cmap_name,
)
from ._core import (
    colormaps as _colormaps,
)
from ._core import (
    register_colormap as _register_colormap,
)
from ._core import (
    render as _render,
)
from ._core import (
    tick_target as _tick_target_core,
)

import sys as _sys
import types as _types



def _late_bind(module: Any, name: Any, value: Any) -> Any:
    """Bind a name a module only needs once it is called."""
    setattr(module, name, value)


from . import _helpers


from . import _containers
_late_bind(_helpers, "_font_family", _containers._font_family)
_late_bind(_helpers, "_font_size", _containers._font_size)


from . import _artists
_late_bind(_containers, "Rectangle", _artists.Rectangle)


from . import _axes_plot


from . import _axes_stats


from . import _axes_field


from . import _axes_decor


from . import _axes


from . import _plot_helpers
_late_bind(_artists, "_as_f64", _plot_helpers._as_f64)
_late_bind(_artists, "_check_same_length", _plot_helpers._check_same_length)
_late_bind(_artists, "_series", _plot_helpers._series)
_late_bind(_axes, "_as_f64", _plot_helpers._as_f64)
_late_bind(_axes, "_log_bounds", _plot_helpers._log_bounds)
_late_bind(_axes, "_norm_aspect", _plot_helpers._norm_aspect)
_late_bind(_axes, "_series", _plot_helpers._series)
_late_bind(_axes_decor, "_as_f64", _plot_helpers._as_f64)
_late_bind(_axes_field, "_as_f64", _plot_helpers._as_f64)
_late_bind(_axes_field, "_as_image", _plot_helpers._as_image)
_late_bind(_axes_field, "_check_same_length", _plot_helpers._check_same_length)
_late_bind(_axes_field, "_cmap_colors", _plot_helpers._cmap_colors)
_late_bind(_axes_field, "_colors", _plot_helpers._colors)
_late_bind(_axes_field, "_contour_args", _plot_helpers._contour_args)
_late_bind(_axes_field, "_levels", _plot_helpers._levels)
_late_bind(_axes_field, "_line_colors", _plot_helpers._line_colors)
_late_bind(_axes_field, "_mesh_args", _plot_helpers._mesh_args)
_late_bind(_axes_field, "_streamplot_field", _plot_helpers._streamplot_field)
_late_bind(_axes_field, "_streamplot_sample", _plot_helpers._streamplot_sample)
_late_bind(_axes_field, "_streamplot_sampler", _plot_helpers._streamplot_sampler)
_late_bind(_axes_field, "_tri_args", _plot_helpers._tri_args)
_late_bind(_axes_field, "_tri_field", _plot_helpers._tri_field)
_late_bind(_axes_plot, "_as_f64", _plot_helpers._as_f64)
_late_bind(_axes_plot, "_band", _plot_helpers._band)
_late_bind(_axes_plot, "_bar_colors", _plot_helpers._bar_colors)
_late_bind(_axes_plot, "_check_same_length", _plot_helpers._check_same_length)
_late_bind(_axes_plot, "_colors", _plot_helpers._colors)
_late_bind(_axes_plot, "_convert_units", _plot_helpers._convert_units)
_late_bind(_axes_plot, "_err_pair", _plot_helpers._err_pair)
_late_bind(_axes_plot, "_fill", _plot_helpers._fill)
_late_bind(_axes_plot, "_line_colors", _plot_helpers._line_colors)
_late_bind(_axes_plot, "_line_styles", _plot_helpers._line_styles)
_late_bind(_axes_plot, "_mid_steps", _plot_helpers._mid_steps)
_late_bind(_axes_plot, "_parse_fmt", _plot_helpers._parse_fmt)
_late_bind(_axes_plot, "_plot_args", _plot_helpers._plot_args)
_late_bind(_axes_plot, "_resolve_data_args", _plot_helpers._resolve_data_args)
_late_bind(_axes_plot, "_runs", _plot_helpers._runs)
_late_bind(_axes_plot, "_scatter_colors", _plot_helpers._scatter_colors)
_late_bind(_axes_plot, "_series", _plot_helpers._series)
_late_bind(_axes_plot, "_sizes", _plot_helpers._sizes)
_late_bind(_axes_plot, "_stem_fmt", _plot_helpers._stem_fmt)
_late_bind(_axes_stats, "_as_f64", _plot_helpers._as_f64)
_late_bind(_axes_stats, "_band", _plot_helpers._band)
_late_bind(_axes_stats, "_box_datasets", _plot_helpers._box_datasets)
_late_bind(_axes_stats, "_colors", _plot_helpers._colors)
_late_bind(_axes_stats, "_fill", _plot_helpers._fill)
_late_bind(_axes_stats, "_kde", _plot_helpers._kde)
_late_bind(_axes_stats, "_series", _plot_helpers._series)
_late_bind(_axes_stats, "_stem_fmt", _plot_helpers._stem_fmt)
_late_bind(_containers, "_as_f64", _plot_helpers._as_f64)
_late_bind(_helpers, "_as_f64", _plot_helpers._as_f64)


from . import _images
_late_bind(_axes, "AxesImage", _images.AxesImage)
_late_bind(_axes, "GridSpec", _images.GridSpec)
_late_bind(_axes, "NonUniformImage", _images.NonUniformImage)
_late_bind(_axes, "SubplotSpec", _images.SubplotSpec)
_late_bind(_axes_field, "AxesImage", _images.AxesImage)
_late_bind(_axes_field, "ContourSet", _images.ContourSet)
_late_bind(_plot_helpers, "ContourSet", _images.ContourSet)


from . import _figure


from . import _pyplot
_late_bind(_axes, "_ScalarFormatter", _pyplot._ScalarFormatter)


from . import _config
_late_bind(_artists, "rcParams", _config.rcParams)
_late_bind(_axes, "_Namespace", _config._Namespace)
_late_bind(_axes, "rcParams", _config.rcParams)
_late_bind(_axes_decor, "rcParams", _config.rcParams)
_late_bind(_axes_field, "rcParams", _config.rcParams)
_late_bind(_axes_plot, "rcParams", _config.rcParams)
_late_bind(_containers, "rcParams", _config.rcParams)
_late_bind(_figure, "rcParams", _config.rcParams)
_late_bind(_helpers, "rcParams", _config.rcParams)
_late_bind(_images, "rcParams", _config.rcParams)
_late_bind(_pyplot, "rcParams", _config.rcParams)


from . import _cm
_late_bind(_axes_field, "_norm_values", _cm._norm_values)
_late_bind(_axes_plot, "_norm_values", _cm._norm_values)
_late_bind(_figure, "_norm_values", _cm._norm_values)
_late_bind(_helpers, "_ListedColormap", _cm._ListedColormap)
_late_bind(_pyplot, "_NoopContext", _cm._NoopContext)


from . import _ticker
_late_bind(_axes, "_MaxNLocator", _ticker._MaxNLocator)
_late_bind(_plot_helpers, "_LogLocator", _ticker._LogLocator)


from . import _png


from . import _misc
_late_bind(_helpers, "mcolors", _misc.mcolors)


from . import _projections
_late_bind(_figure, "PolarAxes", _projections.PolarAxes)
_late_bind(_figure, "_get_projection_class", _projections._get_projection_class)


from . import _fonts


_MODULES = (
    _helpers,
    _containers,
    _artists,
    _axes_plot,
    _axes_stats,
    _axes_field,
    _axes_decor,
    _axes,
    _plot_helpers,
    _images,
    _figure,
    _pyplot,
    _config,
    _cm,
    _ticker,
    _png,
    _misc,
    _projections,
    _fonts,
)


class _PlottingModule(_types.ModuleType):
    """Mirror a facade patch into the module that owns the name."""

    def __setattr__(self, name: Any, value: Any) -> Any:
        super().__setattr__(name, value)
        for _module in _MODULES:
            if name in _module.__dict__:
                setattr(_module, name, value)


_sys.modules[__name__].__class__ = _PlottingModule

from ._helpers import (
    Affine2D,
    Bbox,
    DPI,
    Normalize,
    OffsetFrom,
    Path,
    Table,
    Text,
    TextPath,
    TransformedPath,
    _ARTIST_KWARGS,
    _BAR_KWARGS,
    _Bbox,
    _BboxPatch,
    _CMAP_DATA,
    _COLLECTION_KWARGS,
    _COMPRESSIONS,
    _CYCLE,
    _CmapNamespace,
    _ColormapRegistry,
    _CoordTransform,
    _CycleList,
    _FIGURE_KWARGS,
    _FMT_COLORS,
    _FORMATS,
    _FigureImage,
    _HIST_KWARGS,
    _IGNORED_CALLS,
    _IGNORED_TEXT_KWARGS,
    _IGNORED_WARNED,
    _IMAGE_KWARGS,
    _IdentityTransform,
    _LEGEND_KWARGS,
    _LEGEND_LOCATIONS,
    _LEGEND_LOCATION_CODES,
    _LINE2D_KWARGS,
    _MATH_GREEK,
    _MATH_SUBSCRIPTS,
    _MATH_SUPERSCRIPTS,
    _MATH_SYMBOLS,
    _MAX_BINS,
    _MAX_BIN_CELLS,
    _MAX_CANVAS_AREA,
    _MAX_CANVAS_DIM,
    _MAX_EDGES,
    _MAX_FIGIMAGE_BYTES,
    _MAX_FIGIMAGE_DIM,
    _MAX_FIGIMAGE_PIXELS,
    _MAX_GRID_CELLS,
    _PATCH_KWARGS,
    _PropCycler,
    _SCATTER_KWARGS,
    _SHORT_COLORS,
    _SUBSCRIPTS,
    _SUPERSCRIPTS,
    _Share,
    _TAB10,
    _TableCell,
    _TextArt,
    _TextEntry,
    _TextLabel,
    _Transform,
    _add_months,
    _apply_axes_options,
    _as_list,
    _auto_ticks,
    _check_kwargs,
    _cmap_name,
    _colormap_names,
    _cycle_colors,
    _date_from_num,
    _date_label,
    _date_ticks,
    _date_to_num,
    _datetime_to_num,
    _deprecated,
    _format_ticklabels,
    _ignored,
    _is_rgb,
    _logit_ticks,
    _looks_like_categories,
    _looks_like_dates,
    _margin,
    _math_script,
    _mathtext,
    _nice_step,
    _norm_color,
    _normalize_legend_loc,
    _output_format,
    _register_custom_cmap,
    _rotation_value,
    _scale_transform_pair,
    _scale_values,
    _segment_intersects_bbox,
    _share_axes,
    _span_extent,
    _symlog_label,
    _symlog_ticks,
    _text_bbox,
    _text_props,
    _update_extent,
    _validate_bins,
    _validate_dimension,
    _validate_figsize,
    _validate_grid_shape,
    _validate_linestyle,
    _validate_savefig_mapping,
    _validate_share,
    _with_alpha,
    cm,
    colormaps,
    cycler,
    get_cmap,
)

from ._containers import (
    HandlerLineCollection,
    HandlerTuple,
    _BarContainer,
    _BarHandle,
    _FONT_FAMILY_ALIASES,
    _FONT_SCALINGS,
    _GridLine,
    _HexbinHandle,
    _LegendHandle,
    _LineGroupHandle,
    _LineHandle,
    _PieResult,
    _QuiverHandle,
    _ScatterHandle,
    _StemContainer,
    _StickyEdges,
    _StreamplotSet,
    _ViolinBody,
    _Wedge,
    _call,
    _color_list,
    _family_override,
    _font_family,
    _font_size,
    _number,
    _numbers,
    _single_color,
)

from ._artists import (
    Annulus,
    Arc,
    Arrow,
    Artist,
    Circle,
    CirclePolygon,
    Collection,
    ConnectionPatch,
    Ellipse,
    EllipseCollection,
    EventCollection,
    FancyArrow,
    FancyArrowPatch,
    FancyBboxPatch,
    Line2D,
    LineCollection,
    MouseEvent,
    Patch,
    PatchCollection,
    PathCollection,
    PathPatch,
    PolyCollection,
    Polygon,
    Rectangle,
    RegularPolyCollection,
    RegularPolygon,
    StepPatch,
    Wedge,
    _Axis,
    _AxisAccessor,
    _AxisArtistProxy,
    _AxisHelper,
    _AxisSelection,
    _Callbacks,
    _Canvas,
    _FlexibleStyleNamespace,
    _GroupedBarResult,
    _LayoutEngine,
    _LocatorHandle,
    _MARKERS,
    _Manager,
    _PatchesNamespace,
    _Spine,
    _SpineSelection,
    _Spines,
    _SubplotPars,
    _Timer,
    _collection_entry,
    _patch_entry,
    _patch_name,
    _spectral_estimates,
    patches,
)

from ._axes_plot import (
    _AXES_ARTIST_PROPS,
    _AxesMixinBase,
    _PlotAxes,
)

from ._axes_stats import (
    _StatsAxes,
)

from ._axes_field import (
    _FieldAxes,
)

from ._axes_decor import (
    _DecorAxes,
)

from ._axes import (
    Axes,
)

from ._plot_helpers import (
    MarkerStyle,
    _STEM_MARKERS,
    _as_f64,
    _as_image,
    _band,
    _bar_colors,
    _box_datasets,
    _boxplot_stats,
    _check_same_length,
    _cmap_colors,
    _colors,
    _contour_args,
    _contour_label_colour,
    _contour_label_text,
    _contour_segments,
    _convert_units,
    _err_pair,
    _figimage_payload_estimate,
    _fill,
    _hash_value,
    _is_color_sequence,
    _is_triangulation,
    _kde,
    _levels,
    _line_colors,
    _line_styles,
    _log_bounds,
    _mesh_args,
    _mid_steps,
    _norm_aspect,
    _panel_cache_key,
    _parse_fmt,
    _path_subpaths,
    _plot_args,
    _point_segment_distance,
    _polygon_area_sign,
    _resolve_data_args,
    _runs,
    _scatter_colors,
    _series,
    _sizes,
    _stem_fmt,
    _streamplot_bracket,
    _streamplot_field,
    _streamplot_sample,
    _streamplot_sampler,
    _tri_args,
    _tri_field,
)

from ._images import (
    AxesImage,
    BboxImage,
    Colorbar,
    ContourSet,
    GridSpec,
    NonUniformImage,
    SubplotSpec,
    _ColorbarAxes,
    _ColorbarAxis,
    _ColorbarDividers,
    _resolve_colorbar_extendfrac,
    _span_index,
)

from ._figure import (
    Figure,
    _SubFigure,
    _figures,
    _subfigure_array,
)

from ._pyplot import (
    FormatStrFormatter,
    FuncFormatter,
    _Duration,
    _Epoch,
    _ScalarFormatter,
    _TestingUnits,
    _backend,
    _current_fig,
    _figure_lock,
    _find_figure_locked,
    _is_artist_sequence,
    _is_pandas_data,
    _new_figure_locked,
    annotate,
    autoscale,
    axes,
    axhline,
    axhspan,
    axline,
    axvline,
    axvspan,
    bar,
    bar_label,
    barbs,
    barh,
    box,
    boxplot,
    broken_barh,
    clabel,
    close,
    colorbar,
    connect,
    contour,
    contourf,
    draw,
    draw_all,
    draw_if_interactive,
    ecdf,
    errorbar,
    eventplot,
    figaspect,
    figimage,
    fignum_exists,
    figtext,
    figure,
    fill,
    fill_between,
    fill_betweenx,
    gca,
    gcf,
    get_backend,
    get_data_path,
    get_figlabels,
    get_fignums,
    getp,
    grid,
    grouped_bar,
    hexbin,
    hist,
    hist2d,
    hlines,
    imshow,
    ioff,
    ion,
    legend,
    loglog,
    matshow,
    minorticks_off,
    minorticks_on,
    pause,
    pcolor,
    pcolorfast,
    pcolormesh,
    pie,
    pie_label,
    plot,
    polar,
    quiver,
    quiverkey,
    sca,
    scatter,
    semilogx,
    semilogy,
    set_cmap,
    setp,
    show,
    specgram,
    spy,
    stackplot,
    stairs,
    stem,
    step,
    streamplot,
    subplot,
    subplot2grid,
    subplot_mosaic,
    subplots,
    subplots_adjust,
    suptitle,
    switch_backend,
    table,
    testing,
    text,
    tick_params,
    tight_layout,
    title,
    tricontour,
    tricontourf,
    tripcolor,
    triplot,
    twinx,
    twiny,
    use,
    violinplot,
    vlines,
    xkcd,
    xlabel,
    xlim,
    xscale,
    xticks,
    ylabel,
    ylim,
    yscale,
    yticks,
)

from ._config import (
    _Namespace,
    _RC_DEFAULTS,
    rcParams,
)

from ._cm import (
    Colorizer,
    LightSource,
    ScalarMappable,
    _AxisModule,
    _BivarColormap,
    _LinearSegmentedColormap,
    _ListedColormap,
    _MColors,
    _Mlab,
    _MultivarColormap,
    _NoopContext,
    _norm_values,
    _rgba_tuple,
    bivar_colormaps,
    from_levels_and_colors,
    hsv_to_rgb,
    rgb_to_hsv,
)

from ._ticker import (
    CapStyle,
    FontProperties,
    JoinStyle,
    NullLocator,
    _AutoDateFormatter,
    _AutoDateLocator,
    _CalendarLocator,
    _ConciseDateConverter,
    _ConciseDateFormatter,
    _DateFormatter,
    _DayLocator,
    _EngFormatter,
    _FixedFormatter,
    _FixedLocator,
    _HourLocator,
    _IndexLocator,
    _LinearLocator,
    _Locator,
    _LogLocator,
    _MaxNLocator,
    _MinuteLocator,
    _MonthLocator,
    _MultipleLocator,
    _NoopFormatter,
    _NoopLocator,
    _PNG_SIGNATURE,
    _PathEffects,
    _PercentFormatter,
    _RRuleLocator,
    _SecondLocator,
    _StyleMeta,
    _StyleValue,
    _TransformedBbox,
    _YearLocator,
    _drange,
    _locator_span,
    _locator_value,
    _num_to_date,
    _rrulewrapper,
    same_color,
)

from ._png import (
    _PNG_MAX_BYTES,
    _decode_png,
    _flatten,
    _get_sample_data,
    _imread,
    _png_unfilter_serial,
    _write_png_image,
    imread,
    imsave,
)

from ._misc import (
    GridSpecFromSubplotSpec,
    _INTERPD,
    _blended_transform_factory,
    _offset_copy,
    collections,
    colorizer,
    colors,
    image,
    markers,
    mcollections,
    mcolorbar,
    mcolors,
    mmarkers,
    mpatches,
    mpath,
    mtransforms,
    path,
    transforms,
)

from ._projections import (
    AitoffAxes,
    AutoDateFormatter,
    AutoDateLocator,
    Axes3D,
    ConciseDateConverter,
    ConciseDateFormatter,
    DAILY,
    DateFormatter,
    DayLocator,
    EngFormatter,
    FR,
    FixedFormatter,
    FixedLocator,
    GeoAxes,
    HOURLY,
    HammerAxes,
    HourLocator,
    LambertAxes,
    LinearLocator,
    LogLocator,
    MINUTELY,
    MO,
    MONTHLY,
    MaxNLocator,
    MicrosecondLocator,
    MinuteLocator,
    MollweideAxes,
    MonthLocator,
    MultipleLocator,
    PercentFormatter,
    PolarAxes,
    RRuleLocator,
    SA,
    SECONDLY,
    SU,
    SecondLocator,
    SkewXAxes,
    TH,
    TU,
    WE,
    WEEKLY,
    WeekdayLocator,
    YEARLY,
    YearLocator,
    _PROJECTIONS,
    _ProjectionAxis,
    _Tick,
    _XAxis,
    _XTick,
    _YAxis,
    _YTick,
    _epoch,
    _geo_axes,
    _get_projection_class,
    _get_projection_names,
    _polar_text,
    _register_projection,
    axis,
    drange,
    mticker,
    projections,
    register_projection,
    rrulewrapper,
    ticker,
)

from ._fonts import (
    FT2Font,
    FaceFlags,
    Kerning,
    StyleFlags,
    _ColorSequences,
    _FT2Glyph,
    _FontFlag,
    _FontFlagSet,
    _FontFlagsMeta,
    _PETROFF,
    _STYLE_PRESETS,
    _StyleLibrary,
    _colormap_sequence,
    _findfont,
    _get_epoch,
    _petroff_style,
    _sequence,
    _set_epoch,
    _style_rc,
    cbook,
    color_sequences,
    dates,
    findfont,
    font_manager,
    ft2font,
    gridspec,
    lines,
    mdates,
    mlab,
    path_effects,
    patheffects,
    rc,
    rc_context,
    rcdefaults,
    savefig,
    style,
)
