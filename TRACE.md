# matplotlib test-suite coverage trace

91 test files scanned. Static AST scan, counts are call sites.

Call sites supported: **9602/10098** (95%)

## Priority gaps

Unsupported call sites sorted by how often matplotlib's own tests use them.

| calls | API | files |
|--:|---|---:|
| 23 | `Axes.format_coord` | 2 |
| 22 | `pyplot.imread` | 6 |
| 16 | `Axes.get_cursor_data` | 2 |
| 16 | `Axes.contains` | 6 |
| 15 | `Axes.tripcolor` | 2 |
| 15 | `Axes.table` | 1 |
| 14 | `Figure.get_linewidth` | 6 |
| 13 | `pyplot.streamplot` | 2 |
| 12 | `Axes.format_cursor_data` | 2 |
| 10 | `pyplot.switch_backend` | 3 |
| 10 | `Figure.set_edgecolor` | 4 |
| 8 | `pyplot.imsave` | 1 |
| 8 | `pyplot.fignum_exists` | 2 |
| 8 | `Figure.supylabel` | 2 |
| 8 | `Axes.get_navigate_mode` | 1 |
| 7 | `pyplot.tricontourf` | 2 |
| 7 | `pyplot.polar` | 2 |
| 7 | `Figure.supxlabel` | 2 |
| 7 | `Axes.tricontourf` | 3 |
| 7 | `Axes.tricontour` | 3 |
| 7 | `Axes.streamplot` | 3 |
| 7 | `Axes.set_figure` | 2 |
| 7 | `Axes.get_autoscaley_on` | 2 |
| 7 | `Axes.get_autoscalex_on` | 2 |
| 6 | `pyplot.clabel` | 2 |

## pyplot: unsupported (by call count)

| calls | name | files |
|--:|---|--:|
| 22 | `imread` | 6 |
| 13 | `streamplot` | 2 |
| 10 | `switch_backend` | 3 |
| 8 | `imsave` | 1 |
| 8 | `fignum_exists` | 2 |
| 7 | `tricontourf` | 2 |
| 7 | `polar` | 2 |
| 6 | `clabel` | 2 |
| 5 | `get_fignums` | 2 |
| 4 | `tricontour` | 2 |
| 4 | `table` | 2 |
| 4 | `box` | 1 |
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
| 2 | `FormatStrFormatter` | 1 |
| 1 | `twinx` | 1 |
| 1 | `get_backend` | 1 |
| 1 | `figimage` | 1 |
| 1 | `draw_if_interactive` | 1 |
| 1 | `autoscale` | 1 |
| 1 | `FuncFormatter` | 1 |

pyplot supported: `subplots`, `figure`, `subplot`, `plot`, `gca`, `axes`, `close`, `colorbar`, `legend`, `scatter`, `text`, `draw`, `contourf`, `rc`, `savefig`, `gcf`, `subplot_mosaic`, `contour`, `pcolor`, `tight_layout`, `hist`, `ion`, `ioff`, `axis`, `title`, `rc_context`, `quiver`, `pie`, `pause`, `show`, `setp`, `pcolormesh`, `imshow`, `errorbar`, `ylim`, `xticks`, `xlim`, `subplot2grid`, `Circle`, `figtext`, `Rectangle`, `xlabel`, `subplots_adjust`, `bar`, `ylabel`, `xkcd`, `stairs`, `getp`, `figaspect`, `Line2D`, `suptitle`, `get_cmap`, `FixedLocator`, `yticks`, `fill_between`, `eventplot`, `MultipleLocator`, `FixedFormatter`, `yscale`, `xscale`, `violinplot`, `stem`, `stackplot`, `set_cmap`, `matshow`, `fill`, `boxplot`, `axline`, `annotate`, `MaxNLocator`, `LinearLocator`

## Axes: unsupported (by call count)

