# plt.rs

Matplotlib-style static plots, rendered and written to PNG, SVG or PDF entirely in
Rust (PyO3 + plotters). Python deps: numpy only. No matplotlib, no Pillow.

🔗 **[Live Example Gallery](https://kassoulet.github.io/plt_rs/)** &bull; ⚡ **[Speed Benchmarks](https://kassoulet.github.io/plt_rs/benchmarks.html)**

## Performance at a Glance

| Benchmark Case | `plt.rs` | `matplotlib` | Speedup |
|---|---:|---:|---:|
| Single Line (100 pts, PNG) | **4.03 ms** | 88.42 ms | **21.9x** |
| Single Line (1,000 pts, PNG) | **3.60 ms** | 91.05 ms | **25.3x** |
| Single Line (10,000 pts, PNG) | **7.17 ms** | 96.59 ms | **13.5x** |
| Single Line (100,000 pts, PNG) | **51.58 ms** | 131.65 ms | **2.6x** |
| Multi-Series (5 lines x 2,000 pts, PNG) | **10.78 ms** | 147.40 ms | **13.7x** |
| Subplots (2x2 grid, PNG) | **9.39 ms** | 144.10 ms | **15.3x** |
| Vector SVG Export (1k pts) | **0.51 ms** | 98.43 ms | **192.4x** |
| Cold CLI Process Execution | **146.5 ms** | 607.4 ms | **4.1x** |

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
  facecolor=, edgecolor=)` — PNG, SVG and vector PDF (text stays selectable; the page is
  sized from `figsize`); no path returns `bytes`
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
pip install pytest ruff && pytest
ruff check python tests tools examples
```

## License

Dual-licensed under either of [MIT](LICENSE-MIT) or
[Apache-2.0](LICENSE-APACHE), at your option.
