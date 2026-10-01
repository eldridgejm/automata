CLI Reference
=============

All commands are run from the project root (the directory containing
``automata.yaml``).


``automata build``
------------------

Run the full pipeline and produce the site in the build directory: clean the
build directory (unless ``website.clean_build_directory`` is false), discover,
build materials, export, and render the website. ``automata publish`` runs this
and then deploys.

::

    automata build [--current-time TIME]

Options:

- ``--current-time TIME`` --- Override the current time for release-time checks
  and date-based logic. Accepts ISO datetime (``"2026-01-15T12:00:00"``) or
  relative days (``"+5"`` for 5 days in the future, ``"-3"`` for 3 days in the
  past).


``automata clean-build-directory``
----------------------------------

Empty the build directory, keeping top-level entries whose names start with a
dot (such as ``.git``). Refuses, with an error, if the build directory is or
contains the project or content directory, lies inside the content directory,
or contains an ``automata.yaml`` file.

::

    automata clean-build-directory


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


``automata render-website``
---------------------------

Render the website from the materials written by a previous
``automata export``. Fails if there are no exported materials (for example,
after ``automata clean-build-directory``).

::

    automata render-website [--current-time TIME]


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
