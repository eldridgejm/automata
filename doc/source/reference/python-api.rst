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
        If ``None``, uses the current working directory.
    :type path: Path or None

    .. attribute:: path

        The project directory path.

    .. attribute:: config

        The parsed :class:`Config` object.

    .. attribute:: hooks

        The :class:`Hooks` instance with all extensions registered.

    .. method:: generate(current_time=None)

        Run the full pipeline: discover, build, export, and generate website.

        :param current_time: Override the current time. If ``None``, uses
            ``datetime.now()``.
        :type current_time: datetime or None

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

    .. method:: export(universe)

        Export built materials to the build directory and write
        ``materials.json``.

        :param universe: The built materials to export.
        :type universe: Universe[BuiltArtifact]
        :returns: The exported materials universe.
        :rtype: Universe[ExportedArtifact]

    .. method:: generate_website(current_time=None)

        Generate the website from exported materials. Assumes
        :meth:`export` has already been called.

        :param current_time: Override the current time.
        :type current_time: datetime or None

    .. method:: resolve(path)

        Resolve a ``publication.yaml`` file, returning the fully-resolved
        publication with all variables interpolated.

        :param path: Path to the ``publication.yaml`` file.
        :type path: Path
        :returns: The resolved publication.
        :rtype: Publication[UnbuiltArtifact]


Example: step-by-step pipeline
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from automata import Automata
    from automata.materials import filter

    project = Automata("path/to/course")

    # Discover all materials
    materials = project.discover()

    # Build (run recipes, apply release times)
    materials = project.build_materials(materials)

    # Export to build directory
    project.export(materials)

    # Generate the website
    project.generate_website()


Example: custom hooks
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from automata import Automata
    from automata.hooks import GeneratePostHookArgs

    project = Automata()

    @project.hooks.on_generate_post.register()
    def notify(args: GeneratePostHookArgs):
        print(f"Site built at {args.config.build_directory}")

    project.generate()


``Extension``
-------------

.. code-block:: python

    from automata._extension import Extension, apply_extension

.. class:: Extension(name, hooks, config=None, schema=None, dependencies=None)

    A collection of hooks that customize automata's behavior.

    :param name: A human-readable name.
    :param hooks: A mapping of hook point names to callables.
    :param config: Optional configuration dictionary.
    :param schema: Optional smartconfig schema for validating config.
    :param dependencies: List of extensions to apply before this one.

.. function:: apply_extension(extension, hooks, priority=0)

    Register an extension's hooks onto a hooks instance.

.. function:: extension_from_directory(name, directory, config=None, require_templates=True, dependencies=None)

    Create an Extension from a theme directory layout.

.. function:: extension_from_entry_point(entry_point_name, config=None)

    Create an Extension from an installed package's entry point.


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
