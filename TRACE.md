# matplotlib test-suite coverage trace

91 test files scanned. Static AST scan, counts are call sites.

Call sites supported: **4951/10098** (49%)

## pyplot: unsupported (by call count)

| calls | name | files |
|--:|---|--:|
| 77 | `axes` | 13 |
| 42 | `colorbar` | 10 |
| 30 | `scatter` | 8 |
| 26 | `draw` | 10 |
| 26 | `contourf` | 3 |
| 25 | `rc` | 6 |
| 22 | `imread` | 6 |
| 17 | `subplot_mosaic` | 4 |
| 17 | `contour` | 3 |
| 15 | `pcolor` | 5 |
| 13 | `tight_layout` | 3 |
| 13 | `streamplot` | 2 |
| 12 | `hist` | 2 |
| 11 | `ion` | 1 |
| 11 | `ioff` | 1 |
| 11 | `axis` | 2 |
| 10 | `switch_backend` | 3 |
| 10 | `rc_context` | 7 |
| 10 | `quiver` | 4 |
| 10 | `pie` | 1 |
| 10 | `pause` | 2 |
| 9 | `show` | 4 |
| 9 | `setp` | 6 |
| 9 | `pcolormesh` | 4 |
| 8 | `imsave` | 1 |
| 8 | `fignum_exists` | 2 |
| 8 | `errorbar` | 4 |
| 7 | `xticks` | 3 |
| 7 | `tricontourf` | 2 |
| 7 | `subplot2grid` | 2 |
| 7 | `polar` | 2 |
| 7 | `Circle` | 2 |
| 6 | `figtext` | 3 |
| 6 | `clabel` | 2 |
| 6 | `Rectangle` | 3 |
| 5 | `subplots_adjust` | 4 |
| 5 | `get_fignums` | 2 |
| 5 | `bar` | 4 |
| 4 | `xkcd` | 2 |
| 4 | `tricontour` | 2 |
| 4 | `table` | 2 |
| 4 | `stairs` | 1 |
| 4 | `getp` | 2 |
| 4 | `figaspect` | 1 |
| 4 | `box` | 1 |
| 4 | `Line2D` | 1 |
| 3 | `suptitle` | 3 |
| 3 | `get_cmap` | 3 |
| 3 | `FixedLocator` | 1 |
| 2 | `yticks` | 2 |
| 2 | `triplot` | 1 |
| 2 | `tripcolor` | 1 |
| 2 | `specgram` | 1 |
| 2 | `sca` | 2 |
| 2 | `get_figlabels` | 1 |
| 2 | `fill_between` | 2 |
| 2 | `eventplot` | 1 |
| 2 | `ecdf` | 1 |
| 2 | `draw_all` | 1 |
| 2 | `barbs` | 2 |
| 2 | `NullLocator` | 1 |
| 2 | `Normalize` | 2 |
| 2 | `MultipleLocator` | 1 |
| 2 | `FormatStrFormatter` | 1 |
| 2 | `FixedFormatter` | 1 |
| 1 | `yscale` | 1 |
| 1 | `xscale` | 1 |
| 1 | `violinplot` | 1 |
| 1 | `twinx` | 1 |
| 1 | `stem` | 1 |
| 1 | `stackplot` | 1 |
| 1 | `set_cmap` | 1 |
| 1 | `matshow` | 1 |
| 1 | `get_backend` | 1 |
| 1 | `fill` | 1 |
| 1 | `figimage` | 1 |
| 1 | `draw_if_interactive` | 1 |
| 1 | `boxplot` | 1 |
| 1 | `axline` | 1 |
| 1 | `autoscale` | 1 |
| 1 | `MaxNLocator` | 1 |
| 1 | `LinearLocator` | 1 |
| 1 | `FuncFormatter` | 1 |

pyplot supported: `subplots`, `figure`, `subplot`, `plot`, `gca`, `close`, `legend`, `text`, `savefig`, `gcf`, `title`, `imshow`, `ylim`, `xlim`, `xlabel`, `ylabel`, `annotate`

## Axes: unsupported (by call count)

