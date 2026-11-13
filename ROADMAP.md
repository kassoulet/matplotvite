# Matplotvite — Roadmap

> Tracking progress toward a NumPy-only, Rust-rendered subset of Matplotlib's static API.
> TRACE.md baseline: **9 602 / 10 098 call sites covered (95%)** across 91 real-world matplotlib test files.
> CI runs `tools/trace_unsupported.py --check` against `tools/trace_baseline.json` and fails on any drop.
> Regenerate with `python tools/trace_unsupported.py <matplotlib/tests> TRACE.md` — it introspects the live
> `matplotvite` module/`Axes`/`Figure` API and each callable's accepted kwargs, so counts can't go stale again.

## Release status

- **Current version: 0.6.0** — milestones 0.1 through 0.6 are complete.
- **0.7** widens the parity corpus (Matplotlib's own tests and example gallery, Seaborn's gallery) and adds Pandas `.plot()` compatibility.
- **0.8** turns the Seaborn needs-API ranking into plot families: joint/marginal axes, FacetGrid/PairGrid grids, hue grouping with confidence bands, and the distribution/composition plots.
- Interactive/GUI work built on **GPUI** is planned for a later version, after 0.6.

---

## ✅ 0.1 — Core line chart (done)

- [x] `figure(figsize)` / `close()`
- [x] `plot(x, y, label=, color=)` — NumPy arrays, zero-copy via PyO3; repeated data sets (`plot(x1, y1, x2, y2, ...)`) return one `Line2D` handle each, and the handle's `set_color`/`set_data`/`set_label` setters mutate the drawn series
- [x] `xlabel` / `ylabel` / `title`
- [x] `legend()`
- [x] `savefig(path)` — PNG & SVG encoded in Rust, written by the Python layer; no Pillow
- [x] `subplots(nrows, ncols)`, `subplot(r,c,i)`, `gca()`, `gcf()`
- [x] `Axes`: `plot`, `set_title/xlabel/ylabel`, `legend`, `set_xlim/ylim`, `xlim/ylim`
- [x] Color: named (`red/r/green/g/blue/b/orange/black/k`) + hex strings + tab10 auto-cycle
- [x] Embedded DejaVu Sans (regular/bold) and Geist (serif, mono) fonts — no system font deps

---

## ✅ 0.2 — Plot style & axis control (done)

> TRACE priorities: `plot` kwargs (lw ×44, marker ×35, linestyle ×14, alpha ×10), `savefig` kwargs (format ×112, dpi ×8, bbox_inches ×10), `axis` ×11, `grid` ×28, `xticks/yticks`.

### 0.2.1 `plot()` kwargs
- [x] `linestyle` / `ls` — solid, dashed, dotted and dashdot (dashdot is approximated); fmt shorthand `"r--o"` / positional `plot(x, y, "g--")`
- [x] `linewidth` / `lw`
- [x] `marker` on `plot()` — `o s ^ v < > D x + .` drawn with the scatter marker primitives
- [x] `markersize` / `ms`, `markerfacecolor` / `mfc`, `markeredgecolor` / `mec`, `markeredgewidth` / `mew`
- [x] `alpha` (line + marker transparency)
- [x] `drawstyle` — `"default"`, `"steps-pre"`, `"steps-post"` (other values raise)

### 0.2.2 Color system
- [x] Full CSS named colors (148) in `_colors.py` — CSS4 names plus `tab:*` aliases for the tab10 palette
- [x] RGB tuple `(r, g, b)` and RGBA tuple `(r, g, b, a)` — 0–1 floats, plus hex strings
- [x] `C0`–`C9` shorthand (tab10 cycle references) and bare `0`–`9` aliases
- [x] `"none"` / `"transparent"` color

