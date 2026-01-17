"""Plugin system for Automata.

Plugins can provide templates, static files, elements, and hooks to extend
Automata's functionality. They can be loaded from filesystem directories or
via entry points.

Themes are a special case of plugins that provide base templates for website
generation.

This module provides helper functions for loading plugin components from
directories, which can be used by plugin authors creating Python package
plugins:

- :func:`load_templates_from_directory` - Load templates from a directory
- :func:`load_static_files_from_directory` - Load static files from a directory
- :func:`load_elements_from_directory` - Load elements from a Python package
- :func:`load_hooks_from_directory` - Load hooks from a hooks.py file
"""

import hashlib
import importlib.metadata as metadata
import importlib.resources
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Sequence, cast

import smartconfig.exceptions
import smartconfig.types

if TYPE_CHECKING:
    from .website._elements import Element


def _is_hidden(parts: list[str]) -> bool:
    """Check if any path component is hidden (starts with dot)."""
    return any(part.startswith(".") for part in parts)


def _walk_directory(
    directory: Traversable,
    on_file: Callable[[str, Traversable], None],
    rel_parts: list[str] | None = None,
) -> None:
    """Walk a directory tree, calling on_file for each non-hidden file.

    Parameters
    ----------
    directory : Traversable
        The directory to walk.
    on_file : Callable[[str, Traversable], None]
        Callback called for each file with (relative_path, file_entry).
        The relative_path uses forward slashes as separators.
    rel_parts : list[str] | None
        Internal parameter for tracking relative path components.

    """
    if rel_parts is None:
        rel_parts = []

    for entry in directory.iterdir():
        entry_parts = rel_parts + [entry.name]
        if _is_hidden(entry_parts):
            continue
        if entry.is_dir():
            _walk_directory(entry, on_file, entry_parts)
        else:
            key = "/".join(entry_parts)
            on_file(key, entry)


def load_templates_from_directory(directory: Traversable) -> dict[str, str]:
    """Load templates from a directory.

    Recursively reads all non-hidden files from the directory, treating each
    file's contents as a template string. Hidden files and directories (those
    starting with a dot) are skipped.

    Parameters
    ----------
    directory : Traversable
        The directory containing template files. Can be a ``pathlib.Path``
        or any ``Traversable`` (e.g., from ``importlib.resources``).

    Returns
    -------
    dict[str, str]
        Dictionary mapping relative paths (using forward slashes) to template
        content strings. Returns an empty dict if the directory doesn't exist.

    Examples
    --------
    >>> from pathlib import Path
    >>> from automata.plugin import load_templates_from_directory
    >>> templates = load_templates_from_directory(Path("my_plugin/templates"))
    >>> # templates = {"page.html": "...", "partials/header.html": "..."}

    """
    if not directory.is_dir():
        return {}

    templates: dict[str, str] = {}

    def add_template(key: str, entry: Traversable) -> None:
        templates[key] = entry.read_text()

    _walk_directory(directory, add_template)
    return templates


def load_static_files_from_directory(
    directory: Traversable,
) -> dict[str, str | bytes | Traversable]:
    """Load static files from a directory.

    Recursively collects all non-hidden files from the directory. The files
    are returned as Traversable references rather than being read into memory,
    allowing for lazy loading when the files are actually needed.

    Parameters
    ----------
    directory : Traversable
        The directory containing static files. Can be a ``pathlib.Path``
        or any ``Traversable`` (e.g., from ``importlib.resources``).

    Returns
    -------
    dict[str, str | bytes | Traversable]
        Dictionary mapping relative paths (using forward slashes) to file
        entries. Returns an empty dict if the directory doesn't exist.

    Examples
    --------
    >>> from pathlib import Path
    >>> from automata.plugin import load_static_files_from_directory
    >>> static = load_static_files_from_directory(Path("my_plugin/static"))
    >>> # static = {"style.css": <Traversable>, "images/logo.png": <Traversable>}

    """
    if not directory.is_dir():
        return {}

    static_files: dict[str, str | bytes | Traversable] = {}

    def add_static_file(key: str, entry: Traversable) -> None:
        static_files[key] = entry

    _walk_directory(directory, add_static_file)
    return static_files