| calls | name | files |
|--:|---|--:|
| 208 | `draw` | 37 |
| 176 | `scatter` | 21 |
| 130 | `get_position` | 10 |
| 108 | `add_patch` | 16 |
| 103 | `get_ylim` | 12 |
| 100 | `get_xlim` | 10 |
| 96 | `pcolormesh` | 11 |
| 95 | `set` | 27 |
| 82 | `errorbar` | 7 |
| 81 | `bar` | 13 |
| 74 | `hist` | 8 |
| 72 | `get_visible` | 8 |
| 67 | `remove` | 19 |
| 66 | `add_artist` | 15 |
| 64 | `get_window_extent` | 10 |
| 63 | `get_facecolor` | 10 |
| 59 | `contour` | 7 |
| 51 | `set_yscale` | 13 |
| 48 | `boxplot` | 4 |
| 47 | `tick_params` | 9 |
| 42 | `set_xticks` | 11 |
| 41 | `violinplot` | 2 |
| 40 | `set_xscale` | 8 |
| 35 | `update` | 17 |
| 35 | `set_yticks` | 11 |
| 35 | `get_transform` | 14 |
| 35 | `axis` | 10 |
| 35 | `add_collection` | 8 |
| 34 | `set_prop_cycle` | 3 |
| 34 | `get_xticklabels` | 8 |
| 33 | `stem` | 3 |
| 32 | `set_axis_off` | 9 |
| 32 | `contourf` | 7 |
| 32 | `axhline` | 10 |
| 31 | `twinx` | 7 |
| 31 | `stairs` | 2 |
| 31 | `fill_between` | 6 |
| 30 | `set_visible` | 13 |
| 30 | `set_facecolor` | 11 |
| 30 | `get_alpha` | 7 |
| 29 | `set_position` | 6 |
| 28 | `grid` | 11 |
| 28 | `barh` | 4 |
| 26 | `pie` | 2 |
| 25 | `clear` | 12 |
| 24 | `get_tightbbox` | 6 |
| 24 | `bar_label` | 3 |
| 23 | `psd` | 2 |
| 23 | `format_coord` | 2 |
| 22 | `hexbin` | 3 |
| 22 | `axline` | 3 |
| 21 | `hlines` | 3 |
| 21 | `get_figure` | 8 |
| 21 | `clabel` | 3 |
| 20 | `set_alpha` | 7 |
| 20 | `axvline` | 11 |
| 19 | `vlines` | 4 |
| 19 | `fill` | 4 |
| 18 | `quiverkey` | 1 |
| 18 | `quiver` | 4 |
| 18 | `margins` | 3 |
| 18 | `get_yticklabels` | 6 |
| 17 | `get_label` | 4 |
| 17 | `eventplot` | 2 |
| 16 | `minorticks_on` | 3 |
| 16 | `inset_axes` | 6 |
| 16 | `get_yticks` | 5 |
| 16 | `get_cursor_data` | 2 |
| 16 | `contains` | 6 |
| 15 | `tripcolor` | 2 |
| 15 | `table` | 1 |
| 15 | `set_clip_path` | 6 |
| 15 | `pcolorfast` | 4 |
| 15 | `get_subplotspec` | 4 |
| 15 | `autoscale` | 4 |
| 14 | `specgram` | 2 |
| 14 | `set_label` | 3 |
| 14 | `get_zorder` | 6 |
| 13 | `twiny` | 4 |
| 13 | `get_title` | 2 |
| 12 | `step` | 3 |
| 12 | `stackplot` | 3 |
| 12 | `set_path_effects` | 2 |
| 12 | `loglog` | 2 |
| 12 | `get_ybound` | 2 |
| 12 | `format_cursor_data` | 2 |
| 12 | `axvspan` | 5 |
| 11 | `set_xticklabels` | 4 |
| 11 | `get_children` | 5 |
| 11 | `broken_barh` | 2 |
| 10 | `secondary_xaxis` | 2 |
| 10 | `invert_yaxis` | 3 |
| 10 | `grouped_bar` | 1 |
| 10 | `get_xticks` | 2 |
| 10 | `get_xbound` | 2 |
| 9 | `set_zorder` | 5 |
| 9 | `relim` | 2 |
| 9 | `pcolor` | 5 |
| 9 | `get_gridspec` | 2 |
| 9 | `fill_betweenx` | 2 |
| 9 | `cla` | 1 |
| 9 | `barbs` | 4 |
| 8 | `yaxis_inverted` | 1 |
| 8 | `set_yticklabels` | 4 |
| 8 | `set_box_aspect` | 4 |
| 8 | `get_navigate_mode` | 1 |
| 8 | `axhspan` | 3 |
| 8 | `autoscale_view` | 4 |
| 8 | `add_line` | 1 |
| 7 | `tricontourf` | 3 |
| 7 | `tricontour` | 3 |
| 7 | `streamplot` | 3 |
| 7 | `set_figure` | 2 |
| 7 | `invert_xaxis` | 3 |
| 7 | `get_ylabel` | 3 |
| 7 | `get_autoscaley_on` | 2 |
| 7 | `get_autoscalex_on` | 2 |
| 6 | `violin` | 2 |
| 6 | `semilogx` | 3 |
| 6 | `minorticks_off` | 2 |
| 6 | `hist2d` | 2 |
| 6 | `get_legend_handles_labels` | 3 |
| 6 | `csd` | 2 |
| 6 | `contains_point` | 3 |
| 6 | `arrow` | 3 |
| 5 | `triplot` | 2 |
| 5 | `set_url` | 1 |
| 5 | `pie_label` | 2 |
| 5 | `locator_params` | 3 |
| 5 | `get_yscale` | 2 |
| 5 | `draw_artist` | 3 |
| 4 | `xaxis_inverted` | 1 |
| 4 | `spy` | 2 |
| 4 | `set_ybound` | 1 |
| 4 | `set_xbound` | 1 |
| 4 | `set_rasterized` | 4 |
| 4 | `set_in_layout` | 2 |
| 4 | `semilogy` | 3 |
| 4 | `label_outer` | 1 |
| 4 | `get_xlabel` | 3 |
| 4 | `get_frame_on` | 1 |
| 4 | `get_forward_navigation_events` | 1 |
| 4 | `add_callback` | 2 |
| 3 | `xaxis_date` | 2 |
| 3 | `start_pan` | 1 |
| 3 | `set_transform` | 3 |
| 3 | `is_transform_set` | 1 |
| 3 | `get_yaxis_transform` | 2 |
| 3 | `get_xscale` | 2 |
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
| 2 | `set_clip_on` | 1 |
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
| 2 | `get_in_layout` | 1 |
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

