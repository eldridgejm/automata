"""Tests for the command-line interface."""

import contextlib
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


def test_build_from_a_subdirectory_uses_the_enclosing_project(project):
    with contextlib.chdir(project / "content"):
        result = _invoke("build")

    assert (project / "_build" / "index.html").exists()
    assert f"Using project at {project}" in result.output


def test_build_from_the_project_root_does_not_announce_the_project(project):
    result = _invoke("build")

    assert "Using project at" not in result.output


def test_outside_any_project_prints_an_error_without_a_traceback(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    with contextlib.chdir(elsewhere):
        result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "automata.yaml" in result.output
    assert "Traceback" not in result.output


def test_resolve_outside_any_project_prints_one_clear_error(tmp_path):
    with contextlib.chdir(tmp_path):
        result = runner.invoke(app, ["resolve", "publication.yaml"])

    assert result.exit_code == 1
    assert "automata.yaml" in result.output
    assert "Error resolving" not in result.output


# publish ==============================================================================


_RECORDER_EXTENSION = """\
import json
from pathlib import Path

from automata.extensions import Extension


def _recording(build_dir, config, project_dir):
    with open(Path(project_dir) / "published.log", "a") as log:
        log.write(json.dumps(config) + "\\n")


def _register(args):
    args.publishers["recording"] = _recording
    return args


extension = Extension(name="recorder", hooks={"on_register_publishers": _register})
"""


@pytest.fixture
def publishing_project(project):
    """The project, with two publish targets using a recording strategy."""
    ext_dir = project / "extensions" / "recorder"
    ext_dir.mkdir(parents=True)
    (ext_dir / "extension.py").write_text(_RECORDER_EXTENSION)
    config = project / "automata.yaml"
    config.write_text(
        "extensions:\n  - extensions/recorder\n"
        + config.read_text()
        + dedent("""\
            publish:
              first:
                strategy: recording
                config: {label: one}
              second:
                strategy: recording
                config: {label: two}
        """)
    )
    return project


def _published_labels(project):
    import json

    log = project / "published.log"
    lines = log.read_text().splitlines() if log.exists() else []
    return [json.loads(line)["label"] for line in lines]


def test_publish_without_a_target_publishes_every_target(publishing_project):
    result = _invoke("publish")

    assert sorted(_published_labels(publishing_project)) == ["one", "two"]
    assert "Published to first." in result.output
    assert "Published to second." in result.output


def test_publish_a_named_target(publishing_project):
    result = _invoke("publish", "second")

    assert _published_labels(publishing_project) == ["two"]
    assert "Published to second." in result.output


def test_publish_unknown_target_prints_an_error_without_a_traceback(
    publishing_project,
):
    result = runner.invoke(app, ["publish", "third"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "third" in result.output
    assert _published_labels(publishing_project) == []


def test_publish_without_publish_targets_prints_an_error(project):
    result = runner.invoke(app, ["publish"])

    assert result.exit_code == 1
    assert "publish" in result.output


# discover =============================================================================


def test_discover_prints_each_collection_and_its_publication_count(project):
    result = _invoke("discover")

    assert "homeworks: 1 publication(s)" in result.output


# --current-time =======================================================================


def test_current_time_accepts_days_relative_to_now(project):
    import datetime

    result = _invoke("build-materials", "--current-time", "+5")

    expected = (datetime.datetime.now() + datetime.timedelta(days=5)).date()
    assert f"Running as if it is currently {expected}" in result.output


def test_invalid_current_time_prints_an_error(project):
    result = runner.invoke(app, ["build", "--current-time", "next tuesday"])

    assert result.exit_code == 1
    assert "Invalid --current-time" in result.output
    assert not (project / "_build").exists()


# errors ===============================================================================


def test_invalid_automata_yaml_prints_an_error_without_a_traceback(project):
    (project / "automata.yaml").write_text("website: 3\n")

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Invalid configuration" in result.output


def test_clean_build_directory_refusal_prints_an_error(project):
    config = project / "automata.yaml"
    config.write_text(
        config.read_text().replace('build_directory: "_build"', 'build_directory: "."')
    )

    result = runner.invoke(app, ["clean-build-directory"])

    assert result.exit_code == 1
    assert "Refusing to clean" in result.output
    assert (project / "automata.yaml").exists()


# resolve ==============================================================================


def test_resolve_prints_the_publication_as_json(project, tmp_path):
    import json

    pub = project / "notes" / "publication.yaml"
    pub.parent.mkdir()
    pub.write_text(
        "metadata:\n  title: Notes\n  due: 3 days after 2026-01-01\n"
        "artifacts:\n  notes.pdf:\n    missing_ok: true\n"
    )

    result = _invoke("resolve", str(pub))

    resolved = json.loads(result.output)
    assert resolved["metadata"]["title"] == "Notes"
    assert "notes.pdf" in resolved["artifacts"]


def test_resolve_missing_file_prints_an_error(project):
    result = runner.invoke(app, ["resolve", "nowhere/publication.yaml"])

    assert result.exit_code == 1
    assert "Error" in result.output


# tab completion =======================================================================


def test_publish_target_completion_lists_matching_targets(publishing_project):
    from automata.cli import _complete_publish_targets

    assert sorted(_complete_publish_targets("")) == ["first", "second"]
    assert _complete_publish_targets("se") == ["second"]


def test_publish_target_completion_outside_a_project_is_empty(tmp_path):
    from automata.cli import _complete_publish_targets

    with contextlib.chdir(tmp_path):
        assert _complete_publish_targets("") == []


def test_errors_during_the_build_print_without_a_traceback(project):
    # given: an inline artifact with a recipe, which is not allowed
    config = project / "automata.yaml"
    lines = config.read_text().splitlines()
    i = next(n for n, line in enumerate(lines) if "path: homeworks" in line)
    indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
    lines.insert(i + 1, f"{indent}recipe: make")
    config.write_text("\n".join(lines) + "\n")

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Error:" in result.output
    assert "recipe" in result.output


def test_yaml_syntax_error_in_automata_yaml_prints_without_a_traceback(project):
    (project / "automata.yaml").write_text("website:\n  theme: default\n   x: 1\n")

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Invalid YAML in" in result.output
    assert "line 3" in result.output
