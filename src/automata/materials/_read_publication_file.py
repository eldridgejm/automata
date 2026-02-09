"""Reads a Publication from a publication.yaml file."""

import pathlib
from typing import Any, Dict, Mapping, MutableMapping, Optional, cast

import smartconfig

from ..util.resolution import resolve
from ..util.yaml import parse_yaml
from ._types import Publication, PublicationSchema, UnbuiltArtifact
from .exceptions import DiscoveryError


def _make_publication_file_schema(
    publication_schema: Optional[PublicationSchema],
) -> dict:
    """Construct a smartconfig schema for validating and resolving the publication file.

    A function is necessary here in order to dynamically convert the
    PublicationSchema object given as input into a smartconfig schema
    dictionary.

    Parameters
    ----------
    publication_schema : Optional[PublicationSchema]
        The schema that describes the necessary artifacts of the publication
        and what metadata it should have. If None, a default schema is assumed
        in which only very basic validation is done (see below). Default: None.

    Returns
    -------
    dict
        The smartconfig schema for the publication file.

    Notes
    -----
    If no publication schema is provided, a default schema is assumed in which
    only very basic validation is done. Namely, the metadata schema and required/
    optional artifacts are not enforced. See the :func:`validate` function for
    more information.

    """

    if publication_schema is None:
        publication_schema = PublicationSchema([], allow_unspecified_artifacts=True)

    artifact_schema = {
        "type": "dict",
        "optional_keys": {
            "path": {"type": "string", "nullable": True, "default": None},
            "recipe": {"type": "string", "nullable": True, "default": None},
            "ready": {"type": "boolean", "default": True},
            "missing_ok": {"type": "boolean", "default": False},
            "release_time": {"type": "datetime", "nullable": True, "default": None},
        },
    }

    artifacts_schema: dict[str, Any] = {
        "type": "dict",
        "required_keys": {},
        "optional_keys": {},
    }

    if publication_schema.required_artifacts is not None:
        for artifact_key in publication_schema.required_artifacts:
            artifacts_schema["required_keys"][artifact_key] = artifact_schema

    if publication_schema.optional_artifacts is not None:
        for artifact_key in publication_schema.optional_artifacts:
            artifacts_schema["optional_keys"][artifact_key] = artifact_schema

    if publication_schema.allow_unspecified_artifacts:
        artifacts_schema["extra_keys_schema"] = artifact_schema

    schema: dict[str, Any] = {
        "type": "dict",
        "required_keys": {"artifacts": artifacts_schema},
        "optional_keys": {},
    }

    if publication_schema.metadata_schema is not None:
        schema["optional_keys"]["metadata"] = {
            "type": "dict",
            **publication_schema.metadata_schema,
        }
    else:
        schema["optional_keys"]["metadata"] = {"type": "any", "default": {}}

    return schema


def _resolve_publication_file(
    raw_contents: smartconfig.types.ConfigurationDict,
    publication_schema: Optional[PublicationSchema],
    vars: Optional[Mapping[str, Any]],
    previous: Optional[Mapping[str, Any]],
    path: pathlib.Path,
) -> dict[str, Any]:
    """Resolves (interpolates and parses) the raw publication file contents.

    Parameters
    ----------
    raw_contents : smartconfig.types.ConfigurationDict
        The raw dictionary loaded from the publication file.
    publication_schema : Optional[PublicationSchema]
        A :class:`PublicationSchema` object that describes the necessary artifacts
        and metadata of the publication. If this is None, only very basic validation
        is done. Default: None.
    vars : Optional[Mapping[str, Any]]
        A dictionary of variables available during interpolation through the
        ``${vars}`` variable.
    previous : Optional[Mapping[str, Any]]
        A dictionary representation of the previous publication, available during
        interpolation through the ``${previous}`` variable.
    path : pathlib.Path
        The path to the publication file being read. Used to format error messages.

    Returns
    -------
    dict
        The resolved dictionary.

    """
    schema = _make_publication_file_schema(publication_schema)

    combined_dict: dict[str, Any] = {
        "this": raw_contents,
    }

    combined_schema: dict[str, Any] = {
        "type": "dict",
        "required_keys": {
            "this": schema,
        },
        "optional_keys": {},
    }

    global_variables: dict[str, Any] = {
        "vars": vars if vars is not None else {},
    }

    if previous is not None:
        combined_dict["previous"] = previous
        combined_schema["optional_keys"]["previous"] = {"type": "any"}

    combined = cast(smartconfig.types.ConfigurationDict, combined_dict)

    try:
        resolved = resolve(combined, combined_schema, global_variables=global_variables)
    except smartconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    return cast(Dict[str, Any], resolved["this"])


def read_publication_file(
    path: pathlib.Path,
    publication_schema: Optional[PublicationSchema] = None,
    vars: Optional[Mapping[str, Any]] = None,
    previous: Optional[Publication] = None,
) -> Publication[UnbuiltArtifact]:
    """Reads a :class:`types.Publication` from a ``publication.yaml`` file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the ``publication.yaml`` file.
    publication_schema : Optional[PublicationSchema]
        A schema that describes the necessary artifacts of the publication and
        what metadata it should have. If `None`, only very basic validation is
        done (see below). Default: None.
    vars : Optional[Mapping[str, Any]]
        A dictionary of variables that will be available during interpolation
        of the publication file through the ``${vars}`` variable. If None, no
        variables will be available. Default: None.
    previous : Optional[Publication]
        The previous publication. If None, there is assumed to be no previous.
        If provided, this will be available during interpolation through the
        ``${previous}`` variable. Default: None.

    Returns
    -------
    Publication
        The publication, along with its artifacts as :class:`UnbuiltArtifact` objects.

    Raises
    ------
    DiscoveryError
        If the publication file's contents are invalid.

    Notes
    -----

    The file should have a "metadata" key whose value is a dictionary
    of metadata. It should also have an "artifacts" key whose value is a
    dictionary mapping artifact names to artifact definitions.

    If the ``publication_schema`` argument is not provided, only very basic
    validation is performed by this function. Namely, the metadata schema and
    required/optional artifacts are not enforced.

    """
    yaml_content = path.read_text()
    try:
        raw_contents = parse_yaml(yaml_content)
    except Exception as exc:
        raise DiscoveryError(str(exc), path)

    previous_dict = previous._deep_asdict() if previous is not None else None

    resolved: Dict[str, Any] = _resolve_publication_file(
        raw_contents, publication_schema, vars, previous_dict, path
    )

    # convert each artifact to an UnbuiltArtifact object
    artifacts: MutableMapping[str, UnbuiltArtifact] = {}
    for key, definition in resolved["artifacts"].items():
        # if no file is provided, use the key
        if definition["path"] is None:
            definition["path"] = key

        assert isinstance(key, str)

        artifacts[key] = UnbuiltArtifact(workdir=path.parent.absolute(), **definition)

    publication = Publication[UnbuiltArtifact](
        metadata=resolved["metadata"],
        artifacts=artifacts,
    )

    return publication
