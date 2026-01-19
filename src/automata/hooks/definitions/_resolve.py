"""Hook definitions for resolution operations.

This module contains hook classes for resolution customization.
"""

from __future__ import annotations

from pathlib import Path

from .._base import ResolveOverrides, define_hook


@define_hook("pre_resolve")
def PreResolveHook(call_site: str, path: Path) -> ResolveOverrides | None:
    """Called before resolve() is called.

    Can provide extra functions/variables for resolution.

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


def _merge_resolve_results(
    results: list[ResolveOverrides | None],
) -> ResolveOverrides | None:
    """Merge results from multiple hooks, skipping None values."""
    merged = ResolveOverrides()
    for result in results:
        if result is not None:
            merged = merged.merge(result)
    return merged


PreResolveHook.reduce_results = _merge_resolve_results
