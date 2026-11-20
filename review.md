# Review: performance, security and Matplotlib parity

Scope: `main` after the workspace split, Axes refactor and 0.7 corpus work.
Results on this tree: Python suite **556 passed, 5 skipped**;
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
| Q2 | **Done — `Axes` is split by concern.** `_PlotAxes` owns plot/scatter/bar/hist and the other plot families, `_StatsAxes` owns box/whisker/violin summaries, `_FieldAxes` owns images/contours/quiver/hexbin, and `_DecorAxes` owns text, annotation, labels, legends and grid styling. The remaining `Axes` class owns lifecycle, layout, ticks, scales and panel assembly. `_panel` now delegates reference/polar data to `_panel_series` and tick resolution to `_panel_ticks`; `_apply_axis_scales` delegates points, geometry, artists and limits to focused helpers. The full Python suite passes (556 passed, 5 skipped). |
| Q6 | **Done — one tick path.** Every axis now goes through `draw_manual_ticks`: the plotters mesh draws only the frame and axis descriptions, with its grid and tick marks disabled and empty label formatters so it cannot duplicate labels. The `manual` heuristic and `TickStyle::is_custom` are gone, default panels match the previous mesh output pixel-for-pixel, and the grid width now follows `linewidth * dpi / 72` like the rest of the renderer. |
| Q8 | **Done — gallery and harvester tooling split.** `tools/gallery_render.py` owns sample rendering, timings, matplotlib comparisons, the scaling chart and `samples.json`; `tools/build_pages.py` only builds HTML from that data (`--html-only`), and the Pages workflow runs the render step as its own command. The Matplotlib harvester is split into `tools/mpl_harvest.py` (parsing and snippet rewriting), `tools/mpl_render.py` (isolated matplotvite/matplotlib rendering) and `tools/mpl_metrics.py` (pixel metrics and failure classification); `tools/harvest_matplotlib.py` keeps the gallery orchestration, CLI and compatibility re-exports. |

## Conformance and OSS practice audit (17 Nov)

Architecture is sound (Rust core, thin pyo3 adapter, abi3 wheels, SHA-pinned CI, dual licence, audit tooling, baselined benchmarks, no `unsafe`). Gaps are in the honesty of the coverage numbers, typing, release safety and project governance.

| # | Task |
|---|------|
| C14 | **Done — coverage and robustness.** `pytest-cov` enforces a 75% branch floor; the current suite measures **76.93% branch coverage** (the floor is not the reported total). `cargo-llvm-cov` enforces a 45% line floor on the renderer; the gate runs the core and builder test targets and reports core sources only, which measure **66.13% lines** (the crate's own unit tests alone reach 39.53%, below the floor). Proptest covers scale round-trips, tick ordering/bounds and polyline decimation; Hypothesis checks the Python scale/tick bindings. `fuzz/panel_render.rs` fuzzes the public panel/render path, and `fuzz/python/fuzz_panel_extraction.py` runs a live Python runtime against the real PyO3 dict extraction, either through atheris or the deterministic mutation loop that CI's tests exercise. |
| C15 | **Done — API docs and examples.** Sphinx autodoc builds `docs/` in CI and into `dist/api` on Pages, `tools/check_docstrings.py` gates 100% of the 100 public functions and 90% of public classes, and the `docs`/`test` extras cover those workflows. `examples/quickstart.py` is the runnable user entry point; the remaining files are gallery fixtures. |

## Status

No review findings remain open. The 0.7 follow-ups are complete: checked-in
corpus metadata with hash-based diffing (`e325be0`), Seaborn wrapper pixel-diff
coverage (`8e4ce5a`) and the pandas plotting backend (`319e11c`). The README,
Sphinx docs, roadmap, architecture and this review now describe the same 0.7
state.
