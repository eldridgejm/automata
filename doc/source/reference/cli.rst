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

    automata build [--current-time TIME] [--verbose]

Options:

- ``--current-time TIME`` --- Override the current time for release-time checks
  and date-based logic. Accepts ISO datetime (``"2026-01-15T12:00:00"``) or
  relative days (``"+5"`` for 5 days in the future, ``"-3"`` for 3 days in the
  past).
- ``--verbose`` / ``-v`` --- Show each recipe's output as it runs. By default
  it is captured: if a recipe fails, the error names the artifact (e.g.
  ``homeworks/01-intro/homework.pdf``), the recipe, its directory, and its exit
  status, followed by the last 30 lines of its output (stdout and stderr
  together). ``publish``, ``build-materials``, and ``export`` accept it too.


``automata publish``
--------------------

Build the site, then deploy it to the targets configured under ``publish:`` in
``automata.yaml`` (see :doc:`/guide/deployment`).

::

    automata publish [TARGET] [--current-time TIME] [--verbose]

With no ``TARGET``, publishes to every configured target, in order; prints
``Published to <target>.`` for each. An unknown target or strategy is an error,
reported before the site is built.


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

Show what is released and what is scheduled to be. It reports what the
materials say, as of now (or ``--current-time``); it doesn't look at any build,
since the site may be built and deployed elsewhere. Builds nothing.

::

    automata status [--verbose] [--json] [--current-time TIME]

Each artifact is *released* (its release time has passed, or it has none, and
it is ready), *scheduled* (its release time is in the future), *not ready*
(``ready: false``), or *missing* (no recipe, and its file doesn't exist). The
summary gives the number in each state and the next releases::

    Artifacts: 69 released, 4 scheduled, 7 not ready
    Next releases:
      exams/midterm/exam.pdf      2025-10-30 00:00 (in 40 days)
      exams/final/exam.pdf        2025-12-13 00:00 (in 84 days)

``--verbose`` lists every artifact and its state. ``--json`` prints the full
status as JSON, for programs; an error is printed as JSON too
(``{"error": "..."}``).


``automata calendar``
---------------------

Show week by week the dates in the materials' metadata (for example, each
homework's release and due dates, and each lecture's date), as a table in the
terminal, or written as an HTML page or a PDF. Which dates, how they are
labeled, and each collection's color are set in the ``calendar`` section of
``automata.yaml`` (see :doc:`/guide/configuration`); without it, this is an
error. Builds nothing.

::

    automata calendar [--collection NAME]... [--key KEY]... [--all]
                      [--from DATE] [--to DATE] [--week-start sunday|monday]
                      [--no-highlight-today] [--html FILE] [--pdf FILE]
                      [--ics FILE] [--json] [--current-time TIME]

``--collection`` shows only the named collections, and ``--key`` only dates
under the named metadata keys (glob patterns), e.g. ``--key due`` for just the
due dates; both may be given more than once. The calendar starts with the
current week; ``--all`` shows every week, and ``--from`` and ``--to``
(``YYYY-MM-DD``) set the dates shown. Weeks start on Sunday, unless
``--week-start monday``, and are numbered from the course's
``first_week_start``; the calendar is titled with the course's name and term.
``--html``, ``--pdf`` and ``--ics`` write the calendar to files instead of
printing it (``--ics`` as an iCalendar file, which calendar apps can import or
subscribe to; its events keep their identities when dates change, so that a
subscribed calendar updates them, and use ``--all`` to include past weeks); ``--json`` prints it as JSON, for programs. Dates
before the current time are shown dimmed, and today is highlighted (unless
``--no-highlight-today``). In the HTML, clicking a collection in the legend
hides its dates, or shows them again, and a button switches between light and
dark themes (by default, the system's). In the terminal, upcoming dates are
drawn as rounded pills, whose ends need a `Nerd Font <https://www.nerdfonts.com>`_.
If nothing matches, the message says what was looked for, and over which dates.


``automata check``
------------------

Check the project for problems, without building anything, and report every
problem found, not just the first. Exits with status 1 if there are any.

::

    automata check [--json] [--current-time TIME]

It checks, each on its own:

- ``automata.yaml``;
- the materials, one collection at a time, and released artifacts without a
  recipe whose file doesn't exist;
- each page's frontmatter and template syntax;
- the syntax of the theme's and extensions' templates;
- ``website.elements``: unknown elements, and configurations that don't match
  their element's schema, whether or not a page uses them;
- the publish targets and their strategies.

Some problems can only be found by building (a failing recipe, for example).
``--json`` prints ``{"problems": [{"area": ..., "message": ...}, ...]}``.


``automata pipeline``
---------------------

Run the stages of the pipeline one at a time, in this order; ``automata
build`` runs them all. Useful for debugging a build.

``automata pipeline clean``
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Empty the build directory, keeping top-level entries whose names start with a
dot (such as ``.git``). Refuses, with an error, if the build directory is or
contains the project or content directory; lies outside the project or inside
the content directory; contains an ``automata.yaml`` file or course materials;
or is, contains, or lies inside a directory extension.

::

    automata pipeline clean

``automata pipeline build-materials``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Discover and build materials (run recipes, check release times).

::

    automata pipeline build-materials [--current-time TIME] [--verbose]

``automata pipeline export-materials``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Discover, build, and export materials to the build directory.

::

    automata pipeline export-materials [--current-time TIME] [--verbose]

``automata pipeline render-website``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Render the website from the materials written by a previous ``automata
pipeline export-materials``. Fails if there are no exported materials (for
example, after ``automata pipeline clean``).

::

    automata pipeline render-website [--current-time TIME]
