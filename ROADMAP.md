# plt.rs roadmap (matplotlib features to add)

Done (V1): `figure`, `plot` (x/y, label, color), `xlabel/ylabel/title`, `legend`, `savefig` (PNG, SVG).

## V2: pyplot basics
- [ ] `plot`: `linestyle`, `linewidth`, `marker`, `markersize`, `alpha`, fmt strings (`"r--o"`)
- [ ] `scatter` (size, color, alpha, colormap)
- [ ] `bar` / `barh`, `hist`
- [ ] `xlim/ylim`, `axis`, `grid`, `xticks/yticks`
- [ ] `text`, `annotate`, `axhline/axvline`, `fill_between`
- [ ] Legend `loc`, `ncol`, `frameon`; font sizes
- [ ] Log scales (`xscale/yscale`)
- [ ] `savefig(dpi=, transparent=, facecolor=)`; `figure(dpi=)`

## V3: object API and layout
- [x] `subplots`, `subplot`, `add_subplot`, basic `Axes` (plot, set_title/xlabel/ylabel/xlim/ylim, legend); [ ] mixed grids, GridSpec, remaining Axes methods
- [ ] `tight_layout`, `suptitle`, `GridSpec`, `twinx/twiny`
- [ ] Shared axes (`sharex/sharey`)
- [ ] Style: `plt.style.use`, `rcParams`, color cycle, named/hex/RGB(A) colors, `tab10`/`C0`
- [x] Embedded Geist fonts (sans-serif, serif, monospace) via ab_glyph; no system font deps

## V4: more plot types
- [ ] `errorbar`, `step`, `stem`, `pie`, `boxplot`, `violinplot`
- [ ] `imshow`, `pcolormesh`, `contour/contourf`, colorbar + colormaps (viridis, ...)
- [ ] `hist2d`, `hexbin`, `stackplot`, `polar`, `quiver`

## V5: output and ecosystem
- [ ] PDF output; `savefig` to file-like object / bytes
- [ ] Pandas-friendly input (`data=`, label from Series)
- [ ] LaTeX-ish math text (subset)
- [ ] Date axes, categorical axes
- [ ] 3D (`plot_surface`, `scatter3D`), maybe

## Out of scope (for now)
Interactive windows/`show()`, animation, widgets, GUI backends.

## Cross-cutting
- Benchmarks vs matplotlib; wheels via maturin CI (manylinux, macOS, Windows); type stubs (`.pyi`).
