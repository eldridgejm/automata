"""High-level function for loading configuration and extensions."""

from pathlib import Path
from typing import cast

from .._config import Config, read_config
from ..extension import Extension, merge_extensions
from ..hooks import HOOK_POINTS, Hooks, ScriptableHookMixin

CONFIGURATION_FILENAME = "automata.yaml"


def load(path: Path | None = None) -> tuple[Config, Extension]:
    """Load the configuration and extensions from an automata project.

    This function reads the automata.yaml configuration file, loads the
    theme extension specified in the configuration, and merges in any hooks
    defined in the configuration file.

    Parameters
    ----------
    path : Path | None
        The path to the automata project directory. If None, uses the
        current working directory.

    Returns
    -------
    tuple[Config, Extension]
        A tuple containing:
        - The loaded configuration
        - The merged extension (theme extension + config hooks)

    """
    if path is None:
        path = Path.cwd()

    config = read_config(path / CONFIGURATION_FILENAME)

    # Load the theme as a extension
    theme_extension = Extension.from_spec(
        config.website.theme.use, group="automata.website.themes"
    )

    # Convert config hooks to a synthetic extension
    config_hooks_extension = _config_hooks_to_extension(config, cwd=path)

    # Merge theme extension with config hooks
    merged_extension = merge_extensions([theme_extension, config_hooks_extension])

    return config, merged_extension


def _config_hooks_to_extension(config: Config, cwd: Path) -> Extension:
    """Convert hooks defined in config to a Extension.

    This wraps each shell command hook in a hook instance and creates a
    Extension containing those hooks.

    Only hooks that inherit from ScriptableHookMixin can be defined in config,
    since shell hooks cannot return values.

    Parameters
    ----------
    config : Config
        The loaded configuration.
    cwd : Path
        Working directory for shell commands.

    Returns
    -------
    Extension
        A extension containing only hooks (no templates, elements, etc.).

    Raises
    ------
    ValueError
        If an unknown or non-scriptable hook point is specified.

    """
    hooks_dict: dict[str, list] = {}

    for hook_point, hook_config in config.hooks.items():
        if hook_point not in HOOK_POINTS:
            raise ValueError(f"Unknown hook point: {hook_point!r}")

        hook_class = HOOK_POINTS[hook_point]

        if not issubclass(hook_class, ScriptableHookMixin):
            raise ValueError(
                f"Hook point {hook_point!r} does not support shell scripts "
                f"(it must return a value)"
            )

        hook = hook_class.from_script(
            command=hook_config.command,
            cwd=cwd,
            priority=hook_config.priority,
        )
        hooks_dict[hook_point] = [hook]

    return Extension(hooks=cast(Hooks, hooks_dict))
