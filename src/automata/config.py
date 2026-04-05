from pathlib import Path
from typing import Any

import smartconfig

from ._extension import Extension
from .exceptions import Error
from .util.resolution import resolve
from .util.yaml import parse_yaml
from ._extension import extension_from_directory, extension_from_entry_point

CONFIGURATION_FILENAME = "automata.yaml"


class WebsiteConfig(smartconfig.Prototype):
    """Configuration for the website."""

    # theme extension spec: a string name or dict with "use"/"config" keys
    theme: Any

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


class PublishConfig(smartconfig.Prototype):
    """Configuration for publishing/deployment."""

    # name of the publish strategy (e.g., "gh-pages", "scp")
    strategy: str

    # strategy-specific configuration
    config: dict[str, Any] = {}


class Config(smartconfig.Prototype):
    """Top-level configuration for automata."""

    # a dictionary of variables to be made available globally, including in website
    # pages and configuration files
    vars: dict[str, Any] = {}

    # list of extensions to load. Each entry can be:
    # - a string: entry point name (no slashes) or directory path (with slashes)
    # - a dict with "use" (name/path) and optional "config" keys
    extensions: list[Any] = []

    # inline materials definitions. Each key is a collection name, mapping to
    # a dict with "schema" and "publications" keys.
    materials: dict[str, Any] = {}

    # configuration for the website
    website: WebsiteConfig

    # optional publish/deployment configuration
    publish: PublishConfig | None = None


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


def _load_extension_spec(spec: Any, cwd: Path) -> Extension:
    """Load a single extension from a spec (string or dict).

    Parameters
    ----------
    spec : str or dict
        A string (entry point name or directory path) or a dict with
        ``"use"`` and optional ``"config"`` keys.
    cwd : Path
        Working directory for resolving relative paths.

    """
    if isinstance(spec, str):
        name = spec
        ext_config = None
    elif isinstance(spec, dict):
        name = spec["use"]
        ext_config = spec.get("config")
    else:
        raise Error(f"Invalid extension spec: {spec!r}")

    if "/" in name or "\\" in name:
        return extension_from_directory(name, cwd / name, config=ext_config)
    else:
        return extension_from_entry_point(name, config=ext_config)


def load_extensions(config: Config, cwd: Path) -> list[Extension]:
    """Load all extensions from the configuration.

    The theme (if specified) is loaded first, followed by extensions in
    order.  This ensures theme hooks run before extension hooks.

    Parameters
    ----------
    config : Config
        The resolved configuration.
    cwd : Path
        Working directory for resolving relative paths.

    Returns
    -------
    list[Extension]
        The loaded extensions, in order (theme first).

    """
    extensions: list[Extension] = []

    extensions.append(_load_extension_spec(config.website.theme, cwd))

    for spec in config.extensions:
        extensions.append(_load_extension_spec(spec, cwd))

    return extensions
