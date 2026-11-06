# plt.rs

Matplotlib-style static plots, rendered and saved to PNG entirely in Rust (PyO3 + plotters).
Python deps: numpy only. No matplotlib, no Pillow.

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

## Test
```bash
pip install pytest && pytest
```
