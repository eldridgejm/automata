"""Resources system for automata extensions."""

import hashlib
import importlib.metadata as metadata
import importlib.resources
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import TYPE_CHECKING

from automata.hooks import GenerateHooks, Hooks
from automata.materials import ExportedArtifact, Universe, deserialize

if TYPE_CHECKING:
    from automata.website import Element


# internals ========================================================================

# the file extensions that will be treated as pages (loaded as text and rendered with
# templates) rather than static files.
_PAGE_EXTENSIONS = {".md", ".html"}


def _walk(
    directory: Traversable,
    on_file,
    _prefix_parts: list[str] | None = None,
) -> None:
    """Walk a directory tree, calling on_file(key, entry) for each file.

    Parameters
    ----------
    directory : Traversable
        The root directory to walk.
    on_file : Callable[[str, Traversable], None]
        Callback invoked for each file with its relative key and entry.
    _prefix_parts : list[str] | None, optional
        Path components accumulated so far, relative to the root. Used
        internally for recursion.
    """
    if _prefix_parts is None:
        _prefix_parts = []
    for entry in directory.iterdir():
        entry_parts = _prefix_parts + [entry.name]
        if entry.is_dir():
            _walk(entry, on_file, entry_parts)
        elif entry.is_file():
            key = "/".join(entry_parts)
            on_file(key, entry)


def _load_package_from_filesystem(
    directory: Traversable,
    module_type: str,
):
    """Load a Python package from a filesystem directory.

    The directory must contain an ``__init__.py`` file. The package is loaded
    with submodule search locations set so that relative imports from sibling
    files within the directory are supported.

    Parameters
    ----------
    directory : Traversable
        The directory containing the Python package.
    module_type : str
        Type identifier used in the generated module name (e.g.,
        ``"elements"``, ``"hooks"``).

    Returns
    -------
    module
        The loaded Python module.

    Raises
    ------
    ValueError
        If the directory does not contain ``__init__.py``, the package
        cannot be loaded, or execution fails.
    """
    init_file = directory / "__init__.py"
    if not init_file.is_file():
        raise ValueError(
            f"Directory does not contain __init__.py; cannot load as a "
            f"{module_type} package."
        )

    with importlib.resources.as_file(directory) as dir_path:
        # Multiple extensions may each have their own elements/ or hooks/
        # package. We derive a unique module name from the directory path so
        # that each package gets its own entry in sys.modules and they don't
        # collide.
        digest = hashlib.sha256(str(dir_path).encode()).hexdigest()[:12]
        module_name = f"automata.resources.{module_type}_{digest}"
        file_path = dir_path / "__init__.py"

        spec = importlib.util.spec_from_file_location(
            module_name,
            file_path,
            submodule_search_locations=[str(dir_path)],
        )
        if spec is None or spec.loader is None:
            raise ValueError(f"Unable to load {module_type} module at {file_path}.")

        module = importlib.util.module_from_spec(spec)
        # Register before exec so that relative imports within the package
        # can find the parent module in sys.modules.
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            sys.modules.pop(module_name, None)
            raise ValueError(
                f"Error loading {module_type} from {file_path}: {e}"
            ) from e

    return module


def _try_register_shell_hook(hooks: Hooks, entry: Path) -> None:
    """Register an executable file as a shell hook if it matches a hook point.

    Logs a warning if the file name does not match any known hook point.

    Parameters
    ----------
    hooks : Hooks
        The Hooks instance to register the script on.
    entry : Path
        The executable file whose name should match a hook point attribute.
    """
    hook_attr = getattr(hooks, entry.name, None)
    if hook_attr is None:
        raise ValueError(
            f"Hook script '{entry}': '{entry.name}' does not match any known "
            f"hook point."
        )
    if not hasattr(hook_attr, "register_shell_script"):
        raise ValueError(
            f"Hook script '{entry}': '{entry.name}' does not support shell scripts."
        )
    hook_attr.register_shell_script(str(entry))


# loading helpers ==================================================================


def load_templates(directory: Traversable) -> dict[str, str]:
    """Load Jinja2 templates from a directory.

    Walks the directory recursively, reading each file as text.
    Keys are relative paths within the directory.

    Parameters
    ----------
    directory : Traversable
        The directory containing template files.

    Returns
    -------
    dict[str, str]
        A dictionary mapping relative paths to template content.
    """
    templates: dict[str, str] = {}

    def _add(key: str, entry: Traversable) -> None:
        templates[key] = entry.read_text()

    _walk(directory, _add)
    return templates


def load_content(
    directory: Traversable,
) -> tuple[dict[str, str | bytes], dict[str, str | bytes]]:
    """Load pages and static files from a content directory.

    Files with .md or .html extensions are loaded as pages (text).
    All other files are loaded as static files (text if possible, bytes
    otherwise).

    Parameters
    ----------
    directory : Traversable
        The content directory to walk.

    Returns
    -------
    tuple[dict[str, str | bytes], dict[str, str | bytes]]
        A tuple of (pages, static_files), each mapping relative paths to
        file content.
    """
    pages: dict[str, str | bytes] = {}
    static_files: dict[str, str | bytes] = {}

    def _add(key: str, entry: Traversable) -> None:
        _, ext = os.path.splitext(key)
        if ext in _PAGE_EXTENSIONS:
            pages[key] = entry.read_text()
        else:
            try:
                static_files[key] = entry.read_text()
            except UnicodeDecodeError:
                static_files[key] = entry.read_bytes()

    _walk(directory, _add)
    return pages, static_files


