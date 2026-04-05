"""Extension: a collection of hooks that customize automata's behavior."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.metadata as metadata
import importlib.resources
import importlib.util
import json
import sys
from collections.abc import Callable
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING, Any, cast

import smartconfig.exceptions
import smartconfig.types

from .hooks import GeneratePostHookArgs, WebsiteInputs

if TYPE_CHECKING:
    from .website._elements import Element


@dataclasses.dataclass
class Extension:
    """A collection of hooks that customize automata's behavior.

    An extension is the fundamental unit of customization in automata. It maps
    hook point names to callables that are registered when the extension is
    applied. For example, a theme extension registers a hook on
    ``on_website_collect`` to provide templates, static files, and elements.

    Extensions can declare *dependencies* — other extensions that are
    automatically applied first.

    Attributes
    ----------
    name : str
        A human-readable name for the extension.
    hooks : dict[str, Callable]
        A mapping of hook point names to callables. Each key must correspond
        to a hook defined on :class:`automata.hooks.Hooks`.
    config : dict[str, Any]
        Optional configuration for the extension.
    schema : smartconfig.types.Schema | None
        Optional schema for validating *config*.
    dependencies : list[Extension]
        Extensions that must be applied before this one.

    """

    name: str
    hooks: dict[str, Callable]
    config: dict[str, Any] = dataclasses.field(default_factory=dict)
    schema: smartconfig.types.Schema | None = None
    dependencies: list[Extension] = dataclasses.field(default_factory=list)


def apply_extension(
    extension: Extension,
    hooks: object,
    priority: int = 0,
    _applied: set[str] | None = None,
) -> None:
    """Register all of an extension's hooks onto a hooks instance.

    Dependencies are applied first, and each extension is applied at most
    once (tracked by name).

    Parameters
    ----------
    extension : Extension
        The extension whose hooks should be registered.
    hooks : object
        A hooks instance (e.g., :class:`automata.hooks.Hooks`) with hook
        point attributes.
    priority : int
        The priority at which to register each hook. Lower values run first.

    Raises
    ------
    AttributeError
        If *hooks* does not have a hook point matching a key in
        *extension.hooks*.

    """
    if _applied is None:
        _applied = set()

    if extension.name in _applied:
        return

    for dep in extension.dependencies:
        apply_extension(dep, hooks, priority=priority, _applied=_applied)

    _applied.add(extension.name)

    for hook_name, fn in extension.hooks.items():
        hook_point = getattr(hooks, hook_name)
        hook_point.register(priority=priority)(fn)


# ---------------------------------------------------------------------------
# Loading extensions from directories and entry points
# ---------------------------------------------------------------------------


def _resolve_config(
    config: dict[str, Any] | None,
    schema: "smartconfig.types.Schema | None",
) -> dict[str, Any]:
    """Validate and resolve extension config against a schema."""
    import smartconfig

    resolved = config if config is not None else {}
    if schema is not None and config is not None:
        try:
            resolved = smartconfig.resolve(resolved, schema)
        except smartconfig.exceptions.ResolutionError as e:
            raise ValueError(f"Invalid extension configuration: {e}")
    return resolved


def extension_from_directory(
    name: str,
    directory: Traversable,
    config: dict[str, Any] | None = None,
    require_templates: bool = True,
    dependencies: list[Extension] | None = None,
) -> Extension:
    """Create an Extension from a theme directory.

    The directory must contain a ``templates/`` subdirectory with template
    files (unless *require_templates* is False). It may optionally contain
    a ``static/`` subdirectory with static files, a ``schema.json`` for
    config validation, and a ``hooks.py`` file.

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
    dependencies : list[Extension] | None
        Extensions that must be applied before this one.

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

    if templates_dir.is_dir():
        _walk(templates_dir, lambda key, entry: templates.__setitem__(key, entry.read_text()))
    if static_dir.is_dir():
        _walk(static_dir, lambda key, entry: static_files.__setitem__(key, entry))

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

    resolved_config = _resolve_config(config, schema)

    # Build the hooks dict
    ext_hooks: dict[str, Any] = {}

    # The on_website_collect hook contributes templates, static files,
    # and exposes the extension's resolved config as vars.theme_config
    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(templates)
        inputs.static_files.update(static_files)
        if resolved_config:
            inputs.vars["theme_config"] = resolved_config
        return inputs

    ext_hooks["on_website_collect"] = collect

    # Load post_generate hook from hooks.py if present
    raw_post_generate = _load_raw_post_generate(directory)
    if raw_post_generate is not None:

        def _post_generate_hook(args: GeneratePostHookArgs) -> None:
            raw_post_generate(args.build_directory, resolved_config)

        ext_hooks["on_generate_post"] = _post_generate_hook

    return Extension(
        name=name,
        hooks=ext_hooks,
        config=resolved_config,
        schema=schema,
        dependencies=dependencies or [],
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
        ext = cast(Extension, module.extension)
        resolved_config = _resolve_config(config, ext.schema)
        ext.config = resolved_config
        return ext
    elif hasattr(module, "theme"):
        # Backwards compatibility: fall through to directory loading.
        pass

    # Check if the module declares dependencies
    deps: list[Extension] = []
    if hasattr(module, "dependencies"):
        deps = module.dependencies

    root = importlib.resources.files(module)
    return extension_from_directory(
        entry_point_name, root, config=config, dependencies=deps
    )


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


def _load_python_module(
    directory: Traversable,
    filename: str,
    module_type: str,
    submodule_search_locations: list[str] | None = None,
):
    """Load a Python module from a file in a directory."""
    with importlib.resources.as_file(directory) as dir_path:
        digest = hashlib.sha256(str(dir_path).encode("utf-8")).hexdigest()[:12]
        module_name = f"automata.ext_{module_type}_{digest}"
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


def _load_raw_post_generate(
    hooks_dir: Traversable,
):
    """Load a raw post_generate callable from hooks.py in a directory.

    Returns the callable as defined in hooks.py, or None if not found.
    The caller is responsible for wrapping it to match the hook signature.
    """
    hooks_file = hooks_dir / "hooks.py"
    if not hooks_file.is_file():
        return None

    module = _load_python_module(
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
