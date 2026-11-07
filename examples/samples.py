"""Sample use cases and gallery definitions for plt_rs."""

from __future__ import annotations

import numpy as np
import plt_rs as plt


def run_trigonometric_waves(out_path: str) -> None:
    x = np.linspace(0, 10, 200)
    plt.figure(figsize=(7.5, 4.5))
    plt.plot(x, np.sin(x), label="sin(x)", color="red")
    plt.plot(x, np.cos(x), label="cos(x)", color="blue")
    plt.title("Trigonometric Waves")
    plt.xlabel("x (radians)")
    plt.ylabel("Amplitude")
    plt.legend()
    plt.savefig(out_path)


def run_damped_harmonic(out_path: str) -> None:
    t = np.linspace(0, 10, 400)
    y = np.exp(-0.35 * t) * np.cos(2 * np.pi * 0.75 * t)
    envelope = np.exp(-0.35 * t)
    plt.figure(figsize=(7.5, 4.5))
    plt.plot(t, y, label="Displacement", color="#1f77b4")
    plt.plot(t, envelope, label="Upper Envelope", color="#ff7f0e")
    plt.plot(t, -envelope, label="Lower Envelope", color="#ff7f0e")
    plt.title("Damped Harmonic Oscillator")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude (m)")
    plt.legend()
    plt.savefig(out_path)


def run_polynomial_family(out_path: str) -> None:
    x = np.linspace(0.1, 2.5, 120)
    plt.figure(figsize=(7.5, 4.5))
    plt.plot(x, x, label="Linear: x")
    plt.plot(x, x**1.5, label="Sub-quadratic: x^1.5")
    plt.plot(x, x**2, label="Quadratic: x^2")
    plt.plot(x, np.log(x + 1), label="Log: log(x+1)")
    plt.title("Function Growth & Automatic Color Cycle")
    plt.xlabel("Input x")
    plt.ylabel("Output f(x)")
    plt.legend()
    plt.savefig(out_path)


def run_custom_limits(out_path: str) -> None:
    x = np.linspace(-6, 6, 300)
    y = np.sinc(x)
    plt.figure(figsize=(7.5, 4.5))
    plt.plot(x, y, label="sinc(x) = sin(pi*x)/(pi*x)", color="#2ca02c")
    plt.xlim(-5.0, 5.0)
    plt.ylim(-0.35, 1.1)
    plt.title("Cardinal Sine with Explicit Bounds")
    plt.xlabel("Normalized x")
    plt.ylabel("sinc(x)")
    plt.legend()
    plt.savefig(out_path)


def run_discrete_signal(out_path: str) -> None:
    samples = [4, 7, 2, 9, 12, 11, 15, 14, 18, 16, 22, 20, 25]
    plt.figure(figsize=(7.5, 4.5))
    plt.plot(samples, label="Measurement series", color="black")
    plt.title("Discrete Signal (Implicit 0..N-1 Indices)")
    plt.xlabel("Sample Index")
    plt.ylabel("Measurement Value")
    plt.legend()
    plt.savefig(out_path)


def run_subplots_grid(out_path: str) -> None:
    x = np.linspace(0, 2 * np.pi, 200)
    fig, axs = plt.subplots(2, 2, figsize=(8.5, 6.0))

    axs[0, 0].plot(x, np.sin(x), color="red")
    axs[0, 0].set_title("Sine Wave")
    axs[0, 0].set_xlabel("x")
    axs[0, 0].set_ylabel("sin(x)")

    axs[0, 1].plot(x, np.cos(x), color="blue")
    axs[0, 1].set_title("Cosine Wave")
    axs[0, 1].set_xlabel("x")
    axs[0, 1].set_ylabel("cos(x)")

    axs[1, 0].plot(x, np.sin(2 * x), color="green")
    axs[1, 0].set_title("Double Frequency")
    axs[1, 0].set_xlabel("x")
    axs[1, 0].set_ylabel("sin(2x)")

    axs[1, 1].plot(x, np.abs(np.sin(x)), color="orange")
    axs[1, 1].set_title("Rectified Wave")
    axs[1, 1].set_xlabel("x")
    axs[1, 1].set_ylabel("|sin(x)|")

    fig.savefig(out_path)


