import pathlib
from collections import deque, OrderedDict

import dictconfig
import yaml

from .types import (
    UnbuiltArtifact,
    Publication,
    Collection,
    Universe,
    Schema,
)
from .exceptions import DiscoveryError
from ._validate import _PublicationValidator
from . import constants


# read_collection_file
# --------------------------------------------------------------------------------------


def _collection_file_base_schema():
    return {
        'type': 'dict',
        'required_keys': {
            'schema': {
                    'type': 'dict',
                    'required_keys': {
                        'required_artifacts': {
                                'type': 'list',
                                'element_schema': {'type': 'string'},
                            }
                        },
                    'optional_keys': {
                        'optional_artifacts': {
                                'type': 'list',
                                'element_schema': {'type': 'string'},
                            'default': []
                            },
                        'metadata_schema': {
                                'type': 'dict',
                                'extra_keys_schema': {'type': 'any'},
                                'nullable': True,
                            'default': None
                            },
                        'allow_unspecified_artifacts': {
                            'type': 'boolean',
                            'default': False
                            },
                        'is_ordered': {
                            'type': 'boolean',
                            'default': False
                            },
                        }
                }
            }
        }


def read_collection_file(path, external_variables=None):
    """Read a :class:`Collection` from a yaml file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    external_variables : dict
        A dictionary of external variables available during interpolation.

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
    - is_ordered [optional]
        Is the collection enumerable? If so, set this to True. Defaults to False.
        This must be True in order to use information from previous publications
        in publication.yaml files.

    """
    if external_variables is None:
        external_variables = {}

    with path.open() as fileobj:
        raw_contents = yaml.load(fileobj, Loader=yaml.Loader)

    try:
        resolved = _resolve_collection_file(raw_contents, external_variables, path)
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    schema = Schema(**resolved['schema'])
    return Collection(schema=schema, publications={})


def _resolve_collection_file(raw_contents, external_variables, path):
    """Resolves (interpolates and parses) the raw collection file contents.

    Parameters
    ----------
    raw_contents : dict
        The raw dictionary loaded from the publication file.
    external_variables : Optional[dict]
        A dictionary of external_variables passed to dictconfig and used during
        interpolation.
    path : pathlib.Path
        The path to the collection file being read. Used to format error messages.

    Returns
    -------
    dict
        The resolved dictionary.

    """
    schema = _collection_file_base_schema()

    try:
        resolved = dictconfig.resolve(raw_contents, schema, external_variables=external_variables)
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    _validate_metadata_schema(resolved['schema']['metadata_schema'], path)

    return resolved


def _validate_metadata_schema(metadata_schema, path):
    if metadata_schema is None:
        return

    try:
        dictconfig.validate_schema({
            'type': 'dict',
            **metadata_schema
        })
    except dictconfig.exceptions.SchemaError as exc:
        raise DiscoveryError(exc, path)


# read_publication_file
# --------------------------------------------------------------------------------------


def _publication_file_base_schema():

    artifacts_schema = {
        'type': 'dict',
        'extra_keys_schema': {
            'type': 'dict',
            'optional_keys': {
                'file': {
                    'type': 'string', 'nullable': True,
                    'default': None
                },
                'recipe': {
                    'type': 'string', 'nullable': True,
                    'default': None
                },
                'ready': {
                    'type': 'boolean',
                    'default': True
                },
                'missing_ok': {
                    'type': 'boolean',
                    'default': False
                },
                'release_time': {
                    'type': 'datetime', 'nullable': True,
                    'default': None
                },
            }
        }
    }
    return {
        'type': 'dict',
        'required_keys': {
            'artifacts': artifacts_schema
        },
        'optional_keys': {
            'ready': {
                'default': True,
                'type': 'boolean'
            },
            'release_time': {
                'default': None,
                'type': 'datetime', 'nullable': True
            },
        }
    }

def read_publication_file(path, schema=None, template_vars=None):
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

    # convert each artifact to an Artifact object
    artifacts = {}
    for key, definition in resolved["artifacts"].items():
        # if no file is provided, use the key
        if definition["file"] is None:
            definition["file"] = key

        artifacts[key] = UnbuiltArtifact(workdir=path.parent.absolute(), **definition)

    publication = Publication(
        metadata=resolved['metadata'],
        artifacts=artifacts,
        ready=resolved["ready"],
        release_time=resolved['release_time'],
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
    schema = _publication_file_base_schema()

    if metadata_schema is not None:
        schema['optional_keys']['metadata'] = {
            'type': 'dict',
            **metadata_schema
        }
    else:
        schema['optional_keys']['metadata'] = {
            'type': 'any',
            'default': {}
        }

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


def _add_previous_keys(template_vars, collection):
    """Add the resolved previous publication file to the template_vars."""
    if not collection.schema.is_ordered:
        return

    # the previous publication was just the last one added to collection.publications
    try:
        previous_key = list(collection.publications)[-1]
    except IndexError:
        return

    template_vars['previous'] = collection.publications[previous_key]._deep_asdict()


def _make_publications(
    publication_paths,
    input_directory,
    collections,
    *,
    callbacks,
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
    template_vars : Optional[dict]
        A dictionary of extra variables to be used during interpolation.

    """
    if template_vars is None:
        template_vars = {}

    for path, collection_path in publication_paths.items():
        if collection_path is None:
            collection_key = "default"
            publication_key = str(path.relative_to(input_directory))
        else:
            collection_key = str(collection_path.relative_to(input_directory))
            publication_key = str(path.relative_to(collection_path))

        collection = collections[collection_key]

        _add_previous_keys(template_vars, collection)

        file_path = path / constants.PUBLICATION_FILE
        publication = read_publication_file(
            file_path,
            schema=collection.schema,
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
    template_vars : Optional[dict]
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
        template_vars=template_vars,
    )

    return Universe(collections)
