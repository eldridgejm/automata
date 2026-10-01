"""Tests for the Automata public API."""

import json
from datetime import datetime
from textwrap import dedent

import pytest

from automata import Automata
from automata.exceptions import Error
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


# cleaning the build directory =========================================================


def _write_release_project(
    project, build_directory="_build", content_directory="content", extra=""
):
    """Write a project with one homework released on 2025-01-10."""
    project.mkdir(exist_ok=True)
    (project / "automata.yaml").write_text(
        dedent(f"""\
            materials:
              homeworks:
                schema:
                  required_artifacts:
                    - homework.pdf
                publications:
                  hw01:
                    artifacts:
                      homework.pdf:
                        path: homeworks/hw01/homework.pdf
                        release_time: 2025-01-10 12:00:00

            website:
              theme:
                use: "default"
                config:
                  short_title: "Test"
                  long_title: "Test Course"
                  rebuild_tailwind: false
              content_directory: "{content_directory}"
              build_directory: "{build_directory}"
            {extra}
        """)
    )
    (project / "homeworks" / "hw01").mkdir(parents=True, exist_ok=True)
    (project / "homeworks" / "hw01" / "homework.pdf").write_text("hw1")
    content = project / content_directory
    content.mkdir(parents=True, exist_ok=True)
    (content / "index.md").write_text("# Home")
    return project


_BEFORE_RELEASE = datetime(2025, 1, 1)
_AFTER_RELEASE = datetime(2025, 2, 1)


def _released_files(build_dir):
    return [p for p in build_dir.rglob("homework.pdf")]


def test_generate_removes_artifact_that_is_no_longer_released(tmp_path):
    # given: the homework was released and built
    project = _write_release_project(tmp_path / "project")
    Automata(project).generate(current_time=_AFTER_RELEASE)
    assert _released_files(project / "_build")

    # when: the release is effectively withdrawn and the site is rebuilt
    Automata(project).generate(current_time=_BEFORE_RELEASE)

    # then
    assert _released_files(project / "_build") == []


def test_generate_removes_page_that_was_deleted(tmp_path):
    # given
    project = _write_release_project(tmp_path / "project")
    (project / "content" / "syllabus.md").write_text("# Syllabus")
    Automata(project).generate(current_time=_AFTER_RELEASE)
    assert (project / "_build" / "syllabus.html").exists()

    # when
    (project / "content" / "syllabus.md").unlink()
    Automata(project).generate(current_time=_AFTER_RELEASE)

    # then
    assert not (project / "_build" / "syllabus.html").exists()


def test_generate_keeps_top_level_dot_entries_in_build_directory(tmp_path):
    # given
    project = _write_release_project(tmp_path / "project")
    build = project / "_build"
    (build / ".git").mkdir(parents=True)
    (build / ".git" / "HEAD").write_text("ref: refs/heads/gh-pages")
    (build / ".nojekyll").write_text("")
    (build / "stale.html").write_text("stale")

    # when
    Automata(project).generate(current_time=_AFTER_RELEASE)

    # then
    assert (build / ".git" / "HEAD").read_text() == "ref: refs/heads/gh-pages"
    assert (build / ".nojekyll").exists()
    assert not (build / "stale.html").exists()


def test_generate_does_not_clean_when_disabled(tmp_path):
    # given
    project = _write_release_project(
        tmp_path / "project", extra="  clean_build_directory: false"
    )
    (project / "_build").mkdir()
    (project / "_build" / "stale.html").write_text("stale")

    # when
    Automata(project).generate(current_time=_AFTER_RELEASE)

    # then
    assert (project / "_build" / "stale.html").exists()


def test_clean_build_directory_defaults_to_true(project_dir):
    assert Automata(project_dir).config.website.clean_build_directory is True


def test_clean_build_directory_does_nothing_if_build_directory_missing(project_dir):
    Automata(project_dir).clean_build_directory()

    assert not (project_dir / "_build").exists()


@pytest.mark.parametrize(
    "build_directory, content_directory",
    [
        (".", "content"),  # the project root
        ("..", "content"),  # contains the project root
        ("content", "content"),  # the content directory
        ("website", "website/content"),  # contains the content directory
        ("content/_build", "content"),  # inside the content directory
    ],
)
def test_clean_build_directory_refuses_unsafe_build_directory(
    tmp_path, build_directory, content_directory
):
    # given
    project = _write_release_project(
        tmp_path / "project",
        build_directory=build_directory,
        content_directory=content_directory,
    )
    (project / build_directory).mkdir(parents=True, exist_ok=True)
    sentinel = project / build_directory / "keep-me.txt"
    sentinel.write_text("important")

    # when / then
    with pytest.raises(Error) as excinfo:
        Automata(project).clean_build_directory()

    assert "build_directory" in str(excinfo.value)
    assert sentinel.exists()


def test_clean_build_directory_refuses_directory_with_automata_yaml(tmp_path):
    # given: the build directory is another automata project
    other = _write_release_project(tmp_path / "other")
    project = _write_release_project(tmp_path / "project", build_directory=str(other))

    # when / then
    with pytest.raises(Error):
        Automata(project).clean_build_directory()

    assert (other / "automata.yaml").exists()
