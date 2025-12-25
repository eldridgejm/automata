#!/usr/bin/env python
"""Build the example course website.

This script builds the example course website from the materials in this directory.

Usage:
    python build.py
"""

import pathlib
import sys

import automata.materials
import automata.website


def main():
    """Build the example website."""
    root_dir = pathlib.Path(__file__).parent

    print("Building Example Course Website")
    print("=" * 60)

    # Step 1: Build materials
    print("\n[1/2] Building materials...")

    universe = automata.materials.discover(
        root_directory=root_dir,
        skip_directories=["_build", "website"],
    )

    built = automata.materials.build(universe, ignore_release_time=True)

    materials_dir = root_dir / "website" / "materials"
    materials_dir.mkdir(parents=True, exist_ok=True)

    exported = automata.materials.export(built, outdir=materials_dir)

    # Write materials.json
    materials_json = automata.materials.serialize(exported)
    (materials_dir / "materials.json").write_text(materials_json)

    print(f"  ✓ Built and exported materials to {materials_dir}")

    # Step 2: Generate website
    print("\n[2/2] Generating website...")

    build_dir = root_dir / "_build"

    config = automata.website.Config(
        content_directory=root_dir / "website",
        build_directory=build_dir,
    )

    automata.website.generate(config)

    print(f"  ✓ Generated website to {build_dir}")

    # Done
    print("\n" + "=" * 60)
    print("Website built successfully!")
    print(f"\nOpen {build_dir}/index.html in your browser")
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
