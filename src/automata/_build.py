"""High-level build function for building materials and website."""

from pathlib import Path

from . import materials
from .config import read_config
from .website import generate

CONFIGURATION_FILENAME = "automata.yaml"


def build(path: Path | None = None) -> None:
    """Build the automata project located at the given path.

    This function orchestrates the build process for the automata project,
    including reading the configuration, building materials, and generating the
    website.

    Parameters
    ----------
    path : Path | None
        The path to the automata project directory. If None, uses the current
        working directory.

    """
    if path is None:
        path = Path.cwd()

    config = read_config(path / CONFIGURATION_FILENAME)

    # Discover, build, and export materials
    unbuilt_universe = materials.discover(path)
    built_universe = materials.build(unbuilt_universe)

    # Export materials to content directory (use absolute path)
    content_dir = (path / config.website.content_directory).resolve()
    materials_output_dir = content_dir / config.website.materials_directory_name
    exported_universe = materials.export(built_universe, materials_output_dir)

    # Write materials.json
    materials_json = materials_output_dir / "materials.json"
    materials_json.parent.mkdir(parents=True, exist_ok=True)
    materials_json.write_text(materials.serialize(exported_universe))

    # Generate website (pass cwd so relative paths are resolved correctly)
    generate(config.website, config.vars, cwd=path)
