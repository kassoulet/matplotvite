# plt.rs — Roadmap

> Tracking progress toward a zero-dependency, Rust-powered drop-in for Matplotlib's most common call sites.
> TRACE.md baseline: **8 842 / 10 098 call sites covered (87%)** across 91 real-world matplotlib test files.
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
- [x] `linestyle` / `ls` — solid, dashed, dotted and dashdot (dashdot is approximated); fmt shorthand `"r--o"` / positional `plot(x, y, "g--")`
- [x] `linewidth` / `lw`
- [x] `marker` on `plot()` — `o s ^ v < > D x + .` drawn with the scatter marker primitives
- [x] `markersize` / `ms`, `markerfacecolor` / `mfc`, `markeredgecolor` / `mec`, `markeredgewidth` / `mew`
- [x] `alpha` (line + marker transparency)
- [x] `drawstyle` — `"default"`, `"steps-pre"`, `"steps-post"` (other values raise)

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
- [x] `set_aspect("equal" | float)` — box shrink, see V4
- [x] `axhline(y, color=, linestyle=, linewidth=, xmin=, xmax=)` / `axvline(x, ...)` — axes-fraction ends resolved against the final limits at draw time; `zorder` ignored
- [x] `axhspan(ymin, ymax, xmin=, xmax=)` / `axvspan` (shaded band) — drawn as an unedged bar rectangle over an axes-fraction span

### 2.4 Text & annotations
- [x] `text(x, y, s, color=, fontsize=, ha=, va=)`
- [ ] `text(..., transform=)` — axes / figure coordinate transforms
- [x] `annotate(text, xy, xytext=)` — label plus straight arrow; `arrowprops` styling is accepted but ignored

### 2.5 Fill
- [x] `fill_between(x, y1, y2, where=, color=, alpha=)` / `fill_betweenx` / `fill(...)` — polygons in data space, `where` runs emitted separately (`interpolate`/`step`/`hatch` ignored); `label=` adds a legend swatch
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
- [x] `scatter(x, y, s=, c=, alpha=, cmap=, label=, marker=)` — per-point sizes, explicit colours or cmap-mapped values, markers `o s ^ v < > D x + .`, legend handle for labelled series
- [x] `errorbar(...)` — includes scalar / per-point / `(2, N)` errors, caps, `ecolor`, and `fmt` colours/markers
- [x] `bar(x, height, width=, bottom=, color=, edgecolor=, align=, alpha=, yerr=)` / `barh(...)` — rectangles drawn in pixel space, returning a `BarContainer` of mutable handles; labelled bars get a legend swatch
- [x] `bar_label(container, labels=, fmt=, label_type=, padding=)` — values placed at the bar end or centred
- [x] `hist(x, bins=, density=, cumulative=, color=, alpha=, label=, orientation=)` — implemented over `bar`, returns `(counts, edges, handles)`; `histtype` covers `bar`/`step`/`stepfilled` and `bottom` offsets
- [x] `step(x, y, where=, color=, label=)` — delegates to `plot` with `steps-pre`/`steps-post`; `where="mid"` raises
- [x] `hlines(y, xmin, xmax, colors=, linestyles=)` / `vlines(x, ymin, ymax, ...)` — one segment per entry, per-segment colour and style

### 3.2 Log / symlog scales
- [x] `xscale("log" | "linear")` / `yscale(...)` (pyplot + Axes) — layout and every artist map through log10/base, tick labels are converted back; any positive `base` works, `symlog` raises
- [x] `semilogx`, `semilogy`, `loglog` convenience wrappers

### 3.3 Layout
- [x] `tight_layout(pad=, h_pad=, w_pad=)` — accepted as a no-op: panels always fill their grid cells, so nothing can clip
- [ ] `suptitle(t, fontsize=)` — figure-level title
- [x] `subplots_adjust(left, right, top, bottom, wspace, hspace)` and `set_in_layout`/`set_layout_engine` — accepted as no-ops
- [ ] `GridSpec` / `subplot_mosaic` — irregular grid layouts
- [ ] `twinx()` / `twiny()` — dual axes on same panel
- [ ] `sharex` / `sharey` in `subplots()`

### 3.4 Style & theming
- [ ] `plt.style.use("dark_background" | "ggplot" | "seaborn-v0_8")` — a small preset palette set
- [x] `rc`/`rc_context`/`rcParams`/`rcdefaults` — settings are recorded, `rc_context` restores them on exit; the renderer still uses its fixed defaults
- [x] `grid(True|False, which=, axis=)` — light gridlines under the data; `visible=None` flips the current state
- [x] `tick_params(...)` — accepted and recorded; tick styling is not rendered
- [x] `axline(xy1, xy2=, slope=)` — infinite line clipped to the axes, excluded from the data limits
- [ ] `rcParams` subset that actually changes output: `lines.linewidth`, `axes.labelsize`, `font.size`, `figure.dpi`, `axes.prop_cycle`
- [ ] Color cycle customization (`set_prop_cycle`)
- [x] `plt.show()` as a silent no-op (compatibility)
- [x] `plt.draw()` as a no-op (compatibility)
- [x] `plt.axes()` / `plt.pause()` / `plt.ion()` / `plt.ioff()` compatibility shims

