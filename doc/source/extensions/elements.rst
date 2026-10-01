Creating Custom Elements
========================

Elements are callable Python classes that generate HTML. They are registered via
the ``on_render_collect`` hook and become available in pages as
``${ elements.my_element(config) }``.


Basic element
-------------

The simplest element is a class that inherits from ``Element``:

.. code-block:: python

    from automata.website import Element

    class Greeting(Element):
        def __call__(self, config):
            name = config.get("name", "World")
            return f'<p class="greeting">Hello, {name}!</p>'

Usage in a page:

.. code-block:: markdown

    ${ elements.greeting({"name": "Students"}) }


Template element
----------------

For elements that render Jinja2 templates, use ``TemplateElement``:

.. code-block:: python

    import smartconfig
    from automata.website import TemplateElement

    class BadgeConfig(smartconfig.Prototype):
        label: str
        tone: str = "info"

    class Badge(TemplateElement):
        schema = BadgeConfig._schema()
        template = "elements/badge.html"

        def template_vars(self, config):
            return {}

The template (provided by the theme or extension):

.. code-block:: html

    <span class="badge badge-${ element_config.tone }">
        ${ element_config.label }
    </span>

``TemplateElement`` handles schema validation and default application
automatically. The resolved config is available in the template as
``element_config``.


Registering elements as an extension
-------------------------------------

Elements are contributed via the ``on_render_collect`` hook:

.. code-block:: python

    from automata._extension import Extension
    from automata.hooks import WebsiteInputs

    def _collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.elements["greeting"] = Greeting
        inputs.elements["badge"] = Badge
        return inputs

    my_elements = Extension(
        name="my-elements",
        hooks={"on_render_collect": _collect},
    )

If the module exports it as ``extension`` and registers it in the
``automata.extensions`` entry point group, users can list it under
``extensions`` in ``automata.yaml``. Alternatively, a theme can depend on it:

.. code-block:: python

    # my_theme/__init__.py
    from importlib.resources import files
    from automata._extension import extension_from_directory
    from my_elements import my_elements

    def make_extension(config):
        return extension_from_directory(
            "my-theme", files(__name__), config=config, dependencies=[my_elements]
        )


Registering elements from a theme
---------------------------------

A theme built with ``make_extension`` can also contribute elements from its own
``on_render_collect`` hook. To combine this with the directory layout, wrap the
hook of the extension built by ``extension_from_directory``:

.. code-block:: python

    # my_theme/__init__.py
    from importlib.resources import files
    from automata._extension import extension_from_directory

    from ._greeting import Greeting

    def make_extension(config):
        ext = extension_from_directory("my-theme", files(__name__), config=config)
        collect_files = ext.hooks["on_render_collect"]

        def collect(inputs):
            inputs = collect_files(inputs)
            inputs.elements["greeting"] = Greeting
            return inputs

        ext.hooks["on_render_collect"] = collect
        return ext

Directory extensions loaded by path (e.g., ``./my-theme``) cannot provide
elements; an ``elements/`` subdirectory is not loaded.


Element context
---------------

All elements receive a Jinja2 environment and a ``RenderContext`` on
construction. This gives access to:

- ``self.context.materials`` --- the materials universe
- ``self.context.vars`` --- the ``vars`` section of ``automata.yaml``
- ``self.context.url_for`` --- URL generation
- ``self.context.current_time`` --- the current datetime
- ``self.context.base_path`` --- the site's base URL path
- ``self.context.theme`` --- the theme ``Extension`` (e.g.,
  ``self.context.theme.config``)
- ``self.context.extensions`` --- all loaded extensions, keyed by name
- ``self.jinja_env`` --- the Jinja2 environment (for rendering templates)


Builtin elements
----------------

automata ships with two reusable elements as standalone extensions:

- ``automata.builtin.elements.listing_extension`` --- the ``listing`` element,
  which renders a table of publications from a collection.
- ``automata.builtin.elements.schedule_extension`` --- the ``schedule`` element,
  which renders a week-by-week course schedule.

The default theme depends on both and also provides ``button``, ``date_pill``,
and ``people`` elements.
