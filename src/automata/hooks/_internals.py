"""Internal implementation of the hooks system."""

import dataclasses
import json
import subprocess
from collections.abc import Callable
from typing import Any, get_origin, get_type_hints


def _default_serializer(value: object) -> str:
    """Default serializer for shell script hooks.

    Converts dataclasses to JSON strings; raises TypeError for other values.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return json.dumps(dataclasses.asdict(value), default=str)
    raise TypeError(f"Cannot serialize {type(value).__name__}; expected a dataclass")


class ObserverHook[T]:
    """A hook that notifies multiple observers when an event occurs.

    Observer hooks take a single argument (typically a dataclass) and do not
    return values. All registered implementations are called in order when
    the hook is invoked.
    """

    def __init__(
        self,
        *,
        allow_shell: bool = True,
        serializer: Callable[[T], str] | None = None,
    ) -> None:
        self.allow_shell = allow_shell
        self.serializer = _default_serializer if serializer is None else serializer
        self.implementations: list[tuple[int, Callable[[T], None]]] = []

    def register(
        self, *, priority: int = 0
    ) -> Callable[[Callable[[T], None]], Callable[[T], None]]:
        """Register a hook implementation with the given priority."""

        def decorator(fn: Callable[[T], None]) -> Callable[[T], None]:
            self.implementations.append((priority, fn))
            self.implementations.sort(key=lambda entry: entry[0])
            return fn

        return decorator

    def register_shell_script(self, command: str, *, priority: int = 0) -> None:
        """Register a shell script as a hook implementation."""
        if not self.allow_shell:
            raise TypeError("Shell scripts are not enabled for this hook")

        def _shell_impl(value: T) -> None:
            payload = self.serializer(value)
            subprocess.run(command, input=payload, shell=True, text=True)

        self.register(priority=priority)(_shell_impl)

    def __call__(self, args: T) -> None:
        for _, fn in self.implementations:
            fn(args)


class PipelineHook[T]:
    """A hook that transforms a value through a chain of implementations.

    Each registered implementation receives the output of the previous one.
    The final transformed value is returned.
    """

    def __init__(self) -> None:
        self.implementations: list[tuple[int, Callable[[T], T]]] = []

    def register(
        self, *, priority: int = 0
    ) -> Callable[[Callable[[T], T]], Callable[[T], T]]:
        """Register a hook implementation with the given priority."""

        def decorator(fn: Callable[[T], T]) -> Callable[[T], T]:
            self.implementations.append((priority, fn))
            self.implementations.sort(key=lambda entry: entry[0])
            return fn

        return decorator

    def __call__(self, args: T) -> T:
        for _, fn in self.implementations:
            args = fn(args)
        return args


def _hydrate_hook(
    cls: type, name: str, hook_type: type[ObserverHook[Any] | PipelineHook[Any]]
) -> ObserverHook[Any] | PipelineHook[Any]:
    """Create a fresh hook instance with the same config as the class template."""
    template = getattr(cls, name, None)
    if isinstance(template, ObserverHook):
        return ObserverHook(
            allow_shell=template.allow_shell,
            serializer=template.serializer,
        )
    elif isinstance(template, PipelineHook):
        return PipelineHook()
    return hook_type()


class HooksBase:
    """Base class for hook containers.

    Subclasses define hooks as class attributes. Each instance gets its own
    fresh hook instances with separate implementation lists.
    """

    def __init__(self) -> None:
        hints = get_type_hints(type(self))
        for name, hint in hints.items():
            origin = get_origin(hint)
            if origin in (ObserverHook, PipelineHook):
                hook = _hydrate_hook(type(self), name, origin)
                setattr(self, name, hook)