def load_elements_from_directory(
    directory: Traversable,
) -> dict[str, type["Element"]]:
    """Load elements from a directory.

    The directory must be a Python package (containing an ``__init__.py`` file)
    and must define an ``elements`` variable that is a dictionary mapping
    element names to Element classes.

    Parameters
    ----------
    directory : Traversable
        The directory containing the elements package. Can be a ``pathlib.Path``
        or any ``Traversable``.

    Returns
    -------
    dict[str, type[Element]]
        Dictionary mapping element names to Element classes. Returns an empty
        dict if the directory doesn't exist or has no ``__init__.py``.

    Raises
    ------
    ValueError
        If the elements package exists but cannot be loaded, or does not
        define a valid ``elements`` variable.

    Examples
    --------
    >>> from pathlib import Path
    >>> from automata.plugin import load_elements_from_directory
    >>> elements = load_elements_from_directory(Path("my_plugin/elements"))

    """
    if not directory.is_dir():
        return {}

    init_file = directory / "__init__.py"
    if not init_file.is_file():
        return {}

    module = _load_python_module_from_directory(
        directory=directory,
        filename="__init__.py",
        module_type="elements",
        submodule_search_locations=[str(directory)],
    )

    if hasattr(module, "elements"):
        elements = module.elements
    else:
        raise ValueError(
            f"Elements package at {init_file} must define an `elements` variable."
        )

    if not isinstance(elements, dict):
        raise ValueError(
            f"Elements package at {init_file} must return a dict of elements."
        )

    return elements


def load_hooks_from_directory(
    directory: Traversable,
) -> dict[str, list[tuple[int, Callable[..., Any]]]]:
    """Load hooks from a hooks.py file in a directory.

    The hooks.py file should define functions named after hook points:

    - ``pre_generate(context: dict) -> dict`` - Called before website generation
    - ``post_generate(context: dict) -> None`` - Called after website generation

    Each hook function can optionally have a corresponding priority constant:

    - ``PRE_GENERATE_PRIORITY = 50``
    - ``POST_GENERATE_PRIORITY = 50``

    If no priority constant is defined, the default priority of 50 is used.
    Lower priority values execute first.

    Parameters
    ----------
    directory : Traversable
        The directory containing hooks.py. Can be a ``pathlib.Path``
        or any ``Traversable``.

    Returns
    -------
    dict[str, list[tuple[int, Callable]]]
        Mapping from hook point names to lists of (priority, callable) tuples.
        Returns an empty dict if hooks.py doesn't exist.

    Raises
    ------
    ValueError
        If hooks.py exists but cannot be loaded.

    Examples
    --------
    >>> from pathlib import Path
    >>> from automata.plugin import load_hooks_from_directory
    >>> hooks = load_hooks_from_directory(Path("my_plugin"))

    """
    if not directory.is_dir():
        return {}

    hooks_file = directory / "hooks.py"
    if not hooks_file.is_file():
        return {}

    module = _load_python_module_from_directory(
        directory=directory,
        filename="hooks.py",
        module_type="hooks",
    )

    hooks: dict[str, list[tuple[int, Callable[..., Any]]]] = {}

    # Standard hook points to look for
    hook_points = ["pre_generate", "post_generate"]

    for hook_point in hook_points:
        if hasattr(module, hook_point):
            func = getattr(module, hook_point)
            if callable(func):
                # Look for priority constant (e.g., PRE_GENERATE_PRIORITY)
                priority_attr = f"{hook_point.upper()}_PRIORITY"
                priority = getattr(module, priority_attr, 50)
                hooks[hook_point] = [(priority, func)]

    return hooks


