"""Definitions of all hooks used throughout automata."""

import pathlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Union

from ._internals import HooksBase, ObserverHook, PipelineHook

if TYPE_CHECKING:
    from automata.website import WebsiteConfig, WebsiteContent

# materials hooks ======================================================================

# discover -----------------------------------------------------------------------------


@dataclass
class DiscoverHookArgs:
    """Argument passed to discovery hooks."""

    path: pathlib.Path
    # Not all discovery hooks have a meaningful key. For example, on_discover_skip
    # fires for directories that are skipped entirely, before any key is determined.
    key: Optional[str] = None


class DiscoverHooks(HooksBase):
    """Hooks for the discovery phase."""

    on_discover_collection: ObserverHook[DiscoverHookArgs]
    """Called when a collection is discovered."""

    on_discover_publication: ObserverHook[DiscoverHookArgs]
    """Called when a publication is discovered."""

    on_discover_skip: ObserverHook[DiscoverHookArgs]
    """Called when a directory is skipped."""


# build --------------------------------------------------------------------------------


@dataclass
class BuildNodeHookArgs:
    """Argument passed when building a node (collection/publication/artifact)."""

    key: str
    node_type: str  # "collection", "publication", or "artifact"


@dataclass
class BuildArtifactHookArgs:
    """Argument passed for artifact build events."""

    workdir: pathlib.Path
    path: str
    recipe: Union[str, None]
    release_time: Union[str, None]  # ISO format string for serialization
    ready: bool
    missing_ok: bool


@dataclass
class BuildSuccessHookArgs:
    """Argument passed when a build succeeds."""

    workdir: pathlib.Path
    path: str
    returncode: Union[int, None]


class BuildHooks(HooksBase):
    """Hooks for the build phase."""

    on_build_node: ObserverHook[BuildNodeHookArgs]
    """Called when building a collection, publication, or artifact."""

    on_build_too_soon: ObserverHook[BuildArtifactHookArgs]
    """Called when an artifact's release time hasn't passed yet."""

    on_build_not_ready: ObserverHook[BuildArtifactHookArgs]
    """Called when an artifact is not ready."""

    on_build_missing: ObserverHook[BuildArtifactHookArgs]
    """Called when an artifact is missing but missing_ok is True."""

    on_build_recipe: ObserverHook[BuildArtifactHookArgs]
    """Called when running an artifact's recipe."""

    on_build_success: ObserverHook[BuildSuccessHookArgs]
    """Called when a build succeeds."""


# export -------------------------------------------------------------------------------


@dataclass
class ExportNodeHookArgs:
    """Argument passed when exporting a node."""

    key: str
    node_type: str  # "collection", "publication", or "artifact"


@dataclass
class ExportCopyHookArgs:
    """Argument passed when copying a file during export."""

    src: pathlib.Path
    dst: pathlib.Path


class ExportHooks(HooksBase):
    """Hooks for the export phase."""

    on_export_node: ObserverHook[ExportNodeHookArgs]
    """Called when exporting a collection, publication, or artifact."""

    on_export_copy: ObserverHook[ExportCopyHookArgs]
    """Called when copying a file to the output directory."""


# filter -------------------------------------------------------------------------------


@dataclass
class FilterHookArgs:
    """Argument passed to filter hooks."""

    key: str
    node_type: str  # "collection", "publication", or "artifact"


class FilterHooks(HooksBase):
    """Hooks for the filter phase."""

    on_filter_hit: ObserverHook[FilterHookArgs]
    """Called when a node matches the predicate."""

    on_filter_miss: ObserverHook[FilterHookArgs]
    """Called when a node does not match the predicate."""


# website hooks ========================================================================

# generate -----------------------------------------------------------------------------


@dataclass
class GeneratePreHookArgs:
    """Argument passed to the pre-generate hook.

    This is a pipeline hook that can transform content and vars
    before generation.
    """

    content: "WebsiteContent"
    """The website content (templates, pages, static files, elements, etc.)."""

    vars: dict[str, Any]
    """Template variables available during rendering."""


@dataclass
class GeneratePostHookArgs:
    """Argument passed to the post-generate hook."""

    config: "WebsiteConfig"


class GenerateHooks(HooksBase):
    """Hooks for the website generation phase."""

    on_generate_pre: PipelineHook[GeneratePreHookArgs]
    """Called before generation. Can transform resources and vars."""

    on_generate_post: ObserverHook[GeneratePostHookArgs]
    """Called after generation completes."""


# all hooks ============================================================================


class Hooks(DiscoverHooks, BuildHooks, ExportHooks, FilterHooks, GenerateHooks):
    """Central registry of all hooks in automata."""
