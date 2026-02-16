"""Provides discover(), which searches the filesystem for materials."""

import dataclasses
import pathlib
from collections import deque
from typing import Any, Callable, Optional

from automata import constants
from automata.hooks import DiscoverHookArgs, DiscoverHooks

from ..util.yaml import parse_yaml
from ._discover_collection import parse_collection
from ._discover_publication import parse_publication
from ._types import (
    Collection,
    Publication,
    PublicationSchema,
    UnbuiltArtifact,
    Universe,
)
from .exceptions import DiscoveryError

# scanning =============================================================================


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


def find_parent_collection(dir_path: pathlib.Path) -> Optional[pathlib.Path]:
    """Search upward from a directory for a parent collection.

    Starting from ``dir_path``, walks up the directory tree looking for a
    directory that contains a ``collection.yaml`` file.

    Parameters
    ----------
    dir_path : pathlib.Path
        The directory to start searching from. If ``dir_path`` itself contains
        a ``collection.yaml`` file, it is returned immediately.

    Returns
    -------
    Optional[pathlib.Path]
        The path to the collection directory, or ``None`` if no parent
        collection was found.

    """
    current = dir_path
    while current != current.parent:
        if _is_collection(current):
            return current
        current = current.parent
    return None


def _scan_filesystem(
    root_directory: pathlib.Path,
    skip: Optional[Callable[[pathlib.Path], bool]] = None,
    *,
    hooks: DiscoverHooks,
) -> dict[Optional[pathlib.Path], list[pathlib.Path]]:
    """Perform a BFS to find all collections and publications in the filesystem.

    Returns the results grouped by collection: each key is an absolute path to a
    collection directory (or ``None`` for isolated publications), and each value is
    a sorted list of absolute paths to publication directories.

    Parameters
    ----------
    root_directory : pathlib.Path
        Path to the root directory that will be recursively searched.
    skip : Optional[Callable[[Path], bool]]
        A predicate that receives the path to a directory and returns True if it
        should be skipped. If None, no directories are skipped.
    hooks : DiscoverHooks
        Callbacks invoked when interesting things happen.

    Returns
    -------
    Dict[Optional[Path], list[Path]]
        Mapping from collection paths (or None) to sorted lists of publication paths.

    Raises
    ------
    DiscoveryError
        If a nested collection is found.

    """
    queue: deque[tuple[pathlib.Path, Optional[pathlib.Path]]] = deque(
        [(root_directory, None)]
    )

    # The None key collects isolated publications (those not under any collection).
    # Pre-seeding it guarantees the default collection is always present.
    result: dict[Optional[pathlib.Path], list[pathlib.Path]] = {None: []}

    while queue:
        current_path, parent_collection_path = queue.pop()

        if _is_collection(current_path):
            if parent_collection_path is not None:
                raise DiscoveryError("Nested collection found.", current_path)

            result[current_path] = []
            parent_collection_path = current_path

        if _is_publication(current_path):
            result[parent_collection_path].append(current_path)

        for subpath in current_path.iterdir():
            if subpath.is_dir():
                if skip is not None and skip(subpath):
                    hooks.on_discover_skip(DiscoverHookArgs(path=subpath))
                    continue
                queue.append((subpath, parent_collection_path))

    # sort publication paths within each group
    for pub_paths in result.values():
        pub_paths.sort()

    return result


# building collections =================================================================


@dataclasses.dataclass
class _RawPublication:
    """A publication that has been read from YAML but not yet resolved."""

    contents: dict
    workdir: pathlib.Path
    source: pathlib.Path


def _read_yaml(path: pathlib.Path) -> Any:
    """Read and parse a YAML file, wrapping errors in DiscoveryError."""
    try:
        return parse_yaml(path.read_text())
    except Exception as exc:
        raise DiscoveryError(str(exc), path)


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


def _read_publication_files(
    publication_paths: list[pathlib.Path],
    base_dir: pathlib.Path,
) -> dict[str, _RawPublication]:
    """Read publication.yaml files into raw publications.

    Returns a dict mapping publication keys to :class:`_RawPublication`
    objects, each carrying the raw YAML contents along with the workdir and
    source path needed for resolution.

    """
    result: dict[str, _RawPublication] = {}
    for pub_path in publication_paths:
        pub_file_path = pub_path / constants.PUBLICATION_FILE
        raw_contents = _read_yaml(pub_file_path)
        key = str(pub_path.relative_to(base_dir))
        result[key] = _RawPublication(
            contents=raw_contents, workdir=pub_path, source=pub_file_path
        )
    return result


def _init_default_collection(
    publication_paths: list[pathlib.Path],
    root_directory: pathlib.Path,
) -> tuple[str, Collection, dict[str, _RawPublication]]:
    """Set up the default collection for isolated publications.

    The collection will not have any publications attached to it. Those will be added
    later, in _make_collection(), after the publication schema is read and we are ready
    to resolve the publications.

    """
    default_schema = PublicationSchema(
        required_artifacts=[],
        metadata_schema=None,
        allow_unspecified_artifacts=True,
    )
    collection = Collection(publication_schema=default_schema, publications={})
    raw_publications = _read_publication_files(publication_paths, root_directory)
    return "default", collection, raw_publications


