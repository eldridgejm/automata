"""Provides discover(), which searches the filesystem for materials."""

import pathlib
import typing
from collections import OrderedDict, deque
from typing import Any, Dict, Optional

from automata import constants

from ..hooks._base import Registry, ResolveOverrides, define_hook
from ._read_collection_file import read_collection_file
from ._read_publication_file import read_publication_file
from ._types import (
    Collection,
    Publication,
    PublicationSchema,
    UnbuiltArtifact,
    Universe,
)
from .exceptions import DiscoveryError

# =============================================================================
# Hook Definitions
# =============================================================================


@define_hook("materials.discover:on_collection")
def DiscoverOnCollectionHook(path: pathlib.Path, collection: Collection) -> None:
    """Called when a collection is discovered.

    Parameters
    ----------
    path : Path
        Path to the collection.yaml file.
    collection : Collection
        The discovered collection.

    """
    ...


@define_hook("materials.discover:on_publication")
def DiscoverOnPublicationHook(path: pathlib.Path, publication: Publication) -> None:
    """Called when a publication is discovered.

    Parameters
    ----------
    path : Path
        Path to the publication.yaml file.
    publication : Publication
        The discovered publication.

    """
    ...


@define_hook("materials.discover:on_skip")
def DiscoverOnSkipHook(path: pathlib.Path) -> None:
    """Called when a directory is skipped during discovery.

    Parameters
    ----------
    path : Path
        Path to the skipped directory.

    """
    ...


@define_hook("pre_resolve")
def PreResolveHook(call_site: str, path: pathlib.Path) -> ResolveOverrides | None:
    """Called before resolve() is called.

    Can provide extra functions/variables for resolution.

    Parameters
    ----------
    call_site : str
        Identifier for where resolve() is being called from.
    path : Path
        Path to the file being resolved.

    Returns
    -------
    ResolveOverrides | None
        Overrides to apply, or None for no overrides.

    """
    ...


def _merge_resolve_results(
    results: list[ResolveOverrides | None],
) -> ResolveOverrides | None:
    """Merge results from multiple hooks, skipping None values."""
    merged = ResolveOverrides()
    for result in results:
        if result is not None:
            merged = merged.merge(result)
    return merged


PreResolveHook.reduce_results = _merge_resolve_results


# =============================================================================
# Helper Functions
# =============================================================================


def _is_collection(dirpath: pathlib.Path) -> bool:
    """Determines if the directory at the given path is a collection.

    It does this by checking to see if collection.yaml exists at the path.

    Parameters
    ----------
    dirpath : pathlib.Path
        The path to a directory to check.

    """
    return (dirpath / constants.COLLECTION_FILE).is_file()


def _is_publication(dirpath: pathlib.Path) -> bool:
    """Determine if the directory at the given path is a publication.

    It does this by checking to see if publication.yaml exists at the path.

    Parameters
    ----------
    dirpath : pathlib.Path
        The path to a directory to check.

    """
    return (dirpath / constants.PUBLICATION_FILE).is_file()


