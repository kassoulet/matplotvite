# matplotlib test-suite coverage trace

91 test files scanned. Static AST scan, counts are call sites.

Call sites implemented: **9178/10098** (90%)
Call sites accepted and ignored: **632/10098** (6%)
Call sites missing: **288/10098** (2%)

`implemented` produces renderer output or real state; `accepted and ignored` exists as a no-op compatibility shim; `missing` is not available.

## Priority gaps

Missing call sites sorted by how often matplotlib's own tests use them.

| calls | API | files |
|--:|---|---:|
| 23 | `Axes.format_coord` | 2 |
| 16 | `Axes.get_cursor_data` | 2 |
| 16 | `Axes.contains` | 6 |
| 14 | `Figure.get_linewidth` | 6 |
| 12 | `Axes.format_cursor_data` | 2 |
| 10 | `pyplot.switch_backend` | 3 |
| 10 | `Figure.set_edgecolor` | 4 |
| 8 | `pyplot.imsave` | 1 |
| 8 | `Axes.get_navigate_mode` | 1 |
| 7 | `Axes.set_figure` | 2 |
| 7 | `Axes.get_autoscaley_on` | 2 |
| 7 | `Axes.get_autoscalex_on` | 2 |
| 6 | `Axes.violin` | 2 |
| 6 | `Axes.contains_point` | 3 |
| 5 | `Axes.set_url` | 1 |
| 5 | `Axes.draw_artist` | 3 |
| 4 | `pyplot.box` | 1 |
| 4 | `Axes.set_rasterized` | 4 |
| 4 | `Axes.add_callback` | 2 |
| 3 | `Figure.waitforbuttonpress` | 1 |
| 3 | `Figure.show` | 2 |
| 3 | `Figure.set_linewidth` | 2 |
| 3 | `Figure.set_figwidth` | 2 |
| 3 | `Figure.set_figheight` | 2 |
| 3 | `Figure.get_suptitle` | 2 |

## pyplot: implemented

`subplots`, `figure`, `subplot`, `plot`, `gca`, `axes`, `close`, `colorbar`, `legend`, `scatter`, `text`, `contourf`, `rc`, `savefig`, `imread`, `gcf`, `subplot_mosaic`, `contour`, `pcolor`, `streamplot`, `hist`, `axis`, `title`, `rc_context`, `quiver`, `pie`, `setp`, `pcolormesh`, `imshow`, `fignum_exists`, `errorbar`, `ylim`, `xticks`, `xlim`, `tricontourf`, `subplot2grid`, `polar`, `Circle`, `figtext`, `clabel`, `Rectangle`, `xlabel`, `get_fignums`, `bar`, `ylabel`, `tricontour`, `table`, `stairs`, `getp`, `figaspect`, `Line2D`, `suptitle`, `get_cmap`, `FixedLocator`, `yticks`, `triplot`, `tripcolor`, `fill_between`, `eventplot`, `NullLocator`, `MultipleLocator`, `FormatStrFormatter`, `FixedFormatter`, `yscale`, `xscale`, `violinplot`, `twinx`, `stem`, `stackplot`, `set_cmap`, `matshow`, `fill`, `boxplot`, `axline`, `annotate`, `MaxNLocator`, `LinearLocator`

## pyplot: accepted and ignored

| calls | name | files |
|--:|---|--:|
| 26 | `draw` | 10 |
| 13 | `tight_layout` | 3 |
| 11 | `ion` | 1 |
| 11 | `ioff` | 1 |
| 10 | `pause` | 2 |
| 9 | `show` | 4 |
| 5 | `subplots_adjust` | 4 |
| 4 | `xkcd` | 2 |

## pyplot: missing

| calls | name | files |
|--:|---|--:|
| 10 | `switch_backend` | 3 |
| 8 | `imsave` | 1 |
| 4 | `box` | 1 |
| 2 | `specgram` | 1 |
| 2 | `sca` | 2 |
| 2 | `get_figlabels` | 1 |
| 2 | `ecdf` | 1 |
| 2 | `draw_all` | 1 |
| 2 | `barbs` | 2 |
| 2 | `Normalize` | 2 |
| 1 | `get_backend` | 1 |
| 1 | `figimage` | 1 |
| 1 | `draw_if_interactive` | 1 |
| 1 | `autoscale` | 1 |
| 1 | `FuncFormatter` | 1 |

## Axes: implemented

