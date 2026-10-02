"""Build a Universe from inline materials defined in automata.yaml."""

import pathlib
from typing import Any, Mapping, Optional

from automata import constants
from automata.exceptions import Error
from automata.hooks import DiscoverHookArgs, DiscoverHooks

from ..util.resolution import describe_config_error
from ..util.yaml import SourceMap
from ._discover_collection import parse_collection
from ._discover_publication import parse_publication
from ._types import Collection, UnbuiltArtifact, Universe
from .exceptions import DiscoveryError


def _last_publication(collection: Collection) -> Optional[Any]:
    """Return the last publication in an ordered collection, or None."""
    if not collection.publication_schema.is_ordered:
        return None
    try:
        key_of_last = list(collection.publications)[-1]
    except IndexError:
        return None
    return collection.publications[key_of_last]


def _check_inline_collection(name: str, collection_def: Any) -> None:
    """Check the shape of one inline collection, naming it in any error."""
    where = f"materials.{name}"
    allowed = ("schema", "publications")
    if not isinstance(collection_def, dict):
        raise Error(
            f'{where} must be a mapping with "schema" and "publications" keys, '
            f"not {_describe(collection_def)}."
        )
    for key in collection_def:
        if key not in allowed:
            raise Error(
                f'{where} has unknown key "{key}" (expected "schema" and '
                f'"publications").'
            )
    for key in allowed:
        value = collection_def.get(key, {})
        if not isinstance(value, dict):
            raise Error(f"{where}.{key} must be a mapping, not {_describe(value)}.")
    for pub_name, pub in collection_def.get("publications", {}).items():
        if not isinstance(pub, dict):
            raise Error(
                f"{where}.publications.{pub_name} must be a mapping with "
                f'"metadata" and "artifacts" keys, not {_describe(pub)}.'
            )


def _in_automata_yaml(
    exc: DiscoveryError,
    source: pathlib.Path,
    prefix: tuple,
    source_map: Optional[SourceMap],
    drop: int = 0,
) -> Error:
    """An error from inline materials, with its keypath as written in the file."""
    if exc.reason is None or exc.keypath is None:
        return Error(str(exc))
    keypath = (*prefix, *exc.keypath[drop:])
    return Error(
        describe_config_error(exc.reason, keypath, file=source, source_map=source_map)
    )


def _describe(value: Any) -> str:
    """A short description of a value's type, for error messages."""
    if value is None:
        return "empty"
    return f"a {type(value).__name__}"


def discover_inline(
    materials_config: dict[str, Any],
    project_path: pathlib.Path,
    vars: Optional[Mapping[str, Any]] = None,
    hooks: Optional[DiscoverHooks] = None,
    source_map: Optional[SourceMap] = None,
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
    source_map : SourceMap | None
        The source map of ``automata.yaml``, used to give the line of errors.

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
        if collection_name == constants.DEFAULT_COLLECTION:
            raise Error(
                describe_config_error(
                    f"{constants.DEFAULT_COLLECTION_RESERVED} Rename it.",
                    ("materials", collection_name),
                    file=project_path / "automata.yaml",
                    source_map=source_map,
                )
            )
        _check_inline_collection(collection_name, collection_def)
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

        try:
            collection, _ = parse_collection(collection_yaml, source=source, vars=vars)
        except DiscoveryError as exc:
            # keypaths start with the synthetic "publication_schema" key
            raise _in_automata_yaml(
                exc,
                source,
                ("materials", collection_name, "schema"),
                source_map,
                drop=1,
            ) from None
        hooks.on_discover_collection(DiscoverHookArgs(path=source, key=collection_name))

        # Resolve each publication
        for pub_key, raw_pub in raw_publications.items():
            # Ensure no recipes are specified
            for artifact_key, artifact_def in raw_pub.get("artifacts", {}).items():
                if (
                    isinstance(artifact_def, dict)
                    and artifact_def.get("recipe") is not None
                ):
                    raise Error(
                        f"Inline materials cannot have recipes "
                        f"(collection={collection_name!r}, "
                        f"publication={pub_key!r}, "
                        f"artifact={artifact_key!r}). "
                        f"Use filesystem materials instead."
                    )

            previous = _last_publication(collection)
            try:
                publication = parse_publication(
                    raw_pub,
                    workdir=project_path,
                    publication_schema=collection.publication_schema,
                    vars=vars,
                    previous=previous,
                    templates=collection.templates,
                    source=source,
                )
            except DiscoveryError as exc:
                raise _in_automata_yaml(
                    exc,
                    source,
                    ("materials", collection_name, "publications", pub_key),
                    source_map,
                ) from None
            collection.publications[pub_key] = publication
            hooks.on_discover_publication(DiscoverHookArgs(path=source, key=pub_key))

        collections[collection_name] = collection

    return Universe(collections)