### 0.2.3 Axes control
- [x] `grid(visible, axis, which, linestyle, linewidth, alpha, color)` — styled major gridlines on x, y or both
- [x] `xticks(ticks, labels, rotation, fontsize)` / `yticks(...)` — manual ticks and labels, ticks are drawn by the renderer
- [x] `tick_params(axis, labelsize, length, width, color, rotation)` — label size/colour/rotation and tick mark length/width/colour
- [x] `axis("off" | "on" | "equal" | "scaled" | "auto" | [xmin,xmax,ymin,ymax])`
- [x] `set_aspect("equal" | float)` — box shrink, see 0.4
- [x] `axhline(y, color=, linestyle=, linewidth=, xmin=, xmax=)` / `axvline(x, ...)` — axes-fraction ends resolved against the final limits at draw time; `zorder` ignored
- [x] `axhspan(ymin, ymax, xmin=, xmax=)` / `axvspan` (shaded band) — drawn as an unedged bar rectangle over an axes-fraction span

### 0.2.4 Text & annotations
- [x] `text(x, y, s, color=, fontsize=, ha=, va=)`
- [x] `text(..., transform=)` — `ax.transAxes`, `fig.transFigure` and data coordinates
- [x] `fig.text(...)` / `plt.figtext(...)` — figure-fraction text drawn above the panels so it is never clipped, with no axes required; other `Text` properties (`rotation`, `usetex`, `math_fontfamily`, font families, ...) are accepted but not drawn yet
- [x] `annotate(text, xy, xytext=)` — label plus straight arrow; `arrowprops` styling is accepted but ignored

### 0.2.5 Fill
- [x] `fill_between(x, y1, y2, where=, color=, alpha=)` / `fill_betweenx` / `fill(...)` — polygons in data space, `where` runs emitted separately (`interpolate`/`step`/`hatch` ignored); `label=` adds a legend swatch

### 0.2.6 Legend kwargs
- [x] `loc` — `"best"`, cardinal strings, 2-tuple
- [x] `ncol` / `ncols`, `frameon`, `fontsize`, `title`, `title_fontsize`
- [x] `bbox_to_anchor` — axes-fraction or data coordinates

### 0.2.7 savefig / figure kwargs
- [x] `savefig(format=, dpi=)` — `format` overrides the file extension
- [x] `savefig(bbox_inches="tight", transparent=)` — tight crops PNG pixels / rewrites the SVG viewBox
- [x] `savefig(facecolor=, edgecolor=)`
- [x] `figure(dpi=, facecolor=, edgecolor=)` / `subplots(...)` pass-through
- [x] `savefig()` returning bytes (no path) and writing to file-like objects

### 0.2.8 Font sizes
- [x] `title(fontsize=)`, `xlabel(fontsize=)`, `ylabel(fontsize=)`, and `text(fontsize=)`
- [x] Global `rcParams` font size (`font.size`, `axes.labelsize`, `axes.titlesize`, `legend.fontsize`)
- [x] Font families backed by the embedded faces: `rcParams["font.family"]` selects DejaVu Sans / Geist Serif / Geist Mono, and `title`, `xlabel`, `ylabel`, `text`, `suptitle` and `legend` accept `fontfamily=`

---

## ✅ 0.3 — New plot types & layout (done)

> TRACE priorities: `scatter` ×176 Axes / ×30 pyplot, `bar` ×81, `hist` ×74, `twinx` ×31, `tight_layout` ×20.

