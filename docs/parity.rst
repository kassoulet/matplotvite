Parity evidence
===============

Matplotvite tracks compatibility against pinned Matplotlib and Seaborn material
rather than only curated examples.

Matplotlib corpus
-----------------

``tests/mpl_corpus.json`` contains every harvested Matplotlib 3.11.2
``@image_comparison`` case: 526 rewritten snippets and SHA-256 hashes of all
expected baseline images. The metadata is generated, never hand-edited.

.. code-block:: bash

   # Refresh the checked-in metadata after a deliberate corpus change.
   python tools/harvest_matplotlib.py --source dist/mpl-sdist \
       --write-metadata tests/mpl_corpus.json

   # CI check: fail when the checked-in metadata is stale.
   python tools/harvest_matplotlib.py --source dist/mpl-sdist \
       --check-metadata tests/mpl_corpus.json

   # Render only cases added or changed since the metadata was written.
   python tools/harvest_matplotlib.py --source dist/mpl-sdist \
       --changed-from tests/mpl_corpus.json --out dist/mpl-corpus

The full corpus run currently renders 495 of 526 cases, with 0 failures, 26
unsupported cases and 5 intentionally blank cases. Pixel metrics remain in the
gallery manifest so a successful render is not mistaken for visual parity.

Seaborn wrapper scenes
----------------------

``tests/seaborn_scenes.py`` defines six scenes that reduce to the current
Matplotlib API: ``lineplot``, ``scatterplot``, ``barplot``, ``histplot``,
``boxplot`` and ``heatmap``. ``tests/test_seaborn_parity.py`` renders each scene
through matplotvite, compares it with the committed Matplotlib reference under
``tests/seaborn/``, and enforces the per-scene RGBA RMS tolerance in
``tests/seaborn/scenes.txt``.

These references test the wrappers' underlying bands, markers, grouped bars,
density bars, box statistics and annotated matrices. They are not a claim that
the full Seaborn API is implemented; the harvested gallery keeps the remaining
capabilities ranked by demand.

Pandas backend
--------------

The pandas backend is covered separately by ``tests/test_pandas_backend.py``:
all supported ``kind=`` values, DataFrame/Series defaults, datetime and
categorical indexes, MultiIndex flattening, style/layout keywords, existing axes
and the explicit errors for unsupported kinds. See :doc:`pandas` for usage and
the supported version matrix.
