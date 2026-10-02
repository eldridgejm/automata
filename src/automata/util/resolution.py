"""Utilities for configuration resolution."""

import datetime
import types
import typing
from importlib.resources.abc import Traversable
from pathlib import Path

import smartconfig
import smartconfig.converters
import smartconfig.exceptions
import smartconfig.stdlib.datetime

from ..exceptions import Error
from .yaml import parse_yaml

T = typing.TypeVar("T")
P = typing.TypeVar("P", bound=smartconfig.Prototype)


def string_or_template_string(**extras: typing.Any) -> smartconfig.types.DynamicSchema:
    """Return a dynamic schema that accepts a plain string or a __template__ dict.

    Additional schema entries (e.g., nullable, default) can be passed as keyword
    arguments and will be included in the returned schema when the value is not
    a template.

    """

    def schema(
        config: smartconfig.types.Configuration, keypath: typing.Any
    ) -> smartconfig.types.Schema:
        if isinstance(config, dict) and "__template__" in config:
            return {
                "type": "dict",
                "required_keys": {
                    "__template__": {"type": "any"},
                },
            }
        return {"type": "string", **extras}

    return schema


def unwrap_templates(
    config: smartconfig.types.Configuration,
    preserve: typing.Callable[[smartconfig.types.Configuration], bool] | None = None,
) -> smartconfig.types.Configuration:
    """Recursively unwrap ``{"__template__": ...}`` dicts to plain strings.

    After smartconfig resolution, fields that used the ``__template__`` function
    are represented as single-key dicts ``{"__template__": "<string>"}``. This
    function walks a configuration tree and replaces each such dict with the
    inner string value.

    Parameters
    ----------
    config : smartconfig.types.Configuration
        The configuration to process.
    preserve : Callable[[smartconfig.types.Configuration], bool] | None
        A function that takes a configuration node and returns True if it should be
        left unchanged. This can be used to selectively preserve certain template
        dicts. If None, all template dicts will be unwrapped.

    Returns
    -------
    smartconfig.types.Configuration
        The processed configuration with template dicts converted to strings.

    """
    if preserve is not None:
        if preserve(config):
            return config

    if isinstance(config, dict) and len(config) == 1 and "__template__" in config:
        return config["__template__"]
    elif isinstance(config, dict):
        return {k: unwrap_templates(v, preserve) for k, v in config.items()}
    elif isinstance(config, list):
        return [unwrap_templates(item, preserve) for item in config]
    else:
        return config


def resolve_for_each(
    items: typing.Sequence[T],
    config: smartconfig.types.Configuration,
    schema: smartconfig.types.Schema,
    loop_variable: str = "item",
    vars: dict | None = None,
    functions: smartconfig.types.FunctionMapping | None = None,
    fixup: typing.Callable[
        [smartconfig.types.Configuration, T], smartconfig.types.Configuration
    ]
    | None = None,
) -> list[smartconfig.types.Configuration]:
    """Resolves a configuration once for each item in a sequence.

    Parameters
    ----------
    items : typing.Sequence
        The sequence of items to iterate over.
    config : smartconfig.types.Configuration
        The configuration to resolve for each item. This configuration can include
        references to the current item using the special variable `{{ item }}`.
    loop_variable : str, optional
        The variable name that will be used to represent the current item on each
        iteration.
    vars : dict | None, optional
        Additional variables to include in the resolution context. If None, no
        additional variables are included.
    functions : smartconfig.types.FunctionMapping | None, optional
        A mapping of custom functions to use during resolution. If None, the
        default functions from smartconfig will be used.
    fixup : Callable[
                [smartconfig.types.Configuration, T], smartconfig.types.Configuration
            ] | None, optional
        An optional function that takes in the resolved configuration for each item
        and the item itself, then performs any additional modifications before the
        configuration is added to the final list.

    Returns
    -------
    list
        A list of resolved configurations, one for each item in the input sequence.

    """
    if vars is None:
        vars = {}

    if functions is None:
        functions = smartconfig.DEFAULT_FUNCTIONS

    resolved_configs = []

    for item in items:
        global_vars = {**vars, loop_variable: item}
        resolved_config = resolve(
            config,
            schema,
            global_variables=global_vars,
            functions=functions,
        )

        if fixup is not None:
            resolved_config = fixup(resolved_config, item)

        resolved_configs.append(resolved_config)

    return resolved_configs


def format_keypath(keypath: typing.Sequence[typing.Any]) -> str:
    """A keypath as dotted text, quoting keys that contain dots.

    ``("artifacts", "homework.pdf", "ready")`` becomes
    ``artifacts."homework.pdf".ready``.
    """
    parts = []
    for key in keypath:
        text = str(key)
        parts.append(f'"{text}"' if "." in text else text)
    return ".".join(parts)


def describe_config_error(
    reason: str,
    keypath: typing.Sequence[typing.Any] = (),
    file: Path | Traversable | None = None,
) -> str:
    """A configuration error as ``FILE: KEYPATH: REASON``.

    The file and keypath are left out when not known (or empty).
    """
    parts = [] if file is None else [str(file)]
    if keypath:
        parts.append(format_keypath(keypath))
    parts.append(reason)
    return ": ".join(parts)


