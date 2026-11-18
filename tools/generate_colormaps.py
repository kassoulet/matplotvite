"""Generate the embedded matplotlib colormap registry.

matplotlib is a development-only tool here: the generated table
makes the built wheel independent of it. Run after upgrading matplotlib:

    python tools/generate_colormaps.py

Every registered base colormap is sampled at its own LUT resolution, and the
`_r` variants are derived by reversing the lookup index.
"""

import pathlib

import matplotlib
import numpy as np
from matplotlib.colors import ListedColormap, to_rgba

ROOT = pathlib.Path(__file__).resolve().parents[1]


def bright(value):
    """Convert one matplotlib colour to an 8-bit RGB triple."""
    return tuple(int(round(float(channel) * 255.0)) for channel in to_rgba(value)[:3])


def table(name):
    cmap = matplotlib.colormaps[name]
    if isinstance(cmap, ListedColormap):
        entries = [to_rgba(colour) for colour in cmap.colors]
    else:
        entries = [to_rgba(colour) for colour in cmap(np.linspace(0.0, 1.0, cmap.N))]
    return [bright(colour) for colour in entries]


def names():
    return sorted(name for name in matplotlib.colormaps if not name.endswith("_r"))


def write_data(registry):
    """One line per colormap: `name RRGGBB RRGGBB ...`, read by src/cmap_data.rs."""
    lines = [f"# matplotlib {matplotlib.__version__}"]
    for name in names():
        lines.append(name + " " + " ".join("{:02x}{:02x}{:02x}".format(*c) for c in registry[name]))
    (ROOT / "src" / "cmaps.txt").write_text("\n".join(lines) + "\n")


def main():
    registry = {name: table(name) for name in names()}
    write_data(registry)
    total = sum(len(colours) for colours in registry.values())
    print(
        f"wrote {len(registry)} base colormaps ({len(registry) * 2} names, "
        f"{total} colours) from matplotlib {matplotlib.__version__}"
    )


if __name__ == "__main__":
    main()
