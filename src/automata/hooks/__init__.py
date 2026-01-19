"""Unified Hook System for Automata.

This module provides a typed hook system that replaces the separate callbacks
and hooks systems with a single, unified approach.

Hooks allow extensions and configuration to inject custom logic at specific
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
Output from script hooks is passed through to the terminal.
"""

from typing import TypedDict

# Re-export base types
from ._base import (
    HOOK_POINTS,
    HookBase,
    ResolveOverrides,
    ScriptableHookMixin,
    WebsiteContent,
    hook_point,
)

# Re-export execution utilities
from ._execution import (
    execute_hooks,
    execute_pre_generate_hooks,
    sort_hooks_by_priority,
    validate_hook_point_names,
)

# Re-export all hook definitions
from .definitions import (
    BuildOnMissingHook,
    BuildOnNotReadyHook,
    BuildOnRecipeHook,
    BuildOnStartHook,
    BuildOnSuccessHook,
    BuildOnTooSoonHook,
    DiscoverOnCollectionHook,
    DiscoverOnPublicationHook,
    DiscoverOnSkipHook,
    ExportOnCopyHook,
    ExportOnNodeHook,
    FilterOnHitHook,
    FilterOnMissHook,
    PostGenerateWebsiteHook,
    PreGenerateWebsiteHook,
    PreResolveHook,
)

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

__all__ = [
    # Registry
    "HOOK_POINTS",
    "hook_point",
    # Base class
    "HookBase",
    # Return types
    "ResolveOverrides",
    "WebsiteContent",
    # Mixin
    "ScriptableHookMixin",
    # materials.discover hooks
    "DiscoverOnCollectionHook",
    "DiscoverOnPublicationHook",
    "DiscoverOnSkipHook",
    # materials.build hooks
    "BuildOnStartHook",
    "BuildOnTooSoonHook",
    "BuildOnNotReadyHook",
    "BuildOnMissingHook",
    "BuildOnRecipeHook",
    "BuildOnSuccessHook",
    # materials.export hooks
    "ExportOnCopyHook",
    "ExportOnNodeHook",
    # materials.filter hooks
    "FilterOnHitHook",
    "FilterOnMissHook",
    # resolution hooks
    "PreResolveHook",
    # website hooks
    "PreGenerateWebsiteHook",
    "PostGenerateWebsiteHook",
    # TypedDict
    "Hooks",
    # Execution utilities
    "execute_hooks",
    "execute_pre_generate_hooks",
    "validate_hook_point_names",
    "sort_hooks_by_priority",
]
