# Review: performance, security and Matplotlib parity

Scope: `main` after the workspace split, Axes refactor and 0.7 corpus work.
Results on this tree: Python suite **590 passed, 5 skipped**;
`cargo test --workspace --all-targets` passes; `ruff`, `cargo fmt`,
`cargo clippy --workspace --all-targets -- -D warnings` and pre-commit are
clean.

| Gallery | Cases | Rendered | Blank | Failed / needs API | Other |
|---------|-------|----------|-------|--------------------|-------|
| `mpl-corpus` (`@image_comparison`) | 526 | 495 | 5 | 0 failed | 26 unsupported |
| `mpl-examples` (gallery scripts) | 507 | 389 | 4 | 0 failed, 0 needs API | 114 unsupported |

Both totals are from full runs on this tree. The 526-case corpus was rerun after
the projection, `imread`, and corpus compatibility fixes; the final sample-data
case was confirmed separately when its harness path was wired through.

## 0.7 delivery

| # | Finding |
|---|---------|
| V4 | **Done — corpus metadata is checked in.** `tests/mpl_corpus.json` holds all 526 Matplotlib 3.11.2 cases with rewritten snippets and SHA-256 hashes of every baseline image. `--write-metadata` refreshes it, `--check-metadata` fails CI on drift, and `--changed-from` renders only new or changed cases. |
| V5 | **Done — Seaborn wrapper parity has pixel diffs.** `tests/test_seaborn_parity.py` renders six shared scenes for `lineplot`, `scatterplot`, `barplot`, `histplot`, `boxplot` and `heatmap` and compares them with committed Matplotlib references using RGBA RMS tolerances. |
| V6 | **Done — pandas `.plot()` works through the backend hook.** `_pandas.py` implements `line`, `bar`, `barh`, `hist`, `box`, `area`, `scatter` and `pie`; datetime, categorical and MultiIndex indexes are covered, unknown kinds raise `ValueError`, and `docs/pandas.rst` documents the pandas 2.x/3.x matrix. |

## Corpus and coverage

| # | Finding |
|---|---------|
| V3 | **Done — rendered counts are labelled as an upper bound.** Both harvesters already record `ignored` per case; the CI gallery summary now shows an `Ignored calls` total for every gallery, the harvester stdout and examples page report the total, and the summary states that rendered/pass counts are not proof of visual parity. Per-case visual metrics remain in the manifests and artifact. |

## Rust crate preparation

Goal: a native Rust crate with the same matplotlib-like API. The API (`Figure`, `Axes`, artists, locators, norms; about 10k lines) still lives in Python.

| # | Task |
|---|------|
| R6 | **Done — workspace split.** `crates/matplotvite-core` owns the model, layout, draw, raster and export pipeline and has no Python dependency by default; its optional `python` feature only adds the PyO3 extraction traits. `crates/matplotvite` exposes the native `Figure::new`/`fig.subplot`/`ax.plot`/`fig.savefig` builder, and `crates/matplotvite-py` is the thin extension module. CI runs `cargo test -p matplotvite-core --no-default-features`, the non-Python coverage gate over both non-Python crates (reporting core sources only), and the fuzz target against the builder crate. |
| R7 | **Done — native builder covers the panel surface.** `api::Figure`/`Axes` render `plot`, `scatter`, `bar`, `barh`, `hist`, `imshow`, `imshow_cmap`, `fill_between`, `contour`/`contourf`, `errorbar`, `quiver`, `text`, `annotate`, patches (`rectangle`, `circle`, `polygon`), `line_collection` and `colorbar`. Axis configuration covers explicit ticks and labels, tick styling, linear/log/symlog/logit/asinh scales, grid and legend options, aspect/adjustable, `axis_off`, face/foreground and label colours, plus `add_axes` bounds. The API accepts slices and copies them into the renderer's owned panel records. Optional thread-local `pyplot` layer only if requested. |
| R8 | **Done — locators, norms and colormaps shared.** Python's `_auto_ticks` and `_auto_tick_target` call the Rust locator, and the duplicate `_round_ticks` implementation is gone. The norm classes (`Normalize`, `LogNorm`, `PowerNorm`, `SymLogNorm`, `AsinhNorm`, `TwoSlopeNorm`, `BoundaryNorm`) are `_core` pyclasses, and `Colormap` sampling, reversal, LUT resampling and custom registration run in Rust. Python keeps `_ListedColormap`/`_LinearSegmentedColormap` construction for user-supplied tables and the registry namespace. Date-specific `_nice_step` step lists remain Python-side. |
| R9 | **Done — shared golden-image test set.** `tests/golden/scenes.txt` names four scenes and their RMS tolerance; `tests/test_golden_images.py` renders them through the Python facade and `tests/golden.rs` through the native Rust builder, both against the committed PNGs. The scenes cover lines/legend, bars/scatter, images/colorbar and fills/annotations, and regeneration is documented in `tests/golden/README.md`. |