Axes supported: `plot`, `imshow`, `text`, `set_xlim`, `legend`, `set_ylim`, `set_title`, `set_xlabel`, `annotate`, `set_ylabel`, `set_aspect`, `get_aspect`

## Figure: unsupported (by call count)

| calls | name | files |
|--:|---|--:|
| 121 | `colorbar` | 11 |
| 102 | `draw_without_rendering` | 19 |
| 66 | `add_axes` | 19 |
| 47 | `suptitle` | 10 |
| 45 | `get_edgecolor` | 6 |
| 39 | `subfigures` | 15 |
| 26 | `subplots_adjust` | 10 |
| 20 | `tight_layout` | 6 |
| 20 | `add_gridspec` | 4 |
| 19 | `subplot_mosaic` | 2 |
| 19 | `set_size_inches` | 8 |
| 18 | `get_layout_engine` | 3 |
| 15 | `set_layout_engine` | 3 |
| 14 | `get_linewidth` | 6 |
| 13 | `add_subfigure` | 2 |
| 10 | `set_edgecolor` | 4 |
| 9 | `figimage` | 4 |
| 8 | `supylabel` | 2 |
| 7 | `supxlabel` | 2 |
| 7 | `get_size_inches` | 4 |
| 7 | `get_constrained_layout` | 2 |
| 7 | `autofmt_xdate` | 3 |
| 6 | `get_tight_layout` | 2 |
| 5 | `set_constrained_layout` | 1 |
| 5 | `get_axes` | 3 |
| 4 | `set_tight_layout` | 1 |
| 4 | `get_dpi` | 1 |
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

Figure supported: `add_subplot`, `subplots`, `savefig`, `gca`

## Unsupported kwargs on supported calls