def run_side_by_side(out_path: str) -> None:
    x = np.linspace(0.1, 4.0, 150)
    plt.figure(figsize=(9.0, 4.5))

    plt.subplot(1, 2, 1)
    plt.plot(x, np.exp(x / 2), color="red", label="exp(x/2)")
    plt.title("Exponential Growth")
    plt.xlabel("x")
    plt.ylabel("exp(x/2)")
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(x, np.log(x), color="blue", label="ln(x)")
    plt.title("Logarithmic Growth")
    plt.xlabel("x")
    plt.ylabel("ln(x)")
    plt.legend()

    plt.savefig(out_path)


def run_svg_export(out_path: str) -> None:
    x = np.linspace(0, 10, 250)
    y = np.sin(x) / (0.5 * x + 1.0)
    plt.figure(figsize=(7.5, 4.5))
    plt.plot(x, y, label="sin(x)/(0.5x+1)", color="#9467bd")
    plt.title("Vector Graphics Export (SVG)")
    plt.xlabel("x (arbitrary units)")
    plt.ylabel("y")
    plt.legend()
    plt.savefig(out_path)


def run_contours_colorbar(out_path: str) -> None:
    x = np.linspace(-3, 3, 120)
    y = np.linspace(-3, 3, 120)
    z = np.exp(-(x[None, :] ** 2 + y[:, None] ** 2))
    plt.figure(figsize=(7.0, 4.5))
    plt.contourf(x, y, z, levels=8)
    plt.colorbar(label="density")
    plt.title("Filled Contours with Colorbar")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.savefig(out_path)


def run_scatter_errorbar(out_path: str) -> None:
    rng = np.random.default_rng(7)
    x = np.linspace(1, 10, 24)
    y = np.log(x) + rng.normal(0, 0.08, x.size)
    err = rng.uniform(0.05, 0.2, x.size)
    plt.figure(figsize=(7.5, 4.5))
    plt.errorbar(x, y, yerr=err, fmt="", capsize=3, ecolor="#9467bd")
    plt.scatter(x, y, s=48, c=y, cmap="viridis", marker="o")
    plt.title("Scatter with Error Bars")
    plt.xlabel("x")
    plt.ylabel("log(x) + noise")
    plt.savefig(out_path)


def run_imshow_heatmap(out_path: str) -> None:
    x = np.linspace(-2, 2, 200)
    y = np.linspace(-2, 2, 120)
    z = np.sin(3 * x[None, :]) * np.cos(2 * y[:, None])
    plt.figure(figsize=(6.0, 4.0))
    plt.imshow(z, cmap="viridis", extent=(-2, 2, -2, 2))
    plt.colorbar(label="amplitude")
    plt.title("Heatmap (imshow) with Colorbar")
    plt.savefig(out_path)


