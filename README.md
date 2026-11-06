# plt.rs

Matplotlib-style static plots, rendered and saved to PNG entirely in Rust (PyO3 + plotters).
Python deps: numpy only. No matplotlib, no Pillow.

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
