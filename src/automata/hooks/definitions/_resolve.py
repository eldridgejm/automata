"""Hook definitions for resolution operations.

This module contains hook classes for resolution customization.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from .._base import ResolveOverrides, hook_point


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

    @staticmethod
    def merge_results(results: Sequence[ResolveOverrides | None]) -> ResolveOverrides:
        """Merge results from multiple hooks, skipping None values."""
        merged = ResolveOverrides()
        for result in results:
            if result is not None:
                merged = merged.merge(result)
        return merged
