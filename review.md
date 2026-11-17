# Review: performance, security and Matplotlib parity (open issues)

Scope: `main` after the 16 Nov gallery and font-size fixes. Only open, actionable
tasks are listed. Results on this tree: Python suite **478 passed, 9 skipped**;
`cargo test --all-targets` passes 43 tests; `ruff`, `cargo fmt`, and
`cargo clippy --all-targets -- -D warnings` are clean.

| Gallery | Cases | Rendered | Blank | Failed / needs API | Other |
|---------|-------|----------|-------|--------------------|-------|
| `mpl-corpus` (`@image_comparison`) | 526 | 495 | 5 | 0 failed | 26 unsupported |
| `mpl-examples` (gallery scripts) | 507 | 389 | 4 | 0 failed, 0 needs API | 114 unsupported |

Both totals are from full runs on this tree. The 526-case corpus was rerun after
the projection, `imread`, and corpus compatibility fixes; the final sample-data
case was confirmed separately when its harness path was wired through.

Closed this cycle: the remaining example API/failure groups (G3/G4), Pillow
environment handling (F5), default title/label/tick sizes and tick-label handles
(M12), standalone `Colorbar(ax, cmap=, norm=, drawedges=)` construction, horizontal
colorbars with axis scale/limits and extension geometry, RGB tuple facecolours,
Path/EventCollection compatibility helpers, colorbar `extendfrac`, 3-D/skew
projection compatibility, `polar=True` axes construction, standard-library PNG
`imread` (with generated tests for every PNG colour type and 1/2/4/8/16-bit
depth), and the code-level probes for colorbar mappables/text, shared-axis
labels, twin-axis sides, multiline text and `imshow` antialiasing (M2–M5, M11,
M17). The corpus pass also fixed normalization subclassing, gridspec figure
wiring, masked units, contour label placement and level locators, `mgrid`
grids, pandas `data=` label and date-index handling, bivariate colormaps, and
sample-data resolution. Headless `widgets.RadioButtons` and
`widgets.CheckButtons` now cover Matplotlib's widget images. The KARIOS
legend-order, twin-side and layout fixes are also in this tree. The 3×3
tick-density check is covered by the eight-tick locator test.

## External visual sign-off

| # | Finding |
|---|---------|
| V1 | **The external KARIOS/`02_dx`/`04_ce` reference figures are not available locally.** The code-level probes now cover the mechanisms for M2–M5, M11, M12 and M17, but pixel-level sign-off still requires rebuilding those references and re-rendering the four pairs. |

## Corpus and coverage

| # | Finding |
|---|---------|
| V2 | **No corpus render failures remain.** Backend PDF/PS/SVG and projection cases now render, including `test_png/test_pngsuite` through the standard-library PNG `imread`; the two PS transparency cases are blank because every artist is intentionally `alpha=0`. The remaining 26 unsupported cases are interactive, GUI, or otherwise out of scope. |
| V3 | **“Rendered” is not proof of correctness.** The example count includes ignored calls; use the per-case `ignored` count and the visual checks above as the upper-bound caveat. |

## Rust crate preparation

Goal: a native Rust crate with the same matplotlib-like API. The API (`Figure`, `Axes`, artists, locators, norms; about 10k lines) still lives in Python.

