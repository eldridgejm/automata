"""Base types and utilities for the hooks system.

This module provides the foundational types used by the hook system:
- Registry for hook point registration
- Return types for hooks that provide overrides
- ScriptableHookMixin for hooks that can be invoked as shell scripts
"""

from __future__ import annotations

import inspect
import json
import subprocess
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Self

# =============================================================================
# Base Class
# =============================================================================


class HookBase(ABC):
    """Base class for all hooks.

    All hooks must have a priority attribute that determines execution order.
    Lower priority values execute first.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first). Defaults to 50.

    """

    priority: int = 50


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

    def merge(self, other: "ResolveOverrides") -> "ResolveOverrides":
        """Merge another ResolveOverrides into this one.

        Returns a new instance with combined values. Values from `other`
        override values from `self` for conflicting keys.
        """
        return ResolveOverrides(
            functions={**self.functions, **other.functions},
            global_variables={**self.global_variables, **other.global_variables},
        )


@dataclass
class WebsiteContent:
    """Content, assets, and static files for website generation.

    This dataclass is passed through the pre_generate_website hook chain,
    allowing each hook to transform the content before generation.

    Attributes
    ----------
    content : dict[str, Any]
        Content files to render. Keys are relative paths (e.g., "about.html"),
        values are content (string, bytes, or Traversable).
    assets : dict[str, Any]
        Asset files to copy. Keys are relative paths, values are content.
    static_files : dict[str, Any]
        Static files to copy. Keys are relative paths, values are content.

    """

    content: dict[str, Any] = field(default_factory=dict)
    assets: dict[str, Any] = field(default_factory=dict)
    static_files: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# ScriptableHookMixin
# =============================================================================


class ScriptableHookMixin:
    """Mixin for hooks that support script invocation.

    Script hooks are fire-and-forget—they cannot return values or affect
    program flow. This mixin provides a `from_script` factory method that
    creates a hook instance from a shell command.

    The default `serialize_args` implementation introspects the `__call__`
    signature and serializes all arguments. Subclasses can override this
    method for custom serialization (e.g., expanding complex objects).
    """

    def serialize_args(self, *args, **kwargs) -> dict:
        """Serialize call arguments to JSON-compatible dict for script stdin.

        The default implementation binds arguments to the `__call__` signature
        and returns them as a dictionary. Override this method to customize
        serialization (e.g., to expand complex objects into their fields).

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
        sig = inspect.signature(self.__call__)  # type: ignore[operator]
        bound = sig.bind(self, *args, **kwargs)
        bound.apply_defaults()

        # Remove 'self' and return the rest
        result = dict(bound.arguments)
        result.pop("self", None)
        return result

    @classmethod
    def from_script(cls, command: str, cwd: Path, priority: int = 50) -> Self:
        """Create a hook instance that executes a shell command.

        The shell command receives a JSON-serialized context on stdin.
        Script hooks cannot return values that modify the generation process;
        they are intended for side effects only (e.g., running post-processing
        scripts). Output from the command is passed through to the terminal.

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
        parent_sig = inspect.signature(cls.__call__)

        class ScriptHookInstance(cls):  # type: ignore[valid-type, misc]
            """Dynamically-created script hook instance."""

            def __init__(self):
                self.priority = priority

            def __call__(self, *args, **kwargs):
                context_json = json.dumps(
                    self.serialize_args(*args, **kwargs), default=_json_serializer
                )
                try:
                    subprocess.run(
                        command,
                        shell=True,
                        cwd=str(cwd),
                        input=context_json,
                        text=True,
                        timeout=300,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(
                        f"Shell hook failed with exit code {e.returncode}"
                    ) from e
                except subprocess.TimeoutExpired as e:
                    raise RuntimeError("Shell hook timed out after 300 seconds") from e

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
