# Review: open tasks

Only open, actionable items remain. Fixed, documented and informational findings were removed; they are in git history (`git log -p review.md`).

Last measured state: Python suite 421 passed, 7 skipped; `ruff`, `cargo fmt`, `cargo clippy`, `cargo test` clean. Galleries: `mpl-corpus` 382/526 rendered (338 comparable, median 13.2% differing pixels, 35 above 50%); `mpl-examples` 343/507 rendered (53 needs API, 3 bugs, 106 unsupported).

## 1. Correctness: wrong output (do first)

| # | Task |
|---|------|
| B1b | **`boxplot` never draws outliers.** `Axes.boxplot` skips fliers when `sym is None` (`__init__.py`, near line 3391). `sym=None` must mean `"o"`; hide them only for `sym == ""` or `showfliers=False`. Flier face `none`, black 1 pt edge. Test: `boxplot(data)` returns fliers equal to the points beyond the whiskers and `get_ylim()` contains them. |
| B3 | **`violinplot` extends beyond the data.** `_kde` evaluates on `lo - 3·bw … hi + 3·bw`; Matplotlib uses `min … max`. Fix: `grid = np.linspace(lo, hi, points)`. Test: `get_ylim()` stays within the 5% margin of the data range. |
| G1 | **100 of 264 corpus comparisons still differ in size from the baseline** (metric is `None` there, yet the case counts as "rendered"). Remaining causes: `bbox_inches="tight"`/constrained cases, SVG/PDF baselines rasterised at another size, odd ratios. Fix and re-judge, or state in the gallery summary that "rendered" is not "matches". |
| F6 | **8 blank renders should draw:** `mandelbrot`, `hinton_demo`, `radar_chart`, `arrow_demo`, `font_table`, `figimage_demo` (figure-level `figimage` ignored), `shading_example` (`LightSource`), `style_sheets_reference`. Use the per-case `ignored` count to find the dropped call. Classify the 4 interactive blanks `unsupported`. Nothing flags them in CI today. |

## 2. Styling parity (Matplotlib defaults)

| # | Task |
|---|------|
| B2 | **Box styling.** Edge, whiskers, caps black 1.0 pt (with `patch_artist=True` face `C0`, edge black); median `C1` 1.5 pt; caps `0.5 × widths`. matplotvite uses the box colour and 1.5 pt everywhere and full-width caps. Fix the defaults in `Axes.boxplot`. |
| B4 | **Violin styling.** One body colour (`C0`, alpha 0.3) per call; extrema, bar, mean, median lines in the body colour at 1.5 pt. matplotvite cycles colours, draws opaque bodies and black lines. |
| B5 | **Rough violin edge** (thin spikes along the outline). Check with the SVG path and a higher `points`. |
| M9 | **Scatter markers.** Dense layers draw square pixel-aligned dots, so clouds look sparser. Draw anti-aliased discs of the right area (`s` in points²); keep the 4,096-point fast path. |
| M10 | **Axis labels and titles must reserve space.** `ylabel`/`xlabel` overlap tick labels (label offset ignores tick-label size). `add_axes` plot area is x=72..356 where Matplotlib has 40..360 (probe `add_axes_semantics`; needs Pillow to run). |
| M14 | **`hist(color="gray", alpha=0.4)`**: bars are darker and outlined; match alpha and edge colour. |
| M17 | Optional: `imshow(interpolation="antialiased")` and an rc switch (Matplotlib resamples when shrinking by more than 3×). `nearest` is the current deliberate default. |
| U2 | Cosmetic: legend frame radius is fixed at 6 px; scale it with `dpi`/`fontsize`. |
| U3 | Check that 8 target ticks do not crowd a 3×3 subplot grid. |

## 3. Verify in a fresh KARIOS render

0. **Regenerate the KARIOS images with the current build** (`/home/gautier/projects/isl/karios-matplotvite/docs/matplotvite`, still the 9 Nov renders) and re-judge every item below.

