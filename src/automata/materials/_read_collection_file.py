"""Provides read_collection_file(), which reads a Collection from a collection.yaml."""

import pathlib
from typing import Any, Dict, Mapping, Optional, cast

import smartconfig

from ..util.resolution import resolve
from ..util.yaml import parse_yaml
from ._types import Collection, PublicationSchema, UnbuiltArtifact
from .exceptions import DiscoveryError

# the dictconfig schema describing a valid collection file.
COLLECTION_FILE_SCHEMA = {
    "type": "dict",
    "required_keys": {
        "publication_schema": {
            "type": "dict",
            "required_keys": {
                "required_artifacts": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                }
            },
            "optional_keys": {
                "optional_artifacts": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                    "default": [],
                },
                "metadata_schema": {
                    "type": "dict",
                    "extra_keys_schema": {"type": "any"},
                    "default": None,
                    "nullable": True,
                },
                "allow_unspecified_artifacts": {
                    "type": "boolean",
                    "default": False,
                },
                "is_ordered": {"type": "boolean", "default": False},
            },
        }
    },
}


def _resolve_collection_file(
    raw_contents: smartconfig.types.ConfigurationDict,
    vars: Optional[Mapping[str, Any]],
    path: pathlib.Path,
) -> dict:
    """Resolves (interpolates and parses) the raw collection file contents.

    Parameters
    ----------
    raw_contents : smartconfig.types.ConfigurationDict
        The raw dictionary loaded from the publication file.
    vars : Optional[Mapping[str, Any]]
        A dictionary of variables available during interpolation through the
        ``${vars}`` variable.
    path : pathlib.Path
        The path to the collection file being read. Used to format error messages.

    Returns
    -------
    dict
        The resolved dictionary.

    Raises
    ------
    DiscoveryError
        If the collection file is invalid.

    """
    # Combine the configuration and external variables into a single dictionary.
    # This avoids using global_variables, which can cause namespace pollution.
    # References use ${this.key} for config values and ${vars.key} for external vars.
    combined = cast(
        smartconfig.types.ConfigurationDict,
        {"this": raw_contents, "vars": vars if vars is not None else {}},
    )

    combined_schema = {
        "type": "dict",
        "required_keys": {
            "this": COLLECTION_FILE_SCHEMA,
            "vars": {"type": "any"},
        },
    }

    try:
        resolved: Dict[str, Any] = resolve(combined, combined_schema)
    except smartconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    _validate_metadata_schema(
        resolved["this"]["publication_schema"]["metadata_schema"], path
    )

    return cast(Dict[str, Any], resolved["this"])


def _validate_metadata_schema(
    metadata_schema: Optional[Mapping[str, str]], path: pathlib.Path
):
    """Ensures that the publication metadata schema provided is valid.

    If the function runs without raising an exception, the schema is valid.
    Otherwise, it raises a DiscoveryError.

    Parameters
    ----------
    metadata_schema : Optional[Mapping[str, str]]
        The metadata schema to validate. If the schema is None, this function
        automatically returns.
    path : pathlib.Path
        The path to the collection file being read. Used to format error messages.

    Raises
    ------
    DiscoveryError
        If the metadata schema is invalid.

    """
    if metadata_schema is None:
        return

    try:
        smartconfig.validate_schema({"type": "dict", **metadata_schema})
    except smartconfig.exceptions.InvalidSchemaError as exc:
        raise DiscoveryError(exc, path)


def read_collection_file(
    path: pathlib.Path, vars: Optional[Mapping[str, Any]] = None
) -> Collection[UnbuiltArtifact]:
    """Reads a :class:`types.Collection` from a ``collection.yaml`` file.

    See the documentation for a description of the format of the file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the ``collection.yaml`` file.
    vars : Optional[Mapping[str, str]]
        A dictionary of variables available during interpolation through the
        ``${vars}`` variable. If None, no variables will be made available.

    Returns
    -------
    Collection
        The collection object with no attached publications.

    """
    if vars is None:
        vars = {}

    yaml_content = path.read_text()
    raw_contents = parse_yaml(yaml_content)

    resolved = _resolve_collection_file(raw_contents, vars, path)

    publication_schema = PublicationSchema(**resolved["publication_schema"])
    return Collection(publication_schema=publication_schema, publications={})
