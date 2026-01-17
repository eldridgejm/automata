"""Unified Hook System for Automata.

This module provides a typed hook system that replaces the separate callbacks
and hooks systems with a single, unified approach.

Hooks allow plugins and configuration to inject custom logic at specific
points in the build process. Each hook is a class with a `priority` attribute
and a `__call__` method with a hook-specific signature.

Hook Point Naming
-----------------

Hook points follow two naming patterns based on their scope:

**Function-scoped hooks** use the pattern `module.function:on_event`:
- `materials.discover:on_collection` — called only within `materials.discover()`
- `materials.build:on_recipe` — called only within `materials.build()`

**Top-level hooks** use simple names without a module prefix:
- `pre_resolve` — called from multiple places that invoke resolution
- `pre_generate_website` — called by `build()`, `deploy()`, `preview()`, etc.

Execution Semantics
-------------------

Hooks are executed in ascending priority order (lower values run first).
Ties are resolved by insertion order—hooks registered earlier run first.

For hooks that return overrides (`pre_resolve`, `pre_generate_website`),
results are merged in execution order. Later hooks override earlier ones.

If a hook raises an exception, execution stops and the error propagates.
Hooks should fail fast rather than silently swallow errors.

Script Hooks
------------

Script hooks are fire-and-forget—they cannot return values or affect program flow.
Scriptable hooks inherit from `ScriptableHookMixin` and implement `serialize_args`.
"""

from __future__ import annotations

import inspect
import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Self, Sequence, TypedDict, overload

if TYPE_CHECKING:
    import datetime

    from ._config import WebsiteConfig
    from .materials import (
        BuiltArtifact,
        Collection,
        ExportedArtifact,
        Publication,
        UnbuiltArtifact,
        Universe,
    )
    from .materials._types import Artifact


# =============================================================================
# Registry
# =============================================================================

HOOK_POINTS: dict[str, type] = {}
"""Registry mapping hook point names to their base classes."""


def hook_point(name: str):
    """Decorator that registers a hook class with its hook point name.

    Parameters
    ----------
    name : str
        The hook point name (e.g., "materials.discover:on_collection").

    Returns
    -------
    Callable
        A decorator that registers the class and returns it unchanged.

    """

    def decorator(cls):
        HOOK_POINTS[name] = cls
        cls._hook_point_name = name
        return cls

    return decorator


# =============================================================================
# Return Types
# =============================================================================


@dataclass
class ResolveOverrides:
    """Returned by pre_resolve hooks to customize resolution.

    Attributes
    ----------
    functions : dict[str, Callable]
        Additional functions to make available during resolution.
    global_variables : dict[str, Any]
        Additional global variables to make available during resolution.

    """

    functions: dict[str, Callable] = field(default_factory=dict)
    global_variables: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerateOverrides:
    """Returned by pre_generate_website hooks to add extra content.

    Attributes
    ----------
    pages : dict[str, str]
        Additional pages to generate. Keys are relative paths (e.g., "about.html"),
        values are page content (markdown or HTML with frontmatter).
    assets : dict[str, str | bytes]
        Additional static assets. Keys are relative paths, values are content.

    """

    pages: dict[str, str] = field(default_factory=dict)
    assets: dict[str, str | bytes] = field(default_factory=dict)


# =============================================================================
# ScriptableHookMixin
# =============================================================================


