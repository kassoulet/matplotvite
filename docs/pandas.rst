Pandas plotting backend
=======================

Matplotvite implements pandas' plotting backend protocol. Pandas remains
optional; setting the backend does not add a runtime dependency.

.. code-block:: python

   import pandas as pd
   import matplotvite

   pd.options.plotting.backend = "matplotvite"

   frame = pd.DataFrame(
       {"north": [3, 5, 2], "south": [2, 4, 3]},
       index=["alpha", "beta", "gamma"],
   )
   frame.plot(kind="bar")
   matplotvite.savefig("bars.png")

``frame.plot(kind=...)`` and the accessors ``frame.plot.line()``,
``frame.plot.bar()``, ``frame.plot.box()`` and the other pandas accessors work
through the same entry point.

Supported kinds
---------------

``line``, ``bar``, ``barh``, ``hist``, ``box``, ``area``, ``scatter`` and
``pie``.

- ``line``, ``bar``, ``barh`` and ``area`` plot every selected numeric column
  and label it with the column name.
- ``bar`` and ``barh`` group columns side by side unless ``stacked=True``.
- ``hist`` accepts ``bins``, ``density``, ``stacked`` and the usual histogram
  styling keywords; it follows pandas' ``Frequency`` y-label default.
- ``box`` uses one box per selected column and names the ticks after the
  columns.
- ``scatter`` requires both ``x=`` and ``y=``.
- ``pie`` uses the one selected value column and labels slices from the index.
- ``ax=`` draws into an existing matplotvite axes, and the style keywords
  (``color``, ``linewidth``, ``marker``, ``alpha``, ``title``, ``grid``,
  ``rot``, ``logx``/``logy`` and ``xlim``/``ylim``) pass through.

Datetime indexes keep the renderer's date locator and formatter. Categorical
indexes use their labels as ticks. MultiIndex row and column labels are shown
as ``"level / level"`` strings.

Unsupported behaviour
---------------------

An unknown ``kind`` raises ``ValueError`` listing the supported values instead
of drawing a different chart. ``subplots=True`` raises
``NotImplementedError``.

Version support
---------------

The backend targets pandas 2.x and 3.x. CI runs the tests against the latest
pandas release resolved for each supported Python version (3.9 through 3.14);
pandas 2.x is used where pandas 3.x no longer supports the interpreter. Older
pandas releases are not tested.
