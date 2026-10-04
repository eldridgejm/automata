"""Tests for initializing a new project (automata init)."""

import pytest
from typer.testing import CliRunner

from automata import Automata
from automata.cli import app
from automata.exceptions import Error

runner = CliRunner()


# Automata.init ========================================================================


def test_init_creates_the_configuration_and_website(tmp_path):
    Automata.init(tmp_path)

    assert (tmp_path / "automata.yaml").is_file()
    assert (tmp_path / "website" / "content" / "index.md").is_file()
    assert (tmp_path / "website" / "content" / "syllabus.md").is_file()
    assert (tmp_path / "website" / "schedule.yaml").is_file()


def test_init_returns_the_new_project(tmp_path):
    project = Automata.init(tmp_path)

    assert isinstance(project, Automata)
    assert project.path == tmp_path
    assert project.config.course.name


def test_init_creates_a_project_without_problems(tmp_path):
    project = Automata.init(tmp_path)

    assert project.check() == []


def test_init_leaves_existing_course_files_alone(tmp_path):
    homework = tmp_path / "homeworks" / "hw01" / "homework.tex"
    homework.parent.mkdir(parents=True)
    homework.write_text("the homework")

    Automata.init(tmp_path)

    assert homework.read_text() == "the homework"


def test_init_refuses_if_the_configuration_exists(tmp_path):
    (tmp_path / "automata.yaml").write_text("existing")

    with pytest.raises(Error, match="automata.yaml"):
        Automata.init(tmp_path)

    assert (tmp_path / "automata.yaml").read_text() == "existing"
    assert not (tmp_path / "website").exists()


def test_init_refuses_if_the_website_directory_exists(tmp_path):
    (tmp_path / "website").mkdir()

    with pytest.raises(Error, match="website"):
        Automata.init(tmp_path)

    assert not (tmp_path / "automata.yaml").exists()
    assert list((tmp_path / "website").iterdir()) == []


def test_init_refuses_inside_an_existing_project(tmp_path):
    (tmp_path / "automata.yaml").write_text("existing")
    course = tmp_path / "course"
    course.mkdir()

    with pytest.raises(Error, match=str(tmp_path / "automata.yaml")):
        Automata.init(course)

    assert list(course.iterdir()) == []


def test_init_refuses_deep_inside_an_existing_project(tmp_path):
    (tmp_path / "automata.yaml").write_text("existing")
    course = tmp_path / "a" / "b" / "course"
    course.mkdir(parents=True)

    with pytest.raises(Error, match="inside"):
        Automata.init(course)

    assert list(course.iterdir()) == []


@pytest.mark.integration
def test_init_creates_a_project_that_builds(tmp_path):
    project = Automata.init(tmp_path)

    project.build()

    assert (tmp_path / "_build" / "index.html").is_file()
    assert (tmp_path / "_build" / "syllabus.html").is_file()


# the init command =====================================================================


def test_init_command_initializes_the_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "automata.yaml").is_file()
    assert (tmp_path / "website" / "content" / "index.md").is_file()


def test_init_command_lists_what_it_created_and_what_to_do_next(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert "automata.yaml" in result.output
    assert "website/content/index.md" in result.output
    assert "automata serve" in result.output


def test_init_command_reports_an_existing_project_as_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "automata.yaml").write_text("existing")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert (tmp_path / "automata.yaml").read_text() == "existing"


def test_init_command_reports_being_inside_a_project_as_an_error(tmp_path, monkeypatch):
    (tmp_path / "automata.yaml").write_text("existing")
    course = tmp_path / "course"
    course.mkdir()
    monkeypatch.chdir(course)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert list(course.iterdir()) == []
