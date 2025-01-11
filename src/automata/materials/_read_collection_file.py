"""Provides read_collection_file(), which reads a Collection from a collection.yaml."""

from typing import Optional, Dict, Any
import pathlib

import dictconfig
import yaml

from ._types import Collection, PublicationSchema

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


def read_collection_file(path, vars=None):
    """Reads a :class:`types.Collection` from a ``collection.yaml`` file.

    See the documentation for a description of the format of the file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the ``collection.yaml`` file.
    vars : Optional[dict]
        A dictionary of variables available during interpolation. If None, no
        variables will be made available.

    Returns
    -------
    Collection
        The collection object with no attached publications.

    """
    if vars is None:
        vars = {}

    with path.open() as fileobj:
        raw_contents = yaml.load(fileobj, Loader=yaml.Loader)

    try:
        resolved = _resolve_collection_file(raw_contents, {"vars": vars}, path)
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    publication_schema = PublicationSchema(**resolved["publication_schema"])
    return Collection(publication_schema=publication_schema, publications={})


def _resolve_collection_file(
    raw_contents: dict, external_variables: Optional[dict], path: pathlib.Path
) -> dict:
    """Resolves (interpolates and parses) the raw collection file contents.

    Parameters
    ----------
    raw_contents : dict
        The raw dictionary loaded from the publication file.
    external_variables : Optional[dict]
        A dictionary of external_variables passed to dictconfig and used during
        interpolation. These are accessible under ${vars}.
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
    try:
        resolved: Dict[str, Any] = dictconfig.resolve(
            raw_contents, COLLECTION_FILE_SCHEMA, external_variables=external_variables
        )  # type: ignore
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    _validate_metadata_schema(resolved["publication_schema"]["metadata_schema"], path)

    return resolved


def _validate_metadata_schema(metadata_schema, path):
    """Ensures that the publication metadata schema provided is valid.

    Converts dictconfig exceptions into DiscoveryError exceptions.
    """
    if metadata_schema is None:
        return

    try:
        dictconfig.validate_schema({"type": "dict", **metadata_schema})
    except dictconfig.exceptions.InvalidSchemaError as exc:
        raise DiscoveryError(exc, path)
