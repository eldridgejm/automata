Architecture
============

This document describes automata's internal architecture.


Module overview
---------------

.. code-block:: text

    src/automata/
    ├── __init__.py              # Public API: Automata class
    ├── _automata.py             # Automata class implementation
    ├── _extension.py            # Extension, apply_extension, loaders
    ├── config.py                # Config class, read_config, load_extensions
    ├── cli.py                   # CLI entry point (typer)
    ├── constants.py             # File names (collection.yaml, publication.yaml)
    ├── exceptions.py            # Base exception classes
    │
    ├── hooks/
    │   ├── __init__.py          # Exports all hook types
    │   ├── _definitions.py      # Hook point definitions and arg dataclasses
    │   └── _internals.py        # ObserverHook, PipelineHook, HooksBase
    │
    ├── materials/
    │   ├── __init__.py          # Public API for materials
    │   ├── _types.py            # Artifact, Publication, Collection, Universe
    │   ├── _discover.py         # Filesystem discovery
    │   ├── _discover_collection.py  # collection.yaml parsing
    │   ├── _discover_publication.py # publication.yaml parsing
    │   ├── _inline.py           # Inline materials from config
    │   ├── _build.py            # Recipe execution, release-time filtering
    │   ├── _export.py           # Copy artifacts to build directory
    │   ├── _filter.py           # Filter universe by predicate
    │   └── _resolution.py       # resolve_for_each_publication helper
    │
    ├── website/
    │   ├── __init__.py          # Public API for website
    │   ├── _config.py           # WebsiteConfig
    │   ├── _generate.py         # Website generation pipeline
    │   ├── _elements.py         # Element, BasicElement, TemplateElement
    │   ├── _frontmatter.py      # Frontmatter parsing
    │   └── exceptions.py        # WebsiteError, PageError
    │
    ├── builtin/
    │   ├── elements/            # Listing and Schedule elements
    │   └── themes/default/      # Default theme
    │
    └── util/
        ├── markdown.py          # Markdown rendering
        ├── resolution.py        # smartconfig resolution helpers
        ├── weeks.py             # Week calculation utilities
        └── yaml.py              # YAML parsing


Key abstractions
----------------

Extension system
^^^^^^^^^^^^^^^^

An ``Extension`` is a dataclass with a ``name`` and a ``hooks`` dictionary.
Each hook maps a hook point name to a callable. When ``apply_extension`` is
called, each callable is registered on the corresponding hook point.

Extensions can declare ``dependencies`` --- other extensions applied first,
deduplicated by name.

The ``extension_from_directory`` and ``extension_from_entry_point`` functions
handle loading extensions from the filesystem or installed packages. Entry
points live in two groups, ``automata.themes`` (for ``website.theme``) and
``automata.extensions`` (for ``extensions``); an entry point module exports
either a ``make_extension(config)`` factory or an ``extension`` object.

``load_extensions`` in ``config.py`` returns ``(theme, extensions)``. It checks
that the theme provides ``page.html`` and that no two different extensions
share a name. ``Automata`` keeps these as ``.theme`` and ``.extensions``,
registers them with ``apply_extensions``, and passes them to ``generate`` so
that templates can read them as ``theme`` and ``extensions``.

Hooks system
^^^^^^^^^^^^

The hooks system (``hooks/``) provides two hook types:

- ``ObserverHook[T]``: Fire-and-forget. All registered callables are invoked
  with the args. Used for logging/monitoring events.
- ``PipelineHook[T]``: Transforming. Each registered callable receives the
  output of the previous one. The final value is returned.

``HooksBase`` is a metaclass-like base that auto-creates fresh hook instances
per ``__init__`` call, preventing shared state between instances.

Hook groups inherit from ``HooksBase``: ``DiscoverHooks``, ``BuildHooks``,
``ExportHooks``, ``FilterHooks``, ``GenerateHooks``. The ``Hooks`` class
inherits from all of them.

Materials pipeline
^^^^^^^^^^^^^^^^^^

Materials flow through four phases:

1. **Discover** (``_discover.py``): Walks the filesystem for ``collection.yaml``
   / ``publication.yaml`` files. Produces ``Universe[UnbuiltArtifact]``.
2. **Build** (``_build.py``): Runs recipes, filters by release time and ready
   flag. Produces ``Universe[BuiltArtifact]``.
3. **Export** (``_export.py``): Copies artifact files to the build directory.
   Produces ``Universe[ExportedArtifact]``.
4. **Serialize** (``_types.py``): Converts to/from JSON for ``materials.json``.

Each phase produces a new ``Universe`` parameterized by a different artifact
type. This enforces that you can't skip a step.

Website generation
^^^^^^^^^^^^^^^^^^

``website/_generate.py`` orchestrates:

1. Fire ``on_website_collect`` to gather templates, static files, elements from
   extensions.
2. Fire ``on_generate_pre`` for pre-processing.
3. Create a Jinja2 environment from collected templates.
4. Load materials from ``materials.json``.
5. Process the content directory (render Markdown/HTML, copy static files).
6. Process extra content from extensions and hooks.
7. Copy static files from extensions.
8. Copy materials to the build directory.
9. Fire ``on_generate_post`` for post-processing.


Data flow
---------

.. code-block:: text

    automata.yaml
        │
        ├─── Config ──── load_extensions() ──── Extensions ──── Hooks
        │
        ├─── discover() ──── Universe[UnbuiltArtifact]
        │        │
        │        ├── filesystem (collection.yaml / publication.yaml)
        │        └── inline (automata.yaml materials section)
        │
        ├─── build_materials() ──── Universe[BuiltArtifact]
        │        │
        │        ├── run recipes
        │        └── filter by release_time / ready
        │
        ├─── export() ──── Universe[ExportedArtifact]
        │        │
        │        ├── copy artifacts to _build/materials/
        │        └── write materials.json
        │
        └─── generate_website(materials)
                 │
                 ├── on_website_collect (gather templates, elements, etc.)
                 ├── render content directory
                 ├── copy static files
                 └── on_generate_post (e.g., rebuild Tailwind CSS)


Configuration resolution
------------------------

automata uses `smartconfig <https://github.com/eldridgejm/smartconfig>`_ for
configuration resolution. smartconfig provides:

- Variable interpolation (``${ vars.x }``)
- Schema validation and type coercion (string to date, datetime, etc.)
- Default values
- Functions (``__include__``, ``__datetime.offset__``, ``__datetime.parse__``,
  ``__datetime.at__``, etc.)

The ``util/resolution.py`` module wraps smartconfig's ``resolve()`` with
automata-specific defaults (the ``__include__`` function for file inclusion).
