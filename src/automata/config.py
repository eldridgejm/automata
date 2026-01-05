from pathlib import Path
from typing import Any

import smartconfig

from .exceptions import Error
from .util.resolution import resolve
from .util.yaml import parse_yaml
from .website import WebsiteConfig


class Config(smartconfig.Prototype):
    """Top-level configuration for automata."""

    # a dictionary of variables to be made available globally, including in website
    # pages and configuration files
    vars: dict[str, Any] = {}

    # configuration for the website
    website: WebsiteConfig


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
