"""Build a Universe from inline materials defined in automata.yaml."""

import pathlib
from typing import Any, Mapping, Optional

from automata.hooks import DiscoverHookArgs, DiscoverHooks

from ._discover_collection import parse_collection
from ._discover_publication import parse_publication
from ._types import Collection, UnbuiltArtifact, Universe


def _last_publication(collection: Collection) -> Optional[Any]:
    """Return the last publication in an ordered collection, or None."""
    if not collection.publication_schema.is_ordered:
        return None
    try:
        key_of_last = list(collection.publications)[-1]
    except IndexError:
        return None
    return collection.publications[key_of_last]


def discover_inline(
    materials_config: dict[str, Any],
    project_path: pathlib.Path,
    vars: Optional[Mapping[str, Any]] = None,
    hooks: Optional[DiscoverHooks] = None,
) -> Universe[UnbuiltArtifact]:
    """Create a Universe from inline materials defined in config.

    Parameters
    ----------
    materials_config : dict[str, Any]
        The ``materials`` dict from ``automata.yaml``. Each key is a
        collection name mapping to a dict with ``schema`` and
        ``publications`` keys.
    project_path : pathlib.Path
        The project root directory, used to resolve relative artifact paths.
    vars : Mapping[str, Any] | None
        Variables available during interpolation.
    hooks : DiscoverHooks | None
        Hooks to invoke during discovery. ``on_discover_collection`` and
        ``on_discover_publication`` fire with ``path`` set to ``automata.yaml``
        and ``key`` set to the collection or publication name.

    Returns
    -------
    Universe[UnbuiltArtifact]
        The materials universe. Artifacts will have ``recipe=None``.

    """
    if vars is None:
        vars = {}

    if hooks is None:
        hooks = DiscoverHooks()

    collections: dict[str, Collection[UnbuiltArtifact]] = {}

    for collection_name, collection_def in materials_config.items():
        schema_def = collection_def.get("schema", {})
        raw_publications = collection_def.get("publications", {})

        # Build a collection.yaml-style dict for parse_collection
        collection_yaml = {
            "publication_schema": {
                "required_artifacts": schema_def.get("required_artifacts", []),
                **{k: v for k, v in schema_def.items() if k != "required_artifacts"},
            },
        }

        # Use a synthetic source path for error messages
        source = project_path / "automata.yaml"

        collection, _ = parse_collection(collection_yaml, source=source, vars=vars)
        hooks.on_discover_collection(DiscoverHookArgs(path=source, key=collection_name))

        # Resolve each publication
        for pub_key, raw_pub in raw_publications.items():
            # Ensure no recipes are specified
            for artifact_key, artifact_def in raw_pub.get("artifacts", {}).items():
                if (
                    isinstance(artifact_def, dict)
                    and artifact_def.get("recipe") is not None
                ):
                    raise ValueError(
                        f"Inline materials cannot have recipes "
                        f"(collection={collection_name!r}, "
                        f"publication={pub_key!r}, "
                        f"artifact={artifact_key!r}). "
                        f"Use filesystem materials instead."
                    )

            previous = _last_publication(collection)
            publication = parse_publication(
                raw_pub,
                workdir=project_path,
                publication_schema=collection.publication_schema,
                vars=vars,
                previous=previous,
                templates=collection.templates,
                source=source,
            )
            collection.publications[pub_key] = publication
            hooks.on_discover_publication(DiscoverHookArgs(path=source, key=pub_key))

        collections[collection_name] = collection

    return Universe(collections)
