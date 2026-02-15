"""Provides discover(), which searches the filesystem for materials."""

import pathlib
import typing
from collections import deque
from typing import Any, MutableMapping, Optional

import smartconfig

from automata import constants
from automata.hooks import DiscoverHookArgs, DiscoverHooks

from ..util.resolution import resolve
from ..util.yaml import parse_yaml
from ._types import (
    Collection,
    Publication,
    PublicationSchema,
    UnbuiltArtifact,
    Universe,
)
from .exceptions import DiscoveryError

# Type aliases for raw unresolved data
RawPublication = dict[str, Any]
RawCollection = dict[str, Any]


# schemas ==============================================================================

# Schema for a single artifact within a publication.
ARTIFACT_SCHEMA: dict = {
    "type": "dict",
    "optional_keys": {
        "path": {"type": "string", "nullable": True, "default": None},
        "recipe": {"type": "string", "nullable": True, "default": None},
        "ready": {"type": "boolean", "default": True},
        "missing_ok": {"type": "boolean", "default": False},
        "release_time": {"type": "datetime", "nullable": True, "default": None},
    },
}


def _make_publication_schema(
    publication_schema: Optional[PublicationSchema],
) -> dict:
    """Construct a smartconfig schema for validating and resolving publication data.

    Parameters
    ----------
    publication_schema : Optional[PublicationSchema]
        The schema that describes the necessary artifacts of the publication
        and what metadata it should have. If None, a default schema is assumed.

    Returns
    -------
    dict
        The smartconfig schema for the publication.

    """
    if publication_schema is None:
        publication_schema = PublicationSchema([], allow_unspecified_artifacts=True)

    artifacts_schema: dict[str, Any] = {
        "type": "dict",
        "required_keys": {},
        "optional_keys": {},
    }

    if publication_schema.required_artifacts is not None:
        for artifact_key in publication_schema.required_artifacts:
            artifacts_schema["required_keys"][artifact_key] = ARTIFACT_SCHEMA

    if publication_schema.optional_artifacts is not None:
        for artifact_key in publication_schema.optional_artifacts:
            artifacts_schema["optional_keys"][artifact_key] = ARTIFACT_SCHEMA

    if publication_schema.allow_unspecified_artifacts:
        artifacts_schema["extra_keys_schema"] = ARTIFACT_SCHEMA

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


PUBLICATION_SCHEMA = {
    "type": "dict",
    "required_keys": {
        "artifacts": {
            "type": "dict",
            "extra_keys_schema": ARTIFACT_SCHEMA,
        }
    },
    "optional_keys": {
        "metadata": {"type": "any", "default": {}},
    },
}

COLLECTION_SCHEMA = {
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
    "optional_keys": {
        "publications": {
            "type": "dict",
            "extra_keys_schema": PUBLICATION_SCHEMA,
            "default": None,
            "nullable": True,
        }
    },
}


# Phase A: Scanning ====================================================================


def _is_collection(dirpath: pathlib.Path) -> bool:
    """Determines if the directory at the given path is a collection."""
    return (dirpath / constants.COLLECTION_FILE).is_file()


def _is_publication(dirpath: pathlib.Path) -> bool:
    """Determine if the directory at the given path is a publication."""
    return (dirpath / constants.PUBLICATION_FILE).is_file()


def _scan_filesystem(
    root_directory: pathlib.Path,
    skip_directories: Optional[typing.Collection[str]] = None,
    *,
    hooks: DiscoverHooks,
) -> tuple[list[pathlib.Path], dict[pathlib.Path, Optional[pathlib.Path]]]:
    """Perform a BFS to find all collections and publications in the filesystem.

    Parameters
    ----------
    root_directory : pathlib.Path
        Path to the root directory that will be recursively searched.
    skip_directories : Optional[Collection[str]]
        A collection of folder names that, if found, will be skipped over.
    hooks : DiscoverHooks
        Callbacks invoked when interesting things happen.

    Returns
    -------
    List[Path]
        The path to every collection discovered.
    Mapping[Path, Union[Path, None]]
        A mapping from publication paths to their parent collection paths.
        None means the publication belongs to the "default" collection.

    Raises
    ------
    DiscoveryError
        If a nested collection is found.

    """
    if skip_directories is None:
        skip_directories = set()

    queue: deque[tuple[pathlib.Path, Optional[pathlib.Path]]] = deque(
        [(root_directory, None)]
    )

    collections: list[pathlib.Path] = []
    publications: dict[pathlib.Path, Optional[pathlib.Path]] = {}

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
                    hooks.on_discover_skip(DiscoverHookArgs(path=subpath))
                    continue
                queue.append((subpath, parent_collection_path))

    return collections, publications


