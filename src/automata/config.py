from pathlib import Path
from typing import Any

import smartconfig
import yaml

from .exceptions import Error
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
    # Read the YAML file
    with path.open("r") as f:
        raw_config = yaml.safe_load(f)

    # Resolve the configuration against the schema
    try:
        return smartconfig.resolve(raw_config, Config)
    except smartconfig.exceptions.Error as e:
        raise Error(f"Invalid configuration: {e}") from e
