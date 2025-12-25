#!/usr/bin/env python
"""Build script for the example course.

This script:
1. Discovers all materials (homeworks, lectures) from the file system
2. Builds all artifacts by executing their recipes
3. Exports materials to the website directory
4. Generates the static website

Usage:
    python build.py
"""

import pathlib
import sys

import yaml

import automata.materials
import automata.website


def load_config(config_path: pathlib.Path) -> dict:
    """Load and resolve configuration from YAML file."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Simple variable interpolation for vars
    vars_dict = config.get("vars", {})

    def interpolate(obj):
        """Recursively interpolate variables in strings."""
        if isinstance(obj, str):
            # Simple ${vars.key} interpolation
            result = obj
            for key, value in vars_dict.items():
                result = result.replace(f"${{vars.{key}}}", str(value))
                result = result.replace(f"$( vars.{key} )", str(value))
            return result
        elif isinstance(obj, dict):
            return {k: interpolate(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [interpolate(item) for item in obj]
        else:
            return obj

    return interpolate(config)


def main():
    """Main build function."""
    # Define paths
    root_dir = pathlib.Path(__file__).parent
    materials_root = root_dir
    config_path = root_dir / "automata.yaml"

    # Load configuration
    if config_path.exists():
        full_config = load_config(config_path)
        vars_dict = full_config.get("vars", {})
        website_config = full_config.get("website", {})
        elements_config = full_config.get("website", {}).get("elements", {})
    else:
        vars_dict = {}
        website_config = {}
        elements_config = {}

    website_content_dir = root_dir / "website"
    build_dir = root_dir / "_build"
    materials_export_dir = website_content_dir / "materials"

    print("=" * 80)
    print("Building Example Course")
    print("=" * 80)

    # Step 1: Discover materials
    print("\n[1/4] Discovering materials...")
    print(f"  Root directory: {materials_root}")

    universe = automata.materials.discover(
        root_directory=materials_root,
        skip_directories=["_build", "website", ".git"],
    )

    # Count discovered items
    total_collections = len(universe.collections)
    total_publications = sum(
        len(col.publications) for col in universe.collections.values()
    )
    total_artifacts = sum(
        len(pub.artifacts)
        for col in universe.collections.values()
        for pub in col.publications.values()
    )

    print(f"  ✓ Found {total_collections} collections")
    print(f"  ✓ Found {total_publications} publications")
    print(f"  ✓ Found {total_artifacts} artifacts")

    # Step 2: Build materials
    print("\n[2/4] Building materials...")
    print("  Executing artifact recipes...")

    built = automata.materials.build(
        universe,
        ignore_release_time=False,
        ignore_ready=False,
        verbose=False,
    )

    # Count built items
    built_artifacts = sum(
        len(pub.artifacts)
        for col in built.collections.values()
        for pub in col.publications.values()
    )

    print(f"  ✓ Built {built_artifacts} artifacts")

    # Step 3: Export materials
    print("\n[3/4] Exporting materials...")
    print(f"  Export directory: {materials_export_dir}")

    # Create materials directory if it doesn't exist
    materials_export_dir.mkdir(parents=True, exist_ok=True)

    exported = automata.materials.export(
        built,
        outdir=materials_export_dir,
    )

    print(f"  ✓ Exported {built_artifacts} artifacts")

    # Write materials.json for website
    materials_json = automata.materials.serialize(exported)
    materials_json_path = materials_export_dir / "materials.json"
    materials_json_path.write_text(materials_json)
    print(f"  ✓ Wrote {materials_json_path}")

    # Step 4: Generate website
    print("\n[4/4] Generating website...")
    print(f"  Content directory: {website_content_dir}")
    print(f"  Build directory: {build_dir}")

    # Create build directory
    build_dir.mkdir(parents=True, exist_ok=True)

    # Create config with vars and element configs as additional attributes
    config = automata.website.Config(
        content_directory=website_content_dir,
        build_directory=build_dir,
    )

    # Add vars and element configs as dynamic attributes
    # Note: These will be available in templates via context.vars and context.config
    object.__setattr__(config, "vars", vars_dict)
    object.__setattr__(config, "schedule", elements_config.get("schedule", {}))

    automata.website.generate(config)

    print(f"  ✓ Generated website")

    # Summary
    print("\n" + "=" * 80)
    print("Build Complete!")
    print("=" * 80)
    print(f"\nWebsite available at: {build_dir}/index.html")
    print(f"Materials available at: {materials_export_dir}")
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ Build failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
