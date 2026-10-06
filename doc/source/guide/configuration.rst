Configuration
=============

All configuration lives in ``automata.yaml`` at the project root.


Top-level structure
-------------------

.. code-block:: yaml

    # The course (required)
    course:
      name: "DSC 80"
      title: "The Practice and Application of Data Science"
      term: "Spring 2026"
      first_week_start: 2026-03-30

    # Variables available throughout the project
    vars:
      office_hours: "Wednesdays, 2-4 PM"

    # Extensions to load (optional)
    extensions:
      - my-extension

    # Inline materials definitions (optional)
    materials:
      exams:
        ...

    # Directories not searched for materials (optional)
    ignore:
      - _previous

    # The dates `automata calendar` shows (optional)
    calendar:
      collections:
        ...
      events:
        ...

    # Website generation settings
    website:
      theme: default
      content_directory: content
      build_directory: _build


``course``
----------

The course (required). It is available everywhere ``vars`` is, as ``course``
(e.g. ``${ course.name }``), and automata uses it: the default theme's titles
are the course's name and title (unless set in the theme's config), and weeks
are numbered from ``first_week_start``, in the schedule and in
``automata calendar``.

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Key
     - Default
     - Description
   * - ``name``
     - (required)
     - The course's name, e.g. ``"DSC 80"``.
   * - ``title``
     - (required)
     - The course's title, e.g. ``"The Practice and Application of Data
       Science"``.
   * - ``term``
     - (required)
     - The term, e.g. ``"Spring 2026"``.
   * - ``first_week_start``
     - (required)
     - The first day of the first week, e.g. ``2026-03-30``. Weeks are numbered
       from it.
   * - ``first_week_number``
     - ``1``
     - The first week's number (``0`` for a course with a week 0).
   * - ``instructors``
     - ``[]``
     - The instructors' names.
   * - ``url``
     - ``null``
     - The course's website.


``vars``
--------

A dictionary of variables available for interpolation everywhere: in
``automata.yaml`` itself, in ``collection.yaml`` and ``publication.yaml``
files, and in website pages.

.. code-block:: yaml

    vars:
      office_hours: "Wednesdays, 2-4 PM"
      midterm_date: 2026-04-30

Variables can be nested:

.. code-block:: yaml

    vars:
      gradescope:
        url: https://www.gradescope.com/courses/123456
        code: "ABC123"

Referenced as ``${ vars.gradescope.url }``. (The course's name, title, and
term belong in ``course``.)


``extensions``
--------------

A list of extensions to load, in addition to the theme (which is set with
``website.theme``). Each entry can be:

- **A string** --- an entry point name (no slashes) or a directory path (with
  slashes):

  .. code-block:: yaml

      extensions:
        - my-extension             # entry point
        - ./practice-problems      # local directory

- **A dictionary** with ``use`` and optional ``config``:

  .. code-block:: yaml

      extensions:
        - use: ./practice-problems
          config:
            show_answers: false

Names are looked up in the ``automata.extensions`` entry point group. A
directory extension is named after its directory (``practice-problems``
above). Listing a theme here is an error; use ``website.theme`` instead.

The theme is applied first, then the extensions in order. Later extensions
override earlier ones (and the theme) for templates, static files, and elements
with the same name.

Templates can read an extension's config through ``extensions``, keyed by name
(e.g., ``${ extensions["practice-problems"].config.show_answers }``).


``materials``
-------------

Inline materials definitions. See :doc:`materials` for the full format. This is
optional --- materials can also (or instead) be defined on the filesystem.

Unlike the rest of ``automata.yaml``, ``materials`` isn't resolved when the
file is read. Each publication is resolved when the materials are discovered,
so that it can refer to itself (``this``) and to the publication before it
(``previous``). Materials can refer to ``vars`` and ``course``, but nothing
else in ``automata.yaml`` can refer to the materials: define a value both need
in ``vars``. ``!include`` works in ``materials`` as elsewhere, but its path
must be written out, without ``${ ... }``.


``ignore``
----------

Directories that aren't searched for materials (collections and publications),
for example an archive of a past term's materials whose configuration no
longer resolves. Each is a path relative to the project directory, and may be
a glob; everything inside a matching directory is skipped too. ``automata
serve`` doesn't watch them either. Optional; by default, nothing is ignored.

.. code-block:: yaml

    ignore:
      - _previous          # the directory _previous
      - past-*             # past-2024, past-2025, ...
      - notes/drafts       # only notes/drafts, not drafts elsewhere

