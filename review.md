# Review: performance, security and Matplotlib parity (open issues)

Scope: `main` after the 16 Nov gallery and font-size fixes. Only open, actionable
tasks are listed. Results on this tree: Python suite **451 passed, 12 skipped**;
`cargo test --all-targets` passes 36 tests; `ruff`, `cargo fmt`, and
`cargo clippy --all-targets -- -D warnings` are clean.

| Gallery | Cases | Rendered | Blank | Failed / needs API | Other |
|---------|-------|----------|-------|--------------------|-------|
| `mpl-corpus` (`@image_comparison`) | 526 | 429 | 5 | 66 failed | 26 unsupported |
| `mpl-examples` (gallery scripts) | 507 | 389 | 4 | 0 failed, 0 needs API | 114 unsupported |

The example gallery is current. The corpus total is derived from the last full
run plus the fixed cases re-rendered individually; the whole 526-case corpus has
not been rerun since every shim.

Closed this cycle: the remaining example API/failure groups (G3/G4), Pillow
environment handling (F5), default title/label/tick sizes and tick-label handles
(M12), standalone `Colorbar(ax, cmap=, norm=, drawedges=)` construction, RGB
tuple facecolours, and the code-level probes for colorbar mappables/text,
shared-axis labels, twin-axis sides, multiline text and `imshow` antialiasing
(M2–M5, M11, M17). The KARIOS legend-order, twin-side and layout fixes are also
in this tree. The 3×3 tick-density check is covered by the eight-tick locator test.

## External visual sign-off

| # | Finding |
|---|---------|
| V1 | **The external KARIOS/`02_dx`/`04_ce` reference figures are not available locally.** The code-level probes now cover the mechanisms for M2–M5, M11, M12 and M17, but pixel-level sign-off still requires rebuilding those references and re-rendering the four pairs. |

## Corpus and coverage

| # | Finding |
|---|---------|
| V2 | **The refreshed corpus still has 66 failures.** The multi-font helper, categorical `data=`, Colorbar constructor and RGB facecolour groups now render. The remaining failures are spread across Path helpers, EventCollection methods, and projection/text shims. |
| V3 | **“Rendered” is not proof of correctness.** The example count includes ignored calls; use the per-case `ignored` count and the visual checks above as the upper-bound caveat. |

## Rust crate preparation

Goal: a native Rust crate with the same matplotlib-like API. The API (`Figure`, `Axes`, artists, locators, norms; about 10k lines) still lives in Python.

| # | Task |
|---|------|
| R1 | **Done.** `src/render.rs::render_figure` owns validation, format routing, direct-PNG selection, cropping and encoding; `src/lib.rs` is the PyO3 adapter and maps `RenderError` to Python exceptions. |
| R2 | **Move pyo3 out of `model.rs`** into `py.rs` behind `cfg(feature = "python")`; make `pyo3` and `numpy` optional. `draw`, `layout`, `export`, `raster`, `image`, `scale`, `color` and `fonts` are already pyo3-free. Gate: `cargo test --no-default-features` builds without Python. |
| R3 | **Replace stringly-typed model fields** (`color`, `linestyle`, `marker`, `drawstyle`, `cmap`, `units`: `String`) with `Color`, `LineStyle`, `Marker`, `DrawStyle` and `Cmap` enums parsed once at the boundary; extend `color.rs` rather than add a module. |
| R4 | **Split `draw.rs`** by artist (line, scatter, bar, contour, quiver, text, collection). The `draw/` modules cover axes, series, ticks, legends and images; the remaining `draw.rs` entry point is still large. |
| R5 | **Add pure-Rust render smoke tests.** The 36 unit tests cover layout, raster, encoding and GID assembly, but most high-level drawing is still exercised only through Python. |
| R6 | **Workspace split:** `matplotvite-core` (model, layout, draw, export; no Python), `matplotvite` (builder API: `Figure::new`, `fig.subplot`, `ax.plot(&x, &y).color(..)`, `fig.savefig`), `matplotvite-py` (thin pyo3 module). CI job runs `cargo test -p matplotvite-core`. |
| R7 | **Port the `Axes` API to Rust** from `Axes._panel()`, in `TRACE.md` priority order: `plot`, `scatter`, `bar`, `hist`, `imshow`, `fill_between`, then the rest. Take slices or `ndarray` views, no copies. Optional thread-local `pyplot` layer only if requested. |
| R8 | **De-duplicate tick logic:** `_nice_step` / `Axis._ticks` in Python and `nice_ticks` / `auto_ticks` in `layout.rs` implement the same thing. Expose the Rust locators, norms and colormap lookup to Python and delete the Python copies. |
| R9 | **Shared golden-image test set** rendering the same scenes through the Python wrapper and the Rust crate, so the two front ends cannot drift. |
| R10 | **Decide the output paths:** the direct-PNG and SVG paths produce slightly different output; choose whether the crate exposes one or both before the API is public. |

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

## Suggested order

1. **V1:** rebuild the KARIOS images, re-render `02_dx`/`04_ce`, and finish the pixel-level sign-off.
2. **V2:** regenerate `mpl-corpus`; its failures are now the largest concrete gap list.
3. **R2, R3, R5** first (mechanical, with the 445-test Python suite as a safety net), then R4/R6 onward.