## Refactoring analysis (17 Nov)

Measured: `python/matplotvite/__init__.py` is 12.6k lines (1489 methods; `class Axes` alone spans ~3.6k lines, `Figure` ~3k); `src/draw.rs` was 2.9k lines when measured (about 2.3k now). Tasks complement R3/R4/R8 and do not repeat them.

| # | Task |
|---|------|
| Q1 | **Done — `__init__.py` is now a re-export facade.** The 12.9k-line implementation moved to `_plotting.py`, which the package imports and re-exports; `__init__.py` holds the public surface, satellite imports and compatibility delegation for private internals, and `__init__.pyi` is unchanged. The mutually dependent plotting core remains one module for Q2 to break into plotting/axes/figure modules. |
| Q2 | **Done — `Axes` is split by concern.** `_PlotAxes` owns plot/scatter/bar/hist and the other plot families, `_StatsAxes` owns box/whisker/violin summaries, `_FieldAxes` owns images/contours/quiver/hexbin, and `_DecorAxes` owns text, annotation, labels, legends and grid styling. The remaining `Axes` class owns lifecycle, layout, ticks, scales and panel assembly. `_panel` now delegates reference/polar data to `_panel_series` and tick resolution to `_panel_ticks`; `_apply_axis_scales` delegates points, geometry, artists and limits to focused helpers. The full Python suite passes (590 passed, 5 skipped). |
| Q6 | **Done — one tick path.** Every axis now goes through `draw_manual_ticks`: the plotters mesh draws only the frame and axis descriptions, with its grid and tick marks disabled and empty label formatters so it cannot duplicate labels. The `manual` heuristic and `TickStyle::is_custom` are gone, default panels match the previous mesh output pixel-for-pixel, and the grid width now follows `linewidth * dpi / 72` like the rest of the renderer. |
| Q8 | **Done — gallery and harvester tooling split.** `tools/gallery_render.py` owns sample rendering, timings, matplotlib comparisons, the scaling chart and `samples.json`; `tools/build_pages.py` only builds HTML from that data (`--html-only`), and the Pages workflow runs the render step as its own command. The Matplotlib harvester is split into `tools/mpl_harvest.py` (parsing and snippet rewriting), `tools/mpl_render.py` (isolated matplotvite/matplotlib rendering) and `tools/mpl_metrics.py` (pixel metrics and failure classification); `tools/harvest_matplotlib.py` keeps the gallery orchestration, CLI and compatibility re-exports. |

## Conformance and OSS practice audit (17 Nov)

Architecture is sound (Rust core, thin pyo3 adapter, abi3 wheels, SHA-pinned CI, dual licence, audit tooling, baselined benchmarks, no `unsafe`). Gaps are in the honesty of the coverage numbers, typing, release safety and project governance.

