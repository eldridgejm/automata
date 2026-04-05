"""Loading extensions from theme directories and entry points."""

import hashlib
import importlib.metadata as metadata
import importlib.resources
import importlib.util
import json
import sys
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING, Any, cast

import smartconfig.exceptions
import smartconfig.types

from .._extension import Extension
from ..hooks import GeneratePostHookArgs, WebsiteInputs

if TYPE_CHECKING:
    from ._elements import Element


def extension_from_directory(
    name: str,
    directory: Traversable,
    config: dict[str, Any] | None = None,
    require_templates: bool = True,
) -> Extension:
    """Create an Extension from a theme directory.

    The directory must contain a ``templates/`` subdirectory with template
    files (unless *require_templates* is False). It may optionally contain
    a ``static/`` subdirectory with static files, an ``elements/``
    subdirectory containing a Python package, and a ``hooks.py`` file.

    If the ``elements/`` directory is present, it must contain an
    ``__init__.py`` file that defines an ``elements`` variable — a
    dictionary mapping element names to :class:`Element` classes.

    If a ``hooks.py`` file is present, it may define a ``post_generate``
    function that will be registered as an ``on_generate_post`` hook.

    Parameters
    ----------
    name : str
        A human-readable name for the extension.
    directory : Traversable
        The directory containing the theme files.
    config : dict[str, Any] | None
        Optional configuration for the extension.
    require_templates : bool
        If True (default), the directory must contain a ``templates/``
        subdirectory.

    Returns
    -------
    Extension
        The created Extension.

    """
    if not directory.is_dir():
        raise ValueError("Theme directory does not exist or is not a directory.")

    templates_dir = directory / "templates"
    if require_templates and not templates_dir.is_dir():
        raise ValueError('Theme directory must contain a "templates" directory.')

    static_dir = directory / "static"

    templates: dict[str, str] = {}
    static_files: dict[str, str | bytes | Traversable] = {}
    elements: dict[str, type["Element"]] = {}

    if templates_dir.is_dir():
        _walk(templates_dir, lambda key, entry: templates.__setitem__(key, entry.read_text()))
    if static_dir.is_dir():
        _walk(static_dir, lambda key, entry: static_files.__setitem__(key, entry))

    elements_dir = directory / "elements"
    if elements_dir.is_dir():
        elements = _load_elements_from_directory(elements_dir)

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
            raise ValueError(f"Theme configuration schema is invalid: {e}")

    # Validate config against schema when config is provided
    resolved_config = config if config is not None else {}
    if schema is not None and config is not None:
        try:
            resolved_config = smartconfig.resolve(resolved_config, schema)
        except smartconfig.exceptions.ResolutionError as e:
            raise ValueError(f"Invalid extension configuration: {e}")

    # Build the hooks dict
    hooks: dict[str, Any] = {}

    # The on_website_collect hook contributes templates, static files, elements,
    # and exposes the extension's resolved config as vars.theme_config
    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(templates)
        inputs.static_files.update(static_files)
        inputs.elements.update(elements)
        if resolved_config:
            inputs.vars["theme_config"] = resolved_config
        return inputs

    hooks["on_website_collect"] = collect

    # Load post_generate hook from hooks.py if present
    raw_post_generate = _load_raw_post_generate_from_directory(directory)
    if raw_post_generate is not None:

        def _post_generate_hook(args: GeneratePostHookArgs) -> None:
            raw_post_generate(args.config, resolved_config)

        hooks["on_generate_post"] = _post_generate_hook

    return Extension(
        name=name,
        hooks=hooks,
        config=resolved_config,
        schema=schema,
    )


def extension_from_entry_point(
    entry_point_name: str,
    config: dict[str, Any] | None = None,
) -> Extension:
    """Create an Extension from an entry point.

    The entry point should refer to a module that either:

    1. Exports an ``extension`` attribute containing an :class:`Extension`, or
    2. Is a package with ``templates/`` and optionally ``static/`` directories
       (i.e., a theme directory layout).

    Parameters
    ----------
    entry_point_name : str
        The name of the entry point in the ``"automata.themes"`` group.
    config : dict[str, Any] | None
        Optional configuration for the extension.

    Returns
    -------
    Extension
        The created Extension.

    """
    entry_points = metadata.entry_points()
    entry_point = entry_points.select(group="automata.themes")[entry_point_name]

    module = entry_point.load()
    if hasattr(module, "extension"):
        return cast(Extension, module.extension)
    elif hasattr(module, "theme"):
        # Backwards compatibility: if the module exports a Theme, we can't
        # convert it directly. Fall through to directory loading.
        pass

    root = importlib.resources.files(module)
    return extension_from_directory(entry_point_name, root, config=config)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _walk(
    node: Traversable,
    on_file,
    rel_parts: list[str] | None = None,
) -> None:
    """Walk a directory tree, passing file keys and entries to a handler."""
    if rel_parts is None:
        rel_parts = []

    for entry in node.iterdir():
        entry_parts = rel_parts + [entry.name]
        if any(part.startswith(".") for part in entry_parts):
            continue
        if entry.is_dir():
            _walk(entry, on_file, entry_parts)
        else:
            key = "/".join(entry_parts)
            on_file(key, entry)


def _load_python_module_from_theme_directory(
    directory: Traversable,
    filename: str,
    module_type: str,
    submodule_search_locations: list[str] | None = None,
):
    """Load a Python module from a file in a theme directory."""
    with importlib.resources.as_file(directory) as dir_path:
        digest = hashlib.sha256(str(dir_path).encode("utf-8")).hexdigest()[:12]
        module_name = f"automata.website.theme_{module_type}_{digest}"
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
            sys.modules.pop(module_name, None)
            raise ValueError(
                f"Error loading {module_type} from {file_path}: {e}"
            ) from e

    return module


def _load_elements_from_directory(
    elements_dir: Traversable,
) -> dict[str, type["Element"]]:
    """Load elements from a directory containing a Python package."""
    init_file = elements_dir / "__init__.py"
    if not init_file.is_file():
        return {}

    module = _load_python_module_from_theme_directory(
        directory=elements_dir,
        filename="__init__.py",
        module_type="elements",
        submodule_search_locations=[str(elements_dir)],
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


def _load_raw_post_generate_from_directory(
    hooks_dir: Traversable,
):
    """Load a raw post_generate callable from hooks.py in a theme directory.

    Returns the callable as defined in hooks.py, or None if not found.
    The caller is responsible for wrapping it to match the hook signature.
    """
    hooks_file = hooks_dir / "hooks.py"
    if not hooks_file.is_file():
        return None

    module = _load_python_module_from_theme_directory(
        directory=hooks_dir,
        filename="hooks.py",
        module_type="hooks",
    )

    if not hasattr(module, "post_generate"):
        return None

    post_generate = module.post_generate
    if not callable(post_generate):
        raise ValueError(
            f"post_generate in {hooks_file} must be callable, "
            f"got {type(post_generate)}."
        )

    return post_generate
