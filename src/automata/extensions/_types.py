"""The Extension type and entry point group names."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

import smartconfig.types

# entry point groups: themes are set with website.theme, extensions are listed
# under extensions:
THEMES_GROUP = "automata.themes"
EXTENSIONS_GROUP = "automata.extensions"


@dataclasses.dataclass
class Extension:
    """A collection of hooks that customize automata's behavior.

    An extension is the fundamental unit of customization in automata. It maps
    hook point names to callables that are registered when the extension is
    applied. For example, a theme extension registers a hook on
    ``on_render_collect`` to provide templates, static files, and elements.

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
