"""Unified Hook System for Automata.

This module provides a typed hook system that replaces the separate callbacks
and hooks systems with a single, unified approach.

Hooks allow extensions and configuration to inject custom logic at specific
points in the build process. Each hook is defined using the `@define_hook`
decorator and registered using the `HookClass.register()` method.

Hook Point Naming
-----------------

Hook points follow two naming patterns based on their scope:

**Function-scoped hooks** use the pattern `module.function:on_event`:
- `materials.discover:on_collection` — called only within `materials.discover()`
- `materials.build:on_recipe` — called only within `materials.build()`

**Top-level hooks** use simple names without a module prefix:
- `pre_resolve` — called from multiple places that invoke resolution
- `pre_generate_website` — called by `build()`, `deploy()`, `preview()`, etc.

Execution Semantics
-------------------

Hooks are executed in ascending priority order (lower values run first).
Ties are resolved by insertion order—hooks registered earlier run first.

For hooks that return overrides (`pre_resolve`, `pre_generate_website`),
results are merged in execution order. Later hooks override earlier ones.

If a hook raises an exception, execution stops and the error propagates.
Hooks should fail fast rather than silently swallow errors.

Script Hooks
------------

Script hooks are fire-and-forget—they cannot return values or affect program flow.
Scriptable hooks have a `serialize_args` function assigned. Call `from_script()`
to create a script-based implementation.

Usage
-----

Define a hook::

    @define_hook("materials.discover:on_skip")
    def DiscoverOnSkipHook(path: Path) -> None: ...

    # Make it scriptable
    DiscoverOnSkipHook.serialize_args = lambda path: {"path": path}

Register an implementation::

    @DiscoverOnSkipHook.register(hooks, priority=10)
    def my_hook(path: Path) -> None:
        print(f"Skipped {path}")

Execute hooks::

    DiscoverOnSkipHook.execute(hooks, {"path": path})

"""

from ._base import (
    HOOK_POINTS,
    Hook,
    Registry,
    ResolveOverrides,
    WebsiteContent,
    define_hook,
)
from ._website import PostGenerateWebsiteHook, PreGenerateWebsiteHook

# NOTE: Materials hooks (DiscoverOn*, BuildOn*, ExportOn*, FilterOn*, PreResolve*)
# are not re-exported here to avoid circular imports. Import them from their
# source modules: automata.materials._discover, automata.materials._build, etc.
# The main automata package re-exports them for convenience.


def validate_hook_point_names(hooks: Registry) -> None:
    """Validate that all hook classes in a registry are known.

    Parameters
    ----------
    hooks : Registry
        The hooks registry to validate.

    Raises
    ------
    ValueError
        If an unknown hook class is found.

    """
    for hook_class in hooks:
        if not hasattr(hook_class, "hook_point"):
            raise ValueError(f"Unknown hook class: {hook_class.__name__}")
        if hook_class.hook_point not in HOOK_POINTS:
            raise ValueError(f"Unknown hook point: {hook_class.hook_point!r}")


__all__ = [
    # Registry types
    "HOOK_POINTS",
    "Hook",
    "Registry",
    "define_hook",
    # Return types
    "ResolveOverrides",
    "WebsiteContent",
    # website hooks
    "PreGenerateWebsiteHook",
    "PostGenerateWebsiteHook",
    # Validation
    "validate_hook_point_names",
]
