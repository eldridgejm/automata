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
              theme:
                use: "default"
                config:
                  short_title: "DSC 101"
                  long_title: "Introduction to Data Science"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert isinstance(config, Config)
    assert config.vars["course_name"] == "DSC 101"
    assert config.vars["semester"] == "Fall 2025"
    assert config.website.content_directory == "./content"
    assert config.website.build_directory == "./build"
    assert config.website.theme["use"] == "default"
    assert config.website.theme["config"]["short_title"] == "DSC 101"


def test_read_config_applies_defaults(tmp_path: Path) -> None:
    """Test that read_config applies default values for optional fields."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            website:
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    # vars should default to {}
    assert config.vars == {}

    # extensions should default to []
    assert config.extensions == []

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
              theme: "default"
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
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert config.vars == {}


def test_read_config_with_extensions_list(tmp_path: Path) -> None:
    """Test that read_config handles extensions as a list."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            extensions:
              - "default"
              - "./custom-theme"
              - use: "my-ext"
                config:
                  key: "value"

            website:
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert len(config.extensions) == 3
    assert config.extensions[0] == "default"
    assert config.extensions[1] == "./custom-theme"
    assert config.extensions[2]["use"] == "my-ext"
    assert config.extensions[2]["config"]["key"] == "value"


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
              theme:
                use: "default"
                config:
                  short_title: ${ vars.course_name }
                  long_title: "Introduction to Data Science - ${ vars.semester }"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert config.vars["course_name"] == "DSC 101"
    assert config.vars["semester"] == "Fall 2025"
    assert config.website.theme["config"]["short_title"] == "DSC 101"
    assert (
        config.website.theme["config"]["long_title"]
        == "Introduction to Data Science - Fall 2025"
    )


def test_read_config_with_include(tmp_path: Path) -> None:
    """Test that read_config can include external files."""
    vars_file = tmp_path / "vars.yaml"
    vars_file.write_text(
        dedent(
            """
            course_name: "DSC 101"
            semester: "Fall 2025"
            """
        )
    )

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            vars:
              __include__: vars.yaml

            website:
              theme:
                use: "default"
                config:
                  short_title: ${ vars.course_name }
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert config.vars["course_name"] == "DSC 101"
    assert config.vars["semester"] == "Fall 2025"
    assert config.website.theme["config"]["short_title"] == "DSC 101"


def test_read_config_website_elements_defaults_to_empty(tmp_path: Path) -> None:
    """Test that website.elements defaults to an empty dict."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            website:
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert config.website.elements == {}


def test_read_config_reads_website_elements(tmp_path: Path) -> None:
    """Test that website.elements is read, interpolating vars but preserving
    !template strings for resolution at render time."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            vars:
              course_name: "DSC 101"

            website:
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
              elements:
                listing:
                  title: ${ vars.course_name }
                  cell: !template "${ publication.metadata.name }"
            """
        )
    )

    config = read_config(config_file)

    listing = config.website.elements["listing"]
    assert listing["title"] == "DSC 101"
    assert listing["cell"] == {"__template__": "${ publication.metadata.name }"}
