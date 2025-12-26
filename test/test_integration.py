"""Integration tests for the high-level build function."""

import shutil
from pathlib import Path

import pytest

from automata._build import build


@pytest.fixture
def example_project(tmp_path):
    """Copy the example project to a temporary directory."""
    example_dir = Path(__file__).parent.parent / "example"
    project_dir = tmp_path / "project"

    # Copy the entire example directory to temp
    shutil.copytree(example_dir, project_dir)

    # Clean the build directory if it exists
    build_dir = project_dir / "_build"
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # Clean the materials directory if it exists
    materials_dir = project_dir / "website" / "materials"
    if materials_dir.exists():
        shutil.rmtree(materials_dir)

    return project_dir


def test_build_end_to_end(example_project):
    """Test that build() successfully builds the example project end-to-end."""
    # Run the build
    build(example_project)

    materials_dir = example_project / "website" / "content" / "materials"

    # Verify materials were discovered, built, and exported
    assert materials_dir.exists(), "Materials directory should be created"
    assert (materials_dir / "materials.json").exists(), "materials.json should exist"

    # Verify materials collections were exported
    assert (materials_dir / "homeworks").exists(), "Homeworks collection should exist"
    assert (materials_dir / "lectures").exists(), "Lectures collection should exist"

    # Verify website was generated
    build_dir = example_project / "_build"
    assert build_dir.exists(), "Build directory should be created"
    assert (build_dir / "index.html").exists(), "index.html should be generated"

    # Verify theme static files were copied
    assert (build_dir / "style").exists(), "Style directory should exist"
    assert (build_dir / "style" / "style.css").exists(), "CSS file should be copied"
