# Review: performance, security and Matplotlib parity (open issues)

Scope: `main` after the tick-label, gallery-reference and release-workflow changes. Closed findings have been removed; this file lists what is still open. Galleries were regenerated on 14 Nov with the current build.

Results on this tree: Python suite 401 passed, 7 skipped; `ruff`, `cargo fmt`, `cargo clippy` and `cargo test` clean. The `mpl-examples` gallery now renders the original script with Matplotlib beside every Matplotvite output, and every comparison row has a collapsible source block, so failed and blank cases have a reference image.

| Gallery | Cases | Rendered | Blank | Failed / needs API | other |
|---------|-------|----------|-------|--------------------|-------|
| `mpl-corpus` (`@image_comparison`) | 526 | 368 | 5 | 127 failed | 26 unsupported |
| `mpl-examples` (gallery scripts) | 507 | 256 | 1 | 141 needs API | 0 harvester gaps, 3 bugs, 106 unsupported |

Of the 368 rendered corpus cases, 338 have a pixel metric and all 338 match the baseline's pixel dimensions. The median differing-pixel share is 13.2%; 35 are above 50%. Both gallery runs are current.

## High

| # | Finding | Evidence / next check |
|---|---------|-----------------------|
| F2 | **Remaining `axes_grid1` / `axisartist` shims.** `ImageGrid`, `make_axes_locatable`, the anchored artists, `axes_rgb` and the divider family now cover 17 of 23 gallery cases. Still missing: `host_subplot`/`parasite_axes`, `demo_edge_colorbar`/`demo_fixed_size_axes`, and `axisartist`. | Add `host_subplot`/`parasite_axes` and the remaining grid shims next; `axisartist` remains its own milestone. |

## Parity and visible styling

| # | Finding | Evidence / next check |
|---|---------|-----------------------|
| M2 | **Colorbar mappables remain partly checked.** Scatter collections and standalone `ScalarMappable` work, as does `cax=`. | Re-check `hexbin` and `pcolormesh` mappables and `ticklocation` in a render. |
| M3 | **Colorbar text and layout remain partly checked.** Ticks use round locator values. | Verify label side (right of the bar), `ScalarFormatter` text (`8000`, not `8e+03`) and the Unicode minus in a render. |
| M4 | **Shared axes may still show redundant labels.** `sharex`/`sharey` are supposed to hide inner tick labels; the probe passes, but the old renders showed labels overlapping neighbours in `02_dx` and `04_ce`. | Re-render both figures and confirm inner labels are hidden. |
| M5 | **Twin-axis sides remain partly checked.** `fill_between(color=...)` no longer advances the colour cycle. | Verify the `twinx` left/right axis sides in `02_dx`. |
| M11 | **Multiline text needs a spacing/indent check.** Leading whitespace and 1.2 line spacing were addressed, but the old `04_ce` block ran into the plot below. | Re-render `04_ce` and `02_dx`, check indentation, spacing and the `bbox` frame. |
| M12 | **Default font sizes need a render check.** DejaVu Sans is bundled and default; confirm title 12 pt, suptitle 16 pt and ticks 10 pt against Matplotlib. | Compare all four figures; a bold `Reference`/`Monitored` heading may still be a title-weight bug. |
| M17 | **`imshow` interpolation.** The default stays `nearest` deliberately; Matplotlib's `antialiased` resamples images shrunk by more than 3×. | Offer `interpolation="antialiased"` and an rc switch for byte-for-byte parity if needed. |

## API gaps and failures

