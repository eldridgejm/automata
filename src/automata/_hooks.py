"""Hook system for Automata.

Hooks allow plugins and configuration to inject custom logic at specific
points in the build process. This module provides utilities for executing
hooks and wrapping shell commands as hook callables.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def execute_hooks(
    hooks: dict[str, list[tuple[int, Callable]]],
    hook_point: str,
    context: dict[str, Any],
) -> list[Any]:
    """Execute all hooks for a given hook point in priority order.

    Hooks are executed in ascending priority order (lower values run first).
    Each hook receives the context dict and may return a result. All results
    are collected and returned as a list.

    Parameters
    ----------
    hooks : dict[str, list[tuple[int, Callable]]]
        Dictionary mapping hook point names to lists of (priority, callable) tuples.
    hook_point : str
        The name of the hook point to execute (e.g., "pre_generate").
    context : dict[str, Any]
        Context dictionary passed to each hook. Contents depend on the hook point.

    Returns
    -------
    list[Any]
        List of results from each hook, in execution order. The caller is
        responsible for interpreting and merging these results based on the
        hook point's contract.

    Raises
    ------
    RuntimeError
        If any hook fails. The error includes the hook point name and priority
        of the failing hook.

    """
    hook_list = hooks.get(hook_point, [])
    if not hook_list:
        return []

    # Sort by priority (lower values first)
    sorted_hooks = sorted(hook_list, key=lambda h: h[0])

    results = []
    for priority, hook in sorted_hooks:
        logger.debug(f"Executing {hook_point} hook (priority {priority})")
        try:
            result = hook(context)
            results.append(result)
        except Exception as e:
            raise RuntimeError(
                f"Hook '{hook_point}' (priority {priority}) failed: {e}"
            ) from e

    return results


def create_shell_hook(
    command: str,
    cwd: Path,
    priority: int = 50,
) -> tuple[int, Callable[[dict[str, Any]], dict[str, Any]]]:
    """Create a hook callable that executes a shell command.

    The shell command receives a JSON-serialized context on stdin and is
    expected to return a JSON object on stdout. For hooks that don't need
    to return data (like post_generate), the command may return empty output.

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
    tuple[int, Callable]
        A (priority, callable) tuple suitable for adding to a plugin's hooks.

    """

    def shell_hook(context: dict[str, Any]) -> dict[str, Any]:
        """Execute the shell command with context as JSON stdin."""
        # Serialize context to JSON
        context_json = json.dumps(context, default=_json_serializer)

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                input=context_json,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Shell hook failed with exit code {e.returncode}:\n{e.stderr}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Shell hook timed out after 300 seconds") from e

        # Parse output (empty output is valid for hooks that don't return data)
        stdout = result.stdout.strip()
        if not stdout:
            return {}

        try:
            result_dict: dict[str, Any] = json.loads(stdout)
            return result_dict
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Shell hook returned invalid JSON: {e}\nOutput: {stdout}"
            ) from e

    return (priority, shell_hook)


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
