"""High-level build function for building materials and website."""

import datetime
from pathlib import Path

from . import materials
from ._extension import apply_extension
from .config import load_extensions, read_config
from .hooks import Hooks
from .website import generate

CONFIGURATION_FILENAME = "automata.yaml"


def build(
    path: Path | None = None, current_time: datetime.datetime | None = None
) -> None:
    """Build the automata project located at the given path.

    This function orchestrates the build process for the automata project,
    including reading the configuration, loading extensions, building
    materials, and generating the website.

    Parameters
    ----------
    path : Path | None
        The path to the automata project directory. If None, uses the current
        working directory.
    current_time : datetime.datetime | None
        The current time to use for release time checks and scheduling.
        If None, uses the system time.

    """
    if path is None:
        path = Path.cwd()

    if current_time is None:
        current_time = datetime.datetime.now()

    config = read_config(path / CONFIGURATION_FILENAME)

    # Load extensions and register their hooks
    hooks = Hooks()
    for ext in load_extensions(config, cwd=path):
        apply_extension(ext, hooks)

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

    # Generate website (extensions already registered on hooks)
    generate(
        config.website,
        materials_output_dir,
        config.vars,
        cwd=path,
        current_time=current_time,
        hooks=hooks,
    )
