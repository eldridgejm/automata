"""Hook definitions for materials operations.

This module contains hook classes for:
- materials.discover: Collection, publication, and skip hooks
- materials.build: Start, too soon, not ready, missing, recipe, and success hooks
- materials.export: Copy and node hooks
- materials.filter: Hit and miss hooks
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from .._base import HookBase, ScriptableHookMixin, hook_point

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
# Hook Base Classes - materials.discover
# =============================================================================


@hook_point("materials.discover:on_collection")
class DiscoverOnCollectionHook(HookBase, ScriptableHookMixin):
    """Hook called when a collection is discovered."""

    @abstractmethod
    def __call__(self, path: Path, collection: "Collection") -> None:
        """Called when a collection is discovered.

        Parameters
        ----------
        path : Path
            Path to the collection.yaml file.
        collection : Collection
            The discovered collection.

        """
        ...

    def serialize_args(self, path: Path, collection: "Collection") -> dict:
        """Serialize arguments for script execution (collection is not serialized)."""
        return {"path": path}


@hook_point("materials.discover:on_publication")
class DiscoverOnPublicationHook(HookBase, ScriptableHookMixin):
    """Hook called when a publication is discovered."""

    @abstractmethod
    def __call__(self, path: Path, publication: "Publication") -> None:
        """Called when a publication is discovered.

        Parameters
        ----------
        path : Path
            Path to the publication.yaml file.
        publication : Publication
            The discovered publication.

        """
        ...

    def serialize_args(self, path: Path, publication: "Publication") -> dict:
        """Serialize arguments for script execution (publication is not serialized)."""
        return {"path": path}


@hook_point("materials.discover:on_skip")
class DiscoverOnSkipHook(HookBase, ScriptableHookMixin):
    """Hook called when a directory is skipped during discovery."""

    @abstractmethod
    def __call__(self, path: Path) -> None:
        """Called when a directory is skipped.

        Parameters
        ----------
        path : Path
            Path to the skipped directory.

        """
        ...


# =============================================================================
# Hook Base Classes - materials.build
# =============================================================================


@hook_point("materials.build:on_start")
class BuildOnStartHook(HookBase, ScriptableHookMixin):
    """Hook called when building a node begins."""

    @abstractmethod
    def __call__(
        self, key: str, node: "Collection | Publication | UnbuiltArtifact"
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

    def serialize_args(
        self, key: str, node: "Collection | Publication | UnbuiltArtifact"
    ) -> dict:
        """Serialize arguments for script execution (node serialized as type name)."""
        return {"key": key, "node_type": type(node).__name__}


@hook_point("materials.build:on_too_soon")
class BuildOnTooSoonHook(HookBase, ScriptableHookMixin):
    """Hook called when release time hasn't passed."""

    @abstractmethod
    def __call__(self, artifact: "UnbuiltArtifact") -> None:
        """Called when release time hasn't passed.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The artifact that cannot be built yet.

        """
        ...

    def serialize_args(self, artifact: "UnbuiltArtifact") -> dict:
        """Serialize arguments for script execution (artifact expanded to fields)."""
        return {
            "workdir": artifact.workdir,
            "path": artifact.path,
            "release_time": artifact.release_time,
        }


@hook_point("materials.build:on_not_ready")
class BuildOnNotReadyHook(HookBase, ScriptableHookMixin):
    """Hook called when artifact isn't ready."""

    @abstractmethod
    def __call__(self, artifact: "UnbuiltArtifact") -> None:
        """Called when artifact isn't ready.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The artifact that isn't ready.

        """
        ...

    def serialize_args(self, artifact: "UnbuiltArtifact") -> dict:
        """Serialize arguments for script execution (artifact expanded to fields)."""
        return {"workdir": artifact.workdir, "path": artifact.path}


@hook_point("materials.build:on_missing")
class BuildOnMissingHook(HookBase, ScriptableHookMixin):
    """Hook called when artifact is missing but missing_ok=True."""

    @abstractmethod
    def __call__(self, artifact: "UnbuiltArtifact") -> None:
        """Called when artifact is missing but missing_ok=True.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The missing artifact.

        """
        ...

    def serialize_args(self, artifact: "UnbuiltArtifact") -> dict:
        """Serialize arguments for script execution (artifact expanded to fields)."""
        return {"workdir": artifact.workdir, "path": artifact.path}


@hook_point("materials.build:on_recipe")
class BuildOnRecipeHook(HookBase, ScriptableHookMixin):
    """Hook called when recipe is about to execute."""

    @abstractmethod
    def __call__(self, artifact: "UnbuiltArtifact") -> None:
        """Called when recipe is about to execute.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The artifact whose recipe is about to run.

        """
        ...

    def serialize_args(self, artifact: "UnbuiltArtifact") -> dict:
        """Serialize arguments for script execution (artifact expanded to fields)."""
        return {
            "workdir": artifact.workdir,
            "path": artifact.path,
            "recipe": artifact.recipe,
        }


@hook_point("materials.build:on_success")
class BuildOnSuccessHook(HookBase, ScriptableHookMixin):
    """Hook called when build succeeded."""

    @abstractmethod
    def __call__(self, artifact: "BuiltArtifact") -> None:
        """Called when build succeeded.

        Parameters
        ----------
        artifact : BuiltArtifact
            The successfully built artifact.

        """
        ...

    def serialize_args(self, artifact: "BuiltArtifact") -> dict:
        """Serialize arguments for script execution (artifact expanded to fields)."""
        return {"workdir": artifact.workdir, "path": artifact.path}


# =============================================================================
# Hook Base Classes - materials.export
# =============================================================================


@hook_point("materials.export:on_copy")
class ExportOnCopyHook(HookBase, ScriptableHookMixin):
    """Hook called when copying a file during export."""

    @abstractmethod
    def __call__(self, src: Path, dst: Path) -> None:
        """Called when copying a file.

        Parameters
        ----------
        src : Path
            Source path of the file being copied.
        dst : Path
            Destination path of the file.

        """
        ...


@hook_point("materials.export:on_node")
class ExportOnNodeHook(HookBase, ScriptableHookMixin):
    """Hook called when exporting a node."""

    @abstractmethod
    def __call__(
        self, key: str, node: "Universe | Collection | Publication | Artifact"
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

    def serialize_args(
        self, key: str, node: "Universe | Collection | Publication | Artifact"
    ) -> dict:
        """Serialize arguments for script execution (node serialized as type name)."""
        return {"key": key, "node_type": type(node).__name__}


# =============================================================================
# Hook Base Classes - materials.filter
# =============================================================================


@hook_point("materials.filter:on_hit")
class FilterOnHitHook(HookBase, ScriptableHookMixin):
    """Hook called when predicate matches."""

    @abstractmethod
    def __call__(
        self, key: str, node: "Universe | Collection | Publication | Artifact"
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

    def serialize_args(
        self, key: str, node: "Universe | Collection | Publication | Artifact"
    ) -> dict:
        """Serialize arguments for script execution (node serialized as type name)."""
        return {"key": key, "node_type": type(node).__name__}


@hook_point("materials.filter:on_miss")
class FilterOnMissHook(HookBase, ScriptableHookMixin):
    """Hook called when predicate doesn't match."""

    @abstractmethod
    def __call__(
        self, key: str, node: "Universe | Collection | Publication | Artifact"
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

    def serialize_args(
        self, key: str, node: "Universe | Collection | Publication | Artifact"
    ) -> dict:
        """Serialize arguments for script execution (node serialized as type name)."""
        return {"key": key, "node_type": type(node).__name__}
