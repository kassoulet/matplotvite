Matplotvite
===========

Matplotvite renders matplotlib-style static figures with a Rust renderer and
NumPy as its only runtime dependency.

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
