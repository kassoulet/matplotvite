# Bolt's Journal

## 2026-03-30 - Vectorizing axis limit spans
**Learning:** Matplotvite computes limits in Python (`_extent_x` and `_extent_y`) by calling `_span()` on flattened data points. For large series (10k-100k points), pure-Python list comprehensions (`[float(v) for v in values]` and filtering `np.isfinite`) created severe CPU bottlenecks and GC pressure, taking up over 85% of total savefig time. Vectorizing `_span()` with `np.asarray` and `np.isfinite` yields up to 37x faster span evaluation and brings 100k points PNG render from 554ms down to 64ms (speedup 0.4x -> 3.1x vs matplotlib).
**Action:** When computing summary bounds, min/max, or extents over plot inputs, always leverage NumPy vectorization instead of Python iteration/comprehensions.