`plot`, `imshow`, `text`, `set_xlim`, `legend`, `set_ylim`, `scatter`, `set_title`, `get_position`, `add_patch`, `get_ylim`, `get_xlim`, `pcolormesh`, `set`, `errorbar`, `bar`, `hist`, `get_visible`, `remove`, `add_artist`, `get_window_extent`, `get_facecolor`, `set_xlabel`, `contour`, `set_yscale`, `boxplot`, `annotate`, `tick_params`, `set_ylabel`, `set_xticks`, `violinplot`, `set_xscale`, `set_aspect`, `set_yticks`, `get_transform`, `axis`, `add_collection`, `set_prop_cycle`, `get_xticklabels`, `stem`, `set_axis_off`, `contourf`, `axhline`, `twinx`, `stairs`, `fill_between`, `set_visible`, `set_facecolor`, `get_alpha`, `set_position`, `grid`, `barh`, `pie`, `clear`, `get_tightbbox`, `bar_label`, `psd`, `hexbin`, `axline`, `hlines`, `get_figure`, `clabel`, `set_alpha`, `axvline`, `vlines`, `fill`, `quiver`, `get_yticklabels`, `get_label`, `eventplot`, `minorticks_on`, `inset_axes`, `get_yticks`, `tripcolor`, `table`, `pcolorfast`, `get_subplotspec`, `specgram`, `set_label`, `get_zorder`, `twiny`, `get_title`, `step`, `stackplot`, `loglog`, `get_ybound`, `axvspan`, `set_xticklabels`, `get_children`, `broken_barh`, `invert_yaxis`, `grouped_bar`, `get_xticks`, `get_xbound`, `set_zorder`, `pcolor`, `get_gridspec`, `fill_betweenx`, `cla`, `barbs`, `yaxis_inverted`, `set_yticklabels`, `set_box_aspect`, `get_aspect`, `axhspan`, `add_line`, `tricontourf`, `tricontour`, `streamplot`, `invert_xaxis`, `get_ylabel`, `semilogx`, `minorticks_off`, `hist2d`, `get_legend_handles_labels`, `csd`, `arrow`, `triplot`, `get_yscale`, `xaxis_inverted`, `spy`, `set_ybound`, `set_xbound`, `set_in_layout`, `semilogy`, `get_xlabel`, `get_frame_on`, `get_forward_navigation_events`, `get_yaxis_transform`, `get_xscale`, `get_xaxis_transform`, `add_image`, `sharey`, `sharex`, `matshow`, `magnitude_spectrum`, `indicate_inset_zoom`, `indicate_inset`, `get_in_layout`, `ecdf`, `bxp`, `acorr`, `set_rasterization_zorder`, `set_anchor`, `set_adjustable`, `phase_spectrum`, `get_box_aspect`, `get_adjustable`, `cohere`, `angle_spectrum`

## Axes: accepted and ignored

| calls | name | files |
|--:|---|--:|
| 208 | `draw` | 37 |
| 35 | `update` | 17 |
| 18 | `quiverkey` | 1 |
| 18 | `margins` | 3 |
| 15 | `set_clip_path` | 6 |
| 15 | `autoscale` | 4 |
| 12 | `set_path_effects` | 2 |
| 10 | `secondary_xaxis` | 2 |
| 9 | `relim` | 2 |
| 8 | `autoscale_view` | 4 |
| 5 | `pie_label` | 2 |
| 5 | `locator_params` | 3 |
| 4 | `label_outer` | 1 |
| 2 | `set_frame_on` | 2 |
| 2 | `set_clip_on` | 1 |
| 2 | `set_autoscale_on` | 1 |
| 2 | `secondary_yaxis` | 1 |
| 2 | `get_legend` | 1 |
| 1 | `ticklabel_format` | 1 |
| 1 | `set_xmargin` | 1 |
| 1 | `set_forward_navigation_events` | 1 |
| 1 | `set_axisbelow` | 1 |
| 1 | `set_autoscaley_on` | 1 |
| 1 | `set_autoscalex_on` | 1 |

## Axes: missing

