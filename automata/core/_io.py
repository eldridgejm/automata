"""Read `collection.yaml` and `publication.yaml` files."""

import pathlib

import dictconfig  # type: ignore
import yaml
from typing import Optional

from ..exceptions import Error


# Technical Notes
# ===============
# This module specifies the schema for publication.yaml and collection.yaml files using
# the dictconfig format. Dictconfig handles the heavy-lifting of interpolation and
# parsing of the files' fields.


# exceptions
# ==========


class MalformedFileError(Error):
    """The file being read is malformed."""

    def __init__(self, path, reason):
        self.path = path
        self.reason = reason

    def __str__(self):
        return f"The file {self.path} is malformed: {self.reason}"


# collection files
# ======================================================================================


# we start by building a dictconfig schema for collection.yaml. collection.yaml
# consists mostly of the publication spec, whose dictconfig schema is defined below.
# We'll reuse this schema later when implementing read_publication_file, because that
# function takes in the publication spec as an optional argument, and we'll want to be
# able to validate it.
#
# a specific schema for the "metadata_schema" can't be made, since we don't know what
# metadata the user will provide. Instead, we'll use dictconfig's schema validator to
# dynamically check that it makes sense -- this will be done in read_collection_file.


_PUBLICATION_SPEC_SCHEMA = {
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


# the dictconfig schema describing a valid collection file
_COLLECTION_FILE_DICTCONFIG_SCHEMA = {
    "type": "dict",
    "required_keys": {"publication_spec": _PUBLICATION_SPEC_SCHEMA},
}


def read_collection_file(path: pathlib.Path, vars: Optional[dict] = None) -> dict:
    """Read a collection yaml file, resolving its templated fields.

    See the documentation for a description of the format of the file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    vars : Optional[dict]
        A dictionary of variables available during interpolation. These can be accessed
        in `collection.yaml` via the `${ vars.<key> }` syntax.

    Raises
    ------
    MalformedFileError
        If the file is malformed.

    Returns
    -------
    dict
        The collection file's contents as a dictionary.

    """
    if vars is None:
        vars = {}

    with path.open() as fileobj:
        raw_contents = yaml.load(fileobj, Loader=yaml.Loader)

    # attempt to resolve the templated fields in the dictionary
    try:
        resolved: dict = dictconfig.resolve(
            raw_contents,
            _COLLECTION_FILE_DICTCONFIG_SCHEMA,
            external_variables={"vars": vars},
        )  # type: ignore
    except dictconfig.exceptions.ResolutionError as exc:
        raise MalformedFileError(path, str(exc))

    # validate the metadata schema using dictconfig.validate_schema. this wasn't done by
    # dictconfig.resolve above, because our schema accepted anything for the
    # metadata_schema field.
    metadata_schema = resolved["publication_spec"]["metadata_schema"]
    if metadata_schema is not None:
        try:
            dictconfig.validate_schema({"type": "dict", **metadata_schema})
        except dictconfig.exceptions.InvalidSchemaError as exc:
            raise MalformedFileError(exc, path)

    return resolved


# publication files
# ======================================================================================

# Reading publication.yaml file is considerably more involved than reading
# collection.yaml, largely because the schema of a publication file is dynamic, being
# provided by the collection.yaml file. We do not know a priori what artifacts must be
# in the publication, or what metadata will be provided.
#
# Our goal in the next few lines of code is to construct a dictconfig schema for the
# publication.yaml. To do this, we'll use the "publication spec", if provided. This
# terminology is potentially confusing -- the "publication spec" is *not* a dictconfig
# schema, rather, it is a dictionary specifying the requirements of a publication at a
# higher level of abstraction. It is usually provided in `collection.yaml`. We use this
# "publication spec" to build a "dictconfig schema for publication.yaml".


# we start by making the dictconfig schema for a single artifact in a publication.yaml
# file. This is static -- it doesn't depend on the high-level "publication spec"


_ARTIFACT_DICTCONFIG_SCHEMA = {
    "type": "dict",
    "optional_keys": {
        "path": {"type": "string", "nullable": True, "default": None},
        "recipe": {"type": "string", "nullable": True, "default": None},
        "ready": {"type": "boolean", "default": True},
        "missing_ok": {"type": "boolean", "default": False},
        "release_time": {"type": "datetime", "nullable": True, "default": None},
    },
}


# next, we'll build the dictconfig schema for the artifacts field of publication.yaml
# here we need to know the high-level publication spec.


def _make_artifacts_dictconfig_schema(publication_spec: dict) -> dict:
    """Builds a dictconfig schema for the artifacts key in publication.yaml.

    This requires knowing the publication spec, because the publication spec
    specifies which artifacts are required, which are optional, and whether unknown
    artifacts are permitted.

    """
    artifacts_schema = {
        "type": "dict",
        "required_keys": {},
        "optional_keys": {},
    }

    for artifact in publication_spec["required_artifacts"]:
        artifacts_schema["required_keys"][artifact] = _ARTIFACT_DICTCONFIG_SCHEMA

    for artifact in publication_spec["optional_artifacts"]:
        artifacts_schema["optional_keys"][artifact] = _ARTIFACT_DICTCONFIG_SCHEMA

    if publication_spec["allow_unspecified_artifacts"]:
        artifacts_schema["extra_keys_schema"] = _ARTIFACT_DICTCONFIG_SCHEMA

    return artifacts_schema


# we can now construct a dictconfig schema for the entire publication.yaml file.


def _make_publication_dictconfig_schema(
    publication_spec: dict,
) -> dict:
    """Construct a dictconfig schema for validating and resolving the publication file."""

    artifacts_schema = _make_artifacts_dictconfig_schema(publication_spec)

    dictconfig_schema = {
        "type": "dict",
        "required_keys": {"artifacts": artifacts_schema},
        "optional_keys": {
            "ready": {"type": "boolean", "default": True},
            "release_time": {"type": "datetime", "nullable": True, "default": None},
        },
    }

    if publication_spec["metadata_schema"] is not None:
        dictconfig_schema["optional_keys"]["metadata"] = {
            "type": "dict",
            **publication_spec["metadata_schema"],
        }
    else:
        dictconfig_schema["optional_keys"]["metadata"] = {"type": "any", "default": {}}

    return dictconfig_schema


# now we prepare for the high-level read_publication_file. It will optionally accept a
# publication spec. if one isn't provided, we'll provide the permissive spec below.
# it does only minimal checking, and allows most metadata / artifacts.

_PERMISSIVE_PUBLICATION_SPEC = {
    "required_artifacts": [],
    "optional_artifacts": {},
    "allow_unspecified_artifacts": True,
    "metadata_schema": {"extra_keys_schema": {"type": "any"}},
}


def read_publication_file(
    path: pathlib.Path,
    publication_spec: Optional[dict] = None,
    vars: Optional[dict] = None,
    previous: Optional[dict] = None,
) -> dict:
    """Read a publication.yaml file, resolving its templated fields.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    publication_spec : Optional[dict]
        A dictionary that describes the necessary artifacts of the publication and
        what metadata it should have. This dictionary typically comes from a
        collection.yaml file. If `None`, only very basic validation is done (see below).
        Default: None.
    vars : Optional[dict]
        A dictionary of external variables that will be available during interpolation
        of the publication file. Default: None.
    previous : Optional[dict]
        The previous publication as a dictionary of the form returned by this function.
        If None, there is assumed to be no previous publication.

    Returns
    -------
    dict
        The contents of the publication file with templated areas resolved.

    Raises
    ------
    MalformedFileError
        If the publication file's contents are invalid.

    Notes
    -----

    If the ``publication_spec`` argument is not provided, only very basic validation is
    performed by this function. Namely, the metadata schema and required/optional
    artifacts are not enforced.

    """
    if publication_spec is None:
        publication_spec = _PERMISSIVE_PUBLICATION_SPEC.copy()

    # fill in the defaults in the publication spec
    try:
        publication_spec: dict = dictconfig.resolve(
            publication_spec, schema=_PUBLICATION_SPEC_SCHEMA
        )  # type: ignore
    except dictconfig.exceptions.ResolutionError as exc:
        raise MalformedFileError(path, str(exc))

    with path.open() as fileobj:
        try:
            raw_contents = yaml.load(fileobj.read(), Loader=yaml.Loader)
        except yaml.YAMLError as exc:
            raise MalformedFileError(path, str(exc))

    external_variables = {"vars": vars}

    if previous is not None:
        external_variables["previous"] = previous

    dictconfig_schema = _make_publication_dictconfig_schema(publication_spec)

    try:
        resolved: dict = dictconfig.resolve(
            raw_contents, dictconfig_schema, external_variables=external_variables
        )  # type: ignore
    except dictconfig.exceptions.ResolutionError as exc:
        raise MalformedFileError(path, str(exc))

    for key, definition in resolved["artifacts"].items():
        # if no file is provided, use the key
        if definition["path"] is None:
            definition["path"] = key

    return resolved