SAMPLES: list[dict[str, object]] = [
    {
        "id": "trigonometric_waves",
        "title": "Trigonometric Waves",
        "category": "Basics",
        "description": "Multi-line plotting with custom colors, legend, and descriptive axis labels.",
        "filename": "trigonometric_waves.png",
        "format": "png",
        "runner": run_trigonometric_waves,
        "code": """import numpy as np
import plt_rs as plt

x = np.linspace(0, 10, 200)
plt.figure(figsize=(7.5, 4.5))
plt.plot(x, np.sin(x), label="sin(x)", color="red")
plt.plot(x, np.cos(x), label="cos(x)", color="blue")
plt.title("Trigonometric Waves")
plt.xlabel("x (radians)")
plt.ylabel("Amplitude")
plt.legend()
plt.savefig("trigonometric_waves.png")
""",
    },
    {
        "id": "damped_harmonic",
        "title": "Damped Harmonic Oscillator",
        "category": "Physics & Math",
        "description": "High-density sampling showing an oscillatory curve nested inside exponential decay envelopes.",
        "filename": "damped_harmonic.png",
        "format": "png",
        "runner": run_damped_harmonic,
        "code": """import numpy as np
import plt_rs as plt

t = np.linspace(0, 10, 400)
y = np.exp(-0.35 * t) * np.cos(2 * np.pi * 0.75 * t)
envelope = np.exp(-0.35 * t)

plt.figure(figsize=(7.5, 4.5))
plt.plot(t, y, label="Displacement", color="#1f77b4")
plt.plot(t, envelope, label="Upper Envelope", color="#ff7f0e")
plt.plot(t, -envelope, label="Lower Envelope", color="#ff7f0e")
plt.title("Damped Harmonic Oscillator")
plt.xlabel("Time (s)")
plt.ylabel("Amplitude (m)")
plt.legend()
plt.savefig("damped_harmonic.png")
""",
    },
    {
        "id": "polynomial_family",
        "title": "Function Family & Color Cycle",
        "category": "Basics",
        "description": "Showcasing multiple curves taking distinct colors automatically from the built-in color cycle.",
        "filename": "polynomial_family.png",
        "format": "png",
        "runner": run_polynomial_family,
        "code": """import numpy as np
import plt_rs as plt

x = np.linspace(0.1, 2.5, 120)
plt.figure(figsize=(7.5, 4.5))
plt.plot(x, x, label="Linear: x")
plt.plot(x, x**1.5, label="Sub-quadratic: x^1.5")
plt.plot(x, x**2, label="Quadratic: x^2")
plt.plot(x, np.log(x + 1), label="Log: log(x+1)")
plt.title("Function Growth & Automatic Color Cycle")
plt.xlabel("Input x")
plt.ylabel("Output f(x)")
plt.legend()
plt.savefig("polynomial_family.png")
""",
    },
    {
        "id": "custom_limits",
        "title": "Explicit Axis Bounds (xlim / ylim)",
        "category": "Styling & Bounds",
        "description": "Using xlim() and ylim() to zoom into region of interest on a normalized cardinal sine curve.",
        "filename": "custom_limits.png",
        "format": "png",
        "runner": run_custom_limits,
        "code": """import numpy as np
import plt_rs as plt

x = np.linspace(-6, 6, 300)
y = np.sinc(x)

plt.figure(figsize=(7.5, 4.5))
plt.plot(x, y, label="sinc(x) = sin(pi*x)/(pi*x)", color="#2ca02c")
plt.xlim(-5.0, 5.0)
plt.ylim(-0.35, 1.1)
plt.title("Cardinal Sine with Explicit Bounds")
plt.xlabel("Normalized x")
plt.ylabel("sinc(x)")
plt.legend()
plt.savefig("custom_limits.png")
""",
    },
    {
        "id": "discrete_signal",
        "title": "Discrete Signal (Implicit X Indices)",
        "category": "Basics",
        "description": "Plotting sequential 1D values with plt.plot(y), implicitly using range 0..N-1 as x-axis.",
        "filename": "discrete_signal.png",
        "format": "png",
        "runner": run_discrete_signal,
        "code": """import plt_rs as plt

samples = [4, 7, 2, 9, 12, 11, 15, 14, 18, 16, 22, 20, 25]
plt.figure(figsize=(7.5, 4.5))
plt.plot(samples, label="Measurement series", color="black")
plt.title("Discrete Signal (Implicit 0..N-1 Indices)")
plt.xlabel("Sample Index")
plt.ylabel("Measurement Value")
plt.legend()
plt.savefig("discrete_signal.png")
""",
    },
    {
        "id": "subplots_grid",
        "title": "2x2 Subplots Grid (Object-Oriented API)",
        "category": "Subplots & Layouts",
        "description": "Multi-panel figure created using fig, axs = plt.subplots(2, 2) with individual axes customization.",
        "filename": "subplots_grid.png",
        "format": "png",
        "runner": run_subplots_grid,
        "code": """import numpy as np
import plt_rs as plt

x = np.linspace(0, 2 * np.pi, 200)
fig, axs = plt.subplots(2, 2, figsize=(8.5, 6.0))

axs[0, 0].plot(x, np.sin(x), color="red")
axs[0, 0].set_title("Sine Wave")
axs[0, 0].set_xlabel("x")
axs[0, 0].set_ylabel("sin(x)")

axs[0, 1].plot(x, np.cos(x), color="blue")
axs[0, 1].set_title("Cosine Wave")
axs[0, 1].set_xlabel("x")
axs[0, 1].set_ylabel("cos(x)")

axs[1, 0].plot(x, np.sin(2 * x), color="green")
axs[1, 0].set_title("Double Frequency")
axs[1, 0].set_xlabel("x")
axs[1, 0].set_ylabel("sin(2x)")

axs[1, 1].plot(x, np.abs(np.sin(x)), color="orange")
axs[1, 1].set_title("Rectified Wave")
axs[1, 1].set_xlabel("x")
axs[1, 1].set_ylabel("|sin(x)|")

fig.savefig("subplots_grid.png")
""",
    },
    {
        "id": "side_by_side",
        "title": "Side-by-Side Panels (Pyplot API)",
        "category": "Subplots & Layouts",
        "description": "Two comparative subplots side-by-side using the stateful plt.subplot(1, 2, index) function.",
        "filename": "side_by_side.png",
        "format": "png",
        "runner": run_side_by_side,
        "code": """import numpy as np
import plt_rs as plt

x = np.linspace(0.1, 4.0, 150)
plt.figure(figsize=(9.0, 4.5))

plt.subplot(1, 2, 1)
plt.plot(x, np.exp(x / 2), color="red", label="exp(x/2)")
plt.title("Exponential Growth")
plt.xlabel("x")
plt.ylabel("exp(x/2)")
plt.legend()

plt.subplot(1, 2, 2)
plt.plot(x, np.log(x), color="blue", label="ln(x)")
plt.title("Logarithmic Growth")
plt.xlabel("x")
plt.ylabel("ln(x)")
plt.legend()

plt.savefig("side_by_side.png")
""",
    },
    {
        "id": "svg_export",
        "title": "Scalable Vector Graphics (SVG)",
        "category": "Vectors & Exports",
        "description": "Zero-loss resolution-independent vector rendering exported straight from Rust's SVG backend.",
        "filename": "svg_export.svg",
        "format": "svg",
        "runner": run_svg_export,
        "code": """import numpy as np
import plt_rs as plt

x = np.linspace(0, 10, 250)
y = np.sin(x) / (0.5 * x + 1.0)

plt.figure(figsize=(7.5, 4.5))
plt.plot(x, y, label="sin(x)/(0.5x+1)", color="#9467bd")
plt.title("Vector Graphics Export (SVG)")
plt.xlabel("x (arbitrary units)")
plt.ylabel("y")
plt.legend()
plt.savefig("svg_export.svg")
""",
    },
    {
        "id": "contours_colorbar",
        "title": "Filled Contours with Colorbar",
        "category": "Gridded Data",
        "description": "contourf() renders filled iso-bands and colorbar() adds a gradient scale with ticks.",
        "filename": "contours_colorbar.png",
        "format": "png",
        "runner": run_contours_colorbar,
        "code": """import numpy as np
import plt_rs as plt

x = np.linspace(-3, 3, 120)
y = np.linspace(-3, 3, 120)
z = np.exp(-(x[None, :] ** 2 + y[:, None] ** 2))

plt.figure(figsize=(7.0, 4.5))
plt.contourf(x, y, z, levels=8)
plt.colorbar(label="density")
plt.title("Filled Contours with Colorbar")
plt.xlabel("x")
plt.ylabel("y")
plt.savefig("contours_colorbar.png")
""",
    },
    {
        "id": "scatter_errorbar",
        "title": "Scatter with Error Bars",
        "category": "Statistics & Uncertainty",
        "description": "Per-point marker sizes and colours from a colormap, over error bars with caps.",
        "filename": "scatter_errorbar.png",
        "format": "png",
        "runner": run_scatter_errorbar,
        "code": """import numpy as np
import plt_rs as plt

rng = np.random.default_rng(7)
x = np.linspace(1, 10, 24)
y = np.log(x) + rng.normal(0, 0.08, x.size)
err = rng.uniform(0.05, 0.2, x.size)

plt.figure(figsize=(7.5, 4.5))
plt.errorbar(x, y, yerr=err, fmt="", capsize=3, ecolor="#9467bd")
plt.scatter(x, y, s=48, c=y, cmap="viridis", marker="o")
plt.title("Scatter with Error Bars")
plt.xlabel("x")
plt.ylabel("log(x) + noise")
plt.savefig("scatter_errorbar.png")
""",
    },
    {
        "id": "imshow_heatmap",
        "title": "Heatmap with Colorbar (imshow)",
        "category": "Gridded Data",
        "description": "A 2-D array rendered through viridis, with equal aspect and a colorbar scale.",
        "filename": "imshow_heatmap.png",
        "format": "png",
        "runner": run_imshow_heatmap,
        "code": """import numpy as np
import plt_rs as plt

x = np.linspace(-2, 2, 200)
y = np.linspace(-2, 2, 120)
z = np.sin(3 * x[None, :]) * np.cos(2 * y[:, None])

plt.figure(figsize=(6.0, 4.0))
plt.imshow(z, cmap="viridis", extent=(-2, 2, -2, 2))
plt.colorbar(label="amplitude")
plt.title("Heatmap (imshow) with Colorbar")
plt.savefig("imshow_heatmap.png")
""",
    },
]