| calls | name | files |
|--:|---|--:|
| 23 | `format_coord` | 2 |
| 16 | `get_cursor_data` | 2 |
| 16 | `contains` | 6 |
| 15 | `tripcolor` | 2 |
| 15 | `table` | 1 |
| 12 | `format_cursor_data` | 2 |
| 8 | `get_navigate_mode` | 1 |
| 7 | `tricontourf` | 3 |
| 7 | `tricontour` | 3 |
| 7 | `streamplot` | 3 |
| 7 | `set_figure` | 2 |
| 7 | `get_autoscaley_on` | 2 |
| 7 | `get_autoscalex_on` | 2 |
| 6 | `violin` | 2 |
| 6 | `csd` | 2 |
| 6 | `contains_point` | 3 |
| 6 | `arrow` | 3 |
| 5 | `triplot` | 2 |
| 5 | `set_url` | 1 |
| 5 | `draw_artist` | 3 |
| 4 | `spy` | 2 |
| 4 | `set_ybound` | 1 |
| 4 | `set_xbound` | 1 |
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
| 3 | `add_image` | 1 |
| 2 | `update_from` | 2 |
| 2 | `sharey` | 1 |
| 2 | `sharex` | 1 |
| 2 | `set_gid` | 1 |
| 2 | `set_clip_box` | 2 |
| 2 | `set_agg_filter` | 2 |
| 2 | `properties` | 2 |
| 2 | `pchanged` | 1 |
| 2 | `indicate_inset_zoom` | 2 |
| 2 | `indicate_inset` | 1 |
| 2 | `get_animated` | 1 |
| 2 | `get_anchor` | 1 |
| 2 | `ecdf` | 1 |
| 2 | `drag_pan` | 1 |
| 2 | `acorr` | 1 |
| 1 | `yaxis_date` | 1 |
| 1 | `ticklabel_format` | 1 |
| 1 | `set_sketch_params` | 1 |
| 1 | `set_rasterization_zorder` | 1 |
| 1 | `set_picker` | 1 |
| 1 | `set_animated` | 1 |
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
| 1 | `get_axisbelow` | 1 |
| 1 | `format_ydata` | 1 |
| 1 | `format_xdata` | 1 |
| 1 | `findobj` | 1 |
| 1 | `cohere` | 1 |
| 1 | `angle_spectrum` | 1 |

Axes supported: `plot`, `imshow`, `text`, `draw`, `set_xlim`, `legend`, `set_ylim`, `scatter`, `set_title`, `get_position`, `add_patch`, `get_ylim`, `get_xlim`, `pcolormesh`, `set`, `errorbar`, `bar`, `hist`, `get_visible`, `remove`, `add_artist`, `get_window_extent`, `get_facecolor`, `set_xlabel`, `contour`, `set_yscale`, `boxplot`, `annotate`, `tick_params`, `set_ylabel`, `set_xticks`, `violinplot`, `set_xscale`, `set_aspect`, `update`, `set_yticks`, `get_transform`, `axis`, `add_collection`, `set_prop_cycle`, `get_xticklabels`, `stem`, `set_axis_off`, `contourf`, `axhline`, `twinx`, `stairs`, `fill_between`, `set_visible`, `set_facecolor`, `get_alpha`, `set_position`, `grid`, `barh`, `pie`, `clear`, `get_tightbbox`, `bar_label`, `psd`, `hexbin`, `axline`, `hlines`, `get_figure`, `clabel`, `set_alpha`, `axvline`, `vlines`, `fill`, `quiverkey`, `quiver`, `margins`, `get_yticklabels`, `get_label`, `eventplot`, `minorticks_on`, `inset_axes`, `get_yticks`, `set_clip_path`, `pcolorfast`, `get_subplotspec`, `autoscale`, `specgram`, `set_label`, `get_zorder`, `twiny`, `get_title`, `step`, `stackplot`, `set_path_effects`, `loglog`, `get_ybound`, `axvspan`, `set_xticklabels`, `get_children`, `broken_barh`, `secondary_xaxis`, `invert_yaxis`, `grouped_bar`, `get_xticks`, `get_xbound`, `set_zorder`, `relim`, `pcolor`, `get_gridspec`, `fill_betweenx`, `cla`, `barbs`, `yaxis_inverted`, `set_yticklabels`, `set_box_aspect`, `get_aspect`, `axhspan`, `autoscale_view`, `add_line`, `invert_xaxis`, `get_ylabel`, `semilogx`, `minorticks_off`, `hist2d`, `get_legend_handles_labels`, `pie_label`, `locator_params`, `get_yscale`, `xaxis_inverted`, `set_in_layout`, `semilogy`, `label_outer`, `get_xlabel`, `get_frame_on`, `get_forward_navigation_events`, `get_yaxis_transform`, `get_xscale`, `get_xaxis_transform`, `set_frame_on`, `set_clip_on`, `set_autoscale_on`, `secondary_yaxis`, `matshow`, `magnitude_spectrum`, `get_legend`, `get_in_layout`, `bxp`, `set_xmargin`, `set_forward_navigation_events`, `set_axisbelow`, `set_autoscaley_on`, `set_autoscalex_on`, `set_anchor`, `set_adjustable`, `get_box_aspect`, `get_adjustable`

