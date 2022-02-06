import pathlib
from collections import deque, OrderedDict
import yaml

from ._types import (
    UnbuiltArtifact,
    Publication,
    Collection,
    Universe,
)
from ._io import read_collection_file, read_publication_file
from .exceptions import DiscoveryError

# the file used to define a collection
COLLECTION_FILE = "collection.yaml"

# the file used to define a publication and its artifacts
PUBLICATION_FILE = "publication.yaml"

import dictconfig

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
    return (path / COLLECTION_FILE).is_file()


def _is_publication(path):
    """Determine if the path is a publication."""
    return (path / PUBLICATION_FILE).is_file()


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
    default_schema = dict(
        required_artifacts=[],
        metadata_schema=None,
        allow_unspecified_artifacts=True,
    )
    return Collection(publication_spec=default_schema, publications={})


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
        file_path = path / COLLECTION_FILE

        collection_dct = read_collection_file(file_path)
        collection = Collection(**collection_dct, publications={})

        key = str(path.relative_to(input_directory))
        collections[key] = collection

        callbacks.on_collection(file_path)

    collections["default"] = _make_default_collection()
    return collections


def _previous_publication(collection):
    """Add the resolved previous publication file to the external_variables."""
    if not collection.ordered:
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

        file_path = path / PUBLICATION_FILE
        publication_dct = read_publication_file(
            file_path,
            publication_spec=collection.publication_spec,
            vars=vars,
            previous=previous,
        )

        for key, artifact_dct in publication_dct['artifacts'].items():
            artifact = UnbuiltArtifact(**artifact_dct, workdir=path)
            publication_dct['artifacts'][key] = artifact

        publication = Publication(**publication_dct)

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