| calls | name | files |
|--:|---|--:|
| 23 | `format_coord` | 2 |
| 16 | `get_cursor_data` | 2 |
| 16 | `contains` | 6 |
| 12 | `format_cursor_data` | 2 |
| 8 | `get_navigate_mode` | 1 |
| 7 | `set_figure` | 2 |
| 7 | `get_autoscaley_on` | 2 |
| 7 | `get_autoscalex_on` | 2 |
| 6 | `violin` | 2 |
| 6 | `contains_point` | 3 |
| 5 | `set_url` | 1 |
| 5 | `draw_artist` | 3 |
| 4 | `set_rasterized` | 4 |
| 4 | `add_callback` | 2 |
| 3 | `xaxis_date` | 2 |
| 3 | `start_pan` | 1 |
| 3 | `set_transform` | 3 |
| 3 | `is_transform_set` | 1 |
| 3 | `get_navigate` | 1 |
| 3 | `get_lines` | 1 |
| 3 | `get_autoscale_on` | 1 |
| 3 | `end_pan` | 1 |
| 3 | `apply_aspect` | 1 |
| 2 | `update_from` | 2 |
| 2 | `set_gid` | 1 |
| 2 | `set_clip_box` | 2 |
| 2 | `set_agg_filter` | 2 |
| 2 | `properties` | 2 |
| 2 | `pchanged` | 1 |
| 2 | `get_animated` | 1 |
| 2 | `get_anchor` | 1 |
| 2 | `drag_pan` | 1 |
| 1 | `yaxis_date` | 1 |
| 1 | `set_sketch_params` | 1 |
| 1 | `set_picker` | 1 |
| 1 | `set_animated` | 1 |
| 1 | `remove_callback` | 1 |
| 1 | `redraw_in_frame` | 1 |
| 1 | `pick` | 1 |
| 1 | `get_ymargin` | 1 |
| 1 | `get_xmargin` | 1 |
| 1 | `get_xgridlines` | 1 |
| 1 | `get_path_effects` | 1 |
| 1 | `get_images` | 1 |
| 1 | `get_clip_path` | 1 |
| 1 | `get_axisbelow` | 1 |
| 1 | `format_ydata` | 1 |
| 1 | `format_xdata` | 1 |
| 1 | `findobj` | 1 |

## Figure: implemented

`add_subplot`, `subplots`, `savefig`, `colorbar`, `add_axes`, `suptitle`, `get_edgecolor`, `subfigures`, `add_gridspec`, `subplot_mosaic`, `set_size_inches`, `gca`, `get_layout_engine`, `set_layout_engine`, `add_subfigure`, `figimage`, `supylabel`, `supxlabel`, `get_size_inches`, `get_constrained_layout`, `autofmt_xdate`, `get_tight_layout`, `get_axes`, `get_dpi`

## Figure: accepted and ignored

| calls | name | files |
|--:|---|--:|
| 102 | `draw_without_rendering` | 19 |
| 26 | `subplots_adjust` | 10 |
| 20 | `tight_layout` | 6 |
| 5 | `set_constrained_layout` | 1 |
| 4 | `set_tight_layout` | 1 |
| 4 | `align_ylabels` | 3 |
| 2 | `align_xlabels` | 1 |
| 1 | `align_titles` | 1 |
| 1 | `align_labels` | 1 |

## Figure: missing

| calls | name | files |
|--:|---|--:|
| 14 | `get_linewidth` | 6 |
| 10 | `set_edgecolor` | 4 |
| 3 | `waitforbuttonpress` | 1 |
| 3 | `show` | 2 |
| 3 | `set_linewidth` | 2 |
| 3 | `set_figwidth` | 2 |
| 3 | `set_figheight` | 2 |
| 3 | `get_suptitle` | 2 |
| 3 | `get_figwidth` | 1 |
| 3 | `get_figheight` | 1 |
| 2 | `ginput` | 1 |
| 2 | `get_supylabel` | 1 |
| 2 | `get_supxlabel` | 1 |
| 1 | `set_dpi` | 1 |
| 1 | `sca` | 1 |
| 1 | `get_constrained_layout_pads` | 1 |
| 1 | `delaxes` | 1 |
| 1 | `clf` | 1 |

## Unsupported kwargs on implemented calls

