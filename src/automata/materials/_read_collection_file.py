"""Provides read_collection_file(), which reads a Collection from a collection.yaml."""

import pathlib
from typing import Any, Mapping, Optional

from ._discover import _resolve_single_collection, _scan_collection_from_file
from ._types import Collection, UnbuiltArtifact


def read_collection_file(
    path: pathlib.Path, vars: Optional[Mapping[str, Any]] = None
) -> Collection[UnbuiltArtifact]:
    """Reads a :class:`types.Collection` from a ``collection.yaml`` file.

    This function reads the collection file and resolves all publications,
    whether they are defined inline in the collection file or in separate
    ``publication.yaml`` files in subdirectories.

    For inline publications, the ``publications:`` key in the collection file
    should contain a dict mapping publication keys to publication definitions.

    For separate publications, each subdirectory containing a ``publication.yaml``
    file is treated as a publication.

    The publications are fully resolved, including ``${this}`` self-references
    and ``${previous}`` references (for ordered collections).

    Parameters
    ----------
    path : pathlib.Path
        Path to the ``collection.yaml`` file.
    vars : Optional[Mapping[str, Any]]
        A dictionary of variables available during interpolation through the
        ``${vars}`` variable. If None, no variables will be made available.

    Returns
    -------
    Collection
        The collection object with all its publications resolved.

    Raises
    ------
    DiscoveryError
        If the collection file is invalid or cannot be resolved.

    """
    vars_dict = dict(vars) if vars is not None else None

    # Scan the collection file (handles both inline and separate publications)
    raw_col = _scan_collection_from_file(path)

    # Resolve the collection (wraps with __let__ for this/previous)
    return _resolve_single_collection(raw_col, vars_dict)
