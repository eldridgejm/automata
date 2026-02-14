"""Reads a Publication from a publication.yaml file."""

import pathlib
from typing import Any, Mapping, MutableMapping, Optional

import smartconfig

from ..util.resolution import resolve
from ..util.yaml import parse_yaml
from ._discover import (
    _find_parent_collection,
    _get_publication_key_from_path,
    _make_publication_schema,
    _resolve_single_collection,
    _scan_collection_from_file,
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
    yaml_content = path.read_text()
    try:
        raw_contents = parse_yaml(yaml_content)
    except Exception as exc:
        raise DiscoveryError(str(exc), path)

    schema = _make_publication_schema(publication_schema)

    # Wrap with __let__ for this self-reference
    wrapped = {
        "__let__": {
            "references": {"this": "__this__"},
            "in": raw_contents,
        }
    }

    combined_dict: dict[str, Any] = {"this": wrapped}
    combined_schema: dict[str, Any] = {
        "type": "dict",
        "required_keys": {"this": schema},
    }

    global_variables: dict[str, Any] = {"vars": vars}

    try:
        resolved = resolve(
            combined_dict, combined_schema, global_variables=global_variables
        )
    except smartconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    resolved_pub = resolved["this"]

    # Convert artifacts to UnbuiltArtifact objects
    workdir = path.parent.absolute()
    artifacts: MutableMapping[str, UnbuiltArtifact] = {}

    for artifact_key, definition in resolved_pub["artifacts"].items():
        if definition["path"] is None:
            definition["path"] = artifact_key
        artifacts[artifact_key] = UnbuiltArtifact(workdir=workdir, **definition)

    return Publication[UnbuiltArtifact](
        metadata=resolved_pub["metadata"],
        artifacts=artifacts,
    )