- `plot`: `rasterized` (22), `markevery` (17), `zorder` (14), `transform` (12), `xunits` (6), `animated` (5), `yunits` (4), `picker` (4), `fillstyle` (4), `ds` (4), `path_effects` (3), `solid_joinstyle` (2), `gapcolor` (2), `dashes` (2), `pickradius` (1), `markerfacecoloralt` (1)
- `subplots`: `figsize` (72), `layout` (65), `constrained_layout` (19), `dpi` (16), `width_ratios` (4), `tight_layout` (4), `num` (4), `clear` (2), `height_ratios` (1)
- `scatter`: `color` (16), `edgecolor` (11), `facecolor` (8), `transform` (6), `linewidths` (6), `edgecolors` (6), `ec` (6), `fc` (4), `colorizer` (3), `plotnonfinite` (2), `picker` (2), `ls` (2), `facecolors` (2), `path_effects` (1), `linewidth` (1), `linestyle` (1), `clip_on` (1)
- `text`: `fontsize` (35), `ha` (34), `horizontalalignment` (31), `verticalalignment` (30), `va` (19), `size` (17), `wrap` (15), `usetex` (15), `rotation` (15), `color` (12), `math_fontfamily` (9), `font` (9), `family` (9), `transform` (8), `bbox` (7), `antialiased` (6), `alpha` (6), `fontproperties` (5), `clip_on` (5), `url` (4)
- `imshow`: `interpolation_stage` (20), `transform` (10), `clip_path` (3), `clip_on` (2), `rasterized` (1), `data` (1), `animated` (1)
- `colorbar`: `orientation` (33), `shrink` (27), `extend` (25), `location` (22), `cax` (17), `use_gridspec` (15), `pad` (12), `aspect` (10), `panchor` (6), `anchor` (6), `spacing` (4), `ticks` (3), `fraction` (2), `format` (2), `extendfrac` (2), `boundaries` (2), `ticklocation` (1), `extendrect` (1)
- `errorbar`: `c` (10), `marker` (9), `ls` (9), `errorevery` (8), `uplims` (4), `lolims` (4), `mfc` (3), `markevery` (3), `xuplims` (2), `xlolims` (2), `ms` (2), `linestyle` (2), `data` (2), `zorder` (1), `solid_joinstyle` (1), `solid_capstyle` (1), `mec` (1), `lw` (1), `fillstyle` (1), `elinestyle` (1)
- `legend`: `labelcolor` (39), `shadow` (8), `title_fontproperties` (5), `numpoints` (5), `mode` (4), `reverse` (2), `linewidth` (2), `handler_map` (2), `handlelength` (2), `draggable` (2), `markerfirst` (1), `handleheight` (1), `framealpha` (1), `fancybox` (1), `facecolor` (1), `alignment` (1)
- `savefig`: `backend` (5), `papertype` (3), `orientation` (2), `non_existent_kwarg` (1)
- `set`: `ylim` (41), `xlim` (41), `xlabel` (12), `ylabel` (9), `xscale` (9), `yscale` (6), `yticks` (5), `path_effects` (5), `h_pad` (5), `xticks` (4), `w_pad` (4), `aspect` (3), `yticklabels` (2), `xticklabels` (2), `wspace` (2), `rect` (2), `lw` (2), `linewidth` (2), `hspace` (2), `adjustable` (2)
- `annotate`: `xycoords` (26), `textcoords` (22), `va` (7), `fontproperties` (5), `clip_on` (3), `verticalalignment` (2), `size` (2), `horizontalalignment` (2), `ha` (2), `path_effects` (1), `clip_path` (1), `bbox` (1), `annotation_clip` (1)
- `hist`: `ec` (9), `fc` (5), `log` (3), `zorder` (1), `fill` (1)
- `figure`: `layout` (23), `constrained_layout` (5), `frameon` (2), `clear` (2)
- `pie`: `wedgeprops` (12), `center` (4), `textprops` (3), `frame` (3), `rotatelabels` (2), `radius` (2), `labeldistance` (2), `hatch` (2), `data` (2), `counterclock` (1)
- `tick_params`: `direction` (12), `which` (11), `labelleft` (10), `labelbottom` (9), `bottom` (6), `length` (5), `left` (5), `labeltop` (5), `top` (4), `labelsize` (4), `width` (3), `rotation` (3), `right` (3), `labelrotation` (3), `labelright` (3), `labelcolor` (3), `colors` (3), `tick2On` (2), `tick1On` (2), `reset` (2)
- `violinplot`: `facecolor` (4), `linecolor` (3), `data` (1)
- `bar`: `tick_label` (4), `antialiased` (4), `hatch` (2), `facecolor` (2), `zorder` (1), `xerr` (1), `data` (1), `capsize` (1)
- `add_subplot`: `projection` (48), `polar` (5), `xticks` (4), `facecolor` (3), `axes_class` (3), `aspect` (3), `yticks` (2), `yscale` (2), `xticklabels` (2), `xscale` (2), `sharey` (2), `sharex` (2), `zorder` (1), `ylim` (1), `xlim` (1), `autoscale_on` (1), `anchor` (1)
- `pcolormesh`: `zorder` (5), `lw` (4), `edgecolors` (4), `transform` (2), `snap` (2), `rasterized` (2), `colorizer` (2)
- `specgram`: `norm` (2), `origin` (1)
- `contourf`: `extend` (11), `algorithm` (6), `hatches` (5), `corner_mask` (5), `norm` (4), `colorizer` (3), `transform` (2), `vmin` (1), `vmax` (1), `rasterized` (1), `clip_path` (1)
- `stairs`: `ls` (8), `lw` (5), `hatch` (1), `facecolor` (1)
- `contour`: `linestyles` (7), `extend` (4), `negative_linestyles` (3), `colorizer` (3), `zorder` (1), `norm` (1), `linestyle` (1), `corner_mask` (1), `color` (1), `clip_path` (1), `algorithm` (1), `Z` (1)
- `table`: `loc` (16), `rowLabels` (10), `colLabels` (10), `zorder` (2), `rowColours` (2), `colColours` (2), `bbox` (2), `fontsize` (1), `edges` (1), `colWidths` (1)
- `fill_between`: `facecolor` (11), `hatch` (7), `edgecolor` (3), `lw` (2), `data` (2), `transform` (1)
- `boxplot`: `bootstrap` (7), `usermedians` (3), `conf_intervals` (3), `zorder` (1), `data` (1)
- `axhline`: `lw` (7), `zorder` (4), `c` (1)
- `hlines`: `linewidth` (7), `lw` (4), `color` (4), `ls` (2), `transform` (1), `linestyle` (1)
- `hexbin`: `colorizer` (2), `picker` (1)
- `vlines`: `linewidth` (8), `lw` (4), `color` (4), `ls` (2), `linestyle` (2), `transform` (1), `gapcolor` (1), `alpha` (1)
- `barh`: `yerr` (1), `tick_label` (1)
- `subplot`: `projection` (22), `polar` (5), `theta_offset` (3), `sharey` (2), `anchor` (2), `sharex` (1), `aspect` (1)
- `streamplot`: `transform` (1)
- `set_title`: `loc` (16), `pad` (5), `fontweight` (5), `y` (1)
- `clabel`: `fontsize` (10), `inline` (8), `manual` (6), `use_clabeltext` (2), `fmt` (2), `colors` (2), `zorder` (1), `levels` (1), `inline_spacing` (1)
- `rc`: `size` (12), `fonttype` (10), `family` (7), `prop_cycle` (1), `linewidth` (1), `id` (1)
- `axline`: `color` (10), `transform` (7), `c` (1)
- `eventplot`: `alpha` (4), `linewidth` (1), `linestyle` (1), `label` (1), `data` (1), `color` (1)
- `axvline`: `lw` (3), `zorder` (2), `gapcolor` (1), `c` (1)
- `quiver`: `transform` (2), `zorder` (1)
- `subplot_mosaic`: `layout` (5), `subplot_kw` (4), `width_ratios` (3), `num` (3), `sharey` (2), `sharex` (2), `per_subplot_kw` (2), `height_ratios` (2), `gridspec_kw` (2), `clear` (1)
- `set_ylabel`: `loc` (7), `y` (5), `ha` (4), `fontweight` (2), `fontname` (1)
- `add_axes`: `polar` (8), `projection` (3), `label` (2), `yticks` (1), `ylim` (1), `xticks` (1), `sharex` (1), `frameon` (1), `autoscaley_on` (1), `autoscalex_on` (1), `autoscale_on` (1)
- `step`: `lw` (6), `linestyle` (6), `data` (3), `c` (2)
- `set_xlabel`: `loc` (7), `x` (4), `ha` (3), `fontname` (1)
- `set_xlim`: `xmin` (1), `xmax` (1), `auto` (1)
- `axhspan`: `facecolor` (5), `fc` (2)
- `Circle`: `gid` (6), `transform` (5), `zorder` (3), `facecolor` (3), `clip_on` (2), `alpha` (1)
- `axvspan`: `facecolor` (5), `fc` (2)
- `grouped_bar`: `positions` (1), `hatch` (1), `bar_spacing` (1)
- `barbs`: `transform` (3), `sizes` (3), `rounding` (3), `fill_empty` (3), `pivot` (2), `length` (2), `flip_barb` (1), `cmap` (1)
- `Rectangle`: `hatch` (5), `label` (4), `fill` (3), `edgecolor` (2), `color` (1), `alpha` (1)
- `fill`: `facecolor` (3), `zorder` (2), `lw` (2), `hatch` (2), `edgecolor` (2), `linewidth` (1), `ec` (1)
- `grid`: `color` (4), `linewidth` (3), `linestyle` (2), `path_effects` (1), `alpha` (1)
- `set_prop_cycle`: `linewidth` (3), `color` (3), `lw` (2), `ls` (2), `c` (2), `marker` (1), `label` (1), `foobar` (1), `facecolor` (1)
- `suptitle`: `color` (2), `wrap` (1), `weight` (1), `url` (1), `size` (1), `rotation` (1), `in_layout` (1), `fontproperties` (1)
- `set_ylim`: `ymin` (2), `ymax` (2)
- `figimage`: `colorizer` (2)
- `stackplot`: `hatch` (1), `facecolors` (1), `facecolor` (1), `data` (1)
- `subfigures`: `wspace` (3), `height_ratios` (2), `width_ratios` (1), `label` (1), `hspace` (1)
- `bar_label`: `color` (1)
- `tripcolor`: `clim` (1), `C` (1)
- `fill_betweenx`: `step` (2), `lw` (2), `interpolate` (2), `facecolor` (2)
- `arrow`: `head_length` (3), `width` (2), `head_width` (2), `shape` (1), `length_includes_head` (1), `head_starts_at_zero` (1)
- `tricontour`: `colorizer` (2)
- `set_label`: `ha` (3), `x` (2), `loc` (2), `y` (1)
- `hist2d`: `rasterized` (3)
- `axes`: `projection` (6), `position` (2)
- `set_yscale`: `nonpositive` (3), `subs` (1), `foo` (1)
- `add_gridspec`: `wspace` (1), `left` (1), `figure` (1)
- `get_window_extent`: `dpi` (1)
- `setp`: `visible` (2), `remove_overlapping_locs` (1), `path_effects` (1), `file` (1), `color` (1)
- `set_xscale`: `nonpositive` (1), `linthresh` (1), `functions` (1)
- `loglog`: `lw` (4), `nonpositive` (1), `c` (1)
- `broken_barh`: `align` (4), `facecolors` (2)
- `inset_axes`: `ylim` (1), `xlim` (1), `sharey` (1), `projection` (1), `polar` (1), `axes_class` (1)
- `pcolorfast`: `colorizer` (6)
- `ecdf`: `ls` (1), `data` (1), `compress` (1)
- `Line2D`: `gid` (3), `zorder` (1), `transform` (1), `label` (1)
- `triplot`: `color` (2), `lw` (1), `ls` (1), `linestyle` (1), `label` (1)
- `tricontourf`: `colorizer` (2)
- `xticks`: `rotation` (1), `minor` (1)
- `set_yticks`: `rotation_mode` (2), `minor` (2)
- `twinx`: `delta_zorder` (2), `foo` (1), `axes_class` (1)
- `axis`: `ymin` (1), `ymax` (1), `xmin` (1), `xmax` (1)
- `pcolor`: `colorizer` (3), `transform` (1)
- `get_title`: `loc` (4)
- `ylabel`: `size` (1), `fontproperties` (1), `family` (1), `color` (1)
- `set_xticks`: `rotation_mode` (2), `fontweight` (1)
- `get_tightbbox`: `for_layout_only` (2), `bbox_extra_artists` (1)
- `set_position`: `which` (3)
- `xlabel`: `usetex` (1), `size` (1), `fontproperties` (1)
- `figtext`: `usetex` (2), `c` (1)
- `supxlabel`: `weight` (1), `size` (1)
- `supylabel`: `weight` (1), `size` (1)
- `yticks`: `minor` (1)
- `twiny`: `foo` (1), `axes_class` (1)
- `MaxNLocator`: `symmetric` (1)
- `matshow`: `fignum` (1), `extent` (1)
- `semilogy`: `markeredgecolor` (1), `lw` (1)
- `polar`: `thetaunits` (1), `runits` (1)
- `set_layout_engine`: `pad` (1), `layout` (1)
- `set_xticklabels`: `fontweight` (1)
- `set_yticklabels`: `minor` (1)
- `indicate_inset`: `bounds` (1)
- `add_artist`: `clip` (1)
- `add_subfigure`: `facecolor` (1)
- `title`: `path_effects` (1)
- `indicate_inset_zoom`: `ec` (1)
