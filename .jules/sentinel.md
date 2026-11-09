# Sentinel's Journal - Critical Security Learnings

## 2026-03-30 - Unbounded Canvas Dimensions Causing Out-Of-Memory / Integer Overflows
**Vulnerability:** Figure size (`figsize`) and resolution (`dpi`) were accepted without positive-finite validation or maximum bounds checking in both Python and Rust layers. Unchecked parameters allowed non-positive or excessive numbers, leading to integer overflow conversions or multi-terabyte buffer allocations in Rust rendering engines that crashed or aborted the host process (Denial of Service).
**Learning:** PyO3 bindings converting Python floats directly into integer pixel counts (`(round(w * dpi), round(h * dpi))`) without range validation can cause `OverflowError` on negative/infinite inputs and immediate OOM aborts on huge values in native rasterizers (`tiny-skia` / `resvg`).
**Prevention:** Validate dimension inputs at the Python API boundary (`_validate_dimension`) ensuring positive, finite numbers and reasonable upper bounds on pixel dimensions (32,768px) and total pixel count (2^28 px), and mirror the bounds checking defensively in Rust before memory allocations.
