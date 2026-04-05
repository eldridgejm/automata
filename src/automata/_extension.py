"""Extension: a collection of hooks that customize automata's behavior."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

import smartconfig.types


@dataclasses.dataclass
class Extension:
    """A collection of hooks that customize automata's behavior.

    An extension is the fundamental unit of customization in automata. It maps
    hook point names to callables that are registered when the extension is
    applied. For example, a theme extension registers a hook on
    ``on_website_collect`` to provide templates, static files, and elements.

    Extensions can declare *dependencies* — other extensions that are
    automatically applied first.

    Attributes
    ----------
    name : str
        A human-readable name for the extension.
    hooks : dict[str, Callable]
        A mapping of hook point names to callables. Each key must correspond
        to a hook defined on :class:`automata.hooks.Hooks`.
    config : dict[str, Any]
        Optional configuration for the extension.
    schema : smartconfig.types.Schema | None
        Optional schema for validating *config*.
    dependencies : list[Extension]
        Extensions that must be applied before this one.

    """

    name: str
    hooks: dict[str, Callable]
    config: dict[str, Any] = dataclasses.field(default_factory=dict)
    schema: smartconfig.types.Schema | None = None
    dependencies: list[Extension] = dataclasses.field(default_factory=list)


def apply_extension(
    extension: Extension,
    hooks: object,
    priority: int = 0,
    _applied: set[str] | None = None,
) -> None:
    """Register all of an extension's hooks onto a hooks instance.

    Dependencies are applied first, and each extension is applied at most
    once (tracked by name).

    Parameters
    ----------
    extension : Extension
        The extension whose hooks should be registered.
    hooks : object
        A hooks instance (e.g., :class:`automata.hooks.Hooks`) with hook
        point attributes.
    priority : int
        The priority at which to register each hook. Lower values run first.

    Raises
    ------
    AttributeError
        If *hooks* does not have a hook point matching a key in
        *extension.hooks*.

    """
    if _applied is None:
        _applied = set()

    if extension.name in _applied:
        return

    for dep in extension.dependencies:
        apply_extension(dep, hooks, priority=priority, _applied=_applied)

    _applied.add(extension.name)

    for hook_name, fn in extension.hooks.items():
        hook_point = getattr(hooks, hook_name)
        hook_point.register(priority=priority)(fn)
