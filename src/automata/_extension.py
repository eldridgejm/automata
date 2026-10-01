"""Extension: a collection of hooks that customize automata's behavior."""

from __future__ import annotations

import dataclasses
import importlib.metadata as metadata
import json
import subprocess
from collections.abc import Callable, Iterable
from importlib.resources.abc import Traversable
from typing import Any

import smartconfig.exceptions
import smartconfig.types

from .exceptions import Error
from .hooks import GenerateHooks, WebsiteInputs

# entry point groups: themes are set with website.theme, extensions are listed
# under extensions:
THEMES_GROUP = "automata.themes"
EXTENSIONS_GROUP = "automata.extensions"


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


def apply_extensions(
    extensions: Iterable[Extension],
    hooks: object,
    priority: int = 0,
) -> None:
    """Register several extensions' hooks onto a hooks instance.

    Like :func:`apply_extension`, but each extension (including shared
    dependencies) is applied at most once across all of *extensions*.

    """
    applied: set[str] = set()
    for extension in extensions:
        apply_extension(extension, hooks, priority=priority, _applied=applied)


def all_extensions(extensions: Iterable[Extension]) -> dict[str, Extension]:
    """Return the given extensions and their dependencies, keyed by name.

    Raises
    ------
    automata.exceptions.Error
        If two different extensions have the same name.

    """
    found: dict[str, Extension] = {}

    def visit(extension: Extension) -> None:
        existing = found.get(extension.name)
        if existing is extension:
            return
        if existing is not None:
            raise Error(
                f'Two different extensions are named "{extension.name}". '
                f"Extension names must be unique."
            )
        found[extension.name] = extension
        for dep in extension.dependencies:
            visit(dep)

    for extension in extensions:
        visit(extension)

    return found


def check_theme(theme: Extension) -> None:
    """Check that an extension can serve as a theme.

    A theme (together with its dependencies) must provide a ``page.html``
    template.

    Raises
    ------
    automata.exceptions.Error
        If the theme does not provide ``page.html``.

    """
    hooks = GenerateHooks()
    apply_extension(theme, hooks)
    inputs = hooks.on_website_collect(WebsiteInputs())
    if "page.html" not in inputs.templates:
        raise Error(f'Theme "{theme.name}" does not provide a "page.html" template.')


# ---------------------------------------------------------------------------
# Loading extensions from directories and entry points
# ---------------------------------------------------------------------------


def _resolve_config(
    name: str,
    config: dict[str, Any] | None,
    schema: "smartconfig.types.Schema | None",
) -> dict[str, Any]:
    """Validate and resolve extension config against a schema.

    An omitted config is treated as empty, so that schema defaults are applied
    and missing required keys are reported.

    """
    import smartconfig

    resolved = config if config is not None else {}
    if schema is not None:
        try:
            resolved = smartconfig.resolve(resolved, schema)
        except smartconfig.exceptions.ResolutionError as e:
            raise Error(f'Invalid configuration for extension "{name}": {e}') from e
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
        raise Error(
            f'Extension directory "{directory}" does not exist or is not a directory.'
        )

    templates_dir = directory / "templates"
    if require_templates and not templates_dir.is_dir():
        raise Error(
            f'Extension directory "{directory}" must contain a "templates" directory.'
        )

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
            raise Error(f"Invalid JSON in schema.json: {e}") from e
        except smartconfig.exceptions.InvalidSchemaError as e:
            raise Error(f"Theme configuration schema is invalid: {e}") from e

    resolved_config = _resolve_config(name, config, schema)

    # Build the hooks dict
    ext_hooks: dict[str, Any] = {}

    # The on_website_collect hook contributes templates and static files
    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(templates)
        inputs.static_files.update(static_files)
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
    *,
    group: str = EXTENSIONS_GROUP,
) -> Extension:
    """Create an Extension from an entry point.

    The entry point should refer to a module that exports either:

    1. ``make_extension(config) -> Extension``, a factory called with the
       extension's validated configuration. If the module also exports
       ``schema``, the configuration is validated against it (and defaults
       applied) before the factory is called. Each call builds a new
       Extension, so its hooks can safely close over *config*.
    2. ``extension``, an :class:`Extension` that takes no configuration.

    Parameters
    ----------
    entry_point_name : str
        The name of the entry point within *group*.
    config : dict[str, Any] | None
        Optional configuration for the extension.
    group : str
        The entry point group: :data:`EXTENSIONS_GROUP` (the default) or
        :data:`THEMES_GROUP`.

    Returns
    -------
    Extension
        The created Extension.

    Raises
    ------
    automata.exceptions.Error
        If the entry point is not found, the module exports neither
        ``make_extension`` nor ``extension``, or the configuration is invalid.

    """
    all_entry_points = metadata.entry_points()
    entry_points = all_entry_points.select(group=group)
    kind = "theme" if group == THEMES_GROUP else "extension"

    if entry_point_name not in entry_points.names:
        message = f'Unknown {kind} "{entry_point_name}".'
        if group == EXTENSIONS_GROUP and entry_point_name in (
            all_entry_points.select(group=THEMES_GROUP).names
        ):
            message += (
                f' "{entry_point_name}" is a theme; set it with website.theme, '
                f"not under extensions."
            )
        elif group == THEMES_GROUP and entry_point_name in (
            all_entry_points.select(group=EXTENSIONS_GROUP).names
        ):
            message += (
                f' "{entry_point_name}" is an extension, not a theme; list it '
                f"under extensions."
            )
        else:
            available = ", ".join(sorted(entry_points.names)) or "none"
            message += (
                f" Available {kind}s: {available}. To load an extension from a "
                f"directory, give a path containing a slash "
                f'(e.g., "./{entry_point_name}").'
            )
        raise Error(message)

    module = entry_points[entry_point_name].load()

    if hasattr(module, "make_extension"):
        schema = getattr(module, "schema", None)
        resolved_config = _resolve_config(entry_point_name, config, schema)
        extension = module.make_extension(resolved_config)
        if not isinstance(extension, Extension):
            raise Error(
                f'make_extension() for {kind} "{entry_point_name}" did not return '
                f"an Extension."
            )
        return extension

    if hasattr(module, "extension"):
        if config is not None:
            raise Error(
                f'{kind.capitalize()} "{entry_point_name}" does not accept '
                f"configuration. To accept configuration, its module should "
                f"export make_extension(config)."
            )
        extension = module.extension
        if not isinstance(extension, Extension):
            raise Error(
                f'The "extension" attribute of {kind} "{entry_point_name}" is not '
                f"an Extension."
            )
        return extension

    raise Error(
        f'The module for {kind} "{entry_point_name}" must export either '
        f"make_extension(config) or extension."
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