| # | What to check |
|---|---------------|
| M2 | `colorbar` with `hexbin`/`pcolormesh` mappables and `ticklocation`. |
| M3 | Colorbar label side (right), `ScalarFormatter` text (`8000`, not `8e+03`), Unicode minus. |
| M4 | Shared axes hide inner tick labels (`02_dx` top profile; `04_ce` right profile and bottom-right histogram). |
| M5 | `twinx` left/right axis sides in `02_dx`. |
| M7 | Minor grid lines absent; spine width 0.8 pt. |
| M11 | Text blocks: indentation, 1.2 line spacing, monospace, bbox. |
| M12 | DejaVu Sans sizes (titles 12 pt, suptitle 16 pt, ticks 10 pt); the bold `Reference`/`Monitored` heading looks like a title-weight bug. |

## 4. API gaps (`mpl-examples` / corpus, most cases first)

| # | Task |
|---|------|
| F2 | **`axes_grid1` / `axisartist` shims** (17 cases): `ImageGrid` (5), `Divider` (3), `make_axes_locatable` (2), `host_subplot` (2), `AxesGrid`, `axes_divider`, `anchored_artists`, `axes_rgb`, `parasite_axes`. `axisartist` (curvilinear/floating axes) is large: scope it out or make it its own milestone. |
| G3 | **`streamplot`** (9 corpus cases plus examples, broadest gap); `grouped_bar`, `withTickedStroke`, `NonUniformImage`, `BboxImage`, `Sankey`, `Axes.table`/`Table`, `ContourSet.legend_elements`, `Axes.set_thetagrids`/`set_rlabel_position` and polar setters, `matplotlib.image`/`matplotlib.scale` namespaces. 3-D (`plot_surface`, `plot_wireframe`, `voxels`, `set_zlabel`) is out of scope. |
| F3 | **`matplotlib.tri`:** `tri` module (6), `Triangulation` (3), `triplot`, `tricontour(f)`, `TriAnalyzer`. |
| F4 | `Figure.dpi_scale_trans` (3), `withTickedStroke` (3), `Sankey` (3), `LightSource` (2), `TextPath` (2), `logit` scale (2), `GridSpec.subplots` (2), `matplotvite.spines` (2), `matplotvite.units` (2), `ConciseDateFormatter` (2), `LineCollection._colorbar_spec` (2), `AsinhNorm`, `colors.rgb_to_hsv`, `AnchoredText`, `MouseEvent`, `_ColorbarAxes.yaxis`, `PathPatch.axes`, `_LegendHandle.get_lines`, `Text.set_picker`, `Manager.key_press_handler_id`. |
| E3 | Missing outright: `PercentFormatter`, `EngFormatter`, `AutoDateLocator`, `HandlerTuple`, `FontProperties`, `IdentityTransform`, `ScaledTranslation`, `TransformedBbox`, `TextPath`, `TextArea`. Check that `LogNorm` (aliased to `_Normalize`) is really logarithmic. `LogLocator` is still a no-op. |
| E5 | `Axes.set()` rejects unknown keywords; `Axes.twin()` takes no argument; module-level `polar`, `matshow`, `xkcd`, `get_data_path` missing. Add them or map to `unsupported`. |
| G4 | **Crashes where the feature exists** (triage each to a minimal reproduction; the first two groups hide the most): `NoneType - NoneType` (7), `third arg must be a format string` (4), `AffineND has no len()` (4), `'transform' must be a matplotlib Transform, not _CoordTransform` (4 examples, 2 corpus), `float() ... ContourSet` (2), `float() ... dict_keys` (2), `could not convert string to float: 'x'`/`'green'` (4), `linewidths must be a scalar or match the number of levels` (1), `unsupported interpolation: 'bessel'` (1), `fill expects (x, y) or (xN, yN, xN, yN)` (2 corpus), `blit=True` animation return (3), unit registry (`bar_unit_demo`, `ellipse_with_units`: `TaggedValue`). |

## 5. Harvester and gallery accounting