| # | Task |
|---|------|
| R1 | **Done.** `src/render.rs::render_figure` owns validation, format routing, direct-PNG selection, cropping and encoding; `src/lib.rs` is the PyO3 adapter and maps `RenderError` to Python exceptions. |
| R2 | **Done.** The PyO3 adapter and NumPy extraction live in `src/py.rs` behind the default `python` feature; `pyo3` and `numpy` are optional dependencies and the model uses plain `ndarray`. Gate: `cargo test --no-default-features` and `cargo clippy --no-default-features -- -D warnings` pass without Python. |
| R3 | **Replace stringly-typed model fields** (`color`, `linestyle`, `marker`, `drawstyle`, `cmap`, `units`: `String`) with `Color`, `LineStyle`, `Marker`, `DrawStyle` and `Cmap` enums parsed once at the boundary; extend `color.rs` rather than add a module. **Partly done: `Series.drawstyle` is a `DrawStyle`, `Series.linestyle`/`Grid.linestyle` use `LineStyle`, `Marker` is used by series, scatter and collections, quiver `units`/`scale_units` use `QuiverUnits`, and `Cmap` covers image, contour, scatter and colorbar colormaps; all are parsed by the Python adapter. The colour fields remain strings.** |
| R4 | **Split `draw.rs`** by artist (line, scatter, bar, contour, quiver, text, collection). The `draw/` modules cover axes, series, ticks, legends and images; the remaining `draw.rs` entry point is still large. |
| R5 | **Done.** `src/render.rs` renders a minimal line panel to PNG and SVG through the pure-Rust path, so high-level drawing is no longer covered only through Python. |
| R6 | **Workspace split:** `matplotvite-core` (model, layout, draw, export; no Python), `matplotvite` (builder API: `Figure::new`, `fig.subplot`, `ax.plot(&x, &y).color(..)`, `fig.savefig`), `matplotvite-py` (thin pyo3 module). CI job runs `cargo test -p matplotvite-core`. |
| R7 | **Port the `Axes` API to Rust** from `Axes._panel()`, in `TRACE.md` priority order: `plot`, `scatter`, `bar`, `hist`, `imshow`, `fill_between`, then the rest. Take slices or `ndarray` views, no copies. Optional thread-local `pyplot` layer only if requested. |
| R8 | **De-duplicate tick logic:** `_nice_step` / `Axis._ticks` in Python and `nice_ticks` / `auto_ticks` in `layout.rs` implement the same thing. Expose the Rust locators, norms and colormap lookup to Python and delete the Python copies. |
| R9 | **Shared golden-image test set** rendering the same scenes through the Python wrapper and the Rust crate, so the two front ends cannot drift. |
| R10 | **Done — expose both paths.** Keep the direct raster path for PNG/WebP/EPS and the vector SVG/PDF path; PNG uses the direct path when eligible and falls back to rasterized SVG. R5 pins both paths; R9 will add the shared golden comparison. |

## KARIOS lacraux comparison (16 Nov)

Expected: `data/karios-out/lacraux-overlay/...` (Matplotlib). Ours: `.../matplotvite/lacraux-matplotvite-0.6.1dev/...`. The old output overlaps badly because `karios-matplotvite` (`karios/report/commons.py`) still carries workarounds for older matplotvite: `_AXES_MARGIN_PX = (72, 28, 52, 75)` enlarges every `add_axes` rect, but `add_axes` now treats the rect as the plot area (verified: a 0.1..0.9 rect gives a 0.1..0.9 frame). With the margins zeroed in a scratch copy (current `python/`, same inputs), layout is nearly right; pixel RMS fell from 92.6/55.1/53.1/51.3 to 66.4/42.9/41.6/40.6 (overview/dx/dy/ce). Remaining differences are matplotvite parity bugs:

| # | Finding |
|---|---------|
| K0 | **KARIOS workarounds are stale** (not a matplotvite bug): drop `_AXES_MARGIN_PX`, `text_block`/`figure_text` line splitting, the manual colorbar and `grid_rects` where matplotvite now has the real feature (`\n` text, `fig.text`, `GridSpec` ratios, `colorbar`). Re-run the four images afterwards. |
| K1 | **`ylabel` overlaps wide tick labels** (`04_ce` Radial Error, Northing displacement, row histogram): label offset is not derived from the measured tick-label width. **Status: partly fixed: `ylabel` of `add_axes` axes now sits beside the measured tick labels; the 40 px margin still limits very wide labels.** |
| K2 | **`imshow` leaves the y axis uninverted:** overview image axes read 0 at the bottom, Matplotlib reads 0 at the top (origin `upper`). **Status: fixed.** |
| K3 | **Scatter markers draw larger than Matplotlib** for the same `s` (overview, dx, dy). **Status: fixed.** |
| K4 | **`twinx` sides and styling (confirms M5):** in `02_dx` the left axis shows the KP-per-col counts (0..100) and the right shows the mean (-1..1), the reverse of expected; the `Mean dx by col` legend entry is missing and the `std` `fill_between` is peach (cycle colour) instead of light blue. **Status: fixed.** |
| K5 | **Tick density on narrow axes:** the row panel shows `-2.50.02.5` where Matplotlib picks 3-5 non-overlapping ticks; `MaxNLocator` should use the axis size. **Status: fixed (colorbar strip now counted).** |
| K6 | **Legend order:** expected lists `Count` (histogram) before `Normal` (line); ours lists lines first. Matplotlib uses artist creation order. **Status: fixed (creation order, bar containers last).** |
| K7 | **Colorbar tick text (confirms M3):** `8e+03`-style labels instead of `8000`. **Status: not a matplotvite bug: KARIOS formats labels with `.3g`.** |
| K8 | **Colorbar and axes geometry:** colorbar is narrower than expected and the top `dx` axes is shorter and shifted; re-check after K0. |

