"""Utilities for configuration resolution."""

import typing
from collections.abc import Mapping

import smartconfig

from .. import materials

T = typing.TypeVar("T")


def unwrap_raw_strings(
    config: smartconfig.types.Configuration,
    preserve: typing.Callable[[smartconfig.types.Configuration], bool] | None = None,
) -> smartconfig.types.Configuration:
    """Recursively convert RawString instances to regular strings in a config dict.

    Parameters
    ----------
    config : smartconfig.types.Configuration
        The configuration to process.
    preserve : Callable[[smartconfig.types.Configuration], bool] | None
        A function that takes a configuration node and returns True if it should be
        left unchanged. This can be used to selectively preserve certain instances
        of RawString. If None, all RawString instances will be converted.

    Returns
    -------
    smartconfig.types.Configuration
        The processed configuration with RawString instances converted to strings.

    """
    if preserve is not None:
        if preserve(config):
            return config

    if isinstance(config, smartconfig.types.RawString):
        return str(config)
    elif isinstance(config, dict):
        return {k: unwrap_raw_strings(v, preserve) for k, v in config.items()}
    elif isinstance(config, list):
        return [unwrap_raw_strings(item, preserve) for item in config]
    else:
        return config


def resolve_for_each(
    items: typing.Sequence[T],
    config: smartconfig.types.Configuration,
    schema: smartconfig.types.Schema,
    loop_variable: str = "item",
    vars: dict | None = None,
    functions: Mapping[str, typing.Callable | smartconfig.types.Function] | None = None,
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
    functions : Mapping[str, Callable | smartconfig.types.Function] | None, optional
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
        resolved_config = smartconfig.resolve(
            config,
            schema,
            global_variables=global_vars,
            functions=functions,
        )

        if fixup is not None:
            resolved_config = fixup(resolved_config, item)

        resolved_configs.append(resolved_config)

    return resolved_configs


def resolve_for_each_publication(
    publication: typing.Sequence[materials.Publication],
    config: smartconfig.types.Configuration,
    schema: smartconfig.types.Schema,
    vars: dict | None = None,
    loop_variable: str = "publication",
    functions: Mapping[str, typing.Callable | smartconfig.types.Function] | None = None,
    fixup: typing.Callable[
        [smartconfig.types.Configuration, materials.Publication],
        smartconfig.types.Configuration,
    ]
    | None = None,
) -> list[smartconfig.types.Configuration]:
    """Resolves a configuration once for each publication in a sequence.

    This is a specialized version of resolve_for_each that adds a custom
    `use_metadata` function for convenient access to publication metadata.

    Parameters
    ----------
    publication : typing.Sequence[materials.Publication]
        The sequence of publications to iterate over.
    config : smartconfig.types.Configuration
        The configuration to resolve for each publication. Can include
        references to the current publication via the loop variable
        (default: `{{ publication }}`).
    schema : smartconfig.types.Schema
        The schema to use for validation during resolution.
    vars : dict | None, optional
        Additional variables to include in the resolution context. If None,
        no additional variables are included.
    loop_variable : str, optional
        The variable name that will be used to represent the current publication
        on each iteration. Default: "publication".
    functions : Mapping[str, Callable | smartconfig.types.Function] | None, optional
        A mapping of custom functions to use during resolution. If None, the
        default functions from smartconfig will be used, plus an added
        `use_metadata` function for accessing publication metadata.
    fixup : Callable[
                [smartconfig.types.Configuration, materials.Publication],
                smartconfig.types.Configuration
            ] | None, optional
        An optional function that takes in the resolved configuration for each
        publication and the publication itself, then performs any additional
        modifications before the configuration is added to the final list.

    Returns
    -------
    list[smartconfig.types.Configuration]
        A list of resolved configurations, one for each publication in the
        input sequence.

    Notes
    -----
    The `use_metadata` function takes in a single argument (the name of a metadata
    key) and produces the reference `${ publication.metadata["key"] }`.

    """

    if functions is None:
        functions = dict(smartconfig.DEFAULT_FUNCTIONS)

        def use_metadata(
            args: smartconfig.types.FunctionArgs,
        ) -> smartconfig.types.Configuration:
            key = args.input
            return f'${{ {loop_variable}.metadata["{key}"] }}'

        functions["use_metadata"] = use_metadata

    return resolve_for_each(
        publication,
        config,
        schema,
        loop_variable=loop_variable,
        vars=vars,
        functions=functions,
        fixup=fixup,
    )