### 0.3.1 New plot types
- [x] `scatter(x, y, s=, c=, alpha=, cmap=, label=, marker=)` — per-point sizes, explicit colours or cmap-mapped values, markers `o s ^ v < > D x + .`, legend handle for labelled series
- [x] `errorbar(...)` — includes scalar / per-point / `(2, N)` errors, caps, `ecolor`, and `fmt` colours/markers
- [x] `bar(x, height, width=, bottom=, color=, edgecolor=, align=, alpha=, yerr=)` / `barh(...)` — rectangles drawn in pixel space, returning a `BarContainer` of mutable handles; labelled bars get a legend swatch
- [x] `bar_label(container, labels=, fmt=, label_type=, padding=)` — values placed at the bar end or centred
- [x] `hist(x, bins=, density=, cumulative=, color=, alpha=, label=, orientation=)` — implemented over `bar`, returns `(counts, edges, handles)`; `histtype` covers `bar`/`step`/`stepfilled` and `bottom` offsets
- [x] `step(x, y, where="pre"|"post"|"mid", color=, label=)` — delegates to `plot` with `steps-pre`/`steps-post`/`steps-mid`; `where="mid"` now supported
- [x] `stairs(values, edges=, baseline=, fill=)` — staircase built from bin values and edges, optionally filled to a baseline
- [x] `hlines(y, xmin, xmax, colors=, linestyles=)` / `vlines(x, ymin, ymax, ...)` — one segment per entry, per-segment colour and style

### 0.3.2 Log / symlog scales
- [x] `xscale("log" | "linear")` / `yscale(...)` (pyplot + Axes) — layout and every artist map through log10/base, tick labels are converted back; any positive `base` works, `symlog` raises
- [x] `semilogx`, `semilogy`, `loglog` convenience wrappers

### 0.3.3 Layout
- [x] `tight_layout(pad=, h_pad=, w_pad=)` — accepted as a no-op: panels always fill their grid cells, so nothing can clip
- [x] `suptitle(t, fontsize=)` — figure-level title, placed above the panel grid
- [x] `subplots_adjust(left, right, top, bottom, wspace, hspace)` and `set_in_layout`/`set_layout_engine` — accepted as no-ops
- [x] `GridSpec` / `subplot_mosaic` — irregular grid layouts through explicit panel bounds
- [x] `twinx()` / `twiny()` — dual axes on same panel, with the second axis on the right/top
- [x] `sharex` / `sharey` in `subplots()` — explicit limits propagate through a shared group; inner tick labels are dropped

### 0.3.4 Style & theming
- [x] `plt.style.use("dark_background" | "ggplot" | "seaborn-v0_8")` — presets change figure/axes colours, text colour and the colour cycle
- [x] `rc`/`rc_context`/`rcParams`/`rcdefaults` — settings are recorded, `rc_context` restores them on exit, and the documented subset below changes rendered output
- [x] `grid(True|False, which=, axis=)` — light gridlines under the data; `visible=None` flips the current state, styling is passed through
- [x] `tick_params(...)` — label size/rotation/colour and tick length/width/colour are rendered
- [x] `axline(xy1, xy2=, slope=)` — infinite line clipped to the axes, excluded from the data limits
- [x] `rcParams` subset that actually changes output: `lines.linewidth`, `lines.markersize`, `lines.markerlinewidth`, `axes.labelsize`, `axes.titlesize`, `font.size`, `legend.fontsize`, `figure.dpi`
- [x] Color cycle customization (`set_prop_cycle`) — lines, scatter, bars and fills consume the cycle
- [x] `plt.show()` as a silent no-op (compatibility)
- [x] `plt.draw()` as a no-op (compatibility)
- [x] `plt.axes()` / `plt.pause()` / `plt.ion()` / `plt.ioff()` compatibility shims

