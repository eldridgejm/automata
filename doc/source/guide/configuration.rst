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

    # Extensions to load (themes, plugins)
    extensions:
      - default

    # Inline materials definitions (optional)
    materials:
      exams:
        ...

    # Website generation settings
    website:
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

A list of extensions to load. Each entry can be:

- **A string** --- an entry point name (no slashes) or a directory path (with
  slashes):

  .. code-block:: yaml

      extensions:
        - default              # entry point
        - ./my-theme           # local directory

- **A dictionary** with ``use`` and optional ``config``:

  .. code-block:: yaml

      extensions:
        - use: default
          config:
            short_title: ${ vars.course_name }
            long_title: ${ vars.course_title }
            navigation:
              - text: Home
                url: index.html
              - text: Syllabus
                url: syllabus.html

Extensions are applied in order. Later extensions override earlier ones for
templates, static files, and elements with the same name.


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
   * - ``content_directory``
     - *(required)*
     - Path to the directory containing pages (Markdown, HTML, static files).
   * - ``build_directory``
     - *(required)*
     - Path to the output directory.
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


Including external files
------------------------

Use ``__include__`` to split configuration across files:

.. code-block:: yaml

    vars:
      schedule_config:
        __include__: "schedule.yaml"

The path is resolved relative to the file containing the ``__include__``.
