Extension Overview
==================

What is an extension?
---------------------

An extension is a Python object with a ``name``, a ``hooks`` dictionary, and
optional ``config``, ``schema``, and ``dependencies``:

.. code-block:: python

    from automata.extensions import Extension
    from automata.hooks import WebsiteInputs

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates["page.html"] = "<html>${ content }</html>"
        return inputs

    my_extension = Extension(
        name="my-extension",
        hooks={"on_render_collect": collect},
    )

The ``hooks`` dictionary maps hook point names to callables. When the extension
is applied, each callable is registered on the corresponding hook point.


Loading extensions
------------------

A site has exactly one theme, set with ``website.theme``, and any number of
other extensions, listed under ``extensions``:

.. code-block:: yaml

    extensions:
      - my-extension              # entry point name
      - ./practice-problems       # local directory
      - use: my-package           # entry point with config
        config:
          key: value

    website:
      theme:
        use: default              # entry point name (or a path)
        config:
          short_title: "DSC 80"
          long_title: "The Practice and Application of Data Science"

The theme is applied first, then the extensions in the order they are listed.

**Entry point names** (no slashes) are looked up in one of two entry point
groups: ``website.theme`` names in ``automata.themes``, and names under
``extensions`` in ``automata.extensions``. Register yours in
``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."automata.extensions"]
    my-extension = "my_package.extension"

    [project.entry-points."automata.themes"]
    my-theme = "my_package.theme"

Listing a theme under ``extensions`` is an error that tells you to use
``website.theme`` instead, and vice versa.

The referenced module must export one of:

1. ``make_extension(config)`` --- a factory that returns an ``Extension``. It
   is called with the extension's validated configuration (see below), and
   each call builds a fresh ``Extension``, so its hooks can safely close over
   ``config``.
2. ``extension`` --- an ``Extension`` object that takes no configuration.
   Passing ``config`` to it is an error.

**Directory paths** (contain slashes) are loaded from the filesystem using the
directory layout described in :doc:`themes`. A directory extension is named
after the directory's last path component, so ``./extensions/practice-problems``
is named ``practice-problems``. See `Directory extensions with Python`_ below
for directories that include code.

Every loaded extension, including the theme and its dependencies, must have a
unique name; loading two different extensions with the same name is an
error.


Extension with config and schema
--------------------------------

Extensions can accept configuration, validated against a schema. An entry
point module that exports ``make_extension`` may also export ``schema``; the
user's config is validated against it, and defaults are applied, before
``make_extension`` is called:

.. code-block:: python

    # my_package/extension.py
    from automata.extensions import Extension
    from automata.hooks import WebsiteInputs

    schema = {
        "type": "dict",
        "required_keys": {
            "title": {"type": "string"}
        },
    }

    def make_extension(config):
        def collect(inputs: WebsiteInputs) -> WebsiteInputs:
            inputs.pages["about.html"] = f"# About {config['title']}"
            return inputs

        return Extension(
            name="my-extension",
            hooks={"on_render_collect": collect},
            config=config,
            schema=schema,
        )

When loaded from a directory, the schema is read from ``schema.json``.

If an extension has a schema, its config is always validated, even when none is
given (it is treated as empty). Defaults are applied, and missing required keys
are reported as errors.

In ``automata.yaml``, config is passed via the ``config`` key:

.. code-block:: yaml

    extensions:
      - use: my-extension
        config:
          title: "My Site"

An extension's resolved config is available in templates through
``extensions``, keyed by name (e.g., ``extensions["my-extension"].config.title``),
and the theme's as ``theme.config``. See :doc:`themes`.


Dependencies
------------

An extension can declare dependencies --- other extensions that are
automatically applied before it:

.. code-block:: python

    from automata.builtin.elements import schedule_extension

    my_theme = Extension(
        name="my-theme",
        hooks={"on_render_collect": collect},
        dependencies=[schedule_extension],
    )

Dependencies are deduplicated by name: if two extensions depend on the same
extension, it is applied only once.

Dependencies are declared in Python, on the ``Extension`` returned by
``make_extension`` (or exported as ``extension``). A directory extension can
declare them only from an ``extension.py`` file (see below).


.. _extensions-with-python:

Directory extensions with Python
--------------------------------

A directory extension is just files --- ``templates/``, ``static/``,
``schema.json``, and shell commands in ``hooks/`` --- **unless** it contains an
``extension.py`` file. That one file is the marker for code: if it is absent,
nothing in the directory is imported, so you can tell at a glance what a
directory extension can do.

``extension.py`` exports ``make_extension(config)`` (or a config-less
``extension``), exactly like a package extension:

.. code-block:: text

    extensions/greeter/
        extension.py      # makes this directory extension dynamic
        elements.py       # sibling module, imported relatively
        templates/
            greeting.html

.. code-block:: python

    # extensions/greeter/extension.py
    from automata.extensions import Extension

    from .elements import Greeting   # sibling imports must be relative

    def make_extension(config):
        def collect(inputs):
            inputs.elements["greeting"] = Greeting
            return inputs

        return Extension(name="greeter", hooks={"on_render_collect": collect})

How the files and the code combine:

- The files are still collected automatically. For each hook point, the files'
  hook (collecting ``templates/`` and ``static/``, or a ``hooks/`` script) runs
  first, then the Python hook. So Python can see and change what was
  collected.
- The config schema comes from a module-level ``schema`` in ``extension.py`` or
  from ``schema.json``, not both. The validated config is passed to
  ``make_extension``.
- The extension is named after its directory. Its config and dependencies are
  those of the ``Extension`` that ``extension.py`` provides.
- Each load imports ``extension.py`` into a new, uniquely named package, so
  two extensions' modules never collide and edits are picked up when the
  project is loaded again.

**When to use which.** A directory extension with Python suits course-specific
code with no third-party dependencies: it lives in the course repository and
needs no installation. Anything reusable across courses, or anything that
imports third-party libraries, should be a package extension, so that its
dependencies are declared in ``pyproject.toml``.