@dataclass
class Plugin:
    """A plugin that provides templates, static files, elements, and/or hooks.

    Plugins can be loaded from filesystem directories or via entry points.
    Multiple plugins can be merged together, with later plugins overriding
    earlier ones (except for hooks, which are accumulated).

    Attributes
    ----------
    templates : dict[str, str]
        Dictionary mapping template names to their content.
    static_files : dict[str, str | bytes | Traversable]
        Dictionary mapping static file names to their content. If the value
        is a Traversable, the file will be copied from that location. If the
        value is bytes or a string, that content will be written directly.
    elements : dict[str, type[Element]]
        Dictionary mapping element names to Element classes.
    schema : smartconfig.types.Schema | None
        Optional smartconfig schema for validating plugin configuration.
    hooks : dict[str, list[tuple[int, Callable]]]
        Dictionary mapping hook point names (e.g., "pre_generate") to lists
        of (priority, callable) tuples. Lower priority values execute first.
    """

    templates: dict[str, str] = field(default_factory=dict)
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    elements: dict[str, type["Element"]] = field(default_factory=dict)
    schema: smartconfig.types.Schema | None = None
    hooks: dict[str, list[tuple[int, Callable[..., Any]]]] = field(default_factory=dict)

    @classmethod
    def from_directory(
        cls, directory: Traversable, require_templates: bool = False
    ) -> "Plugin":
        """Create a Plugin instance from a directory.

        If the directory contains an ``__init__.py`` file, it is treated as a
        Python package and loaded as a module. The module is expected to export
        a ``plugin`` attribute containing a Plugin instance.

        For non-Python plugins (directories without ``__init__.py``), the
        directory may contain:

        - ``templates/`` subdirectory with Jinja2 template files
        - ``static/`` subdirectory with static files (CSS, JS, images, etc.)
        - ``elements/`` subdirectory containing a Python package that exports
          an ``elements`` dictionary
        - ``schema.json`` file with a smartconfig schema for configuration
        - ``hooks.py`` file with hook functions

        All components are optional unless ``require_templates`` is True.

        Parameters
        ----------
        directory : Traversable
            The directory containing the plugin files. Use ``PathTraversable``
            to wrap a ``pathlib.Path``.
        require_templates : bool, optional
            If True, the directory must contain a ``templates/`` subdirectory.
            Default is False.

        Returns
        -------
        Plugin
            The created Plugin instance.

        Raises
        ------
        ValueError
            If the directory does not exist, if ``require_templates`` is True
            and the ``templates/`` directory is missing, if the directory
            contains ``__init__.py`` but does not export a ``plugin``
            attribute, or if the ``elements/`` package is invalid.
        """
        if not directory.is_dir():
            raise ValueError("Plugin directory does not exist or is not a directory.")

        # Check if this is a Python package (has __init__.py)
        init_file = directory / "__init__.py"
        if init_file.is_file():
            return _load_plugin_from_package(directory)

        templates_dir = directory / "templates"
        if require_templates and not templates_dir.is_dir():
            raise ValueError('Plugin directory must contain a "templates" directory.')

        # Load components using public helper functions
        templates = load_templates_from_directory(templates_dir)
        static_files = load_static_files_from_directory(directory / "static")
        elements = load_elements_from_directory(directory / "elements")
        hooks = load_hooks_from_directory(directory)

        # Load schema from schema.json if present
        schema_file = directory / "schema.json"
        schema: smartconfig.types.Schema | None = None

        if schema_file.is_file():
            try:
                schema_content = schema_file.read_text()
                schema = json.loads(schema_content)
                smartconfig.validate_schema(schema)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in schema.json: {e}")
            except smartconfig.exceptions.InvalidSchemaError as e:
                raise ValueError(f"Plugin configuration schema is invalid: {e}")

        return cls(
            templates=templates,
            static_files=static_files,
            elements=elements,
            schema=schema,
            hooks=hooks,
        )

    @classmethod
    def from_entry_point(cls, name: str, group: str = "automata.plugins") -> "Plugin":
        """Create a Plugin instance from an entry point.

        The entry point should refer to a module that either:
        1. Exports a ``plugin`` attribute containing a Plugin instance, or
        2. Is a package with ``templates/``, ``static/``, and/or ``elements/``
           directories.

        If the module has a ``plugin`` attribute, it will be used. Otherwise,
        the module will be treated as a plugin package and loaded from its
        directories.

        Parameters
        ----------
        name : str
            The name of the entry point.
        group : str, optional
            The entry point group to search in. Default is "automata.plugins".
            Use "automata.website.themes" for theme plugins.

        Returns
        -------
        Plugin
            The created Plugin instance.

        Raises
        ------
        KeyError
            If the entry point is not found.
        ValueError
            If the plugin cannot be loaded.
        """
        entry_points = metadata.entry_points()
        entry_point = entry_points.select(group=group)[name]

        module = entry_point.load()
        if hasattr(module, "plugin"):
            return cast(Plugin, module.plugin)
        else:
            root = importlib.resources.files(module)
            return cls.from_directory(root)

    @classmethod
    def from_spec(cls, spec: str, group: str = "automata.plugins") -> "Plugin":
        """Create a Plugin instance from a specification string.

        The spec can be either:
        - A path to a directory (contains a path separator)
        - An entry point name (looked up in the specified group)

        Parameters
        ----------
        spec : str
            Either a filesystem path or an entry point name.
        group : str, optional
            The entry point group to search in if spec is a name.
            Default is "automata.plugins".

        Returns
        -------
        Plugin
            The created Plugin instance.

        Raises
        ------
        ValueError
            If the plugin cannot be loaded.
        """
        if os.sep in spec or (os.altsep and os.altsep in spec):
            # It's a path - Path is duck-typed compatible with Traversable
            return cls.from_directory(Path(spec))  # type: ignore[arg-type]
        else:
            # It's an entry point name
            return cls.from_entry_point(name=spec, group=group)


