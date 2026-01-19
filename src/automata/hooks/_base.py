"""Base infrastructure for the hooks system.

This module provides the foundational types for the descriptor-based hook system:

- HookInteractor: Handles hook registration and execution
- HookDescriptor: Creates HookInteractor instances bound to a registry
- HooksBase: Base class for Hooks classes that holds the registry
- hook: Decorator to create hook points from function signatures

The hook system uses a descriptor pattern where hook points are defined as
decorated static methods on a Hooks class. Accessing a hook point on an
instance returns a HookInteractor that can be used to register implementations
or execute the hook.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# =============================================================================
# Registry Type
# =============================================================================

HookImpl = tuple[int, Callable[..., Any]]
"""A hook implementation: (priority, callable) tuple."""

Registry = dict[str, list[HookImpl]]
"""Maps hook point names to lists of (priority, callable) tuples."""


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


# =============================================================================
# Default Reducers
# =============================================================================


def _default_reduce[T](results: list[T]) -> T | None:
    """Default reducer: return the last result, or None if empty."""
    return results[-1] if results else None


# =============================================================================
# Hook Interactor
# =============================================================================


class HookInteractor[**P, R]:
    """Handles hook registration and execution for a specific hook point.

    HookInteractor is created by HookDescriptor when accessing a hook point
    on a Hooks instance. It provides methods to register implementations and
    execute all registered implementations.

    Type Parameters
    ---------------
    P : ParamSpec
        The parameter specification for hook implementations.
    R : TypeVar
        The return type of hook implementations.

    Parameters
    ----------
    registry_list : list[HookImpl]
        The list of (priority, callable) tuples for this hook point.
    hook_name : str
        The name of this hook point (for error messages).
    pipeline_arg : str | None
        If set, this hook uses pipeline execution where the output of one
        implementation becomes the input to the next.
    reduce_results : Callable | None
        Function to reduce multiple results into one.
    serialize_args : Callable | None
        Function to serialize arguments for script execution.

    """

    def __init__(
        self,
        registry_list: list[HookImpl],
        hook_name: str,
        *,
        pipeline_arg: str | None = None,
        reduce_results: Callable[[list[R | None]], R | None] | None = None,
        serialize_args: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._registry_list = registry_list
        self._hook_name = hook_name
        self._pipeline_arg = pipeline_arg
        self._reduce_results = reduce_results or _default_reduce
        self._serialize_args = serialize_args

    @property
    def serialize_args(self) -> Callable[..., dict[str, Any]] | None:
        """Get the serialize_args function for this hook."""
        return self._serialize_args

    def register(
        self, priority: int = 50
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Register a hook implementation.

        Parameters
        ----------
        priority : int, optional
            Execution priority (lower runs first). Default is 50.

        Returns
        -------
        Callable
            A decorator that registers the implementation.

        Example
        -------
        >>> @hooks.on_skip.register(priority=10)
        ... def my_hook(path: Path) -> None:
        ...     print(f"Skipped {path}")

        """

        def decorator(hook_impl: Callable[P, R]) -> Callable[P, R]:
            self._registry_list.append((priority, hook_impl))
            return hook_impl

        return decorator

    def append(self, impl: HookImpl) -> None:
        """Append a (priority, callable) tuple directly to the registry.

        This is useful for programmatically adding hook implementations,
        such as script hooks created via from_script().

        Parameters
        ----------
        impl : HookImpl
            A (priority, callable) tuple to add.

        """
        self._registry_list.append(impl)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> list[R] | R:
        """Execute all registered implementations for this hook.

        Implementations are executed in ascending priority order (lower first).
        Ties are resolved by insertion order.

        The execution mode depends on the pipeline_arg setting:

        - If pipeline_arg is None (default): Each implementation receives
          the same arguments and all results are collected into a list.

        - If pipeline_arg is set: The hook runs as a pipeline where the
          output of one implementation becomes the input to the next. The
          pipeline_arg specifies which argument receives the pipeline value.
          Returns the final transformed value instead of a list.

        Returns
        -------
        list[R] | R
            For regular hooks: List of results from each implementation.
            For pipeline hooks: The final transformed value.

        Raises
        ------
        RuntimeError
            If any implementation fails.

        """
        # Sort by priority
        impls = sorted(self._registry_list, key=lambda x: x[0])

        # Pipeline execution mode
        if self._pipeline_arg is not None:
            # First positional arg is the pipeline value
            if args:
                current = args[0]
                other_kwargs = kwargs
            else:
                current = kwargs.pop(self._pipeline_arg)
                other_kwargs = kwargs

            for priority, impl in impls:
                try:
                    result = impl(current, **other_kwargs)
                    if result is not None:
                        current = result
                except Exception as e:
                    raise RuntimeError(
                        f"Hook '{self._hook_name}' (priority {priority}) failed: {e}"
                    ) from e

            return current

        # Regular execution mode
        results: list[R] = []

        for priority, impl in impls:
            try:
                result = impl(*args, **kwargs)
                results.append(result)
            except Exception as e:
                raise RuntimeError(
                    f"Hook '{self._hook_name}' (priority {priority}) failed: {e}"
                ) from e

        return results

    def reduce(self, results: list[R | None]) -> R | None:
        """Reduce multiple hook results into a single value.

        Parameters
        ----------
        results : list[R | None]
            The list of results from hook execution.

        Returns
        -------
        R | None
            The reduced result.

        """
        return self._reduce_results(results)

    def from_script(self, command: str, cwd: Path, priority: int = 50) -> HookImpl:
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
        HookImpl
            A (priority, implementation) tuple ready to append to the registry.

        Raises
        ------
        ValueError
            If the hook is not scriptable (serialize_args is None).

        """
        if self._serialize_args is None:
            raise ValueError(f"Hook '{self._hook_name}' is not scriptable")

        serialize_fn = self._serialize_args

        def script_hook(**kwargs: Any) -> None:
            context_json = json.dumps(serialize_fn(**kwargs), default=_json_serializer)
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
# Hook Descriptor
# =============================================================================


class HookDescriptor[**P, R]:
    """Descriptor that creates HookInteractor instances for hook points.

    When accessed on a Hooks instance, returns a HookInteractor bound to
    that instance's registry.

    Type Parameters
    ---------------
    P : ParamSpec
        The parameter specification for hook implementations.
    R : TypeVar
        The return type of hook implementations.

    """

    def __init__(
        self,
        hook_impl: Callable[P, R],
        *,
        pipeline_arg: str | None = None,
        reduce_results: Callable[[list[R | None]], R | None] | None = None,
        serialize_args: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._hook_impl = hook_impl
        self._hook_name = hook_impl.__name__
        self._pipeline_arg = pipeline_arg
        self._reduce_results = reduce_results
        self._serialize_args = serialize_args
        self.__doc__ = hook_impl.__doc__

    def __get__(
        self, obj: "HooksBase | None", objtype: type | None = None
    ) -> HookInteractor[P, R]:
        if obj is None:
            # Accessed on the class, return descriptor for introspection
            raise AttributeError(
                f"Hook '{self._hook_name}' must be accessed on an instance"
            )
        return HookInteractor[P, R](
            obj._registry.setdefault(self._hook_name, []),
            self._hook_name,
            pipeline_arg=self._pipeline_arg,
            reduce_results=self._reduce_results,
            serialize_args=self._serialize_args,
        )

    @property
    def hook_name(self) -> str:
        """The name of this hook point."""
        return self._hook_name


# =============================================================================
# hook Decorator
# =============================================================================


def hook[**P, R](
    hook_impl: Callable[P, R] | None = None,
    *,
    pipeline_arg: str | None = None,
    reduce_results: Callable[[list[R | None]], R | None] | None = None,
    serialize_args: Callable[..., dict[str, Any]] | None = None,
) -> HookDescriptor[P, R] | Callable[[Callable[P, R]], HookDescriptor[P, R]]:
    """Decorator to create a hook point from a function signature.

    The function body is not used; only the signature matters. Use @staticmethod
    on the decorated function for type checking purposes.

    Parameters
    ----------
    hook_impl : Callable, optional
        The function defining the hook signature.
    pipeline_arg : str | None, optional
        If set, this hook uses pipeline execution. The value specifies which
        argument is passed through the pipeline.
    reduce_results : Callable | None, optional
        Function to reduce multiple results into one.
    serialize_args : Callable | None, optional
        Function to serialize arguments for script execution. If provided,
        the hook becomes scriptable.

    Returns
    -------
    HookDescriptor
        A descriptor that creates HookInteractor instances.

    Example
    -------
    >>> class Hooks(HooksBase):
    ...     @hook
    ...     @staticmethod
    ...     def on_collection(path: Path, collection: Collection) -> None:
    ...         '''Called when a collection is discovered.'''
    ...         raise NotImplementedError

    """

    def decorator(fn: Callable[P, R]) -> HookDescriptor[P, R]:
        return HookDescriptor[P, R](
            fn,
            pipeline_arg=pipeline_arg,
            reduce_results=reduce_results,
            serialize_args=serialize_args,
        )

    if hook_impl is not None:
        return decorator(hook_impl)
    return decorator


# =============================================================================
# Hooks Base Class
# =============================================================================


class HooksBase:
    """Base class for Hooks classes that holds the registry.

    Subclass this to create a Hooks class with hook point definitions.
    Each instance maintains its own registry of hook implementations.

    Example
    -------
    >>> class Hooks(HooksBase):
    ...     @hook
    ...     @staticmethod
    ...     def on_skip(path: Path) -> None:
    ...         '''Called when a directory is skipped.'''
    ...         raise NotImplementedError
    ...
    >>> hooks = Hooks()
    >>> @hooks.on_skip.register(priority=10)
    ... def my_handler(path: Path) -> None:
    ...     print(f"Skipped: {path}")

    """

    def __init__(self) -> None:
        self._registry: Registry = {}

    def copy(self) -> "HooksBase":
        """Create a shallow copy of this Hooks instance.

        The new instance has its own registry with copies of all hook lists.
        """
        new = self.__class__.__new__(self.__class__)
        new._registry = {name: list(impls) for name, impls in self._registry.items()}
        return new

    @classmethod
    def get_hook_names(cls) -> list[str]:
        """Get all hook point names defined on this class.

        Returns
        -------
        list[str]
            List of hook point names.

        """
        names = []
        for name in dir(cls):
            attr = getattr(cls, name, None)
            if isinstance(attr, HookDescriptor):
                names.append(attr.hook_name)
        return names

    def merge_registry(self, registry: Registry) -> None:
        """Merge a registry dictionary into this Hooks instance.

        This is useful for loading hooks from extensions or files. The
        registry uses hook names (strings) as keys.

        Parameters
        ----------
        registry : Registry
            A dictionary mapping hook names to lists of (priority, callable) tuples.

        """
        for hook_name, impls in registry.items():
            self._registry.setdefault(hook_name, []).extend(impls)


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
# Merge Resolve Results
# =============================================================================


def merge_resolve_results(
    results: list[ResolveOverrides | None],
) -> ResolveOverrides | None:
    """Merge results from multiple hooks, skipping None values."""
    merged = ResolveOverrides()
    for result in results:
        if result is not None:
            merged = merged.merge(result)
    return merged