| # | Finding |
|---|---------|
| G3 | **API gaps, most frequent first:** `streamplot` (broadest gap), `NonUniformImage`, `BboxImage`, `Sankey`, `Table`/`Axes.table`, `Axes.set_thetagrids`/`set_rlabel_position` and the polar-axis setters, `matplotlib.image`/`matplotlib.scale` when used. 3-D remains out of scope. |
| G4 | **Failures where the feature exists but crashes.** Remaining groups: `NoneType - NoneType` (7), `third arg must be a format string` (4), `AffineND has no len()` (4), real-Matplotlib transforms mixed with matplotvite transforms (4 examples, 2 corpus), `float() ... not 'ContourSet'` (2), `float() ... not 'dict_keys'` (2), string-to-float failures for `'x'`/`'green'` (4), `linewidths must ... match the number of levels` (1), `unsupported interpolation: 'bessel'` (1), `fill` argument forms (2 corpus), blit animation return type (3). |
| F4 | **Smaller gaps, 2–3 cases each:** `Figure.dpi_scale_trans`, `withTickedStroke`, `Sankey`, `LightSource`, `TextPath`, `logit` scale, `GridSpec.subplots`, `matplotvite.spines`, `matplotvite.units`, `ConciseDateFormatter`, `LineCollection._colorbar_spec`, `AsinhNorm`, `colors.rgb_to_hsv`, `AnchoredText`, `MouseEvent`, `_ColorbarAxes.yaxis`, `PathPatch.axes`, `_LegendHandle.get_lines`, `Text.set_picker`, `Manager.key_press_handler_id`. |
| F5 | **Environment cases:** install Pillow in the gallery job (`image_demo`, `image_clip_path`, `demo_annotation_box`, `demo_text_path`, `demo_ribbon_box`, `mathtext_asarray`); mark `units/*` out of scope because it needs `matplotlib.testing.jpl_units`. |
| E5 | **One-line API gaps:** `Axes.set()` rejects unknown keywords, `Axes.twin()` takes no argument, and `matplotvite.polar`, `matshow`, `xkcd`, `get_data_path` and `LogLocator` are missing at module level. |

## Accounting, tests and trust

| # | Finding |
|---|---------|
| G5 | **Environment accounting:** 9 examples need `gi` and 7 need `wx`; `user_interfaces` (25), `widgets` (16) and `animation` (10) are interactive by nature and should be `unsupported` up front. Local runs should also state when `cairosvg`/`pypdfium2` are missing, because SVG/PDF baselines then get no metric. |
| G6 / E4 | **Failure accounting still mixes causes.** Add a `reason` field (`out_of_scope`, `harvester`, `needs_api`, `bug`) to the `mpl-examples` manifest and print the four counts in `gallery_summary.py` instead of one "failed" number. |
| F7 / N7 | **"Rendered" is not proof of correctness.** It still includes ignored calls (see the per-case `ignored` count). Treat rendered counts as an upper bound and check the remaining float-conversion and `_ListedColormap` cases did not merely move into `needs-api`. |
| E6 | **Test gap:** no test checks that every `mpl-examples` failure carries a reason, or that a stripped `import matplotlib.dates as mdates` binds `mdates`. Add both to the gallery tests once E4 lands. |

## Watch items and residual risks

| # | Item |
|---|------|
| S6 | `cargo audit` has no vulnerabilities but two "unmaintained" warnings (`rustybuzz` RUSTSEC-2026-0206, `ttf-parser` RUSTSEC-2026-0192). Re-run when replacements are published. |
| X3 | PDF output is still assembled by hand from `svg2pdf::to_chunk` plus `pdf-writer`, with a usvg bounds workaround. Keep the tight-PDF tests as the upgrade gate; Dependabot only moves `pdf-writer` with `svg2pdf`. |
| N2 | Harvested snippets now run in a timeout-bound child interpreter with a scratch cwd, but still have filesystem and network access. Keep the Matplotlib `3.11.2` and seaborn `v0.13.2` pins and never point `--examples` at an unpinned checkout; a stronger sandbox remains optional hardening. |
| S5 | CI installs are constrained but not hash-pinned. `--require-hashes` is optional hardening. |
| P8 | SVG assembly builds the document once; the only `insert_str` is the optional root background. Keep the tight-bounds test as the gate when changing this path. |
| U3 | Tick count is now 8; check a 3×3 subplot grid for crowding. |

## Suggested order

1. **F2**: add the remaining `axes_grid1` shims, then tackle `axisartist`.
2. **G4 and G3**: triage the crash groups, then the remaining API gaps.
3. **G5/G6/E4/E6**: make the gallery numbers explain themselves and keep them honest.
4. Rebuild the KARIOS images, re-render the four pairs, and re-judge every "(image)" item listed above.