### 0.3.5 Axes introspection (compatibility surface)
- [x] State getters: `get_xlim`/`get_ylim`/`get_xbound`/`get_ybound`, `get_position`/`set_position`, `get_visible`/`set_visible`, `get_facecolor`/`set_facecolor`, `get_alpha`/`set_alpha`, `get_label`/`set_label`, `get_zorder`/`set_zorder`, `get_title`/`get_xlabel`/`get_ylabel`, `get_figure`, `get_children`
- [x] No-ops that keep scripts running: `draw`, `update`, `margins`, `relim`, `autoscale`, `autoscale_view`, `set_clip_on`/`set_clip_path`, `set_path_effects`, `add_artist`/`add_patch`/`add_collection`/`add_line`
- [x] Real behaviour: `remove()` and `set_visible(False)` drop the panel, `axis("off")` hides axes/ticks/labels, `axis("equal"|"auto"|[limits])`, `invert_xaxis`/`invert_yaxis`, `clear`/`cla`, `set(**kwargs)` dispatch
- [x] Tick/label storage: `set_xticks`/`set_yticks`, `set_xticklabels`/`set_yticklabels`, `get_xticks`/`get_yticks`, `get_xticklabels`/`get_yticklabels` — custom ticks and labels are rendered
- [x] `get_window_extent` that accounts for labels/titles rather than the raw grid cell
- [x] `setp`/`getp` cover bar handles (`set_height`/`set_width`/`set_x`/`set_y`, `get_facecolor`) but only artists that expose matching `set_*`/`get_*` methods
- [x] Render artists registered through `add_patch`/`add_collection` — Rectangle/Circle/Polygon-like patches and offset/segment collections

---

## ✅ 0.4 — Advanced plot types (done)

> TRACE: `imshow` ×235, `errorbar` ×82, `boxplot` ×48, `contourf` ×32, `pie` ×26, `stem` ×33.

