"""Resolve a publication.yaml using the automata.yaml config for context.

Reads the project config, extracts variables, and uses discover() to produce
a fully-resolved Publication. Used by the CLI entry point.
"""

import pathlib

from .config import find_config, read_config
from .materials import (
    Publication,
    UnbuiltArtifact,
    discover,
    find_parent_collection,
)


def resolve(path: pathlib.Path) -> Publication[UnbuiltArtifact]:
    """Resolve a publication.yaml file.

    This high-level function finds the automata.yaml config file, extracts
    variables, and resolves the publication file with all context.

    Finds the parent collection by searching upward for collection.yaml,
    calls discover() on the appropriate root, then extracts the specific
    publication. If no parent collection exists, discovers from the
    publication's own directory and extracts from the default collection.

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

    """
    path = path.resolve()

    config_path = find_config(path)
    if config_path is None:
        raise FileNotFoundError(
            f"Could not find automata.yaml in {path.parent} or any parent directory."
        )

    config = read_config(config_path)
    vars = config.vars

    pub_dir = path.parent
    collection_dir = find_parent_collection(pub_dir)

    if collection_dir is not None:
        universe = discover(collection_dir, vars=vars)
        collection = universe.collections["."]
        pub_key = str(pub_dir.relative_to(collection_dir))
        return collection.publications[pub_key]
    else:
        universe = discover(pub_dir, vars=vars)
        return universe.collections["default"].publications["."]