def _parse_yaml_file(path: pathlib.Path) -> Any:
    """Parse a YAML file without resolving references."""
    yaml_content = path.read_text()
    try:
        return parse_yaml(yaml_content)
    except Exception as exc:
        raise DiscoveryError(str(exc), path)


def _scan_single_collection(
    collection_path: pathlib.Path,
    publication_paths: dict[pathlib.Path, Optional[pathlib.Path]],
    root_directory: pathlib.Path,
) -> tuple[str, RawCollection]:
    """Scan a single collection and its publications without resolving.

    Parameters
    ----------
    collection_path : pathlib.Path
        Path to the collection directory (containing collection.yaml).
    publication_paths : dict[pathlib.Path, pathlib.Path]
        Mapping from publication directory paths to their collection directory paths.
    root_directory : pathlib.Path
        Root directory for computing relative keys.

    Returns
    -------
    tuple[str, RawCollection]
        The collection key and raw unresolved collection data.

    Raises
    ------
    DiscoveryError
        If both inline publications and separate publication.yaml files exist.

    """
    collection_file = collection_path / constants.COLLECTION_FILE
    raw_yaml = _parse_yaml_file(collection_file)

    # Extract publication_schema (will be resolved later)
    publication_schema_raw = raw_yaml.get("publication_schema", {})

    # Check for inline publications
    inline_publications = raw_yaml.get("publications")

    # Find separate publication files for this collection
    separate_pub_paths = [
        pub_path
        for pub_path, col_path in publication_paths.items()
        if col_path == collection_path
    ]

    # Validate: can't have both inline and separate
    if inline_publications is not None and separate_pub_paths:
        raise DiscoveryError(
            "Collection has both inline 'publications:' key and separate "
            "publication.yaml files. Use one approach, not both.",
            collection_file,
        )

    # Gather publications
    publications: dict[str, RawPublication] = {}

    if inline_publications is not None:
        # Use inline publications
        for pub_key, pub_data in inline_publications.items():
            pub_data = dict(pub_data) if pub_data else {}
            pub_data["_path"] = collection_file
            publications[pub_key] = pub_data
    else:
        # Use separate publication.yaml files
        for pub_path in sorted(separate_pub_paths):
            pub_file = pub_path / constants.PUBLICATION_FILE
            pub_data = _parse_yaml_file(pub_file)
            pub_data["_path"] = pub_file
            pub_key = str(pub_path.relative_to(collection_path))
            publications[pub_key] = pub_data

    collection_key = str(collection_path.relative_to(root_directory))

    return collection_key, RawCollection(
        publication_schema=publication_schema_raw,
        publications=publications,
        _path=collection_file,
    )


def _scan_default_collection(
    publication_paths: dict[pathlib.Path, Optional[pathlib.Path]],
    root_directory: pathlib.Path,
) -> RawCollection:
    """Create a "default" collection for orphan publications.

    Parameters
    ----------
    publication_paths : dict[pathlib.Path, Optional[pathlib.Path]]
        Mapping from publication paths to their parent collection paths.
    root_directory : pathlib.Path
        Root directory for computing relative keys.

    Returns
    -------
    RawCollection
        Raw collection data for the default collection.

    """
    # Find publications without a parent collection
    orphan_pubs = [
        pub_path for pub_path, col_path in publication_paths.items() if col_path is None
    ]

    publications: dict[str, RawPublication] = {}
    for pub_path in sorted(orphan_pubs):
        pub_file = pub_path / constants.PUBLICATION_FILE
        pub_data = _parse_yaml_file(pub_file)
        pub_data["_path"] = pub_file
        pub_key = str(pub_path.relative_to(root_directory))
        publications[pub_key] = pub_data

    return RawCollection(
        publication_schema={
            "required_artifacts": [],
            "allow_unspecified_artifacts": True,
        },
        publications=publications,
        _path=root_directory,
    )


def _scan_collections(
    root_directory: pathlib.Path,
    skip_directories: Optional[typing.Collection[str]],
    hooks: DiscoverHooks,
) -> dict[str, RawCollection]:
    """Phase A: Scan filesystem and parse YAML without resolving.

    Returns
    -------
    dict[str, RawCollection]
        Mapping from collection keys to raw unresolved collection data.

    """
    collection_paths, publication_paths = _scan_filesystem(
        root_directory, skip_directories, hooks=hooks
    )

    raw_collections: dict[str, RawCollection] = {}

    # Process each collection
    for col_path in collection_paths:
        key, raw_col = _scan_single_collection(
            col_path, publication_paths, root_directory
        )
        raw_collections[key] = raw_col
        hooks.on_discover_collection(
            DiscoverHookArgs(path=col_path / constants.COLLECTION_FILE)
        )

    # Add default collection for orphan publications
    raw_collections["default"] = _scan_default_collection(
        publication_paths, root_directory
    )

    return raw_collections


# Phase B: Wrapping with __let__ =======================================================


