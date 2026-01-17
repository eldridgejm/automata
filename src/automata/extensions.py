"""Extension system for Automata.

Extensions can provide templates, static files, elements, and hooks to extend
Automata's functionality. They can be loaded from filesystem directories or
via entry points.

Themes are a special case of extensions that provide base templates for website
generation.

Extension Types
------------

There are two types of extensions:

1. **Filesystem extensions** - A directory without ``__init__.py`` that uses a
   conventional structure to provide extension components.

2. **Python package extensions** - A directory with ``__init__.py`` that exports
   a ``extension`` attribute containing a :class:`Extension` instance.

Filesystem Extension Structure
---------------------------

A filesystem extension is a directory with the following optional structure::

    my_extension/
    ├── templates/          # Jinja2 template files
    │   ├── base.html
    │   ├── page.html
    │   └── partials/
    │       └── header.html
    ├── static/             # Static files (CSS, JS, images, etc.)
    │   ├── style.css
    │   └── images/
    │       └── logo.png
    ├── elements/           # Custom elements (Python package)
    │   ├── __init__.py     # Must export `elements` dict
    │   └── _my_element.py
    ├── hooks/              # Hook functions or scripts
    │   └── ...             # See below for structure options
    └── schema.json         # Configuration schema (smartconfig format)

All components are optional. The directory must NOT contain an ``__init__.py``
file at the root level (that would make it a Python package extension instead).

- **templates/**: Contains Jinja2 template files. Files are loaded recursively
  and keyed by their relative path (e.g., ``partials/header.html``).

- **static/**: Contains static files to be copied to the build output. Files
  are loaded recursively and keyed by their relative path.

- **elements/**: Must be a Python package (contain ``__init__.py``) that exports
  an ``elements`` dictionary mapping element names to Element classes.

- **hooks/**: Can be structured in one of two ways:

  1. **Python package** (contains ``__init__.py``): The module must export a
     ``hooks`` variable containing a dictionary mapping hook point names to
     lists of hook instances::

         hooks/
         ├── __init__.py     # Must export `hooks` dict
         └── _helpers.py     # Optional helper modules

     The ``__init__.py`` defines hook classes and exports them::

         from automata.hooks import (
             PreGenerateWebsiteHook,
             PostGenerateWebsiteHook,
             GenerateOverrides,
         )

         class MyPreGenerateHook(PreGenerateWebsiteHook):
             priority = 50

             def __call__(self, materials, website_config, build_directory,
                          vars, current_time):
                 return GenerateOverrides(pages={}, assets={})

         class MyPostGenerateHook(PostGenerateWebsiteHook):
             priority = 100

             def __call__(self, materials, website_config, build_directory,
                          vars, current_time):
                 pass

         hooks = {
             "pre_generate_website": [MyPreGenerateHook()],
             "post_generate_website": [MyPostGenerateHook()],
         }

  2. **Script directory** (no ``__init__.py``): Contains executable scripts
     named after hook points::

         hooks/
         └── post_generate_website   # Executable script

     Scripts receive context as JSON on stdin and cannot return values.
     All script hooks run with priority 50. Note that only
     ``post_generate_website`` supports script hooks since
     ``pre_generate_website`` must return values.

  Supported hooks: ``pre_generate_website``, ``post_generate_website``.
  Lower priority values execute first.

- **schema.json**: A smartconfig schema for validating extension configuration.

Python Package Extension Structure
-------------------------------

A Python package extension is a directory with an ``__init__.py`` that exports
a ``extension`` attribute::

    my_extension/
    ├── __init__.py         # Must export `extension = Extension(...)`
    ├── templates.py        # Can organize however you like
    └── ...

The ``__init__.py`` must export a :class:`Extension` instance::

    from automata import Extension, load_templates_from_directory
    from pathlib import Path

    here = Path(__file__).parent

    extension = Extension(
        templates=load_templates_from_directory(here / "templates"),
        static_files={"style.css": (here / "style.css").read_text()},
    )

Helper Functions
----------------

This module provides helper functions for loading extension components from
directories, useful when creating Python package extensions:

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
from typing import TYPE_CHECKING, Callable, Sequence, cast

import smartconfig.exceptions
import smartconfig.types

from .hooks import Hooks, PostGenerateWebsiteHook

if TYPE_CHECKING:
    from .hooks import PreGenerateWebsiteHook
    from .website._elements import Element

# Standard hook points supported by the system (script hooks only support post_generate)
HOOK_POINTS = ["post_generate_website"]


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
    >>> from automata.extension import load_templates_from_directory
    >>> templates = load_templates_from_directory(Path("my_extension/templates"))
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
    >>> from automata.extension import load_static_files_from_directory
    >>> static = load_static_files_from_directory(Path("my_extension/static"))
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
    >>> from automata.extension import load_elements_from_directory
    >>> elements = load_elements_from_directory(Path("my_extension/elements"))

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
) -> dict[str, list["PreGenerateWebsiteHook | PostGenerateWebsiteHook"]]:
    """Load hooks from a directory.

    The directory can be either:

    1. A Python package (contains ``__init__.py``) that exports a ``hooks``
       variable - a dictionary mapping hook point names to lists of hook
       instances (objects with a ``priority`` attribute and ``__call__`` method).

    2. A directory containing executable scripts named after hook points
       (e.g., ``post_generate_website``). Scripts receive JSON on stdin and
       run with priority 50. Note: Only ``post_generate_website`` supports
       script hooks since ``pre_generate_website`` must return values.

    Parameters
    ----------
    directory : Traversable
        The hooks directory. Can be a ``pathlib.Path`` or any ``Traversable``.

    Returns
    -------
    dict[str, list]
        Mapping from hook point names to lists of hook instances.
        Returns an empty dict if the directory doesn't exist or has no hooks.

    Raises
    ------
    ValueError
        If the directory contains ``__init__.py`` but does not export a valid
        ``hooks`` variable.

    Examples
    --------
    >>> from pathlib import Path
    >>> from automata.extension import load_hooks_from_directory
    >>> hooks = load_hooks_from_directory(Path("my_extension/hooks"))

    """
    if not directory.is_dir():
        return {}

    # Check if this is a Python package
    init_file = directory / "__init__.py"
    if init_file.is_file():
        return _load_hooks_from_package(directory)

    # Otherwise, load as script hooks
    hooks: dict[str, list["PreGenerateWebsiteHook | PostGenerateWebsiteHook"]] = {}

    # Need actual filesystem path for script execution
    with importlib.resources.as_file(directory) as dir_path:
        for hook_point in HOOK_POINTS:
            script_file = directory / hook_point
            if script_file.is_file():
                script_path = dir_path / hook_point
                # Create hook instance from script
                hook = PostGenerateWebsiteHook.from_script(
                    command=str(script_path),
                    cwd=dir_path,
                    priority=50,
                )
                hooks[hook_point] = [hook]

    return hooks


def _load_hooks_from_package(
    directory: Traversable,
) -> dict[str, list["PreGenerateWebsiteHook | PostGenerateWebsiteHook"]]:
    """Load hooks from a Python package (directory with __init__.py).

    The package must export a ``hooks`` variable that is a dictionary mapping
    hook point names to lists of hook instances (objects with a ``priority``
    attribute and ``__call__`` method).

    Example hooks/__init__.py::

        from automata.hooks import PreGenerateWebsiteHook, GenerateOverrides

        class MyPreGenerateHook(PreGenerateWebsiteHook):
            priority = 50

            def __call__(self, materials, website_config, build_directory,
                         vars, current_time):
                return GenerateOverrides(pages={}, assets={})

        hooks = {
            "pre_generate_website": [MyPreGenerateHook()],
        }

    """
    module = _load_python_module_from_directory(
        directory=directory,
        filename="__init__.py",
        module_type="hooks",
        submodule_search_locations=[str(directory)],
    )

    if not hasattr(module, "hooks"):
        raise ValueError(
            f"Hooks package at {directory} must define a `hooks` variable."
        )

    hooks = module.hooks

    if not isinstance(hooks, dict):
        raise ValueError(f"Hooks package at {directory} must define `hooks` as a dict.")

    return hooks


@dataclass
class Extension:
    """A extension that provides templates, static files, elements, and/or hooks.

    Extensions can be loaded from filesystem directories or via entry points.
    Multiple extensions can be merged together, with later extensions overriding
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
        Optional smartconfig schema for validating extension configuration.
    hooks : dict[str, list]
        Dictionary mapping hook point names (e.g., "pre_generate_website") to
        lists of hook instances. Each hook instance has a ``priority`` attribute
        and a ``__call__`` method. Lower priority values execute first.
    """

    templates: dict[str, str] = field(default_factory=dict)
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    elements: dict[str, type["Element"]] = field(default_factory=dict)
    schema: smartconfig.types.Schema | None = None
    hooks: Hooks = field(default_factory=lambda: cast(Hooks, {}))

    @classmethod
    def from_directory(
        cls, directory: Traversable, require_templates: bool = False
    ) -> "Extension":
        """Create a Extension instance from a directory.

        If the directory contains an ``__init__.py`` file, it is treated as a
        Python package and loaded as a module. The module is expected to export
        a ``extension`` attribute containing a Extension instance.

        For non-Python extensions (directories without ``__init__.py``), the
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
            The directory containing the extension files. Use ``PathTraversable``
            to wrap a ``pathlib.Path``.
        require_templates : bool, optional
            If True, the directory must contain a ``templates/`` subdirectory.
            Default is False.

        Returns
        -------
        Extension
            The created Extension instance.

        Raises
        ------
        ValueError
            If the directory does not exist, if ``require_templates`` is True
            and the ``templates/`` directory is missing, if the directory
            contains ``__init__.py`` but does not export a ``extension``
            attribute, or if the ``elements/`` package is invalid.
        """
        if not directory.is_dir():
            raise ValueError(
                "Extension directory does not exist or is not a directory."
            )

        # Check if this is a Python package (has __init__.py)
        init_file = directory / "__init__.py"
        if init_file.is_file():
            return _load_extension_from_package(directory)

        templates_dir = directory / "templates"
        if require_templates and not templates_dir.is_dir():
            raise ValueError(
                'Extension directory must contain a "templates" directory.'
            )

        # Load components using public helper functions
        templates = load_templates_from_directory(templates_dir)
        static_files = load_static_files_from_directory(directory / "static")
        elements = load_elements_from_directory(directory / "elements")
        hooks = cast(Hooks, load_hooks_from_directory(directory / "hooks"))

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
                raise ValueError(f"Extension configuration schema is invalid: {e}")

        return cls(
            templates=templates,
            static_files=static_files,
            elements=elements,
            schema=schema,
            hooks=hooks,
        )

    @classmethod
    def from_entry_point(
        cls, name: str, group: str = "automata.extensions"
    ) -> "Extension":
        """Create an Extension instance from an entry point.

        The entry point should refer to a module that either:
        1. Exports an ``extension`` attribute containing an Extension instance, or
        2. Is a package with ``templates/``, ``static/``, and/or ``elements/``
           directories.

        If the module has a ``extension`` attribute, it will be used. Otherwise,
        the module will be treated as a extension package and loaded from its
        directories.

        Parameters
        ----------
        name : str
            The name of the entry point.
        group : str, optional
            The entry point group to search in. Default is "automata.extensions".
            Use "automata.website.themes" for theme extensions.

        Returns
        -------
        Extension
            The created Extension instance.

        Raises
        ------
        KeyError
            If the entry point is not found.
        ValueError
            If the extension cannot be loaded.
        """
        entry_points = metadata.entry_points()
        entry_point = entry_points.select(group=group)[name]

        module = entry_point.load()
        if hasattr(module, "extension"):
            return cast(Extension, module.extension)
        else:
            root = importlib.resources.files(module)
            return cls.from_directory(root)

    @classmethod
    def from_spec(cls, spec: str, group: str = "automata.extensions") -> "Extension":
        """Create a Extension instance from a specification string.

        The spec can be either:
        - A path to a directory (contains a path separator)
        - An entry point name (looked up in the specified group)

        Parameters
        ----------
        spec : str
            Either a filesystem path or an entry point name.
        group : str, optional
            The entry point group to search in if spec is a name.
            Default is "automata.extensions".

        Returns
        -------
        Extension
            The created Extension instance.

        Raises
        ------
        ValueError
            If the extension cannot be loaded.
        """
        if os.sep in spec or (os.altsep and os.altsep in spec):
            # It's a path - Path is duck-typed compatible with Traversable
            return cls.from_directory(Path(spec))  # type: ignore[arg-type]
        else:
            # It's an entry point name
            return cls.from_entry_point(name=spec, group=group)


def merge_extensions(extensions: Sequence[Extension]) -> Extension:
    """Merge multiple extensions into a single extension.

    Extensions are merged in order, with later extensions overriding earlier ones.
    For example, if extension A provides template "page.html" and extension B also
    provides "page.html", the merged result will use extension B's version.

    Hooks are accumulated rather than overridden - all hooks from all extensions
    are collected and will execute in priority order.

    The merged extension will have no schema, as individual extension configurations
    should be validated before merging.

    Parameters
    ----------
    extensions : Sequence[Extension]
        The extensions to merge, in order of increasing priority.

    Returns
    -------
    Extension
        A new Extension instance containing the merged templates, static files,
        elements, and hooks from all input extensions.
    """
    templates: dict[str, str] = {}
    static_files: dict[str, str | bytes | Traversable] = {}
    elements: dict[str, type["Element"]] = {}
    hooks_dict: dict[str, list] = {}

    for extension in extensions:
        templates.update(extension.templates)
        static_files.update(extension.static_files)
        elements.update(extension.elements)

        # Accumulate hooks (don't override)
        for hook_point, hook_list in extension.hooks.items():
            if hook_point not in hooks_dict:
                hooks_dict[hook_point] = []
            hooks_dict[hook_point].extend(cast(list, hook_list))

    return Extension(
        templates=templates,
        static_files=static_files,
        elements=elements,
        schema=None,
        hooks=cast(Hooks, hooks_dict),
    )


# Private helper functions


def _load_python_module_from_directory(
    directory: Traversable,
    filename: str,
    module_type: str,
    submodule_search_locations: list[str] | None = None,
):
    """Load a Python module from a file in a extension directory.

    Handles the common pattern of loading Python modules from extension directories:
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
        module_name = f"automata.extension_{module_type}_{digest}"
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


def _load_extension_from_package(directory: Traversable) -> "Extension":
    """Load a Extension instance from a Python package.

    The directory must contain an __init__.py that exports a ``extension``
    attribute which is a Extension instance.

    Parameters
    ----------
    directory : Traversable
        The directory containing the Python package.

    Returns
    -------
    Extension
        The Extension instance.

    Raises
    ------
    ValueError
        If the module cannot be loaded or does not export a valid ``extension``
        attribute.

    """
    module = _load_python_module_from_directory(
        directory=directory,
        filename="__init__.py",
        module_type="extension",
        submodule_search_locations=[str(directory)],
    )

    if not hasattr(module, "extension"):
        raise ValueError(
            f"Python package extension at {directory} must export an "
            f"'extension' attribute."
        )

    extension = module.extension
    if not isinstance(extension, Extension):
        raise ValueError(
            f"Python package extension at {directory} must export an "
            f"Extension instance, got {type(extension).__name__}."
        )

    return extension
