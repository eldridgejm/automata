CLI Reference
=============

All commands are run from the project root (the directory containing
``automata.yaml``).


``automata generate``
---------------------

Run the full pipeline: discover, build, export, and generate website.

::

    automata generate [--current-time TIME]

Options:

- ``--current-time TIME`` --- Override the current time for release-time checks
  and date-based logic. Accepts ISO datetime (``"2026-01-15T12:00:00"``) or
  relative days (``"+5"`` for 5 days in the future, ``"-3"`` for 3 days in the
  past).


``automata discover``
---------------------

Discover materials and print a summary.

::

    automata discover

Prints the number of publications in each collection.


``automata build-materials``
----------------------------

Discover and build materials (run recipes, check release times).

::

    automata build-materials [--current-time TIME]


``automata export``
-------------------

Discover, build, and export materials to the build directory.

::

    automata export [--current-time TIME]


``automata resolve``
--------------------

Resolve a ``publication.yaml`` file and output as JSON.

::

    automata resolve PATH

Arguments:

- ``PATH`` --- Path to the ``publication.yaml`` file to resolve.

This is useful for debugging: it shows the fully-resolved publication with all
variables interpolated and defaults applied.


``automata status``
-------------------

Check the status of course materials.

::

    automata status