### 3.5 Axes introspection (compatibility surface)
- [x] State getters: `get_xlim`/`get_ylim`/`get_xbound`/`get_ybound`, `get_position`/`set_position`, `get_visible`/`set_visible`, `get_facecolor`/`set_facecolor`, `get_alpha`/`set_alpha`, `get_label`/`set_label`, `get_zorder`/`set_zorder`, `get_title`/`get_xlabel`/`get_ylabel`, `get_figure`, `get_children`
- [x] No-ops that keep scripts running: `draw`, `update`, `margins`, `relim`, `autoscale`, `autoscale_view`, `set_clip_on`/`set_clip_path`, `set_path_effects`, `add_artist`/`add_patch`/`add_collection`/`add_line`
- [x] Real behaviour: `remove()` and `set_visible(False)` drop the panel, `axis("off")` hides axes/ticks/labels, `axis("equal"|"auto"|[limits])`, `invert_xaxis`/`invert_yaxis`, `clear`/`cla`, `set(**kwargs)` dispatch
- [x] Tick/label storage: `set_xticks`/`set_yticks`, `set_xticklabels`/`set_yticklabels`, `get_xticks`/`get_yticks`, `get_xticklabels`/`get_yticklabels` (stored values are not yet used by the renderer)
- [ ] `get_window_extent` that accounts for labels/titles rather than the raw grid cell
- [x] `setp`/`getp` cover bar handles (`set_height`/`set_width`/`set_x`/`set_y`, `get_facecolor`) but only artists that expose matching `set_*`/`get_*` methods
- [ ] Render artists registered through `add_patch`/`add_collection`

---

## V4 — Advanced plot types  *(lower frequency, high visual value)*

> TRACE: `imshow` ×235, `errorbar` ×82, `boxplot` ×48, `contourf` ×32, `pie` ×26, `stem` ×33.

- [x] `errorbar(x, y, yerr=, xerr=, fmt=, capsize=, ecolor=)`
- [x] `stem(x, y, linefmt=, markerfmt=, basefmt=, bottom=)` — segments over `vlines`, tips via `scatter`, baseline via `hlines`; `orientation="horizontal"` draws sideways stems
- [x] `pie(x, labels=, autopct=, colors=, explode=, startangle=, normalize=)` — wedges as filled polygons with equal aspect, axis off, returns `(wedges, texts, autotexts)`; `shadow` ignored
- [ ] `boxplot(x, notch=, vert=, patch_artist=, labels=)`
- [ ] `violinplot(dataset, positions=, vert=, widths=)`
- [x] `imshow(X, cmap=, vmin=, vmax=, origin=, extent=, aspect=)` — 2-D arrays via colormap and RGB(A) arrays, embedded as PNG data URIs; `interpolation`/`alpha` accepted but ignored
- [x] `set_aspect('equal' | 'auto' | <number>)` — shrinks the plotting box to fix the data scale (matplotlib's `adjustable="box"`)
- [x] `contour(X, Y, Z, levels=, colors=, cmap=)` — marching-squares iso-lines (`linewidths`/`alpha` accepted but ignored)
- [x] `contourf(X, Y, Z, levels=, colors=, cmap=)` — filled iso-bands by clipping each grid triangle against the level pair (`alpha` accepted but ignored)
- [x] `contour(X, Y, Z, levels=)` / `contourf(...)` with colorbar
- [x] `colorbar(mappable, ax=, label=)` — gradient strip with min/mid/max ticks in a reserved grid cell (single-axes figures)
- [x] `pcolormesh(X, Y, Z, cmap=, vmin=, vmax=)` / `pcolor` / `pcolorfast` — cells rasterised through the image path, edges or centres accepted (`shading`/`norm` accepted but ignored)
- [ ] `hist2d(x, y, bins=, cmap=)` / `hexbin(x, y, gridsize=, cmap=)`
- [x] `stackplot(x, *ys, colors=, alpha=)` — cumulative layers over `fill_between` (`baseline="zero"` and `"sym"`)
- [ ] `quiver(X, Y, U, V)` — vector field arrows
- [x] `stairs(values, edges=, baseline=, fill=)` — staircase built from bin values and edges, optionally filled to a baseline (`orientation="horizontal"` raises)
- [x] `eventplot(positions, orientation=, lineoffsets=, linelengths=, colors=, linestyles=)` — one short line per event, one row per positions array; `linewidths` honoured
- [x] `broken_barh(xranges, yrange, colors=, edgecolor=, alpha=)` — `(start, width)` pairs drawn as bars over a shared y range, edge colour and alpha honoured
- [x] `minorticks_on()` / `minorticks_off()` — recorded only; minor ticks are not rendered
- [x] `setp(artist, **kwargs)` / `getp(artist, *names)` — generic `set_*`/`get_*` dispatch, raising `AttributeError` for unknown names (no validation of values)

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
