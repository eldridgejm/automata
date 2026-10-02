"""Helpers shared by the directory and entry point loaders."""

from __future__ import annotations

from typing import Any

import smartconfig
import smartconfig.exceptions
import smartconfig.types

from ..exceptions import Error
from ..util.resolution import describe_config_error, resolve
from ._types import Extension


class ExtensionConfigError(Error):
    """An extension's configuration does not match its schema.

    The cause is kept so that the caller, which knows where the configuration
    was written, can name the file and the full keypath.

    """

    def __init__(self, name: str, cause: smartconfig.exceptions.ResolutionError):
        self.name = name
        self.cause = cause
        super().__init__(f'Invalid configuration for extension "{name}": {cause}')


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
            raise ExtensionConfigError(name, e) from e
    return resolved


def _check_module_schema(module: Any, name: str, kind: str) -> None:
    """Check the config schema a module declares, blaming the module if it's wrong.

    Without this, a mistake in the schema is reported as a mistake in the
    user's configuration (e.g. a misspelled "required_keys" makes a correct
    key "unexpected").

    """
    schema = getattr(module, "schema", None)
    if schema is None:
        return

    if not hasattr(module, "make_extension"):
        raise Error(
            f'{kind.capitalize()} "{name}" defines a config schema but no '
            f"make_extension(config), so the schema is never used. Export "
            f"make_extension(config), or remove the schema."
        )

    try:
        smartconfig.validate_schema(schema)
    except smartconfig.exceptions.InvalidSchemaError as e:
        # a module imported from a file (e.g. extension.py) knows its file
        where = getattr(module, "__file__", None) or f'The module of {kind} "{name}"'
        raise Error(
            describe_config_error(e.reason, ("schema", *e.keypath), file=where)
        ) from None


def extension_from_module(
    module: Any,
    name: str,
    kind: str,
    config: dict[str, Any] | None,
    schema: smartconfig.types.Schema | None,
) -> Extension:
    """Build an Extension from a module exporting make_extension or extension."""
    _check_module_schema(module, name, kind)

    if hasattr(module, "make_extension"):
        resolved_config = resolve_config(name, config, schema)
        try:
            extension = module.make_extension(resolved_config)
        except Error:
            raise
        except Exception as e:
            raise Error(
                f'make_extension() of {kind} "{name}" failed: {type(e).__name__}: {e}'
            ) from e
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
