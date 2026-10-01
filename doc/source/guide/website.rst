Creating Website Pages
======================

The website is generated from files in the content directory. automata processes
three types of files:

- **Markdown** (``.md``) --- converted to HTML, wrapped in a template.
- **HTML** (``.html``) --- variable-interpolated, wrapped in a template.
- **Other files** --- copied as-is to the build directory.


Content directory structure
---------------------------

.. code-block:: text

    content/
        index.md
        syllabus.md
        staff.html
        images/
            logo.png
        data/
            grades.csv

The directory structure is preserved in the output. ``content/index.md``
becomes ``_build/index.html``, ``content/syllabus.md`` becomes
``_build/syllabus.html``, and ``content/images/logo.png`` is copied to
``_build/images/logo.png``.


Template syntax
---------------

Pages use Jinja2 syntax with custom delimiters:

- ``${ expression }`` for variable interpolation
- ``{% ... %}`` for control flow (if, for, etc.)

Available variables in pages:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Variable
     - Description
   * - ``vars``
     - The ``vars`` dictionary from ``automata.yaml``.
   * - ``materials``
     - The materials universe (collections, publications, artifacts).
   * - ``elements``
     - Theme-provided callable elements (e.g., ``elements.schedule(...)``).
   * - ``url_for(path)``
     - Generates a URL respecting the site's ``base_path``.
   * - ``current_time``
     - The current datetime (or the overridden time).
   * - ``website_config``
     - The website configuration object.
   * - ``frontmatter``
     - The current page's frontmatter (see below).

Example page:

.. code-block:: markdown

    # ${ vars.course_name }

    Welcome to the course website.

    ## Materials

    {% for name, collection in materials.collections.items() %}
    - **${ name }**: ${ collection.publications | length } publications
    {% endfor %}


Frontmatter
-----------

Pages can include YAML frontmatter between ``---`` delimiters:

.. code-block:: markdown

    ---
    vars:
      title: "Syllabus"
      author: "Jane Doe"
    template: page.html
    ---

    # ${ frontmatter.vars.title }

    By ${ frontmatter.vars.author }

Frontmatter fields:

- ``vars``: Page-specific variables, accessible via ``frontmatter.vars``.
- ``template``: Which theme template to use. Defaults to ``page.html``.


Using elements
--------------

Extensions provide callable **elements** that generate HTML. The default theme
includes:

- ``elements.schedule(config)`` --- renders a weekly course schedule.
- ``elements.listing(config)`` --- renders a table of publications.
- ``elements.people(config)`` --- renders a staff directory.
- ``elements.date_pill(config)`` --- renders a date-sensitive label.
- ``elements.button(config)`` --- renders a styled button.

Example:

.. code-block:: markdown

    ---
    template: page.html
    ---

    ${ elements.schedule() }


.. _configuring-elements:

Configuring elements
^^^^^^^^^^^^^^^^^^^^

An element's configuration comes from one of two places:

- **The call.** ``${ elements.button({"label": "Zoom", "url": "..."}) }`` uses
  exactly the configuration passed. Anything set for the element in
  ``automata.yaml`` is ignored; the two are not merged.
- **automata.yaml.** ``${ elements.schedule() }``, called without a
  configuration, uses ``website.elements.schedule``:

  .. code-block:: yaml

      website:
        elements:
          schedule:
            __include__: "schedule.yaml"

  If the element has no entry there, it receives an empty configuration, so
  it renders with its defaults or raises an error naming its missing required
  keys.

Configuring an element that no extension provides (for example, a misspelled
name) is an error.


The ``url_for`` function
------------------------

Use ``url_for`` to generate URLs that respect the site's ``base_path``:

.. code-block:: html

    <a href="${ url_for('syllabus.html') }">Syllabus</a>
    <img src="${ url_for('images/logo.png') }">

With the default ``base_path`` of ``"/"``, ``url_for('about.html')`` produces
``/about.html``. With ``base_path: "/course/"``, it produces
``/course/about.html``.


Raw files (no rendering)
------------------------

Files with the ``no_render_suffix`` (default: ``.no_render``) are copied
without rendering, with the suffix stripped. This is useful for including files
that contain template syntax that should not be interpreted:

.. code-block:: text

    content/
        data.csv.no_render    -->    _build/data.csv
        template.html.no_render    -->    _build/template.html
