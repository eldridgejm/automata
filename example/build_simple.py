#!/usr/bin/env python
"""Simple build script for the example course.

This script demonstrates the core automata workflow:
1. Discovers all materials (homeworks, lectures) from the file system
2. Builds all artifacts by executing their recipes
3. Exports materials to JSON for the website

Note: Full website generation with the schedule element requires additional
configuration handling. This script focuses on the materials pipeline.

Usage:
    python build_simple.py
"""

import json
import pathlib
import sys

import automata.materials


def main():
    """Main build function."""
    # Define paths
    root_dir = pathlib.Path(__file__).parent
    materials_root = root_dir
    materials_export_dir = root_dir / "website" / "materials"

    print("=" * 80)
    print("Building Example Course Materials")
    print("=" * 80)

    # Step 1: Discover materials
    print("\n[1/3] Discovering materials...")
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
    print(f"\n  Collections:")
    for coll_name, collection in sorted(universe.collections.items()):
        print(f"    - {coll_name}: {len(collection.publications)} publications")

    # Step 2: Build materials
    print("\n[2/3] Building materials...")
    print("  Executing artifact recipes...")

    built = automata.materials.build(
        universe,
        ignore_release_time=True,  # Build all regardless of release time
        ignore_ready=True,  # Build all regardless of ready flag
        verbose=False,
    )

    # Count built items
    built_count = 0
    for col in built.collections.values():
        for pub in col.publications.values():
            for artifact in pub.artifacts.values():
                if artifact.returncode == 0:
                    built_count += 1

    print(f"  ✓ Successfully built {built_count} artifacts")

    # Step 3: Export materials
    print("\n[3/3] Exporting materials...")
    print(f"  Export directory: {materials_export_dir}")

    # Create materials directory if it doesn't exist
    materials_export_dir.mkdir(parents=True, exist_ok=True)

    exported = automata.materials.export(
        built,
        outdir=materials_export_dir,
    )

    exported_artifacts = sum(
        len(pub.artifacts)
        for col in exported.collections.values()
        for pub in col.publications.values()
    )

    print(f"  ✓ Exported {exported_artifacts} artifacts")

    # Write materials.json for website
    materials_json = automata.materials.serialize(exported)
    materials_json_path = materials_export_dir / "materials.json"
    materials_json_path.write_text(materials_json)
    print(f"  ✓ Wrote {materials_json_path}")

    # Summary
    print("\n" + "=" * 80)
    print("Build Complete!")
    print("=" * 80)
    print(f"\nMaterials available at: {materials_export_dir}")
    print(f"\nGenerated files:")
    print(f"  - materials.json: {materials_json_path}")
    for coll_name in sorted(exported.collections.keys()):
        coll_dir = materials_export_dir / coll_name
        if coll_dir.exists():
            file_count = len(list(coll_dir.rglob("*.*")))
            print(f"  - {coll_name}/: {file_count} files")
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
