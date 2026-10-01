Core Concepts
=============

The materials hierarchy
-----------------------

automata organizes course materials into a three-level hierarchy:

.. code-block:: text

    Universe
    ├── Collection: "homeworks"
    │   ├── Publication: "hw01"
    │   │   ├── Artifact: homework.pdf
    │   │   └── Artifact: solution.pdf
    │   └── Publication: "hw02"
    │       ├── Artifact: homework.pdf
    │       └── Artifact: solution.pdf
    ├── Collection: "lectures"
    │   └── ...
    └── Collection: "exams"
        └── ...

**Artifacts** are individual files distributed to students: a homework PDF, a
solution, a starter code ZIP, lecture slides.

**Publications** are coherent groupings of artifacts with metadata. For
example, "Homework 1" is a publication containing a homework PDF and a solution
PDF, with metadata like the due date and the topic.

**Collections** are groups of related publications. "Homeworks," "Lectures," and
"Exams" are collections.

The **Universe** is the top-level container holding all collections.


The build pipeline
------------------

When you run ``automata generate``, four things happen in sequence:

1. **Discover.** automata finds all materials --- both from the filesystem
   (``collection.yaml`` / ``publication.yaml`` files) and from inline
   definitions in ``automata.yaml``.

2. **Build.** For filesystem materials with recipes, automata runs the shell
   commands to produce artifact files. Artifacts with future release times or
   ``ready: false`` are filtered out.

3. **Export.** Built artifacts are copied to the build directory and a
   ``materials.json`` manifest is written.

4. **Generate website.** The website is rendered using the content directory,
   the exported materials, the theme templates, and any extensions.

You can run each step individually via the CLI or the Python API::

    # CLI
    automata discover
    automata build-materials
    automata export
    automata generate        # runs all four

    # Python
    project = Automata()
    project.clean_build_directory()
    materials = project.discover()
    materials = project.build_materials(materials)
    materials = project.export(materials)
    project.generate_website(materials)


Extensions
----------

An **extension** is a collection of hooks that customize automata's behavior.
The most common extension is a *theme*, which provides HTML templates, CSS,
JavaScript, and custom elements for the website.

The theme is set with ``website.theme``, and any other extensions are listed
under ``extensions`` in ``automata.yaml``:

.. code-block:: yaml

    extensions:
      - ./my-custom-extension    # a local directory

    website:
      theme: default             # the built-in theme

The ``default`` theme provides a responsive sidebar
layout with Tailwind CSS, dark mode, and built-in elements like
``schedule``, ``listing``, ``people``, ``date_pill``, and ``button``.

Extensions can depend on other extensions. For example, the default theme
depends on the ``builtin-listing`` and ``builtin-schedule`` extensions, which
provide the ``listing`` and ``schedule`` elements.

See :doc:`/extensions/index` for how to create your own.


Variable interpolation
----------------------

automata uses a Jinja2-based interpolation system. Variables defined in the
``vars`` section of ``automata.yaml`` are available everywhere:

- In ``automata.yaml`` itself (including materials definitions)
- In ``collection.yaml`` and ``publication.yaml`` files
- In website pages (Markdown and HTML)

The template syntax uses ``${ ... }`` for variable substitution and
``{% ... %}`` for control flow:

.. code-block:: markdown

    # ${ vars.course_name }

    {% if vars.term == "Spring 2026" %}
    Office hours are on Tuesdays.
    {% endif %}


Release times
-------------

Artifacts can have a ``release_time`` that controls when they become visible.
Before the release time, the artifact is excluded from the built materials.
This lets you schedule releases ahead of time.

.. code-block:: yaml

    artifacts:
      solution.pdf:
        path: homeworks/hw01/solution.pdf
        release_time: 2026-01-22 12:00:00

Release times can be computed relative to other dates using smartconfig
functions:

.. code-block:: yaml

    artifacts:
      solution.pdf:
        path: homeworks/hw01/solution.pdf
        release_time:
          __datetime.offset__:
            after: ${ vars.hw01_due_date }
            by: "3 days"

Available datetime functions:

- ``__datetime.offset__``: Offset a date by a duration. Takes ``after`` (or
  ``before``) and ``by`` (e.g., ``"7 days"``, ``"2 weeks"``).
- ``__datetime.at__``: Combine a date and a time into a datetime. Takes
  ``date`` and ``time``.
- ``__datetime.parse__``: Parse a natural-language date expression, such as
  ``"first tuesday, thursday after 2026-01-15"``.
