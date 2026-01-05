"""High-level function for resolving publication files.

Not to be confused with the lower-level resolve() functions for resolving arbitrary
configurations.

"""

import pathlib
from typing import Any

from . import constants
from .config import find_config, read_config
from .materials import (
    Publication,
    UnbuiltArtifact,
    read_collection_file,
    read_publication_file,
)


def _find_parent_collection_root(dir_path: pathlib.Path) -> pathlib.Path | None:
    """Find the parent directory containing a collection.yaml file.

    Searches upward from the given directory to find a collection.yaml file.

    Parameters
    ----------
    dir_path : pathlib.Path
        The directory to start searching from.

    Returns
    -------
    pathlib.Path | None
        The path to the directory containing collection.yaml, or None if not found.

    """
    # We are at the root of the filesystem
    if dir_path == dir_path.parent:
        return None

    if (dir_path / constants.COLLECTION_FILE).is_file():
        return dir_path

    return _find_parent_collection_root(dir_path.parent)


def _find_previous(
    this_publication_path: pathlib.Path, collection_root: pathlib.Path
) -> pathlib.Path | None:
    """Find the previous publication in an ordered collection.

    Parameters
    ----------
    this_publication_path : pathlib.Path
        The path to the current publication.yaml file.
    collection_root : pathlib.Path
        The root directory of the collection.

    Returns
    -------
    pathlib.Path | None
        The path to the previous publication.yaml file, or None if this is the
        first publication.

    """
    all_publications = sorted(collection_root.glob(f"**/{constants.PUBLICATION_FILE}"))
    all_publications = [p.resolve() for p in all_publications]

    try:
        index = all_publications.index(this_publication_path.resolve())
    except ValueError:
        return None

    if index == 0:
        return None
    else:
        return all_publications[index - 1]


def _resolve_publication_file(
    path: pathlib.Path, vars_dict: dict[str, Any]
) -> Publication[UnbuiltArtifact]:
    """Recursively resolve a publication file with schema and previous publication.

    Parameters
    ----------
    path : pathlib.Path
        Path to the publication.yaml file.
    vars_dict : dict[str, Any]
        Variables for interpolation.

    Returns
    -------
    Publication[UnbuiltArtifact]
        The resolved publication.

    """
    # Find the collection that the publication belongs to
    collection_dir = _find_parent_collection_root(path.parent)

    if collection_dir is not None:
        collection = read_collection_file(
            collection_dir / constants.COLLECTION_FILE, vars_dict
        )
        publication_schema = collection.publication_schema

        # Find the previous publication if the collection is ordered
        previous_path = _find_previous(path, collection_dir)
        if previous_path is not None:
            previous = _resolve_publication_file(previous_path, vars_dict)
        else:
            previous = None
    else:
        publication_schema = None
        previous = None

    return read_publication_file(
        path, publication_schema=publication_schema, vars=vars_dict, previous=previous
    )


def resolve(path: pathlib.Path) -> Publication[UnbuiltArtifact]:
    """Resolve a publication.yaml file.

    This high-level function finds the automata.yaml config file, extracts
    variables, finds the parent collection (if any), finds the previous
    publication (if any), and resolves the publication file with all context.

    Parameters
    ----------
    path : pathlib.Path
        Path to the publication.yaml file.

    Returns
    -------
    Publication[UnbuiltArtifact]
        The resolved publication with all artifacts as UnbuiltArtifact objects.

    Raises
    ------
    FileNotFoundError
        If the automata.yaml config file cannot be found.
    Exception
        If there are errors reading the config or resolving the publication.

    """
    # Resolve to absolute path immediately to ensure consistent path operations
    path = path.resolve()

    # Find the automata.yaml config file by searching upwards
    config_path = find_config(path)
    if config_path is None:
        raise FileNotFoundError(
            f"Could not find automata.yaml in {path.parent} or any parent directory."
        )

    # Read config and extract variables
    config = read_config(config_path)
    vars_dict = config.vars

    # Resolve the publication file with schema and previous publication
    return _resolve_publication_file(path, vars_dict)
