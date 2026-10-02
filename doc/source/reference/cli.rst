CLI Reference
=============

Commands can be run from the project root (the directory containing
``automata.yaml``) or from any directory inside it: automata searches upward
from the current directory for ``automata.yaml`` and uses the first one it
finds. When that is not the current directory, it says so::

    $ cd website/content
    $ automata build
    Using project at /path/to/course

If no ``automata.yaml`` is found in the current directory or any parent, the
command prints an error and exits with status 1.


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


``automata publish``
--------------------

Build the site, then deploy it to the targets configured under ``publish:`` in
``automata.yaml`` (see :doc:`/guide/deployment`).

::

    automata publish [TARGET] [--current-time TIME]

With no ``TARGET``, publishes to every configured target, in order; prints
``Published to <target>.`` for each. An unknown target or strategy is an error,
reported before the site is built.


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
