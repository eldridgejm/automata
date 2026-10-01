"""Tests for the command-line interface."""

from textwrap import dedent

import pytest
from typer.testing import CliRunner

from automata.cli import app

runner = CliRunner()


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A minimal project with one released homework; the cwd is set to it."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "automata.yaml").write_text(
        dedent("""\
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

            website:
              theme:
                use: "default"
                config:
                  short_title: "Test"
                  long_title: "Test Course"
                  rebuild_tailwind: false
              content_directory: "content"
              build_directory: "_build"
        """)
    )
    (project / "homeworks" / "hw01").mkdir(parents=True)
    (project / "homeworks" / "hw01" / "homework.pdf").write_text("hw1")
    (project / "content").mkdir()
    (project / "content" / "index.md").write_text("# Home")

    monkeypatch.chdir(project)
    return project


def _invoke(*args):
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result


# build ================================================================================


def test_build_builds_the_site(project):
    _invoke("build")

    assert (project / "_build" / "index.html").exists()
    assert (project / "_build" / "materials" / "materials.json").exists()


def test_build_accepts_current_time(project):
    result = _invoke("build", "--current-time", "2025-01-01T00:00:00")

    assert "2025-01-01 00:00:00" in result.output
    assert (project / "_build" / "index.html").exists()


# pipeline steps =======================================================================


def test_clean_build_directory_empties_the_build_directory(project):
    (project / "_build").mkdir()
    (project / "_build" / "stale.html").write_text("stale")

    _invoke("clean-build-directory")

    assert not (project / "_build" / "stale.html").exists()


def test_build_materials_runs(project):
    result = _invoke("build-materials")

    assert "Materials built." in result.output


def test_export_writes_materials(project):
    _invoke("export")

    assert (project / "_build" / "materials" / "materials.json").exists()


def test_render_website_renders_previously_exported_materials(project):
    _invoke("export")

    _invoke("render-website")

    assert (project / "_build" / "index.html").exists()


def test_render_website_fails_helpfully_without_exported_materials(project):
    result = runner.invoke(app, ["render-website"])

    assert result.exit_code == 1
    assert "export" in result.output


# old names ============================================================================


@pytest.mark.parametrize("old_name", ["generate", "make-materials"])
def test_old_command_names_are_gone(project, old_name):
    result = runner.invoke(app, [old_name])

    assert result.exit_code != 0


# finding the project ==================================================================


def test_build_from_a_subdirectory_uses_the_enclosing_project(project, monkeypatch):
    monkeypatch.chdir(project / "content")

    result = _invoke("build")

    assert (project / "_build" / "index.html").exists()
    assert f"Using project at {project}" in result.output


def test_build_from_the_project_root_does_not_announce_the_project(project):
    result = _invoke("build")

    assert "Using project at" not in result.output


def test_outside_any_project_prints_an_error_without_a_traceback(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "automata.yaml" in result.output
    assert "Traceback" not in result.output


def test_resolve_outside_any_project_prints_one_clear_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["resolve", "publication.yaml"])

    assert result.exit_code == 1
    assert "automata.yaml" in result.output
    assert "Error resolving" not in result.output
