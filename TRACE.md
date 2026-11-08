# matplotlib test-suite coverage trace

91 test files scanned. Static AST scan, counts are call sites.

Call sites supported: **9254/10098** (91%)

## Priority gaps

Unsupported call sites sorted by how often matplotlib's own tests use them.

| calls | API | files |
|--:|---|---:|
| 39 | `Figure.subfigures` | 15 |
| 23 | `Axes.psd` | 2 |
| 23 | `Axes.format_coord` | 2 |
| 22 | `pyplot.imread` | 6 |
| 21 | `Axes.clabel` | 3 |
| 18 | `Axes.quiverkey` | 1 |
| 16 | `Axes.inset_axes` | 6 |
| 16 | `Axes.get_cursor_data` | 2 |
| 16 | `Axes.contains` | 6 |
| 15 | `Axes.tripcolor` | 2 |
| 15 | `Axes.table` | 1 |
| 15 | `Axes.get_subplotspec` | 4 |
| 14 | `Figure.get_linewidth` | 6 |
| 14 | `Axes.specgram` | 2 |
| 13 | `pyplot.streamplot` | 2 |
| 13 | `Figure.add_subfigure` | 2 |
| 12 | `Axes.format_cursor_data` | 2 |
| 10 | `pyplot.switch_backend` | 3 |
| 10 | `Figure.set_edgecolor` | 4 |
| 10 | `Axes.secondary_xaxis` | 2 |
| 10 | `Axes.grouped_bar` | 1 |
| 9 | `Figure.figimage` | 4 |
| 9 | `Axes.get_gridspec` | 2 |
| 9 | `Axes.barbs` | 4 |
| 8 | `pyplot.imsave` | 1 |

## pyplot: unsupported (by call count)

| calls | name | files |
|--:|---|--:|
| 22 | `imread` | 6 |
| 13 | `streamplot` | 2 |
| 10 | `switch_backend` | 3 |
| 8 | `imsave` | 1 |
| 8 | `fignum_exists` | 2 |
| 7 | `tricontourf` | 2 |
| 7 | `subplot2grid` | 2 |
| 7 | `polar` | 2 |
| 7 | `Circle` | 2 |
| 6 | `figtext` | 3 |
| 6 | `clabel` | 2 |
| 6 | `Rectangle` | 3 |
| 5 | `get_fignums` | 2 |
| 4 | `xkcd` | 2 |
| 4 | `tricontour` | 2 |
| 4 | `table` | 2 |
| 4 | `figaspect` | 1 |
| 4 | `box` | 1 |
| 4 | `Line2D` | 1 |
| 3 | `FixedLocator` | 1 |
| 2 | `triplot` | 1 |
| 2 | `tripcolor` | 1 |
| 2 | `specgram` | 1 |
| 2 | `sca` | 2 |
| 2 | `get_figlabels` | 1 |
| 2 | `ecdf` | 1 |
| 2 | `draw_all` | 1 |
| 2 | `barbs` | 2 |
| 2 | `NullLocator` | 1 |
| 2 | `Normalize` | 2 |
| 2 | `MultipleLocator` | 1 |
| 2 | `FormatStrFormatter` | 1 |
| 2 | `FixedFormatter` | 1 |
| 1 | `twinx` | 1 |
| 1 | `matshow` | 1 |
| 1 | `get_backend` | 1 |
| 1 | `figimage` | 1 |
| 1 | `draw_if_interactive` | 1 |
| 1 | `autoscale` | 1 |
| 1 | `MaxNLocator` | 1 |
| 1 | `LinearLocator` | 1 |
| 1 | `FuncFormatter` | 1 |

pyplot supported: `subplots`, `figure`, `subplot`, `plot`, `gca`, `axes`, `close`, `colorbar`, `legend`, `scatter`, `text`, `draw`, `contourf`, `rc`, `savefig`, `gcf`, `subplot_mosaic`, `contour`, `pcolor`, `tight_layout`, `hist`, `ion`, `ioff`, `axis`, `title`, `rc_context`, `quiver`, `pie`, `pause`, `show`, `setp`, `pcolormesh`, `imshow`, `errorbar`, `ylim`, `xticks`, `xlim`, `xlabel`, `subplots_adjust`, `bar`, `ylabel`, `stairs`, `getp`, `suptitle`, `get_cmap`, `yticks`, `fill_between`, `eventplot`, `yscale`, `xscale`, `violinplot`, `stem`, `stackplot`, `set_cmap`, `fill`, `boxplot`, `axline`, `annotate`

