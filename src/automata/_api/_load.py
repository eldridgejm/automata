"""High-level function for loading configuration and plugins."""

from pathlib import Path

from .._config import Config, read_config
from .._plugin import Plugin

CONFIGURATION_FILENAME = "automata.yaml"


def load(path: Path | None = None) -> tuple[Config, Plugin]:
    """Load the configuration and plugins from an automata project.

    This function reads the automata.yaml configuration file and loads the
    theme plugin specified in the configuration.

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
        - The merged plugin (theme and any additional plugins)

    """
    if path is None:
        path = Path.cwd()

    config = read_config(path / CONFIGURATION_FILENAME)

    # Load the theme as a plugin
    theme_plugin = Plugin.from_spec(
        config.website.theme.use, group="automata.website.themes"
    )

    return config, theme_plugin
