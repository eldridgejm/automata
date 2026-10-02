from pathlib import Path
from typing import Any

import smartconfig

from .exceptions import Error
from .extensions import (
    EXTENSIONS_GROUP,
    THEMES_GROUP,
    Extension,
    extension_from_directory,
    extension_from_entry_point,
)
from .extensions._apply import all_extensions, check_theme
from .util.resolution import resolve
from .util.yaml import parse_yaml

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

    # whether to empty the build directory before each build, so that it holds
    # only what the current build produces (top-level dot-entries such as .git
    # are kept)
    clean_build_directory: bool = True

    # suffix indicating that a file should not be rendered. If None, all files
    # will be rendered.
    no_render_suffix: str | None = ".no_render"

    # base path for the website (e.g., "/" or "/course/")
    base_path: str = "/"

    # element configurations, keyed by element name. An element called in a page
    # without a configuration (e.g., ``${ elements.schedule() }``) uses the
    # configuration given here.
    elements: dict[str, Any] = {}


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

    # publish/deployment configurations, keyed by name
    publish: dict[str, Any] = {}


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
    config_dict = parse_yaml(yaml_content, source=path)
    if config_dict is None:
        raise Error(f"{path} is empty.")

    try:
        return resolve(config_dict, Config, base_path=path.parent)
    except smartconfig.exceptions.Error as e:
        raise Error(f"Invalid configuration: {e}") from e


def _load_extension_spec(spec: Any, cwd: Path, group: str, where: str) -> Extension:
    """Load a single extension from a spec (string or dict).

    Parameters
    ----------
    spec : str or dict
        A string (entry point name or directory path) or a dict with
        ``"use"`` and optional ``"config"`` keys.
    cwd : Path
        Working directory for resolving relative paths.
    group : str
        The entry point group in which to look up names without slashes.

    """
    if isinstance(spec, str):
        name = spec
        ext_config = None
    elif isinstance(spec, dict):
        for key in spec:
            if key not in ("use", "config"):
                raise Error(
                    f'{where} has unknown key "{key}" (expected "use" and "config").'
                )
        if "use" not in spec:
            raise Error(
                f'{where} must have a "use" key, naming the extension or giving '
                f"its path."
            )
        name = spec["use"]
        if not isinstance(name, str):
            raise Error(f'"use" in {where} must be a string, not {name!r}.')
        ext_config = spec.get("config")
    else:
        raise Error(
            f"Invalid extension spec in {where}: {spec!r}. Give a name, a path, or "
            f'a mapping with "use" (and optionally "config").'
        )

    if "/" in name or "\\" in name:
        # directory extensions are named after the directory itself
        return extension_from_directory(
            Path(name).name,
            cwd / name,
            config=ext_config,
            require_templates=False,
            project_directory=cwd,
            allow_python=True,
        )
    else:
        return extension_from_entry_point(name, config=ext_config, group=group)


def load_extensions(config: Config, cwd: Path) -> tuple[Extension, list[Extension]]:
    """Load the theme and extensions from the configuration.

    The theme is looked up in the ``automata.themes`` entry point group, and
    extensions in ``automata.extensions``. Paths containing a slash are loaded
    from directories, and named after the directory.

    Parameters
    ----------
    config : Config
        The resolved configuration.
    cwd : Path
        Working directory for resolving relative paths.

    Returns
    -------
    tuple[Extension, list[Extension]]
        The theme, and the other extensions in the order they are listed.

    Raises
    ------
    automata.exceptions.Error
        If an extension cannot be loaded, the theme does not provide a
        ``page.html`` template, or two different extensions share a name.

    """
    theme = _load_extension_spec(
        config.website.theme, cwd, THEMES_GROUP, "website.theme"
    )
    check_theme(theme)

    extensions = [
        _load_extension_spec(spec, cwd, EXTENSIONS_GROUP, f"extensions.{i}")
        for i, spec in enumerate(config.extensions)
    ]

    # raises if two different extensions share a name
    all_extensions([theme, *extensions])

    return theme, extensions
