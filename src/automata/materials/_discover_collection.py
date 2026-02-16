"""Provides parse_collection(), which builds an empty Collection from a dict."""

import pathlib
from typing import Any, Dict, Mapping, Optional, cast

import smartconfig

from ..util.resolution import resolve
from ._types import Collection, PublicationSchema, UnbuiltArtifact
from .exceptions import DiscoveryError

# the smartconfig schema describing a valid collection.
COLLECTION_SCHEMA = {
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
    "optional_keys": {
        "templates": {
            "type": "any",
            "default": None,
            "nullable": True,
        },
    },
}


def _resolve_collection(
    raw_contents: smartconfig.types.ConfigurationDict,
    vars: Optional[Mapping[str, Any]],
    source: pathlib.Path,
) -> dict:
    """Resolves (interpolates and parses) raw collection contents.

    Parameters
    ----------
    raw_contents : smartconfig.types.ConfigurationDict
        The raw dictionary describing the collection.
    vars : Optional[Mapping[str, Any]]
        A dictionary of variables available during interpolation through the
        ``${vars}`` variable.
    source : Path
        The file that the data was read from, used for error messages.

    Returns
    -------
    dict
        The resolved dictionary.

    Raises
    ------
    DiscoveryError
        If the collection contents are invalid.

    """
    contents = cast(smartconfig.types.ConfigurationDict, raw_contents)

    try:
        resolved: Dict[str, Any] = resolve(
            contents,
            COLLECTION_SCHEMA,
            global_variables={"vars": vars if vars is not None else {}},
        )
    except smartconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), source)

    _validate_metadata_schema(resolved["publication_schema"]["metadata_schema"], source)

    return cast(Dict[str, Any], resolved)


def _validate_metadata_schema(
    metadata_schema: Optional[Mapping[str, str]],
    source: pathlib.Path,
):
    """Ensures that the publication metadata schema provided is valid.

    If the function runs without raising an exception, the schema is valid.
    Otherwise, it raises a DiscoveryError.

    Parameters
    ----------
    metadata_schema : Optional[Mapping[str, str]]
        The metadata schema to validate. If the schema is None, this function
        automatically returns.
    source : Path
        The file that the data was read from, used for error messages.

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
        raise DiscoveryError(str(exc), source)


def parse_collection(
    raw_contents: dict,
    *,
    source: pathlib.Path,
    vars: Optional[Mapping[str, Any]] = None,
) -> tuple[Collection[UnbuiltArtifact], Optional[dict]]:
    """Build a :class:`Collection` from a "raw" dictionary of collection contents.

    If the contents include a ``publications`` key, the raw (unresolved) publications
    dict is extracted and returned separately. It is not included in the smartconfig
    resolution of the collection itself, because each publication needs its own
    resolution pass in order to validate the publication schema defined in the
    collection specification against each publication individually.

    Parameters
    ----------
    raw_contents : dict
        The parsed YAML dictionary from a ``collection.yaml`` file.
    source : Path
        The file that the data was read from, used for error messages.
    vars : Optional[Mapping[str, Any]]
        A dictionary of variables available during interpolation through the
        ``${vars}`` variable. If None, no variables will be made available.

    Returns
    -------
    tuple[Collection, Optional[dict]]
        The collection object (with no attached publications) and the raw
        inline publications dict, or ``None`` if no ``publications`` key
        was present.

    """
    if vars is None:
        vars = {}

    raw_publications = raw_contents.pop("publications", None)

    resolved = _resolve_collection(raw_contents, vars, source)

    publication_schema = PublicationSchema(**resolved["publication_schema"])
    templates = resolved.get("templates")
    collection = Collection(
        publication_schema=publication_schema, publications={}, templates=templates
    )
    return collection, raw_publications
