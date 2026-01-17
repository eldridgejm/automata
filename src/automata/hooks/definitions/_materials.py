"""Hook definitions for materials operations.

This module contains hook classes for:
- materials.discover: Collection, publication, and skip hooks
- materials.build: Start, too soon, not ready, missing, recipe, and success hooks
- materials.export: Copy and node hooks
- materials.filter: Hit and miss hooks
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from .._base import ScriptableHookMixin, hook_point

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
class DiscoverOnCollectionHook(ScriptableHookMixin, ABC):
    """Hook called when a collection is discovered.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

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

    @staticmethod
    def serialize_args(path: Path, collection: "Collection") -> dict:
        """Serialize arguments for script execution."""
        return {"path": str(path)}


@hook_point("materials.discover:on_publication")
class DiscoverOnPublicationHook(ScriptableHookMixin, ABC):
    """Hook called when a publication is discovered.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

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

    @staticmethod
    def serialize_args(path: Path, publication: "Publication") -> dict:
        """Serialize arguments for script execution."""
        return {"path": str(path)}


@hook_point("materials.discover:on_skip")
class DiscoverOnSkipHook(ScriptableHookMixin, ABC):
    """Hook called when a directory is skipped during discovery.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(self, path: Path) -> None:
        """Called when a directory is skipped.

        Parameters
        ----------
        path : Path
            Path to the skipped directory.

        """
        ...

    @staticmethod
    def serialize_args(path: Path) -> dict:
        """Serialize arguments for script execution."""
        return {"path": str(path)}


# =============================================================================
# Hook Base Classes - materials.build
# =============================================================================


@hook_point("materials.build:on_start")
class BuildOnStartHook(ScriptableHookMixin, ABC):
    """Hook called when building a node begins.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

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

    @staticmethod
    def serialize_args(
        key: str, node: "Collection | Publication | UnbuiltArtifact"
    ) -> dict:
        """Serialize arguments for script execution."""
        return {"key": key, "node_type": type(node).__name__}


@hook_point("materials.build:on_too_soon")
class BuildOnTooSoonHook(ScriptableHookMixin, ABC):
    """Hook called when release time hasn't passed.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(self, artifact: "UnbuiltArtifact") -> None:
        """Called when release time hasn't passed.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The artifact that cannot be built yet.

        """
        ...

    @staticmethod
    def serialize_args(artifact: "UnbuiltArtifact") -> dict:
        """Serialize arguments for script execution."""
        return {
            "workdir": str(artifact.workdir),
            "path": str(artifact.path),
            "release_time": artifact.release_time.isoformat()
            if artifact.release_time
            else None,
        }


@hook_point("materials.build:on_not_ready")
class BuildOnNotReadyHook(ScriptableHookMixin, ABC):
    """Hook called when artifact isn't ready.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(self, artifact: "UnbuiltArtifact") -> None:
        """Called when artifact isn't ready.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The artifact that isn't ready.

        """
        ...

    @staticmethod
    def serialize_args(artifact: "UnbuiltArtifact") -> dict:
        """Serialize arguments for script execution."""
        return {
            "workdir": str(artifact.workdir),
            "path": str(artifact.path),
        }


@hook_point("materials.build:on_missing")
class BuildOnMissingHook(ScriptableHookMixin, ABC):
    """Hook called when artifact is missing but missing_ok=True.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(self, artifact: "UnbuiltArtifact") -> None:
        """Called when artifact is missing but missing_ok=True.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The missing artifact.

        """
        ...

    @staticmethod
    def serialize_args(artifact: "UnbuiltArtifact") -> dict:
        """Serialize arguments for script execution."""
        return {
            "workdir": str(artifact.workdir),
            "path": str(artifact.path),
        }


@hook_point("materials.build:on_recipe")
class BuildOnRecipeHook(ScriptableHookMixin, ABC):
    """Hook called when recipe is about to execute.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(self, artifact: "UnbuiltArtifact") -> None:
        """Called when recipe is about to execute.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The artifact whose recipe is about to run.

        """
        ...

    @staticmethod
    def serialize_args(artifact: "UnbuiltArtifact") -> dict:
        """Serialize arguments for script execution."""
        return {
            "workdir": str(artifact.workdir),
            "path": str(artifact.path),
            "recipe": artifact.recipe,
        }


@hook_point("materials.build:on_success")
class BuildOnSuccessHook(ScriptableHookMixin, ABC):
    """Hook called when build succeeded.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(self, artifact: "BuiltArtifact") -> None:
        """Called when build succeeded.

        Parameters
        ----------
        artifact : BuiltArtifact
            The successfully built artifact.

        """
        ...

    @staticmethod
    def serialize_args(artifact: "BuiltArtifact") -> dict:
        """Serialize arguments for script execution."""
        return {
            "workdir": str(artifact.workdir),
            "path": str(artifact.path),
        }


# =============================================================================
# Hook Base Classes - materials.export
# =============================================================================


@hook_point("materials.export:on_copy")
class ExportOnCopyHook(ScriptableHookMixin, ABC):
    """Hook called when copying a file during export.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

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

    @staticmethod
    def serialize_args(src: Path, dst: Path) -> dict:
        """Serialize arguments for script execution."""
        return {"src": str(src), "dst": str(dst)}


@hook_point("materials.export:on_node")
class ExportOnNodeHook(ScriptableHookMixin, ABC):
    """Hook called when exporting a node.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

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

    @staticmethod
    def serialize_args(
        key: str, node: "Universe | Collection | Publication | Artifact"
    ) -> dict:
        """Serialize arguments for script execution."""
        return {"key": key, "node_type": type(node).__name__}


# =============================================================================
# Hook Base Classes - materials.filter
# =============================================================================


@hook_point("materials.filter:on_hit")
class FilterOnHitHook(ScriptableHookMixin, ABC):
    """Hook called when predicate matches.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

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

    @staticmethod
    def serialize_args(
        key: str, node: "Universe | Collection | Publication | Artifact"
    ) -> dict:
        """Serialize arguments for script execution."""
        return {"key": key, "node_type": type(node).__name__}


@hook_point("materials.filter:on_miss")
class FilterOnMissHook(ScriptableHookMixin, ABC):
    """Hook called when predicate doesn't match.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

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

    @staticmethod
    def serialize_args(
        key: str, node: "Universe | Collection | Publication | Artifact"
    ) -> dict:
        """Serialize arguments for script execution."""
        return {"key": key, "node_type": type(node).__name__}