- `plot`: `lw` (44), `marker` (35), `c` (33), `rasterized` (22), `ms` (17), `markevery` (17), `markersize` (17), `mfc` (16), `zorder` (14), `linestyle` (14), `markerfacecolor` (13), `transform` (12), `mec` (12), `data` (12), `markeredgecolor` (10), `ls` (10), `alpha` (10), `drawstyle` (9), `linewidth` (8), `markeredgewidth` (7)
- `subplots`: `layout` (65), `sharex` (50), `sharey` (42), `subplot_kw` (23), `constrained_layout` (19), `dpi` (16), `gridspec_kw` (6), `squeeze` (5), `width_ratios` (4), `tight_layout` (4), `num` (4), `clear` (2), `height_ratios` (1)
- `scatter`: `c` (84), `s` (69), `marker` (48), `label` (38), `color` (16), `edgecolor` (11), `cmap` (10), `facecolor` (8), `transform` (6), `linewidths` (6), `edgecolors` (6), `ec` (6), `alpha` (5), `fc` (4), `y` (3), `x` (3), `colorizer` (3), `plotnonfinite` (2), `picker` (2), `norm` (2)
- `text`: `horizontalalignment` (31), `verticalalignment` (30), `size` (17), `wrap` (15), `usetex` (15), `rotation` (15), `math_fontfamily` (9), `font` (9), `family` (9), `transform` (8), `bbox` (7), `antialiased` (6), `alpha` (6), `fontproperties` (5), `clip_on` (5), `url` (4), `style` (3), `rotation_mode` (3), `linespacing` (3), `language` (3)
- `imshow`: `norm` (39), `interpolation_stage` (20), `transform` (10), `colorizer` (3), `clip_path` (3), `clip_on` (2), `rasterized` (1), `data` (1), `clim` (1), `animated` (1)
- `colorbar`: `ax` (78), `orientation` (33), `shrink` (27), `extend` (25), `location` (22), `cax` (17), `use_gridspec` (15), `pad` (12), `aspect` (10), `panchor` (6), `anchor` (6), `label` (5), `spacing` (4), `ticks` (3), `fraction` (2), `format` (2), `extendfrac` (2), `boundaries` (2), `ticklocation` (1), `extendrect` (1)
- `errorbar`: `yerr` (62), `xerr` (37), `fmt` (30), `y` (14), `x` (14), `capsize` (12), `color` (10), `c` (10), `marker` (9), `ls` (9), `label` (8), `errorevery` (8), `uplims` (4), `lolims` (4), `ecolor` (4), `mfc` (3), `markevery` (3), `xuplims` (2), `xlolims` (2), `ms` (2)
- `legend`: `loc` (76), `labelcolor` (39), `labels` (35), `title` (13), `shadow` (8), `bbox_to_anchor` (8), `handles` (6), `title_fontproperties` (5), `numpoints` (5), `ncols` (5), `mode` (4), `title_fontsize` (2), `reverse` (2), `linewidth` (2), `handler_map` (2), `handlelength` (2), `draggable` (2), `ncol` (1), `markerfirst` (1), `handleheight` (1)
- `savefig`: `metadata` (12), `pil_kwargs` (6), `backend` (5), `facecolor` (4), `papertype` (3), `pad_inches` (3), `orientation` (2), `edgecolor` (2), `non_existent_kwarg` (1)
- `set`: `ylim` (41), `xlim` (41), `xlabel` (12), `ylabel` (9), `xscale` (9), `yscale` (6), `yticks` (5), `path_effects` (5), `h_pad` (5), `xticks` (4), `w_pad` (4), `aspect` (3), `yticklabels` (2), `xticklabels` (2), `wspace` (2), `rect` (2), `lw` (2), `linewidth` (2), `hspace` (2), `adjustable` (2)
- `annotate`: `xycoords` (26), `textcoords` (22), `va` (7), `fontproperties` (5), `clip_on` (3), `verticalalignment` (2), `size` (2), `horizontalalignment` (2), `ha` (2), `path_effects` (1), `clip_path` (1), `bbox` (1), `annotation_clip` (1)
- `hist`: `histtype` (39), `label` (23), `bins` (23), `stacked` (13), `color` (11), `ec` (9), `weights` (7), `bottom` (6), `fc` (5), `density` (5), `range` (4), `log` (3), `alpha` (3), `zorder` (1), `orientation` (1), `fill` (1), `data` (1), `align` (1)
- `figure`: `layout` (23), `dpi` (16), `constrained_layout` (5), `num` (3), `frameon` (2), `clear` (2)
- `psd`: `noverlap` (22), `NFFT` (22), `Fs` (22), `sides` (21), `x` (19), `window` (15), `pad_to` (11), `detrend` (6), `scale_by_freq` (5)
- `pie`: `labels` (18), `explode` (18), `startangle` (17), `autopct` (17), `shadow` (16), `colors` (16), `wedgeprops` (12), `center` (4), `textprops` (3), `frame` (3), `x` (2), `rotatelabels` (2), `radius` (2), `normalize` (2), `labeldistance` (2), `hatch` (2), `data` (2), `counterclock` (1)
- `tick_params`: `axis` (18), `direction` (12), `which` (11), `labelleft` (10), `labelbottom` (9), `bottom` (6), `length` (5), `left` (5), `labeltop` (5), `top` (4), `labelsize` (4), `width` (3), `rotation` (3), `right` (3), `labelrotation` (3), `labelright` (3), `labelcolor` (3), `colors` (3), `tick2On` (2), `tick1On` (2)
- `violinplot`: `positions` (22), `showmedians` (17), `showmeans` (17), `showextrema` (17), `orientation` (11), `quantiles` (7), `points` (4), `facecolor` (4), `linecolor` (3), `side` (2), `widths` (1), `vert` (1), `data` (1)
- `bar`: `align` (15), `width` (12), `bottom` (11), `color` (9), `label` (8), `height` (7), `edgecolor` (7), `x` (6), `yerr` (5), `tick_label` (4), `antialiased` (4), `hatch` (2), `facecolor` (2), `alpha` (2), `zorder` (1), `xerr` (1), `data` (1), `capsize` (1)
- `add_subplot`: `projection` (48), `polar` (5), `xticks` (4), `facecolor` (3), `axes_class` (3), `aspect` (3), `yticks` (2), `yscale` (2), `xticklabels` (2), `xscale` (2), `sharey` (2), `sharex` (2), `zorder` (1), `ylim` (1), `xlim` (1), `autoscale_on` (1), `anchor` (1)
- `pcolormesh`: `shading` (23), `cmap` (12), `vmin` (8), `vmax` (8), `norm` (7), `zorder` (5), `lw` (4), `edgecolors` (4), `alpha` (4), `transform` (2), `snap` (2), `rasterized` (2), `colorizer` (2)
- `specgram`: `Fs` (13), `NFFT` (12), `sides` (11), `pad_to` (11), `noverlap` (11), `mode` (7), `x` (6), `scale` (4), `norm` (2), `origin` (1)
- `contourf`: `levels` (21), `extend` (11), `algorithm` (6), `hatches` (5), `corner_mask` (5), `cmap` (5), `norm` (4), `colors` (4), `locator` (3), `colorizer` (3), `transform` (2), `vmin` (1), `vmax` (1), `rasterized` (1), `clip_path` (1)
- `stairs`: `baseline` (14), `fill` (12), `ls` (8), `label` (8), `color` (8), `orientation` (7), `lw` (5), `edges` (3), `hatch` (1), `facecolor` (1)
- `contour`: `colors` (19), `levels` (16), `linestyles` (7), `linewidths` (4), `extend` (4), `negative_linestyles` (3), `colorizer` (3), `zorder` (1), `norm` (1), `linestyle` (1), `corner_mask` (1), `color` (1), `clip_path` (1), `alpha` (1), `algorithm` (1), `Z` (1)
- `table`: `loc` (16), `cellText` (15), `rowLabels` (10), `colLabels` (10), `zorder` (2), `rowColours` (2), `colColours` (2), `bbox` (2), `fontsize` (1), `edges` (1), `colWidths` (1), `cellColours` (1)
- `subplots_adjust`: `left` (16), `bottom` (14), `top` (12), `right` (10), `hspace` (7), `wspace` (2)
- `fill_between`: `facecolor` (11), `alpha` (8), `where` (7), `hatch` (7), `color` (7), `interpolate` (6), `label` (5), `edgecolor` (3), `step` (2), `lw` (2), `data` (2), `transform` (1)
- `boxplot`: `positions` (7), `capwidths` (7), `bootstrap` (7), `widths` (6), `notch` (6), `sym` (4), `label` (4), `usermedians` (3), `conf_intervals` (3), `orientation` (2), `medianprops` (2), `zorder` (1), `tick_labels` (1), `showmeans` (1), `showbox` (1), `patch_artist` (1), `manage_ticks` (1), `data` (1), `autorange` (1)
- `axhline`: `color` (17), `lw` (7), `linewidth` (6), `xmin` (5), `xmax` (5), `zorder` (4), `y` (4), `alpha` (2), `c` (1)
- `hlines`: `xmin` (9), `xmax` (9), `colors` (8), `linewidth` (7), `lw` (4), `color` (4), `y` (3), `ls` (2), `transform` (1), `linestyle` (1)
- `quiverkey`: `labelpos` (8), `label` (8), `coordinates` (7), `color` (7), `angle` (5), `fontproperties` (3), `zorder` (2), `Y` (2), `X` (2), `U` (2)
- `hexbin`: `gridsize` (8), `extent` (7), `reduce_C_function` (4), `bins` (4), `yscale` (2), `vmin` (2), `vmax` (2), `mincnt` (2), `marginals` (2), `edgecolors` (2), `colorizer` (2), `C` (2), `xscale` (1), `picker` (1), `norm` (1), `data` (1)
- `vlines`: `linewidth` (8), `colors` (8), `ymin` (4), `ymax` (4), `lw` (4), `color` (4), `x` (3), `ls` (2), `linestyle` (2), `transform` (1), `gapcolor` (1), `alpha` (1)
- `barh`: `left` (11), `height` (11), `width` (6), `align` (5), `y` (4), `yerr` (1), `tick_label` (1), `label` (1)
- `subplot`: `projection` (22), `polar` (5), `theta_offset` (3), `sharey` (2), `anchor` (2), `sharex` (1), `aspect` (1)
- `streamplot`: `linewidth` (7), `start_points` (5), `density` (5), `color` (5), `maxlength` (3), `num_arrows` (2), `integration_max_step_scale` (2), `integration_max_error_scale` (2), `cmap` (2), `broken_streamlines` (2), `transform` (1), `integration_direction` (1), `arrowsize` (1)
- `set_title`: `loc` (16), `fontsize` (9), `pad` (5), `fontweight` (5), `y` (1)
- `stem`: `markerfmt` (11), `linefmt` (8), `bottom` (7), `orientation` (4), `basefmt` (3), `label` (1)
- `clabel`: `fontsize` (10), `inline` (8), `manual` (6), `use_clabeltext` (2), `fmt` (2), `colors` (2), `zorder` (1), `levels` (1), `inline_spacing` (1)
- `rc`: `size` (12), `fonttype` (10), `family` (7), `prop_cycle` (1), `linewidth` (1), `id` (1)
- `axline`: `slope` (14), `color` (10), `transform` (7), `c` (1)
- `eventplot`: `colors` (7), `lineoffsets` (6), `linelengths` (4), `alpha` (4), `linewidths` (1), `linewidth` (1), `linestyles` (1), `linestyle` (1), `label` (1), `data` (1), `color` (1)
- `axvline`: `color` (8), `ymin` (3), `ymax` (3), `lw` (3), `zorder` (2), `x` (2), `linewidth` (2), `linestyle` (1), `gapcolor` (1), `c` (1), `alpha` (1)
- `quiver`: `angles` (5), `scale_units` (3), `scale` (3), `pivot` (3), `width` (2), `units` (2), `transform` (2), `headlength` (2), `zorder` (1), `headwidth` (1), `headaxislength` (1), `color` (1)
- `subplot_mosaic`: `layout` (5), `subplot_kw` (4), `width_ratios` (3), `num` (3), `sharey` (2), `sharex` (2), `per_subplot_kw` (2), `height_ratios` (2), `gridspec_kw` (2), `clear` (1)
- `set_ylabel`: `loc` (7), `y` (5), `fontsize` (5), `ha` (4), `fontweight` (2), `fontname` (1)
- `add_axes`: `polar` (8), `projection` (3), `rect` (2), `label` (2), `yticks` (1), `ylim` (1), `xticks` (1), `sharex` (1), `frameon` (1), `autoscaley_on` (1), `autoscalex_on` (1), `autoscale_on` (1)
- `step`: `where` (6), `lw` (6), `linestyle` (6), `data` (3), `c` (2)
- `set_xlabel`: `loc` (7), `fontsize` (6), `x` (4), `ha` (3), `fontname` (1)
- `set_xlim`: `right` (9), `left` (9), `xmin` (1), `xmax` (1), `auto` (1)
- `axhspan`: `alpha` (7), `facecolor` (5), `ymin` (3), `ymax` (3), `fc` (2)
- `csd`: `NFFT` (5), `pad_to` (3), `noverlap` (3), `Fs` (3), `y` (2), `x` (2), `sides` (2)
- `Circle`: `gid` (6), `transform` (5), `zorder` (3), `facecolor` (3), `clip_on` (2), `alpha` (1)
- `axvspan`: `facecolor` (5), `alpha` (5), `xmin` (3), `xmax` (3), `fc` (2)
- `grouped_bar`: `tick_labels` (8), `labels` (5), `positions` (1), `hatch` (1), `group_spacing` (1), `colors` (1), `bar_spacing` (1)
- `barbs`: `transform` (3), `sizes` (3), `rounding` (3), `fill_empty` (3), `pivot` (2), `length` (2), `flip_barb` (1), `cmap` (1)
- `Rectangle`: `hatch` (5), `label` (4), `fill` (3), `edgecolor` (2), `color` (1), `alpha` (1)
- `fill`: `facecolor` (3), `zorder` (2), `lw` (2), `hatch` (2), `edgecolor` (2), `alpha` (2), `linewidth` (1), `ec` (1), `color` (1)
- `grid`: `color` (4), `which` (3), `linewidth` (3), `visible` (2), `linestyle` (2), `path_effects` (1), `alpha` (1)
- `set_prop_cycle`: `linewidth` (3), `color` (3), `lw` (2), `ls` (2), `c` (2), `marker` (1), `label` (1), `foobar` (1), `facecolor` (1)
- `suptitle`: `y` (3), `fontsize` (3), `color` (2), `x` (1), `wrap` (1), `weight` (1), `url` (1), `size` (1), `rotation` (1), `in_layout` (1), `fontproperties` (1)
- `set_ylim`: `bottom` (6), `top` (5), `ymin` (2), `ymax` (2)
- `figimage`: `yo` (4), `xo` (4), `origin` (4), `colorizer` (2), `resize` (1)
- `stackplot`: `colors` (4), `baseline` (4), `labels` (2), `hatch` (1), `facecolors` (1), `facecolor` (1), `data` (1)
- `get_position`: `original` (14)
- `subfigures`: `wspace` (3), `nrows` (2), `ncols` (2), `height_ratios` (2), `width_ratios` (1), `squeeze` (1), `label` (1), `hspace` (1)
- `bar_label`: `label_type` (4), `padding` (3), `fmt` (3), `labels` (2), `color` (1)
- `imsave`: `format` (8), `pil_kwargs` (2), `dpi` (2), `origin` (1)
- `tripcolor`: `facecolors` (6), `shading` (3), `edgecolors` (2), `clim` (1), `C` (1)
- `fill_betweenx`: `where` (2), `step` (2), `lw` (2), `interpolate` (2), `facecolor` (2), `alpha` (2)
- `get_figure`: `root` (11)
- `violin`: `widths` (5), `positions` (5), `orientation` (1)
- `arrow`: `head_length` (3), `width` (2), `head_width` (2), `shape` (1), `length_includes_head` (1), `head_starts_at_zero` (1)
- `autoscale`: `tight` (4), `enable` (3), `axis` (2)
- `tricontour`: `levels` (4), `colorizer` (2), `linewidths` (1), `colors` (1), `cmap` (1)
- `set_label`: `ha` (3), `x` (2), `loc` (2), `y` (1)
- `hist2d`: `rasterized` (3), `bins` (3), `density` (1), `data` (1)
- `axes`: `projection` (6), `position` (2)
- `set_yscale`: `nonpositive` (3), `base` (3), `subs` (1), `foo` (1)
- `subplot2grid`: `colspan` (4), `rowspan` (3), `fig` (1)
- `tight_layout`: `rect` (5), `h_pad` (2), `w_pad` (1)
- `secondary_xaxis`: `functions` (4), `xticks` (1), `transform` (1), `color` (1)
- `add_gridspec`: `nrows` (2), `ncols` (2), `wspace` (1), `left` (1), `figure` (1)
- `get_window_extent`: `renderer` (6), `dpi` (1)
- `setp`: `visible` (2), `remove_overlapping_locs` (1), `path_effects` (1), `file` (1), `color` (1)
- `set_xscale`: `base` (3), `nonpositive` (1), `linthresh` (1), `functions` (1)
- `loglog`: `lw` (4), `nonpositive` (1), `c` (1)
- `broken_barh`: `align` (4), `facecolors` (2)
- `inset_axes`: `ylim` (1), `xlim` (1), `sharey` (1), `projection` (1), `polar` (1), `axes_class` (1)
- `pcolorfast`: `colorizer` (6)
- `ecdf`: `orientation` (2), `ls` (1), `data` (1), `compress` (1), `complementary` (1)
- `Line2D`: `gid` (3), `zorder` (1), `transform` (1), `label` (1)
- `triplot`: `color` (2), `lw` (1), `ls` (1), `linestyle` (1), `label` (1)
- `locator_params`: `nbins` (5)
- `tricontourf`: `levels` (3), `colorizer` (2)
- `xticks`: `labels` (2), `rotation` (1), `minor` (1)
- `set_yticks`: `rotation_mode` (2), `minor` (2)
- `get_xticklabels`: `which` (4)
- `twinx`: `delta_zorder` (2), `foo` (1), `axes_class` (1)
- `axis`: `ymin` (1), `ymax` (1), `xmin` (1), `xmax` (1)
- `pcolor`: `colorizer` (3), `transform` (1)
- `get_title`: `loc` (4)
- `ylabel`: `size` (1), `fontproperties` (1), `family` (1), `color` (1)
- `show`: `block` (4)
- `pie_label`: `rotate` (1), `distance` (1), `alignment` (1)
- `set_xticks`: `rotation_mode` (2), `fontweight` (1)
- `get_yticklabels`: `which` (2), `minor` (1)
- `get_tightbbox`: `for_layout_only` (2), `bbox_extra_artists` (1)
- `set_position`: `which` (3)
- `rc_context`: `rc` (3)
- `magnitude_spectrum`: `sides` (2), `scale` (1)
- `xlabel`: `usetex` (1), `size` (1), `fontproperties` (1)
- `set_sketch_params`: `scale` (1), `randomness` (1), `length` (1)
- `figtext`: `usetex` (2), `c` (1)
- `supxlabel`: `x` (1), `weight` (1), `size` (1)
- `supylabel`: `y` (1), `weight` (1), `size` (1)
- `update`: `left` (2), `bottom` (1)
- `cohere`: `noverlap` (1), `NFFT` (1), `Fs` (1)
- `yticks`: `ticks` (1), `minor` (1), `labels` (1)
- `acorr`: `maxlags` (2)
- `spy`: `origin` (1), `marker` (1)
- `relim`: `visible_only` (2)
- `add_collection`: `autolim` (2)
- `margins`: `y` (1), `x` (1)
- `set_xbound`: `upper` (1), `lower` (1)
- `set_ybound`: `upper` (1), `lower` (1)
- `twiny`: `foo` (1), `axes_class` (1)
- `MaxNLocator`: `symmetric` (1), `nbins` (1)
- `matshow`: `fignum` (1), `extent` (1)
- `imread`: `format` (2)
- `semilogy`: `markeredgecolor` (1), `lw` (1)
- `polar`: `thetaunits` (1), `runits` (1)
- `set_layout_engine`: `pad` (1), `layout` (1)
- `draw`: `extra` (1)
- `set_xticklabels`: `fontweight` (1)
- `set_yticklabels`: `minor` (1)
- `indicate_inset`: `bounds` (1)
- `secondary_yaxis`: `yticks` (1)
- `add_artist`: `clip` (1)
- `ticklabel_format`: `scilimits` (1)
- `angle_spectrum`: `sides` (1)
- `phase_spectrum`: `sides` (1)
- `findobj`: `include_self` (1)
- `add_callback`: `flush` (1)
- `set_clip_path`: `transform` (1)
- `align_ylabels`: `axs` (1)
- `bxp`: `orientation` (1)
- `add_subfigure`: `facecolor` (1)
- `waitforbuttonpress`: `timeout` (1)
- `title`: `path_effects` (1)
- `get_yticks`: `minor` (1)
- `indicate_inset_zoom`: `ec` (1)
- `label_outer`: `remove_inner_ticks` (1)
