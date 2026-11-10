# Review: performance and security (update 2)

Scope: local `main` at `d0a191e` (now `65824ff` after the rebase). This re-checks every finding from the first review (written against `d1859eb`) and covers the code added since: bounded allocations, contour polylines, parallel downsampling, direct image drawing, the PDF rewrite, trusted publishing and pinned CI dependencies.

Not covered: a line-by-line read of all of `draw.rs` and `python/matplotvite/__init__.py`. Nothing was profiled or benchmarked, and I did not rebuild or run the test suites for this update, so "fixed" below means "the code now does the right thing", not "measured". `cargo audit` was re-run. `bandit` and `pip-audit` were not.

Note on git: local `main` had diverged from a rewritten `origin/main`. It was rebased onto `origin/main` (conflicts in `export.rs`, `lib.rs` and `visual_compare.py` resolved by keeping origin's `FigureDecorations` refactor), so the hashes above refer to the pre-rebase commits. The merged tree builds and passes the Python tests (243 passed, 3 skipped).

## Summary

All the actionable findings from the first review are fixed. The new code is sound, and I found no new security issues. There are two minor correctness differences (X1, X2) and a few small leftovers.

## Status of the first review

| # | Finding | Status | Evidence |
|---|---------|--------|----------|
| S1 | High memory ceilings | **Fixed** | Canvas and image budgets are now 2^26 px in `lib.rs:75`, `raster.rs:19`, `image.rs:9` and Python `_MAX_CANVAS_AREA`. |
| S2 | Unbounded bins and gridsize | **Mostly fixed** | `_validate_bins` caps bins at 4096, bin cells at 4M and edge arrays at 100k. `hexbin` is also capped. Gaps: see L1. |
| S3 | No SVG-injection test | **Fixed** | `test_svg_text_is_escaped` covers the title, xlabel, tick labels and legend with a hostile payload. |
| S4 | Long-lived PyPI token | **Fixed** | `publish.yml` now uses `id-token: write` (trusted publishing) and no secret. |
| S5 | Unpinned CI installs | **Mostly fixed** | `.github/requirements-ci.txt` pins exact versions and every `pip install` uses `-c`. Left: `pip install --upgrade pip` and `ruff` are unconstrained and nothing is hash-pinned. |
| S6 | `cargo audit` warnings | **Unchanged** | No vulnerabilities. Two "unmaintained" warnings: `rustybuzz` (RUSTSEC-2026-0206) and `ttf-parser` (RUSTSEC-2026-0192), both indirect. The new `pdf-writer` dependency raised no advisory. |
| P1 | Data hashed twice per save | **Fixed** | The figure key now hashes the per-panel `cache_key` strings (`__init__.py:~3638-3643`), not the arrays again. |
| P2 | One SVG element per contour segment | **Fixed** | `contour_polylines` joins segments into polylines. Shared endpoints match exactly because adjacent cells interpolate the same pair of values in the same order. |
| P3 | Single-threaded downsample | **Fixed** | `downsample` runs over rows with rayon, with a 2×2 fast path. |
| P4 | Cache hits clone fragments | **Fixed** | The panel cache stores `Arc<PanelFragment>`. There is still no single-flight (two identical panels rendered at once are both computed). |
| P5 | Tight PDF parsed the SVG twice | **Fixed** | `render_pdf` measures bounds in its single parse (`d0a191e`). Tight SVG still parses once with usvg, which is unavoidable. |
| P6 | Font re-parsed per call | **Fixed** | `text_width` uses a cached `OnceLock<Option<FontRef>>`. |
| P7 | Images always took the SVG path | **Fixed, with caveat** | Large images (≥ 512×512) are now drawn straight into the bitmap. See X1. |
| P8 | `insert_str` shifts the SVG once | **Open, negligible** | `export.rs:454` is unchanged. Not worth touching without a profile. |

## New findings

| # | Severity | Finding |
|---|----------|---------|
| X1 | Low (correctness) | **Large images ignore `interpolation`.** `image_rgb` (`image.rs`) always samples nearest-neighbour. Images under 512×512 still go through the SVG path, where `bilinear`, `bicubic` and `antialiased` are honoured by resvg. So the same call gives different output on either side of the size cutoff. Also, large images shown smaller than their source alias, since nearest sampling does not average. This is consistent with the new `nearest` default, but not with an explicit `interpolation="bilinear"`. Either route explicit non-nearest interpolation to the SVG path in `direct_eligible`, or implement bilinear in `image_rgb`. |
| X2 | Low (correctness) | **PDF background drops alpha.** `render_pdf` fills the page with `bg.0/.1/.2` only (`export.rs`, `content.set_fill_rgb`). A `facecolor` with alpha is painted opaque in PDF, but blended over white in PNG (`background_pixel`). Rare, easy to fix by pre-blending with white as `background_pixel` does. |
| X3 | Low (maintainability) | **PDF output depends on svg2pdf internals.** The page is assembled by hand from `svg2pdf::to_chunk` plus `pdf-writer`, assuming the returned XObject is a 1×1 unit square. There is also a workaround for a usvg 0.45 image-bounds bug (`pdf_node_bounds`). Both are likely to break silently on an svg2pdf or usvg upgrade. The tests added in `d0a191e` cover the crop. Keep them as the upgrade gate and note the coupling in the Dependabot PR checklist. |
| X4 | Low (performance) | **`image_rgb` is single-threaded.** It samples with per-pixel `u64` divisions over the display size. It is only used for images ≥ 512×512, which is exactly where parallelism pays. Row-parallel rayon and hoisting the `x * sw / width` column map would remove most of the cost. |
| X5 | Info | **`contour_polylines` uses `Vec::insert(0, …)`** when extending backwards, which is O(n) per insert, so O(n²) on very long open contours. Closed loops (the common case) never hit it. At realistic sizes this is milliseconds. Only change it if a profile points here. |
| L1 | Low | **Bin validation gaps.** Two-element lists of edge arrays (`hist2d(bins=[xedges, yedges])`) skip `_validate_bins`, because the array is ragged or has object dtype. String bins such as `"auto"` pass through unchecked (NumPy bounds those by the data). Edge-array length is only checked for 1-D input. Cheap to extend if S2 matters for your threat model. |
| L2 | Info (behaviour) | **1-D `hist` is now capped at 4096 bins**, where Matplotlib has no cap. Reasonable, but it is a compatibility difference worth a line in the README. |

## Still good

No `unsafe`. No `unwrap`/`expect`/`panic!` outside tests (the only ones are in the PNG decode test helper in `lib.rs`). No `eval`, `exec`, `pickle` or `subprocess` in the shipped Python. SVG overlays contain only numbers and base64. Actions are pinned by SHA with minimal permissions, and publishing is OIDC-based.

## Suggested order

1. X1 (decide: route non-nearest interpolation to the SVG path, or implement bilinear). This is the only one that changes visible output.
2. X2 (one-line blend), then X4 if large `imshow` speed matters.
3. L1/L2 and the S5 leftovers when convenient. S6 and X3 are watch items.