## Figure: unsupported (by call count)

| calls | name | files |
|--:|---|--:|
| 14 | `get_linewidth` | 6 |
| 10 | `set_edgecolor` | 4 |
| 8 | `supylabel` | 2 |
| 7 | `supxlabel` | 2 |
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

Figure supported: `add_subplot`, `subplots`, `savefig`, `colorbar`, `draw_without_rendering`, `add_axes`, `suptitle`, `get_edgecolor`, `subfigures`, `subplots_adjust`, `tight_layout`, `add_gridspec`, `subplot_mosaic`, `set_size_inches`, `gca`, `get_layout_engine`, `set_layout_engine`, `add_subfigure`, `figimage`, `get_size_inches`, `get_constrained_layout`, `autofmt_xdate`, `get_tight_layout`, `set_constrained_layout`, `get_axes`, `set_tight_layout`, `get_dpi`

## Unsupported kwargs on supported calls

- `savefig`: `metadata` (12), `pil_kwargs` (6), `backend` (5), `papertype` (3), `orientation` (2), `non_existent_kwarg` (1)
- `table`: `loc` (16), `cellText` (15), `rowLabels` (10), `colLabels` (10), `zorder` (2), `rowColours` (2), `colColours` (2), `bbox` (2), `fontsize` (1), `edges` (1), `colWidths` (1), `cellColours` (1)
- `streamplot`: `linewidth` (7), `start_points` (5), `density` (5), `color` (5), `maxlength` (3), `num_arrows` (2), `integration_max_step_scale` (2), `integration_max_error_scale` (2), `cmap` (2), `broken_streamlines` (2), `transform` (1), `integration_direction` (1), `arrowsize` (1)
- `csd`: `NFFT` (5), `pad_to` (3), `noverlap` (3), `Fs` (3), `y` (2), `x` (2), `sides` (2)
- `imsave`: `format` (8), `pil_kwargs` (2), `dpi` (2), `origin` (1)
- `tripcolor`: `facecolors` (6), `shading` (3), `edgecolors` (2), `clim` (1), `C` (1)
- `violin`: `widths` (5), `positions` (5), `orientation` (1)
- `arrow`: `head_length` (3), `width` (2), `head_width` (2), `shape` (1), `length_includes_head` (1), `head_starts_at_zero` (1)
- `tricontour`: `levels` (4), `colorizer` (2), `linewidths` (1), `colors` (1), `cmap` (1)
- `set_label`: `ha` (3), `x` (2), `loc` (2), `y` (1)
- `get_window_extent`: `dpi` (1)
- `ecdf`: `orientation` (2), `ls` (1), `data` (1), `compress` (1), `complementary` (1)
- `triplot`: `color` (2), `lw` (1), `ls` (1), `linestyle` (1), `label` (1)
- `tricontourf`: `levels` (3), `colorizer` (2)
- `get_title`: `loc` (4)
- `set_position`: `which` (3)
- `set_sketch_params`: `scale` (1), `randomness` (1), `length` (1)
- `supxlabel`: `x` (1), `weight` (1), `size` (1)
- `supylabel`: `y` (1), `weight` (1), `size` (1)
- `cohere`: `noverlap` (1), `NFFT` (1), `Fs` (1)
- `acorr`: `maxlags` (2)
- `spy`: `origin` (1), `marker` (1)
- `set_xbound`: `upper` (1), `lower` (1)
- `set_ybound`: `upper` (1), `lower` (1)
- `imread`: `format` (2)
- `polar`: `thetaunits` (1), `runits` (1)
- `indicate_inset`: `bounds` (1)
- `add_artist`: `clip` (1)
- `ticklabel_format`: `scilimits` (1)
- `angle_spectrum`: `sides` (1)
- `phase_spectrum`: `sides` (1)
- `findobj`: `include_self` (1)
- `add_callback`: `flush` (1)
- `align_ylabels`: `axs` (1)
- `waitforbuttonpress`: `timeout` (1)
- `indicate_inset_zoom`: `ec` (1)
