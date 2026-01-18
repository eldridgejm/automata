from pathlib import Path
from typing import Any

import smartconfig

from .exceptions import Error
from .util.resolution import resolve
from .util.yaml import parse_yaml

CONFIGURATION_FILENAME = "automata.yaml"


class ExtensionConfig(smartconfig.Prototype):
    """Configuration for a extension."""

    # which extension to use. If this contains slashes, it is treated as a path to a
    # extension directory. Otherwise, it is treated as the name of an entry point.
    use: str

    # additional configuration options to pass to the extension
    config: Any = {}


class ShellHookConfig(smartconfig.Prototype):
    """Configuration for a shell hook in automata.yaml.

    Example usage in automata.yaml::

        hooks:
          pre_generate:
            command: "python scripts/generate_calendar.py"
            priority: 50
    """

    # the shell command to execute
    command: str

    # execution priority (lower values run first)
    priority: int = 50


class WebsiteConfig(smartconfig.Prototype):
    """Configuration for the website."""

    # path to the directory containing the pages and materials
    content_directory: str

    # name of the subdirectory within the build directory where materials will be copied
    materials_directory_name: str = "materials"

    # path to the output directory where the website will be built
    build_directory: str

    # suffix indicating that a file should not be rendered. If None, all files
    # will be rendered.
    no_render_suffix: str | None = ".no_render"

    # base path for the website (e.g., "/" or "/course/")
    base_path: str = "/"

    theme: ExtensionConfig = ExtensionConfig(use="default")


class Config(smartconfig.Prototype):
    """Top-level configuration for automata."""

    # a dictionary of variables to be made available globally, including in website
    # pages and configuration files
    vars: dict[str, Any] = {}

    # configuration for the website
    website: WebsiteConfig

    # shell hooks to run at various points in the build process
    hooks: dict[str, ShellHookConfig] = {}

    # list of paths to plugin directories. Each plugin directory should contain
    # a hooks/ subdirectory with an __init__.py that exports a `hooks` dictionary
    plugins: list[str] = []


def find_config(start_path: Path) -> Path | None:
    """Find the automata.yaml config file by searching upwards from start_path.

    This function walks up the directory tree from the given path until it finds
    an automata.yaml file or reaches the filesystem root.

    Parameters
    ----------
    start_path : Path
        The path to start searching from. If this is a file, searching starts
        from its parent directory.

    Returns
    -------
    Path | None
        The path to the automata.yaml config file if found, None otherwise.

    """
    # Start from the directory (or parent if start_path is a file)
    if start_path.is_file():
        search_dir = start_path.parent.resolve()
    else:
        search_dir = start_path.resolve()

    # Walk up the directory tree
    while search_dir != search_dir.parent:  # Not at filesystem root
        candidate = search_dir / CONFIGURATION_FILENAME
        if candidate.is_file():
            return candidate
        search_dir = search_dir.parent

    return None


def read_config(path: Path) -> Config:
    """Read the configuration from the given yaml file.

    Parameters
    ----------
    path : Path
        Path to the YAML configuration file.

    Returns
    -------
    Config
        The resolved configuration.

    Raises
    ------
    automata.exceptions.Error
        If the configuration is invalid or does not match the schema.

    """
    # Read and resolve the YAML file
    yaml_content = path.read_text()
    config_dict = parse_yaml(yaml_content)

    # Resolve the configuration against the schema
    # (include function is automatically provided by resolve)
    try:
        return resolve(config_dict, Config, base_path=path.parent)
    except smartconfig.exceptions.Error as e:
        raise Error(f"Invalid configuration: {e}") from e