- [x] `errorbar(x, y, yerr=, xerr=, fmt=, capsize=, ecolor=)`
- [x] `stem(x, y, linefmt=, markerfmt=, basefmt=, bottom=)` — segments over `vlines`, tips via `scatter`, baseline via `hlines`; `orientation="horizontal"` draws sideways stems
- [x] `pie(x, labels=, autopct=, colors=, explode=, startangle=, normalize=)` — wedges as filled polygons with equal aspect, axis off, returns `(wedges, texts, autotexts)`; `shadow` ignored
- [x] `boxplot(x, notch=, vert=, patch_artist=, labels=)` — boxes, whiskers, caps, medians and fliers from 1.5-IQR statistics; notched outlines, horizontal orientation, optional filled boxes and per-dataset labels
- [x] `violinplot(dataset, positions=, vert=, widths=)` — Gaussian KDE per dataset drawn as a filled violin, with optional mean/median/extrema lines, one-sided bodies and quantile markers
- [x] `imshow(X, cmap=, vmin=, vmax=, origin=, extent=, aspect=)` — 2-D arrays via colormap and RGB(A) arrays, embedded as fast PNG data URIs; `interpolation`/`alpha` honoured
- [x] `set_aspect('equal' | 'auto' | <number>)` — shrinks the plotting box to fix the data scale (matplotlib's `adjustable="box"`)
- [x] `contour(X, Y, Z, levels=, colors=, cmap=)` — marching-squares iso-lines (`linewidths`/`alpha` accepted but ignored)
- [x] `contourf(X, Y, Z, levels=, colors=, cmap=)` — filled iso-bands by clipping each grid triangle against the level pair (`alpha` accepted but ignored)
- [x] `contour(X, Y, Z, levels=)` / `contourf(...)` with colorbar
- [x] `colorbar(mappable, ax=, label=)` — gradient strip with min/mid/max ticks, one per axes (including multi-panel figures)
- [x] `pcolormesh(X, Y, Z, cmap=, vmin=, vmax=)` / `pcolor` / `pcolorfast` — cells rasterised through the image path, edges or centres accepted (`shading`/`norm` accepted but ignored)
- [x] `hist2d(x, y, bins=, cmap=)` / `hexbin(x, y, gridsize=, cmap=)` — 2-D histograms through the image path and hexagonal binning with colormap-mapped cells, including `C=`, `mincnt=` and per-axis `bins`
- [x] `stackplot(x, *ys, colors=, alpha=)` — cumulative layers over `fill_between` (`baseline="zero"` and `"sym"`)
- [x] `quiver(X, Y, U, V)` — vector field arrows, including the `quiver(U, V)` grid form, `scale`, `pivot` and head sizing
- [x] `stairs(values, edges=, baseline=, fill=)` — staircase built from bin values and edges, optionally filled to a baseline (`orientation="horizontal"` raises)
- [x] `eventplot(positions, orientation=, lineoffsets=, linelengths=, colors=, linestyles=)` — one short line per event, one row per positions array; `linewidths` honoured
- [x] `broken_barh(xranges, yrange, colors=, edgecolor=, alpha=)` — `(start, width)` pairs drawn as bars over a shared y range, edge colour and alpha honoured
- [x] `minorticks_on()` / `minorticks_off()` — recorded only; minor ticks are not rendered
- [x] `setp(artist, **kwargs)` / `getp(artist, *names)` — generic `set_*`/`get_*` dispatch, raising `AttributeError` for unknown names (no validation of values)

---

## ✅ 0.5 — Ecosystem & output (done)

### 0.5.1 Output formats
- [x] PDF output via `svg2pdf` (real vector text, page size from `dpi`)
- [x] `savefig()` to `io.BytesIO` / file-like object
- [x] `savefig()` → `bytes` return (no path argument)
- [x] WebP output option (lossless, alpha-aware)

### 0.5.2 Data integration
- [x] Pandas `DataFrame` / `Series` input (`data=` kwarg, label from Series name)
- [x] `plot(x="col_x", y="col_y", data=df)` sugar
- [x] `datetime64` / `Timestamp` x-axis (date ticks + formatting)
- [x] Categorical x-axis (string ticks, bar alignment)

### 0.5.3 Math text
- [x] LaTeX-ish math subset in titles/labels — `$x^2$`, Greek letters via Unicode fallback

### 0.5.4 Packaging & distribution
- [x] Type stubs (`.pyi`) and `py.typed` for IDE autocomplete and mypy
- [x] Wheel CI: `cp39-abi3` wheels for manylinux (x86_64, aarch64), macOS (arm64, x86_64) and Windows (x86_64, arm64); the full test suite runs against the installed wheel, and the sdist is built and rebuilt into a wheel to prove the source distribution is complete
- [x] `maturin publish` GitHub Action on tag push

### 0.5.5 Performance
- [x] Parallel subplot rendering with **Rayon** (independent panels rendered concurrently)
- [x] Incremental re-render: cache unchanged panels, only redraw dirty ones
- [x] Comparison benchmark suite in CI (25 workloads) with an advisory 30% regression report
- [x] Criterion benchmarks for the Rust output stages (rasterize, PNG, WebP, PDF)

---

## Fidelity follow-ups — static render

- [x] Default data margins — autoscaled axes expand by matplotlib's 5% margin on each side, with flat data widened symmetrically and explicit `xlim`/`ylim` left untouched
- [x] Legend `loc="best"` — scores matplotlib's candidate corners in its own order (upper right → center), using the same badness formula (contained line vertices and point offsets, patch overlaps, one per crossing line) against the drawn series, bars, fills, patches and collections, and takes the least-overlapping placement

---

## ✅ 0.6 — Performance & fidelity (done)

> Goal: widen the speed gap and tighten visual parity without giving up vector output.
> Target: no workload below 4× matplotlib and a tracked gallery pixel-diff budget.

### Performance
- [x] Render PNG panels directly instead of building and re-parsing an SVG (2× oversampled bitmap for multi-panel/large figures; WebP, transparent, and image output still use the vector path)
- [x] Extend raster marker layers to every marker source (series markers, error bars, collections)
- [x] Merge filled-contour interiors into runs and clip only boundary cells
- [x] Share cached panel fragments across figures with identical content
- [x] Add an advisory Criterion budget report alongside the end-to-end benchmark guard

### Fidelity
- [x] Pixel-diff the gallery against Matplotlib and track a per-snippet mismatch metric
- [x] Match marker shapes and cap/join styles exactly — every documented marker (`o s p P h H 8 * X d v ^ < > 1-4 x + | _`) is drawn from matplotlib's own unit paths in both the vector and raster marker layers; solid lines use `projecting` caps and `round` joins (the backend union's false miter point and inner notch are filled and split away), and dashes keep `butt` caps with `round` joins (dash sequences follow Matplotlib's linewidth-scaled lengths)
- [x] Honour `imshow(interpolation=, alpha=)` and `contour(linewidths=, alpha=)`
- [x] Use real glyph metrics for text alignment and legend packing
- [x] Verify alpha compositing and colour conversion against Matplotlib

---

## 🎯 0.7 — Corpus & ecosystem compatibility

> Goal: stop relying on a hand-written gallery as our only parity evidence. Harvest other projects' own
> reference outputs, and widen the entry points users actually call.
> Every harvested snippet is tracked by its per-snippet `mismatch_pct` / `rms`, the same metric
> `tools/visual_compare.py` uses against Matplotlib Agg.

### Matplotlib test corpus
- [x] Harvest `lib/matplotlib/tests/baseline_images` — `tools/harvest_matplotlib.py` pulls every `@image_comparison` case out of a checkout, rewrites the standalone ones into snippets, renders them with matplotvite and writes a baseline-vs-ours gallery plus a JSON manifest. On Matplotlib 3.11.2 that is 526 cases, 125 rendering today (66 at the baseline's pixel size, 12% median mismatch), so the ~375 API failures are the concrete gap list. The wheel ships `test_*.py` but not the images, so the tool needs an sdist or git clone (its default search is `dist/mpl-sdist/`)
- [x] Harvest the gallery examples — `tools/harvest_matplotlib.py --examples <checkout>` rewrites every script under `galleries/examples`, strips the interactive tail, renders it and writes a per-category gallery whose failures are the gap list. On Matplotlib 3.11.2, 65 of 507 render (lines 11/41, text 11/43, pyplots 2/2); the largest remaining gaps are `nothing to plot` (18), helpers imported from `matplotlib.cbook` (16), missing module attributes (14) and `Axes.spines`/`canvas` (17). `examples/` now lives at `galleries/examples` in the checkout, so a sparse checkout of that path is enough
- [x] Keep the galleries reproducible — `pytest -m gallery` regenerates all three from local checkouts and skips when they are absent (the default `pytest` run deselects the marker), and CI publishes the HTML plus relative baseline copies as a build artifact
- [ ] Check in the corpus as generated metadata (snippet source + expected-image hash), refreshed by a tool rather than hand-copied, and diff only the snippets a change actually touches

### Seaborn gallery
- [x] Harvest Seaborn's `examples/` gallery — `tools/harvest_seaborn.py` parses every script and classifies each `sns.*` call against our Matplotlib surface. Seaborn's gallery images are docs build artifacts, so statuses are static capability statements rather than image diffs. The current gallery has no theming-only example: 0 pass, 48 needs-API, 1 unsupported (`clustermap`)
- [x] Report Seaborn compatibility as pass / needs-API / unsupported, and feed the needs-API list back into TRACE priorities — the report ranks the missing capabilities (`jointplot`/`JointGrid` and `FacetGrid`/`PairGrid` at the top, then `relplot`, `displot`, `lmplot`, `lineplot`, `catplot`, `violinplot`), alongside any `plt.*` call we cannot express
- [ ] Cover the Seaborn plots that are thin wrappers over API we already have with pixel-diff tests

### Pandas `.plot()`
- [ ] Ship a `pandas` plotting backend module so `pd.options.plotting.backend = "matplotvite"` works, covering `kind=` line, bar, barh, hist, box, area, scatter and pie
- [ ] Verify `df.plot()` / `Series.plot()` against pandas + Matplotlib for index handling (datetime, categorical, MultiIndex), axis labels, legend and kwarg pass-through
- [ ] Document the supported pandas version matrix and the behaviour for unimplemented `kind=` values (raise clearly rather than drawing something wrong)

---

## 🎯 0.8 — Plot families the Seaborn gallery asks for

> Goal: turn the needs-API ranking into actual plot families, so seaborn-style figures can be expressed
> through our Matplotlib surface. The order below follows how many of Seaborn's 48 needs-API gallery
> examples want each capability (`python tools/harvest_seaborn.py` re-ranks them).

### Joint & marginal axes (6 examples)
- [ ] `jointplot` / `JointGrid` layout — a main axes plus top/right marginal axes sharing the limits, with axes-level `kind=` presets (scatter, hist, kde, reg, hex)
- [ ] Marginal histograms and KDE curves, including the shared tick grid and the space reserved for a figure-level legend

### Multi-axes grids (6 examples)
- [ ] `FacetGrid` / `PairGrid` over `subplots` — row/col variables, shared or independent axes, per-facet titles and figure-level legend
- [ ] Per-facet plot calls (strip, box, line) without rebuilding the figure for each cell

### Grouping and uncertainty (~18 examples)
- [ ] `hue` / `style` grouping that maps groups to the colour cycle, markers and linestyles, with one legend entry per variable rather than per group
- [ ] Confidence bands around a line (bootstrap mean ± CI) drawn as a filled band with the same alpha/legend semantics as Seaborn
- [ ] Violin bodies (KDE silhouette plus inner quartiles) and jittered/swarmed categorical positions
- [ ] Point estimates with error bars (`pointplot`, `barplot`)

### Distribution and composition (~16 examples)
- [ ] Histogram and ECDF statistics (`stat=count/density/probability`) with stacked and `multiple=dodge/fill` bars
- [ ] Annotated matrices for `heatmap` — `pcolormesh` with per-cell text and diverging colour maps
- [ ] KDE curves on arbitrary axes (`kdeplot`) including bivariate contours

### Regression (4 examples)
- [ ] Ordinary-least-squares fit with a confidence band and scatter (`regplot`), dependency-free; a statsmodels path stays optional for the model-based variants

### Not planned
- [ ] `clustermap` — hierarchical clustering and dendrogram layout need SciPy, which the dependency-free renderer does not take on

---

## 🔮 Later — Interactive & GUI (GPUI)

> Planned after 0.6: an optional interactive window built on GPUI. The static
> renderer and the default wheel stay headless and dependency-free.

- [ ] Separate, feature-gated crate (for example `matplotvite-gpui`) so the base wheel never links a GUI toolkit
- [ ] GPUI window with panning, zooming, hover readouts and legend toggles
- [ ] Incremental redraws from the Rust drawing model without rebuilding Python state
- [ ] Reuse the panel layout, colour and marker code; only the presentation backend changes
- [ ] GPU-backed preview for large series, with `savefig` remaining the source of truth for output
- [ ] `plt.show()` opens the GPUI window when it is installed and stays a no-op otherwise

---

## Out of scope (forever)

Animation (`FuncAnimation`), widgets, `%matplotlib inline`, and non-GPUI GUI backends (TkAgg, Qt, etc.). Interactive windows are a future GPUI target, not part of the static library.

---

## Cross-cutting / always-on

- Benchmarks page vs matplotlib — built from the checked-in results; refresh with `tools/benchmark.py`
- Backend comparison page — every gallery snippet run through Matplotlib Agg with per-snippet timings
- Comparison galleries harvested from Matplotlib's `@image_comparison` tests, Matplotlib's examples and Seaborn's examples — regenerated with `pytest -m gallery` (skipped when the checkouts are absent) and published as the `galleries-<sha>` CI artifact, with reference images copied alongside the HTML
- prek pre-commit hooks: `cargo fmt`, `cargo clippy --deny warnings`, `cargo test`, whitespace/EOF checks, and a commit-msg check that rejects `Co-Authored-By` trailers
- Mandatory security scan on pre-push and CI: `cargo audit`, Bandit on runtime Python, `pip-audit`, and secret-key detection
- Python test matrix: 3.9 → 3.14 on every PR (`maturin develop --release`, then `pytest`)