def _init_collection_from_file(
    collection_path: pathlib.Path,
    publication_paths: list[pathlib.Path],
    root_directory: pathlib.Path,
    *,
    hooks: DiscoverHooks,
    vars: dict[str, Any],
) -> tuple[str, Collection, dict[str, _RawPublication]]:
    """Set up a collection from a ``collection.yaml`` file.

    Reads the collection file, determines the publication source (inline
    definitions or separate ``publication.yaml`` files), and returns the
    collection key, the empty collection, and the raw publications.

    The collection will not have any publications attached to it. Those will be added
    later, in _make_collection(), after the publication schema is read and we are ready
    to resolve the publications.

    Raises
    ------
    DiscoveryError
        If the collection has both inline and filesystem publications.

    """
    file_path = collection_path / constants.COLLECTION_FILE
    raw_contents = _read_yaml(file_path)
    collection, inline_publications = parse_collection(
        raw_contents, vars=vars, source=file_path
    )
    key = str(collection_path.relative_to(root_directory))
    hooks.on_discover_collection(DiscoverHookArgs(path=file_path))

    if inline_publications is not None and publication_paths:
        raise DiscoveryError(
            "Collection has inline publications in collection.yaml "
            "but publication.yaml files were also found on the "
            "filesystem. Use one or the other, not both.",
            collection_path,
        )

    if inline_publications is not None:
        raw_publications = {
            pub_key: _RawPublication(
                contents=raw_pub,
                workdir=collection_path,
                source=file_path,
            )
            for pub_key, raw_pub in inline_publications.items()
        }
    else:
        raw_publications = _read_publication_files(publication_paths, collection_path)

    return key, collection, raw_publications


def _make_collection(
    collection_path: Optional[pathlib.Path],
    publication_paths: list[pathlib.Path],
    root_directory: pathlib.Path,
    *,
    hooks: DiscoverHooks,
    vars: Optional[dict[str, Any]] = None,
) -> tuple[str, Collection]:
    """Create a Collection with its Publications.

    Publications may come from the filesystem (separate ``publication.yaml``
    files) or from inline definitions within ``collection.yaml``.  If both
    sources are present, a :class:`DiscoveryError` is raised.

    If ``collection_path`` is None, creates the default collection for isolated
    publications.

    """
    if vars is None:
        vars = {}

    # We build a collection in two steps because the publication schema lives in
    # collection.yaml, which may also define publications inline. Step 1 reads the
    # collection file to obtain the schema (without resolving any publications) and
    # gathers the raw publication contents. Step 2 resolves each publication against the
    # schema.
    if collection_path is None:
        key, collection, raw_publications = _init_default_collection(
            publication_paths, root_directory
        )
    else:
        key, collection, raw_publications = _init_collection_from_file(
            collection_path,
            publication_paths,
            root_directory,
            hooks=hooks,
            vars=vars,
        )

    # Step 2: resolve each publication against the schema and populate the collection
    # with the publications
    for pub_key, entry in raw_publications.items():
        previous = _last_publication(collection)
        publication = parse_publication(
            entry.contents,
            workdir=entry.workdir,
            publication_schema=collection.publication_schema,
            vars=vars,
            previous=previous,
            templates=collection.templates,
            source=entry.source,
        )
        collection.publications[pub_key] = publication
        hooks.on_discover_publication(DiscoverHookArgs(path=entry.source, key=pub_key))

    return key, collection


# public API ===========================================================================


def discover(
    root_directory: pathlib.Path,
    skip: Optional[Callable[[pathlib.Path], bool]] = None,
    hooks: Optional[DiscoverHooks] = None,
    vars: Optional[dict[str, Any]] = None,
) -> Universe[UnbuiltArtifact]:
    """Discover the course materials in the filesystem.

    This function recursively searches down from the given root directory for
    collections and publications defined by ``collection.yaml'' and
    ``publication.yaml'' files, respectively. It then reads these files and
    creates a :class:`Universe` object containing all information about the
    discovered course materials.

    Parameters
    ----------
    root_directory : Path
        The path to the root directory that will be recursively searched.
    skip : Optional[Callable[[Path], bool]]
        A predicate that receives the path to a directory and returns True if it should
        be skipped. If None, no directories will be skipped.
    hooks : Optional[DiscoverHooks]
        Callbacks to be invoked during the discovery. If omitted, no hooks are executed.
        See below for the possible hooks and their arguments.
    vars : Optional[dict]
        A dictionary of user-defined variables to be available during interpolation
        within collection.yaml and publication.yaml files. If omitted, no user-defined
        variables will be available.

    Returns
    -------
    Universe
        The discovered course materials, contained in a :class:`Universe`
        instance.

    Notes
    -----

    All of the discovered collections are represented as :class:`Collection` objects.
    All of the discovered publications are represented as :class:`Publication` objects.
    All of the discovered artifacts are represented as :class:`UnbuiltArtifact` objects.

    The returned Universe also contains a "default" collection for publications which
    are not part of any collection.

    Each discovered collection is represented as a :class:`Collection` object within the
    ``._children`` attribute of the Universe. The ``._children`` attribute is a mapping
    from collection keys to Collection objects. A collection's key is the string form of
    its path relative to the input directory.

    Likewise, each discovered publication is represented as a :class:`Publication`
    object within the ``._children`` attribute of the Collection to which it belongs.
    The ``._children`` attribute of a Collection is a mapping from publication keys to
    Publication objects. A publication's key is the string form of its path relative to
    the *collection* to which it belongs.

    """
    if hooks is None:
        hooks = DiscoverHooks()

    scan_result = _scan_filesystem(root_directory, skip=skip, hooks=hooks)

    collections = {}
    for collection_path, publication_paths in scan_result.items():
        key, collection = _make_collection(
            collection_path,
            publication_paths,
            root_directory,
            hooks=hooks,
            vars=vars,
        )
        collections[key] = collection

    return Universe(collections)
