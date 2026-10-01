"""Loading extensions from installed packages' entry points."""

from __future__ import annotations

import importlib.metadata as metadata
from typing import Any

from ..exceptions import Error
from ._common import extension_from_module
from ._types import EXTENSIONS_GROUP, THEMES_GROUP, Extension


def extension_from_entry_point(
    entry_point_name: str,
    config: dict[str, Any] | None = None,
    *,
    group: str = EXTENSIONS_GROUP,
) -> Extension:
    """Create an Extension from an entry point.

    The entry point should refer to a module that exports either:

    1. ``make_extension(config) -> Extension``, a factory called with the
       extension's validated configuration. If the module also exports
       ``schema``, the configuration is validated against it (and defaults
       applied) before the factory is called. Each call builds a new
       Extension, so its hooks can safely close over *config*.
    2. ``extension``, an :class:`Extension` that takes no configuration.

    Parameters
    ----------
    entry_point_name : str
        The name of the entry point within *group*.
    config : dict[str, Any] | None
        Optional configuration for the extension.
    group : str
        The entry point group: :data:`EXTENSIONS_GROUP` (the default) or
        :data:`THEMES_GROUP`.

    Returns
    -------
    Extension
        The created Extension.

    Raises
    ------
    automata.exceptions.Error
        If the entry point is not found, the module exports neither
        ``make_extension`` nor ``extension``, or the configuration is invalid.

    """
    all_entry_points = metadata.entry_points()
    entry_points = all_entry_points.select(group=group)
    kind = "theme" if group == THEMES_GROUP else "extension"

    if entry_point_name not in entry_points.names:
        message = f'Unknown {kind} "{entry_point_name}".'
        if group == EXTENSIONS_GROUP and entry_point_name in (
            all_entry_points.select(group=THEMES_GROUP).names
        ):
            message += (
                f' "{entry_point_name}" is a theme; set it with website.theme, '
                f"not under extensions."
            )
        elif group == THEMES_GROUP and entry_point_name in (
            all_entry_points.select(group=EXTENSIONS_GROUP).names
        ):
            message += (
                f' "{entry_point_name}" is an extension, not a theme; list it '
                f"under extensions."
            )
        else:
            available = ", ".join(sorted(entry_points.names)) or "none"
            message += (
                f" Available {kind}s: {available}. To load an extension from a "
                f"directory, give a path containing a slash "
                f'(e.g., "./{entry_point_name}").'
            )
        raise Error(message)

    module = entry_points[entry_point_name].load()
    return extension_from_module(
        module, entry_point_name, kind, config, getattr(module, "schema", None)
    )
