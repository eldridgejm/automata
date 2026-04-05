"""Publisher strategy registry."""

from pathlib import Path
from typing import Any, Callable

Publisher = Callable[[Path, dict[str, Any]], None]

_registry: dict[str, Publisher] = {}


def register(name: str, publisher: Publisher) -> None:
    """Register a publish strategy by name."""
    _registry[name] = publisher


def get(name: str) -> Publisher:
    """Look up a registered publish strategy.

    Raises
    ------
    KeyError
        If no strategy with the given name is registered.

    """
    return _registry[name]


def all() -> dict[str, Publisher]:
    """Return a copy of the full registry."""
    return dict(_registry)
