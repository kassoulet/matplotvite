# Matplotvite

[![CI](https://github.com/kassoulet/matplotvite/actions/workflows/ci.yml/badge.svg)](https://github.com/kassoulet/matplotvite/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.5.0-blue)](ROADMAP.md)

> **Experimental.** Matplotvite is under active development. Its API may change
> between releases, and it does not cover the full matplotlib surface. Validate
> output before relying on it in production.

Matplotvite renders matplotlib-style static figures from Python through a compiled
Rust extension (PyO3 + plotters). It writes PNG, SVG, PDF, and WebP, and NumPy is its
only Python runtime dependency.

- [Example gallery](https://kassoulet.github.io/matplotvite/)
- [Performance measurements](https://kassoulet.github.io/matplotvite/benchmarks.html)
- [Supported API](#whats-supported)

## Build from source

```bash
pip install maturin numpy
maturin develop --release
```

No package release is currently published; build the extension from the repository.

## Measured performance

Representative end-to-end timings from `tools/benchmark.py`. The comparison is
against matplotlib's Agg backend on the same figures and data; treat the ratio as
machine- and load-dependent, not as a general guarantee.

| Workload | Matplotvite | matplotlib | Ratio |
|---|---:|---:|---:|
| Single line, 100 points, PNG | 3.85 ms | 118.95 ms | 30.9× |
| Single line, 1,000 points, PNG | 4.67 ms | 119.11 ms | 25.5× |
| Single line, 10,000 points, PNG | 6.91 ms | 123.21 ms | 17.8× |
| Single line, 100,000 points, PNG | 29.61 ms | 179.50 ms | 6.1× |
| Five series, 2,000 points each, PNG | 13.67 ms | 186.90 ms | 13.7× |
| 2×2 subplot grid, PNG | 13.04 ms | 214.57 ms | 16.5× |
| Scatter, 5,000 points, PNG | 11.09 ms | 260.33 ms | 23.5× |
| Scatter, 50,000 points, PNG | 25.39 ms | 136.60 ms | 5.4× |
| Bar chart, 20 categories, PNG | 4.88 ms | 154.25 ms | 31.6× |
| Filled contours, 160×160, PNG | 33.42 ms | 102.10 ms | 3.1× |
| SVG export, 1,000 points | 0.88 ms | 109.35 ms | 124.8× |
| PDF export, 1,000 points | 3.70 ms | 125.23 ms | 33.8× |
| Cold CLI process, plot, and save | 135.00 ms | 728.40 ms | 5.4× |

The suite now measures 25 workloads, including line scaling, dense SVG export,
subplots, scatter up to 50,000 points, bar, histogram, box/violin summaries,
contour fills and lines, image and quad-mesh rendering, 2-D histograms,
hexagonal bins, quiver fields, datetime axes, repeated saves, and SVG/PDF output.
The full matrix and methodology are on the
[benchmark page](https://kassoulet.github.io/matplotvite/benchmarks.html).

Dense line series are simplified to sub-pixel resolution before drawing, dense
scatters are composited into a raster marker layer for PNG/WebP, and filled
contour bands merge interior cells into runs; those keep the slow paths bounded
by output resolution instead of input size.

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
`target/criterion/`; use `--quick` for a short smoke run.

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
| Text | `fontdb`, `ttf-parser`, `rustybuzz`, `subsetter` | Rust; only the embedded Geist faces are loaded |
| Fonts | Geist sans/serif/mono TTFs | OFL, embedded in the binary (see `assets/fonts/`) |
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
  subscripts, fractions, roots and Greek/symbol commands such as `\alpha`
- Colors: all 148 CSS4 names (plus `tab:*` aliases), hex strings, RGB/RGBA tuples,
  `C0`–`C9` and `0`–`9` cycle references, and `"none"`/`"transparent"`
- `scatter(x, y, s=, c=, alpha=, cmap=, marker=)` — per-point sizes and colours,
  markers `o s ^ v < > D x + .`, with a legend handle when labelled
- `errorbar(x, y, yerr=, xerr=, fmt=, capsize=, ecolor=)` — scalar, per-point or
  `(2, N)` asymmetric errors, optional caps, and `fmt` markers
- `quiver(X, Y, U, V)` / `quiver(U, V)` — vector-field arrows with `scale`,
  `pivot`, per-arrow colours and head sizing
- `bar(x, height, width=, bottom=, color=, edgecolor=, align=, alpha=, yerr=)` and
  `barh(...)` — single or per-bar colours, optional edge and error bars; returns a
  `BarContainer` whose handles support `set_facecolor`/`set_alpha`, with a legend swatch
  when labelled
- `bar_label(container, labels=, fmt=, label_type=, padding=)` — value labels on bars
- `hist(x, bins=, density=, cumulative=, orientation=, color=)` — drawn over `bar` (or as a `step`/`stepfilled` outline),
  returning `(counts, edges, handles)`
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
  `axes.labelsize`, `axes.titlesize`, `font.size`, `legend.fontsize` and `figure.dpi`
  affect output
- `fill_between(x, y1, y2, where=, color=, alpha=)`, `fill_betweenx` and `fill(...)` —
  filled polygons; `where` masks split into separate runs, `label=` gives a legend swatch
- `axhline`/`axvline`/`axhspan`/`axvspan` — reference lines and bands over axes-fraction
  ranges, resolved against the final limits
- `hlines(y, xmin, xmax, colors=, linestyles=)` / `vlines(...)` — segment collections with optional `linewidths`
- `set_xscale("log")`/`set_yscale("log")`, `semilogx`, `semilogy`, `loglog` and the
  `xscale`/`yscale` pyplot shims — artists and limits map through log10, with base-aware
  tick labels (`base=` honoured, `symlog` raises)

### Gridded data
- `imshow(X, cmap=, vmin=, vmax=, extent=, origin=, aspect=)` — 2-D arrays mapped
  through a colormap, or `(H, W, 3|4)` RGB(A) arrays
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
- `colorbar(mappable, label=)` — gradient strip with min/mid/max ticks

### Axes and layout
- `figure(figsize=, dpi=, facecolor=, edgecolor=)` / `subplots(...)` pass-through,
  `subplot`, `gca`, `gcf`, `axes`
- `xlabel` / `ylabel` / `title` (all with `fontsize=`), `legend(...)`, `xlim` / `ylim`
- `legend(loc=, ncol=, frameon=, fontsize=, title=, title_fontsize=, bbox_to_anchor=)` —
  cardinal/2-tuple locations, multi-column layouts, titles and axes-fraction anchors
- `xticks(ticks, labels=, rotation=, fontsize=)` / `yticks(...)` — manual ticks whose
  labels, rotation and size are rendered
- `tick_params(axis=, labelsize=, length=, width=, color=, rotation=)` — label and tick
  mark styling
- `grid(visible, axis="both", linestyle=, linewidth=, alpha=, color=)` — styled gridlines
- `text(x, y, s, color=, fontsize=, ha=, va=, transform=)` — data, `ax.transAxes` or
  `fig.transFigure` coordinates; `annotate(text, xy, xytext=)` adds a straight arrow
- `set_aspect("equal" | "auto" | <number>)` — shrinks the plotting box, like
  matplotlib's `adjustable="box"` (images default to `"equal"`)
- `savefig(path | file-like | None, format=, dpi=, bbox_inches="tight", transparent=,
  facecolor=, edgecolor=, compression=)` — PNG, SVG, vector PDF (text stays selectable;
  the page is sized from `figsize`) and lossless WebP; no path returns `bytes`. PNG
  compression is `"fast"` (default), `"default"`, or `"best"`
- `GridSpec` and `SubplotSpec` via `fig.add_gridspec(...)`, including row/column spans
- `subplot_mosaic(...)` with named panels and empty cells
- `twinx()` / `twiny()` for independent scales on a shared panel
- `fig.suptitle(...)` and `fig.subplots(..., sharex=, sharey=, squeeze=)`
- `style.use`, `style.context`, `style.available`, and `rcParams` style presets
- `set(**kwargs)` shorthand, `axis("off" | "on" | "equal" | "scaled" | [limits])`,
  `invert_xaxis`/`invert_yaxis`

### Introspection

`get_xlim`/`get_ylim`, `get_position`, `get_window_extent`, `get_visible`/`set_visible`,
`remove`, `clear`, `add_artist`/`add_patch`, `get_children`, `get_transform`,
`get_figure`, `get_facecolor`, and `get_alpha`. Visibility, removal, and custom tick
positions/labels are honoured by the renderer.

### Compatibility no-ops

`show`, `draw`, `pause`, `ion`, `ioff`, `update`, `margins`, `autoscale`,
`set_clip_on`, and `set_path_effects` are accepted for source compatibility.

### Not supported

- colorbars on figures with multiple axes
- `streamplot`, polar plots, 3-D axes, and other specialised matplotlib modules
- interactive display (out of scope)

## Coverage

`TRACE.md` tracks how many call sites from matplotlib's own test suite matplotvite
accepts — currently **9 254 / 10 098 (91%)**. CI re-runs the trace against
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
```

Subplot panels render concurrently with Rayon, and repeated `savefig()` calls on an
unchanged figure reuse the previously encoded bytes. CI runs the comparison suite
against `tools/benchmark_baseline.json` and fails when the matplotlib-normalized
speedup drops by more than 30% (`tools/benchmark_guard.py`). The wider budget
accounts for single-run variance on shared CI hosts; Criterion provides the
lower-noise, output-stage measurements.

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
plus a feature-to-example coverage matrix.

## Security

The same mandatory scan runs on pre-push through `prek` and in the CI security
job. It checks Cargo.lock with `cargo audit`, scans the shipped Python package
with Bandit, and audits installed Python packages with `pip-audit`:

```bash
cargo install cargo-audit --locked
pip install "bandit>=1.9" "pip-audit>=2.9" numpy
python tools/security_audit.py
```

## License

Dual-licensed under either of [MIT](LICENSE-MIT) or
[Apache-2.0](LICENSE-APACHE), at your option.
