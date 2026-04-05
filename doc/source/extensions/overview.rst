Extension Overview
==================

What is an extension?
---------------------

An extension is a Python object with a ``name``, a ``hooks`` dictionary, and
optional ``config``, ``schema``, and ``dependencies``:

.. code-block:: python

    from automata._extension import Extension
    from automata.hooks import WebsiteInputs

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates["page.html"] = "<html>${ content }</html>"
        return inputs

    my_extension = Extension(
        name="my-extension",
        hooks={"on_website_collect": collect},
    )

The ``hooks`` dictionary maps hook point names to callables. When the extension
is applied, each callable is registered on the corresponding hook point.


Loading extensions
------------------

Extensions are specified in ``automata.yaml``:

.. code-block:: yaml

    extensions:
      - default                   # entry point name
      - ./my-theme                # local directory
      - use: my-package           # entry point with config
        config:
          key: value

**Entry point names** (no slashes) are looked up in the ``automata.themes``
entry point group. Register yours in ``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."automata.themes"]
    my-theme = "my_package.themes.custom"

The referenced module can export:

1. An ``extension`` attribute (an ``Extension`` object) --- used directly.
2. A standard theme directory layout (``templates/``, ``static/``, etc.) ---
   converted to an Extension automatically.

**Directory paths** (contain slashes) are loaded from the filesystem using the
theme directory layout.


Extension with config and schema
--------------------------------

Extensions can accept configuration, validated against a JSON schema:

.. code-block:: python

    my_extension = Extension(
        name="my-extension",
        hooks={"on_website_collect": collect},
        config={"title": "My Site"},
        schema={
            "type": "dict",
            "required_keys": {
                "title": {"type": "string"}
            }
        },
    )

When loaded from a directory, the schema is read from ``schema.json``.

In ``automata.yaml``, config is passed via the ``config`` key:

.. code-block:: yaml

    extensions:
      - use: my-extension
        config:
          title: "My Site"


Dependencies
------------

An extension can declare dependencies --- other extensions that are
automatically applied before it:

.. code-block:: python

    from automata.builtin.elements import schedule_extension

    my_theme = Extension(
        name="my-theme",
        hooks={"on_website_collect": collect},
        dependencies=[schedule_extension],
    )

Dependencies are deduplicated by name: if two extensions depend on the same
extension, it is applied only once.

When loading from a directory or entry point, dependencies can be declared in
the module's ``__init__.py``:

.. code-block:: python

    # my_theme/__init__.py
    from automata.builtin.elements import listing_extension, schedule_extension

    dependencies = [listing_extension, schedule_extension]
