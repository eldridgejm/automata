"""Provides parse_publication(), which builds a Publication from raw parsed YAML."""

import pathlib
from typing import Any, Dict, Mapping, MutableMapping, Optional, cast

import smartconfig

from ..util.resolution import resolve
from ._types import Publication, PublicationSchema, UnbuiltArtifact
from .exceptions import DiscoveryError


def _make_publication_schema(
    publication_schema: Optional[PublicationSchema],
) -> dict:
    """Construct a smartconfig schema for validating and resolving a publication.

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
        The smartconfig schema for the publication.

    Notes
    -----
    If no publication schema is provided, a default schema is assumed in which
    only very basic validation is done. Namely, the metadata schema and required/
    optional artifacts are not enforced.

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


def _resolve_publication(
    raw_contents: smartconfig.types.ConfigurationDict,
    publication_schema: Optional[PublicationSchema],
    vars: Optional[Mapping[str, Any]],
    previous: Optional[Mapping[str, Any]],
    source: pathlib.Path,
) -> dict[str, Any]:
    """Resolves (interpolates and parses) raw publication contents.

    Parameters
    ----------
    raw_contents : smartconfig.types.ConfigurationDict
        The raw dictionary describing the publication.
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
    source : Path
        The file that the data was read from, used for error messages.

    Returns
    -------
    dict
        The resolved dictionary.

    """
    schema = _make_publication_schema(publication_schema)

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
        raise DiscoveryError(str(exc), source)

    return cast(Dict[str, Any], resolved["this"])


def parse_publication(
    raw_contents: smartconfig.types.ConfigurationDict,
    workdir: pathlib.Path,
    *,
    source: pathlib.Path,
    publication_schema: Optional[PublicationSchema] = None,
    vars: Optional[Mapping[str, Any]] = None,
    previous: Optional[Publication] = None,
) -> Publication[UnbuiltArtifact]:
    """Create a :class:`Publication` from raw (pre-YAML-parsed) contents.

    Parameters
    ----------
    raw_contents : smartconfig.types.ConfigurationDict
        The raw dictionary describing the publication (same structure as a
        parsed publication.yaml).
    workdir : Path
        The working directory for artifact recipes and paths.
    source : Path
        The file that the data was read from, used for error messages.
    publication_schema : Optional[PublicationSchema]
        A schema that describes the necessary artifacts of the publication and
        what metadata it should have. If `None`, only very basic validation is
        done. Default: None.
    vars : Optional[Mapping[str, Any]]
        A dictionary of variables that will be available during interpolation
        through the ``${vars}`` variable. Default: None.
    previous : Optional[Publication]
        The previous publication, available during interpolation through the
        ``${previous}`` variable. Default: None.

    Returns
    -------
    Publication
        The publication, along with its artifacts as :class:`UnbuiltArtifact` objects.

    """
    previous_dict = previous._deep_asdict() if previous is not None else None

    resolved: Dict[str, Any] = _resolve_publication(
        raw_contents,
        publication_schema,
        vars,
        previous_dict,
        source,
    )

    artifacts: MutableMapping[str, UnbuiltArtifact] = {}
    for key, definition in resolved["artifacts"].items():
        if definition["path"] is None:
            definition["path"] = key

        assert isinstance(key, str)

        artifacts[key] = UnbuiltArtifact(workdir=workdir.absolute(), **definition)

    return Publication[UnbuiltArtifact](
        metadata=resolved["metadata"],
        artifacts=artifacts,
    )
