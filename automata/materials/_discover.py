import typing
import datetime
import pathlib
import re
from collections import namedtuple, deque, OrderedDict

import cerberus
import dictconfig
import yaml
import jinja2

from .types import (
    UnbuiltArtifact,
    Publication,
    Collection,
    Universe,
    Schema,
    DateContext,
)
from .exceptions import ValidationError, DiscoveryError
from ._validate import validate, _PublicationValidator
from ._smartdates import resolve_smart_dates
from . import constants


# read_collection_file
# --------------------------------------------------------------------------------------


def read_collection_file(path):
    """Read a :class:`Collection` from a yaml file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.

    Returns
    -------
    Collection
        The collection object with no attached publications.

    Notes
    -----
    The file should have one key, "schema", whose value is a dictionary with
    the following keys/values:

    - required_artifacts
        A list of artifacts names that are required
    - optional_artifacts [optional]
        A list of artifacts that are optional. If not provided, the default value of []
        (empty list) will be used.
    - metadata_schema [optional]
        A dictionary describing a schema for validating publication metadata.  The
        dictionary should deserialize to something recognized by the cerberus package.
        If not provided, the default value of None will be used.
    - allow_unspecified_artifacts [optional]
        Whether or not to allow unspecified artifacts in the publications.
        Default: False.

    """
    with path.open() as fileobj:
        contents = yaml.load(fileobj, Loader=yaml.Loader)

    # define the structure of the collections file. we require only the
    # 'required_artifacts' field.
    validator = cerberus.Validator(
        {
            "schema": {
                "schema": {
                    "required_artifacts": {
                        "type": "list",
                        "schema": {"type": "string"},
                        "required": True,
                    },
                    "optional_artifacts": {
                        "type": "list",
                        "schema": {"type": "string"},
                        "default": [],
                    },
                    "metadata_schema": {
                        "type": "dict",
                        "required": False,
                        "nullable": True,
                        "default": None,
                    },
                    "allow_unspecified_artifacts": {
                        "type": "boolean",
                        "default": False,
                    },
                    "is_ordered": {"type": "boolean", "default": False,},
                },
            }
        },
        require_all=True,
    )

    # validate and normalize
    validated_contents = validator.validated(contents)

    if validated_contents is None:
        raise DiscoveryError(str(validator.errors), path)

    # make sure that the metadata schema is valid
    if validated_contents["schema"]["metadata_schema"] is not None:
        try:
            _PublicationValidator(validated_contents["schema"]["metadata_schema"])
        except Exception as exc:
            raise DiscoveryError("Invalid metadata schema.", path)

    schema = Schema(**validated_contents["schema"])
    return Collection(schema=schema, publications={})


# read_publication_file
# --------------------------------------------------------------------------------------


def _resolve_smart_dates_in_metadata(metadata, metadata_schema, path, date_context):
    def _is_smart_date(k):
        try:
            return metadata_schema[k]["type"] in {"smartdate", "smartdatetime"}
        except Exception:
            return False

    smart_dates = {k: v for k, v in metadata.items() if _is_smart_date(k)}

    known = {} if date_context.known is None else date_context.known.copy()
    for k, v in metadata.items():
        if not _is_smart_date(k):
            known[k] = v

    date_context = date_context._replace(known=known)

    try:
        resolved = resolve_smart_dates(smart_dates, date_context)
    except ValidationError as exc:
        raise DiscoveryError(str(exc), path)

    result = metadata.copy()
    for key, value in resolved.items():
        result[key] = value

    return result


def _resolve_smart_dates_in_release_time(release_time, metadata, path, date_context):
    # the release time can be None, or a datetime object
    if not isinstance(release_time, str):
        return release_time

    smart_dates = {"release_time": release_time}
    # we prepend "metadata." to every key, because the release_time has to reference
    # things in metadata this way

    known = {} if date_context.known is None else date_context.known.copy()
    for k, v in metadata.items():
        known["metadata." + k] = v

    date_context = date_context._replace(known=known)

    try:
        resolved = resolve_smart_dates(smart_dates, date_context)["release_time"]
    except ValidationError as exc:
        raise DiscoveryError(str(exc), path)

    if not isinstance(resolved, datetime.datetime):
        raise DiscoveryError("release_time is not a datetime.", path)

    return resolved



def _publication_file_base_schema():
    return {
        "ready": {"type": "boolean", "default": True, "nullable": True},
        "release_time": {
            "type": ["datetime", "string"],
            "default": None,
            "nullable": True,
        },
        "artifacts": {
            "required": True,
            "type": "dict",
            "valuesrules": {
                "type": "dict",
                "schema": {
                    "file": {"type": "string", "default": None, "nullable": True},
                    "recipe": {"type": "string", "default": None, "nullable": True},
                    "ready": {"type": "boolean", "default": True, "nullable": True},
                    "missing_ok": {"type": "boolean", "default": False},
                    "release_time": {
                        "type": "datetime",
                        "default": None,
                        "nullable": True,
                    },
                }
            },
        },
    }



