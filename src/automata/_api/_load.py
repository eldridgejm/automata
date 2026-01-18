"""High-level function for loading configuration and extensions."""

from pathlib import Path
from typing import cast

from .._config import Config, read_config
from ..extensions import Extension, merge_extensions
from ..hooks import HOOK_POINTS, Hooks, ScriptableHookMixin
from ..loaders import load_hooks_from_directory, load_website_components_from_directory

CONFIGURATION_FILENAME = "automata.yaml"


def load(path: Path | None = None) -> tuple[Config, Extension]:
    """Load the configuration and extensions from an automata project.

    This function reads the automata.yaml configuration file, loads the
    theme extension specified in the configuration, loads website components
    from the site directory, loads any configured plugins, and merges in any
    hooks defined in the configuration file.

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
        - The merged extension (theme + site components + plugins + config hooks)

    """
    if path is None:
        path = Path.cwd()

    config = read_config(path / CONFIGURATION_FILENAME)

    # Load the theme as an extension
    theme_extension = Extension.from_spec(
        config.website.theme.use, group="automata.website.themes"
    )

    # Load website components from the site directory (parent of content_directory)
    # The site directory is expected to have: content/, assets/, static/, templates/
    site_dir = path / config.website.content_directory
    site_extension = _load_site_extension(site_dir.parent)

    # Load plugins from configured paths
    plugin_extensions = _load_plugins(config.plugins, cwd=path)

    # Convert config hooks to a synthetic extension
    config_hooks_extension = _config_hooks_to_extension(config, cwd=path)

    # Merge extensions: theme < site < plugins < config hooks (later = higher priority)
    merged_extension = merge_extensions(
        [
            theme_extension,
            site_extension,
            *plugin_extensions,
            config_hooks_extension,
        ]
    )

    return config, merged_extension


def _load_site_extension(site_dir: Path) -> Extension:
    """Load website components from a site directory as an Extension.

    The site directory is expected to have subdirectories for content, assets,
    static files, templates, and elements (all optional).

    Content files are split based on extension:
    - .md and .html files go into pages (to be rendered)
    - All other files go into static_files (copied as-is)

    Assets are merged into static_files.

    Parameters
    ----------
    site_dir : Path
        The site directory containing website components.

    Returns
    -------
    Extension
        An extension containing the loaded website components.

    """
    components = load_website_components_from_directory(site_dir)

    # Split content files: .md and .html go to pages, others to static_files
    pages = {}
    content_static = {}
    for path, content in components.pages.items():
        if path.endswith(".md") or path.endswith(".html"):
            pages[path] = content
        else:
            content_static[path] = content

    # Merge: assets + content static files + explicit static files
    # Later entries override earlier ones
    merged_static = {**components.assets, **content_static, **components.static}

    return Extension(
        templates=components.templates,
        static_files=merged_static,
        elements=components.elements,
        pages=pages,
    )


def _load_plugins(plugin_paths: list[str], cwd: Path) -> list[Extension]:
    """Load plugins from configured paths.

    Each plugin path should point to a directory containing a hooks/
    subdirectory with an __init__.py that exports a ``hooks`` dictionary.

    Parameters
    ----------
    plugin_paths : list[str]
        List of paths to plugin directories (relative to cwd).
    cwd : Path
        The base directory for resolving relative paths.

    Returns
    -------
    list[Extension]
        List of Extension objects, one for each plugin.

    """
    extensions = []
    for plugin_path in plugin_paths:
        plugin_dir = cwd / plugin_path
        hooks = load_hooks_from_directory(plugin_dir / "hooks")
        extensions.append(Extension(hooks=cast(Hooks, hooks)))
    return extensions


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
