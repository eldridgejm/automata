"""Loading extensions from directories, optionally with Python (extension.py)."""

from __future__ import annotations

import importlib
import itertools
import json
import os
import pathlib
import sys
import types
from collections.abc import Callable
from importlib.resources.abc import Traversable
from typing import Any, get_origin, get_type_hints

import smartconfig
import smartconfig.exceptions
import smartconfig.types

from ..exceptions import Error
from ..hooks import WebsiteInputs
from ._common import extension_from_module, resolve_config
from ._types import Extension


def extension_from_directory(
    name: str,
    directory: Traversable,
    config: dict[str, Any] | None = None,
    require_templates: bool = True,
    dependencies: list[Extension] | None = None,
    project_directory: pathlib.Path | None = None,
    allow_python: bool = False,
) -> Extension:
    """Create an Extension from a directory.

    The directory must contain a ``templates/`` subdirectory with template
    files (unless *require_templates* is False). It may optionally contain:

    - ``static/`` --- static files served alongside the website.
    - ``schema.json`` --- JSON schema for validating extension config.
    - ``hooks/`` --- shell script hooks. Each file is named after an
      observer hook point (e.g., ``on_render_post``). The file content
      is the shell command; hook args are piped as JSON on stdin. The
      command runs in *project_directory* (if given), with the environment
      variables ``AUTOMATA_PROJECT_DIR`` and ``AUTOMATA_EXTENSION_DIR`` set.
    - ``extension.py`` --- Python code, imported only if *allow_python* is
      true. It must export ``make_extension(config)`` or ``extension``, as an
      entry point module would. Its hooks are combined with those of the
      files: for each hook point, the files' hook runs first, then the Python
      hook. The config schema comes from the module's ``schema`` or from
      ``schema.json``, but not both, and the validated config is passed to
      ``make_extension``. The extension keeps *name*; its config and
      dependencies are those of the Extension the module provides (plus
      *dependencies*). ``extension.py`` is imported as part of a new, uniquely
      named package each time, so it can import sibling modules relatively
      (``from .helpers import x``), extensions never collide, and changes are
      picked up when reloaded.

    Parameters
    ----------
    name : str
        A human-readable name for the extension.
    directory : Traversable
        The directory containing the extension's files. Must be a
        :class:`pathlib.Path` if *allow_python* is true and it contains
        ``extension.py``.
    config : dict[str, Any] | None
        Optional configuration for the extension.
    require_templates : bool
        If True (default), the directory must contain a ``templates/``
        subdirectory.
    dependencies : list[Extension] | None
        Extensions that must be applied before this one.
    project_directory : pathlib.Path | None
        The project root (the directory containing ``automata.yaml``). Script
        hooks run there, so relative paths in their commands are relative to
        the project. If None, they run in the current working directory.
    allow_python : bool
        Whether to import ``extension.py`` if present. Default False, so that a
        package calling this on its own files never imports itself. Directory
        paths in ``automata.yaml`` are loaded with this set to True.

    Returns
    -------
    Extension
        The created Extension.

    Raises
    ------
    automata.exceptions.Error
        If the directory is invalid, ``extension.py`` cannot be imported or
        exports neither ``make_extension`` nor ``extension``, a schema is
        defined in both ``extension.py`` and ``schema.json``, or the
        configuration is invalid.

    """
    files = _extension_from_files(
        name,
        directory,
        config=config,
        require_templates=require_templates,
        dependencies=dependencies,
        project_directory=project_directory,
    )

    if not allow_python or not (directory / "extension.py").is_file():
        return files

    if not isinstance(directory, pathlib.Path):
        raise Error(
            f'Cannot import extension.py of extension "{name}": "{directory}" is '
            f"not a filesystem path."
        )

    module = _import_local_extension(name, directory)
    module_schema = getattr(module, "schema", None)
    if module_schema is not None and files.schema is not None:
        raise Error(
            f'Extension "{name}" defines a config schema in both extension.py and '
            f"schema.json. Define it in one place."
        )
    schema = module_schema if module_schema is not None else files.schema

    python = extension_from_module(module, name, "extension", config, schema)

    hooks = dict(files.hooks)
    for hook_name, fn in python.hooks.items():
        hooks[hook_name] = (
            _chain_hooks(hook_name, hooks[hook_name], fn) if hook_name in hooks else fn
        )

    return Extension(
        name=name,
        hooks=hooks,
        config=python.config,
        schema=schema,
        dependencies=[*files.dependencies, *python.dependencies],
    )


