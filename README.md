# plt.rs

Matplotlib-style static plots, rendered and written to PNG or SVG entirely in Rust
(PyO3 + plotters). Python deps: numpy only. No matplotlib, no Pillow.

🔗 **[Live Example Gallery](https://kassoulet.github.io/plt_rs/)** &bull; ⚡ **[Speed Benchmarks](https://kassoulet.github.io/plt_rs/benchmarks.html)**

## Performance at a Glance

| Benchmark Case | `plt.rs` | `matplotlib` | Speedup |
|---|---:|---:|---:|
| Single Line (100 pts, PNG) | **0.44 ms** | 60.37 ms | **137x** |
| Single Line (1,000 pts, PNG) | **0.56 ms** | 60.38 ms | **108x** |
| Single Line (10,000 pts, PNG) | **0.78 ms** | 63.68 ms | **82x** |
| Subplots (2x2 grid, PNG) | **1.53 ms** | 110.28 ms | **72x** |
| Vector SVG Export (1k pts) | **0.13 ms** | 55.02 ms | **428x** |
| Cold CLI Process Execution | **71 ms** | 404 ms | **5.7x** |
| Peak Memory (RSS) | **30.7 MB** | 93.4 MB | **67% less RAM** |

*Measured on Linux x86_64. View full interactive charts on the [Benchmarks Page](https://kassoulet.github.io/plt_rs/benchmarks.html).*

## Build
```bash
pip install maturin numpy
maturin develop --release
```

## Usage
```python
import numpy as np
import plt_rs as plt

x = np.linspace(0, 10, 200)
plt.figure(figsize=(8, 5))
plt.plot(x, np.sin(x), label="sin", color="red")
plt.plot(x, np.cos(x), label="cos")
plt.xlabel("x"); plt.ylabel("y"); plt.title("Demo"); plt.legend()
plt.savefig("demo.png")  # or "demo.svg"
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
- `scatter(x, y, s=, c=, alpha=, cmap=, marker=)` — per-point sizes and colours,
  markers `o s ^ v < > D x + .`
- `errorbar(x, y, yerr=, xerr=, fmt=, capsize=, ecolor=)` — scalar, per-point or
  `(2, N)` asymmetric errors, with optional caps
- `bar(x, height, width=, bottom=, color=, edgecolor=, align=, alpha=, yerr=)` and
  `barh(...)` — single or per-bar colours, optional edge and error bars; returns a
  `BarContainer` whose handles support `set_facecolor`/`set_alpha`, with a legend swatch
  when labelled
- `bar_label(container, labels=, fmt=, label_type=, padding=)` — value labels on bars
- `hist(x, bins=, density=, cumulative=, orientation=, color=)` — drawn over `bar`,
  returning `(counts, edges, handles)`
- `step(x, y, where="pre"|"post")` and `stairs(values, edges=, baseline=, fill=)` —
  staircase lines, with optional fill to a baseline
- `tight_layout`/`subplots_adjust`/`set_in_layout` — accepted as no-ops (window-fitted
  panels, so there is nothing to negotiate)
- `fill_between(x, y1, y2, where=, color=, alpha=)`, `fill_betweenx` and `fill(...)` —
  filled polygons; `where` masks split into separate runs
- `axhline`/`axvline`/`axhspan`/`axvspan` — reference lines and bands over axes-fraction
  ranges, resolved against the final limits

**Gridded data**
- `imshow(X, cmap=, vmin=, vmax=, extent=, origin=, aspect=)` — 2-D arrays mapped
  through a colormap, or `(H, W, 3|4)` RGB(A) arrays
- `contour(X, Y, Z, levels=, colors=, cmap=)` — marching-squares iso-lines
- `contourf(X, Y, Z, levels=, colors=, cmap=)` — filled iso-bands
- `pcolormesh(X, Y, Z, cmap=, vmin=, vmax=)` — quad mesh through the image path
  (also `pcolor`/`pcolorfast`; edges or cell centres accepted)
- `colorbar(mappable, label=)` — gradient strip with min/mid/max ticks

**Axes & layout**
- `figure(figsize=)`, `subplots(nrows, ncols)`, `subplot`, `gca`, `gcf`, `axes`
- `xlabel` / `ylabel` / `title` / `legend`, `xlim` / `ylim`
- `set_aspect("equal" | "auto" | <number>)` — shrinks the plotting box, like
  matplotlib's `adjustable="box"` (images default to `"equal"`)
- `text(x, y, s, color=, fontsize=, ha=, va=)`, `annotate(text, xy, xytext=)`
- `savefig(path, format=, dpi=, bbox_inches="tight", transparent=)` — PNG and SVG
- `set(**kwargs)` shorthand, `axis("off" | "equal" | [limits])`, `invert_xaxis`/`invert_yaxis`

**Introspection:** `get_xlim`/`get_ylim`, `get_position`, `get_window_extent`,
`get_visible`/`set_visible`, `remove`, `clear`, `add_artist`/`add_patch`,
`get_children`, `get_transform`, `get_figure`, `get_facecolor`, `get_alpha`.
Visibility and removal are honoured by the renderer; tick getters/setters store
values but the renderer still chooses tick locations automatically.

**Compatibility no-ops:** `show`, `draw`, `pause`, `ion`, `ioff`, `update`, `margins`,
`autoscale`, `set_clip_on`, `set_path_effects`.

### Not supported (yet)
- log scales, `twinx`, `tight_layout`, `GridSpec`, `suptitle`
- `bar`, `hist`, `boxplot`, `pie`, `stem`, `quiver`, `hist2d`
- colormaps beyond `viridis`/`gray`; colorbars on multi-axes figures
- interactive display (out of scope forever)

## Coverage

`TRACE.md` tracks how many call sites from matplotlib's own test suite plt_rs
accepts — currently **8 509 / 10 098 (84%)**. CI re-runs the trace against
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
pip install pytest && pytest
```