| # | Task |
|---|------|
| C14 | **Done — coverage and robustness.** `pytest-cov` enforces a 75% branch floor; the current suite measures **77.98% branch coverage** (the floor is not the reported total). `cargo-llvm-cov` enforces a 45% line floor on the renderer; the gate runs the core and builder test targets and reports core sources only, which measure **73.07% lines** (the crate's own unit tests alone reach **48.96% lines**, above the same floor). Proptest covers scale round-trips, tick ordering/bounds and polyline decimation; Hypothesis checks the Python scale/tick bindings. `fuzz/panel_render.rs` fuzzes the public panel/render path, and `fuzz/python/fuzz_panel_extraction.py` runs a live Python runtime against the real PyO3 dict extraction, either through atheris or the deterministic mutation loop that CI's tests exercise. |
| C15 | **Done — API docs and examples.** Sphinx autodoc builds `docs/` in CI and into `dist/api` on Pages, `tools/check_docstrings.py` gates all 101 public functions at 100% and every public class (99/99, against a 90% floor), and the `docs`/`test` extras cover those workflows. `examples/quickstart.py` is the runnable user entry point; the remaining files are gallery fixtures. |

## Re-audit and follow-up (23–24 Nov)

Scope: `main` at `a63ba1e`, continued on 24 Nov after the re-audit. The checks in
the header still pass, but the TRACE gate did not: `tools/trace_unsupported.py
--check` reported 9178 -> 9155 implemented call sites because the facade hid
lazily delegated names from `dir()`. No new security finding was found: the
canvas, image and bin limits and the SVG text-escaping test are in place. R14
and R15 then closed the remaining call-site gaps named by R11–R13.

| # | Task |
|---|------|
| R10 | **Done — facade introspection restores the TRACE gate.** `matplotvite.__getattr__` forwards names from `_plotting`, but `dir(matplotvite)` omitted 23 of them (`Line2D`, `Text`, `CirclePolygon`, `GridSpecFromSubplotSpec`, `Colorizer`, `figaspect`, `findfont`, `connect`, `from_levels_and_colors`, `grouped_bar`, `tricontour`, ...), so any tool that introspects the module saw them as missing. `__dir__` now unions the module globals with everything `_plotting` exposes (including the `typing`/`contextlib` names, which `matplotlib.pyplot` exposes too), `test_api_surface.py` guards the delegated callables, and the refreshed baseline drops the two non-Matplotlib leaks. `tools/trace_unsupported.py --check` passed at the then-current 9178/10098. |
| R11 | **Done — Figure state accessors.** The 15 missing `Figure` methods now exist: the size and DPI setters validate and feed the render size, `get/set_linewidth` and `set_edgecolor` update the figure state, `get_suptitle`/`get_supxlabel`/`get_supylabel` return the stored strings, `sca` sets the current axes, `get_constrained_layout_pads` reports the inactive layout, and `clf`/`delaxes` really clear or remove axes. TRACE implementation rises from 9178 to 9229 call sites; only the interactive `show`/`ginput`/`waitforbuttonpress` remain missing on `Figure`. |
| R12 | **Done — Axes state accessors.** The missing `Axes` state methods now store and return real state: autoscale flags, `navigate`, `gid`, `url`, rasterisation, animation, anchor, axisbelow, picker, clip box, aggregation filter, transform and its set flag, sketch params, callbacks, date flags, formatted x/y data, `get_lines`/`get_images`, `update_from`, `properties`, `pchanged`, `findobj`, `apply_aspect`, `draw_artist` and `set_figure`. TRACE implementation rises from 9229 to 9324 call sites; only the interactive pan handlers and the cursor/geometry items in R13 remain among the non-plotting gaps. |
| R13 | **Done — Axes hit-testing and cursor formatting.** `format_coord`, `format_cursor_data`, `contains` and `contains_point` now use the axes box in display coordinates and Matplotlib's `[%.3g]` cursor format; `get_cursor_data` returns the same `None` default as Matplotlib, so TRACE counts its 16 call sites as accepted rather than missing. The remaining `Axes` gaps are the interactive pan handlers, `violin`, the margin/gridline getters and `pick`; the workspace total is now 9381/10098 implemented with 69 missing. |
| R14 | **Done — the remaining Axes APIs.** `violin` draws from pre-computed `cbook.violin_stats` dictionaries (positions/widths validation, datetime position checks, vertical/horizontal orientation, `side`, bodies, means, extrema, medians and quantiles). `margins`/`set_xmargin`/`set_ymargin`/`get_xmargin`/`get_ymargin` store per-axis margins that feed the autoscale limits, `get_xgridlines`/`get_ygridlines` return handles backed by the grid state, `get_clip_path`/`set_clip_path` return the axes rectangle or the stored path, `pick` dispatches to children, and `start_pan`/`drag_pan`/`end_pan` shift the view in display coordinates. TRACE implementation rises from 9381 to 9434 call sites with 615 accepted and ignored and 49 missing: the Axes section has no missing calls, only the accepted `redraw_in_frame` shim. |
| R15 | **Done — Figure and pyplot coverage closed.** `Figure.show`, `waitforbuttonpress` and `ginput` are honest no-op shims for the static backend (recorded as accepted), and `Figure.pick` dispatches to its axes. `pyplot` gains `imsave` (native PNG encoder, Pillow for JPEG/TIFF, the renderer for vector formats), `switch_backend`/`get_backend`, `sca`, `get_figlabels`, `box`, `autoscale`, `specgram`, `barbs`, `ecdf`, `figimage`, `draw_all` and `draw_if_interactive`, and exports `Normalize` and `FuncFormatter`. `Axes.specgram` now maps `Fs=None` to the default 2 Hz, and the core `Normalize` call/inverse apply the linear mapping instead of the identity. The workspace total is 9473/10098 implemented with 625 accepted and ignored and no missing call sites. |
| R16 | **Done — autoscale honors the stored margins.** `Axes.autoscale`/`autoscale_view` enable, disable or leave autoscaling per axis, recompute the view from the data plus `margins()` (with `tight=True` zeroing the margins and `autoscale(False)` freezing the current view), update shared-axis limits, and validate `axis`; `pyplot.autoscale` delegates to it. Pixel tests decode the rendered PNGs for the violin body, its median line and `imsave` PNG/JPEG/TIFF output. TRACE reaches 9497/10098 implemented with 601 accepted and ignored and no missing call sites. |
| R17 | **Done — remaining Axes shims.** `label_outer` hides inner tick labels from the subplot position, `quiverkey` draws a scaled reference arrow plus its label, `pie_label` places sequence or format-string labels (and `pyplot.pie_label` delegates to it), `locator_params` installs/configures a `MaxNLocator`, `ticklabel_format` installs a plain/scientific formatter with Matplotlib's `scilimits` validation, `relim` drops explicit limits on autoscaled axes, `get_legend` returns the shown legend, `get_cursor_data` reads the image pixel under the event, and the navigation-event policy is stored. `set_xlim`/`set_ylim` gain Matplotlib's `auto` flag. TRACE reaches 9558/10098 implemented with 540 accepted and ignored and no missing call sites. |
| R18 | **Done — violin and autoscale-margin golden scenes.** The shared manifest gains `violin` and `autoscale_margins`, each rendered by both the Python facade and the native builder. `Axes::violin` draws bodies plus extrema bars from precomputed statistics, and `Axes::margins` expands the data span, so both front ends compare the same committed PNGs; both scenes match within an RMS of 0.3. |

## Refactoring analysis (26 Nov)

Measured on `main` at `a1cb087`. Behaviour is covered by 590 Python tests, the
Rust suites, the shared golden scenes and the TRACE gate, so every task below
is a pure move or simplification: **no task may change rendered output or the
public surface** (`dir(matplotvite)`, `__all__`, TRACE counts and golden
images stay identical). Q2 split `Axes` by concern but left everything in one
13.9k-line module, which is the root of most items here.

Hot spots: `_plotting.py` is 13.9k lines with 433 top-level definitions
(254 module functions); `Axes` alone is 2126 lines and 238 methods; the Rust
`Panel` record has 57 public fields, 22 of them x/y pairs; `api.rs` is 1493
lines and 61 public functions; `tests/test_plt.py` is 5.8k lines and 345 tests.

| # | Task |
|---|------|
| F1 | **Done — split `_plotting.py` into modules.** `_plotting.py` is now an 881-line re-export facade over 19 modules: `_helpers`, `_containers`, `_artists`, the four `_axes_*` mixins, `_axes`, `_plot_helpers`, `_images`, `_figure`, `_pyplot`, `_config`, `_cm`, `_ticker`, `_png`, `_misc`, `_projections` and `_fonts`. The largest is `_axes.py` at 2,211 lines, so no module exceeds the 2.5k target. The code is one strongly connected component, so names a function only needs once called are declared under `TYPE_CHECKING` and bound by the facade after every module loads; facade patches are mirrored to the owning module. `dir(matplotvite)`, `__all__`, the TRACE gate (9558/10098 implemented, 540 accepted) and the golden scenes are unchanged. |
| F2 | **Done — the mixins have a real contract.** `_AxesMixinBase` is a class that declares the 46 state members and 41 methods the four mixins share (plot families, private append/date helpers and the projection hooks). The blanket `__getattr__` is gone and the eight `type: ignore` comments it forced were removed. |
| F3 | **Done — one table for the pyplot wrappers.** `_PYPLOT_DELEGATES` holds the 72 `gca()`/`gcf()` wrappers with their signature, call arguments and docstring; `_make_delegate` builds each function, so `inspect.signature`, the docstring gate and the stubs checks all see the declared surface. `tools/trace_unsupported.py` reads the same table when classifying delegated calls. |
| F4 | **Done — the shims are declared once.** `_noop_method` and `_state_setter` in `_helpers.py` build the 206 repeated one-line methods (179 no-ops, 27 trivial state setters) from their declarations and keep each signature. The 47 accepted-but-ignored ones still call `_ignored`, and `tools/trace_unsupported.py` classifies them from the function marker, so the warning and the TRACE accepted set cannot drift from the declarations. |
| F5 | **Done — broke up the long functions.** The eight long methods now delegate their validation and geometry to module-level helpers: `savefig` 106 → 27 lines (`_savefig_request`, `_canvas_pixels`, `_encode`, `_write_output`), `streamplot` 169 → 71 (`_streamplot_check`/`_seeds`/`_trajectories`/`_segments`), `hexbin` 112 → 62 (`_hexbin_grid`, `_hexbin_cells`), `hist` 128 → 105 (`_hist_datasets`, `_hist_centers`, `_hist_steps`), `violin` 128 → 78 (`_violin_axes`, `_violin_line_ends`, plus the core outline), `violinplot` 115 → 94 (`_violinplot_outline`), `boxplot` 158 → 118 and `bxp` 99 → 95 (`_box_stats`, `_box_style`, `_bxp_fields`). The extracted helpers take arrays and return arrays, so they run without a figure; the suite and rendered output are unchanged. |
| F6 | **Done — one source for violin and margins geometry.** `matplotvite-core::stats` owns `violin_outline` (mirrored and one-sided bodies, horizontal or vertical), `validate_violin`, `margin_pad` and `expand_limits`. `Axes::violin` in Rust and `Axes.violin` in Python both draw the core-outline bands, `Axes.margins` and `_margin` both use the shared pad, and the finite/non-negative/equal-length rules and their messages come from `StatsError`. The shared `violin` and `autoscale_margins` goldens still match, and the core tests cover the geometry and margin arithmetic directly. |
| F7 | **Done — slimmed the builder and the `Panel` record.** `api.rs` is now `api/mod.rs` (types, `Figure`, lifecycle and `Axes` state mutators) plus `api/plot.rs`, `api/field.rs` and `api/axis.rs` by artist family; the largest is 678 lines. `push_series`/`push_band`/`record` and the `owned`/`line_series` constructors replace the repeated push-and-remember blocks, and the `OwnedArray1::from(x.to_vec())` calls go through `owned`. `Panel`'s 22 paired x/y fields are one `AxisSpec` held as `x` and `y`, so limits, scale flags and label presentation have one definition; `test_panel_contract.py` now checks the `AxisSpec` payload against the Rust struct too. The suite, the Rust tests and the shared goldens are unchanged. |
| F8 | **Done — the Python suite is split by area.** The 5.8k-line `tests/test_plt.py` is now `test_plt_api.py`, `test_plt_artists.py`, `test_plt_axes_decor.py`, `test_plt_axes_field.py`, `test_plt_axes_plot.py`, `test_plt_axes_stats.py` and `test_plt_figure.py` (24 to 99 tests each, 345 in total); the 14 module helpers moved to `tests/plt_helpers.py`, which each module imports only what it uses. The split exposed two order dependencies, both fixed rather than papered over: `colormaps()` no longer lists anonymous `ListedColormap` tables, and those tables are keyed by a content fingerprint, so two `from_levels_and_colors` results with different levels no longer share one table. The golden, TRACE, API-surface and PNG fuzz tests are untouched, and the suite still reports 590 passed, 5 skipped. |
| F9 | **Done — one snippet runner and split page tools.** `tools/snippet_runner.py` holds the repository's only `exec` (outside the baseline evaluator), the child-process isolation and the timeout; `mpl_render.render` runs `_render_entry` through it, and `gallery_render`/`visual_compare` use its in-process `execute`, keeping their snippets in-process because they measure timings. `build_pages.py` went 1204 → 159 lines with `pages_common.py` (metadata, coverage, status breakdowns), `pages_gallery.py` (gallery, comparison and SVG reports), `pages_benchmarks.py`, `pages_karios.py`; `pages_assets.py` 874 → 70 with `pages_styles.py` (shared/gallery CSS and JS) and `pages_report_styles.py` (comparison/benchmark CSS); `benchmark.py` 682 → 110 with `benchmark_cases.py` holding one function per benchmark group. The tools' CLIs, the tests that import `build_pages`/`measure_callable`, and a full `--quick` benchmark run (34 results, 9 categories) still work. |
| F10 | **Done — coercion helpers.** `_as_f64` now backs the 85 call sites that spelled `np.asarray(..., dtype=float).ravel()`, and the new `_check_same_length` helper centralises the repeated axis-length checks. Error messages are unchanged, the suite passes and TRACE still reports 9558/10098 implemented. |
| F11 | **Done for the package, in progress per module.** Ruff's `PERF401`, `PERF203` and `SIM108` exceptions are gone (12 findings fixed: 9 `extend` rewrites and 3 ternaries) and no `ignore` entry remains. mypy gained the checking half of `strict` for the whole package — `warn_return_any`, `no_implicit_optional`, `strict_equality`, `disallow_any_generics` — which cost 15 annotations (bare `list`/`dict`/`tuple` subclasses and parameters). The annotation half is turned on per module through a `[[tool.mypy.overrides]]` list: `matplotvite._config` and `matplotvite.units` require typed calls too, while `matplotvite._axes_decor`, `matplotvite._colors`, `matplotvite._misc`, `matplotvite._png`, `matplotvite.sankey`, `matplotvite.scale`, `matplotvite.spines`, `matplotvite.tri` and `matplotvite.widgets` also require typed calls (131 findings fixed, mostly signatures). Getting there meant annotating the helpers those modules call — `_font_size`, `_font_family`, `_family_override`, `_check_kwargs`, `_norm_color`, `_with_alpha`, `_text_props`, `_mathtext`, `_normalize_legend_loc`, `_as_f64`, `_ignored`, `get_cmap`, `_Transform`, `_CoordTransform`, `_TextArt`, `_LegendHandle`, `FancyArrow`, `GridSpec` and `Figure.__init__`/`add_axes`/`savefig` — so `disallow_untyped_calls` now applies to the whole group. A third list, `matplotvite._pandas` and `matplotvite.offsetbox`, enforces full annotations while their callees are still untyped, and the rest of the ratchet continues from there. |

Suggested order: F10 and F4 (low risk, shrink the surface), F1 with F2 and F3
(the structural change), then F6 and F7 (Rust and Python together), F5, F8,
F9 and F11.

## OpenSSF Scorecard (26 Nov, 6.6 / 10)

Scanned at `cbb6971`. Already 10: Dependency-Update-Tool, Binary-Artifacts,
Security-Policy, Dangerous-Workflow, Token-Permissions, Fuzzing (License 9).

| # | Task |
|---|------|
| S1 | **Done in-repo — hash-pinned installs.** `.github/requirements/` holds purpose-scoped `*.in` sources compiled with `uv pip compile --universal --generate-hashes` into `*.txt` files that carry every wheel and sdist hash for Python 3.9–3.14 (`tools`, `test`, `runtime`, `build`, `docs`, `corpus`, `release`). Every `pip install` in `ci.yml`, `pages.yml` and `publish.yml` now runs `--require-hashes -r <file>`, and the built wheel is installed by path (`dist/*.whl`) so Scorecard counts it as pinned instead of as a bare package name. `tools/check_requirements.py` recompiles every `.in` and fails on any drift, `tests/test_requirements_pins.py` keeps each entry pinned and hashed, `tools/security_audit.py` audits every file and the `dep-audit` hook watches the directory. The installs were verified with pip on 3.9, 3.12, 3.13 and 3.14; the score itself moves on the next scan of `main`. |
| S2 | **Open — Code-Review 0 and CI-Tests 0.** Every change lands directly on `main`. Open PRs for changes (even self-merged) so CI runs before merge and a review is recorded; enable branch protection requiring the CI checks. Scores rise as new changesets are merged through PRs. |
| S3 | **Done — SAST.** `codeql.yml` already runs `python`, `rust` and `actions` analysis on `pull_request` as well as on pushes and weekly (`59b686d`, 25 Nov). The check reads 0 of the last 5 commits because those landed directly on `main` without a PR; it rises once changes arrive through PRs (see S2). |
| S4 | **Manual — Branch-Protection (−1, unreadable).** The scan token cannot read the rules. `scorecard.yml` now passes `repo_token: ${{ secrets.SCORECARD_TOKEN || github.token }}`, so a `SCORECARD_TOKEN` secret with administration read turns the check on without another workflow edit. Enabling protection on `main` (required checks, no force push) and creating that PAT are repository settings, not code. |
| S5 | **Blocked upstream — Vulnerabilities 7 (3 findings, none exploitable).** `RUSTSEC-2026-0192` (`ttf-parser`) and `RUSTSEC-2026-0206` (`rustybuzz`) are "unmaintained" notices with no patched version. The upgrade was checked against the registry and the advisory database on 27 Nov 2026: both notices list `patched = []`, so the crates have to leave the tree rather than be bumped. `svg2pdf` 0.13.0 is still the latest release, it requires `usvg`/`resvg` `^0.45` (so `^0.45` cannot move to a newer minor) and it uses `ttf-parser` `^0.25` directly for the subsetting behind its default `text` feature; its `main` branch has only reached `usvg` 0.46. The one crates.io alternative, `vl-convert-pdf`, is older still (`usvg` 0.36, `ttf-parser` 0.20). `usvg` itself dropped `rustybuzz` for `harfrust`/`skrifa` in 0.49, so the two notices clear when `svg2pdf` releases on that stack — neither `cosmic-text` nor `swash` is reachable while the PDF text path stays on `ttf-parser`, and disabling `svg2pdf`'s `text` feature would drop labels from PDF output. A locally built PDF writer is **out of scope: do not rewrite the PDF generator**; wait for upstream `svg2pdf`. Both stay ignored in `deny.toml` with the reason recorded there, and dependabot already opens the `svg2pdf` update when it lands. `PYSEC-2026-1845` is `pytest` 8.4.2, dev only, pinned for Python 3.9/3.10. |
| S6 | **Waiting — release hygiene (Packaging, Signed-Releases at −1).** `publish.yml` already builds the wheels and sdist, attests both with `actions/attest-build-provenance`, uploads them through PyPI trusted publishing and records a GitHub release. Both checks need a first tagged release, which is a publishing action rather than a code change. |
| S7 | **Open — CII-Best-Practices 0.** Apply for the OpenSSF Best Practices (passing) badge; most criteria are already met by the CI and policy files. |
| S8 | **Waiting — Maintained 0 and Contributors 0.** Clear with time (project under 90 days) and with contributors from other organizations. No code action. |

Done in this pass: `dep-audit` pre-commit hook (runs `cargo audit`, bandit and
`pip-audit` when `Cargo.lock`, `requirements-ci.txt`, `pyproject.toml` or
`deny.toml` change); `cargo deny check` pre-push hook; `pip-audit` now audits
the pinned requirements instead of the tool-only environment. CI already ran
`cargo deny`, `cargo audit`, `pip-audit` and trivy.

## Status

No security or parity findings remain open. The Scorecard pass pinned every CI dependency by hash (S1), confirmed CodeQL runs on PRs (S3) and made the branch-protection token a secret away (S4); S2, S5–S8 still need repository settings, a tagged release, a crate replacement or time. The F1–F11 refactoring tasks above are proposals. The 23 Nov re-audit is complete: the facade
introspection fix (R10), Figure state accessors (R11), Axes state accessors
(R12), Axes hit-testing/cursor formatting (R13), the remaining Axes APIs (R14)
and the Figure/pyplot coverage (R15) lift the TRACE report from 9178/10098 to
9473/10098 implemented (625 accepted and ignored, none missing); R16 makes
autoscale honor the margins and R17 implements the remaining Axes shims,
raising it to 9558/10098 (540 accepted, none missing); R18 adds the
violin/autoscale-margin golden scenes on both front ends.
The 0.7 follow-ups are complete: checked-in
corpus metadata with hash-based diffing (`e325be0`), Seaborn wrapper pixel-diff
coverage (`8e4ce5a`) and the pandas plotting backend (`319e11c`). The README,
Sphinx docs, roadmap, architecture and this review now describe the same 0.7
state.
