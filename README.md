# Matplotvite

[![CI](https://github.com/kassoulet/matplotvite/actions/workflows/ci.yml/badge.svg)](https://github.com/kassoulet/matplotvite/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.6.1--alpha-blue)](ROADMAP.md)

> **Experimental.** Matplotvite is under active development. Its API may change
> between releases, and it does not cover the full matplotlib surface. Validate
> output before relying on it in production.

Matplotvite renders matplotlib-style static figures from Python through a compiled
Rust extension (PyO3 + plotters). It writes PNG, SVG, PDF, and WebP, and NumPy is its
only Python runtime dependency.

- [Example gallery](https://kassoulet.github.io/matplotvite/)
- [Performance measurements](https://kassoulet.github.io/matplotvite/benchmarks.html)
- [Architecture](architecture.md)
- [Supported API](#whats-supported)

## Install

```bash
pip install matplotvite
```

Wheels are published to PyPI from each `v*` version tag: Linux (x86_64, aarch64),
macOS (arm64, x86_64) and Windows (x64, arm64). They use the stable ABI, so a single
wheel serves CPython 3.9 and newer; other platforms install from the sdist.

The latest release is 0.6.0; version tags after it publish automatically.

### Build from source

```bash
pip install maturin numpy
maturin develop --release
```

## Measured performance

Representative end-to-end timings from `tools/benchmark.py`. The comparison is
against matplotlib's Agg backend on the same figures and data; treat the ratio as
machine- and load-dependent, not as a general guarantee.

| Workload | Matplotvite | matplotlib | Ratio |
|---|---:|---:|---:|
| Single line, 100 points, PNG | 5.11 ms | 161.48 ms | 31.6× |
| Single line, 1,000 points, PNG | 6.23 ms | 131.82 ms | 21.1× |
| Single line, 10,000 points, PNG | 6.78 ms | 137.12 ms | 20.2× |
| Single line, 100,000 points, PNG | 30.04 ms | 192.15 ms | 6.4× |
| Five series, 2,000 points each, PNG | 13.74 ms | 197.95 ms | 14.4× |
| 2×2 subplot grid, PNG | 10.85 ms | 268.86 ms | 24.8× |
| Scatter, 5,000 points, PNG | 11.27 ms | 276.89 ms | 24.6× |
| Scatter, 50,000 points, PNG | 26.16 ms | 145.35 ms | 5.6× |
| Bar chart, 20 categories, PNG | 5.89 ms | 169.14 ms | 28.7× |
| Filled contours, 160×160, PNG | 34.49 ms | 108.65 ms | 3.2× |
| Hexagonal bins, 5,000 points, PNG | 21.16 ms | 154.18 ms | 7.3× |
| SVG export, 1,000 points | 0.95 ms | 116.29 ms | 121.9× |
| PDF export, 1,000 points | 3.16 ms | 134.02 ms | 42.3× |
| Cold CLI process, plot, and save | 146.30 ms | 762.00 ms | 5.2× |

The suite now measures 25 workloads, including line scaling, dense SVG export,
subplots, scatter up to 50,000 points, bar, histogram, box/violin summaries,
contour fills and lines, image and quad-mesh rendering, 2-D histograms,
hexagonal bins, quiver fields, datetime axes, repeated saves, and SVG/PDF output.
The full matrix and methodology are on the
[benchmark page](https://kassoulet.github.io/matplotvite/benchmarks.html).

Dense line series are simplified to sub-pixel resolution before drawing, dense
series, scatter and collection markers are composited into a raster layer for
PNG/WebP, and hexbin cells and filled-contour interiors are drawn in batches;
those keep the slow paths bounded by output resolution instead of input size.

Measured on a Linux x86_64 host (Python 3.14, matplotlib 3.10.7). Wall-clock
times vary with machine load and should be reproduced on the target system.

## Criterion benchmarks

The Rust output stages have a separate Criterion suite:

```bash
cargo bench --bench render
```

It measures SVG rasterization at three figure sizes plus dense-line and
filled-polygon fixtures, PNG encoding at fast/default/best compression, lossless
WebP encoding, and vector PDF conversion. Results are written under
`target/criterion/`; use `--quick` for a short smoke run. CI runs the quick suite,
reports it against `benches/criterion_baseline.json` with
`tools/criterion_guard.py` (advisory 25% budget, `--fail` to enforce), and uploads the estimates as
workflow artifacts. Refresh the baseline with:

```bash
cargo bench --bench render -- --quick
python tools/criterion_guard.py target/criterion benches/criterion_baseline.json --write
```

## Dependencies

The wheel is a compiled Rust extension. No C/C++ sources are compiled and there is no
system graphics stack (Cairo, Pango, fontconfig) to install. Python needs only NumPy
at runtime.

| Layer | Dependency | Language / boundary |
|---|---|---|
| Python runtime | `numpy` | the only required Python package |
| Native FFI | `pyo3` → CPython, `numpy` crate → NumPy C API | **non-Rust boundary**: CPython and NumPy are C/C++; these crates contain `unsafe` FFI code |
| Native FFI | `libc`, `memmap2` (via `fontdb`) | **non-Rust boundary**: OS/libc bindings, used for memory-mapped font files |
| Rendering | `plotters` | Rust |
| Rendering | `resvg`, `usvg`, `tiny-skia` | Rust (`tiny-skia` contains some `unsafe` SIMD internals) |
| Rendering | `svg2pdf`, `pdf-writer`, `png` | Rust |
| Text | `fontdb`, `ttf-parser`, `rustybuzz`, `subsetter` | Rust; only the embedded DejaVu Sans and Geist faces are loaded |
| Fonts | DejaVu Sans regular/bold, Geist serif/mono TTFs | Bitstream Vera / OFL, embedded in the binary (see `assets/fonts/`) |
| Build | Rust stable, `maturin`, CPython (with development headers) | NumPy is only needed to import the built module |

Matplotvite itself contains no `unsafe` code. All non-Rust code sits behind the
`pyo3`/`numpy` and `libc` bindings; nothing on the drawing path shells out or links
a C library directly.

Type stubs (`.pyi`) and the PEP 561 `py.typed` marker ship in the wheel, so editors
and type checkers see the public API. Wheels use CPython's stable ABI
(`cp39-abi3`), so one build per platform supports Python 3.9 and newer.

## Usage
```python
import numpy as np
import matplotvite as plt

x = np.linspace(0, 10, 200)
plt.figure(figsize=(8, 5))
plt.plot(x, np.sin(x), label="sin", color="red")
plt.plot(x, np.cos(x), label="cos")
plt.xlabel("x"); plt.ylabel("y"); plt.title("Demo"); plt.legend()
plt.savefig("demo.png")  # or "demo.svg" / "demo.pdf" / "demo.webp"
```

Gridded data, contours and a colorbar:
```python
import numpy as np
import matplotvite as plt

x = np.linspace(-3, 3, 120)
y = np.linspace(-3, 3, 120)
z = np.exp(-(x[None, :] ** 2 + y[:, None] ** 2))

plt.figure(figsize=(6, 4))
plt.contourf(x, y, z, levels=8)
plt.colorbar(label="density")
plt.title("Gaussian bump")
plt.savefig("contours.png")
```

## What's supported

### Line and marker plots
- `plot(x, y, label=, color=)` — NumPy arrays, zero-copy through PyO3
- `plot(data=df, x="col_x", y="col_y")` — pandas DataFrame/Series input, with
  the Series name used as the default label and its index used when `x` is omitted
- `datetime`/`datetime64`/pandas `Timestamp` x values — matplotlib date numbers,
  calendar-aligned date ticks, explicit date limits/ticks, and time-of-day labels
- string x values — categorical positions with tick labels and normal bar alignment
- `plot` styling: `linestyle`/`ls`, `linewidth`/`lw`, `marker`, `markersize`/`ms`,
  `markerfacecolor`/`mfc`, `markeredgecolor`/`mec`, `markeredgewidth`/`mew`, `alpha`,
  `drawstyle="steps-pre"|"steps-post"`, and fmt shorthand (`plot(x, y, "r--o")`)
- Titles, labels, legends and text accept a small `$...$` math subset: `x^2`,
  `e^{-x}`, subscripts, fractions, roots and Greek/symbol commands such as `\alpha`
  (DejaVu Sans renders letters and signs as Unicode scripts; the Geist faces keep
  a parenthesized fallback for glyphs they do not contain)
- Colors: all 148 CSS4 names (plus `tab:*` aliases), hex strings, RGB/RGBA tuples,
  `C0`–`C9` and `0`–`9` cycle references, and `"none"`/`"transparent"`
- `scatter(x, y, s=, c=, alpha=, cmap=, marker=)` — per-point sizes and colours,
  markers `o s ^ v < > D x + .`, with a legend handle when labelled
- `errorbar(x, y, yerr=, xerr=, fmt=, capsize=, ecolor=)` — scalar, per-point or
  `(2, N)` asymmetric errors, optional caps, and `fmt` markers
- `quiver(X, Y, U, V)` / `quiver(U, V)` — vector-field arrows with `scale`,
  `pivot`, per-arrow colours and head sizing
- `specgram(x, NFFT=, Fs=, noverlap=, cmap=)` — short-time spectrum computed with
  NumPy and drawn through `imshow`
- `bar(x, height, width=, bottom=, color=, edgecolor=, align=, alpha=, yerr=)` and
  `barh(...)` — single or per-bar colours, optional edge and error bars; returns a
  `BarContainer` whose handles support `set_facecolor`/`set_alpha`, with a legend swatch
  when labelled
- `bar_label(container, labels=, fmt=, label_type=, padding=)` — value labels on bars;
  `padding` is in points, like Matplotlib
- `grouped_bar(data, tick_labels=, labels=, bottom=)` — side-by-side bars for a
  mapping or 2-D array, returning one `BarContainer` per series
- `hist(x, bins=, density=, cumulative=, orientation=, color=)` — drawn over `bar` (or as a `step`/`stepfilled` outline),
  returning `(counts, edges, handles)`; for safety, a 1-D histogram is capped at 4096 bins (Matplotlib has no such cap)
- `step(x, y, where="pre"|"post"|"mid")` and `stairs(values, edges=, baseline=, fill=)` —
  staircase lines, with optional fill to a baseline
  (`where="mid"` places corners at interval midpoints)
- `boxplot(x, notch=, vert=, patch_artist=, labels=)` — boxes, whiskers, caps,
  medians and fliers from the 1.5-IQR rule, with notched outlines, horizontal
  orientation and optional filled boxes
- `violinplot(dataset, positions=, vert=, widths=)` — Gaussian-KDE violins with
  optional mean, median, extrema and quantile lines
- `stem(x, y, linefmt=, markerfmt=, basefmt=)` — segments plus markers and a baseline (`orientation="horizontal"` works)
- `pie(x, labels=, autopct=, colors=, explode=, startangle=)` — filled wedges with
  equal aspect, returning `(wedges, texts, autotexts)`
- `stackplot(x, *ys, colors=, alpha=)` — cumulative filled layers (`baseline="zero"` or `"sym"`)
- `eventplot(positions, lineoffsets=, linelengths=, colors=)` — one short line per
  event, one row per positions array
- `broken_barh(xranges, yrange, colors=)` — `(start, width)` pairs as bars, edge colour and alpha honoured
- `minorticks_on()`/`minorticks_off()` — recorded, but minor ticks are not drawn
- `setp(artist, **kwargs)` / `getp(artist, *names)` — generic `set_*`/`get_*` dispatch;
  unknown names raise `AttributeError`, and values are not validated
- `tight_layout`/`subplots_adjust`/`set_in_layout` — accepted as no-ops (window-fitted
  panels, so there is nothing to negotiate)
- `axline(xy1, xy2=, slope=)` — infinite line clipped to the axes, excluded from limits
- `rc("lines", linewidth=2)`, `rc_context`, `rcParams`, `rcdefaults` — recorded settings
  with restore-on-exit; `lines.linewidth`, `lines.markersize`, `lines.markerlinewidth`,
  `axes.labelsize`, `axes.titlesize`, `font.size`, `font.family`, `legend.fontsize`,
  `figure.dpi` and `image.interpolation` affect output. `font.family` selects one of
  the embedded faces (`sans-serif`/`DejaVu Sans`, `serif`/`Geist Serif`,
  `monospace`/`Geist Mono`); `title`/`xlabel`/`ylabel`/`text`/`suptitle`/`legend`
  accept `fontfamily=` to override it for that artist
- `fill_between(x, y1, y2, where=, color=, alpha=)`, `fill_betweenx` and `fill(...)` —
  filled polygons; `where` masks split into separate runs, `label=` gives a legend swatch
- `axhline`/`axvline`/`axhspan`/`axvspan` — reference lines and bands over axes-fraction
  ranges, resolved against the final limits
- `hlines(y, xmin, xmax, colors=, linestyles=)` / `vlines(...)` — segment collections with optional `linewidths`
- `set_xscale("log")`/`set_yscale("log")`, `semilogx`, `semilogy`, `loglog` and the
  `xscale`/`yscale` pyplot shims — artists and limits map through log10, with base-aware
  tick labels (`base=` honoured, `symlog` raises)

### Gridded data
- `imshow(X, cmap=, vmin=, vmax=, extent=, origin=, aspect=, interpolation=, alpha=)` —
  2-D arrays mapped through a colormap, or `(H, W, 3|4)` RGB(A) arrays; supports
  nearest/antialiased/bilinear interpolation hints and constant opacity
- `contour(..., linewidths=, alpha=)` / `contourf(..., alpha=)` — style iso-lines and
  filled bands without changing the geometry
- `colormaps`, `get_cmap(name)`, `cm` and `set_cmap` — all 182 matplotlib colormap
  names (including every `_r` reversal), with per-colormap lookup tables embedded
  in the wheel so matplotlib is not a runtime dependency
- `contour(X, Y, Z, levels=, colors=, cmap=)` — marching-squares iso-lines
- `contourf(X, Y, Z, levels=, colors=, cmap=)` — filled iso-bands
- `pcolormesh(X, Y, Z, cmap=, vmin=, vmax=)` — quad mesh through the image path
  (also `pcolor`/`pcolorfast`; edges or cell centres accepted)
- `hist2d(x, y, bins=, cmap=, cmin=, cmax=)` — 2-D histogram rasterised through
  the image path; returns `(counts, xedges, yedges, image)`
- `hexbin(x, y, gridsize=, C=, cmap=, mincnt=)` — hexagonal binning with
  colormap-mapped cells; returns a collection of counts and cell centres
- `matshow(Z, ...)` — a 2-D array through `imshow`, defaulting to an equal aspect
  and the origin at the top
- `contours.clabel(levels=, fmt=, colors=, fontsize=)` — label each contour level
  at the midpoint of its longest segment (`manual=True` raises)
- `colorbar(mappable, ax=, label=)` — gradient strip with min/mid/max ticks, one per axes

### Axes and layout
- `figure(figsize=, dpi=, facecolor=, edgecolor=)` / `subplots(...)` pass-through,
  `subplot`, `gca`, `gcf`, `axes`
- `xlabel` / `ylabel` / `title` (all with `fontsize=`), `legend(...)`, `xlim` / `ylim`
- `legend(loc=, ncol=, frameon=, fontsize=, title=, title_fontsize=, bbox_to_anchor=)` —
  cardinal/2-tuple locations, multi-column layouts, titles and axes-fraction anchors
- `xticks(ticks, labels=, rotation=, fontsize=)` / `yticks(...)` — manual ticks whose
  labels, rotation and size are rendered
- Tick locators and formatters through `ax.xaxis` / `ax.yaxis`: `MultipleLocator`,
  `MaxNLocator`, `LinearLocator`, `LogLocator`, `FixedLocator` and `FixedFormatter`;
  the resulting tick positions and labels are rendered
- `tick_params(axis=, labelsize=, length=, width=, color=, rotation=)` — label and tick
  mark styling
- `grid(visible, axis="both", linestyle=, linewidth=, alpha=, color=)` — styled gridlines
- `text(x, y, s, color=, fontsize=, ha=, va=, transform=)` — data, `ax.transAxes` or
  `fig.transFigure` coordinates, with `\n` line breaks; `annotate(text, xy, xytext=)`
  adds a straight arrow, and `fig.text(...)` / `plt.figtext(...)` place
  figure-fraction text above the panels
- `set_aspect("equal" | "auto" | <number>)` — shrinks the plotting box, like
  matplotlib's `adjustable="box"` (images default to `"equal"`)
- `savefig(path | file-like | None, format=, dpi=, bbox_inches="tight", transparent=,
  facecolor=, edgecolor=, compression=)` — PNG, SVG, vector PDF (text stays selectable;
  the page is sized from `figsize`) and lossless WebP; no path returns `bytes`. PNG
  compression is `"fast"` (default), `"default"`, or `"best"`
- `GridSpec` and `SubplotSpec` via `fig.add_gridspec(...)`, including row/column spans
  and `width_ratios`/`height_ratios`; `subplot2grid((rows, cols), (row, col),
  rowspan=, colspan=)` for the same layout shortcut
- `figaspect(aspect)` returns a `(width, height)` pair for an aspect ratio
- `ax.inset_axes([x, y, w, h])` for child axes placed in parent-axes fractions
- `fig.add_axes([x, y, w, h])` where the rectangle is the plotting area, not a panel
  that includes tick and label margins
- `matplotvite.mpl_toolkits.axes_grid1.inset_locator.inset_axes` /
  `zoomed_inset_axes` for the common inset-locator calls
- `subplot_mosaic(...)` with named panels and empty cells
- `twinx()` / `twiny()` for independent scales on a shared panel
- `fig.suptitle(...)` and `fig.subplots(..., sharex=, sharey=, squeeze=)`
- `style.use`, `style.context`, `style.available`, and `rcParams` style presets
- `set(**kwargs)` shorthand, `axis("off" | "on" | "equal" | "scaled" | [limits])`,
  `invert_xaxis`/`invert_yaxis`

The inset-locator shim lives under `matplotvite.mpl_toolkits`; the wheel does not
install a top-level `mpl_toolkits`, so it cannot overwrite or shadow Matplotlib's
`axes_grid1`, `mplot3d`, or `axisartist`. Existing code that imports
`mpl_toolkits.axes_grid1.inset_locator` should switch to the scoped path above
when using matplotvite without Matplotlib installed.

### Introspection

`get_xlim`/`get_ylim`, `get_position`, `get_window_extent`, `get_visible`/`set_visible`,
`remove`, `clear`, `add_artist`/`add_patch`, `get_children`, `get_transform`,
`get_figure`, `get_facecolor`, and `get_alpha`. Visibility, removal, and custom tick
positions/labels are honoured by the renderer.

### Compatibility no-ops

`show`, `draw`, `pause`, `ion`, `ioff`, `update`, `margins`, `autoscale`,
`set_clip_on`, `set_path_effects`, `xkcd`, `quiverkey`, `label_outer`,
`secondary_xaxis`/`secondary_yaxis`, `set_xmargin`/`set_ymargin` and
`locator_params` are accepted for source compatibility. `psd` and
`magnitude_spectrum` are accepted and draw nothing, and `barbs` is drawn as a
quiver of arrows. Shims that cannot affect the renderer emit a one-time
`RuntimeWarning`, and the harvested gallery manifests count ignored calls per case.

### Not supported

- `streamplot`, polar plots, 3-D axes, `Axes.table`, tripcolor/tricontour, and
  other specialised matplotlib modules
- a pandas `.plot()` backend (planned for 0.7)
- interactive display (planned for a future GPUI-based version)

## Coverage

`TRACE.md` tracks how many call sites from matplotlib's own test suite matplotvite
accepts — currently **9 602 / 10 098 (95%)**. CI re-runs the trace against
matplotlib 3.11.2 and fails if coverage drops (`tools/trace_unsupported.py --check`).

## Examples and benchmarks

The gallery and performance pages are generated from the repository:

```bash
python tools/build_pages.py --out dist
# open dist/index.html or dist/benchmarks.html in your browser
```

The gallery source lives in `examples/samples.py`. Every entry is executed both by
the page generator and by `tests/test_samples.py`.

To run the live benchmark suite:
```bash
python tools/benchmark.py
python tools/visual_compare.py visual --json visual_diff.json
```

The visual comparison renders every gallery case through Matplotlib and
matplotvite and records per-snippet RMS and visibly-different-pixel percentages.
It also runs the examples from `examples/samples.py` (skipping any whose optional
dependency is missing), so the page covers the same material as the gallery.
CI uploads `visual_diff.json` with the side-by-side HTML gallery. Add
`--format svg` to export both sides as SVG first; the Pages build does that and
writes `dist/svg-comparison.html`, linked from the galleries page.

### Harvested comparison galleries

Three more galleries use other projects' own material instead of the sample
list (build the extension first with `maturin develop --release`):

```bash
# Matplotlib's @image_comparison cases; needs an sdist or git checkout, because
# the wheel ships the tests but not their baseline images.
python tools/harvest_matplotlib.py --out dist/mpl-corpus
# Matplotlib's gallery examples (a sparse checkout of galleries/examples is enough).
python tools/harvest_matplotlib.py --examples path/to/matplotlib --out dist/mpl-examples
# Seaborn's examples, classified pass / needs-API / unsupported.
python tools/harvest_seaborn.py --out dist/seaborn-gallery
```

Each writes an `index.html` and a `manifest.json`; the baseline gallery copies its
reference images alongside the page so it stays browsable when moved. The pixel
metrics read PNGs through Matplotlib, so without it the corpus gallery still
renders and records `metrics_error` per case. PDF, SVG, and EPS baselines are
rasterised at the rendered PNG's size when `pypdfium2`, `cairosvg`, and Ghostscript
respectively are available. These are gitignored build artifacts under `dist/`.
To regenerate all three as a check:

```bash
pytest -m gallery
```

The `gallery` tests are skipped in the default run (and skip individually when the
checkouts are missing). CI rebuilds the same galleries, uploads them as the
`galleries-<sha>` artifact for each commit, and writes the per-gallery status
counts and artifact link into the job summary.

These harvested snippets run in-process with the same filesystem and network
permissions as the caller. Only run them against the pinned Matplotlib and Seaborn
versions used by CI, never an unpinned checkout. The rendered counts are an upper
bound: helper code imported from those projects can do part of the work.

Opaque PNG figures with multiple panels, or at least 1,000 plotted primitives,
render through a 2× oversampled bitmap backend and skip SVG generation and resvg.
Small single-panel plots, marker-heavy panels, transparent output, embedded images,
WebP, SVG, and PDF keep the existing vector path; dense markers use its batched
raster-marker layer instead.

Subplot panels render concurrently with Rayon, and repeated `savefig()` calls on an
unchanged figure reuse the previously encoded bytes. CI runs the comparison suite
against `tools/benchmark_baseline.json` and reports when the matplotlib-normalized
speedup drops by more than 30% (`tools/benchmark_guard.py`). The wider budget
accounts for single-run variance on shared CI hosts; the guard warns by default
and only exits non-zero with `--fail`, so benchmark noise never blocks a run.
Criterion provides the lower-noise, output-stage measurements.

## Test

```bash
maturin develop --release
pip install pytest ruff
pytest
ruff check python tests tools examples
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings
cargo test --all-targets
```

The Python suite includes runner and snippet execution for every gallery example,
plus a feature-to-example coverage matrix. `pytest -m gallery` additionally
regenerates the harvested Matplotlib/Seaborn galleries; it is skipped by default
and when the external checkouts are absent.

The `prek` commit-msg hook rejects `Co-Authored-By` trailers, so keep attribution
out of commit messages (`python tools/check_commit_message.py <file>` runs the same
check by hand).

## Security

The same mandatory scan runs on pre-push through `prek` and in the CI security
job. It checks Cargo.lock with `cargo audit`, scans the shipped Python package
with Bandit, and audits installed Python packages with `pip-audit`:

```bash
cargo install cargo-audit --locked
pip install "bandit>=1.9" "pip-audit>=2.9" numpy
python tools/security_audit.py
```

`cargo audit` currently reports two unmaintained-crate warnings, `rustybuzz` and
`ttf-parser`, both pulled in indirectly by `svg2pdf 0.13`'s pinned `usvg 0.45`
dependency. That is the latest `svg2pdf` release; there are no known
vulnerabilities. Revisit when `svg2pdf`/`usvg` update. The tight-PDF tests gate
those upgrades, so the hand-assembled PDF path is not changed independently.

## License

Dual-licensed under either of [MIT](LICENSE-MIT) or
[Apache-2.0](LICENSE-APACHE), at your option.
