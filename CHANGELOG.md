# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Before 1.0, a minor release may contain a breaking change; see
[CONTRIBUTING.md](CONTRIBUTING.md) for the compatibility policy.

## [Unreleased]

### Added

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

### Changed

- Legend ordering now derives from each artist's creation sequence number instead
  of a separate label-order list, preserving the bar-container-last rule.
- The coverage trace now separates implemented, accepted-and-ignored, and missing
  call sites, and its baseline fails if an implemented API becomes a no-op shim.
- Release source distributions now contain only build inputs; development
  trees, galleries, and editor state are excluded.
- Python linting covers Pyflakes, import sorting, bugbear, pyupgrade, and Ruff
  correctness rules, with mypy checking the package.

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
