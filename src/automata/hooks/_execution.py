"""Hook execution utilities.

This module provides functions for executing hooks and managing hook collections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._base import HOOK_POINTS

if TYPE_CHECKING:
    from . import Hooks


def execute_hooks(
    hooks: "Hooks | dict[str, list[Any]] | None",
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


def validate_hook_point_names(hooks: "Hooks") -> None:
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


def sort_hooks_by_priority(hooks: "Hooks") -> "Hooks":
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
