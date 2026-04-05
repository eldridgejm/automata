"""Tests for the Automata public API."""

import json
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pytest

from automata import Automata
from automata.materials import Universe


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal automata project."""
    project = tmp_path / "project"
    project.mkdir()

    # Theme path (use the built-in default theme via filesystem path)
    theme_path = (
        Path(__file__).parent.parent
        / "src"
        / "automata"
        / "builtin"
        / "themes"
        / "default"
    )

    # automata.yaml
    (project / "automata.yaml").write_text(
        dedent(f"""\
            website:
              theme:
                use: "{theme_path}"
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


class TestAutomataInit:

    def test_reads_config(self, project_dir):
        a = Automata(project_dir)
        assert a.config.website.build_directory == "_build"

    def test_path_is_stored(self, project_dir):
        a = Automata(project_dir)
        assert a.path == project_dir

    def test_hooks_are_initialized(self, project_dir):
        a = Automata(project_dir)
        assert a.hooks is not None


class TestDiscover:

    def test_returns_universe(self, project_dir):
        a = Automata(project_dir)
        universe = a.discover()
        assert isinstance(universe, Universe)
        assert "homeworks" in universe.collections


class TestBuildMaterials:

    def test_returns_built_universe(self, project_dir):
        a = Automata(project_dir)
        discovered = a.discover()
        built = a.build_materials(
            discovered, ignore_release_time=True, ignore_ready=True
        )
        assert isinstance(built, Universe)
        assert "homeworks" in built.collections


class TestExport:

    def test_writes_materials_json(self, project_dir):
        a = Automata(project_dir)
        discovered = a.discover()
        built = a.build_materials(
            discovered, ignore_release_time=True, ignore_ready=True
        )
        a.export(built)

        materials_json = project_dir / "_build" / "materials" / "materials.json"
        assert materials_json.exists()
        data = json.loads(materials_json.read_text())
        assert "homeworks" in data["collections"]

    def test_returns_exported_universe(self, project_dir):
        a = Automata(project_dir)
        discovered = a.discover()
        built = a.build_materials(
            discovered, ignore_release_time=True, ignore_ready=True
        )
        exported = a.export(built)
        assert isinstance(exported, Universe)


class TestGenerateWebsite:

    def test_generates_html(self, project_dir):
        a = Automata(project_dir)
        discovered = a.discover()
        built = a.build_materials(
            discovered, ignore_release_time=True, ignore_ready=True
        )
        a.export(built)
        a.generate_website()

        index = project_dir / "_build" / "index.html"
        assert index.exists()
        assert "Home" in index.read_text()


class TestGenerate:

    def test_full_pipeline(self, project_dir):
        a = Automata(project_dir)
        a.generate()

        index = project_dir / "_build" / "index.html"
        assert index.exists()
        assert "Home" in index.read_text()

        materials_json = project_dir / "_build" / "materials" / "materials.json"
        assert materials_json.exists()
