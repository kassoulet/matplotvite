# plt.rs — Roadmap

> Tracking progress toward a zero-dependency, Rust-powered drop-in for Matplotlib's most common call sites.
> TRACE.md baseline: **4 951 / 10 098 call sites covered (49%)** across 91 real-world matplotlib test files.
> CI runs `tools/trace_unsupported.py --check` against `tools/trace_baseline.json` and fails on any drop.
> Regenerate with `python tools/trace_unsupported.py <matplotlib/tests> TRACE.md` — it introspects the live
> `plt_rs` module/`Axes`/`Figure` API and each callable's accepted kwargs, so counts can't go stale again.

---

## ✅ V1 — Core line chart (done)

- [x] `figure(figsize)` / `close()`
- [x] `plot(x, y, label=, color=)` — NumPy arrays, zero-copy via PyO3
- [x] `xlabel` / `ylabel` / `title`
- [x] `legend()`
- [x] `savefig(path)` — PNG & SVG, written from Rust (`std::fs`), no Pillow
- [x] `subplots(nrows, ncols)`, `subplot(r,c,i)`, `gca()`, `gcf()`
- [x] `Axes`: `plot`, `set_title/xlabel/ylabel`, `legend`, `set_xlim/ylim`, `xlim/ylim`
- [x] Color: named (`red/r/green/g/blue/b/orange/black/k`) + hex strings + tab10 auto-cycle
- [x] Embedded Geist fonts (sans-serif, serif, mono) — no system font deps

---

## V2 — Plot style & axis control  *(high-frequency gaps)*

> TRACE priorities: `plot` kwargs (lw ×44, marker ×35, linestyle ×14, alpha ×10), `savefig` kwargs (format ×112, dpi ×8, bbox_inches ×10), `axis` ×11, `grid` ×28, `xticks/yticks`.

### 2.1 `plot()` kwargs
- [ ] `linestyle` / `ls` — solid, dashed, dotted, dashdot, fmt string shorthand (`"r--o"`)
- [ ] `linewidth` / `lw`
- [ ] `marker` — point, circle, square, triangle, cross, plus, diamond (`"o"`, `"s"`, `"^"`, `"+"`, `"x"`, `"D"`)
- [ ] `markersize` / `ms`, `markerfacecolor` / `mfc`, `markeredgecolor` / `mec`, `markeredgewidth`
- [ ] `alpha` (line + marker transparency)
- [ ] `drawstyle` — `"default"`, `"steps-pre"`, `"steps-post"`

### 2.2 Color system
- [ ] Full CSS named colors (140+) in `color()` fn
- [ ] RGB tuple `(r, g, b)` and RGBA tuple `(r, g, b, a)` — 0–1 floats
- [ ] `C0`–`C9` shorthand (tab10 cycle references)
- [ ] `"none"` / `"transparent"` color

### 2.3 Axes control
- [ ] `grid(visible, axis, linestyle, linewidth, alpha, color)`
- [ ] `xticks(ticks, labels, rotation)` / `yticks(ticks, labels, rotation)`
- [ ] `tick_params(axis, labelsize, length, width, color, rotation)`
- [ ] `axis("off" | "equal" | "scaled" | [xmin,xmax,ymin,ymax])`
- [ ] `set_aspect("equal" | float)`
- [ ] `axhline(y, color, linestyle, linewidth, alpha)` / `axvline(x, ...)`
- [ ] `axhspan` / `axvspan` (shaded band)

### 2.4 Text & annotations
- [x] `text(x, y, s, color=, fontsize=, ha=, va=)`
- [ ] `text(..., transform=)` — axes / figure coordinate transforms
- [x] `annotate(text, xy, xytext=)` — label plus straight arrow; `arrowprops` styling is accepted but ignored

### 2.5 Fill
- [ ] `fill_between(x, y1, y2, alpha, color, label)`
- [ ] `fill(x, y, color, alpha)`

### 2.6 Legend kwargs
- [ ] `loc` — `"best"`, cardinal strings, 2-tuple
- [ ] `ncol` / `ncols`, `frameon`, `fontsize`, `title`, `title_fontsize`
- [ ] `bbox_to_anchor`

### 2.7 savefig / figure kwargs
- [x] `savefig(format=, dpi=)` — `format` overrides the file extension
- [x] `savefig(bbox_inches="tight", transparent=)` — tight crops PNG pixels / rewrites the SVG viewBox
- [ ] `savefig(facecolor=)`
- [ ] `figure(dpi=, facecolor=, edgecolor=)`
- [ ] `savefig()` returning bytes (no path — for streaming / in-memory use)

### 2.8 Font sizes
- [ ] `title(fontsize=)`, `xlabel(fontsize=)`, `ylabel(fontsize=)`
- [ ] Global default font size

---

## V3 — New plot types & layout  *(medium-frequency)*

> TRACE priorities: `scatter` ×176 Axes / ×30 pyplot, `bar` ×81, `hist` ×74, `twinx` ×31, `tight_layout` ×20.

### 3.1 New plot types
- [ ] `scatter(x, y, s=, c=, alpha=, cmap=, label=, marker=)`
- [ ] `bar(x, height, width=, bottom=, color=, label=, align=)` / `barh(...)`
- [ ] `hist(x, bins=, density=, cumulative=, color=, alpha=, label=, histtype=)`
- [ ] `step(x, y, where=, color=, label=)` — equivalent to `drawstyle="steps"`
- [ ] `hlines(y, xmin, xmax, ...)` / `vlines(x, ymin, ymax, ...)`

