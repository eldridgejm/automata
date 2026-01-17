"""Hook definitions for the automata hook system.

This subpackage contains all hook class definitions organized by domain:
- _materials.py: Hooks for materials discovery, build, export, and filter
- _resolve.py: Hooks for resolution customization
- _website.py: Hooks for website generation
"""

from ._materials import (
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
)
from ._resolve import PreResolveHook
from ._website import PostGenerateWebsiteHook, PreGenerateWebsiteHook

__all__ = [
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
]
