"""Extension: a collection of hooks that customize automata's behavior."""

from __future__ import annotations

import dataclasses
import importlib.metadata as metadata
import importlib.resources
import json
import subprocess
from collections.abc import Callable
from importlib.resources.abc import Traversable
from typing import Any, cast

import smartconfig.exceptions
import smartconfig.types

from .exceptions import Error
from .hooks import WebsiteInputs


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
    """Create an Extension from a directory.

    The directory must contain a ``templates/`` subdirectory with template
    files (unless *require_templates* is False). It may optionally contain:

    - ``static/`` --- static files served alongside the website.
    - ``schema.json`` --- JSON schema for validating extension config.
    - ``hooks/`` --- shell script hooks. Each file is named after an
      observer hook point (e.g., ``on_generate_post``). The file content
      is the shell command; hook args are piped as JSON on stdin.

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
        _walk(
            templates_dir,
            lambda key, entry: templates.__setitem__(key, entry.read_text()),
        )
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

    # Load script hooks from hooks/ directory
    hooks_dir = directory / "hooks"
    if hooks_dir.is_dir():
        ext_hooks.update(_load_script_hooks(hooks_dir))

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
    entry_points = metadata.entry_points().select(group="automata.themes")
    if entry_point_name not in entry_points.names:
        available = ", ".join(sorted(entry_points.names)) or "none"
        raise Error(
            f'Unknown extension "{entry_point_name}". Available: {available}. '
            f"To load an extension from a directory, give a path containing a "
            f'slash (e.g., "./{entry_point_name}").'
        )
    entry_point = entry_points[entry_point_name]

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


def _load_script_hooks(hooks_dir: Traversable) -> dict[str, Callable]:
    """Load shell script hooks from a hooks/ directory.

    Each file in the directory is named after an observer hook point
    (e.g., ``on_generate_post``, ``on_build_success``). The file content
    is the shell command to run. Hook args are serialized as JSON and
    piped to the command on stdin.

    Returns a dict mapping hook point names to callables.
    """
    from .hooks._internals import _default_serializer

    script_hooks: dict[str, Callable] = {}

    for entry in hooks_dir.iterdir():
        if entry.is_dir() or entry.name.startswith("."):
            continue

        hook_name = entry.name
        command = entry.read_text().strip()
        if not command:
            continue

        def _make_hook(cmd: str) -> Callable:
            def _hook(args: Any) -> None:
                payload = _default_serializer(args)
                subprocess.run(cmd, input=payload, shell=True, text=True)

            return _hook

        script_hooks[hook_name] = _make_hook(command)

    return script_hooks
