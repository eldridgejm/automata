import dictconfig
import yaml

from .types import UnbuiltArtifact, Publication, Collection, PublicationSchema

from .exceptions import DiscoveryError


def read_publication_file(path, publication_schema=None, vars=None, previous=None):
    """Read a :class:`Publication` from a ``publication.yaml`` file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the ``publication.yaml`` file.
    publication_schema : Optional[PublicationSchema]
        A schema that described the necessary artifacts of the publication and
        what metadata it should have. If `None`, only very basic validation is
        done (see below). Default: None.
    vars : Optional[dict]
        A dictionary of external variables that will be available during
        interpolation of the publication file. If None, no variables will be
        available. Default: None.
    previous : Optional[Publication]
        The previous publication. If None, there is assumed to be no previous.

    Returns
    -------
    Publication
        The publication, along with its artifacts.

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

    resolved = _resolve_publication_file(
        raw_contents, publication_schema, external_variables, path
    )

    # convert each artifact to an Artifact object
    artifacts = {}
    for key, definition in resolved["artifacts"].items():
        # if no file is provided, use the key
        if definition["path"] is None:
            definition["path"] = key

        artifacts[key] = UnbuiltArtifact(workdir=path.parent.absolute(), **definition)

    publication = Publication(
        metadata=resolved["metadata"],
        artifacts=artifacts,
    )

    return publication


def _make_publication_file_schema(publication_schema):
    """Construct a dictconfig schema for validating and resolving the publication file."""

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

    artifacts_schema = {
        "type": "dict",
        "required_keys": {},
        "optional_keys": {},
    }

    if publication_schema.required_artifacts is not None:
        for artifact in publication_schema.required_artifacts:
            artifacts_schema["required_keys"][artifact] = artifact_schema

    if publication_schema.optional_artifacts is not None:
        for artifact in publication_schema.optional_artifacts:
            artifacts_schema["optional_keys"][artifact] = artifact_schema

    if publication_schema.allow_unspecified_artifacts:
        artifacts_schema["extra_keys_schema"] = artifact_schema

    schema = {
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
    raw_contents, publication_schema, external_variables, path
):
    """Resolves (interpolates and parses) the raw publication file contents.

    Parameters
    ----------
    raw_contents : dict
        The raw dictionary loaded from the publication file.
    metadata_schema : Optional[dict]
        A dictconfig schema for the "metadata" field of `raw_contents`. If this is
        None, the schema passed to dictconfig will not have a "metadata" field,
        and so it will not be interpolated/parsed (all leafs will be left as-is).
    external_variables : Optional[dict]
        A dictionary of external_variables passed to dictconfig and used during
        interpolation. These are accessible under ${vars}

    Returns
    -------
    dict
        The resolved dictionary.

    """
    schema = _make_publication_file_schema(publication_schema)

    try:
        return dictconfig.resolve(
            raw_contents, schema, external_variables=external_variables
        )
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)
