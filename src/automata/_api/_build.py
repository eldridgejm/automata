"""High-level build function for building materials and website."""

import datetime
from pathlib import Path

from .. import materials
from ..hooks import WebsiteContent, execute_hooks, execute_pre_generate_hooks
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

    config, extension = load(path)

    # Discover and build materials
    unbuilt_universe = materials.discover(path, vars=config.vars, hooks=extension.hooks)
    built_universe = materials.build(
        unbuilt_universe, current_time=current_time, hooks=extension.hooks
    )

    # Export materials directly to the build directory
    build_dir = path / config.website.build_directory
    materials_output_dir = build_dir / config.website.materials_directory_name

    exported_universe = materials.export(
        built_universe,
        outdir=build_dir,
        prefix=config.website.materials_directory_name,
        hooks=extension.hooks,
    )

    # Write materials.json
    materials_json = materials_output_dir / "materials.json"
    materials_json.parent.mkdir(parents=True, exist_ok=True)
    materials_json.write_text(materials.serialize(exported_universe))

    # Filter out files in the materials directory (they're handled separately)
    materials_dir_name = config.website.materials_directory_name
    pages_from_extension = {
        k: v
        for k, v in extension.pages.items()
        if not k.startswith(materials_dir_name + "/") and k != materials_dir_name
    }

    # Create initial website content from extension
    initial_content = WebsiteContent(
        content=pages_from_extension,
        assets=dict(extension.assets),
        static_files=dict(extension.static_files),
    )

    # Execute pre_generate_website hooks as a pipeline
    # Each hook can transform the content, assets, and static_files
    final_content = execute_pre_generate_hooks(
        extension.hooks,
        initial_content,
        materials=exported_universe,
        website_config=config.website,
        build_directory=build_dir,
        vars=config.vars,
        current_time=current_time,
    )

    # Generate website (materials are already in place, so no copy needed)
    generate(
        materials_output_dir,
        extension.templates,
        build_directory=build_dir,
        base_path=config.website.base_path,
        materials_directory_name=config.website.materials_directory_name,
        elements=extension.elements,
        pages=final_content.content,
        assets=final_content.assets,
        static_files=final_content.static_files,
        vars=config.vars,
        cwd=path,
        current_time=current_time,
    )

    # Execute post_generate_website hooks
    execute_hooks(
        extension.hooks,
        "post_generate_website",
        materials=exported_universe,
        website_config=config.website,
        build_directory=build_dir,
        vars=config.vars,
        current_time=current_time,
    )
