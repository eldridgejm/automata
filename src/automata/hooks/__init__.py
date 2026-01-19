"""Unified Hook System for Automata.

This module provides a typed, descriptor-based hook system for injecting custom
logic at specific points in the build process.

Hook Point Naming
-----------------

Hook points are named using snake_case identifiers. The Hooks class centralizes
all hook point definitions:

**Materials hooks**:
- `discover_on_collection` - Called when a collection is discovered
- `discover_on_publication` - Called when a publication is discovered
- `discover_on_skip` - Called when a directory is skipped
- `build_on_start` - Called when building a node begins
- `build_on_too_soon` - Called when release time hasn't passed
- `build_on_not_ready` - Called when artifact isn't ready
- `build_on_missing` - Called when artifact is missing but missing_ok=True
- `build_on_recipe` - Called when recipe is about to execute
- `build_on_success` - Called when build succeeded
- `export_on_copy` - Called when copying a file during export
- `export_on_node` - Called when exporting a node
- `filter_on_hit` - Called when predicate matches
- `filter_on_miss` - Called when predicate doesn't match

**Resolution hooks**:
- `pre_resolve` - Called before resolve() for custom functions/variables

**Website hooks**:
- `pre_generate_website` - Pipeline hook before website generation
- `post_generate_website` - Called after website generation (scriptable)

Execution Semantics
-------------------

Hooks are executed in ascending priority order (lower values run first).
Ties are resolved by insertion order.

Most hooks collect all results into a list. Pipeline hooks (like
`pre_generate_website`) pass output through the chain. Some hooks have
custom reducers to merge results.

Usage
-----

Create a Hooks instance and register implementations::

    from automata.hooks import Hooks

    hooks = Hooks()

    @hooks.discover_on_skip.register(priority=10)
    def my_skip_handler(path):
        print(f"Skipped {path}")

Execute hooks by calling them::

    hooks.discover_on_skip(path)

"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ._base import (
    HookDescriptor,
    HookImpl,
    HookInteractor,
    HooksBase,
    Registry,
    ResolveOverrides,
    WebsiteContent,
    hook,
    merge_resolve_results,
)

if TYPE_CHECKING:
    from .._config import WebsiteConfig
    from ..materials import (
        Artifact,
        BuiltArtifact,
        Collection,
        ExportedArtifact,
        Publication,
        UnbuiltArtifact,
        Universe,
    )


# =============================================================================
# Serializers for Script Hooks
# =============================================================================


def _serialize_discover_on_collection(
    path: Path, collection: "Collection"
) -> dict[str, Any]:
    """Serialize arguments for discover_on_collection script hook."""
    return {"path": path, "collection_key": str(path.parent)}


def _serialize_discover_on_publication(
    path: Path, publication: "Publication"
) -> dict[str, Any]:
    """Serialize arguments for discover_on_publication script hook."""
    return {"path": path}


def _serialize_discover_on_skip(path: Path) -> dict[str, Any]:
    """Serialize arguments for discover_on_skip script hook."""
    return {"path": path}


def _serialize_build_on_start(
    key: str, node: "Collection | Publication | UnbuiltArtifact"
) -> dict[str, Any]:
    """Serialize arguments for build_on_start script hook."""
    return {"key": key, "node_type": type(node).__name__}


def _serialize_build_on_artifact(artifact: "UnbuiltArtifact") -> dict[str, Any]:
    """Serialize arguments for artifact-related build hooks."""
    return {
        "workdir": artifact.workdir,
        "path": artifact.path,
        "release_time": artifact.release_time,
    }


def _serialize_build_on_success(artifact: "BuiltArtifact") -> dict[str, Any]:
    """Serialize arguments for build_on_success script hook."""
    return {"workdir": artifact.workdir, "path": artifact.path}


def _serialize_export_on_copy(src: Path, dst: Path) -> dict[str, Any]:
    """Serialize arguments for export_on_copy script hook."""
    return {"src": src, "dst": dst}


def _serialize_export_on_node(
    key: str, node: "Universe | Collection | Publication | Artifact"
) -> dict[str, Any]:
    """Serialize arguments for export_on_node script hook."""
    return {"key": key, "node_type": type(node).__name__}


def _serialize_filter_on_hit(
    key: str, node: "Universe | Collection | Publication | Artifact"
) -> dict[str, Any]:
    """Serialize arguments for filter_on_hit script hook."""
    return {"key": key, "node_type": type(node).__name__}


def _serialize_filter_on_miss(
    key: str, node: "Universe | Collection | Publication | Artifact"
) -> dict[str, Any]:
    """Serialize arguments for filter_on_miss script hook."""
    return {"key": key, "node_type": type(node).__name__}


def _serialize_post_generate(
    materials: "Universe[ExportedArtifact]",
    website_config: "WebsiteConfig",
    build_directory: Path,
    vars: dict[str, Any],
    current_time: datetime.datetime,
) -> dict[str, Any]:
    """Serialize arguments for post_generate_website script hook."""
    from .. import materials as materials_module

    return {
        "materials": materials_module.serialize(materials),
        "config": {
            "content_directory": website_config.content_directory,
            "build_directory": website_config.build_directory,
            "materials_directory_name": website_config.materials_directory_name,
            "base_path": website_config.base_path,
        },
        "build_directory": build_directory,
        "vars": vars,
        "current_time": current_time,
    }


# =============================================================================
# Hooks Class
# =============================================================================


class Hooks(HooksBase):
    """Centralized hook definitions for Automata.

    Each hook point is defined as a decorated static method. Access a hook on
    an instance to get a HookInteractor for registration and execution.

    Example
    -------
    >>> hooks = Hooks()
    >>> @hooks.discover_on_skip.register(priority=10)
    ... def my_handler(path):
    ...     print(f"Skipped: {path}")
    >>> hooks.discover_on_skip(Path("/some/path"))

    """

    # -------------------------------------------------------------------------
    # Materials Discovery Hooks
    # -------------------------------------------------------------------------

    @hook(serialize_args=_serialize_discover_on_collection)
    @staticmethod
    def discover_on_collection(path: Path, collection: "Collection") -> None:
        """Called when a collection is discovered.

        Parameters
        ----------
        path : Path
            Path to the collection.yaml file.
        collection : Collection
            The discovered collection.

        """
        raise NotImplementedError

    @hook(serialize_args=_serialize_discover_on_publication)
    @staticmethod
    def discover_on_publication(path: Path, publication: "Publication") -> None:
        """Called when a publication is discovered.

        Parameters
        ----------
        path : Path
            Path to the publication.yaml file.
        publication : Publication
            The discovered publication.

        """
        raise NotImplementedError

    @hook(serialize_args=_serialize_discover_on_skip)
    @staticmethod
    def discover_on_skip(path: Path) -> None:
        """Called when a directory is skipped during discovery.

        Parameters
        ----------
        path : Path
            Path to the skipped directory.

        """
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Resolution Hooks
    # -------------------------------------------------------------------------

    @hook(reduce_results=merge_resolve_results)
    @staticmethod
    def pre_resolve(call_site: str, path: Path) -> ResolveOverrides | None:
        """Called before resolve() is called.

        Can provide extra functions/variables for resolution. Results from
        multiple hooks are merged together.

        Parameters
        ----------
        call_site : str
            Identifier for where resolve() is being called from.
        path : Path
            Path to the file being resolved.

        Returns
        -------
        ResolveOverrides | None
            Overrides to apply, or None for no overrides.

        """
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Materials Build Hooks
    # -------------------------------------------------------------------------

    @hook(serialize_args=_serialize_build_on_start)
    @staticmethod
    def build_on_start(
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
        raise NotImplementedError

    @hook(serialize_args=_serialize_build_on_artifact)
    @staticmethod
    def build_on_too_soon(artifact: "UnbuiltArtifact") -> None:
        """Called when release time hasn't passed.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The artifact that cannot be built yet.

        """
        raise NotImplementedError

    @hook(serialize_args=_serialize_build_on_artifact)
    @staticmethod
    def build_on_not_ready(artifact: "UnbuiltArtifact") -> None:
        """Called when artifact isn't ready.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The artifact that isn't ready.

        """
        raise NotImplementedError

    @hook(serialize_args=_serialize_build_on_artifact)
    @staticmethod
    def build_on_missing(artifact: "UnbuiltArtifact") -> None:
        """Called when artifact is missing but missing_ok=True.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The missing artifact.

        """
        raise NotImplementedError

    @hook(serialize_args=_serialize_build_on_artifact)
    @staticmethod
    def build_on_recipe(artifact: "UnbuiltArtifact") -> None:
        """Called when recipe is about to execute.

        Parameters
        ----------
        artifact : UnbuiltArtifact
            The artifact whose recipe is about to run.

        """
        raise NotImplementedError

    @hook(serialize_args=_serialize_build_on_success)
    @staticmethod
    def build_on_success(artifact: "BuiltArtifact") -> None:
        """Called when build succeeded.

        Parameters
        ----------
        artifact : BuiltArtifact
            The successfully built artifact.

        """
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Materials Export Hooks
    # -------------------------------------------------------------------------

    @hook(serialize_args=_serialize_export_on_copy)
    @staticmethod
    def export_on_copy(src: Path, dst: Path) -> None:
        """Called when copying a file during export.

        Parameters
        ----------
        src : Path
            Source path of the file being copied.
        dst : Path
            Destination path of the file.

        """
        raise NotImplementedError

    @hook(serialize_args=_serialize_export_on_node)
    @staticmethod
    def export_on_node(
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
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Materials Filter Hooks
    # -------------------------------------------------------------------------

    @hook(serialize_args=_serialize_filter_on_hit)
    @staticmethod
    def filter_on_hit(
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
        raise NotImplementedError

    @hook(serialize_args=_serialize_filter_on_miss)
    @staticmethod
    def filter_on_miss(
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
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Website Generation Hooks
    # -------------------------------------------------------------------------

    @hook(pipeline_arg="website_content")
    @staticmethod
    def pre_generate_website(
        website_content: WebsiteContent,
        materials: "Universe[ExportedArtifact]",
        website_config: "WebsiteConfig",
        build_directory: Path,
        vars: dict[str, Any],
        current_time: datetime.datetime,
    ) -> WebsiteContent:
        """Called before website generation.

        Hooks form a pipeline: each hook receives the website content and
        returns potentially modified content. The output of one hook becomes
        the input to the next.

        Parameters
        ----------
        website_content : WebsiteContent
            The current website content (content, assets, static_files).
            Modify and return to affect the generated website.
        materials : Universe[ExportedArtifact]
            The exported materials universe.
        website_config : WebsiteConfig
            The website configuration.
        build_directory : Path
            Path to the build output directory.
        vars : dict[str, Any]
            Variables available for rendering.
        current_time : datetime.datetime
            The current build time.

        Returns
        -------
        WebsiteContent
            The (potentially modified) website content.

        """
        raise NotImplementedError

    @hook(serialize_args=_serialize_post_generate)
    @staticmethod
    def post_generate_website(
        materials: "Universe[ExportedArtifact]",
        website_config: "WebsiteConfig",
        build_directory: Path,
        vars: dict[str, Any],
        current_time: datetime.datetime,
    ) -> None:
        """Called after website generation.

        This hook is scriptable - it can be implemented as a shell script.

        Parameters
        ----------
        materials : Universe[ExportedArtifact]
            The exported materials universe.
        website_config : WebsiteConfig
            The website configuration.
        build_directory : Path
            Path to the build output directory.
        vars : dict[str, Any]
            Variables available for rendering.
        current_time : datetime.datetime
            The current build time.

        """
        raise NotImplementedError


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Base types
    "HookDescriptor",
    "HookImpl",
    "HookInteractor",
    "HooksBase",
    "Registry",
    "hook",
    # Main Hooks class
    "Hooks",
    # Return types
    "ResolveOverrides",
    "WebsiteContent",
    # Utilities
    "merge_resolve_results",
]