def _search_for_collections_and_publications(
    root_directory: pathlib.Path,
    skip_directories: Optional[typing.Collection[str]] = None,
    *,
    hooks: Registry | None = None,
):
    """Perform a BFS to find all collections and publications in the filesystem.

    Parameters
    ----------
    root_directory : pathlib.Path
        Path to the root directory that will be recursively searched.
    skip_directories : Optional[Collection[str]]
        A collection of folder names that, if found, will be skipped over. If None,
        every folder is searched.
    hooks : Registry | None
        Hooks to invoke during discovery.

    Returns
    -------
    List[Path]
        The path to every collection discovered. The "default" collection is
        not included.
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

    queue = deque([(root_directory, None)])

    collections = []
    publications = {}

    while queue:
        current_path, parent_collection_path = queue.pop()

        if _is_collection(current_path):
            if parent_collection_path is not None:
                raise DiscoveryError("Nested collection found.", current_path)

            collections.append(current_path)
            parent_collection_path = current_path

        if _is_publication(current_path):
            publications[current_path] = parent_collection_path

        for subpath in current_path.iterdir():
            if subpath.is_dir():
                if subpath.name in skip_directories:
                    DiscoverOnSkipHook.execute(hooks, {"path": subpath})
                    continue
                queue.append((subpath, parent_collection_path))  # type: ignore

    return collections, publications


def _make_default_collection() -> Collection:
    """Create a "default" collection."""
    default_schema = PublicationSchema(
        required_artifacts=[],
        metadata_schema=None,
        allow_unspecified_artifacts=True,
    )
    return Collection(publication_schema=default_schema, publications={})


def _make_collections(
    collection_paths: typing.Collection[pathlib.Path],
    root_directory,
    vars: Optional[Dict[str, Any]] = None,
    hooks: Registry | None = None,
) -> typing.MutableMapping[str, Collection]:
    """Given a collection of paths to collections, create Collection objects.

    In other words, this function reads the collection.yaml files and creates
    Collection objects from them. It is a relatively thin wrapper around
    :func:`read_collection_file`. Beyond reading the collection files, this
    function assigns each collection a key, which is the string form of the
    path relative to the input directory. It also adds a "default" collection
    to the output for publications that are not part of any collection.

    Parameters
    ----------
    collection_paths : Collection[pathlib.Path]
        A collection containing paths to directories representing collections.
    root_directory : Path
        Path to the root directory containing all course materials. All collection keys
        will be relative to this path.
    vars : Optional[dict]
        A dictionary of extra variables to be used during interpolation of fields in
        collection.yaml.
    hooks : Registry | None
        Hooks to invoke during discovery.

    Returns
    -------
    Mapping[str, Collection]
        A mapping from collection keys to new Collection objects. A collection's key is
        the string form of its path relative to the input directory.

    """
    collections = {}
    for path in collection_paths:
        file_path = path / constants.COLLECTION_FILE

        collection = read_collection_file(file_path, vars=vars)

        key = str(path.relative_to(root_directory))
        collections[key] = collection

        DiscoverOnCollectionHook.execute(
            hooks, {"path": file_path, "collection": collection}
        )

    collections["default"] = _make_default_collection()
    return collections


def _last_publication(collection: Collection) -> Optional[Publication]:
    """Finds the last publication in an (ordered) collection.

    Returns
    -------
    Optional[Publication]
        The last publication, if it exists. If the collection is unordered,
        this function returns None. If there is no last publication, as is the
        case when the collection is empty, this function also returns None.

    """
    if not collection.publication_schema.is_ordered:
        return None

    try:
        key_of_last = list(collection.publications)[-1]
    except IndexError:
        return None

    return collection.publications[key_of_last]


def _make_publications(
    publication_paths: typing.Mapping[pathlib.Path, typing.Optional[pathlib.Path]],
    root_directory: pathlib.Path,
    collections: typing.MutableMapping[str, Collection],
    *,
    vars: Optional[Dict[str, Any]] = None,
    hooks: Registry | None = None,
) -> None:
    """Given a collection of paths to publications, create Publication objects.

    Parameters
    ----------
    publication_paths : Mapping[Path, Union[Path, None]]
        Mapping from publication paths to the paths of the collections containing them
        (or ``None`` if the publication is part of the "default" collection.
    root_directory : Path
        Path to the root directory containing all course materials. All publication keys
        will be relative to this path.
    collections : MutableMapping[str, Collection]
        A mapping from collection keys to Collection objects. The newly-created
        Publication objects will be added to these Collection objects in-place.
    vars : Optional[dict]
        A dictionary of extra variables to be used during interpolation of fields in
        publication.yaml.
    hooks : Registry | None
        Hooks to invoke during discovery.

    Returns
    -------
    None
        This function has no return value. Instead, the created Publication
        objects are added to the collections passed to this function in the
        `collections` parameter.

    """
    if vars is None:
        vars = {}

    for path, collection_path in publication_paths.items():
        if collection_path is None:
            collection_key = "default"
            publication_key = str(path.relative_to(root_directory))
        else:
            collection_key = str(collection_path.relative_to(root_directory))
            publication_key = str(path.relative_to(collection_path))

        collection = collections[collection_key]

        previous = _last_publication(collection)

        file_path = path / constants.PUBLICATION_FILE

        # Execute pre_resolve hooks to get additional functions
        pre_resolve_results = PreResolveHook.execute(
            hooks, {"call_site": "publication", "path": file_path}
        )
        overrides = PreResolveHook.reduce_results(pre_resolve_results)
        functions = overrides.functions if overrides and overrides.functions else None

        publication = read_publication_file(
            file_path,
            publication_schema=collection.publication_schema,
            vars=vars,
            previous=previous,
            functions=functions,
        )

        collection.publications[publication_key] = publication

        DiscoverOnPublicationHook.execute(
            hooks, {"path": file_path, "publication": publication}
        )


def _sort_dictionary(dct) -> OrderedDict:
    """Utility function that sorts a dictionary by its keys."""
    result = OrderedDict()
    for key in sorted(dct):
        result[key] = dct[key]
    return result


# =============================================================================
# discover()
# =============================================================================


def discover(
    root_directory: pathlib.Path,
    skip_directories: Optional[typing.Collection[str]] = None,
    vars: Optional[Dict[str, Any]] = None,
    hooks: Registry | None = None,
) -> Universe[UnbuiltArtifact]:
    """Discover the course materials in the filesystem.

    This function recursively searches down from the given root directory for
    collections and publications defined by ``collection.yaml'' and
    ``publication.yaml'' files, respectively. It then reads these files and
    creates a :class:`Universe` object containing all information about the
    discovered course materials.

    All of the discovered collections are represented as :class:`Collection`
    objects. All of the discovered publications are represented as
    :class:`Publication` objects. All of the discovered artifacts are
    represented as :class:`UnbuiltArtifact` objects.

    The returned Universe also contains a "default" collection for publications
    which are not part of any collection.

    Each discovered collection is represented as a :class:`Collection` object
    within the ``._children`` attribute of the Universe. The ``._children``
    attribute is a mapping from collection keys to Collection objects. A
    collection's key is the string form of its path relative to the input
    directory.

    Likewise, each discovered publication is represented as a
    :class:`Publication` object within the ``._children`` attribute of the
    Collection to which it belongs. The ``._children`` attribute of a
    Collection is a mapping from publication keys to Publication objects. A
    publication's key is the string form of its path relative to the
    *collection* to which it belongs.

    Parameters
    ----------
    root_directory : Path
        The path to the root directory that will be recursively searched.
    skip_directories : Optional[Collection[str]]
        A collection of directory names that should be skipped if discovered.
        If None, no directories will be skipped.
    vars : Optional[dict]
        A dictionary of user-defined variables to be available during
        interpolation. Passed to :func:`read_publication_file` and
        :func:`read_collection_file`.
    hooks : Registry | None
        Hooks to be invoked during the discovery. Supports:
        - ``materials.discover:on_collection``
        - ``materials.discover:on_publication``
        - ``materials.discover:on_skip``

    Returns
    -------
    Universe
        The discovered course materials, contained in a :class:`Universe`
        instance.

    """
    collection_paths, publication_paths = _search_for_collections_and_publications(
        root_directory,
        skip_directories=skip_directories,
        hooks=hooks,
    )

    publication_paths = _sort_dictionary(publication_paths)

    collections = _make_collections(
        collection_paths,
        root_directory,
        vars=vars,
        hooks=hooks,
    )
    _make_publications(
        publication_paths,
        root_directory,
        collections,
        vars=vars,
        hooks=hooks,
    )

    return Universe(collections)
