# Review: performance, security and Matplotlib parity (open issues)

Scope: `main` after the 16 Nov gallery fixes. Only open, actionable tasks are listed.
Results on this tree: Python suite **444 passed, 12 skipped**; `cargo test
--all-targets` passes (36 tests), and `ruff`, `cargo fmt` and `cargo clippy
--all-targets -- -D warnings` are clean. The examples gallery was
regenerated on 16 Nov with the current build and a Pillow-enabled environment.

| Gallery | Cases | Rendered | Blank | Failed / needs API | Other |
|---------|-------|----------|-------|--------------------|-------|
| `mpl-corpus` (`@image_comparison`) | 526 | 382 | 5 | 113 failed | 26 unsupported |
| `mpl-examples` (gallery scripts) | 507 | 389 | 4 | 0 failed, 0 needs API | 114 unsupported |

The examples gallery is current. The corpus row and its pixel metrics are from the
last corpus run; they were not regenerated for these fixes. The four blank examples
are scripts whose main effect is printed output or interactive state rather than a
saved figure.

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
| G3 | **No remaining examples API errors.** The fresh examples run has 0 `needs-api` and 0 `bug` cases. The 114 unsupported cases are interactive GUI/widgets/animation, 3-D, `axes_grid1`/`axisartist`, and missing third-party modules; the 4 blanks create no saved figure. |
| G4 | **No known example failures.** EPS output and the previously failing `FT2Font`, custom-scale, custom-projection, polar-bar and boxplot-stat paths now render. SVG gallery post-processing cases are classified as unsupported rather than crashing. |
| F5 | **Pillow is available in CI and is now installed locally.** `watermark_image` renders; no environment-only `needs-api` case remains. |
| G5 | **Environment accounting is complete for this run.** Interactive forbears are classified up front, and unsupported counts no longer hide API failures. |
| F7 / N7 | **"Rendered" is not proof of correctness.** It still includes ignored calls (see the per-case `ignored` count). Treat rendered counts as an upper bound and keep the visual checks above. |

## Other checks

| # | Task |
|---|------|
| U3 | Tick count is now 8; check a 3×3 subplot grid for crowding. |

## Rust crate preparation

Goal: a native Rust crate with the same matplotlib-like API. The API (`Figure`, `Axes`, artists, locators, norms; about 10k lines) still lives in Python.

| # | Task |
|---|------|
| R1 | **Done.** `src/render.rs::render_figure` now owns validation, format routing, direct-PNG selection, cropping and encoding; `src/lib.rs` is the PyO3 adapter and maps `RenderError` to Python exceptions. |
| R2 | **Move pyo3 out of `model.rs`** into `py.rs` behind `cfg(feature = "python")`; make `pyo3` and `numpy` optional. `draw`, `layout`, `export`, `raster`, `image`, `scale`, `color` and `fonts` are already pyo3-free. Gate: `cargo test --no-default-features` builds without Python. |
| R3 | **Replace stringly-typed model fields** (`color`, `linestyle`, `marker`, `drawstyle`, `cmap`, `units`: `String`) with `Color`, `LineStyle`, `Marker`, `DrawStyle` and `Cmap` enums parsed once at the boundary; extend `color.rs` rather than add a module. |
| R4 | **Split `draw.rs`** by artist (line, scatter, bar, contour, quiver, text, collection). The `draw/` modules cover axes, series, ticks, legends and images; the remaining `draw.rs` entry point is still large. |
| R5 | **Add pure-Rust render smoke tests.** A few unit tests in `lib.rs` exist, but Python tests remain the main coverage of the Rust API. |
| R6 | **Workspace split:** `matplotvite-core` (model, layout, draw, export; no Python), `matplotvite` (builder API: `Figure::new`, `fig.subplot`, `ax.plot(&x, &y).color(..)`, `fig.savefig`), `matplotvite-py` (thin pyo3 module). CI job runs `cargo test -p matplotvite-core`. |
| R7 | **Port the `Axes` API to Rust** from `Axes._panel()`, in `TRACE.md` priority order: `plot`, `scatter`, `bar`, `hist`, `imshow`, `fill_between`, then the rest. Take slices or `ndarray` views, no copies. Optional thread-local `pyplot` layer only if requested. |
| R8 | **De-duplicate tick logic:** `_nice_step` / `Axis._ticks` in Python and `nice_ticks` / `auto_ticks` in `layout.rs` implement the same thing. Expose the Rust locators, norms and colormap lookup to Python and delete the Python copies. |
| R9 | **Shared golden-image test set** rendering the same scenes through the Python wrapper and the Rust crate, so the two front ends cannot drift. |
| R10 | **Decide the output paths:** the direct-PNG and SVG paths produce slightly different output; choose whether the crate exposes one or both before the API is public. |

## Suggested order

1. **Visual checks:** rebuild the KARIOS images, re-render `02_dx`/`04_ce`, and re-judge M2–M5, M11, M12 and M17.
2. **Corpus refresh:** regenerate `mpl-corpus`; its 113 failures are now the largest concrete gap list.
3. **R2, R3, R5** first (mechanical, keeps the 444-test Python suite as a safety net), then R4/R6 onward.
