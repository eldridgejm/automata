Python API Reference
====================

The primary interface is the ``Automata`` class.


``Automata``
------------

.. code-block:: python

    from automata import Automata

.. class:: Automata(path=None)

    A handle to an automata project.

    :param path: Path to the project directory (must contain ``automata.yaml``).
        If ``None``, uses the current working directory. Unlike the CLI, this
        does not search parent directories.
    :type path: Path or None
    :raises automata.exceptions.Error: If the directory does not contain
        ``automata.yaml``.

    .. attribute:: path

        The project directory path.

    .. attribute:: config

        The parsed :class:`Config` object.

    .. attribute:: theme

        The theme :class:`Extension`, loaded from ``website.theme``.

    .. attribute:: extensions

        The other extensions, loaded from ``extensions`` in the order listed.

    .. attribute:: hooks

        The :class:`Hooks` instance with the theme and all extensions
        registered.

    .. method:: build(current_time=None)

        Run the full pipeline: clean the build directory (if
        ``website.clean_build_directory`` is true), discover, build materials,
        export, and render the website.

        :param current_time: Override the current time. If ``None``, uses
            ``datetime.now()``.
        :type current_time: datetime or None

    .. method:: clean_build_directory()

        Empty the build directory, keeping top-level entries whose names start
        with a dot. Does nothing if the build directory does not exist.

        :raises automata.exceptions.Error: If the build directory is or
            contains the project or content directory, lies inside the content
            directory, or contains an ``automata.yaml`` file.

    .. method:: publish(target=None, current_time=None)

        Check the target and strategy names, run :meth:`build`, then deploy to
        the configured targets (all of them, in order, if *target* is
        ``None``). See :doc:`/guide/deployment`.

        :returns: The names of the targets published to.
        :rtype: list[str]
        :raises automata.exceptions.Error: If there are no publish targets,
            or the target or a strategy is unknown.

    .. method:: discover()

        Discover materials from the filesystem and from inline definitions
        in ``automata.yaml``.

        :returns: The discovered materials universe.
        :rtype: Universe[UnbuiltArtifact]

    .. method:: build_materials(universe, current_time=None, **kwargs)

        Build materials by running recipes and checking release times.

        :param universe: The discovered materials to build.
        :type universe: Universe[UnbuiltArtifact]
        :param current_time: Override the current time. If ``None``, uses
            ``datetime.now()``.
        :type current_time: datetime or None
        :param kwargs: Additional arguments passed to ``materials.build()``
            (e.g., ``ignore_release_time=True``, ``ignore_ready=True``).
        :returns: The built materials universe.
        :rtype: Universe[BuiltArtifact]

    .. method:: filter(universe, predicate, remove_empty_nodes=False)

        Select materials according to a predicate, firing this project's
        ``on_filter_hit`` and ``on_filter_miss`` hooks. A wrapper around
        :func:`automata.materials.filter`; it can be applied to discovered,
        built, or exported materials.

        :param universe: The materials to filter.
        :param predicate: Called with each node's key and the node; returns
            ``True`` to keep it.
        :param remove_empty_nodes: Whether to remove nodes left with no
            children.
        :returns: A new universe with the rejected nodes removed.

    .. method:: export(universe)

        Export built materials to the build directory and write
        ``materials.json``, which is published with the site. (The library
        function :func:`automata.materials.export` only copies files; it does
        not write ``materials.json``.)

        :param universe: The built materials to export.
        :type universe: Universe[BuiltArtifact]
        :returns: The exported materials universe.
        :rtype: Universe[ExportedArtifact]

    .. method:: load_exported_materials()

        Load the materials written by a previous :meth:`export` from
        ``materials.json`` in the build directory. Useful for regenerating the
        website without re-running the earlier steps::

            project.render_website(project.load_exported_materials())

        :returns: The exported materials universe.
        :rtype: Universe[ExportedArtifact]
        :raises automata.exceptions.Error: If ``materials.json`` does not exist
            (for example, after :meth:`clean_build_directory`) or does not
            contain a universe.

    .. method:: render_website(materials, current_time=None)

        Render the website from exported materials. The materials' files
        must already be in the build directory (see :meth:`export`).

        :param materials: The exported materials to render with, as returned
            by :meth:`export` (possibly filtered with :meth:`filter`).
        :type materials: Universe[ExportedArtifact]
        :param current_time: Override the current time.
        :type current_time: datetime or None

    .. method:: resolve(path)

        Resolve a ``publication.yaml`` file, returning the fully-resolved
        publication with all variables interpolated.

        :param path: Path to the ``publication.yaml`` file.
        :type path: Path
        :returns: The resolved publication.
        :rtype: Publication[UnbuiltArtifact]

    .. method:: status(current_time=None)

        What is released and scheduled, and whether the site is up to date (see
        ``automata status``). Builds nothing and runs no recipes or hooks.

        :param current_time: Override the current time.
        :type current_time: datetime or None
        :returns: Each artifact's state (``status.artifacts``), the counts, the
            next releases, the out-of-date artifacts, and when the site was last
            built; ``status.to_dict()`` gives it as JSON-ready data.
        :rtype: Status

    .. method:: check(current_time=None)

        Check the project for problems without building anything (see
        ``automata check``), returning every problem found.

        :param current_time: Override the current time.
        :type current_time: datetime or None
        :returns: The problems, each with an ``area`` and a ``message``; empty if
            there are none.
        :rtype: list[Problem]

    ``Status``, ``ArtifactStatus`` (an artifact's status, in
    ``status.artifacts``) and ``Problem`` can be imported from ``automata``,
    e.g. for type annotations.


