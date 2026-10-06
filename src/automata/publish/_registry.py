"""Publisher strategy registry."""

from typing import Any, Callable

# A publisher is called as publisher(build_directory, config, project_directory).
# One that can do a dry run also takes a dry_run keyword argument, and given
# dry_run=True, returns the list of Changes it would make instead of publishing.
Publisher = Callable[..., Any]

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
