"""Applying extensions to hooks, and checks on sets of extensions."""

from __future__ import annotations

from collections.abc import Iterable
from typing import get_type_hints

from ..exceptions import Error
from ..hooks import RenderHooks, WebsiteInputs
from ._types import Extension


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
        hook_point = getattr(hooks, hook_name, None)
        if hook_point is None:
            known = sorted(get_type_hints(type(hooks)))
            raise Error(
                f'Extension "{extension.name}" registers unknown hook '
                f'"{hook_name}". Known hooks: {", ".join(known)}.'
            )
        hook_point.register(priority=priority)(fn)


def apply_extensions(
    extensions: Iterable[Extension],
    hooks: object,
    priority: int = 0,
) -> None:
    """Register several extensions' hooks onto a hooks instance.

    Like :func:`apply_extension`, but each extension (including shared
    dependencies) is applied at most once across all of *extensions*.

    """
    applied: set[str] = set()
    for extension in extensions:
        apply_extension(extension, hooks, priority=priority, _applied=applied)


def all_extensions(extensions: Iterable[Extension]) -> dict[str, Extension]:
    """Return the given extensions and their dependencies, keyed by name.

    Raises
    ------
    automata.exceptions.Error
        If two different extensions have the same name.

    """
    found: dict[str, Extension] = {}

    def visit(extension: Extension) -> None:
        existing = found.get(extension.name)
        if existing is extension:
            return
        if existing is not None:
            raise Error(
                f'Two different extensions are named "{extension.name}". '
                f"Extension names must be unique."
            )
        found[extension.name] = extension
        for dep in extension.dependencies:
            visit(dep)

    for extension in extensions:
        visit(extension)

    return found


def check_theme(theme: Extension) -> None:
    """Check that an extension can serve as a theme.

    A theme (together with its dependencies) must provide a ``page.html``
    template.

    Raises
    ------
    automata.exceptions.Error
        If the theme does not provide ``page.html``.

    """
    hooks = RenderHooks()
    apply_extension(theme, hooks)
    inputs = hooks.on_render_collect(WebsiteInputs())
    if "page.html" not in inputs.templates:
        raise Error(f'Theme "{theme.name}" does not provide a "page.html" template.')