## Axes: unsupported (by call count)

| calls | name | files |
|--:|---|--:|
| 23 | `psd` | 2 |
| 23 | `format_coord` | 2 |
| 21 | `clabel` | 3 |
| 18 | `quiverkey` | 1 |
| 16 | `inset_axes` | 6 |
| 16 | `get_cursor_data` | 2 |
| 16 | `contains` | 6 |
| 15 | `tripcolor` | 2 |
| 15 | `table` | 1 |
| 15 | `get_subplotspec` | 4 |
| 14 | `specgram` | 2 |
| 12 | `format_cursor_data` | 2 |
| 10 | `secondary_xaxis` | 2 |
| 10 | `grouped_bar` | 1 |
| 9 | `get_gridspec` | 2 |
| 9 | `barbs` | 4 |
| 8 | `set_box_aspect` | 4 |
| 8 | `get_navigate_mode` | 1 |
| 7 | `tricontourf` | 3 |
| 7 | `tricontour` | 3 |
| 7 | `streamplot` | 3 |
| 7 | `set_figure` | 2 |
| 7 | `get_autoscaley_on` | 2 |
| 7 | `get_autoscalex_on` | 2 |
| 6 | `violin` | 2 |
| 6 | `get_legend_handles_labels` | 3 |
| 6 | `csd` | 2 |
| 6 | `contains_point` | 3 |
| 6 | `arrow` | 3 |
| 5 | `triplot` | 2 |
| 5 | `set_url` | 1 |
| 5 | `pie_label` | 2 |
| 5 | `locator_params` | 3 |
| 5 | `draw_artist` | 3 |
| 4 | `spy` | 2 |
| 4 | `set_ybound` | 1 |
| 4 | `set_xbound` | 1 |
| 4 | `set_rasterized` | 4 |
| 4 | `label_outer` | 1 |
| 4 | `get_frame_on` | 1 |
| 4 | `get_forward_navigation_events` | 1 |
| 4 | `add_callback` | 2 |
| 3 | `xaxis_date` | 2 |
| 3 | `start_pan` | 1 |
| 3 | `set_transform` | 3 |
| 3 | `is_transform_set` | 1 |
| 3 | `get_yaxis_transform` | 2 |
| 3 | `get_xaxis_transform` | 1 |
| 3 | `get_navigate` | 1 |
| 3 | `get_lines` | 1 |
| 3 | `get_autoscale_on` | 1 |
| 3 | `end_pan` | 1 |
| 3 | `apply_aspect` | 1 |
| 3 | `add_image` | 1 |
| 2 | `update_from` | 2 |
| 2 | `sharey` | 1 |
| 2 | `sharex` | 1 |
| 2 | `set_gid` | 1 |
| 2 | `set_frame_on` | 2 |
| 2 | `set_clip_box` | 2 |
| 2 | `set_autoscale_on` | 1 |
| 2 | `set_agg_filter` | 2 |
| 2 | `secondary_yaxis` | 1 |
| 2 | `properties` | 2 |
| 2 | `pchanged` | 1 |
| 2 | `matshow` | 2 |
| 2 | `magnitude_spectrum` | 1 |
| 2 | `indicate_inset_zoom` | 2 |
| 2 | `indicate_inset` | 1 |
| 2 | `get_legend` | 1 |
| 2 | `get_animated` | 1 |
| 2 | `get_anchor` | 1 |
| 2 | `ecdf` | 1 |
| 2 | `drag_pan` | 1 |
| 2 | `bxp` | 2 |
| 2 | `acorr` | 1 |
| 1 | `yaxis_date` | 1 |
| 1 | `ticklabel_format` | 1 |
| 1 | `set_xmargin` | 1 |
| 1 | `set_sketch_params` | 1 |
| 1 | `set_rasterization_zorder` | 1 |
| 1 | `set_picker` | 1 |
| 1 | `set_forward_navigation_events` | 1 |
| 1 | `set_axisbelow` | 1 |
| 1 | `set_autoscaley_on` | 1 |
| 1 | `set_autoscalex_on` | 1 |
| 1 | `set_animated` | 1 |
| 1 | `set_anchor` | 1 |
| 1 | `set_adjustable` | 1 |
| 1 | `remove_callback` | 1 |
| 1 | `redraw_in_frame` | 1 |
| 1 | `pick` | 1 |
| 1 | `phase_spectrum` | 1 |
| 1 | `get_ymargin` | 1 |
| 1 | `get_xmargin` | 1 |
| 1 | `get_xgridlines` | 1 |
| 1 | `get_path_effects` | 1 |
| 1 | `get_images` | 1 |
| 1 | `get_clip_path` | 1 |
| 1 | `get_box_aspect` | 1 |
| 1 | `get_axisbelow` | 1 |
| 1 | `get_adjustable` | 1 |
| 1 | `format_ydata` | 1 |
| 1 | `format_xdata` | 1 |
| 1 | `findobj` | 1 |
| 1 | `cohere` | 1 |
| 1 | `angle_spectrum` | 1 |

