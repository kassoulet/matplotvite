# Contributing to Matplotvite

Contributions are welcome, especially reproducible rendering differences,
missing Matplotlib API surface, packaging fixes, and documentation.

By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
For security issues, follow [SECURITY.md](SECURITY.md) instead of opening a
public issue.

## Development setup

You need Rust 1.88 or newer, Python 3.9 or newer, and a C compiler for the
bundled WebP sources. The extension is built with maturin:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install maturin numpy pytest ruff mypy pandas
maturin develop --release
```

`maturin develop --release` must be rerun after Rust changes. Python-only
changes take effect from the source tree immediately.

## Checks

Run the checks that cover your change before opening a pull request:

```bash
python -m pytest
ruff check python tests tools examples
python -m mypy
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings
cargo test --all-targets
cargo deny check licenses bans sources
```

The full Python suite builds and renders examples and takes a few minutes.
`pytest -m gallery` regenerates the harvested Matplotlib and Seaborn galleries;
those tests need external checkouts and are skipped by default.

The `prek` hooks run the fast checks on commit and the test suite on push. The
commit-msg hook rejects `Co-Authored-By` trailers, so do not add attribution
trailers to commits.

## Pull requests

- Keep a change focused and include a test for changed behavior.
- Update `python/matplotvite/__init__.pyi` when public Python signatures change.
- Update `CHANGELOG.md` for user-visible changes.
- State which checks you ran and any that could not run.
- Do not commit generated `dist/`, gallery, or benchmark artifacts.

## Compatibility policy

Matplotvite is pre-1.0. A breaking API change is released only in a minor
version (`0.x.0`) and must be introduced through a deprecation warning at least
one minor release before removal when practical. Patch releases are limited to
fixes and backward-compatible additions.

## Releases

Releases are cut from a `v*` tag. `Cargo.toml` is the version source; update it
and `Cargo.lock`, move the changelog entries from Unreleased, then push the tag.
The release workflow reuses the full CI matrix, validates the metadata and
installed wheel, publishes through PyPI trusted publishing, and attaches build
provenance attestations and an SPDX SBOM.
