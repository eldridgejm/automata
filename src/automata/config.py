from pathlib import Path
from typing import Any

import smartconfig

from ._extension import Extension
from .exceptions import Error
from .util.resolution import resolve
from .util.yaml import parse_yaml
from .website import WebsiteConfig
from ._extension import extension_from_directory, extension_from_entry_point

CONFIGURATION_FILENAME = "automata.yaml"


class Config(smartconfig.Prototype):
    """Top-level configuration for automata."""

    # a dictionary of variables to be made available globally, including in website
    # pages and configuration files
    vars: dict[str, Any] = {}

    # list of extensions to load. Each entry can be:
    # - a string: entry point name (no slashes) or directory path (with slashes)
    # - a dict with "use" (name/path) and optional "config" keys
    extensions: list[Any] = []

    # configuration for the website
    website: WebsiteConfig


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
    if start_path.is_file():
        search_dir = start_path.parent.resolve()
    else:
        search_dir = start_path.resolve()

    while search_dir != search_dir.parent:
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
    yaml_content = path.read_text()
    config_dict = parse_yaml(yaml_content)

    try:
        return resolve(config_dict, Config, base_path=path.parent)
    except smartconfig.exceptions.Error as e:
        raise Error(f"Invalid configuration: {e}") from e


def load_extensions(config: Config, cwd: Path) -> list[Extension]:
    """Load extensions from the configuration.

    Each entry in ``config.extensions`` can be:

    - A string without slashes: treated as an entry point name.
    - A string with slashes: treated as a directory path (relative to *cwd*).
    - A dict with ``"use"`` (name/path) and optional ``"config"`` keys.

    Parameters
    ----------
    config : Config
        The resolved configuration.
    cwd : Path
        Working directory for resolving relative paths.

    Returns
    -------
    list[Extension]
        The loaded extensions, in order.

    """
    extensions: list[Extension] = []

    for spec in config.extensions:
        if isinstance(spec, str):
            name = spec
            ext_config = None
        elif isinstance(spec, dict):
            name = spec["use"]
            ext_config = spec.get("config")
        else:
            raise Error(f"Invalid extension spec: {spec!r}")

        if "/" in name or "\\" in name:
            ext = extension_from_directory(
                name, cwd / name, config=ext_config
            )
        else:
            ext = extension_from_entry_point(name, config=ext_config)

        extensions.append(ext)

    return extensions