def read_publication_file(path, schema=None, template_vars=None, date_context=None):
    """Read a :class:`Publication` from a yaml file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    schema : Optional[Schema]
        A schema for validating the publication. Default: None, in which case the
        publication's metadata are not validated.
    template_vars : dict
        A dictionary of external variables that will be available during interpolation
        of the publication file.

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

    If the ``schema`` argument is not provided, only very basic validation is
    performed by this function. Namely, the metadata schema and
    required/optional artifacts are not enforced. See the :func:`validate`
    function for validating these aspects of the publication. If the schema is
    provided, :func:`validate` is called as a convenience.

    """
    with path.open() as fileobj:
        raw_contents = yaml.load(fileobj.read(), Loader=yaml.Loader)

    metadata_schema = None if schema is None else schema.metadata_schema

    resolved = _resolve_publication_file(raw_contents, metadata_schema, template_vars, path)
    validated = _validate_publication_file(resolved, schema, path)

    # convert each artifact to an Artifact object
    artifacts = {}
    for key, definition in validated["artifacts"].items():
        # if no file is provided, use the key
        if definition["file"] is None:
            definition["file"] = key

        artifacts[key] = UnbuiltArtifact(workdir=path.parent.absolute(), **definition)

    publication = Publication(
        metadata=validated['metadata'],
        artifacts=artifacts,
        ready=validated["ready"],
        release_time=validated['release_time'],
    )

    return publication