def merge_plugins(plugins: Sequence[Plugin]) -> Plugin:
    """Merge multiple plugins into a single plugin.

    Plugins are merged in order, with later plugins overriding earlier ones.
    For example, if plugin A provides template "page.html" and plugin B also
    provides "page.html", the merged result will use plugin B's version.

    Hooks are accumulated rather than overridden - all hooks from all plugins
    are collected and will execute in priority order.

    The merged plugin will have no schema, as individual plugin configurations
    should be validated before merging.

    Parameters
    ----------
    plugins : Sequence[Plugin]
        The plugins to merge, in order of increasing priority.

    Returns
    -------
    Plugin
        A new Plugin instance containing the merged templates, static files,
        elements, and hooks from all input plugins.
    """
    templates: dict[str, str] = {}
    static_files: dict[str, str | bytes | Traversable] = {}
    elements: dict[str, type["Element"]] = {}
    hooks: dict[str, list[tuple[int, Callable[..., Any]]]] = {}

    for plugin in plugins:
        templates.update(plugin.templates)
        static_files.update(plugin.static_files)
        elements.update(plugin.elements)

        # Accumulate hooks (don't override)
        for hook_point, hook_list in plugin.hooks.items():
            if hook_point not in hooks:
                hooks[hook_point] = []
            hooks[hook_point].extend(hook_list)

    return Plugin(
        templates=templates,
        static_files=static_files,
        elements=elements,
        schema=None,
        hooks=hooks,
    )


# Private helper functions


def _load_python_module_from_directory(
    directory: Traversable,
    filename: str,
    module_type: str,
    submodule_search_locations: list[str] | None = None,
):
    """Load a Python module from a file in a plugin directory.

    Handles the common pattern of loading Python modules from plugin directories:
    1. Converting Traversable to file path
    2. Generating unique module name with hash
    3. Loading module with spec_from_file_location
    4. Adding to sys.modules and executing
    5. Cleaning up on error

    Parameters
    ----------
    directory : Traversable
        The directory containing the file.
    filename : str
        Name of the Python file to load (e.g., "__init__.py").
    module_type : str
        Type identifier for module name (e.g., "elements").
    submodule_search_locations : list[str] | None, optional
        Optional submodule search locations for package loading.

    Returns
    -------
    module
        The loaded module object.

    Raises
    ------
    ValueError
        If the module cannot be loaded.
    """
    with importlib.resources.as_file(directory) as dir_path:
        digest = hashlib.sha256(str(dir_path).encode("utf-8")).hexdigest()[:12]
        module_name = f"automata.plugin_{module_type}_{digest}"
        file_path = dir_path / filename

        spec = importlib.util.spec_from_file_location(
            module_name,
            file_path,
            submodule_search_locations=submodule_search_locations,
        )
        if spec is None or spec.loader is None:
            raise ValueError(f"Unable to load {module_type} module at {file_path}.")

        module = importlib.util.module_from_spec(spec)

        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            # Clean up sys.modules if loading fails
            sys.modules.pop(module_name, None)
            raise ValueError(
                f"Error loading {module_type} from {file_path}: {e}"
            ) from e

    return module


def _load_plugin_from_package(directory: Traversable) -> "Plugin":
    """Load a Plugin instance from a Python package.

    The directory must contain an __init__.py that exports a ``plugin``
    attribute which is a Plugin instance.

    Parameters
    ----------
    directory : Traversable
        The directory containing the Python package.

    Returns
    -------
    Plugin
        The Plugin instance.

    Raises
    ------
    ValueError
        If the module cannot be loaded or does not export a valid ``plugin``
        attribute.

    """
    module = _load_python_module_from_directory(
        directory=directory,
        filename="__init__.py",
        module_type="plugin",
        submodule_search_locations=[str(directory)],
    )

    if not hasattr(module, "plugin"):
        raise ValueError(
            f"Python package plugin at {directory} must export a 'plugin' attribute."
        )

    plugin = module.plugin
    if not isinstance(plugin, Plugin):
        raise ValueError(
            f"Python package plugin at {directory} must export a Plugin instance, "
            f"got {type(plugin).__name__}."
        )

    return plugin