Axes supported: `plot`, `imshow`, `text`, `draw`, `set_xlim`, `legend`, `set_ylim`, `scatter`, `set_title`, `get_position`, `add_patch`, `get_ylim`, `get_xlim`, `pcolormesh`, `set`, `errorbar`, `bar`, `hist`, `get_visible`, `remove`, `add_artist`, `get_window_extent`, `get_facecolor`, `set_xlabel`, `contour`, `set_yscale`, `boxplot`, `annotate`, `tick_params`, `set_ylabel`, `set_xticks`, `violinplot`, `set_xscale`, `set_aspect`, `update`, `set_yticks`, `get_transform`, `axis`, `add_collection`, `set_prop_cycle`, `get_xticklabels`, `stem`, `set_axis_off`, `contourf`, `axhline`, `twinx`, `stairs`, `fill_between`, `set_visible`, `set_facecolor`, `get_alpha`, `set_position`, `grid`, `barh`, `pie`, `clear`, `get_tightbbox`, `bar_label`, `hexbin`, `axline`, `hlines`, `get_figure`, `set_alpha`, `axvline`, `vlines`, `fill`, `quiver`, `margins`, `get_yticklabels`, `get_label`, `eventplot`, `minorticks_on`, `get_yticks`, `set_clip_path`, `pcolorfast`, `autoscale`, `set_label`, `get_zorder`, `twiny`, `get_title`, `step`, `stackplot`, `set_path_effects`, `loglog`, `get_ybound`, `axvspan`, `set_xticklabels`, `get_children`, `broken_barh`, `invert_yaxis`, `get_xticks`, `get_xbound`, `set_zorder`, `relim`, `pcolor`, `fill_betweenx`, `cla`, `yaxis_inverted`, `set_yticklabels`, `get_aspect`, `axhspan`, `autoscale_view`, `add_line`, `invert_xaxis`, `get_ylabel`, `semilogx`, `minorticks_off`, `hist2d`, `get_yscale`, `xaxis_inverted`, `set_in_layout`, `semilogy`, `get_xlabel`, `get_xscale`, `set_clip_on`, `get_in_layout`

## Figure: unsupported (by call count)

| calls | name | files |
|--:|---|--:|
| 39 | `subfigures` | 15 |
| 14 | `get_linewidth` | 6 |
| 13 | `add_subfigure` | 2 |
| 10 | `set_edgecolor` | 4 |
| 9 | `figimage` | 4 |
| 8 | `supylabel` | 2 |
| 7 | `supxlabel` | 2 |
| 7 | `get_constrained_layout` | 2 |
| 7 | `autofmt_xdate` | 3 |
| 6 | `get_tight_layout` | 2 |
| 5 | `set_constrained_layout` | 1 |
| 4 | `set_tight_layout` | 1 |
| 4 | `align_ylabels` | 3 |
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
| 2 | `align_xlabels` | 1 |
| 1 | `set_dpi` | 1 |
| 1 | `sca` | 1 |
| 1 | `get_constrained_layout_pads` | 1 |
| 1 | `delaxes` | 1 |
| 1 | `clf` | 1 |
| 1 | `align_titles` | 1 |
| 1 | `align_labels` | 1 |

