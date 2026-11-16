# Review: performance, security and Matplotlib parity (open issues)

Scope: `main` after the compatibility-shim, table, polar and gallery-reference changes. Only open, actionable tasks are listed; closed findings and passive watch items are removed. The examples gallery was regenerated on 15 Nov with the current build.

Results on this tree: Python suite 430 passed, 7 skipped; `ruff`, `cargo fmt`, `cargo clippy` and `cargo test` clean. The `mpl-examples` gallery renders the original script with Matplotlib beside every Matplotvite output, and every comparison row has a collapsible source block, so failed and blank cases have a reference image.

| Gallery | Cases | Rendered | Blank | Failed / needs API | other |
|---------|-------|----------|-------|--------------------|-------|
| `mpl-corpus` (`@image_comparison`) | 526 | 382 | 5 | 113 failed | 26 unsupported |
| `mpl-examples` (gallery scripts) | 507 | 384 | 2 | 12 needs API | 0 harvester gaps, 3 bugs, 106 unsupported |

The examples gallery is current. The corpus row and its pixel metrics are from the last corpus run; they were not regenerated for this change.

## Parity and visible styling

| # | Finding | Evidence / next check |
|---|---------|-----------------------|
| M2 | **Colorbar mappables remain partly checked.** Scatter collections and standalone `ScalarMappable` work, as does `cax=`. | `hexbin`, `pcolormesh` and `ticklocation` now run without error; still check the rendered output. |
| M3 | **Colorbar text and layout remain partly checked.** Ticks use round locator values. | Verify label side (right of the bar), `ScalarFormatter` text (`8000`, not `8e+03`) and the Unicode minus in a render. |
| M4 | **Shared axes may still show redundant labels.** `sharex`/`sharey` are supposed to hide inner tick labels; the probe passes, but the old renders showed labels overlapping neighbours in `02_dx` and `04_ce`. | Re-render both figures and confirm inner labels are hidden. |
| M5 | **Twin-axis sides remain partly checked.** `fill_between(color=...)` no longer advances the colour cycle. | Verify the `twinx` left/right axis sides in `02_dx`. |
| M11 | **Multiline text needs a spacing/indent check.** Leading whitespace and 1.2 line spacing were addressed, but the old `04_ce` block ran into the plot below. | Re-render `04_ce` and `02_dx`, check indentation, spacing and the `bbox` frame. |
| M12 | **Default font sizes need a render check.** DejaVu Sans is bundled and default; confirm title 12 pt, suptitle 16 pt and ticks 10 pt against Matplotlib. | Compare all four figures; a bold `Reference`/`Monitored` heading may still be a title-weight bug. |
| M17 | **`imshow` interpolation.** The default stays `nearest` deliberately; Matplotlib's `antialiased` resamples images shrunk by more than 3×. | `interpolation="antialiased"` is accepted; check it really resamples, and add an rc switch for byte-for-byte parity if needed. |

## API gaps and failures

| # | Finding |
|---|---------|
| G3 | **Remaining examples API gaps (12):** `matplotlib.scale`; hand-built contour paths and manual `clabel`; `PdfPages`; `FT2Font.set_charmap`/`num_named_instances`; `BboxConnector`; radar `set_varlabels`; boxplot/`time_series_histogram` styling. 3-D remains out of scope. |
| G4 | **Known example failures (3):** `rasterization_demo` saves EPS (only PNG/SVG/PDF/WebP are encoded); `svg_filter_line` and `svg_filter_pie` ask `ElementTree.XMLID` for gids that the SVG backend does not emit yet. |
| F5 | **Environment cases:** install Pillow in the gallery job (`image_demo`, `image_clip_path`, `demo_annotation_box`, `demo_text_path`, `demo_ribbon_box`, `mathtext_asarray`); `units/*` now uses the bundled converter registry. |
| E5 | **One-line API gap:** `Axes.set()` raises `AttributeError` on unknown keywords; find which keyword the examples pass that Matplotlib accepts. (`Axes.twin()` now works.) |

