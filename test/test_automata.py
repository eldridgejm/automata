"""Tests for the Automata public API."""

import json
from textwrap import dedent

import pytest

from automata import Automata
from automata.materials import Universe


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal automata project."""
    project = tmp_path / "project"
    project.mkdir()

    # automata.yaml
    (project / "automata.yaml").write_text(
        dedent("""\
            website:
              theme:
                use: "default"
                config:
                  short_title: "Test"
                  long_title: "Test Course"
              content_directory: "content"
              build_directory: "_build"
        """)
    )

    # Content
    content = project / "content"
    content.mkdir()
    (content / "index.md").write_text("# Home")

    # A simple collection with one publication
    hw = project / "homeworks"
    hw.mkdir()
    (hw / "collection.yaml").write_text(
        dedent("""\
            publication_schema:
                required_artifacts:
                    - homework.pdf
        """)
    )

    pub = hw / "hw01"
    pub.mkdir()
    (pub / "publication.yaml").write_text(
        dedent("""\
            metadata:
                name: Homework 1

            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
        """)
    )

    return project


# Automata() ===========================================================================


def test_init_reads_config(project_dir):
    a = Automata(project_dir)
    assert a.config.website.build_directory == "_build"


def test_init_stores_path(project_dir):
    a = Automata(project_dir)
    assert a.path == project_dir


def test_init_initializes_hooks(project_dir):
    a = Automata(project_dir)
    assert a.hooks is not None


# discover() ===========================================================================


def test_discover_returns_universe(project_dir):
    a = Automata(project_dir)
    universe = a.discover()
    assert isinstance(universe, Universe)
    assert "homeworks" in universe.collections


# build_materials() ====================================================================


def test_build_materials_returns_built_universe(project_dir):
    a = Automata(project_dir)
    discovered = a.discover()
    built = a.build_materials(discovered, ignore_release_time=True, ignore_ready=True)
    assert isinstance(built, Universe)
    assert "homeworks" in built.collections


# export() =============================================================================


def test_export_writes_materials_json(project_dir):
    a = Automata(project_dir)
    discovered = a.discover()
    built = a.build_materials(discovered, ignore_release_time=True, ignore_ready=True)
    a.export(built)

    materials_json = project_dir / "_build" / "materials" / "materials.json"
    assert materials_json.exists()
    data = json.loads(materials_json.read_text())
    assert "homeworks" in data["collections"]


def test_export_returns_exported_universe(project_dir):
    a = Automata(project_dir)
    discovered = a.discover()
    built = a.build_materials(discovered, ignore_release_time=True, ignore_ready=True)
    exported = a.export(built)
    assert isinstance(exported, Universe)


# generate_website() ===================================================================


def test_generate_website_generates_html(project_dir):
    a = Automata(project_dir)
    discovered = a.discover()
    built = a.build_materials(discovered, ignore_release_time=True, ignore_ready=True)
    a.export(built)
    a.generate_website()

    index = project_dir / "_build" / "index.html"
    assert index.exists()
    assert "Home" in index.read_text()


# generate() ===========================================================================


def test_generate_runs_full_pipeline(project_dir):
    a = Automata(project_dir)
    a.generate()

    index = project_dir / "_build" / "index.html"
    assert index.exists()
    assert "Home" in index.read_text()

    materials_json = project_dir / "_build" / "materials" / "materials.json"
    assert materials_json.exists()