### 3.2 Log / symlog scales
- [ ] `xscale("log" | "symlog" | "linear")` / `yscale(...)` (pyplot + Axes)
- [ ] `semilogx`, `semilogy`, `loglog` convenience wrappers

### 3.3 Layout
- [ ] `tight_layout(pad=, h_pad=, w_pad=)` — auto-shrink margins so labels don't clip
- [ ] `suptitle(t, fontsize=)` — figure-level title
- [ ] `subplots_adjust(left, right, top, bottom, wspace, hspace)`
- [ ] `GridSpec` / `subplot_mosaic` — irregular grid layouts
- [ ] `twinx()` / `twiny()` — dual axes on same panel
- [ ] `sharex` / `sharey` in `subplots()`

### 3.4 Style & theming
- [ ] `plt.style.use("dark_background" | "ggplot" | "seaborn-v0_8")` — a small preset palette set
- [ ] `rcParams` subset: `lines.linewidth`, `axes.labelsize`, `font.size`, `figure.dpi`, `axes.prop_cycle`
- [ ] Color cycle customization (`set_prop_cycle`)
- [ ] `plt.show()` as a silent no-op (compatibility)
- [ ] `plt.draw()` as a no-op (compatibility)

---

## V4 — Advanced plot types  *(lower frequency, high visual value)*

> TRACE: `imshow` ×235, `errorbar` ×82, `boxplot` ×48, `contourf` ×32, `pie` ×26, `stem` ×33.

- [ ] `errorbar(x, y, yerr=, xerr=, fmt=, capsize=, ecolor=)`
- [ ] `stem(x, y, linefmt=, markerfmt=, basefmt=)`
- [ ] `pie(x, labels=, autopct=, colors=, explode=, startangle=)`
- [ ] `boxplot(x, notch=, vert=, patch_artist=, labels=)`
- [ ] `violinplot(dataset, positions=, vert=, widths=)`
- [x] `imshow(X, cmap=, vmin=, vmax=, origin=, extent=, aspect=)` — 2-D arrays via colormap and RGB(A) arrays, embedded as PNG data URIs; `interpolation`/`alpha` accepted but ignored
- [x] `set_aspect('equal' | 'auto' | <number>)` — shrinks the plotting box to fix the data scale (matplotlib's `adjustable="box"`)
- [ ] `contour(X, Y, Z, levels=)` / `contourf(...)` with colorbar
- [ ] `colorbar(mappable, ax=, label=)` — figure-level colorbar
- [ ] `hist2d(x, y, bins=, cmap=)` / `hexbin(x, y, gridsize=, cmap=)`
- [ ] `stackplot(x, *ys, labels=, colors=, alpha=)`
- [ ] `quiver(X, Y, U, V)` — vector field arrows
- [ ] `stairs(values, edges=)` — histogram-like step chart

---

## V5 — Ecosystem & output  *(wheels, integrations, advanced output)*

### 5.1 Output formats
- [ ] PDF output via `printpdf` or `cairo` Rust crate
- [ ] `savefig()` to `io.BytesIO` / file-like object (Python buffer protocol)
- [ ] `savefig()` → `bytes` return (no path argument)
- [ ] WebP output option

### 5.2 Data integration
- [ ] Pandas `DataFrame` / `Series` input (`data=` kwarg, label from Series name)
- [ ] `plot(x="col_x", y="col_y", data=df)` sugar
- [ ] `datetime64` / `Timestamp` x-axis (date ticks + formatting)
- [ ] Categorical x-axis (string ticks, bar alignment)

### 5.3 Math text
- [ ] LaTeX-ish math subset in titles/labels — `$x^2$`, Greek letters via Unicode fallback

### 5.4 Packaging & distribution
- [ ] Type stubs (`.pyi`) for IDE autocomplete and mypy
- [ ] PyPI wheel CI: manylinux2014 (x86_64, aarch64), macOS arm64, Windows x86_64 via maturin `--release`
- [ ] `maturin publish` GitHub Action on tag push

### 5.5 Performance
- [ ] Parallel subplot rendering with **Rayon** (independent panels rendered concurrently)
- [ ] Incremental re-render: cache unchanged panels, only redraw dirty ones
- [ ] Benchmark suite in CI with regression guard (fail if >20% slower than baseline)

---

## V6 — 3-D & specialty  *(optional, long-term)*

- [ ] `Axes3D`: `plot_surface`, `scatter3D`, `plot3D`, `contourf3d`
- [ ] Polar axes (`polar=True`, `plt.polar()`)
- [ ] `subplot_mosaic` with mixed 2-D / 3-D panels
- [ ] `imshow` colormaps beyond viridis/gray (plasma, inferno, magma, cividis)

---

## Out of scope (forever)

Interactive display windows, `plt.show()` opening a GUI, animation (`FuncAnimation`), widgets, GUI backends (TkAgg, Qt, etc.), `%matplotlib inline` magic.

---

## Cross-cutting / always-on

- Benchmarks page vs matplotlib — regenerated by CI on every push (`tools/benchmark.py`)
- Gallery page of sample outputs — deployed to GitHub Pages (`tools/build_pages.py`)
- prek pre-commit hooks: `cargo fmt`, `cargo clippy --deny warnings`, `cargo test`, whitespace/EOF checks
- Python test matrix: 3.9 → 3.13 on every PR (`pytest`, `PYTHONPATH=python:.`)
