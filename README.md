# plt.rs

> **Experimental and incomplete.** `plt.rs` is under active development, its API
> may change between releases, and it does not yet cover the full matplotlib
> surface. Do not rely on it for production-critical output without validation.

Matplotlib-style static plots, rendered and encoded to PNG, SVG or PDF entirely in
Rust (PyO3 + plotters). Python deps: numpy only. No matplotlib, no Pillow.

🔗 **[Live Example Gallery](https://kassoulet.github.io/plt_rs/)** &bull; ⚡ **[Speed Benchmarks](https://kassoulet.github.io/plt_rs/benchmarks.html)**

## Performance at a Glance

| Benchmark Case | `plt.rs` | `matplotlib` | Speedup |
|---|---:|---:|---:|
| Single Line (100 pts, PNG) | **3.05 ms** | 77.51 ms | **25.4x** |
| Single Line (1,000 pts, PNG) | **2.68 ms** | 77.72 ms | **29.0x** |
| Single Line (10,000 pts, PNG) | **6.06 ms** | 81.34 ms | **13.4x** |
| Single Line (100,000 pts, PNG) | **38.74 ms** | 103.96 ms | **2.7x** |
| Multi-Series (5 lines x 2,000 pts, PNG) | **8.97 ms** | 121.98 ms | **13.6x** |
| Subplots (2x2 grid, PNG) | **7.88 ms** | 131.19 ms | **16.6x** |
| Vector SVG Export (1k pts) | **0.44 ms** | 70.09 ms | **160.6x** |
| Cold CLI Process Execution | **83.1 ms** | 463.4 ms | **5.6x** |

*Measured on a shared Linux x86_64 host (AMD Ryzen 5 5600G, Python 3.14, matplotlib 3.11.2); wall-clock times vary with machine load. View full interactive charts on the [Benchmarks Page](https://kassoulet.github.io/plt_rs/benchmarks.html) and regenerate with `python tools/benchmark.py`.*

## Build
```bash
pip install maturin numpy
maturin develop --release
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
| Text | `fontdb`, `ttf-parser`, `rustybuzz`, `subsetter` | Rust; only the embedded Geist faces are loaded |
| Fonts | Geist sans/serif/mono TTFs | OFL, embedded in the binary (see `assets/fonts/`) |
| Build | Rust stable, `maturin`, CPython (with development headers) | NumPy is only needed to import the built module |

`plt.rs` itself contains no `unsafe` code. All non-Rust code sits behind the
`pyo3`/`numpy` and `libc` bindings; nothing on the drawing path shells out or links
a C library directly.

Type stubs (`.pyi`) and the PEP 561 `py.typed` marker ship in the wheel, so editors
and type checkers see the public API. Wheels use CPython's stable ABI
(`cp39-abi3`), so one build per platform supports Python 3.9 and newer.

## Usage
```python
import numpy as np
import plt_rs as plt

x = np.linspace(0, 10, 200)
plt.figure(figsize=(8, 5))
plt.plot(x, np.sin(x), label="sin", color="red")
plt.plot(x, np.cos(x), label="cos")
plt.xlabel("x"); plt.ylabel("y"); plt.title("Demo"); plt.legend()
plt.savefig("demo.png")  # or "demo.svg" / "demo.pdf"
```

Gridded data, contours and a colorbar:
```python
import numpy as np
import plt_rs as plt

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

**Line & marker plots**
- `plot(x, y, label=, color=)` — NumPy arrays, zero-copy through PyO3
- `plot` styling: `linestyle`/`ls`, `linewidth`/`lw`, `marker`, `markersize`/`ms`,
  `markerfacecolor`/`mfc`, `markeredgecolor`/`mec`, `markeredgewidth`/`mew`, `alpha`,
  `drawstyle="steps-pre"|"steps-post"`, and fmt shorthand (`plot(x, y, "r--o")`)
- Colors: all 148 CSS4 names (plus `tab:*` aliases), hex strings, RGB/RGBA tuples,
  `C0`–`C9` and `0`–`9` cycle references, and `"none"`/`"transparent"`
- `scatter(x, y, s=, c=, alpha=, cmap=, marker=)` — per-point sizes and colours,
  markers `o s ^ v < > D x + .`, with a legend handle when labelled
- `errorbar(x, y, yerr=, xerr=, fmt=, capsize=, ecolor=)` — scalar, per-point or
  `(2, N)` asymmetric errors, optional caps, and `fmt` markers
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

**Gridded data**
- `imshow(X, cmap=, vmin=, vmax=, extent=, origin=, aspect=)` — 2-D arrays mapped
  through a colormap, or `(H, W, 3|4)` RGB(A) arrays
- `contour(X, Y, Z, levels=, colors=, cmap=)` — marching-squares iso-lines
- `contourf(X, Y, Z, levels=, colors=, cmap=)` — filled iso-bands
- `pcolormesh(X, Y, Z, cmap=, vmin=, vmax=)` — quad mesh through the image path
  (also `pcolor`/`pcolorfast`; edges or cell centres accepted)
- `colorbar(mappable, label=)` — gradient strip with min/mid/max ticks

**Axes & layout**
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
  facecolor=, edgecolor=, compression=)` — PNG, SVG and vector PDF (text stays selectable;
  the page is sized from `figsize`); no path returns `bytes`. PNG compression is
  `"fast"` (default), `"default"`, or `"best"`
- `set(**kwargs)` shorthand, `axis("off" | "on" | "equal" | "scaled" | [limits])`,
  `invert_xaxis`/`invert_yaxis`

**Introspection:** `get_xlim`/`get_ylim`, `get_position`, `get_window_extent`,
`get_visible`/`set_visible`, `remove`, `clear`, `add_artist`/`add_patch`,
`get_children`, `get_transform`, `get_figure`, `get_facecolor`, `get_alpha`.
Visibility, removal, and custom tick positions/labels are honoured by the renderer.

**Compatibility no-ops:** `show`, `draw`, `pause`, `ion`, `ioff`, `update`, `margins`,
`autoscale`, `set_clip_on`, `set_path_effects`.

### Not supported (yet)
- `twinx`/`twiny`, `GridSpec`, `suptitle`
- `boxplot`, `quiver`, `hist2d`
- colormaps beyond `viridis`/`gray`; colorbars on multi-axes figures
- interactive display (out of scope forever)

## Coverage

`TRACE.md` tracks how many call sites from matplotlib's own test suite plt_rs
accepts — currently **8 896 / 10 098 (88%)**. CI re-runs the trace against
matplotlib 3.11.2 and fails if coverage drops (`tools/trace_unsupported.py --check`).

## Examples & Benchmarks
To build and view the gallery and benchmark pages locally:
```bash
python tools/build_pages.py --out dist
# open dist/index.html or dist/benchmarks.html in your browser
```

To run the live benchmark suite:
```bash
python tools/benchmark.py
```

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
