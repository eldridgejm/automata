"""Base types and utilities for the hooks system.

This module provides the foundational types used by the hook system:
- Hook: Generic base class for type-safe hooks using ParamSpec
- Registry: Type alias for hook storage
- define_hook: Decorator to create hook classes from function signatures
- Return types for hooks that provide overrides
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar

# =============================================================================
# Registry Type
# =============================================================================

Registry = dict[type, list[tuple[int, Callable]]]
"""Maps hook classes to (priority, implementation) pairs."""


# =============================================================================
# Registry
# =============================================================================

HOOK_POINTS: dict[str, type] = {}
"""Registry mapping hook point names to their hook classes."""


# =============================================================================
# Default Reducers
# =============================================================================


def _default_reduce[T](results: list[T]) -> T | None:
    """Default reducer: return the last result, or None if empty."""
    return results[-1] if results else None


# =============================================================================
# Hook Base Class
# =============================================================================


class Hook[**P, R]:
    """Base class for typed hooks using ParamSpec.

    Hook implementations are plain functions registered via the `register()`
    decorator. Hooks are executed via the `execute()` class method.

    Type Parameters
    ---------------
    P : ParamSpec
        The parameter specification for hook implementations.
    R : TypeVar
        The return type of hook implementations.

    Class Attributes
    ----------------
    hook_point : str
        The hook point name (e.g., "materials.discover:on_skip").
    serialize_args : Callable | None
        Function to serialize arguments for script execution.
        None means the hook is not scriptable.
    reduce_results : Callable
        Function to reduce multiple results into one.

    """

    hook_point: ClassVar[str]
    serialize_args: Callable[..., dict] | None = None
    reduce_results: Callable[[list[R | None]], R | None] = _default_reduce

    @classmethod
    def register(
        cls, registry: Registry, /, priority: int = 50
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Register a hook implementation.

        Parameters
        ----------
        registry : Registry
            The registry to add the implementation to.
        priority : int, optional
            Execution priority (lower runs first). Default is 50.

        Returns
        -------
        Callable
            A decorator that registers the implementation.

        Example
        -------
        >>> @DiscoverOnSkipHook.register(hooks, priority=10)
        ... def my_hook(path: Path) -> None:
        ...     print(f"Skipped {path}")

        """

        def decorator(hook_impl: Callable[P, R]) -> Callable[P, R]:
            registry.setdefault(cls, []).append((priority, hook_impl))
            return hook_impl

        return decorator

    @classmethod
    def execute(
        cls,
        registry: Registry | None,
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> list[R | None]:
        """Execute all registered implementations for this hook.

        Implementations are executed in ascending priority order (lower first).
        Ties are resolved by insertion order.

        Parameters
        ----------
        registry : Registry | None
            The hook registry, or None for no hooks.
        *args : P.args
            Positional arguments to pass to each implementation.
        **kwargs : P.kwargs
            Keyword arguments to pass to each implementation.

        Returns
        -------
        list[R | None]
            List of results from each implementation, in execution order.

        Raises
        ------
        RuntimeError
            If any implementation fails.

        """
        if registry is None:
            return []

        impls = sorted(registry.get(cls, []), key=lambda x: x[0])
        results = []

        for priority, impl in impls:
            try:
                result = impl(*args, **kwargs)
                results.append(result)
            except Exception as e:
                raise RuntimeError(
                    f"Hook '{cls.hook_point}' (priority {priority}) failed: {e}"
                ) from e

        return results

    @classmethod
    def execute_pipeline(
        cls,
        registry: Registry | None,
        initial: R,
        /,
        **kwargs,
    ) -> R:
        """Execute implementations as a pipeline, passing output through.

        Each implementation receives the output of the previous one as its
        first argument. This is useful for hooks that transform content.

        Parameters
        ----------
        registry : Registry | None
            The hook registry, or None for no hooks.
        initial : R
            The initial value to pass to the first implementation.
        **kwargs : P.kwargs
            Additional keyword arguments to pass to each implementation.

        Returns
        -------
        R
            The final value after all implementations have processed it.

        Raises
        ------
        RuntimeError
            If any implementation fails.

        """
        if registry is None:
            return initial

        impls = sorted(registry.get(cls, []), key=lambda x: x[0])
        current = initial

        for priority, impl in impls:
            try:
                result = impl(current, **kwargs)
                if result is not None:
                    current = result
            except Exception as e:
                raise RuntimeError(
                    f"Hook '{cls.hook_point}' (priority {priority}) failed: {e}"
                ) from e

        return current

    @classmethod
    def from_script(
        cls, command: str, cwd: Path, priority: int = 50
    ) -> tuple[int, Callable[P, None]]:
        """Create a script-based hook implementation.

        The shell command receives a JSON-serialized context on stdin.
        Script hooks cannot return values; they are for side effects only.

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
            A (priority, implementation) tuple ready to append to a registry.

        Raises
        ------
        ValueError
            If the hook is not scriptable (serialize_args is None).

        """
        if cls.serialize_args is None:
            raise ValueError(f"{cls.__name__} is not scriptable")

        # Get the signature from serialize_args for the wrapper
        serialize_fn = cls.serialize_args

        def script_hook(*args, **kwargs) -> None:
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

        return (priority, script_hook)


# =============================================================================
# Hook Definition Decorator
# =============================================================================


def define_hook[**P, R](
    hook_point: str,
) -> Callable[[Callable[P, R]], type[Hook[P, R | None]]]:
    """Create a hook class from a function signature.

    The function body is not used; only the signature matters. The return
    type is automatically widened to `R | None` to allow implementations
    to return None.

    Parameters
    ----------
    hook_point : str
        The hook point name (e.g., "materials.discover:on_skip").

    Returns
    -------
    Callable
        A decorator that creates a Hook subclass with the given signature.

    Example
    -------
    >>> @define_hook("materials.discover:on_skip")
    ... def DiscoverOnSkipHook(path: Path) -> None: ...
    >>>
    >>> # Make it scriptable
    >>> DiscoverOnSkipHook.serialize_args = lambda path: {"path": path}

    """

    def decorator(hook_proto: Callable[P, R]) -> type[Hook[P, R | None]]:
        class HookClass(Hook[P, R | None]):
            pass

        HookClass.__name__ = hook_proto.__name__
        HookClass.__qualname__ = hook_proto.__qualname__
        HookClass.__doc__ = hook_proto.__doc__
        HookClass.hook_point = hook_point

        # Register in the global hook points registry
        HOOK_POINTS[hook_point] = HookClass

        return HookClass

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
# JSON Serialization Helper
# =============================================================================


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
