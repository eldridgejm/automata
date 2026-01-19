"""Hook definitions for materials operations.

This module contains hook classes for:
- materials.discover: Collection, publication, and skip hooks
- materials.build: Start, too soon, not ready, missing, recipe, and success hooks
- materials.export: Copy and node hooks
- materials.filter: Hit and miss hooks
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .._base import define_hook

if TYPE_CHECKING:
    from ...materials import (
        BuiltArtifact,
        Collection,
        Publication,
        UnbuiltArtifact,
        Universe,
    )
    from ...materials._types import Artifact


# =============================================================================
# Hook Definitions - materials.discover
# =============================================================================


@define_hook("materials.discover:on_collection")
def DiscoverOnCollectionHook(path: Path, collection: "Collection") -> None:
    """Called when a collection is discovered.

    Parameters
    ----------
    path : Path
        Path to the collection.yaml file.
    collection : Collection
        The discovered collection.

    """
    ...


def _serialize_collection_args(path: Path, collection: "Collection") -> dict:
    """Serialize arguments for script execution (collection is not serialized)."""
    return {"path": path}


DiscoverOnCollectionHook.serialize_args = _serialize_collection_args


@define_hook("materials.discover:on_publication")
def DiscoverOnPublicationHook(path: Path, publication: "Publication") -> None:
    """Called when a publication is discovered.

    Parameters
    ----------
    path : Path
        Path to the publication.yaml file.
    publication : Publication
        The discovered publication.

    """
    ...


def _serialize_publication_args(path: Path, publication: "Publication") -> dict:
    """Serialize arguments for script execution (publication is not serialized)."""
    return {"path": path}


DiscoverOnPublicationHook.serialize_args = _serialize_publication_args


@define_hook("materials.discover:on_skip")
def DiscoverOnSkipHook(path: Path) -> None:
    """Called when a directory is skipped during discovery.

    Parameters
    ----------
    path : Path
        Path to the skipped directory.

    """
    ...


def _serialize_path(path: Path) -> dict:
    """Serialize path argument."""
    return {"path": path}


DiscoverOnSkipHook.serialize_args = _serialize_path


# =============================================================================
# Hook Definitions - materials.build
# =============================================================================


@define_hook("materials.build:on_start")
def BuildOnStartHook(
    key: str, node: "Collection | Publication | UnbuiltArtifact"
) -> None:
    """Called when building a node begins.

    Parameters
    ----------
    key : str
        The key of the node being built.
    node : Collection | Publication | UnbuiltArtifact
        The node being built.

    """
    ...


def _serialize_start_args(
    key: str, node: "Collection | Publication | UnbuiltArtifact"
) -> dict:
    """Serialize arguments for script execution (node serialized as type name)."""
    return {"key": key, "node_type": type(node).__name__}


BuildOnStartHook.serialize_args = _serialize_start_args


@define_hook("materials.build:on_too_soon")
def BuildOnTooSoonHook(artifact: "UnbuiltArtifact") -> None:
    """Called when release time hasn't passed.

    Parameters
    ----------
    artifact : UnbuiltArtifact
        The artifact that cannot be built yet.

    """
    ...


def _serialize_too_soon_args(artifact: "UnbuiltArtifact") -> dict:
    """Serialize arguments for script execution (artifact expanded to fields)."""
    return {
        "workdir": artifact.workdir,
        "path": artifact.path,
        "release_time": artifact.release_time,
    }


BuildOnTooSoonHook.serialize_args = _serialize_too_soon_args


@define_hook("materials.build:on_not_ready")
def BuildOnNotReadyHook(artifact: "UnbuiltArtifact") -> None:
    """Called when artifact isn't ready.

    Parameters
    ----------
    artifact : UnbuiltArtifact
        The artifact that isn't ready.

    """
    ...


def _serialize_not_ready_args(artifact: "UnbuiltArtifact") -> dict:
    """Serialize arguments for script execution (artifact expanded to fields)."""
    return {"workdir": artifact.workdir, "path": artifact.path}


BuildOnNotReadyHook.serialize_args = _serialize_not_ready_args


@define_hook("materials.build:on_missing")
def BuildOnMissingHook(artifact: "UnbuiltArtifact") -> None:
    """Called when artifact is missing but missing_ok=True.

    Parameters
    ----------
    artifact : UnbuiltArtifact
        The missing artifact.

    """
    ...


def _serialize_missing_args(artifact: "UnbuiltArtifact") -> dict:
    """Serialize arguments for script execution (artifact expanded to fields)."""
    return {"workdir": artifact.workdir, "path": artifact.path}


BuildOnMissingHook.serialize_args = _serialize_missing_args


@define_hook("materials.build:on_recipe")
def BuildOnRecipeHook(artifact: "UnbuiltArtifact") -> None:
    """Called when recipe is about to execute.

    Parameters
    ----------
    artifact : UnbuiltArtifact
        The artifact whose recipe is about to run.

    """
    ...


def _serialize_recipe_args(artifact: "UnbuiltArtifact") -> dict:
    """Serialize arguments for script execution (artifact expanded to fields)."""
    return {
        "workdir": artifact.workdir,
        "path": artifact.path,
        "recipe": artifact.recipe,
    }


BuildOnRecipeHook.serialize_args = _serialize_recipe_args


@define_hook("materials.build:on_success")
def BuildOnSuccessHook(artifact: "BuiltArtifact") -> None:
    """Called when build succeeded.

    Parameters
    ----------
    artifact : BuiltArtifact
        The successfully built artifact.

    """
    ...


def _serialize_success_args(artifact: "BuiltArtifact") -> dict:
    """Serialize arguments for script execution (artifact expanded to fields)."""
    return {"workdir": artifact.workdir, "path": artifact.path}


BuildOnSuccessHook.serialize_args = _serialize_success_args


# =============================================================================
# Hook Definitions - materials.export
# =============================================================================


@define_hook("materials.export:on_copy")
def ExportOnCopyHook(src: Path, dst: Path) -> None:
    """Called when copying a file during export.

    Parameters
    ----------
    src : Path
        Source path of the file being copied.
    dst : Path
        Destination path of the file.

    """
    ...


def _serialize_copy_args(src: Path, dst: Path) -> dict:
    """Serialize arguments for script execution."""
    return {"src": src, "dst": dst}


ExportOnCopyHook.serialize_args = _serialize_copy_args


@define_hook("materials.export:on_node")
def ExportOnNodeHook(
    key: str, node: "Universe | Collection | Publication | Artifact"
) -> None:
    """Called when exporting a node.

    Parameters
    ----------
    key : str
        The key of the node being exported.
    node : Universe | Collection | Publication | Artifact
        The node being exported.

    """
    ...


def _serialize_node_args(
    key: str, node: "Universe | Collection | Publication | Artifact"
) -> dict:
    """Serialize arguments for script execution (node serialized as type name)."""
    return {"key": key, "node_type": type(node).__name__}


ExportOnNodeHook.serialize_args = _serialize_node_args


# =============================================================================
# Hook Definitions - materials.filter
# =============================================================================


@define_hook("materials.filter:on_hit")
def FilterOnHitHook(
    key: str, node: "Universe | Collection | Publication | Artifact"
) -> None:
    """Called when predicate matches.

    Parameters
    ----------
    key : str
        The key of the matching node.
    node : Universe | Collection | Publication | Artifact
        The matching node.

    """
    ...


def _serialize_filter_hit_args(
    key: str, node: "Universe | Collection | Publication | Artifact"
) -> dict:
    """Serialize arguments for script execution (node serialized as type name)."""
    return {"key": key, "node_type": type(node).__name__}


FilterOnHitHook.serialize_args = _serialize_filter_hit_args


@define_hook("materials.filter:on_miss")
def FilterOnMissHook(
    key: str, node: "Universe | Collection | Publication | Artifact"
) -> None:
    """Called when predicate doesn't match.

    Parameters
    ----------
    key : str
        The key of the non-matching node.
    node : Universe | Collection | Publication | Artifact
        The non-matching node.

    """
    ...


def _serialize_filter_miss_args(
    key: str, node: "Universe | Collection | Publication | Artifact"
) -> dict:
    """Serialize arguments for script execution (node serialized as type name)."""
    return {"key": key, "node_type": type(node).__name__}


FilterOnMissHook.serialize_args = _serialize_filter_miss_args
