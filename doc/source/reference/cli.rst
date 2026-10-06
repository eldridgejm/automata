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

Extensions can add commands of their own, which ``automata --help`` lists under
"Extensions" (see :ref:`extension-commands`).


.. _cli-init:

``automata init``
-----------------

Create a new project in the current directory. Unlike the other commands, it
doesn't need an existing project.

::

    automata init

It creates an ``automata.yaml`` and a ``website`` directory::

    automata.yaml           the course, the website, and (commented) examples
    website/
        content/
            index.md        the home page, showing the schedule
            syllabus.md     a page linked from the navigation
        schedule.yaml       the schedule's weeks, events, and announcements

The course's name, title, term, and first week start are placeholders: fill
them in, then run ``automata serve`` to see the site. Nothing else in the
directory is changed, so ``init`` can be run in a directory that already holds
your course materials. If ``automata.yaml`` or ``website`` already exists, or
the directory is inside another project (an ``automata.yaml`` is found in a
parent directory), it prints an error and creates nothing. From Python, this is
:meth:`Automata.init`.


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
  together). ``publish``, ``pipeline build-materials``, and
  ``pipeline export-materials`` accept it too.

It reports its progress: how many collections and publications were
discovered, how many artifacts were built (and how many by their recipes), how
many were skipped and why (not released yet, not ready, or missing), and how
long the build took::

    → Discovered 4 collections, 40 publications.
    ✓ Built 69 artifacts (69 by their recipes).
    ○ Skipped 11 artifacts: 4 not released yet, 7 not ready.
    ✓ Built the site in _build (1.6 s).

On a terminal, this is in color, and a spinner shows what is happening at the
moment (discovering, building materials, with the count so far and the recipe
running, exporting, or rendering), on a line that each of these replaces when
done. With ``--verbose``, there is no spinner: each recipe is named before its
output instead. ``automata publish`` reports the same.


``automata serve``
------------------

Build the site and serve it locally, then rebuild it whenever a file in the
project changes, until stopped with Ctrl-C.

::

    automata serve [--port PORT] [--no-open] [--current-time TIME] [--verbose]

The site is served at ``http://127.0.0.1:8000`` (or ``--port``), under
``website.base_path`` if that is an absolute path such as ``/course/``, and
opened in the default browser once it is built (unless ``--no-open``). Pages
reload themselves after each rebuild. A new or changed page only re-renders the
website, which is quick; any other change (to ``automata.yaml``, the materials,
an extension, or a deleted page) reloads the project and builds it all. If a
build fails, the error is printed, and shown at the bottom of the open pages,
while the last good build is still served. Files whose names start with a dot
(such as ``.git``) are not watched, and neither is the build directory, nor
the files a build writes itself (such as recipes' outputs). With
``--current-time``, every build is for that time; otherwise, each is for the
time it runs.


``automata archive``
--------------------

Build the materials, and zip them up (or write them to a directory), with
``materials.json`` describing them. The website, and the build directory, are
untouched.

::

    automata archive [PATH] [--all] [--current-time TIME] [--verbose]

If ``PATH`` ends in ``.zip``, it is the zip written; by default, one named after
the course in the project directory (e.g. ``dsc-40b-fall-2026-materials.zip``).
The zip's contents are in a folder named like it: each artifact as
``<collection>/<publication>/<artifact>``.

Otherwise, ``PATH`` is a directory, which holds the materials themselves (each
artifact as ``<collection>/<publication>/<artifact>``, and ``materials.json``),
laid out as ``automata pipeline export-materials --to`` writes them, e.g. for a
browsable preview of a branch's materials::

    automata archive --all _preview/materials

An existing directory's contents are replaced, so that withdrawn artifacts
don't linger. To keep from deleting anything else, the directory must be empty
or have been written by ``archive`` or ``export-materials`` (it has a
``materials.json``); otherwise, it is an error, and nothing is built or
changed. So is a ``PATH`` that is a file but not a ``.zip``, or that is or
contains the project directory.

``--all`` includes the artifacts that are not released yet, or not ready, for
an archive of everything (at the end of a term, say). It reports the build's
progress, as ``automata build`` does.


``automata publish``
--------------------

Build the site, then deploy it to the targets configured under ``publish:`` in
``automata.yaml`` (see :doc:`/guide/deployment`).

::

    automata publish [TARGET] [--dry-run] [--json] [--current-time TIME]
                     [--verbose]

With no ``TARGET``, publishes to every configured target, in order, and says
what each one changed::

    ✓ Published to github (gh-pages): 3 files changed.
    ✓ Published to server (rsync).

(``nothing changed`` if nothing did; rsync, and an extension's strategy, may
not say.) An unknown target or strategy is an error, reported before the site
is built.

``--dry-run`` builds the site, then says what publishing would change, without
publishing: for each target, the files that would be added (``A``), modified
(``M``), or deleted (``D``), relative to the site's root, in order of path::

    Publishing to github (gh-pages) would change 3 files:
      A CNAME
      M index.html
      D materials/homeworks/hw01/old.pdf
    Publishing to server (rsync) would change nothing.

It changes nothing where the site is published (gh-pages and git fetch the
branch, but push nothing; rsync runs with ``--dry-run``), needs no git identity,
and exits with status 0 whether or not anything would change. A target whose
strategy can't do a dry run (an extension's strategy may not) is an error,
reported before the site is built.

