"""Render a first Matplotvite figure and write it beside this script."""

from __future__ import annotations

from pathlib import Path

import matplotvite as plt
import numpy as np


def main() -> Path:
    """Draw a damped sine wave and return the written PNG path."""
    x = np.linspace(0.0, 2.0 * np.pi, 200)
    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=120)
    ax.plot(x, np.sin(x) * np.exp(-0.2 * x), label="damped sine")
    ax.set_title("Matplotvite quickstart")
    ax.set_xlabel("x")
    ax.set_ylabel("amplitude")
    ax.grid(True, alpha=0.3)
    ax.legend()
    output = Path(__file__).with_name("quickstart.png")
    fig.savefig(output)
    print(f"wrote {output}")
    return output


if __name__ == "__main__":
    main()