Example: step-by-step pipeline
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from automata import Automata
    from automata.materials import filter

    project = Automata("path/to/course")

    # Start from an empty build directory
    project.clean_build_directory()

    # Discover all materials
    materials = project.discover()

    # Build (run recipes, apply release times)
    materials = project.build_materials(materials)

    # Export to build directory
    materials = project.export(materials)

    # Optionally, select materials in Python before generating
    materials = project.filter(materials, lambda key, node: key != "drafts")

    # Render the website
    project.render_website(materials)


Example: custom hooks
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from automata import Automata
    from automata.hooks import RenderPostHookArgs

    project = Automata()

    @project.hooks.on_render_post.register()
    def notify(args: RenderPostHookArgs):
        print(f"Site built at {args.build_directory}")

    project.build()


``Extension``
-------------

.. code-block:: python

    from automata.extensions import (
        EXTENSIONS_GROUP,
        THEMES_GROUP,
        Extension,
        apply_extension,
        apply_extensions,
        extension_from_directory,
        extension_from_entry_point,
    )

``automata.extensions`` is the public API for writing and loading extensions.

.. class:: Extension(name, hooks, config=None, schema=None, dependencies=None)

    A collection of hooks that customize automata's behavior.

    :param name: A human-readable name.
    :param hooks: A mapping of hook point names to callables.
    :param config: Optional configuration dictionary.
    :param schema: Optional smartconfig schema for validating config.
    :param dependencies: List of extensions to apply before this one.

.. function:: apply_extension(extension, hooks, priority=0)

    Register an extension's hooks onto a hooks instance. Dependencies are
    applied first, and each extension is applied at most once (by name).

.. function:: apply_extensions(extensions, hooks, priority=0)

    Register several extensions' hooks onto a hooks instance, in order. Each
    extension, including shared dependencies, is applied at most once across
    all of *extensions*.

.. function:: extension_from_directory(name, directory, config=None, require_templates=True, dependencies=None, project_directory=None, allow_python=False)

    Create an Extension from a directory containing ``templates/`` and,
    optionally, ``static/``, ``schema.json``, and ``hooks/``. If
    ``schema.json`` is present, *config* is validated against it. Script hooks
    in ``hooks/`` run in *project_directory* (if given).

    If *allow_python* is true and the directory contains ``extension.py``, that
    file is imported and its ``make_extension(config)`` or ``extension`` is
    combined with the directory's files (see :ref:`extensions-with-python`).
    It defaults to false, so a package calling this on its own files never
    imports itself; directory paths in ``automata.yaml`` are loaded with it set
    to true.

.. function:: extension_from_entry_point(entry_point_name, config=None, *, group=EXTENSIONS_GROUP, entry_points=None)

    Create an Extension from an installed package's entry point in *group*
    (``EXTENSIONS_GROUP``, ``"automata.extensions"``, or ``THEMES_GROUP``,
    ``"automata.themes"``). The module must export ``make_extension(config)``
    or ``extension``. Raises :class:`automata.exceptions.Error` if the entry
    point is not found or the config is invalid. *entry_points* is the set of
    entry points to search (default: those of the installed packages); each
    needs ``name``, ``group``, and ``load()``, so tests can pass fakes.

.. code-block:: python

    from automata.config import load_extensions

.. function:: load_extensions(config, cwd)

    Load the theme (from ``website.theme``) and the extensions (from
    ``extensions``) named in a :class:`Config`. Relative paths are resolved
    against *cwd*.

    :returns: ``(theme, extensions)``, where *extensions* is a list in the
        order listed.
    :raises automata.exceptions.Error: If an extension cannot be loaded, the
        theme does not provide ``page.html``, or two different extensions
        share a name.


``render``
----------

.. code-block:: python

    from automata.website import render

.. function:: render(build_directory, materials_directory, pages=None, static_content=None, vars=None, current_time=None, render_markdown=..., hooks=None, base_path="/", materials_directory_name="materials", element_configs=None, theme=None, extensions=(), materials=None)

    Render a static website from exported materials. Most users should call
    :meth:`Automata.render_website` instead.

    :param theme: The theme, available in templates as ``theme``.
    :param extensions: The other extensions. These, the theme, and their
        dependencies are available in templates as ``extensions``, keyed by
        name.
    :param hooks: A :class:`RenderHooks` instance. If given, *theme* and
        *extensions* are assumed to be registered on it already. If omitted,
        hooks are created and *theme* and *extensions* are registered on them.
    :param materials: The exported materials to render with. If omitted,
        ``materials.json`` is read from *materials_directory*. The given
        universe is not modified.


Materials types
---------------

.. class:: Universe(collections)

    The top-level container holding all collections.

    :param collections: A dictionary mapping collection names to Collection
        objects.

    .. method:: merge(other)

        Merge two universes. Raises ``KeyError`` if both contain a collection
        with the same name.

.. class:: Collection(publication_schema, publications)

    A group of related publications.

.. class:: Publication(metadata, artifacts)

    A coherent grouping of artifacts with metadata.

.. class:: UnbuiltArtifact(workdir, path, recipe=None, release_time=None, ready=True, missing_ok=False)

    An artifact before building.

.. class:: BuiltArtifact(workdir, path, returncode=None, stdout=None, stderr=None)

    An artifact after building.

.. class:: ExportedArtifact(path)

    An artifact after exporting (just a path to the file).
