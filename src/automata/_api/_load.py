"""High-level function for loading configuration and plugins."""

from pathlib import Path

from .._config import Config, read_config
from .._hooks import create_shell_hook
from .._plugin import Plugin, merge_plugins

CONFIGURATION_FILENAME = "automata.yaml"


def load(path: Path | None = None) -> tuple[Config, Plugin]:
    """Load the configuration and plugins from an automata project.

    This function reads the automata.yaml configuration file, loads the
    theme plugin specified in the configuration, and merges in any hooks
    defined in the configuration file.

    Parameters
    ----------
    path : Path | None
        The path to the automata project directory. If None, uses the
        current working directory.

    Returns
    -------
    tuple[Config, Plugin]
        A tuple containing:
        - The loaded configuration
        - The merged plugin (theme plugin + config hooks)

    """
    if path is None:
        path = Path.cwd()

    config = read_config(path / CONFIGURATION_FILENAME)

    # Load the theme as a plugin
    theme_plugin = Plugin.from_spec(
        config.website.theme.use, group="automata.website.themes"
    )

    # Convert config hooks to a synthetic plugin
    config_hooks_plugin = _config_hooks_to_plugin(config, cwd=path)

    # Merge theme plugin with config hooks
    merged_plugin = merge_plugins([theme_plugin, config_hooks_plugin])

    return config, merged_plugin


def _config_hooks_to_plugin(config: Config, cwd: Path) -> Plugin:
    """Convert hooks defined in config to a Plugin.

    This wraps each shell command hook in a callable and creates a
    Plugin containing those hooks.

    Parameters
    ----------
    config : Config
        The loaded configuration.
    cwd : Path
        Working directory for shell commands.

    Returns
    -------
    Plugin
        A plugin containing only hooks (no templates, elements, etc.).

    """
    hooks = {}

    for hook_point, hook_config in config.hooks.items():
        priority, hook_fn = create_shell_hook(
            command=hook_config.command,
            cwd=cwd,
            priority=hook_config.priority,
        )
        hooks[hook_point] = [(priority, hook_fn)]

    return Plugin(hooks=hooks)
