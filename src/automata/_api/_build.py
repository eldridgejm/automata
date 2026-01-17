"""High-level build function for building materials and website."""

import datetime
from pathlib import Path
from typing import Any

from .. import materials
from .._hooks import execute_hooks
from ..website import generate
from ._load import load


def build(
    path: Path | None = None, current_time: datetime.datetime | None = None
) -> None:
    """Build the automata project located at the given path.

    This function orchestrates the build process for the automata project,
    including reading the configuration, building materials, and generating the
    website.

    Parameters
    ----------
    path : Path | None
        The path to the automata project directory. If None, uses the current
        working directory.
    current_time : datetime.datetime | None
        The current time to use for release time checks and scheduling.
        If None, uses the system time. This can be used to simulate building
        at a different time for testing purposes.

    """
    if path is None:
        path = Path.cwd()

    if current_time is None:
        current_time = datetime.datetime.now()

    config, plugin = load(path)

    # Discover and build materials
    unbuilt_universe = materials.discover(path, vars=config.vars)
    built_universe = materials.build(unbuilt_universe, current_time=current_time)

    # Export materials directly to the build directory
    build_dir = path / config.website.build_directory
    materials_output_dir = build_dir / config.website.materials_directory_name

    exported_universe = materials.export(
        built_universe,
        outdir=build_dir,
        prefix=config.website.materials_directory_name,
    )

    # Write materials.json
    materials_json = materials_output_dir / "materials.json"
    materials_json.parent.mkdir(parents=True, exist_ok=True)
    materials_json.write_text(materials.serialize(exported_universe))

    # Create hook context
    hook_context = _create_hook_context(
        config, exported_universe, current_time, build_dir
    )

    # Execute pre_generate hooks
    extra_pages: dict[str, str] = {}
    extra_assets: dict[str, str | bytes] = {}

    pre_generate_results = execute_hooks(plugin.hooks, "pre_generate", hook_context)
    for result in pre_generate_results:
        if result is not None:
            extra_pages.update(result.get("pages", {}))
            extra_assets.update(result.get("assets", {}))

    # Generate website (materials are already in place, so no copy needed)
    generate(
        config.website,
        materials_output_dir,
        templates=plugin.templates,
        elements=plugin.elements,
        extra_assets={**plugin.static_files, **extra_assets},
        extra_pages=extra_pages if extra_pages else None,
        vars=config.vars,
        cwd=path,
        current_time=current_time,
    )

    # Execute post_generate hooks
    execute_hooks(plugin.hooks, "post_generate", hook_context)


def _create_hook_context(
    config: "Config",
    exported_universe: materials.Universe,
    current_time: datetime.datetime,
    build_directory: Path,
) -> dict[str, Any]:
    """Create a JSON-serializable context dict for hooks.

    Parameters
    ----------
    config : Config
        The automata configuration.
    exported_universe : Universe
        The exported materials universe.
    current_time : datetime.datetime
        Current time for the build.
    build_directory : Path
        Path to the build output directory.

    Returns
    -------
    dict[str, Any]
        A JSON-serializable context dictionary containing config data,
        materials, current time, and variables.

    """
    return {
        "config": {
            "content_directory": str(config.website.content_directory),
            "build_directory": str(config.website.build_directory),
            "materials_directory_name": config.website.materials_directory_name,
            "base_path": config.website.base_path,
        },
        "materials": materials.serialize(exported_universe),
        "current_time": current_time.isoformat(),
        "vars": config.vars,
        "build_directory": str(build_directory),
    }


# Import Config for type hints
from .._config import Config  # noqa: E402
