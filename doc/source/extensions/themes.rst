Creating a Theme
================

A theme is an extension that provides HTML templates, static files (CSS, JS),
and optionally custom elements. It hooks into ``on_website_collect`` to
contribute these resources to the website generation pipeline.


Theme directory layout
----------------------

The simplest way to create a theme is as a directory:

.. code-block:: text

    my-theme/
        __init__.py          # optional: dependencies, or export an Extension
        templates/
            page.html        # required: the default page template
            base.html        # optional: base template for inheritance
        static/
            style.css        # optional: static files copied to output
        elements/
            __init__.py      # optional: custom elements
        hooks.py             # optional: post-generation hooks
        schema.json          # optional: config validation schema

When loaded (via entry point or path), this directory is converted into an
``Extension`` whose ``on_website_collect`` hook provides the templates, static
files, and elements.


Templates
---------

Templates use Jinja2 with custom delimiters:

- ``${ expression }`` for output
- ``{% ... %}`` for control flow

The ``page.html`` template is required. It receives:

- ``content`` --- the rendered page content (HTML)
- ``base_url_path`` --- the site's base URL path
- All fields from the render context (``vars``, ``materials``, ``elements``,
  ``url_for``, ``current_time``, ``website_config``, ``frontmatter``)

Minimal ``page.html``:

.. code-block:: html

    <!DOCTYPE html>
    <html>
    <head>
        <title>${ vars.theme_config.short_title }</title>
        <link href="${ url_for('static/style.css') }" rel="stylesheet">
    </head>
    <body>
        ${ content }
    </body>
    </html>

Templates can use inheritance:

.. code-block:: html

    {# base.html #}
    <!DOCTYPE html>
    <html>
    <body>
        <header>{% block header %}{% endblock %}</header>
        <main>{% block main %}${ content }{% endblock %}</main>
    </body>
    </html>

    {# page.html #}
    {% extends "base.html" %}
    {% block header %}<h1>${ vars.theme_config.short_title }</h1>{% endblock %}


Theme configuration
-------------------

Themes can define a ``schema.json`` to validate configuration passed by users:

.. code-block:: json

    {
        "type": "dict",
        "required_keys": {
            "short_title": {"type": "string"},
            "long_title": {"type": "string"}
        },
        "optional_keys": {
            "navigation": {
                "type": "list",
                "element_schema": {
                    "type": "dict",
                    "required_keys": {
                        "text": {"type": "string"},
                        "url": {"type": "string"}
                    }
                },
                "default": []
            }
        }
    }

The resolved config is available in templates as ``vars.theme_config``.


Post-generation hooks
---------------------

A ``hooks.py`` file can define a ``post_generate`` function that runs after the
website is generated. It receives the website config and the extension's
resolved config:

.. code-block:: python

    def post_generate(config, extension_config):
        """Run after website generation."""
        if extension_config.get("rebuild_css", True):
            # rebuild CSS, optimize images, etc.
            ...

The default theme uses this to rebuild Tailwind CSS.


Distributing a theme as a package
----------------------------------

1. Create a Python package with the theme directory layout.

2. Register the entry point in ``pyproject.toml``:

   .. code-block:: toml

       [project.entry-points."automata.themes"]
       my-theme = "my_package.themes.custom"

3. The module can either:

   - Export a theme directory (templates/, static/, etc.) as package resources.
   - Export an ``extension`` variable directly for full control.

4. Declare dependencies in ``__init__.py``:

   .. code-block:: python

       from automata.builtin.elements import listing_extension, schedule_extension

       dependencies = [listing_extension, schedule_extension]

5. Users install your package and reference the theme by name:

   .. code-block:: yaml

       extensions:
         - use: my-theme
           config:
             short_title: "My Course"


The default theme
-----------------

The built-in ``default`` theme provides:

- A responsive sidebar layout with Tailwind CSS
- Dark mode toggle
- Mobile-friendly navigation
- Built-in elements: ``schedule``, ``listing``, ``people``, ``date_pill``,
  ``button``
- Automatic Tailwind CSS rebuild (requires Node.js)

Configuration:

.. code-block:: yaml

    extensions:
      - use: default
        config:
          short_title: "DSC 80"
          long_title: "The Practice and Application of Data Science"
          navigation:
            - text: Home
              url: index.html
            - text: Syllabus
              url: syllabus.html
          rebuild_tailwind: true  # default; set false to skip
