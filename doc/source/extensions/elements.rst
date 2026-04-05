Creating Custom Elements
=======================

Elements are callable Python classes that generate HTML. They are registered via
the ``on_website_collect`` hook and become available in pages as
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

Elements are contributed via the ``on_website_collect`` hook:

.. code-block:: python

    from automata._extension import Extension
    from automata.hooks import WebsiteInputs

    def _collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.elements["greeting"] = Greeting
        inputs.elements["badge"] = Badge
        return inputs

    my_elements = Extension(
        name="my-elements",
        hooks={"on_website_collect": _collect},
    )

A theme can depend on this extension:

.. code-block:: python

    # my_theme/__init__.py
    from my_elements import my_elements

    dependencies = [my_elements]


Registering elements from a theme directory
-------------------------------------------

If using the theme directory layout, create an ``elements/`` package:

.. code-block:: text

    my-theme/
        elements/
            __init__.py
            _greeting.py

``elements/__init__.py`` must export an ``elements`` dictionary:

.. code-block:: python

    from ._greeting import Greeting

    elements = {
        "greeting": Greeting,
    }

These elements are automatically included when the theme is loaded.


Element context
---------------

All elements receive a Jinja2 environment and a ``RenderContext`` on
construction. This gives access to:

- ``self.context.materials`` --- the materials universe
- ``self.context.vars`` --- template variables
- ``self.context.url_for`` --- URL generation
- ``self.context.current_time`` --- the current datetime
- ``self.context.website_config`` --- the website config
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