## Accounting, tests and trust

| # | Finding |
|---|---------|
| G5 | **Environment accounting:** 9 examples need `gi` and 7 need `wx`; `user_interfaces` (25), `widgets` (16) and `animation` (10) are interactive by nature and should be `unsupported` up front. Local runs should also state when `cairosvg`/`pypdfium2` are missing, because SVG/PDF baselines then get no metric. |
| F7 / N7 | **"Rendered" is not proof of correctness.** It still includes ignored calls (see the per-case `ignored` count). Treat rendered counts as an upper bound and check the remaining float-conversion cases did not merely move into `needs-api`. |

## Other checks

| # | Task |
|---|------|
| U3 | Tick count is now 8; check a 3×3 subplot grid for crowding. |

## Rust crate preparation

Goal: a native Rust crate with the same matplotlib-like API. Today Rust is only a renderer fed by a Python-built `Panel` dict; the API (`Figure`, `Axes`, artists, locators, norms; about 10k lines) lives in Python.

| # | Task |
|---|------|
| R1 | **Split `lib.rs::render`** (about 150 lines of validation, format routing, direct-PNG path and cropping) into `render.rs::render_figure(&Figure, &RenderConfig) -> Result<Vec<u8>, RenderError>`. `lib.rs` keeps only the pyo3 adapter. Replace `Result<_, String>` with an error enum. |
| R2 | **Move pyo3 out of `model.rs`** (203 pyo3 hits: `FromPyObject`, `OwnedArray*`) into `py.rs` behind `cfg(feature = "python")`; make `pyo3` and `numpy` optional. `draw`, `layout`, `export`, `raster`, `image`, `scale`, `color` and `fonts` are already pyo3-free. Gate: `cargo test --no-default-features` builds without Python. |
| R3 | **Replace stringly-typed model fields** (`color`, `linestyle`, `marker`, `drawstyle`, `cmap`, `units`: `String`) with `Color`, `LineStyle`, `Marker`, `DrawStyle` and `Cmap` enums parsed once at the boundary; extend `color.rs` rather than add a module. |
| R4 | **Split `draw.rs`** (2,652 lines; `draw_panel` starts at line 1576) by artist (line, scatter, bar, contour, quiver, text, collection) under `draw/`. |
| R5 | **Add pure-Rust render smoke tests.** Only a few unit tests in `lib.rs` exist; Python tests do not exercise the Rust API directly. Needed before R1/R2 can be trusted without the Python suite. |
| R6 | **Workspace split:** `matplotvite-core` (model, layout, draw, export; no Python), `matplotvite` (builder API: `Figure::new`, `fig.subplot`, `ax.plot(&x, &y).color(..)`, `fig.savefig`), `matplotvite-py` (thin pyo3 module). CI job runs `cargo test -p matplotvite-core`. |
| R7 | **Port the `Axes` API to Rust** from `Axes._panel()`, in `TRACE.md` priority order: `plot`, `scatter`, `bar`, `hist`, `imshow`, `fill_between`, then the rest. Take slices or `ndarray` views, no copies. Optional thread-local `pyplot` layer only if requested. |
| R8 | **De-duplicate tick logic:** `_nice_step` / `Axis._ticks` in Python and `nice_ticks` / `auto_ticks` in `layout.rs` implement the same thing. Expose the Rust locators, norms and colormap lookup to Python and delete the Python copies. |
| R9 | **Shared golden-image test set** rendering the same scenes through the Python wrapper and the Rust crate, so the two front ends cannot drift. |
| R10 | **Decide the output paths:** the direct-PNG and SVG paths produce slightly different output; choose whether the crate exposes one or both before the API is public. |

## Suggested order

1. **G4 and G3**: triage the crash groups, then the remaining API gaps.
2. **G5**: finish the environment accounting.
3. Rebuild the KARIOS images, re-render the four pairs, and re-judge every "(image)" item listed above.
4. **R2, R1, R5** first (mechanical, keeps the 430-test Python suite as a safety net), then R3/R4, then R6 onward.