def _extension_from_files(
    name: str,
    directory: Traversable,
    config: dict[str, Any] | None = None,
    require_templates: bool = True,
    dependencies: list[Extension] | None = None,
    project_directory: pathlib.Path | None = None,
) -> Extension:
    """Create an Extension from a directory's files (no Python is imported).

    The directory must contain a ``templates/`` subdirectory with template
    files (unless *require_templates* is False). It may optionally contain:

    - ``static/`` --- static files served alongside the website.
    - ``schema.json`` --- JSON schema for validating extension config.
    - ``hooks/`` --- shell script hooks. Each file is named after an
      observer hook point (e.g., ``on_render_post``). The file content
      is the shell command; hook args are piped as JSON on stdin. The
      command runs in *project_directory* (if given), with the environment
      variables ``AUTOMATA_PROJECT_DIR`` and ``AUTOMATA_EXTENSION_DIR`` set.

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
    project_directory : pathlib.Path | None
        The project root (the directory containing ``automata.yaml``). Script
        hooks run there, so relative paths in their commands are relative to
        the project. If None, they run in the current working directory.

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

    resolved_config = resolve_config(name, config, schema)

    # Build the hooks dict
    ext_hooks: dict[str, Any] = {}

    # The on_render_collect hook contributes templates and static files
    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(templates)
        inputs.static_files.update(static_files)
        return inputs

    ext_hooks["on_render_collect"] = collect

    # Load script hooks from hooks/ directory
    hooks_dir = directory / "hooks"
    if hooks_dir.is_dir():
        ext_hooks.update(
            _load_script_hooks(name, hooks_dir, directory, project_directory)
        )

    return Extension(
        name=name,
        hooks=ext_hooks,
        config=resolved_config,
        schema=schema,
        dependencies=dependencies or [],
    )


_local_extension_counter = itertools.count()


def _import_local_extension(name: str, directory: pathlib.Path) -> Any:
    """Import a local extension's extension.py as part of a fresh package."""
    package_name = f"_automata_local_extension_{next(_local_extension_counter)}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(directory)]
    sys.modules[package_name] = package

    try:
        return importlib.import_module(f"{package_name}.extension")
    except Exception as e:
        raise Error(
            f'Could not import extension.py of extension "{name}" '
            f'("{directory}"): {type(e).__name__}: {e}'
        ) from e


def _chain_hooks(hook_name: str, first: Callable, second: Callable) -> Callable:
    """Combine two callables for the same hook point, running *first* first."""
    from ..hooks import Hooks
    from ..hooks._internals import PipelineHook

    if get_origin(get_type_hints(Hooks)[hook_name]) is PipelineHook:

        def pipeline(value: Any) -> Any:
            return second(first(value))

        return pipeline

    def observer(args: Any) -> None:
        first(args)
        second(args)

    return observer


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


def _load_script_hooks(
    extension_name: str,
    hooks_dir: Traversable,
    extension_directory: Traversable,
    project_directory: pathlib.Path | None,
) -> dict[str, Callable]:
    """Load shell script hooks from a hooks/ directory.

    Each file in the directory is named after an observer hook point
    (e.g., ``on_render_post``, ``on_build_artifact_success``). The file content
    is the shell command to run. Hook args are serialized as JSON and
    piped to the command on stdin.

    Commands run in *project_directory* (or the current working directory if
    it is None), with ``AUTOMATA_EXTENSION_DIR`` and (if known)
    ``AUTOMATA_PROJECT_DIR`` set in their environment.

    Returns a dict mapping hook point names to callables.
    """
    from ..hooks import Hooks
    from ..hooks._internals import ObserverHook, _default_serializer, run_shell_hook

    observer_hooks = sorted(
        name
        for name, hint in get_type_hints(Hooks).items()
        if get_origin(hint) is ObserverHook
    )

    cwd = None if project_directory is None else project_directory.absolute()
    env = {**os.environ, "AUTOMATA_EXTENSION_DIR": str(extension_directory)}
    if cwd is not None:
        env["AUTOMATA_PROJECT_DIR"] = str(cwd)

    script_hooks: dict[str, Callable] = {}

    for entry in hooks_dir.iterdir():
        if entry.is_dir() or entry.name.startswith("."):
            continue

        hook_name = entry.name
        if hook_name not in observer_hooks:
            raise Error(
                f'Script hook "{hook_name}" in "{hooks_dir}" is not an observer '
                f"hook point. Script hook files must be named after one of: "
                f"{', '.join(observer_hooks)}."
            )
        command = entry.read_text().strip()
        if not command:
            continue

        def _make_hook(cmd: str, description: str) -> Callable:
            def _hook(args: Any) -> None:
                run_shell_hook(
                    cmd,
                    _default_serializer(args),
                    description=description,
                    cwd=None if cwd is None else str(cwd),
                    env=env,
                )

            return _hook

        script_hooks[hook_name] = _make_hook(
            command, f'Script hook "{hook_name}" of extension "{extension_name}"'
        )

    return script_hooks
