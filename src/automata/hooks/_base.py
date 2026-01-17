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
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Self

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

    def merge(self, other: "GenerateOverrides") -> "GenerateOverrides":
        """Merge another GenerateOverrides into this one.

        Returns a new instance with combined values. Values from `other`
        override values from `self` for conflicting keys.
        """
        return GenerateOverrides(
            pages={**self.pages, **other.pages},
            assets={**self.assets, **other.assets},
        )


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
                        timeout=300,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(
                        f"Shell hook failed with exit code {e.returncode}"
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
