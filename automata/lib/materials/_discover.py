import pathlib
from collections import deque, OrderedDict

import dictconfig
import yaml

from .types import (
    UnbuiltArtifact,
    Publication,
    Collection,
    Universe,
    PublicationSchema,
)
from .exceptions import DiscoveryError
from . import constants


# read_collection_file
# --------------------------------------------------------------------------------------


def read_collection_file(path, vars=None):
    """Read a :class:`Collection` from a yaml file.

    See the documentation for a description of the format of the file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    vars : Optional[dict]
        A dictionary of variables available during interpolation.

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


def _collection_file_schema():
    """The dictconfig schema describing a valid collection file."""
    return {
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


def _resolve_collection_file(raw_contents, external_variables, path):
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
    schema = _collection_file_schema()

    try:
        resolved = dictconfig.resolve(
            raw_contents, schema, external_variables=external_variables
        )
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    _validate_metadata_schema(resolved["publication_schema"]["metadata_schema"], path)

    return resolved


def _validate_metadata_schema(metadata_schema, path):
    if metadata_schema is None:
        return

    try:
        dictconfig.validate_schema({"type": "dict", **metadata_schema})
    except dictconfig.exceptions.InvalidSchemaError as exc:
        raise DiscoveryError(exc, path)


# read_publication_file
# --------------------------------------------------------------------------------------


def read_publication_file(path, publication_schema=None, vars=None, previous=None):
    """Read a :class:`Publication` from a yaml file.

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
    previpus : Publication
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

    resolved = _resolve_publication_file(
        raw_contents, publication_schema, external_variables, path
    )

    # convert each artifact to an Artifact object
    artifacts = {}
    for key, definition in resolved["artifacts"].items():
        # if no file is provided, use the key
        if definition["file"] is None:
            definition["file"] = key

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
            "file": {"type": "string", "nullable": True, "default": None},
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
    default_schema = PublicationSchema(
        required_artifacts=[],
        metadata_schema=None,
        allow_unspecified_artifacts=True,
    )
    return Collection(publication_schema=default_schema, publications={})


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


def _previous_publication(collection):
    """Add the resolved previous publication file to the external_variables."""
    if not collection.publication_schema.is_ordered:
        return

    # the previous publication was just the last one added to collection.publications
    try:
        previous_key = list(collection.publications)[-1]
    except IndexError:
        return

    return collection.publications[previous_key]


def _make_publications(
    publication_paths,
    input_directory,
    collections,
    *,
    callbacks,
    vars,
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
    vars : Optional[dict]
        A dictionary of extra variables to be used during interpolation.

    """
    if vars is None:
        vars = {}

    for path, collection_path in publication_paths.items():
        if collection_path is None:
            collection_key = "default"
            publication_key = str(path.relative_to(input_directory))
        else:
            collection_key = str(collection_path.relative_to(input_directory))
            publication_key = str(path.relative_to(collection_path))

        collection = collections[collection_key]

        previous = _previous_publication(collection)

        file_path = path / constants.PUBLICATION_FILE
        publication = read_publication_file(
            file_path,
            publication_schema=collection.publication_schema,
            vars=vars,
            previous=previous,
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
    vars=None,
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
    vars : Optional[dict]
        A dictionary of extra variables to be available during interpolation.

    Returns
    -------
    Universe
        The collections and the nested publications and artifacts, contained in
        a :class:`Universe` instance.
    """
    if callbacks is None:
        callbacks = DiscoverCallbacks()

    collection_paths, publication_paths = _search_for_collections_and_publications(
        input_directory, skip_directories=skip_directories, callbacks=callbacks
    )

    publication_paths = _sort_dictionary(publication_paths)

    collections = _make_collections(collection_paths, input_directory, callbacks)
    _make_publications(
        publication_paths,
        input_directory,
        collections,
        callbacks=callbacks,
        vars=vars,
    )

    return Universe(collections)