def _wrap_publication_with_let(pub_data: dict) -> dict:
    """Wrap a publication dict with __let__ for this self-reference.

    Parameters
    ----------
    pub_data : dict
        The raw publication data (without _path).

    Returns
    -------
    dict
        The publication wrapped with __let__ for ${this} references.

    Note
    ----
    The ${previous} reference is handled separately by passing it as a
    global variable during resolution, since smartconfig's __previous__
    only works inside lists, not dicts.

    """
    return {"__let__": {"references": {"this": "__this__"}, "in": pub_data}}


# Phase C: Resolution ==================================================================


def _validate_metadata_schema(
    metadata_schema: Optional[typing.Mapping[str, str]], path: pathlib.Path
) -> None:
    """Ensures that the publication metadata schema provided is valid."""
    if metadata_schema is None:
        return

    try:
        smartconfig.validate_schema({"type": "dict", **metadata_schema})
    except smartconfig.exceptions.InvalidSchemaError as exc:
        raise DiscoveryError(exc, path)


def _resolve_collection_schema(
    raw_schema: dict,
    vars: Optional[dict[str, Any]],
    path: pathlib.Path,
) -> PublicationSchema:
    """Resolve a collection's publication_schema and return PublicationSchema."""
    # Wrap with "this" for self-references
    combined: Any = {"this": {"publication_schema": raw_schema}}

    combined_schema: Any = {
        "type": "dict",
        "required_keys": {
            "this": COLLECTION_SCHEMA,
        },
    }

    try:
        resolved = resolve(
            combined,
            combined_schema,
            global_variables={"vars": vars if vars is not None else {}},
        )
    except smartconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    schema_dict = resolved["this"]["publication_schema"]
    _validate_metadata_schema(schema_dict.get("metadata_schema"), path)

    return PublicationSchema(**schema_dict)


def _resolve_publications(
    wrapped_publications: dict[str, dict],
    publication_schema: PublicationSchema,
    raw_publications: dict[str, RawPublication],
    vars: Optional[dict[str, Any]],
) -> MutableMapping[str, Publication[UnbuiltArtifact]]:
    """Resolve all wrapped publications in a collection.

    Parameters
    ----------
    wrapped_publications : dict[str, dict]
        Publications wrapped with __let__ for resolution.
    publication_schema : PublicationSchema
        The resolved publication schema.
    raw_publications : dict[str, RawPublication]
        Original raw publication data (for _path).
    vars : Optional[dict[str, Any]]
        User-provided variables.

    Returns
    -------
    MutableMapping[str, Publication[UnbuiltArtifact]]
        Resolved publications.

    """
    schema = _make_publication_schema(publication_schema)
    publications: MutableMapping[str, Publication[UnbuiltArtifact]] = {}

    pub_keys = list(wrapped_publications.keys())
    previous_resolved: Optional[dict] = None

    for pub_key in pub_keys:
        wrapped = wrapped_publications[pub_key]
        raw = raw_publications[pub_key]
        path = raw.get("_path", pathlib.Path("unknown"))

        # Build combined dict for resolution
        combined_dict: dict = {"this": wrapped}
        combined_schema: dict = {
            "type": "dict",
            "required_keys": {"this": schema},
            "optional_keys": {},
        }

        global_variables: dict = {"vars": vars if vars is not None else {}}

        if previous_resolved is not None:
            combined_dict["previous"] = previous_resolved
            combined_schema["optional_keys"]["previous"] = {"type": "any"}

        try:
            resolved = resolve(
                combined_dict, combined_schema, global_variables=global_variables
            )
        except smartconfig.exceptions.ResolutionError as exc:
            raise DiscoveryError(str(exc), path)

        resolved_pub = resolved["this"]

        # Convert artifacts to UnbuiltArtifact objects
        if isinstance(path, pathlib.Path):
            workdir = path.parent.absolute()
        else:
            workdir = pathlib.Path.cwd()
        artifacts: MutableMapping[str, UnbuiltArtifact] = {}

        for artifact_key, definition in resolved_pub["artifacts"].items():
            if definition["path"] is None:
                definition["path"] = artifact_key
            artifacts[artifact_key] = UnbuiltArtifact(workdir=workdir, **definition)

        publication = Publication[UnbuiltArtifact](
            metadata=resolved_pub["metadata"],
            artifacts=artifacts,
        )

        publications[pub_key] = publication
        previous_resolved = publication._deep_asdict()

    return publications