## Refactoring analysis (17 Nov)

Measured: `python/matplotvite/__init__.py` is 12.6k lines (1489 methods; `class Axes` alone spans ~3.6k lines, `Figure` ~3k); `src/draw.rs` is 2.9k lines. Tasks complement R3/R4/R8 and do not repeat them.

| # | Task |
|---|------|
| Q1 | **Split `__init__.py` into modules, re-exported from the package.** Pure moves in this order: colours/colormaps (`_norm_color`, `Colormap`, registry; lines 89-505), transforms/bbox/path (`Affine2D`, `Path`, `_Bbox`, 619-975), patches (`Patch` … `Annulus`, 2262-2770), collections (2899-3220), legend/container handles (1672-2130), `Axis`/spines/`_Axis*` (3375-3663), then `Axes` and `Figure`. Gate: the Python suite plus `__init__.pyi` unchanged. Makes the file reviewable and unblocks R7. |
| Q2 | **Break up `Axes`** (3849-7498): mixins per concern (`_plotting` for plot/scatter/bar/hist, `_stats` for boxplot/violin, `_fields` for contour/quiver/streamplot, `_decor` for legend/annotate/text). Biggest single methods to split first: `_panel` (217 lines), `_apply_axis_scales` (213), `set_axis` (179), `streamplot` (170), `boxplot` (159). |
| Q3 | **Finish moving `draw.rs` into `draw/`** (R4): `draw_legend`, `best_legend_pos`, `anchored_legend_pos`, `draw_rounded_frame` (draw.rs 391-640) duplicate the role of `draw/legend.rs`; colorbar (1095-1320), contour (1321-1530), markers (891-1660), polyline clipping/dashing (642-890) and tick formatting (1662-1740, next to `draw/ticks.rs`) each become one module. Target: `draw.rs` under 600 lines of orchestration. |
| Q4 | **Move scale maths to `scale.rs`:** `symlog`, `logit`, `asinh_scale`, `asinh_inverse` live in `draw.rs` while `src/scale.rs` and `python/matplotvite/scale.py` hold the same transforms. One Rust implementation, exposed to Python (part of R8). |
| Q5 | **Remove the Python/Rust panel contract duplication:** `_panel()` builds a dict whose keys are re-declared in `src/model.rs` (866 lines) and read by hand in `py.rs`. Generate one from the other (a `serde` model with `pythonize`, or a schema test that fails when the key sets differ) so adding a field is a one-place change, as with the recent `yside`/`legend.order` additions. |
| Q6 | **Unify the two tick paths in `draw/ticks.rs`/`draw/axes.rs`.** The plotters mesh path and `draw_manual_ticks` produce different results (K1, K2, K5 were all path-dependent). Route every axis through the manual path once it matches the mesh output on the golden images, then delete the mesh-label code and the `manual` heuristic in `axes.rs`. |
| Q7 | **Typed legend/label ordering in Python:** `_Stamped` plus `_label_order`/`_container_order` is a side channel. Give each artist a creation sequence number (`Artist._seq`) and sort at `legend()` time; delete `_Stamped`. |
| Q8 | **Tools:** `tools/harvest_matplotlib.py` (1.3k) and `tools/build_pages.py` (1.3k) mix harvesting, rendering, metrics and HTML. Split rendering/metrics from HTML templates so CI can run the render step alone (see CI note below). |
| Q9 | **CI galleries (716 s, the long pole):** the examples gallery already skips Matplotlib references; the remaining time is our own renders and comparison metrics. Profile per step, then (a) shard the corpus/examples/seaborn steps into parallel jobs, (b) cache `dist/sdist`, `dist/mpl-src` and `dist/sns-src` keyed on the version pins instead of re-downloading, (c) run the full gallery only on `main` and a sampled subset on pull requests. |

## Suggested order

1. **V1:** rebuild the KARIOS images, re-render `02_dx`/`04_ce`, and finish the pixel-level sign-off.
2. **V2:** no corpus render failures remain; keep the 26 interactive/GUI cases out of scope.
3. **R3** first (mechanical, with the 475-test Python suite as a safety net), then R4/R6 onward; R2 and R5 are done.
4. **Q4, Q3** next (mechanical Rust moves), then **Q1** before **Q2**; **Q5** before adding more model fields; **Q9** whenever CI time matters.
