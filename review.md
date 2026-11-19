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

## External visual sign-off

| # | Finding |
|---|---------|
| V1 | **The external KARIOS/`02_dx`/`04_ce` reference figures are not available locally.** The code-level probes now cover the mechanisms for M2–M5, M11, M12 and M17, but pixel-level sign-off still requires rebuilding those references and re-rendering the four pairs. |

## Corpus and coverage

| # | Finding |
|---|---------|
| V3 | **“Rendered” is not proof of correctness.** The example count includes ignored calls; use the per-case `ignored` count and the visual checks above as the upper-bound caveat. |

## Rust crate preparation

Goal: a native Rust crate with the same matplotlib-like API. The API (`Figure`, `Axes`, artists, locators, norms; about 10k lines) still lives in Python.

| # | Task |
|---|------|
| R6 | **Workspace split:** `matplotvite-core` (model, layout, draw, export; no Python), `matplotvite` (builder API: `Figure::new`, `fig.subplot`, `ax.plot(&x, &y).color(..)`, `fig.savefig`), `matplotvite-py` (thin pyo3 module). CI job runs `cargo test -p matplotvite-core`. |
| R7 | **Partly done — priority Rust API exists.** `api::Figure`/`Axes` now cover `plot`, `scatter`, `bar`, `hist`, `imshow`, and `fill_between` through the shared renderer; the remaining `Axes._panel()` surface still needs a native builder. The API accepts slices and copies them into the renderer's owned panel records. Optional thread-local `pyplot` layer only if requested. |
| R8 | **Partly done — tick locators shared.** Python's `_auto_ticks` and `_auto_tick_target` now call the Rust locator, and the duplicate `_round_ticks` implementation is gone. Remaining: expose the norm classes and finish removing Python colormap wrapper code. Date-specific `_nice_step` step lists remain Python-side. |
| R9 | **Shared golden-image test set** rendering the same scenes through the Python wrapper and the Rust crate, so the two front ends cannot drift. |

## KARIOS lacraux comparison (16 Nov)

Expected: `data/karios-out/lacraux-overlay/...` (Matplotlib). Ours: `.../matplotvite/lacraux-matplotvite-0.6.1dev/...`. The old output overlaps badly because `karios-matplotvite` (`karios/report/commons.py`) still carries workarounds for older matplotvite: `_AXES_MARGIN_PX = (72, 28, 52, 75)` enlarges every `add_axes` rect, but `add_axes` now treats the rect as the plot area (verified: a 0.1..0.9 rect gives a 0.1..0.9 frame). With the margins zeroed in a scratch copy (current `python/`, same inputs), layout is nearly right; pixel RMS fell from 92.6/55.1/53.1/51.3 to 66.4/42.9/41.6/40.6 (overview/dx/dy/ce). Remaining differences are matplotvite parity bugs:

| # | Finding |
|---|---------|
| K0 | **KARIOS workarounds are stale** (not a matplotvite bug): drop `_AXES_MARGIN_PX`, `text_block`/`figure_text` line splitting, the manual colorbar and `grid_rects` where matplotvite now has the real feature (`\n` text, `fig.text`, `GridSpec` ratios, `colorbar`). Re-run the four images afterwards. |
| K1 | **`ylabel` overlaps wide tick labels** (`04_ce` Radial Error, Northing displacement, row histogram): label offset is not derived from the measured tick-label width. **Status: partly fixed: `ylabel` of `add_axes` axes now sits beside the measured tick labels; the 40 px margin still limits very wide labels.** |
| K8 | **Colorbar and axes geometry:** colorbar is narrower than expected and the top `dx` axes is shorter and shifted; re-check after K0. |

## Refactoring analysis (17 Nov)

Measured: `python/matplotvite/__init__.py` is 12.6k lines (1489 methods; `class Axes` alone spans ~3.6k lines, `Figure` ~3k); `src/draw.rs` was 2.9k lines when measured (about 2.3k now). Tasks complement R3/R4/R8 and do not repeat them.

| # | Task |
|---|------|
| Q1 | **Split `__init__.py` into modules, re-exported from the package.** Pure moves in this order: colours/colormaps (`_norm_color`, `Colormap`, registry; lines 89-505), transforms/bbox/path (`Affine2D`, `Path`, `_Bbox`, 619-975), patches (`Patch` … `Annulus`, 2262-2770), collections (2899-3220), legend/container handles (1672-2130), `Axis`/spines/`_Axis*` (3375-3663), then `Axes` and `Figure`. Gate: the Python suite plus `__init__.pyi` unchanged. Makes the file reviewable and unblocks R7. |
| Q2 | **Break up `Axes`** (3849-7498): mixins per concern (`_plotting` for plot/scatter/bar/hist, `_stats` for boxplot/violin, `_fields` for contour/quiver/streamplot, `_decor` for legend/annotate/text). Biggest single methods to split first: `_panel` (217 lines), `_apply_axis_scales` (213), `set_axis` (179), `streamplot` (170), `boxplot` (159). |
| Q6 | **Unify the two tick paths in `draw/ticks.rs`/`draw/axes.rs`.** The plotters mesh path and `draw_manual_ticks` produce different results (K1, K2, K5 were all path-dependent). Route every axis through the manual path once it matches the mesh output on the golden images, then delete the mesh-label code and the `manual` heuristic in `axes.rs`. |
| Q8 | **Tools:** `tools/harvest_matplotlib.py` (1.3k) and `tools/build_pages.py` (1.3k) mix harvesting, rendering, metrics and HTML. Split rendering/metrics from HTML templates so CI can run the render step alone (see CI note below). |

## Conformance and OSS practice audit (17 Nov)

Architecture is sound (Rust core, thin pyo3 adapter, abi3 wheels, SHA-pinned CI, dual licence, audit tooling, baselined benchmarks, no `unsafe`). Gaps are in the honesty of the coverage numbers, typing, release safety and project governance.

| # | Task |
|---|------|
| C14 | **Done — coverage and robustness.** `pytest-cov` enforces 75% branch coverage and `cargo-llvm-cov` enforces 45% lines on the non-Python crate. Proptest covers scale round-trips, tick ordering/bounds and polyline decimation; Hypothesis checks the Python scale/tick bindings. `fuzz/panel_render.rs` fuzzes the public panel/render path, and `fuzz/python/fuzz_panel_extraction.py` runs a live Python runtime against the real PyO3 dict extraction, either through atheris or the deterministic mutation loop that CI's tests exercise. |
| C15 | **Docs:** API reference site (mkdocs/sphinx) built in CI, docstring coverage for the ~105 public functions, user-facing `examples/` (current directory holds test fixtures), `test`/`docs` extras. |

## Suggested order

1. **V1:** rebuild the KARIOS images, re-render `02_dx`/`04_ce`, and finish the pixel-level sign-off.
2. **R6** onward (R7 after Q1).
3. **Q1** before **Q2**.
4. **C1/C2/C4** → **C7/C9/C11** → the rest of C.
