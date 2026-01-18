"""Loader functions for extension components.

This module provides helper functions for loading extension components from
directories, useful when creating Python package extensions:

- :func:`load_templates_from_directory` - Load templates from a directory
- :func:`load_files_from_directory` - Load files from a directory
- :func:`load_elements_from_directory` - Load elements from a Python package
- :func:`load_hooks_from_directory` - Load hooks from a hooks.py file
- :func:`load_website_components_from_directory` - Load all website components
"""

import hashlib
import importlib.resources
import importlib.util
import sys
from dataclasses import dataclass, field
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING, Callable

from .hooks import PostGenerateWebsiteHook

if TYPE_CHECKING:
    from .hooks import PreGenerateWebsiteHook
    from .website._elements import Element

# Standard hook points supported by script hooks
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


def _load_python_module_from_directory(
    directory: Traversable,
    filename: str,
    module_type: str,
    submodule_search_locations: list[str] | None = None,
):
    """Load a Python module from a file in an extension directory.

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
    >>> from automata.loaders import load_templates_from_directory
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


def load_files_from_directory(
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
    >>> from automata.loaders import load_files_from_directory
    >>> static = load_files_from_directory(Path("my_extension/static"))
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
    >>> from automata.loaders import load_elements_from_directory
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
    >>> from automata.loaders import load_hooks_from_directory
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

        from automata.hooks import PreGenerateWebsiteHook, WebsiteContent

        class MyPreGenerateHook(PreGenerateWebsiteHook):
            priority = 50

            def __call__(self, website_content, materials, website_config,
                         build_directory, vars, current_time):
                # Hooks form a pipeline - return modified or unchanged content
                return website_content

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
class WebsiteComponents:
    """Container for website components loaded from a directory.

    Attributes
    ----------
    elements : dict[str, type[Element]]
        Dictionary mapping element names to Element classes.
    templates : dict[str, str]
        Dictionary mapping template names to their content.
    content : dict[str, str | bytes | Traversable]
        Dictionary mapping content file paths to their entries.
    assets : dict[str, str | bytes | Traversable]
        Dictionary mapping asset file paths to their entries.
    """

    elements: dict[str, type["Element"]] = field(default_factory=dict)
    templates: dict[str, str] = field(default_factory=dict)
    content: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    assets: dict[str, str | bytes | Traversable] = field(default_factory=dict)


def load_website_components_from_directory(
    directory: Traversable,
) -> WebsiteComponents:
    """Load all website components from a directory.

    Loads elements, templates, content, and assets from their respective
    subdirectories within the given directory.

    Parameters
    ----------
    directory : Traversable
        The directory containing website components. Can be a ``pathlib.Path``
        or any ``Traversable``. Expected subdirectories:

        - ``elements/`` - Python package with Element classes
        - ``templates/`` - Jinja2 template files
        - ``content/`` - Content files (markdown, HTML, images, etc.)
        - ``assets/`` - Asset files (images, CSS, JS, etc.)

    Returns
    -------
    WebsiteComponents
        A dataclass containing all loaded components. Missing subdirectories
        result in empty dictionaries for those components.

    Raises
    ------
    ValueError
        If the elements package exists but cannot be loaded or is invalid.

    Examples
    --------
    >>> from pathlib import Path
    >>> from automata.loaders import load_website_components_from_directory
    >>> components = load_website_components_from_directory(Path("my_theme"))
    >>> # components.templates = {"base.html": "...", ...}
    >>> # components.content = {"index.md": <Traversable>, ...}

    """
    return WebsiteComponents(
        elements=load_elements_from_directory(directory / "elements"),
        templates=load_templates_from_directory(directory / "templates"),
        content=load_files_from_directory(directory / "content"),
        assets=load_files_from_directory(directory / "assets"),
    )
