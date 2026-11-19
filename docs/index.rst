Matplotvite
===========

Matplotvite renders matplotlib-style static figures with a Rust renderer and
NumPy as its only runtime dependency.

The native implementation is split into three crates: ``matplotvite-core`` owns
the drawing model, layout, rasterisation and export pipeline and builds without
Python; ``matplotvite`` exposes the native ``Figure``/``Axes`` builder; and
``matplotvite-py`` is the thin PyO3 extension used by this package. See
`architecture.md <https://github.com/kassoulet/matplotvite/blob/main/architecture.md>`_
for the module map and data flow.

.. code-block:: python

   import numpy as np
   import matplotvite as plt

   fig, ax = plt.subplots()
   ax.plot(np.arange(5), np.arange(5) ** 2)
   fig.savefig("plot.png")

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api
