# Review: performance and security

Scope: commit `d1859eb`. Rust core (`src/lib.rs`, `export.rs`, `raster.rs`, `image.rs`, `fonts.rs`, `model.rs`), the Python `savefig`/caching path, `draw.rs` hot spots (contours, polyline simplification, text measurement) and the CI/release workflows.

Not covered: a line-by-line read of all 2,092 lines of `draw.rs` and all 3,900 lines of `python/matplotvite/__init__.py`. Nothing below was profiled, so the performance items are estimates from reading the code. `bandit` and `pip-audit` were not run. `cargo audit` was run.

## Summary

The codebase is in good shape. There is no `unsafe` and no `unwrap`/`expect`/`panic!` outside tests. There is no `eval`, `exec`, `pickle` or `subprocess` in the shipped Python. The SVG overlays only contain numbers and base64. GitHub Actions are pinned by SHA and run with minimal permissions. `cargo audit` reports no vulnerabilities.

The real issues are memory ceilings that are high for untrusted input, and some avoidable repeated work in the save path.

## Security

| # | Severity | Finding |
|---|----------|---------|
| S1 | Medium (only if parameters come from untrusted users) | **Memory ceilings are high.** `lib.rs:74-90` allows a canvas of up to 2^28 px (1 GiB as RGBA). The direct PNG path adds a 3 B/px buffer, a downsampled pixmap and the output pixmap on top of that, so peak memory is roughly 2.5-3 GiB. `image.rs:9` allows images of 2^28 px. An image that large is encoded to PNG, base64'd (+33%), embedded in the SVG string and decoded again by resvg, so peak memory is several GiB. Fine for a local library. For a service that renders user-supplied sizes or images, lower both budgets (for example 2^26) or make them configurable. |
| S2 | Low | **No upper bound on binning parameters.** `hexbin(gridsize=...)` builds `centers` arrays of roughly `2·nx·ny` rows (`__init__.py` hexbin). `hist2d` and `hist` bins are likewise unchecked. A huge value allocates until the process dies. This only matters if those arguments are user-controlled. |
| S3 | Low | **SVG injection is not covered by a test.** Overlays (`draw.rs:1610, 1748, 1877, 2022`) interpolate only numbers and base64, and colours are parsed to RGBA, so these are safe. Text goes through plotters' SVG backend. I did not verify that every text and attribute path escapes `<`, `&` and `"`. Add one test that renders a title, label, tick label and legend entry containing `</text><image href="file:///etc/passwd"/>` and asserts that the SVG has no stray elements. This matters because usvg can resolve `href` paths from disk if a raw element ever slips in. |
| S4 | Low | **Release uses a long-lived token.** `publish.yml:31` uses `secrets.PYPI_API_TOKEN`. PyPI trusted publishing (OIDC, `id-token: write`, no secret) removes the token. The `environment: pypi` gate is already there, which is good. |
| S5 | Low | **Unpinned CI installs.** `pip install maturin numpy pandas pytest` and `pip install "matplotlib==3.11.2"` (`ci.yml`, `pages.yml`) are not hash-pinned or version-pinned (except matplotlib). Pin them with a constraints or requirements file. `Cargo.lock` is already used. |
| S6 | Info | **`cargo audit`: no vulnerabilities, 2 warnings.** `rustybuzz` (RUSTSEC-2026-0206) and `ttf-parser` (RUSTSEC-2026-0192) are flagged unmaintained. Both are transitive via resvg/usvg. Track them. Nothing to do now. |
| S7 | Info | **Handled well.** Canvas dimension and area are validated in both Python and Rust. `dpi` must be finite and positive. The panel cache is bounded (256 entries, 64 MiB) and keyed by a 128-bit digest. `savefig` writes only to the path the caller gives it, like Matplotlib. |

## Performance

Ordered by expected payoff.

| # | Impact | Finding and suggested fix |
|---|--------|---------------------------|
| P1 | Medium on large data | **Every array is hashed twice per `savefig`.** `_panel_cache_key` hashes each panel in full (`__init__.py:~3582`). Then `_hash_value(hasher, (..., panels, options))` hashes the same panels again (`~3600`). The arrays are then copied a third time on the way into Rust (`model.rs:30, 55`, `to_owned`; this copy is needed because the GIL is released). Fix: hash the per-panel `cache_key` strings plus `options` for the figure key instead of re-walking the data. |
| P2 | Medium for contour-heavy plots | **Contours emit one SVG element per segment.** `draw.rs:1936-1943` draws every marching-squares segment as its own `PathElement` and never joins them into polylines. A 200×200 grid with 10 levels gives tens of thousands of elements. Chain segments into polylines per level. This also gives proper line joins at segment ends. |
| P3 | Medium for single-panel PNGs | **`raster::downsample` is single-threaded and per-pixel.** `raster.rs:85-118` uses nested loops with `u64` arithmetic and a bounds-checked write per pixel. It is called once per panel, and figures with one panel get no parallelism. Use rayon over rows and specialise the 2×2 case. The background fill in `render_panel` (`raster.rs:129`) is also a per-pixel 3-byte copy. A `Vec` filled by repeating a pattern is faster. |
| P4 | Low-Medium | **Cache hits clone whole fragments.** `export.rs:189-191` returns `fragment.clone()`, a multi-MB `String` plus overlays for dense plots. Store `Arc<PanelFragment>` instead. Identical concurrent panels are also computed twice, since there is no single-flight. |
| P5 | Low-Medium | **Tight SVG/PDF bounds parse the document up to twice.** `svg_bounds` (`export.rs:323`) runs a full usvg parse, including decoding embedded base64 images, only to measure bounds. PDF output then parses again in `render_pdf`. For figures with images this is noticeable. |
| P6 | Low | **`text_width` re-parses the font on every call.** `fonts.rs:15` calls `FontRef::try_from_slice` each time. It is called per text line and per legend entry (`draw.rs:40, 404`). Cache the `FontRef` in a `OnceLock`. |
| P7 | Opportunity | **Images always take the SVG path.** `lib.rs:135` excludes any panel with images from direct PNG rendering. An `imshow` therefore goes colormap → PNG encode → base64 → SVG → resvg decode → raster. Drawing the image straight into the pixmap with tiny-skia would skip four steps. This is the biggest speed-up available for `imshow`/`pcolormesh`/`hist2d`, but it is also the biggest change. |
| P8 | Low | **Full-document `insert_str`.** `export.rs:316` inserts the background after the root tag, which shifts the whole SVG string once. Cheap next to rendering. Build the background first, or write it into the string before the body, if profiling ever points here. |

## Suggested order

1. S3 (one test), then P1 (small change, helps every save of a large figure).
2. S1/S2 (decide limits if untrusted input is in scope), P3, P6.
3. P2, P4.
4. S4/S5 housekeeping. P7 only if `imshow` speed matters.