def _resolve_universe(
    raw_collections: dict[str, RawCollection],
    vars: Optional[dict[str, Any]],
    hooks: DiscoverHooks,
) -> Universe[UnbuiltArtifact]:
    """Phase B+C: Wrap with __let__, resolve, and build Universe.

    Parameters
    ----------
    raw_collections : dict[str, RawCollection]
        Mapping from collection keys to raw unresolved collection data.
    vars : Optional[dict[str, Any]]
        User-provided variables.
    hooks : DiscoverHooks
        Hooks for discovery events.

    Returns
    -------
    Universe[UnbuiltArtifact]
        The fully resolved universe.

    """
    collections: MutableMapping[str, Collection[UnbuiltArtifact]] = {}

    for col_key, raw_col in raw_collections.items():
        collections[col_key] = _resolve_single_collection(raw_col, vars)

        # Fire hooks for each publication
        for pub_key in raw_col["publications"]:
            raw_pub = raw_col["publications"][pub_key]
            pub_path = raw_pub.get("_path")
            if pub_path is not None:
                hooks.on_discover_publication(DiscoverHookArgs(path=pub_path))

    return Universe(collections)


# Public API ===========================================================================


def discover(
    root_directory: pathlib.Path,
    skip_directories: Optional[typing.Collection[str]] = None,
    hooks: Optional[DiscoverHooks] = None,
    vars: Optional[dict[str, Any]] = None,
) -> Universe[UnbuiltArtifact]:
    """Discover the course materials in the filesystem.

    This function recursively searches down from the given root directory for
    collections and publications defined by ``collection.yaml`` and
    ``publication.yaml`` files, respectively. It then reads these files and
    creates a :class:`Universe` object containing all information about the
    discovered course materials.

    Publications can be defined in two ways:
    1. **Separate files**: Each publication has its own ``publication.yaml`` file
       in a subdirectory under the collection.
    2. **Inline**: Publications are defined directly in the ``publications:`` key
       of the collection's ``collection.yaml`` file.

    A collection cannot use both approaches simultaneously - this will raise an error.

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
    hooks : Optional[DiscoverHooks]
        Callbacks to be invoked during the discovery. If omitted, no hooks
        are executed. See below for the possible hooks and their arguments.
    vars : Optional[dict]
        A dictionary of user-defined variables to be available during
        interpolation.

    Returns
    -------
    Universe
        The discovered course materials, contained in a :class:`Universe`
        instance.

    """
    if hooks is None:
        hooks = DiscoverHooks()

    # Phase A: Scan filesystem and parse YAML without resolving
    raw_collections = _scan_collections(root_directory, skip_directories, hooks)

    # Phase B+C: Wrap with __let__, resolve, and build Universe
    return _resolve_universe(raw_collections, vars, hooks)


# Helpers for read_collection_file and read_publication_file ===========================


def _scan_collection_from_file(
    collection_file: pathlib.Path,
) -> RawCollection:
    """Scan a single collection.yaml file and its publications.

    This is used by read_collection_file() to handle both inline and
    separate publication.yaml files.
    """
    collection_path = collection_file.parent

    # Build publication_paths by scanning subdirectories
    publication_paths: dict[pathlib.Path, Optional[pathlib.Path]] = {}
    for subpath in collection_path.iterdir():
        if subpath.is_dir() and _is_publication(subpath):
            publication_paths[subpath] = collection_path

    _, raw_col = _scan_single_collection(
        collection_path, publication_paths, collection_path
    )
    return raw_col


def _resolve_single_collection(
    raw_col: RawCollection,
    vars: Optional[dict[str, Any]],
) -> Collection[UnbuiltArtifact]:
    """Resolve a single collection from raw data.

    Used by read_collection_file().
    """
    path = raw_col["_path"]

    # Resolve the publication schema
    pub_schema = _resolve_collection_schema(raw_col["publication_schema"], vars, path)

    # Wrap and resolve publications
    wrapped_publications = {}
    pub_keys = list(raw_col["publications"].keys())

    for pub_key in pub_keys:
        pub_data = dict(raw_col["publications"][pub_key])
        pub_data.pop("_path", None)
        wrapped_publications[pub_key] = _wrap_publication_with_let(pub_data)

    publications = _resolve_publications(
        wrapped_publications, pub_schema, raw_col["publications"], vars
    )

    return Collection(publication_schema=pub_schema, publications=publications)


def _find_parent_collection(pub_path: pathlib.Path) -> Optional[pathlib.Path]:
    """Find the parent collection.yaml for a publication.yaml file.

    Walks up the directory tree looking for collection.yaml.

    Returns
    -------
    Optional[pathlib.Path]
        Path to the collection.yaml file, or None if not found.

    """
    current = pub_path.parent
    while current != current.parent:
        collection_file = current / constants.COLLECTION_FILE
        if collection_file.is_file():
            return collection_file
        current = current.parent
    return None


def _get_publication_key_from_path(
    pub_file: pathlib.Path,
    collection_file: pathlib.Path,
) -> str:
    """Get the publication key from its path relative to the collection."""
    pub_dir = pub_file.parent
    collection_dir = collection_file.parent
    return str(pub_dir.relative_to(collection_dir))