def _parse_date_phrase(value: str) -> datetime.date | datetime.datetime:
    """Parse a date phrase like "7 days after 2026-01-01 at 23:59:00".

    Uses the same syntax as smartconfig's ``__datetime.parse__`` function.
    """
    args = types.SimpleNamespace(input=value, keypath=())
    try:
        return smartconfig.stdlib.datetime.parse(args)  # type: ignore[arg-type]
    except smartconfig.exceptions.ResolutionError:
        raise smartconfig.exceptions.ConversionError(
            f'Cannot read "{value}" as a date or a date phrase (like '
            f'"3 days after 2026-01-01", "first monday, wednesday after '
            f'2026-01-01", or "2026-01-01 at 23:59:00").'
        ) from None


def _date_or_phrase(value: typing.Any) -> datetime.date:
    """Convert to a date, reading strings that are not ISO dates as phrases."""
    try:
        return smartconfig.converters.date(value)
    except smartconfig.exceptions.ConversionError:
        if not isinstance(value, str):
            raise
    result = _parse_date_phrase(value)
    return result.date() if isinstance(result, datetime.datetime) else result


def _datetime_or_phrase(value: typing.Any) -> datetime.datetime:
    """Convert to a datetime, reading strings that are not ISO as phrases."""
    try:
        return smartconfig.converters.datetime(value)
    except smartconfig.exceptions.ConversionError:
        if not isinstance(value, str):
            raise
    result = _parse_date_phrase(value)
    if isinstance(result, datetime.datetime):
        return result
    return datetime.datetime.combine(result, datetime.time())


# The converters automata uses for every resolution: smartconfig's defaults,
# except that date and datetime fields also accept date phrases, so
# __datetime.parse__ is not needed for them.
CONVERTERS: dict[str, typing.Callable] = {
    **smartconfig.DEFAULT_CONVERTERS,
    "date": _date_or_phrase,
    "datetime": _datetime_or_phrase,
}


@typing.overload
def resolve(
    config: smartconfig.types.Configuration,
    schema: type[P],
    base_path: Path | None = None,
    **kwargs: typing.Any,
) -> P: ...


@typing.overload
def resolve(
    config: smartconfig.types.ConfigurationDict,
    schema: smartconfig.types.Schema,
    base_path: Path | None = None,
    **kwargs: typing.Any,
) -> dict: ...


@typing.overload
def resolve(
    config: smartconfig.types.ConfigurationList,
    schema: smartconfig.types.Schema,
    base_path: Path | None = None,
    **kwargs: typing.Any,
) -> list: ...


@typing.overload
def resolve(
    config: smartconfig.types.ConfigurationValue,
    schema: smartconfig.types.Schema,
    base_path: Path | None = None,
    **kwargs: typing.Any,
) -> typing.Any: ...


def resolve(
    config: smartconfig.types.Configuration,
    schema: smartconfig.types.Schema | type[P],
    base_path: Path | None = None,
    **kwargs: typing.Any,
) -> typing.Any:
    """Resolve a configuration using smartconfig with built-in functions.

    This function wraps smartconfig.resolve() and automatically provides built-in
    functions like 'include' for common operations.

    Fields of type ``date`` or ``datetime`` accept date phrases as well as ISO
    strings and date objects, e.g. ``"7 days before ${this.metadata.due} at
    00:00:00"`` or ``"first tuesday, thursday after 2026-09-24"`` (the syntax of
    ``__datetime.parse__``). ISO strings are read exactly as before; phrases are
    only tried for strings that are not ISO dates.

    Parameters
    ----------
    config : smartconfig.types.Configuration
        The configuration to resolve (typically a dict loaded from YAML).
    schema : smartconfig.types.Schema | type
        The schema to validate and resolve against. Can be a schema dictionary
        or a Prototype class.
    base_path : Path | None
        The base directory for resolving relative paths in __include__ directives.
        If None, the include function will not be available. Default: None.
    **kwargs : Any
        Additional keyword arguments to pass to the underlying resolver
        (e.g., global_variables, etc.). Note that if 'functions' is provided,
        it will be merged with the built-in functions.

    Returns
    -------
    Any
        The resolved configuration.

    Raises
    ------
    smartconfig.exceptions.ResolutionError
        If the configuration cannot be resolved against the schema.

    """
    # Set up built-in functions
    functions = dict(smartconfig.DEFAULT_FUNCTIONS)

    if base_path is not None:

        def include(args: smartconfig.types.FunctionArgs) -> typing.Any:
            """Include another YAML file and return its contents."""
            schema = {"type": "string"}
            include_path = resolve(args.input, schema)
            include_path = typing.cast(str, include_path)

            include_path = base_path / include_path
            try:
                yaml_content = include_path.read_text()
            except FileNotFoundError:
                raise Error(f'Included file "{include_path}" not found.') from None
            return parse_yaml(yaml_content, source=include_path)

        functions["include"] = include

    # Merge with any user-provided functions
    if "functions" in kwargs:
        user_functions = kwargs.pop("functions")
        functions.update(user_functions)

    kwargs.setdefault("converters", CONVERTERS)
    return smartconfig.resolve(config, schema, functions=functions, **kwargs)
