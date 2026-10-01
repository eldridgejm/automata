Configuration
=============

All configuration lives in ``automata.yaml`` at the project root.


Top-level structure
-------------------

.. code-block:: yaml

    # Variables available throughout the project
    vars:
      course_name: "DSC 80"
      term: "Spring 2026"

    # Extensions to load (optional)
    extensions:
      - my-extension

    # Inline materials definitions (optional)
    materials:
      exams:
        ...

    # Website generation settings
    website:
      theme: default
      content_directory: content
      build_directory: _build


``vars``
--------

A dictionary of variables available for interpolation everywhere: in
``automata.yaml`` itself, in ``collection.yaml`` and ``publication.yaml``
files, and in website pages.

.. code-block:: yaml

    vars:
      course_name: "DSC 80"
      term: "Spring 2026"
      start_date: "2026-03-30"
      instructor: "Jane Doe"

Variables can be nested:

.. code-block:: yaml

    vars:
      course:
        name: "DSC 80"
        title: "The Practice and Application of Data Science"

Referenced as ``${ vars.course.name }``.


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
       that is or contains the project or content directory, lies inside the
       content directory, or contains an ``automata.yaml`` file.
   * - ``materials_directory_name``
     - ``"materials"``
     - Name of the subdirectory within the build directory where materials are
       placed.
   * - ``no_render_suffix``
     - ``".no_render"``
     - Files with this suffix are copied without rendering (suffix removed).
       Set to ``null`` to disable.
   * - ``base_path``
     - ``"/"``
     - URL base path for the site. Set to ``"."`` for relative URLs, or
       ``"/course/"`` when deploying to a subdirectory.
   * - ``elements``
     - ``{}``
     - Element configurations, keyed by element name. An element called in a
       page without a configuration (e.g., ``${ elements.schedule() }``) uses
       its entry here. See :ref:`configuring-elements`.


Including external files
------------------------

Use ``__include__`` to split configuration across files:

.. code-block:: yaml

    website:
      elements:
        schedule:
          __include__: "schedule.yaml"

The path is resolved relative to the file containing the ``__include__``.