``--json``, with or without ``--dry-run``, prints what each target changed (or
would change) as JSON instead (the build's progress goes to stderr), e.g. for a
CI job that comments on a pull request::

    {
      "targets": {
        "github": {
          "strategy": "gh-pages",
          "dry_run": true,
          "changes": [
            {"status": "added", "path": "CNAME"},
            {"status": "modified", "path": "index.html"}
          ]
        }
      }
    }

A ``status`` is ``added``, ``modified``, or ``deleted``; ``changes`` is ``null``
for a target whose strategy doesn't report them. An error is printed as
``{"error": "..."}``, with status 1.


``automata resolve``
--------------------

Print the materials, resolved, as JSON: every collection and publication,
with their metadata, and every artifact, with its recipe, release time, and
whether it is ready. Builds nothing.

::

    automata resolve [TARGET]

``TARGET`` limits it to one collection or publication: its key (such as
``homeworks`` or ``homeworks/hw01``), or the path of its directory or YAML file
(such as ``homeworks/hw01/publication.yaml``). This is useful for debugging:
it shows each publication fully resolved, with its variables interpolated and
its defaults applied. A key that names nothing is an error. (In Python,
:meth:`Automata.discover` gives all the materials, resolved.)


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
homework's release and due dates, and each lecture's date), and events of their
own (exams, holidays), as a table in the terminal, or written as an HTML page or
a PDF. Which dates, how they are labeled, and each category's color are set in
the ``calendar`` section of ``automata.yaml`` (see :doc:`/guide/configuration`);
without it, this is an error. Its categories are its collections and event
groups. Builds nothing.

::

    automata calendar [CATEGORY]... [--key KEY]... [--all]
                      [--from DATE] [--to DATE] [--week-start sunday|monday]
                      [--no-highlight-today] [--html FILE] [--pdf FILE]
                      [--ics FILE] [--json] [--current-time TIME]

Naming categories shows only those (e.g. ``automata calendar exams holidays``),
and ``--key`` shows only dates under the named metadata keys (glob patterns),
e.g. ``--key due`` for just the due dates, and no events; it may be given more
than once. The calendar starts with the
current week; ``--all`` shows every week, and ``--from`` and ``--to``
(``YYYY-MM-DD``) set the dates shown. Weeks start on Sunday, unless
``--week-start monday``, and are numbered from the course's
``first_week_start``; the calendar is titled with the course's name and term.
``--html``, ``--pdf`` and ``--ics`` write the calendar to files instead of
printing it (``--ics`` as an iCalendar file, which calendar apps can import or
subscribe to; its events keep their identities when dates change, so that a
subscribed calendar updates them, and use ``--all`` to include past weeks); ``--json`` prints it as JSON, for programs. Dates
before the current time are shown dimmed, and today is highlighted (unless
``--no-highlight-today``). In the HTML, clicking a category in the legend
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

    automata pipeline export-materials [--all] [--to DIR] [--current-time TIME]
                                       [--verbose]

``--all`` includes the artifacts that are not released yet, or not ready (so
their recipes run too). ``--to DIR`` exports to ``DIR`` instead of the build
directory: each artifact goes to ``DIR/<collection>/<publication>/<artifact>``,
with ``DIR/materials.json`` describing them. Together, they export every
material, for instance to preview them::

    automata pipeline export-materials --all --to _materials

``automata pipeline render-website``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Render the website from the materials written by a previous ``automata
pipeline export-materials``. Fails if there are no exported materials (for
example, after ``automata pipeline clean``).

::

    automata pipeline render-website [--current-time TIME]