def _resolve_publication_file(raw_contents, metadata_schema, external_variables, path):
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
        interpolation.

    Returns
    -------
    dict
        The resolved dictionary.

    """
    schema = {
        'type': 'dict',
        'schema': _publication_file_base_schema()
    }

    if metadata_schema is not None:
        schema['schema']['metadata'] = {'type': 'dict', 'schema': metadata_schema}

    try:
        return dictconfig.resolve(raw_contents, schema, external_variables=external_variables)
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)


def _validate_publication_file(resolved, schema, path):
    full_schema = _publication_file_base_schema()

    full_schema["metadata"] = {"type": "dict", "required": False, "default":
            {}}

    if schema is not None and schema.metadata_schema is not None:
        full_schema['metadata']['schema'] = schema.metadata_schema

    # validate and normalize the contents
    validator = _PublicationValidator(full_schema, require_all=True)
    validated = validator.validated(resolved)

    if validated is None:
        raise DiscoveryError(str(validator.errors), path)

    return validated


def _construct_publication_file_schema(schema, raw_contents):
    """Constructs a schema for validating and resolving the publication file.

    We could in principle directly construct a static Cerberus schema for validating a
    publication file, however, it would use features that are not supported by the simple
    schema grammar expected by dictconfig. For example, we do not know what artifacts
    will be supplied by the publication file, so we might use the "valuesrules"
    rule in a Cerberus schema to provide a schema for dict values without listing the keys.
    But dictconfig doesn't understand this 

    """


    quick_schema = {
        "ready": {"type": "boolean", "default": True, "nullable": True},
        "release_time": {
            "type": ["datetime", "string"],
            "default": None,
            "nullable": True,
        },
        "metadata": {"type": "dict", "required": False, "default": {}},
        "artifacts": {
            "required": True,
            "naluesrules": {
                "schema": {
                    "file": {"type": "string", "default": None, "nullable": True},
                    "recipe": {"type": "string", "default": None, "nullable": True},
                    "ready": {"type": "boolean", "default": True, "nullable": True},
                    "missing_ok": {"type": "boolean", "default": False},
                    "release_time": {
                        "type": "datetime",
                        "default": None,
                        "nullable": True,
                    },
                }
            },
        },
    }

def read_publication_file_old(path, schema=None, date_context=None, template_vars=None):
    """Read a :class:`Publication` from a yaml file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    schema : Optional[Schema]
        A schema for validating the publication. Default: None, in which case the
        publication's metadata are not validated.
    date_context : Optional[DateContext]
        A context used to evaluate smart dates. If None, no context is provided.

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

    If the ``schema`` argument is not provided, only very basic validation is
    performed by this function. Namely, the metadata schema and
    required/optional artifacts are not enforced. See the :func:`validate`
    function for validating these aspects of the publication. If the schema is
    provided, :func:`validate` is called as a convenience.


    """
    if date_context is None:
        date_context = DateContext({})

    if template_vars is None:
        template_vars = {}

    with path.open() as fileobj:
        raw_contents = fileobj.read()

    # interpolation on the publication file using template_vars
    contents = yaml.load(raw_contents, Loader=yaml.Loader)

    # we'll just do a quick check of the file structure first. validating the metadata
    # schema and checking that the right artifacts are provided will be done later
    quick_schema = {
        "ready": {"type": "boolean", "default": True, "nullable": True},
        "release_time": {
            "type": ["datetime", "string"],
            "default": None,
            "nullable": True,
        },
        "metadata": {"type": "dict", "required": False, "default": {}},
        "artifacts": {
            "type": "dict",
            "required": True,
            "schema": {}
        },
    }

    artifact_schema = {
            'type': 'dict',
            'schema': {
            "file": {"type": "string", "default": None, "nullable": True},
            "recipe": {"type": "string", "default": None, "nullable": True},
            "ready": {"type": "boolean", "default": True, "nullable": True},
            "missing_ok": {"type": "boolean", "default": False},
            "release_time": {
                "type": "datetime",
                "default": None,
                "nullable": True,
                }
            }
        }

    for artifact_name in contents['artifacts']:
        quick_schema['artifacts']['schema'][artifact_name] = artifact_schema

    # validate and normalize the contents
    validator = _PublicationValidator(quick_schema, require_all=True)
    validated = validator.validated(contents)

    if validated is None:
        raise DiscoveryError(str(validator.errors), path)

    sch = quick_schema.copy()
    sch['metadata'] = {'type': 'dict', 'schema': schema.metadata_schema}

    validated = dictconfig.resolve(validated, {'type': 'dict', 'schema': sch},
            external_variables=template_vars)
    metadata = validated['metadata']

    # convert each artifact to an Artifact object
    artifacts = {}
    for key, definition in validated["artifacts"].items():
        # handle relative release times
        definition["release_time"] = _resolve_smart_dates_in_release_time(
            definition["release_time"], metadata, path, date_context
        )

        # if no file is provided, use the key
        if definition["file"] is None:
            definition["file"] = key

        artifacts[key] = UnbuiltArtifact(workdir=path.parent.absolute(), **definition)

    # handle publication release time
    release_time = _resolve_smart_dates_in_release_time(
        validated["release_time"], metadata, path, date_context
    )

    publication = Publication(
        metadata=metadata,
        artifacts=artifacts,
        ready=validated["ready"],
        release_time=release_time,
    )

    if schema is not None:
        try:
            validate(publication, against=schema)
        except ValidationError as exc:
            raise DiscoveryError(str(exc), path)

    return publication


# discovery: discover()
# --------------------------------------------------------------------------------------


class DiscoverCallbacks:
    """Callbacks used in :func:`discover`. Defaults do nothing."""

    def on_collection(self, path):
        """When a collection is discovered.

        Parameters
        ----------
        path : pathlib.Path
            The path of the collection file.

        """

    def on_publication(self, path):
        """When a publication is discovered.

        Parameters
        ----------
        path : pathlib.Path
            The path of the publication file.

        """

    def on_skip(self, path):
        """When a directory is skipped.

        Parameters
        ----------
        path : pathlib.Path
            The path of the directory to be skipped.

        """


def _is_collection(path):
    """Determine if the path is a collection."""
    return (path / constants.COLLECTION_FILE).is_file()


def _is_publication(path):
    """Determine if the path is a publication."""
    return (path / constants.PUBLICATION_FILE).is_file()


def _search_for_collections_and_publications(
    input_directory: pathlib.Path, skip_directories=None, callbacks=None
):
    """Perform a BFS to find all collections and publications in the filesystem.

    Parameters
    ----------
    input_directory : pathlib.Path
        Path to the input directory that will be recursively searched.
    skip_directories : Optional[Collection[str]]
        A collection of folder names that, if found, will be skipped over. If None,
        every folder is searched.
    callbacks : DiscoverCallbacks
        Callbacks invoked when interesting things happen.

    Returns
    -------
    List[Path]
        The path to every collection discovered. The "default" collection is not included.
    Mapping[Path, Union[Path, None]]
        A mapping whose keys are the paths to all discovered publications. The values
        are paths to the collections containing the publications. If a publication has
        no collection (or rather, belongs to the "default" collection), its value will
        be ``None``.

    Raises
    ------
    DiscoveryError
        If a nested collection is found.

    """
    if skip_directories is None:
        skip_directories = set()

    if callbacks is None:
        callbacks = DiscoverCallbacks()

    queue = deque([(input_directory, None)])

    collections = []
    publications = {}

    while queue:
        current_path, parent_collection_path = queue.pop()

        if _is_collection(current_path):
            if parent_collection_path is not None:
                raise DiscoveryError(f"Nested collection found.", current_path)

            collections.append(current_path)
            parent_collection_path = current_path

        if _is_publication(current_path):
            publications[current_path] = parent_collection_path

        for subpath in current_path.iterdir():
            if subpath.is_dir():
                if subpath.name in skip_directories:
                    callbacks.on_skip(subpath)
                    continue
                queue.append((subpath, parent_collection_path))

    return collections, publications


def _make_default_collection():
    """Create a default collection."""
    default_schema = Schema(
        required_artifacts=[], metadata_schema=None, allow_unspecified_artifacts=True,
    )
    return Collection(schema=default_schema, publications={})


def _make_collections(collection_paths, input_directory, callbacks):
    """Make the Collection objects. 

    Parameters
    ----------
    collection_paths : List[Path]
        A list containing the path to every discovered collection.
    input_directory : Path
        Path to the root of the search.
    callbacks : DiscoverCallbacks
        The callbacks to be invoked when interesting things happen.

    Returns
    -------
    Mapping[str, Collection]
        A mapping from collection keys to new Collection objects. A collection's key is
        the string form of its path relative to the input directory.

    """
    collections = {}
    for path in collection_paths:
        file_path = path / constants.COLLECTION_FILE

        collection = read_collection_file(file_path)

        key = str(path.relative_to(input_directory))
        collections[key] = collection

        callbacks.on_collection(file_path)

    collections["default"] = _make_default_collection()
    return collections


def _add_previous_keys(date_context, collection):
    copy = date_context._replace()

    if not collection.schema.is_ordered:
        return copy

    # the previous publication was just the last one added to collection.publications
    try:
        previous_key = list(collection.publications)[-1]
    except IndexError:
        return copy

    prev_meta = collection.publications[previous_key].metadata

    known = {} if date_context.known is None else date_context.known.copy()
    for key, value in prev_meta.items():
        if isinstance(value, datetime.date):
            known[f"previous.metadata.{key}"] = value

    return date_context._replace(known=known)


def _make_publications(
    publication_paths,
    input_directory,
    collections,
    *,
    callbacks,
    date_context,
    template_vars,
):
    """Make the Publication objects.

    Parameters
    ----------
    publication_paths : Mapping[Path, Union[Path, None]]
        Mapping from publication paths to the paths of the collections containing them
        (or ``None`` if the publication is part of the "default" collection.
    input_directory : Path
        Path to the root of the search.
    collections : Mapping[str, Collection]
        A mapping from collection keys to Collection objects. The newly-created 
        Publication objects will be added to these Collection objects in-place.
    callbacks : DiscoverCallbacks
        The callbacks to be invoked when interesting things happen.
    date_context : DateContext
        A date context used to evaluate smart dates.

    """
    for path, collection_path in publication_paths.items():
        if collection_path is None:
            collection_key = "default"
            publication_key = str(path.relative_to(input_directory))
        else:
            collection_key = str(collection_path.relative_to(input_directory))
            publication_key = str(path.relative_to(collection_path))

        collection = collections[collection_key]

        publication_date_context = _add_previous_keys(date_context, collection)

        file_path = path / constants.PUBLICATION_FILE
        publication = read_publication_file(
            file_path,
            schema=collection.schema,
            date_context=publication_date_context,
            template_vars=template_vars,
        )

        collection.publications[publication_key] = publication

        callbacks.on_publication(file_path)


def _sort_dictionary(dct):
    result = OrderedDict()
    for key in sorted(dct):
        result[key] = dct[key]
    return result


def discover(
    input_directory,
    skip_directories=None,
    callbacks=None,
    date_context=None,
    template_vars=None,
):
    """Discover the collections and publications in the filesystem.

    Parameters
    ----------
    input_directory : Path
        The path to the directory that will be recursively searched.
    skip_directories : Optional[Collection[str]]
        A collection of directory names that should be skipped if discovered.
        If None, no directories will be skipped.
    callbacks : Optional[DiscoverCallbacks]
        Callbacks to be invoked during the discovery. If omitted, no callbacks
        are executed. See :class:`DiscoverCallbacks` for the possible callbacks
        and their arguments.
    date_context : Optional[DateContext]
        A date context used to evaluate smart dates. If ``None``, an empty context is
        used.

    Returns
    -------
    Universe
        The collections and the nested publications and artifacts, contained in
        a :class:`Universe` instance.
    """
    if callbacks is None:
        callbacks = DiscoverCallbacks()

    if date_context is None:
        date_context = DateContext()

    collection_paths, publication_paths = _search_for_collections_and_publications(
        input_directory, skip_directories=skip_directories, callbacks=callbacks
    )

    publication_paths = _sort_dictionary(publication_paths)

    collections = _make_collections(collection_paths, input_directory, callbacks)
    _make_publications(
        publication_paths,
        input_directory,
        collections,
        date_context=date_context,
        callbacks=callbacks,
        template_vars=template_vars,
    )

    return Universe(collections)