class ScriptableHookMixin(ABC):
    """Mixin for hooks that support script invocation.

    Script hooks are fire-and-forget—they cannot return values or affect
    program flow. This mixin provides a `from_script` factory method that
    creates a hook instance from a shell command.

    Subclasses must implement `serialize_args` to convert call arguments
    to a JSON-serializable dictionary for passing to the script.

    """

    @staticmethod
    @abstractmethod
    def serialize_args(*args, **kwargs) -> dict:
        """Serialize call arguments to JSON-compatible dict for script stdin.

        This method must be implemented by subclasses to define how the
        hook's arguments are converted to a dictionary for JSON serialization.

        Parameters
        ----------
        *args : Any
            Positional arguments passed to the hook.
        **kwargs : Any
            Keyword arguments passed to the hook.

        Returns
        -------
        dict
            A JSON-serializable dictionary containing the arguments.

        """
        ...

    @classmethod
    def from_script(cls, command: str, cwd: Path, priority: int = 50) -> Self:
        """Create a hook instance that executes a shell command.

        The shell command receives a JSON-serialized context on stdin.
        Script hooks cannot return values that modify the generation process;
        they are intended for side effects only (e.g., running post-processing
        scripts). Any output from the command is ignored.

        Parameters
        ----------
        command : str
            The shell command to execute.
        cwd : Path
            Working directory for the command.
        priority : int, optional
            Hook priority (lower runs first). Default is 50.

        Returns
        -------
        Self
            A hook instance that executes the command when called.

        """
        serialize_fn = cls.serialize_args
        parent_sig = inspect.signature(cls.__call__)

        class ScriptHookInstance(cls):  # type: ignore[valid-type, misc]
            """Dynamically-created script hook instance."""

            def __init__(self):
                self.priority = priority

            def __call__(self, *args, **kwargs):
                context_json = json.dumps(
                    serialize_fn(*args, **kwargs), default=_json_serializer
                )
                try:
                    subprocess.run(
                        command,
                        shell=True,
                        cwd=str(cwd),
                        input=context_json,
                        text=True,
                        capture_output=True,
                        timeout=300,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(
                        f"Shell hook failed with exit code {e.returncode}:\n{e.stderr}"
                    ) from e
                except subprocess.TimeoutExpired as e:
                    raise RuntimeError("Shell hook timed out after 300 seconds") from e

            @staticmethod
            def serialize_args(*args, **kwargs) -> dict:
                return serialize_fn(*args, **kwargs)

        # Copy signature from parent's __call__ for introspection
        ScriptHookInstance.__call__.__signature__ = parent_sig  # type: ignore[attr-defined]

        return ScriptHookInstance()  # type: ignore[abstract]


def _json_serializer(obj: Any) -> Any:
    """JSON serializer for types not natively supported.

    Parameters
    ----------
    obj : Any
        Object to serialize.

    Returns
    -------
    Any
        JSON-serializable representation.

    Raises
    ------
    TypeError
        If the object cannot be serialized.

    """
    # Handle datetime
    if hasattr(obj, "isoformat"):
        return obj.isoformat()

    # Handle Path
    if isinstance(obj, Path):
        return str(obj)

    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


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


# =============================================================================
# Hook Base Classes - resolution
# =============================================================================


@hook_point("pre_resolve")
class PreResolveHook(ABC):
    """Hook called before resolve() is called.

    Can provide extra functions/variables for resolution.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(self, call_site: str, path: Path) -> ResolveOverrides | None:
        """Called before resolve().

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
        ...


# =============================================================================
# Hook Base Classes - website.generate
# =============================================================================


@hook_point("pre_generate_website")
class PreGenerateWebsiteHook(ABC):
    """Hook called before website generation.

    Can provide extra pages/assets.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(
        self,
        materials: "Universe[ExportedArtifact]",
        website_config: "WebsiteConfig",
        build_directory: Path,
        vars: dict[str, Any],
        current_time: "datetime.datetime",
    ) -> GenerateOverrides | None:
        """Called before website generation.

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

        Returns
        -------
        GenerateOverrides | None
            Overrides to apply, or None for no overrides.

        """
        ...


@hook_point("post_generate_website")
class PostGenerateWebsiteHook(ScriptableHookMixin):
    """Hook called after website generation.

    This hook is scriptable - it can be implemented as a shell script.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(
        self,
        materials: "Universe[ExportedArtifact]",
        website_config: "WebsiteConfig",
        build_directory: Path,
        vars: dict[str, Any],
        current_time: "datetime.datetime",
    ) -> None:
        """Called after website generation.

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
        ...

    @staticmethod
    def serialize_args(
        materials: "Universe[ExportedArtifact]",
        website_config: "WebsiteConfig",
        build_directory: Path,
        vars: dict[str, Any],
        current_time: "datetime.datetime",
    ) -> dict:
        """Serialize arguments for script execution.

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

        Returns
        -------
        dict
            JSON-serializable dictionary of arguments.

        """
        from . import materials as materials_module

        return {
            "materials": materials_module.serialize(materials),
            "config": {
                "content_directory": str(website_config.content_directory),
                "build_directory": str(website_config.build_directory),
                "materials_directory_name": website_config.materials_directory_name,
                "base_path": website_config.base_path,
            },
            "build_directory": str(build_directory),
            "vars": vars,
            "current_time": current_time.isoformat(),
        }


# =============================================================================
# Hooks TypedDict
# =============================================================================

# Using functional syntax due to special characters in keys
Hooks = TypedDict(
    "Hooks",
    {
        # Resolution
        "pre_resolve": list[PreResolveHook],
        # Materials discovery
        "materials.discover:on_collection": list[DiscoverOnCollectionHook],
        "materials.discover:on_publication": list[DiscoverOnPublicationHook],
        "materials.discover:on_skip": list[DiscoverOnSkipHook],
        # Materials build
        "materials.build:on_start": list[BuildOnStartHook],
        "materials.build:on_too_soon": list[BuildOnTooSoonHook],
        "materials.build:on_not_ready": list[BuildOnNotReadyHook],
        "materials.build:on_missing": list[BuildOnMissingHook],
        "materials.build:on_recipe": list[BuildOnRecipeHook],
        "materials.build:on_success": list[BuildOnSuccessHook],
        # Materials export
        "materials.export:on_copy": list[ExportOnCopyHook],
        "materials.export:on_node": list[ExportOnNodeHook],
        # Materials filter
        "materials.filter:on_hit": list[FilterOnHitHook],
        "materials.filter:on_miss": list[FilterOnMissHook],
        # Website generation
        "pre_generate_website": list[PreGenerateWebsiteHook],
        "post_generate_website": list[PostGenerateWebsiteHook],
    },
    total=False,
)


# =============================================================================
# Execution Utilities
# =============================================================================


def execute_hooks(
    hooks: Hooks | dict[str, list[Any]] | None,
    hook_point_name: str,
    *args,
    **kwargs,
) -> list[Any]:
    """Execute all hooks for a given hook point.

    Hooks are executed in ascending priority order (lower values run first).
    Ties are resolved by insertion order—hooks registered earlier run first.

    Parameters
    ----------
    hooks : Hooks | dict[str, list[Any]] | None
        The hooks dictionary, or None for no hooks. Can be either a typed
        Hooks dict or a generic dict mapping hook point names to lists of
        hook instances.
    hook_point_name : str
        The name of the hook point to execute.
    *args : Any
        Positional arguments to pass to each hook.
    **kwargs : Any
        Keyword arguments to pass to each hook.

    Returns
    -------
    list[Any]
        List of results from each hook, in execution order.

    Raises
    ------
    RuntimeError
        If any hook fails.

    """
    if hooks is None:
        return []

    hooks_dict: dict[str, list] = dict(hooks)  # type: ignore[arg-type]
    hook_list: list = hooks_dict.get(hook_point_name, [])
    if not hook_list:
        return []

    # Sort by priority (stable sort preserves insertion order for ties)
    sorted_hooks = sorted(hook_list, key=lambda h: h.priority)

    results = []
    for hook in sorted_hooks:
        try:
            result = hook(*args, **kwargs)
            results.append(result)
        except Exception as e:
            raise RuntimeError(
                f"Hook '{hook_point_name}' (priority {hook.priority}) failed: {e}"
            ) from e

    return results


@overload
def merge_hook_results(
    results: Sequence[ResolveOverrides | None],
    result_type: type[ResolveOverrides],
) -> ResolveOverrides: ...


@overload
def merge_hook_results(
    results: Sequence[GenerateOverrides | None],
    result_type: type[GenerateOverrides],
) -> GenerateOverrides: ...


def merge_hook_results(
    results: Sequence[ResolveOverrides | GenerateOverrides | None],
    result_type: type[ResolveOverrides] | type[GenerateOverrides],
) -> ResolveOverrides | GenerateOverrides:
    """Merge results from multiple hooks.

    Results are merged in order, with later hooks overriding earlier ones
    for any conflicting keys.

    Parameters
    ----------
    results : Sequence
        Sequence of results from hook execution (may contain None values).
    result_type : type
        The type of result to create (ResolveOverrides or GenerateOverrides).

    Returns
    -------
    ResolveOverrides | GenerateOverrides
        The merged result.

    """
    if result_type is ResolveOverrides:
        merged_functions: dict[str, Callable] = {}
        merged_globals: dict[str, Any] = {}

        for result in results:
            if result is not None and isinstance(result, ResolveOverrides):
                merged_functions.update(result.functions)
                merged_globals.update(result.global_variables)

        return ResolveOverrides(
            functions=merged_functions, global_variables=merged_globals
        )

    elif result_type is GenerateOverrides:
        merged_pages: dict[str, str] = {}
        merged_assets: dict[str, str | bytes] = {}

        for result in results:
            if result is not None and isinstance(result, GenerateOverrides):
                merged_pages.update(result.pages)
                merged_assets.update(result.assets)

        return GenerateOverrides(pages=merged_pages, assets=merged_assets)

    else:
        raise ValueError(f"Unknown result type: {result_type}")


def validate_hook_point_names(hooks: Hooks) -> None:
    """Validate that all hook point names in a hooks dict are known.

    Parameters
    ----------
    hooks : Hooks
        The hooks dictionary to validate.

    Raises
    ------
    ValueError
        If an unknown hook point name is found.

    """
    for hook_point_name in hooks:
        if hook_point_name not in HOOK_POINTS:
            raise ValueError(f"Unknown hook point: {hook_point_name!r}")


def sort_hooks_by_priority(hooks: Hooks) -> Hooks:
    """Pre-sort all hook lists by priority.

    This function creates a new Hooks dict with all hook lists sorted
    by priority. This allows execution to skip the sort step.

    Parameters
    ----------
    hooks : Hooks
        The hooks dictionary to sort.

    Returns
    -------
    Hooks
        A new hooks dictionary with sorted lists.

    """
    sorted_hooks: dict[str, list] = {}
    hooks_dict: dict[str, list] = dict(hooks)  # type: ignore[arg-type]
    for hook_point_name, hook_list in hooks_dict.items():
        sorted_hooks[hook_point_name] = sorted(hook_list, key=lambda h: h.priority)
    return sorted_hooks  # type: ignore[return-value]