Figure supported: `add_subplot`, `subplots`, `savefig`, `colorbar`, `draw_without_rendering`, `add_axes`, `suptitle`, `get_edgecolor`, `subplots_adjust`, `tight_layout`, `add_gridspec`, `subplot_mosaic`, `set_size_inches`, `gca`, `get_layout_engine`, `set_layout_engine`, `get_size_inches`, `get_axes`, `get_dpi`

## Unsupported kwargs on supported calls

- `text`: `horizontalalignment` (31), `verticalalignment` (30), `size` (17), `wrap` (15), `usetex` (15), `rotation` (15), `math_fontfamily` (9), `font` (9), `family` (9), `bbox` (7), `antialiased` (6), `alpha` (6), `fontproperties` (5), `clip_on` (5), `url` (4), `style` (3), `rotation_mode` (3), `linespacing` (3), `language` (3), `weight` (2)
- `imshow`: `norm` (39), `interpolation_stage` (20), `transform` (10), `colorizer` (3), `clip_path` (3), `clip_on` (2), `rasterized` (1), `data` (1), `clim` (1), `animated` (1)
- `colorbar`: `orientation` (33), `shrink` (27), `extend` (25), `location` (22), `cax` (17), `use_gridspec` (15), `pad` (12), `aspect` (10), `panchor` (6), `anchor` (6), `spacing` (4), `ticks` (3), `fraction` (2), `format` (2), `extendfrac` (2), `boundaries` (2), `ticklocation` (1), `extendrect` (1)
- `savefig`: `metadata` (12), `pil_kwargs` (6), `backend` (5), `papertype` (3), `pad_inches` (3), `orientation` (2), `non_existent_kwarg` (1)
- `annotate`: `xycoords` (26), `textcoords` (22), `va` (7), `fontproperties` (5), `clip_on` (3), `verticalalignment` (2), `size` (2), `horizontalalignment` (2), `ha` (2), `path_effects` (1), `clip_path` (1), `bbox` (1), `annotation_clip` (1)
- `psd`: `noverlap` (22), `NFFT` (22), `Fs` (22), `sides` (21), `x` (19), `window` (15), `pad_to` (11), `detrend` (6), `scale_by_freq` (5)
- `specgram`: `Fs` (13), `NFFT` (12), `sides` (11), `pad_to` (11), `noverlap` (11), `mode` (7), `x` (6), `scale` (4), `norm` (2), `origin` (1)
- `contourf`: `extend` (11), `algorithm` (6), `hatches` (5), `corner_mask` (5), `norm` (4), `locator` (3), `colorizer` (3), `transform` (2), `vmin` (1), `vmax` (1), `rasterized` (1), `clip_path` (1)
- `contour`: `linestyles` (7), `extend` (4), `negative_linestyles` (3), `colorizer` (3), `zorder` (1), `norm` (1), `linestyle` (1), `corner_mask` (1), `color` (1), `clip_path` (1), `algorithm` (1), `Z` (1)
- `table`: `loc` (16), `cellText` (15), `rowLabels` (10), `colLabels` (10), `zorder` (2), `rowColours` (2), `colColours` (2), `bbox` (2), `fontsize` (1), `edges` (1), `colWidths` (1), `cellColours` (1)
- `quiverkey`: `labelpos` (8), `label` (8), `coordinates` (7), `color` (7), `angle` (5), `fontproperties` (3), `zorder` (2), `Y` (2), `X` (2), `U` (2)
- `streamplot`: `linewidth` (7), `start_points` (5), `density` (5), `color` (5), `maxlength` (3), `num_arrows` (2), `integration_max_step_scale` (2), `integration_max_error_scale` (2), `cmap` (2), `broken_streamlines` (2), `transform` (1), `integration_direction` (1), `arrowsize` (1)
- `clabel`: `fontsize` (10), `inline` (8), `manual` (6), `use_clabeltext` (2), `fmt` (2), `colors` (2), `zorder` (1), `levels` (1), `inline_spacing` (1)
- `set_xlim`: `right` (9), `left` (9), `xmin` (1), `xmax` (1), `auto` (1)
- `csd`: `NFFT` (5), `pad_to` (3), `noverlap` (3), `Fs` (3), `y` (2), `x` (2), `sides` (2)
- `Circle`: `gid` (6), `transform` (5), `zorder` (3), `facecolor` (3), `clip_on` (2), `alpha` (1)
- `grouped_bar`: `tick_labels` (8), `labels` (5), `positions` (1), `hatch` (1), `group_spacing` (1), `colors` (1), `bar_spacing` (1)
- `barbs`: `transform` (3), `sizes` (3), `rounding` (3), `fill_empty` (3), `pivot` (2), `length` (2), `flip_barb` (1), `cmap` (1)
- `Rectangle`: `hatch` (5), `label` (4), `fill` (3), `edgecolor` (2), `color` (1), `alpha` (1)
- `set_ylim`: `bottom` (6), `top` (5), `ymin` (2), `ymax` (2)
- `figimage`: `yo` (4), `xo` (4), `origin` (4), `colorizer` (2), `resize` (1)
- `get_position`: `original` (14)
- `subfigures`: `wspace` (3), `nrows` (2), `ncols` (2), `height_ratios` (2), `width_ratios` (1), `squeeze` (1), `label` (1), `hspace` (1)
- `imsave`: `format` (8), `pil_kwargs` (2), `dpi` (2), `origin` (1)
- `tripcolor`: `facecolors` (6), `shading` (3), `edgecolors` (2), `clim` (1), `C` (1)
- `get_figure`: `root` (11)
- `violin`: `widths` (5), `positions` (5), `orientation` (1)
- `arrow`: `head_length` (3), `width` (2), `head_width` (2), `shape` (1), `length_includes_head` (1), `head_starts_at_zero` (1)
- `tricontour`: `levels` (4), `colorizer` (2), `linewidths` (1), `colors` (1), `cmap` (1)
- `set_label`: `ha` (3), `x` (2), `loc` (2), `y` (1)
- `subplot2grid`: `colspan` (4), `rowspan` (3), `fig` (1)
- `secondary_xaxis`: `functions` (4), `xticks` (1), `transform` (1), `color` (1)
- `get_window_extent`: `dpi` (1)
- `inset_axes`: `ylim` (1), `xlim` (1), `sharey` (1), `projection` (1), `polar` (1), `axes_class` (1)
- `ecdf`: `orientation` (2), `ls` (1), `data` (1), `compress` (1), `complementary` (1)
- `Line2D`: `gid` (3), `zorder` (1), `transform` (1), `label` (1)
- `triplot`: `color` (2), `lw` (1), `ls` (1), `linestyle` (1), `label` (1)
- `locator_params`: `nbins` (5)
- `tricontourf`: `levels` (3), `colorizer` (2)
- `twinx`: `delta_zorder` (2), `foo` (1), `axes_class` (1)
- `get_title`: `loc` (4)
- `pie_label`: `rotate` (1), `distance` (1), `alignment` (1)
- `get_tightbbox`: `for_layout_only` (2), `bbox_extra_artists` (1)
- `set_position`: `which` (3)
- `magnitude_spectrum`: `sides` (2), `scale` (1)
- `set_sketch_params`: `scale` (1), `randomness` (1), `length` (1)
- `figtext`: `usetex` (2), `c` (1)
- `supxlabel`: `x` (1), `weight` (1), `size` (1)
- `supylabel`: `y` (1), `weight` (1), `size` (1)
- `cohere`: `noverlap` (1), `NFFT` (1), `Fs` (1)
- `acorr`: `maxlags` (2)
- `spy`: `origin` (1), `marker` (1)
- `set_xbound`: `upper` (1), `lower` (1)
- `set_ybound`: `upper` (1), `lower` (1)
- `twiny`: `foo` (1), `axes_class` (1)
- `MaxNLocator`: `symmetric` (1), `nbins` (1)
- `matshow`: `fignum` (1), `extent` (1)
- `imread`: `format` (2)
- `polar`: `thetaunits` (1), `runits` (1)
- `indicate_inset`: `bounds` (1)
- `secondary_yaxis`: `yticks` (1)
- `add_artist`: `clip` (1)
- `ticklabel_format`: `scilimits` (1)
- `angle_spectrum`: `sides` (1)
- `phase_spectrum`: `sides` (1)
- `findobj`: `include_self` (1)
- `add_callback`: `flush` (1)
- `align_ylabels`: `axs` (1)
- `bxp`: `orientation` (1)
- `add_subfigure`: `facecolor` (1)
- `waitforbuttonpress`: `timeout` (1)
- `indicate_inset_zoom`: `ec` (1)
- `label_outer`: `remove_inner_ticks` (1)