Directories whose names start with a dot (such as ``.git``) and the build
directory are always skipped, without being listed.


``website``
-----------

Website generation settings:

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Field
     - Default
     - Description
   * - ``theme``
     - *(required)*
     - Theme to use. A string --- an ``automata.themes`` entry point name
       (e.g., ``"default"``) or a directory path --- or a dict with ``use``
       and ``config`` keys. The theme's config is available in templates as
       ``theme.config``.
   * - ``content_directory``
     - *(required)*
     - Path to the directory containing pages (Markdown, HTML, static files).
   * - ``build_directory``
     - *(required)*
     - Path to the output directory.
   * - ``clean_build_directory``
     - ``true``
     - Empty the build directory before each build, so it holds only what the
       current build produces. Without this, an artifact that is un-released
       (or a page that is deleted) would stay in the build directory and be
       published again. Top-level entries starting with a dot (e.g., ``.git``)
       are kept. As a safeguard, automata refuses to clean a build directory
       that is or contains the project or content directory; lies outside the
       project or inside the content directory; contains an ``automata.yaml``
       file or course materials (a ``collection.yaml`` or
       ``publication.yaml``); or is, contains, or lies inside a directory
       extension. To build outside the project, set this to ``false``.
   * - ``materials_directory_name``
     - ``"materials"``
     - Name of the subdirectory within the build directory where materials are
       placed.
   * - ``no_render_suffix``
     - ``".no_render"``
     - Files ending in this suffix (e.g. ``template.html.no_render``) are
       copied without rendering, with the suffix removed. Set to ``null`` to
       disable.
   * - ``base_path``
     - ``"/"``
     - URL base path for the site. Set to ``"."`` for relative URLs, or
       ``"/course/"`` when deploying to a subdirectory.
   * - ``elements``
     - ``{}``
     - Element configurations, keyed by element name. An element called in a
       page without a configuration (e.g., ``${ elements.schedule() }``) uses
       its entry here. See :ref:`configuring-elements`.


``calendar``
------------

The dates that ``automata calendar`` shows (it is an error to run it without
this section). It has two parts, each optional: ``collections``, whose dates
come from the publications' metadata, and ``events``, dates of their own that
aren't publications (exams without files, holidays, and so on).

Under ``collections``, for each collection, ``dates`` maps metadata keys to
labels: each publication with a date (or date and time) under the key gets an
entry on that day. A label is written with ``!template``, and can use
``publication``, ``vars`` and ``course``; without one, the entry is labeled like
``hw01 due``. ``color`` (optional) is the collection's color; otherwise one is
chosen from a palette:

.. code-block:: yaml

    calendar:
      collections:
        lectures:
          dates:
            date: !template "Lecture ${ publication.metadata.number }: ${ publication.metadata.topic }"
        homeworks:
          dates:
            released: !template "HW ${ publication.metadata.number } released"
            due:

Publications without the key are left out. A key that no publication in the
collection has, or a value that isn't a date, is an error.

Under ``events``, events are in named groups. Each group has a list of
``dates``, each with a ``label`` and a ``date``, and optionally a ``color``. A
date (like ``2026-10-26``, or a phrase like ``first monday after
${ vars.start }``) makes an all-day entry; a date and time (like
``${ vars.final_date } at 08:00:00``) a timed one. An all-day event over
several days gives its last day as ``end``:

.. code-block:: yaml

    calendar:
      events:
        exams:
          color: "#e15759"
          dates:
            - label: "Midterm"
              date: ${ vars.midterm_date }
            - label: "Final"
              date: ${ vars.final_date } at 08:00:00
        holidays:
          dates:
            - label: "Thanksgiving break"
              date: 2026-11-26
              end: 2026-11-27

Event groups are shown, colored and filtered (with ``--collection``) like
collections, so a group can't have the same name as a collection in the
calendar. Labels can be written with ``!template``, and use ``vars`` and
``course``.


Including external files
------------------------

Use ``!include`` to split configuration across files:

.. code-block:: yaml

    website:
      elements:
        schedule: !include "schedule.yaml"

The value is the included file's contents. The path is resolved relative to
the file containing the ``!include``, and included files can include others.

``!include "schedule.yaml"`` is shorthand for a mapping with the single key
``__include__``, which can also be written out:

.. code-block:: yaml

    schedule:
      __include__: "schedule.yaml"
