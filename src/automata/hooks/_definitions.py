"""Definitions of all hooks used throughout automata."""

import pathlib
from dataclasses import dataclass, field
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING, Any, Optional, Union

from ._internals import HooksBase, ObserverHook, PipelineHook

if TYPE_CHECKING:
    from automata.website._elements import Element

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
class BuildMaterialsNodeHookArgs:
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
class BuildArtifactSuccessHookArgs:
    """Argument passed when a build succeeds."""

    workdir: pathlib.Path
    path: str
    returncode: Union[int, None]


class BuildHooks(HooksBase):
    """Hooks for the build-materials step (fired once per node or artifact)."""

    on_build_materials_node: ObserverHook[BuildMaterialsNodeHookArgs]
    """Called when building a collection, publication, or artifact."""

    on_build_artifact_too_soon: ObserverHook[BuildArtifactHookArgs]
    """Called when an artifact's release time hasn't passed yet."""

    on_build_artifact_not_ready: ObserverHook[BuildArtifactHookArgs]
    """Called when an artifact is not ready."""

    on_build_artifact_missing: ObserverHook[BuildArtifactHookArgs]
    """Called when an artifact is missing but missing_ok is True."""

    on_build_artifact_recipe: ObserverHook[BuildArtifactHookArgs]
    """Called when running an artifact's recipe."""

    on_build_artifact_success: ObserverHook[BuildArtifactSuccessHookArgs]
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

# collect ------------------------------------------------------------------------------


@dataclass
class WebsiteInputs:
    """Accumulated website inputs gathered from extensions.

    Extensions register hooks on ``on_render_collect`` to contribute
    templates, static files, elements, and pages to the website when it is
    rendered.
    """

    templates: dict[str, str] = field(default_factory=dict)
    static_files: dict[str, "str | bytes | Traversable"] = field(default_factory=dict)
    elements: dict[str, "type[Element]"] = field(default_factory=dict)
    pages: dict[str, str] = field(default_factory=dict)


# render -------------------------------------------------------------------------------


@dataclass
class RenderPreHookArgs:
    """Argument passed before website content is loaded.

    Fired before ``load_content_directory`` reads pages from disk, giving
    script hooks (or other observers) a chance to generate files into the
    content directory.
    """

    content_directory: pathlib.Path
    build_directory: pathlib.Path


@dataclass
class RenderExtraPagesHookArgs:
    """Argument passed to the ``on_render_extra_pages`` hook.

    This is a pipeline hook that can add or change extra pages (in
    ``extra_content``) before pages are rendered.
    """

    build_directory: pathlib.Path
    extra_content: dict[str, str | bytes | pathlib.Path] | None


@dataclass
class RenderPostHookArgs:
    """Argument passed to the ``on_render_post`` hook."""

    build_directory: pathlib.Path


class RenderHooks(HooksBase):
    """Hooks for the render-website step."""

    on_render_pre: ObserverHook[RenderPreHookArgs]
    """Called before content is loaded from disk. Script hooks can use this
    to generate files into the content directory."""

    on_render_collect: PipelineHook[WebsiteInputs]
    """Called to gather website inputs (templates, static files, elements, etc.)."""

    on_render_extra_pages: PipelineHook[RenderExtraPagesHookArgs]
    """Called before pages are rendered. Can add or change extra pages."""

    on_render_post: ObserverHook[RenderPostHookArgs]
    """Called after the website has been written to the build directory."""


# publish hooks ========================================================================


@dataclass
class PublisherRegistryArgs:
    """Mutable registry of publisher strategies.

    Passed through the ``on_register_publishers`` pipeline hook so that
    extensions can add custom publish strategies.
    """

    publishers: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishPreHookArgs:
    """Argument passed before publishing."""

    build_directory: pathlib.Path
    strategy: str


@dataclass
class PublishPostHookArgs:
    """Argument passed after publishing."""

    build_directory: pathlib.Path
    strategy: str


class PublishHooks(HooksBase):
    """Hooks for the publish/deploy phase."""

    on_register_publishers: PipelineHook[PublisherRegistryArgs]
    """Called to let extensions register custom publish strategies."""

    on_publish_pre: ObserverHook[PublishPreHookArgs]
    """Called before publishing begins."""

    on_publish_post: ObserverHook[PublishPostHookArgs]
    """Called after publishing completes."""


# all hooks ============================================================================


class Hooks(
    DiscoverHooks,
    BuildHooks,
    ExportHooks,
    FilterHooks,
    RenderHooks,
    PublishHooks,
):
    """Central registry of all hooks in automata."""