| # | Task |
|---|------|
| F0 | **Explain the 223 → 215 drop in `mpl-examples`.** Either the earlier run had Pillow/Matplotlib installed (numbers depend on the machine: print missing optional modules at the start of a run and record what CI uses) or a commit lost 8 cases. Diff `status` per case between runs. |
| F5 | Install Pillow in the gallery job (6 cases: `image_demo`, `image_clip_path`, `demo_annotation_box`, `demo_text_path`, `demo_ribbon_box`, `mathtext_asarray`). Mark `units/*` out of scope (needs `matplotlib.testing.jpl_units`). |
| E2 | `import matplotlib.X as alias` is not resolved for `mpatch`, `mscale`, `maxis`, `mcolorizer`, `dates`, `image`, `transforms`. Map to `matplotvite.X` when it exists; otherwise class as `needs-api`. Re-check how many `NameError`s remain. |
| E4 / G6 | Add a `reason` field to the manifest (`out_of_scope`, `harvester`, `needs_api`, `bug`) and print the four counts in `tools/gallery_summary.py` instead of one "failed" number. |
| G5 | Mark `gi` (9), `wx` (7), `user_interfaces` (25), `widgets` (16), `animation` (10) `unsupported` up front. Local runs lack `cairosvg` and `pypdfium2` (27 SVG/PDF baselines get no metrics): say so in the output. |
| F7 | "0 bugs" is not evidence: check the float-conversion and `_ListedColormap` cases were fixed and did not move into `needs-api`, and open three "rendered" examples by eye. |
| G7 / E6 | Tests: decorator parser reads `savefig_kwarg` dpi and `style`; a stripped `from matplotlib.ticker import MaxNLocator` and `import matplotlib.dates as mdates` bind; every `mpl-examples` failure carries a reason. |
| B6 | Tests: quiver pixel-length against a stored value; violin `get_ylim()` within data range; boxplot fliers exist (see B1b, B3). |

## 6. Simplification (ponytail audit)

Grep the tests before cutting; items 3 and 4 were not checked against them.

| # | Task |
|---|------|
| A1 | **Colormaps embedded twice** (`python/matplotvite/_cmaps.py` 3657 lines, `src/cmap_data.rs` 21193 lines). Keep the Rust table only; have `_CMAP_DATA` ask `_core` for the colours. Drops the Python table and its half of `tools/generate_colormaps.py`. |
| A2 | **`cmap_data.rs` writes one `[r, g, b],` per line.** Emit packed rows or `include_bytes!` a blob: about 21k lines become about 300. |
| A3 | **`mpl_toolkits` shim is 834 lines.** Keep `inset_locator` and `make_axes_locatable` if used; delete `axes_rgb`, `parasite_axes`, `axes_size`, `anchored_artists`, the `axisartist` stub. |
| A4 | **`_NoopLocator`, `_NoopFormatter`, `_NoopContext`** (`__init__.py:7025, 7309, 7474, 7770`): one `_Noop` class with `__getattr__` for the aliases that only avoid an `AttributeError`. |
| A5 | `usvg` and `tiny-skia` are direct deps but `resvg` re-exports both: use `resvg::usvg` and `resvg::tiny_skia`, drop them from `Cargo.toml:23-24`. |
| A6 | `plotters-backend` is used in one file (`scale.rs:7`); `plotters::backend` re-exports it: drop the crate. |
| A7 | **Status is duplicated** across `review.md`, `ROADMAP.md`, `TRACE.md`, `architecture.md`. Keep one status file; generate `TRACE.md` and `trace_baseline.json` into `dist/` instead of committing them. |
| A8 | `tools/benchmark_guard.py` and `tools/criterion_guard.py` run with `--warn-only` in CI: delete, or make them fail and keep one. |
| A9 | `tools/security_audit.py` only wraps `cargo audit`, `bandit`, `pip-audit`; call them from `prek.toml` and `ci.yml` unless it is the single place that sets their flags. |
| A10 | `tools/harvest_seaborn.py` (206 lines) repeats `harvest_matplotlib.py`: make it a `--source seaborn` option. |

Expected gain: about -25,000 lines (mostly generated), about -1,500 hand-written, 3 dependencies.

## 7. CI and supply chain

- Make the Rust build and tests a required check on Dependabot PRs (a bad `pdf-writer` bump merged unbuilt). Keep the tight-PDF tests as the gate for `svg2pdf`/`usvg` updates.
- Optional: `--require-hashes` for the CI constraints.
- Keep the Matplotlib (3.11.2) and seaborn (v0.13.2) pins; harvested snippets run in-process.
- Re-run `cargo audit` when `rustybuzz` or `ttf-parser` publish replacements (RUSTSEC-2026-0206, -0192).
