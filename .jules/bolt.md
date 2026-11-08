# Bolt journal

## 2026-11-08 - PNG save prep: demultiply, not the clone, is the cost

**Learning:** `encode_png` copied the pixmap and then demultiplied it on every
save. An A/B toggle (same session, interleaved) showed skipping both is worth
~4% of `savefig` at 750×450 and ~14% at 1500×900, but the demultiplication pass
is essentially all of it — removing the clone alone moved nothing. PNG prep
cost is also invisible for WebP because its lossless encoder takes 146 ms–1.25 s,
so optimizing shared prep code for WebP is wasted effort. Stored Criterion
baselines on this host are unstable under load; use same-session toggles for
small deltas and treat `--baseline` comparisons with p > 0.05 as noise.
**Action:** When saving figures, exploit the known-opaque canvas instead of
demultiplying; measure encode-stage changes with a toggle, not a stale baseline.
