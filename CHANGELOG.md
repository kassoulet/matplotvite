# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Before 1.0, a minor release may contain a breaking change; see
[CONTRIBUTING.md](CONTRIBUTING.md) for the compatibility policy.

## [Unreleased]

### Added

- A pandas plotting backend: set `pd.options.plotting.backend = "matplotvite"`
  to draw line, bar, barh, hist, box, area, scatter and pie charts through
  `DataFrame.plot()`/`Series.plot()`, with datetime, categorical and MultiIndex
  index handling.
- Pixel-diff coverage for the Seaborn wrappers that reduce to current API:
  lineplot bands, grouped scatter, bar errors, density histograms, box plots
  and annotated heatmaps, with committed Matplotlib references.
- A checked-in Matplotlib corpus metadata file containing every harvested
  snippet and SHA-256 baseline hash. The harvester can regenerate it with
  `--write-metadata`, fail CI when it drifts with `--check-metadata`, and render
  only changed or new snippets with `--changed-from`.
- A Cargo workspace split into `matplotvite-core` (renderer with no Python
  dependency by default), `matplotvite` (the native `Figure`/`Axes` builder) and
  `matplotvite-py` (the thin PyO3 extension). CI now tests the core crate without
  Python features, and the fuzz target builds against the builder crate.
- A Sphinx API reference built in CI and on the Pages site, a public-API
  docstring coverage gate, `docs`/`test` extras, and a runnable
  `examples/quickstart.py`.
- Coverage gates for Python branch coverage and non-Python Rust lines, property
  tests for scales, ticks and polyline decimation, and a cargo-fuzz target for
  the native panel/render path.
- A Python-enabled fuzz harness that mutates a captured figure payload through
  the real PyO3 panel extraction path, runnable under atheris or deterministically
  without extra dependencies.
- `tools/gallery_render.py` renders the site assets and writes `samples.json`,
  so `tools/build_pages.py --html-only` can build the HTML without re-rendering.
- Colour norms and colormaps are native PyO3 classes: `Normalize`, `LogNorm`,
  `PowerNorm`, `SymLogNorm`, `AsinhNorm`, `TwoSlopeNorm` and `BoundaryNorm` map
  values in Rust, and `Colormap` sampling, reversal, LUT resampling and custom
  registration no longer duplicate their logic in Python.
- A documented pre-1.0 compatibility and deprecation policy, plus a helper that
  emits user-visible `FutureWarning` messages for deprecated APIs.
- Release provenance attestations and an SPDX SBOM for every tagged release, plus
  musllinux wheels for x86_64 and aarch64.
- A release gate that reuses the full CI matrix, plus `twine check` and an
  installed-wheel rendering smoke test.
- Governance files, issue and pull-request templates, citation metadata, and
  project changelog/issue/documentation URLs.
- An explicit Python support policy covering the tested 3.9 through 3.14
  interpreters.
- `matplotvite/__init__.py` is now a re-export facade; the implementation lives
  in `_plotting.py`, with the existing satellite modules imported afterwards
  to preserve their package-level compatibility imports.
- Ticks and tick labels always render through the manual path; the plotters
  mesh now contributes only the axis frame and descriptions, so customised and
  default axes can no longer diverge.
- The Matplotlib harvester is split into harvesting (`mpl_harvest`), isolated
  rendering (`mpl_render`) and metrics (`mpl_metrics`) modules; the
  `harvest_matplotlib` CLI keeps the gallery orchestration and re-exports.
- A shared golden-image suite renders the same scenes through the Python
  facade and the native Rust builder, so the two front ends cannot drift
  without one of the two tests failing.
- A native Rust `Figure`/`Axes` builder covering `plot`, `scatter`, `bar`,
  `barh`, `hist`, `imshow`, `imshow_cmap`, `fill_between`, `contour`/`contourf`,
  `errorbar`, `quiver`, text, annotations, patches, line collections and
  colorbars, with explicit ticks, scales, grid/legend styling, aspect, `add_axes`
  and PNG/SVG/PDF/WebP/EPS output through the same renderer as the Python API.

### Changed

- `Axes` is assembled from plotting, statistics, field and decoration concern
  mixins, and its panel/custom-scale serializers are split into focused helpers,
  so the core class owns layout, ticks and lifecycle rather than every plot family.
- Supply-chain checks now include OpenSSF Scorecard, cargo-deny advisories
  with yanked-crate enforcement, reproducible-wheel verification, and PyPI,
  Python-version, licence, and scorecard badges.
- Wheel builds from the sdist are byte-for-byte reproducible. The generated
  wheel-level Rust SBOM is disabled because it embedded pip's temporary build
  path; release artifacts still carry an SPDX SBOM.
- Type stubs now cover every public export, and CI runs `mypy.stubtest`
  against the installed wheel to catch signature drift.
- Public plotting and figure calls now reject unknown keyword arguments with
  `TypeError`; recognized Matplotlib properties that are not rendered are still
  accepted and recorded as ignored. The coverage trace no longer treats
  `**kwargs` as accepting every keyword.
- Legend ordering now derives from each artist's creation sequence number instead
  of a separate label-order list, preserving the bar-container-last rule.
- The Python scale shims now delegate symlog, logit, and asinh transforms to
  Rust. Symlog uses Matplotlib's linear-inside/logarithmic-outside formula,
  asinh includes its linear width, and logit uses base-10 odds.
- Python's automatic tick positions and tick-label budget now come from the
  Rust locator, so the Python and native Rust front ends share one step
  selection; zero positions are normalized to avoid rendering `-0`.
- The coverage trace now separates implemented, accepted-and-ignored, and missing
  call sites, and its baseline fails if an implemented API becomes a no-op shim.
- A contract test keeps the Python panel payload and the Rust `Panel`, `Legend`,
  `Grid`, and `Ticks` field sets in sync.
- Release source distributions now contain only build inputs; development
  trees, galleries, and editor state are excluded.
- Python linting covers Pyflakes, import sorting, bugbear, pyupgrade, and Ruff
  correctness rules, with mypy checking the package.
- CI shards the comparison galleries into parallel corpus, examples, and Seaborn
  jobs, caches the pinned source checkouts, and renders sampled subsets on pull
  requests instead of the full galleries.

### Fixed

- `savefig`, `plot`, `hist`, `legend`, and `subplots` now match Matplotlib's
  signatures and validation, including `fname`, transparent defaults,
  metadata/pil_kwargs acceptance, length and location checks, error types, and
  keyword-only subplot arguments.
- Rust builds are checked against the declared 1.88 MSRV and a dependency
  policy for licences, duplicate versions, banned crates, and registries.

## [0.6.0] - 2026-11-13

### Added

- Matplotlib-style static plotting through a Rust extension, with PNG, SVG,
  PDF, WebP, and EPS output.
- Line, scatter, bar, histogram, box/violin, pie, stem, step, contour,
  quiver, image, mesh, hexbin, and fill helpers, including legends, labels,
  ticks, grids, colorbars, insets, and subplot layouts.
- Linear, logarithmic, symlog, logit, and asinh scales, colormaps, date and
  categorical axes, and polar and geographic projections.
- Stable-ABI wheels for CPython 3.9 and newer on Linux, macOS, and Windows,
  with NumPy as the only Python runtime dependency.
- A bundled example gallery, harvested Matplotlib and Seaborn comparisons,
  KARIOS report figures, and benchmark and visual-difference tooling.

[Unreleased]: https://github.com/kassoulet/matplotvite/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/kassoulet/matplotvite/releases/tag/v0.6.0
