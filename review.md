# Review: performance, security and Matplotlib parity (open issues)

Scope: `main` after the compatibility-shim, table, polar and gallery-reference changes. Closed findings have been removed; this file lists what is still open. The examples gallery was regenerated on 15 Nov with the current build.

Results on this tree: Python suite 427 passed, 7 skipped; `ruff`, `cargo fmt`, `cargo clippy` and `cargo test` clean. The `mpl-examples` gallery renders the original script with Matplotlib beside every Matplotvite output, and every comparison row has a collapsible source block, so failed and blank cases have a reference image.

| Gallery | Cases | Rendered | Blank | Failed / needs API | other |
|---------|-------|----------|-------|--------------------|-------|
| `mpl-corpus` (`@image_comparison`) | 526 | 382 | 5 | 113 failed | 26 unsupported |
| `mpl-examples` (gallery scripts) | 507 | 377 | 2 | 19 needs API | 0 harvester gaps, 3 bugs, 106 unsupported |

The examples gallery is current. The corpus row and its pixel metrics are from the last corpus run; they were not regenerated for this change.

## High

No open high-severity findings. All 23 `axes_grid1` and all 17 `axisartist` gallery cases now render.

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
| G3 | **Remaining examples API gaps (19):** `NonUniformImage`; `matplotlib.image`, `matplotlib.scale` and `matplotlib.colorizer`; hand-built contour paths and manual `clabel`; per-pixel alpha arrays; `stackplot(baseline="wiggle")`; `stairs(orientation="horizontal")`; `PdfPages`; `FT2Font.set_charmap`/`num_named_instances`; `ContourSet.set_linestyle`; `BboxConnector`; radar `set_varlabels`; boxplot/`time_series_histogram` styling. 3-D remains out of scope. |
| G4 | **Known example failures (3):** `rasterization_demo` saves EPS (only PNG/SVG/PDF/WebP are encoded); `svg_filter_line` and `svg_filter_pie` ask `ElementTree.XMLID` for gids that the SVG backend does not emit yet. |
| F5 | **Environment cases:** install Pillow in the gallery job (`image_demo`, `image_clip_path`, `demo_annotation_box`, `demo_text_path`, `demo_ribbon_box`, `mathtext_asarray`); `units/*` now uses the bundled converter registry. |
| E5 | **One-line API gaps:** `Axes.set()` rejects unknown keywords and `Axes.twin()` takes no argument. |

## Accounting, tests and trust

| # | Finding |
|---|---------|
| G5 | **Environment accounting:** 9 examples need `gi` and 7 need `wx`; `user_interfaces` (25), `widgets` (16) and `animation` (10) are interactive by nature and should be `unsupported` up front. Local runs should also state when `cairosvg`/`pypdfium2` are missing, because SVG/PDF baselines then get no metric. |
| F7 / N7 | **"Rendered" is not proof of correctness.** It still includes ignored calls (see the per-case `ignored` count). Treat rendered counts as an upper bound and check the remaining float-conversion cases did not merely move into `needs-api`. |

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

1. **G4 and G3**: triage the crash groups, then the remaining API gaps.
2. **G5/E6**: finish the environment accounting and the remaining harvester test.
3. Rebuild the KARIOS images, re-render the four pairs, and re-judge every "(image)" item listed above.
