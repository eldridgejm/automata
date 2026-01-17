"""Tests for automata.config module."""

from pathlib import Path
from textwrap import dedent

import pytest

from automata import exceptions
from automata.config import Config, read_config


def test_read_config_reads_valid_config(tmp_path: Path) -> None:
    """Test that read_config successfully reads a valid config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            vars:
              course_name: "DSC 101"
              semester: "Fall 2025"

            website:
              content_directory: "./content"
              build_directory: "./build"
              theme:
                use: "default"
                config:
                  short_title: "DSC 101"
                  long_title: "Introduction to Data Science"
            """
        )
    )

    config = read_config(config_file)

    assert isinstance(config, Config)
    assert config.vars["course_name"] == "DSC 101"
    assert config.vars["semester"] == "Fall 2025"
    assert config.website.content_directory == "./content"
    assert config.website.build_directory == "./build"
    assert config.website.theme.use == "default"
    assert config.website.theme.config["short_title"] == "DSC 101"


def test_read_config_applies_defaults(tmp_path: Path) -> None:
    """Test that read_config applies default values for optional fields."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            website:
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    # vars should default to {}
    assert config.vars == {}

    # website theme should have defaults
    assert config.website.theme.use == "default"
    assert config.website.theme.config == {}

    # Other website defaults
    assert config.website.materials_directory_name == "materials"
    assert config.website.no_render_suffix == ".no_render"
    assert config.website.base_path == "/"


def test_read_config_raises_on_missing_file(tmp_path: Path) -> None:
    """Test that read_config raises FileNotFoundError for missing files."""
    config_file = tmp_path / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError):
        read_config(config_file)


def test_read_config_raises_on_invalid_yaml(tmp_path: Path) -> None:
    """Test that read_config raises an error for invalid YAML."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("invalid: yaml: content: [")

    with pytest.raises(Exception):  # YAML parsing error
        read_config(config_file)


def test_read_config_raises_on_missing_required_fields(tmp_path: Path) -> None:
    """Test that read_config raises ResolutionError for missing required fields."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            vars:
              test: "value"
            # Missing required 'website' field
            """
        )
    )

    with pytest.raises(exceptions.Error):
        read_config(config_file)


def test_read_config_validates_nested_structure(tmp_path: Path) -> None:
    """Test that read_config validates nested configuration structure."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            website:
              content_directory: "./content"
              # Missing required build_directory
            """
        )
    )

    with pytest.raises(exceptions.Error):
        read_config(config_file)


def test_read_config_with_empty_vars(tmp_path: Path) -> None:
    """Test that read_config handles empty vars dict."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            vars: {}

            website:
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert config.vars == {}


def test_read_config_with_complex_theme_config(tmp_path: Path) -> None:
    """Test that read_config handles complex theme configurations."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            website:
              content_directory: "./content"
              build_directory: "./build"
              theme:
                use: "./custom-theme"
                config:
                  short_title: "Course"
                  long_title: "Full Course Title"
                  navigation:
                    - text: "Home"
                      url: "/index.html"
                    - text: "Syllabus"
                      url: "/syllabus.html"
            """
        )
    )

    config = read_config(config_file)

    assert config.website.theme.use == "./custom-theme"
    assert len(config.website.theme.config["navigation"]) == 2
    assert config.website.theme.config["navigation"][0]["text"] == "Home"


def test_read_config_performs_variable_interpolation(tmp_path: Path) -> None:
    """Test that read_config performs variable interpolation from vars."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            vars:
              course_name: "DSC 101"
              semester: "Fall 2025"

            website:
              content_directory: "./content"
              build_directory: "./build"
              theme:
                use: "default"
                config:
                  short_title: ${ vars.course_name }
                  long_title: "Introduction to Data Science - ${ vars.semester }"
            """
        )
    )

    config = read_config(config_file)

    # Check that interpolation worked
    assert config.vars["course_name"] == "DSC 101"
    assert config.vars["semester"] == "Fall 2025"
    assert config.website.theme.config["short_title"] == "DSC 101"
    assert (
        config.website.theme.config["long_title"]
        == "Introduction to Data Science - Fall 2025"
    )


def test_read_config_with_include(tmp_path: Path) -> None:
    """Test that read_config can include external files."""
    # Create the included file
    vars_file = tmp_path / "vars.yaml"
    vars_file.write_text(
        dedent(
            """
            course_name: "DSC 101"
            semester: "Fall 2025"
            """
        )
    )

    # Create the main config file
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            vars:
              __include__: vars.yaml

            website:
              content_directory: "./content"
              build_directory: "./build"
              theme:
                use: "default"
                config:
                  short_title: ${ vars.course_name }
            """
        )
    )

    config = read_config(config_file)

    assert config.vars["course_name"] == "DSC 101"
    assert config.vars["semester"] == "Fall 2025"
    assert config.website.theme.config["short_title"] == "DSC 101"
