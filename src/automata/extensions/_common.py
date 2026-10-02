"""Helpers shared by the directory and entry point loaders."""

from __future__ import annotations

from typing import Any

import smartconfig
import smartconfig.exceptions
import smartconfig.types

from ..exceptions import Error
from ..util.resolution import resolve
from ._types import Extension


def resolve_config(
    name: str,
    config: dict[str, Any] | None,
    schema: "smartconfig.types.Schema | None",
) -> dict[str, Any]:
    """Validate and resolve extension config against a schema.

    An omitted config is treated as empty, so that schema defaults are applied
    and missing required keys are reported.

    """
    resolved = config if config is not None else {}
    if schema is not None:
        try:
            resolved = resolve(resolved, schema)
        except smartconfig.exceptions.ResolutionError as e:
            raise Error(f'Invalid configuration for extension "{name}": {e}') from e
    return resolved


def extension_from_module(
    module: Any,
    name: str,
    kind: str,
    config: dict[str, Any] | None,
    schema: smartconfig.types.Schema | None,
) -> Extension:
    """Build an Extension from a module exporting make_extension or extension."""
    if hasattr(module, "make_extension"):
        resolved_config = resolve_config(name, config, schema)
        extension = module.make_extension(resolved_config)
        if not isinstance(extension, Extension):
            raise Error(
                f'make_extension() for {kind} "{name}" did not return an Extension.'
            )
        return extension

    if hasattr(module, "extension"):
        if config is not None:
            raise Error(
                f'{kind.capitalize()} "{name}" does not accept configuration. To '
                f"accept configuration, its module should export "
                f"make_extension(config)."
            )
        extension = module.extension
        if not isinstance(extension, Extension):
            raise Error(
                f'The "extension" attribute of {kind} "{name}" is not an Extension.'
            )
        return extension

    raise Error(
        f'The module for {kind} "{name}" must export either '
        f"make_extension(config) or extension."
    )
