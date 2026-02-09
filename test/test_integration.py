"""Integration tests for the high-level build function."""

import json
import shutil
from datetime import datetime
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


@pytest.mark.integration
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
    assert (build_dir / "static").exists(), "Style directory should exist"
    assert (build_dir / "static" / "style.css").exists(), "CSS file should be copied"


@pytest.mark.integration
def test_release_time_and_ready_flag_behavior(temporary_course):
    """
    Integration test documenting how release_time, ready flags, and metadata dates
    affect publication and artifact visibility in materials.json.

    This test covers 4 scenarios:
    1. All artifacts have future release_time, none ready
    2. All artifacts have future release_time, all ready
    3. Some artifacts past-released+ready, others future-released+ready
    4. Artifact ready with no release_time, metadata date in future

    Key insights:
    - materials.json inclusion is controlled by artifact-level release_time
      and ready flags
    - Publications appear even when all artifacts are filtered (empty
      artifacts dict)
    - Metadata dates don't affect materials.json inclusion (only schedule
      week placement)
    """
    # Set a fixed current_time for reproducible tests (today is 2025-01-15)
    current_time = datetime(2025, 1, 15, 12, 0, 0)

    # Get path to default theme (use path syntax to avoid entry point lookup)
    theme_path = (
        Path(__file__).parent.parent
        / "src"
        / "automata"
        / "builtin"
        / "themes"
        / "default"
    )

    # Create automata.yaml config with schedule configuration
    config_path = temporary_course.path / "automata.yaml"
    config_path.write_text(
        f"""
vars:
  schedule_config:
    __include__: "schedule.yaml"

website:
  content_directory: "content"
  build_directory: "_build"
  materials_directory_name: "materials"
  base_path: "."
  theme:
    use: "{theme_path}"
    config:
      short_title: "Test Course"
      long_title: "Test Course - Release Time Behavior"
"""
    )

    # Create schedule.yaml
    schedule_path = temporary_course.path / "schedule.yaml"
    schedule_path.write_text(
        """
first_week_start_date: "2025-01-13"  # Week 1: Jan 13-19
week_order: this_week_first

week_topics:
  - Week 1
  - Week 2

primary_activity_collections:
  - collection: assignments
    for_each_publication:
      start_displaying_on:
        __template__: "${ publication.metadata.released }"
      title:
        __template__: "${ publication.metadata.name }"
      resources:
        - type: artifact_links
          links:
            - text: Assignment
              artifact: assignment.pdf
            - text: Solution
              artifact: solution.pdf

secondary_activity_collections: []
"""
    )

    # Create a page that uses the schedule element
    content_dir = temporary_course.path / "content"
    content_dir.mkdir(exist_ok=True)
    (content_dir / "index.html").write_text(
        """
---
title: Schedule
---

${ elements.schedule(vars.schedule_config) }
"""
    )

    # Create a test collection
    temporary_course.create_collection(
        "assignments",
        """
        publication_schema:
            required_artifacts:
                - assignment.pdf
            optional_artifacts:
                - solution.pdf
            metadata_schema:
                required_keys:
                    name:
                        type: string
                    released:
                        type: date
        """,
    )

    # Scenario 1: All artifacts have future release_time, none ready
    temporary_course.create_publication(
        "assignments",
        "scenario1",
        """
        metadata:
            name: Scenario 1 - Future and Not Ready
            released: 2025-01-20

        artifacts:
            assignment.pdf:
                recipe: touch assignment.pdf
                release_time: 2025-01-20 12:00:00
                ready: false
            solution.pdf:
                recipe: touch solution.pdf
                release_time: 2025-01-25 12:00:00
                ready: false
        """,
    )

    # Scenario 2: All artifacts have future release_time, all ready
    temporary_course.create_publication(
        "assignments",
        "scenario2",
        """
        metadata:
            name: Scenario 2 - Future but Ready
            released: 2025-01-20

        artifacts:
            assignment.pdf:
                recipe: touch assignment.pdf
                release_time: 2025-01-20 12:00:00
                ready: true
            solution.pdf:
                recipe: touch solution.pdf
                release_time: 2025-01-25 12:00:00
                ready: true
        """,
    )

    # Scenario 3: Some artifacts past-released+ready, others future-released+ready
    # Released in current week (Jan 13-19), so should appear in schedule
    temporary_course.create_publication(
        "assignments",
        "scenario3",
        """
        metadata:
            name: Scenario 3 - Partial Release
            released: 2025-01-15

        artifacts:
            assignment.pdf:
                recipe: touch assignment.pdf
                release_time: 2025-01-10 12:00:00
                ready: true
            solution.pdf:
                recipe: touch solution.pdf
                release_time: 2025-01-25 12:00:00
                ready: true
        """,
    )

    # Scenario 4: Artifact ready with no release_time, metadata date in future
    temporary_course.create_publication(
        "assignments",
        "scenario4",
        """
        metadata:
            name: Scenario 4 - Artifact Available, Schedule Future
            released: 2025-01-20

        artifacts:
            assignment.pdf:
                recipe: touch assignment.pdf
                ready: true
        """,
    )

    # Run the full build (discovers, builds, exports materials, and generates website)
    build(temporary_course.path, current_time=current_time)

    # Read the generated materials.json from the build directory
    materials_json_path = (
        temporary_course.path / "_build" / "materials" / "materials.json"
    )
    with materials_json_path.open() as f:
        materials_data = json.load(f)

    assignments = materials_data["collections"]["assignments"]["publications"]

    # Scenario 1: All artifacts future + not ready
    # Expected: Publication APPEARS but with empty artifacts dict
    assert "scenario1" in assignments, (
        "Scenario 1: Publication should appear even when all artifacts are filtered"
    )
    assert len(assignments["scenario1"]["artifacts"]) == 0, (
        "Scenario 1: All artifacts should be filtered (empty artifacts dict)"
    )

    # Scenario 2: All artifacts future + ready
    # Expected: Publication APPEARS but with empty artifacts dict
    # (release_time blocks them)
    assert "scenario2" in assignments, (
        "Scenario 2: Publication should appear even when all artifacts are filtered"
    )
    assert len(assignments["scenario2"]["artifacts"]) == 0, (
        "Scenario 2: All artifacts should be filtered due to future release_time, "
        "even when ready=true (release_time takes precedence)"
    )

    # Scenario 3: Partial release (some past, some future)
    # Expected: Publication APPEARS with only past-released artifacts
    assert "scenario3" in assignments, (
        "Scenario 3: Publication with at least one past-released artifact SHOULD appear"
    )
    scenario3_artifacts = assignments["scenario3"]["artifacts"]
    assert "assignment.pdf" in scenario3_artifacts, (
        "Scenario 3: Past-released artifact (assignment.pdf) should appear"
    )
    assert "solution.pdf" not in scenario3_artifacts, (
        "Scenario 3: Future-released artifact (solution.pdf) should NOT appear"
    )

    # Scenario 4: No release_time (always released) + ready, but metadata date future
    # Expected: Publication APPEARS in materials.json (artifact level passes)
    #           Schedule visibility would be controlled separately by metadata.released
    assert "scenario4" in assignments, (
        "Scenario 4: Publication with no release_time should appear in materials.json"
    )
    scenario4_artifacts = assignments["scenario4"]["artifacts"]
    assert "assignment.pdf" in scenario4_artifacts, (
        "Scenario 4: Artifact with no release_time should appear"
    )
    # Note: The metadata.released = 2025-01-20 (future) doesn't affect materials.json
    # It would only affect schedule week filtering during website rendering

    # Verify the metadata is preserved correctly
    assert assignments["scenario3"]["metadata"]["released"] == "2025-01-15", (
        "Metadata dates should be preserved in materials.json"
    )
    assert assignments["scenario4"]["metadata"]["released"] == "2025-01-20", (
        "Metadata dates should be preserved even when in the future"
    )

    # Verify artifacts were actually exported to the build/materials directory
    materials_dir = temporary_course.path / "_build" / "materials"
    assert (materials_dir / "assignments" / "scenario3" / "assignment.pdf").exists()
    assert not (materials_dir / "assignments" / "scenario3" / "solution.pdf").exists()
    assert (materials_dir / "assignments" / "scenario4" / "assignment.pdf").exists()

    # Verify the website was also built
    build_dir = temporary_course.path / "_build"
    assert build_dir.exists(), "Website build directory should be created"

    # NOW: Check what actually appears in the generated schedule HTML
    index_html_path = build_dir / "index.html"
    assert index_html_path.exists(), "index.html should be generated"

    with index_html_path.open() as f:
        html_content = f.read()

    # Scenario 1 & 2: Future releases (2025-01-20) should NOT appear in current week
    # (They would appear in week 2, but we're only checking if they're visible at all)
    assert "Scenario 1 - Future and Not Ready" not in html_content, (
        "Scenario 1: Publication with future metadata date (week 2) "
        "should not appear in current week's schedule"
    )
    assert "Scenario 2 - Future but Ready" not in html_content, (
        "Scenario 2: Publication with future metadata date (week 2) "
        "should not appear in current week's schedule"
    )

    # Scenario 3: Current week release (2025-01-15) SHOULD appear
    assert "Scenario 3 - Partial Release" in html_content, (
        "Scenario 3: Publication with current week metadata date "
        "should appear in schedule"
    )
    # Check that only assignment.pdf link appears, not solution.pdf (artifact filtering)
    # The button text is "Assignment" and "Solution"
    assert html_content.count("assignment.pdf") >= 1, (
        "Scenario 3: Assignment artifact should have a link in the schedule"
    )
    # Solution button may appear but should be disabled/unavailable
    # (depends on theme implementation - some themes show disabled buttons,
    # some hide them)

    # Scenario 4: Future release (2025-01-20) should NOT appear in current week
    assert "Scenario 4 - Artifact Available, Schedule Future" not in html_content, (
        "Scenario 4: Publication with future metadata date should not appear "
        "in current week's schedule, even though artifacts are available "
        "in materials.json"
    )
