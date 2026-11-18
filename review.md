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
| R7 | **Port the `Axes` API to Rust** from `Axes._panel()`, in `TRACE.md` priority order: `plot`, `scatter`, `bar`, `hist`, `imshow`, `fill_between`, then the rest. Take slices or `ndarray` views, no copies. Optional thread-local `pyplot` layer only if requested. |
| R8 | **De-duplicate tick logic:** `_nice_step` / `Axis._ticks` in Python and `nice_ticks` / `auto_ticks` in `layout.rs` implement the same thing. Expose the Rust locators, norms and colormap lookup to Python and delete the Python copies. |
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
| Q4 | **Partly done — Rust side.** `symlog`, `logit`, `asinh_scale` and `asinh_inverse` now live in `scale.rs` with their tests; `draw.rs` and `draw/ticks.rs` import them. `python/matplotvite/scale.py` still duplicates the formulas; exposing the Rust transforms and deleting those copies remains part of R8. |
| Q5 | **Remove the Python/Rust panel contract duplication:** `_panel()` builds a dict whose keys are re-declared in `src/model.rs` (866 lines) and read by hand in `py.rs`. Generate one from the other (a `serde` model with `pythonize`, or a schema test that fails when the key sets differ) so adding a field is a one-place change, as with the recent `yside`/`legend.order` additions. |
| Q6 | **Unify the two tick paths in `draw/ticks.rs`/`draw/axes.rs`.** The plotters mesh path and `draw_manual_ticks` produce different results (K1, K2, K5 were all path-dependent). Route every axis through the manual path once it matches the mesh output on the golden images, then delete the mesh-label code and the `manual` heuristic in `axes.rs`. |
| Q7 | **Typed legend/label ordering in Python:** `_Stamped` plus `_label_order`/`_container_order` is a side channel. Give each artist a creation sequence number (`Artist._seq`) and sort at `legend()` time; delete `_Stamped`. |
| Q8 | **Tools:** `tools/harvest_matplotlib.py` (1.3k) and `tools/build_pages.py` (1.3k) mix harvesting, rendering, metrics and HTML. Split rendering/metrics from HTML templates so CI can run the render step alone (see CI note below). |
| Q9 | **CI galleries (716 s, the long pole):** the examples gallery already skips Matplotlib references; the remaining time is our own renders and comparison metrics. Profile per step, then (a) shard the corpus/examples/seaborn steps into parallel jobs, (b) cache `dist/sdist`, `dist/mpl-src` and `dist/sns-src` keyed on the version pins instead of re-downloading, (c) run the full gallery only on `main` and a sampled subset on pull requests. |

## Conformance and OSS practice audit (17 Nov)

Architecture is sound (Rust core, thin pyo3 adapter, abi3 wheels, SHA-pinned CI, dual licence, audit tooling, baselined benchmarks, no `unsafe`). Gaps are in the honesty of the coverage numbers, typing, release safety and project governance.

| # | Task |
|---|------|
| C1 | **Unknown kwargs are silently accepted** on `plot`, `scatter`, `bar`, `hist`, `imshow`, `legend`, `subplots` (561 `**kwargs` signatures; `_ignored` is called from only 65 shims). Raise `TypeError`/warn like Matplotlib. Make `tools/trace_unsupported.py::accepted_kwargs` treat `**kwargs` as unknown, so TRACE.md stops overstating (96% is an upper bound). |
| C2 | **"Supported" counts no-op shims** (`set_axisbelow`, `set_xmargin`, `set_frame_on`, `label_outer`, `secondary_xaxis` returning `self`). Split TRACE.md into implemented / accepted-and-ignored / missing. |
| C4 | **`__init__.pyi` covers 94 of 239 public names** and drifts (`set_xlim(lo, hi)` vs `left/right`; missing `norm`, `pad_inches`, `handles/labels`, `**kwargs`). Extend or generate the stubs and add `mypy.stubtest` to CI; today only a test that the file exists. |
| C5 | **Parity of signatures and validation:** `savefig` first parameter `filepath` (Matplotlib: `fname`), `transparent` default, `metadata`/`pil_kwargs` rejected; `plot` length mismatch, bad `linestyle` and bad `legend(loc=)` accepted; `hist(histtype=)` raises `NotImplementedError` not `ValueError`; `subplots` keyword-only rules and message text. |
| C8 | **musllinux wheels** (x86_64, aarch64); consider a free-threaded 3.14 test. |
| C14 | **Coverage and robustness:** `pytest-cov` + `cargo-llvm-cov` with a threshold; only 43 Rust unit tests. Add proptest/hypothesis for scales, ticks and decimation, and a cargo-fuzz target for the panel parser. |
| C15 | **Docs:** API reference site (mkdocs/sphinx) built in CI, docstring coverage for the ~105 public functions, user-facing `examples/` (current directory holds test fixtures), `test`/`docs` extras. |
| C16 | **Python support policy:** state the 3.9 EOL decision, run every supported minor in CI (3.11/3.12/3.14 gaps), align classifiers. |
| C18 | **No API stability or deprecation policy:** no `FutureWarning`/`DeprecationWarning` helper, `__all__` unchecked against the stubs, no semver statement for a `0.x` crate/package. Add `_deprecated()` plus a policy paragraph in CONTRIBUTING/README (breaking changes only in minor versions before 1.0, one release of warning). |

## Suggested order

1. **V1:** rebuild the KARIOS images, re-render `02_dx`/`04_ce`, and finish the pixel-level sign-off.
2. **R6** onward (R7 after Q1).
3. **Q4**, then **Q1** before **Q2**; **Q5** before adding more model fields; **Q9** whenever CI time matters.
4. **C1/C2/C4** → **C7/C9/C11** → the rest of C.
