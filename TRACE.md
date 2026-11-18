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

- `set_label`: `ha` (3), `x` (2), `loc` (2), `y` (1)
- `get_window_extent`: `dpi` (1)
- `get_title`: `loc` (4)
- `get_tightbbox`: `for_layout_only` (2), `bbox_extra_artists` (1)
- `set_position`: `which` (3)
