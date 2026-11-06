Here is the updated, complete specification and developer prompt for **`plt.rs`**, fully aligned with your refined V1 constraints: **headless static image generation, zero Matplotlib dependency, and zero Pillow dependency** (with Rust handling both rendering and direct file I/O).

---

# Project Specification: `plt.rs` (V1 - Headless & Standalone)

## 1. Project Overview & Vision

* **Package Name (PyPI):** `plt-rs`
* **Import Namespace:** `import plt_rs as plt`
* **Mission:** Provide a lightning-fast, zero-dependency (in Python) plotting library that mimics the familiar Matplotlib API, but is implemented entirely in Rust using **PyO3**, NumPy, and the **`plotters`** crate.
* **Key Constraints:**
* **No Matplotlib:** Completely standalone Python API; no underlying dependency on matplotlib.
* **No Pillow (PIL):** Rust handles all rasterization, image encoding, and disk writing natively, keeping the Python installation pristine and lightweight.



---

## 2. Core Architecture & Data Flow

1. **The Python Wrapper (`plt_rs`)**: A pure-Python module defining familiar classes (`Figure`, `Axes`) and functions (`plt.plot()`, `plt.savefig()`) that collect data and style parameters.
2. **The PyO3 Bridge**: Passes NumPy arrays (via zero-copy memory views) and plotting metadata directly across the Python/Rust boundary.
3. **The Rust Backend (`plotters` + `std::fs`)**:
* Uses the `plotters` crate to draw geometries onto an in-memory buffer.
* Encodes the buffer directly to a PNG byte stream natively in Rust.
* Writes the file straight to disk via standard Rust file I/O (`std::fs::write`).



---

## 3. V1 API Scope

* `plt.figure(figsize=(width, height))`
* `plt.plot(x, y, label="...", color="...")`
* `plt.xlabel(text)`, `plt.ylabel(text)`, `plt.title(text)`
* `plt.legend()`
* `plt.savefig(filepath)`

---

## 4. Scaffold Prompt (Copy-Pasteable for Coding Agents)

Feed this prompt directly to an AI coding agent to bootstrap the repository:

```text
Act as a senior systems architect and PyO3/Rust extension specialist. Scaffold a v1 implementation of a standalone Python library named "plt.rs" (package name: plt-rs).

This library must have ZERO Python dependencies (no matplotlib, no pillow/PIL). It uses PyO3, Maturin, NumPy, and Rust's "plotters" crate to generate high-performance static plots directly from Rust and save them to disk.

Please generate:
1. Cargo.toml configuring a PyO3 cdylib extension with dependencies: pyo3, numpy, and plotters (with bitmap_backend and svg backend features).
2. pyproject.toml configured for maturin build system.
3. src/lib.rs containing a PyO3 module that accepts NumPy arrays (x, y) and configuration strings, sets up a plotters BitMapBackend, draws a line chart, encodes the image as a PNG natively in Rust, and writes it directly to a file path via std::fs.
4. python/plt_rs/__init__.py providing a clean, standalone matplotlib-compatible wrapper class/functions (e.g., plt.plot(), plt.savefig()) that invokes the Rust backend cleanly without importing any external plotting libraries.
5. A basic README.md with build instructions via maturin and a quick-start usage example.

```

---
