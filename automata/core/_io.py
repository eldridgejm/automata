import pathlib

import dictconfig  # type: ignore
import yaml
from typing import Optional

from .exceptions import DiscoveryError


# collection files
# ======================================================================================

"""The dictconfig schema describing a valid collection file."""
_COLLECTION_FILE_SCHEMA = {
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


def read_collection_file(path: pathlib.Path, vars: Optional[dict] = None) -> dict:
    """Read a collection file and resolve its templated fields.

    See the documentation for a description of the format of the file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    vars : Optional[dict]
        A dictionary of variables available during interpolation.

    Returns
    -------
    dict
        The collection file's interpolated contents as a dictionary.

    """
    if vars is None:
        vars = {}

    with path.open() as fileobj:
        raw_contents = yaml.load(fileobj, Loader=yaml.Loader)

    # attempt to resolve the templated fields in the dictionary
    try:
        resolved: dict = dictconfig.resolve(
            raw_contents, _COLLECTION_FILE_SCHEMA, external_variables={"vars": vars}
        )  # type: ignore
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    # validate the metadata schema
    metadata_schema = resolved["publication_schema"]["metadata_schema"]
    if metadata_schema is not None:
        try:
            dictconfig.validate_schema({"type": "dict", **metadata_schema})
        except dictconfig.exceptions.InvalidSchemaError as exc:
            raise DiscoveryError(exc, path)

    return resolved


# publication files
# ======================================================================================


def read_publication_file(
    path: pathlib.Path, publication_schema=None, vars=None, previous=None
) -> dict:
    """Read a publication.yaml file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    publication_schema : Optional[PublicationSchema]
        A schema that described the necessary artifacts of the publication and
        what metadata it should have. If `None`, only very basic validation is
        done (see below). Default: None.
    vars : dict
        A dictionary of external variables that will be available during interpolation
        of the publication file.
    previous : Publication
        The previous publication. If None, there is assumed to be no previous.

    Returns
    -------
    Publication
        The publication.

    Raises
    ------
    DiscoveryError
        If the publication file's contents are invalid.

    Notes
    -----

    The file should have a "metadata" key whose value is a dictionary
    of metadata. It should also have an "artifacts" key whose value is a
    dictionary mapping artifact names to artifact definitions.

    Optionally, the file can have a "release_time" key providing a time at
    which the publication should be considered released. It may also have
    a "ready" key; if this is False, the publication will not be considered
    released.

    If the ``publication_schema`` argument is not provided, only very basic
    validation is performed by this function. Namely, the metadata schema and
    required/optional artifacts are not enforced. See the :func:`validate`
    function for validating these aspects of the publication. If the schema is
    provided, :func:`validate` is called as a convenience.

    """
    with path.open() as fileobj:
        try:
            raw_contents = yaml.load(fileobj.read(), Loader=yaml.Loader)
        except yaml.YAMLError as exc:
            raise DiscoveryError(str(exc), path)

    external_variables = {"vars": vars}

    if previous is not None:
        external_variables["previous"] = previous._deep_asdict()

    schema = _make_dictconfig_scheme_for_publication_file(publication_schema)

    try:
        resolved = dictconfig.resolve(
            raw_contents, schema, external_variables=external_variables
        )
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    for key, definition in resolved["artifacts"].items():
        # if no file is provided, use the key
        if definition["path"] is None:
            definition["path"] = key

    return resolved


_PERMISSIVE_PUBLICATION_SCHEMA = {
    "required_artifacts": [],
    "optional_artifacts": {},
    "allow_unspecified_artifacts": True,
    "metadata_schema": {"extra_keys_schema": {"type": "any"}},
}

_DEFAULT_PUBLICATION_SCHEMA = {
    "required_artifacts": [],
    "optional_artifacts": {},
    "allow_unspecified_artifacts": False,
    "metadata_schema": {},
}


_ARTIFACT_SCHEMA = {
            "type": "dict",
            "optional_keys": {
                "path": {"type": "string", "nullable": True, "default": None},
                "recipe": {"type": "string", "nullable": True, "default": None},
                "ready": {"type": "boolean", "default": True},
                "missing_ok": {"type": "boolean", "default": False},
                "release_time": {"type": "datetime", "nullable": True, "default": None},
                },
            }

def _make_artifacts_schema(publication_schema) -> dict:
    artifacts_schema = {
    "type": "dict",
    "required_keys": {},
    "optional_keys": {},
    }

    if publication_schema["required_artifacts"] is not None:
        for artifact in publication_schema["required_artifacts"]:
            artifacts_schema["required_keys"][artifact] = _ARTIFACT_SCHEMA

    if publication_schema["optional_artifacts"] is not None:
        for artifact in publication_schema["optional_artifacts"]:
            artifacts_schema["optional_keys"][artifact] = _ARTIFACT_SCHEMA

    if publication_schema["allow_unspecified_artifacts"]:
        artifacts_schema["extra_keys_schema"] = _ARTIFACT_SCHEMA

    return artifacts_schema


def _make_dictconfig_scheme_for_publication_file(publication_schema: Optional[dict]) -> dict:
    """Construct a dictconfig schema for validating and resolving the publication file."""

    if publication_schema is None:
        publication_schema = _PERMISSIVE_PUBLICATION_SCHEMA.copy()

    for key in _DEFAULT_PUBLICATION_SCHEMA.keys():
        if key not in publication_schema:
            publication_schema[key] = _DEFAULT_PUBLICATION_SCHEMA[key]

    artifacts_schema = _make_artifacts_schema(publication_schema)

    schema = {
        "type": "dict",
        "required_keys": {"artifacts": artifacts_schema},
        "optional_keys": {},
    }

    if publication_schema["metadata_schema"] is not None:
        schema["optional_keys"]["metadata"] = {
            "type": "dict",
            **publication_schema["metadata_schema"],
        }
    else:
        schema["optional_keys"]["metadata"] = {"type": "any", "default": {}}

    return schema