def load_elements(directory: Traversable) -> dict[str, type["Element"]]:
    """Load element classes from a Python package directory.

    The directory must contain an ``__init__.py`` that defines an ``elements``
    variable -- a dict mapping element names to Element classes.

    Parameters
    ----------
    directory : Traversable
        The directory containing the elements Python package.

    Returns
    -------
    dict[str, type[Element]]
        A dictionary mapping element names to Element classes.

    Raises
    ------
    ValueError
        If ``__init__.py`` is missing or does not define an ``elements``
        variable.
    """
    module = _load_package_from_filesystem(directory, module_type="elements")
    if not hasattr(module, "elements"):
        raise ValueError("Elements package must define an `elements` attribute.")
    result: dict[str, type["Element"]] = module.elements
    return result


def load_hooks(directory: Traversable) -> Hooks:
    """Load hooks from a hooks directory.

    Supports two mechanisms simultaneously:

    - Executable scripts named after hook points are registered as shell hooks.
    - If ``__init__.py`` is present, it is loaded and its ``register(hooks)``
      function is called.

    Parameters
    ----------
    directory : Traversable
        The directory containing hook scripts and/or a Python package.

    Returns
    -------
    Hooks
        A Hooks instance with all discovered hooks registered.

    Raises
    ------
    ValueError
        If an executable script name does not match a known hook point,
        if a hook point does not support shell scripts, or if
        ``__init__.py`` is present but does not define a ``register``
        function.
    """
    hooks = Hooks()

    # Register executable scripts
    with importlib.resources.as_file(directory) as dir_path:
        for entry in dir_path.iterdir():
            if entry.name.startswith(".") or entry.name == "__init__.py":
                continue
            if entry.is_file() and os.access(entry, os.X_OK):
                _try_register_shell_hook(hooks, entry)

    # Register Python hooks
    init_file = directory / "__init__.py"
    if init_file.is_file():
        module = _load_package_from_filesystem(directory, module_type="hooks")
        if not hasattr(module, "register"):
            raise ValueError("Hooks package must define a `register` attribute.")
        module.register(hooks)

    return hooks


# dataclasses =====================================================================


@dataclass
class WebsiteResources:
    """Resources specific to website generation."""

    templates: dict[str, str] = field(default_factory=dict)
    pages: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    elements: dict[str, type["Element"]] = field(default_factory=dict)
    materials: Universe[ExportedArtifact] | None = None
    hooks: GenerateHooks = field(default_factory=GenerateHooks)


@dataclass
class Resources(WebsiteResources):
    """Full resource set including all hook types."""

    hooks: Hooks = field(default_factory=Hooks)  # type: ignore[reportIncompatibleVariableOverride]

    @classmethod
    def from_directory(cls, directory: Traversable) -> "Resources":
        """Load a Resources instance from a filesystem extension directory.

        Looks for ``templates/``, ``content/``, ``elements/``, and ``hooks/``
        subdirectories and loads whichever are present.

        Parameters
        ----------
        directory : Traversable
            The root directory of the filesystem extension.

        Returns
        -------
        Resources
            A Resources instance populated from the directory contents.
        """
        templates: dict[str, str] = {}
        pages: dict[str, str | bytes | Traversable] = {}
        static_files: dict[str, str | bytes | Traversable] = {}
        elements: dict[str, type["Element"]] = {}
        materials: Universe[ExportedArtifact] | None = None
        hooks = Hooks()

        templates_dir = directory / "templates"
        if templates_dir.is_dir():
            templates = load_templates(templates_dir)

        content_dir = directory / "content"
        if content_dir.is_dir():
            loaded_pages, loaded_static = load_content(content_dir)
            pages.update(loaded_pages)
            static_files.update(loaded_static)

        elements_dir = directory / "elements"
        if elements_dir.is_dir():
            elements = load_elements(elements_dir)

        materials_file = directory / "materials.json"
        if materials_file.is_file():
            loaded = deserialize(materials_file.read_text())
            assert isinstance(loaded, Universe)
            materials = loaded

        hooks_dir = directory / "hooks"
        if hooks_dir.is_dir():
            hooks = load_hooks(hooks_dir)

        return cls(
            templates=templates,
            pages=pages,
            static_files=static_files,
            elements=elements,
            materials=materials,
            hooks=hooks,
        )

    @classmethod
    def from_entry_point(
        cls, name: str, group: str = "automata.extensions"
    ) -> "Resources":
        """Load a Resources instance from an installed package entry point.

        The entry point must refer to a module that exports a ``resources``
        attribute containing a Resources instance.

        Parameters
        ----------
        name : str
            The name of the entry point.
        group : str, optional
            The entry point group to search in. Defaults to
            ``"automata.extensions"``.

        Returns
        -------
        Resources
            The Resources instance exported by the package.
        """
        entry_points = metadata.entry_points()
        ep = entry_points.select(group=group)[name]
        module = ep.load()
        result: Resources = module.resources
        return result
