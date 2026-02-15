"""Reads a Publication from a publication.yaml file."""

import pathlib
from typing import Any, Mapping, Optional

from ._discover import (
    _find_parent_collection,
    _get_publication_key_from_path,
    _parse_yaml_file,
    _resolve_publications,
    _resolve_single_collection,
    _scan_collection_from_file,
    _wrap_publication_with_let,
)
from ._types import Publication, PublicationSchema, UnbuiltArtifact
from .exceptions import DiscoveryError


def read_publication_file(
    path: pathlib.Path,
    publication_schema: Optional[PublicationSchema] = None,
    vars: Optional[Mapping[str, Any]] = None,
) -> Publication[UnbuiltArtifact]:
    """Reads a :class:`types.Publication` from a ``publication.yaml`` file.

    This function resolves the publication file, including ``${this}`` self-references.
    If the publication is part of an ordered collection, ``${previous}`` references
    are also resolved by reading the entire parent collection.

    Parameters
    ----------
    path : pathlib.Path
        Path to the ``publication.yaml`` file.
    publication_schema : Optional[PublicationSchema]
        A schema that describes the necessary artifacts of the publication and
        what metadata it should have. If `None`, the schema from the parent
        collection is used (if available). If no parent collection exists,
        only very basic validation is done.
    vars : Optional[Mapping[str, Any]]
        A dictionary of variables that will be available during interpolation
        of the publication file through the ``${vars}`` variable. If None, no
        variables will be available. Default: None.

    Returns
    -------
    Publication
        The publication, along with its artifacts as :class:`UnbuiltArtifact` objects.

    Raises
    ------
    DiscoveryError
        If the publication file's contents are invalid.

    Notes
    -----

    The file should have a "metadata" key whose value is a dictionary
    of metadata. It should also have an "artifacts" key whose value is a
    dictionary mapping artifact names to artifact definitions.

    If the publication is part of an ordered collection and uses ``${previous}``
    references, the entire collection must be resolved to correctly compute
    the previous publication's values. This is done automatically.

    **Breaking change from previous versions:** The ``previous`` parameter has
    been removed. Previous publication references are now computed automatically
    by resolving the parent collection.

    """
    vars_dict = dict(vars) if vars is not None else {}

    # Try to find the parent collection
    collection_file = _find_parent_collection(path)

    if collection_file is not None:
        # Resolve via the parent collection (handles ${previous} automatically)
        raw_col = _scan_collection_from_file(collection_file)
        collection = _resolve_single_collection(raw_col, vars_dict)

        # Find this publication in the resolved collection
        pub_key = _get_publication_key_from_path(path, collection_file)

        if pub_key not in collection.publications:
            raise DiscoveryError(
                f"Publication '{pub_key}' not found in parent collection.",
                path,
            )

        return collection.publications[pub_key]
    else:
        # No parent collection - resolve standalone
        return _resolve_standalone_publication(path, publication_schema, vars_dict)


def _resolve_standalone_publication(
    path: pathlib.Path,
    publication_schema: Optional[PublicationSchema],
    vars: dict[str, Any],
) -> Publication[UnbuiltArtifact]:
    """Resolve a publication that is not part of any collection.

    This is used for publications in the "default" collection or when
    read_publication_file is called on a file without a parent collection.
    """
    raw_contents = _parse_yaml_file(path)

    if publication_schema is None:
        publication_schema = PublicationSchema([], allow_unspecified_artifacts=True)

    # Prepare raw data with _path for _resolve_publications
    raw_with_path = dict(raw_contents)
    raw_with_path["_path"] = path

    # Wrap with __let__ for ${this} self-reference
    wrapped = _wrap_publication_with_let(raw_contents)

    publications = _resolve_publications(
        wrapped_publications={"_standalone": wrapped},
        publication_schema=publication_schema,
        raw_publications={"_standalone": raw_with_path},
        vars=vars,
    )

    return publications["_standalone"]
