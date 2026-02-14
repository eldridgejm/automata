"""Configuration resolution helpers for materials workflows."""

import typing

import smartconfig

from ..util.resolution import resolve_for_each
from ._types import Publication


def resolve_for_each_publication(
    publication: typing.Sequence[Publication],
    config: smartconfig.types.Configuration,
    schema: smartconfig.types.Schema,
    vars: dict | None = None,
    loop_variable: str = "publication",
    functions: smartconfig.types.FunctionMapping | None = None,
    fixup: typing.Callable[
        [smartconfig.types.Configuration, Publication], smartconfig.types.Configuration
    ]
    | None = None,
) -> list[smartconfig.types.Configuration]:
    """Resolves a configuration once for each publication in a sequence.

    This is a specialized version of resolve_for_each that adds a custom
    `use_metadata` function for convenient access to publication metadata.

    Parameters
    ----------
    publication : typing.Sequence[Publication]
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
    functions : smartconfig.types.FunctionMapping | None, optional
        A mapping of custom functions to use during resolution. If None, the
        default functions from smartconfig will be used, plus an added
        `use_metadata` function for accessing publication metadata.
    fixup : Callable[
                [smartconfig.types.Configuration, Publication],
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
