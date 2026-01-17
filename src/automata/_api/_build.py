"""High-level build function for building materials and website."""

import datetime
from pathlib import Path

from .. import materials
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

    # Generate website (materials are already in place, so no copy needed)
    generate(
        config.website,
        materials_output_dir,
        templates=plugin.templates,
        elements=plugin.elements,
        extra_assets=plugin.static_files,
        vars=config.vars,
        cwd=path,
        current_time=current_time,
    )
