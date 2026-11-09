# Bolt's Journal

## 2026-03-30 - Lazy evaluation of axes extent in get_xlim/get_ylim
**Learning:** `get_xlim` and `get_ylim` repeatedly evaluated `_extent_x()` and `_extent_y()` even for linear scales and explicit limits. In `_log_bounds`, `extent` was always passed as an eagerly computed argument even though log adjustments only apply when `scale == "log"`. In addition, `self.xlim or self._extent_x()` caused double-evaluation of `_extent_x()`. Passing `extent` as a lazy callable cuts redundant full-series extent scans in half, consistently improving SVG export, multi-series, subplots, and line benchmarks without modifying shared data layout.
**Action:** When calculating bounds and limits that depend on conditional properties (e.g. log scale vs linear scale), compute expensive extents lazily rather than eagerly passing them.
