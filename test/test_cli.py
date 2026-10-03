"""Tests for the command-line interface."""

import contextlib
import datetime
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

            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
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


def test_build_reports_its_progress(project):
    import re

    result = _invoke("build")

    assert "Discovered 1 collection, 1 publication." in result.output
    assert "Built 1 artifact." in result.output
    assert re.search(r"Built the site in _build \(\d+\.\d s\)\.", result.output)
    assert "Skipped" not in result.output


def _recipes_project(project):
    """Add a publication with a recipe, and one not released yet."""
    pub = project / "notes" / "01-intro"
    pub.mkdir(parents=True)
    (project / "notes" / "collection.yaml").write_text(
        "publication_schema:\n  required_artifacts: [notes.pdf, later.pdf]\n"
    )
    (pub / "publication.yaml").write_text(
        "metadata: {}\nartifacts:\n"
        "  notes.pdf:\n    recipe: touch notes.pdf\n"
        "  later.pdf:\n    recipe: touch later.pdf\n"
        "    release_time: 2099-01-01 00:00:00\n"
    )


def test_build_summarizes_the_artifacts(project):
    _recipes_project(project)

    result = _invoke("build")

    # (and the homework, which has no recipe)
    assert "Built 2 artifacts (1 by its recipe)." in result.output
    assert "Skipped 1 artifact: 1 not released yet." in result.output
    # each recipe is shown only as it runs, on a terminal
    assert "Running the recipe" not in result.output


def test_verbose_build_says_which_recipe_each_output_is_from(project):
    _recipes_project(project)

    result = _invoke("build", "--verbose")

    assert "Running the recipe for notes/01-intro/notes.pdf" in result.output
    assert (
        "  in working directory: notes/01-intro\n  $ touch notes.pdf" in result.output
    )


def test_verbose_build_says_which_artifacts_were_skipped(project):
    _recipes_project(project)

    result = _invoke("build", "--verbose", "--current-time", "2098-12-25T00:00:00")

    assert (
        "○ Skipped notes/01-intro/later.pdf: not released yet (releases "
        "Thu 2099-01-01 00:00, in 7 days)" in result.output
    )


def test_build_lists_skipped_artifacts_only_when_verbose(project):
    _recipes_project(project)

    result = _invoke("build")

    assert "Skipped 1 artifact: 1 not released yet." in result.output
    assert "later.pdf" not in result.output


def test_build_progress_shows_the_running_recipe_as_a_status(project):
    from automata import Automata
    from automata.cli import _BuildProgress

    _recipes_project(project)
    automata = Automata(project)
    lines, statuses = [], []
    _BuildProgress(automata, echo=lines.append, status=statuses.append)

    automata.build()

    from rich.text import Text

    shown = [Text.from_markup(s).plain if s else s for s in statuses]
    assert shown[0] == "Discovering materials…"
    assert any(
        "running the recipe for notes/01-intro/notes.pdf" in s for s in shown[:-1]
    )
    assert "Rendering the website…" in shown
    assert shown[-1] is None
    assert not any("running the recipe" in line.lower() for line in lines)


def test_publish_reports_the_builds_progress(publishing_project):
    result = _invoke("publish")

    assert "Discovered" in result.output
    assert "Built the site in" in result.output


def test_build_accepts_current_time(project):
    result = _invoke("build", "--current-time", "2025-01-01T00:00:00")

    assert "2025-01-01 00:00:00" in result.output
    assert (project / "_build" / "index.html").exists()


def test_current_time_with_an_offset_is_converted_to_local_time(project):
    result = _invoke("build", "--current-time", "2025-01-01T00:00:00+00:00")

    local = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc).astimezone()
    assert local.strftime("%Y-%m-%d %H:%M:%S") in result.output
    assert (project / "_build" / "index.html").exists()


# pipeline steps =======================================================================


@pytest.mark.parametrize(
    "command", ["clean-build-directory", "build-materials", "export", "render-website"]
)
def test_the_pipeline_stages_are_only_under_pipeline(project, command):
    result = runner.invoke(app, [command])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_clean_build_directory_empties_the_build_directory(project):
    (project / "_build").mkdir()
    (project / "_build" / "stale.html").write_text("stale")

    _invoke("pipeline", "clean")

    assert not (project / "_build" / "stale.html").exists()


def test_build_materials_runs(project):
    result = _invoke("pipeline", "build-materials")

    assert "Materials built." in result.output


def test_export_writes_materials(project):
    import json

    _invoke("pipeline", "export-materials")

    materials_json = project / "_build" / "materials" / "materials.json"
    artifacts = json.loads(materials_json.read_text())["collections"]["homeworks"][
        "publications"
    ]["hw01"]["artifacts"]
    # relative to the build directory, as the website links to them
    assert artifacts["homework.pdf"]["path"] == "materials/homeworks/hw01/homework.pdf"


def test_export_materials_writes_to_another_directory(project, tmp_path):
    out = tmp_path / "materials"

    _invoke("pipeline", "export-materials", "--to", str(out))

    assert (out / "materials.json").exists()
    assert (out / "homeworks" / "hw01" / "homework.pdf").exists()
    assert not (project / "_build" / "materials").exists()


@pytest.mark.parametrize(
    "hold_back",
    [
        lambda project: _schedule_homework(project, "2099-01-01 00:00:00"),
        lambda project: _mark_homework_not_ready(project),
    ],
    ids=["not released yet", "not ready"],
)
def test_export_materials_all_includes_what_isnt_released(project, tmp_path, hold_back):
    hold_back(project)
    some, every = tmp_path / "some", tmp_path / "all"

    _invoke("pipeline", "export-materials", "--to", str(some))
    _invoke("pipeline", "export-materials", "--all", "--to", str(every))

    assert not (some / "homeworks" / "hw01" / "homework.pdf").exists()
    assert (every / "homeworks" / "hw01" / "homework.pdf").exists()


# archive ==============================================================================


def _zip_names(path):
    import zipfile

    with zipfile.ZipFile(path) as archive:
        return set(archive.namelist())


def test_archive_zips_the_materials(project, tmp_path):
    zip_path = tmp_path / "materials.zip"

    result = _invoke("archive", str(zip_path))

    names = _zip_names(zip_path)
    # everything in one folder, named after the zip
    assert "materials/materials.json" in names
    assert "materials/homeworks/hw01/homework.pdf" in names
    assert "Archived 1 artifact to" in result.output
    assert not (project / "_build").exists()


def test_archive_is_named_after_the_course_by_default(project):
    _invoke("archive")

    zip_path = project / "test-fall-2025-materials.zip"
    assert "test-fall-2025-materials/materials.json" in _zip_names(zip_path)


@pytest.mark.parametrize(
    "hold_back",
    [
        lambda project: _schedule_homework(project, "2099-01-01 00:00:00"),
        lambda project: _mark_homework_not_ready(project),
    ],
    ids=["not released yet", "not ready"],
)
def test_archive_all_includes_what_isnt_released(project, tmp_path, hold_back):
    hold_back(project)

    _invoke("archive", str(tmp_path / "some.zip"))
    _invoke("archive", "--all", str(tmp_path / "all.zip"))

    assert "some/homeworks/hw01/homework.pdf" not in _zip_names(tmp_path / "some.zip")
    assert "all/homeworks/hw01/homework.pdf" in _zip_names(tmp_path / "all.zip")


def test_render_website_renders_previously_exported_materials(project):
    _invoke("pipeline", "export-materials")

    _invoke("pipeline", "render-website")

    assert (project / "_build" / "index.html").exists()


def test_render_website_fails_helpfully_without_exported_materials(project):
    result = runner.invoke(app, ["pipeline", "render-website"])

    assert result.exit_code == 1
    assert "automata pipeline export-materials" in result.output
    assert "export()" not in result.output


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
        result = runner.invoke(app, ["resolve"])

    assert result.exit_code == 1
    assert "automata.yaml" in result.output
    assert "Traceback" not in result.output


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


# --current-time =======================================================================


def test_current_time_accepts_days_relative_to_now(project):
    import datetime

    result = _invoke("pipeline", "build-materials", "--current-time", "+5")

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
    assert result.output == (
        f"Error: {project / 'automata.yaml'}:1: website: Expected a dict, but got the "
        "number 3.\n"
    )


def test_clean_build_directory_refusal_prints_an_error(project):
    config = project / "automata.yaml"
    config.write_text(
        config.read_text().replace('build_directory: "_build"', 'build_directory: "."')
    )

    result = runner.invoke(app, ["pipeline", "clean"])

    assert result.exit_code == 1
    assert "Refusing to clean" in result.output
    assert (project / "automata.yaml").exists()


# resolve ==============================================================================


def _notes(project):
    """A publication outside any collection, at notes/."""
    pub = project / "notes" / "publication.yaml"
    pub.parent.mkdir()
    pub.write_text(
        "metadata:\n  title: Notes\n  due: 3 days after 2026-01-01\n"
        "artifacts:\n  notes.pdf:\n    missing_ok: true\n"
    )
    return pub


def test_resolve_prints_everything_discovered_as_json(project):
    import json

    result = _invoke("resolve")

    universe = json.loads(result.output)
    hw01 = universe["collections"]["homeworks"]["publications"]["hw01"]
    assert "homework.pdf" in hw01["artifacts"]


def test_resolve_prints_a_collection_by_its_key(project):
    import json

    result = _invoke("resolve", "homeworks")

    assert "hw01" in json.loads(result.output)["publications"]


def test_resolve_prints_a_publication_by_its_key(project):
    import json

    result = _invoke("resolve", "homeworks/hw01")

    publication = json.loads(result.output)
    assert "homework.pdf" in publication["artifacts"]
    assert "metadata" in publication


@pytest.mark.parametrize("which", ["file", "directory"])
def test_resolve_prints_a_publication_by_its_path(project, which):
    import json

    pub = _notes(project)
    path = pub if which == "file" else pub.parent

    result = _invoke("resolve", str(path))

    publication = json.loads(result.output)
    assert publication["metadata"]["title"] == "Notes"
    assert "notes.pdf" in publication["artifacts"]


def test_resolve_says_when_nothing_has_the_key(project):
    result = runner.invoke(app, ["resolve", "homeworks/hw99"])

    assert result.exit_code == 1
    assert 'Error: Nothing discovered is named "homeworks/hw99".' in result.output


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


def test_failing_script_hook_fails_the_build(project):
    ext_dir = project / "extensions" / "generator"
    (ext_dir / "hooks").mkdir(parents=True)
    (ext_dir / "hooks" / "on_render_pre").write_text(
        "cat > /dev/null && echo 'problem generator crashed' >&2 && exit 1"
    )
    config = project / "automata.yaml"
    config.write_text("extensions:\n  - extensions/generator\n" + config.read_text())

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert 'Error: Script hook "on_render_pre" of extension "generator"' in (
        result.output
    )
    assert not (project / "_build" / "index.html").exists()


# build errors =========================================================================


def _failing_recipe_project(project):
    pub = project / "notes" / "01-intro"
    pub.mkdir(parents=True)
    (project / "notes" / "collection.yaml").write_text(
        "publication_schema:\n  required_artifacts: [notes.pdf]\n"
    )
    (pub / "publication.yaml").write_text(
        "metadata: {}\nartifacts:\n  notes.pdf:\n"
        "    recipe: \"echo '! LaTeX Error: File not found.' && exit 1\"\n"
    )


def test_failing_recipe_shows_the_artifact_and_its_output(project):
    _failing_recipe_project(project)

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Error: Building notes/01-intro/notes.pdf failed" in result.output
    assert "! LaTeX Error: File not found." in result.output


@pytest.mark.parametrize(
    "command",
    ["build", "pipeline build-materials", "pipeline export-materials"],
)
def test_verbose_flag_streams_recipe_output(project, command):
    _failing_recipe_project(project)

    result = runner.invoke(app, [*command.split(), "--verbose"])

    # the recipe's output streams to the terminal, so the error points to it
    assert "output shown above" in result.output


def test_publish_verbose_flag_streams_recipe_output(publishing_project):
    _failing_recipe_project(publishing_project)

    result = runner.invoke(app, ["publish", "--verbose"])

    assert "output shown above" in result.output


# configuration errors =================================================================


@pytest.mark.parametrize(
    "bad_vars, expected",
    [
        ("vars: [1, 2]\n", "automata.yaml:1: vars: Expected a dict, but got a list."),
        (
            'vars: {course: "${ vars. }"}\n',
            'automata.yaml:1: vars.course: Invalid template "${ vars. }"',
        ),
        (
            "vars: {course: DSC 40B, title: '${ vars.nope }'}\n",
            'automata.yaml:1: vars.title: "vars" has no key "nope".',
        ),
    ],
)
def test_configuration_errors_print_without_a_traceback(project, bad_vars, expected):
    config = project / "automata.yaml"
    config.write_text(bad_vars + config.read_text())

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert expected in result.output


# status ===============================================================================


def _schedule_homework(project, release_time):
    """Give the homework a release time (next to its path, at the same indent)."""
    config = project / "automata.yaml"
    lines = []
    for line in config.read_text().splitlines():
        lines.append(line)
        if line.strip() == "path: homeworks/hw01/homework.pdf":
            indent = line[: len(line) - len(line.lstrip())]
            lines.append(f"{indent}release_time: {release_time}")
    config.write_text("\n".join(lines) + "\n")


def _mark_homework_not_ready(project):
    """Mark the homework ready: false (next to its path, at the same indent)."""
    config = project / "automata.yaml"
    lines = []
    for line in config.read_text().splitlines():
        lines.append(line)
        if line.strip() == "path: homeworks/hw01/homework.pdf":
            indent = line[: len(line) - len(line.lstrip())]
            lines.append(f"{indent}ready: false")
    config.write_text("\n".join(lines) + "\n")


def test_status_verbose_says_why_an_artifact_is_not_ready(project):
    _mark_homework_not_ready(project)

    result = _invoke("status", "--verbose")

    line = _line_with(result.output, "homework.pdf")
    assert "○ not ready" in line and "marked ready: false" in line


def test_status_verbose_says_a_scheduled_artifact_is_also_not_ready(project):
    _schedule_homework(project, "2025-06-01 00:00:00")
    _mark_homework_not_ready(project)

    result = _invoke("status", "--verbose", "--current-time", "2025-05-01T00:00:00")

    # (the last line with it: in all the artifacts)
    line = [line for line in result.output.splitlines() if "homework.pdf" in line][-1]
    assert "◷ scheduled" in line and "Sun 2025-06-01 00:00" in line
    assert "also marked ready: false" in line


def test_status_summarizes_the_artifacts(project):
    result = _invoke("status")

    assert "● 1 released" in result.output
    assert "build" not in result.output.lower()


def test_status_shows_the_next_releases(project):
    _schedule_homework(project, "2025-06-01 00:00:00")

    result = _invoke("status", "--current-time", "2025-05-01T00:00:00")

    line = _line_with(result.output, "homeworks/hw01/homework.pdf")
    assert "Next releases" in result.output
    assert "◷ 1 scheduled" in result.output
    assert "Sun 2025-06-01 00:00" in line and "in 4 weeks" in line


def test_status_verbose_lists_every_artifact(project):
    result = _invoke("status", "--verbose")

    assert "All artifacts" in result.output
    assert "● released" in _line_with(result.output, "homeworks/hw01/homework.pdf")


def test_status_verbose_shows_when_scheduled_artifacts_release(project):
    _schedule_homework(project, "2025-06-01 00:00:00")

    result = _invoke("status", "--verbose", "--current-time", "2025-05-01T00:00:00")

    lines = [line for line in result.output.splitlines() if "homework.pdf" in line]
    # (in the next releases, and in all the artifacts)
    assert any(
        "◷ scheduled" in line and "Sun 2025-06-01 00:00" in line for line in lines
    )


def test_status_is_colorful_on_a_terminal(project):
    import io

    from rich.console import Console

    from automata import Automata
    from automata.cli import _print_status

    console = Console(file=io.StringIO(), force_terminal=True, width=120)

    _print_status(Automata(project).status(), verbose=True, console=console)

    output = console.file.getvalue()
    assert "\x1b[" in output
    assert "● released" in _strip_ansi(output)


def _line_with(output, text):
    """The line of *output* containing *text*."""
    return next(line for line in output.splitlines() if text in line)


def test_status_json_gives_every_artifact(project):
    import json

    result = _invoke("status", "--json")

    data = json.loads(result.stdout)
    assert [a["key"] for a in data["artifacts"]] == ["homeworks/hw01/homework.pdf"]
    assert "out_of_date" not in data


def test_status_json_with_a_current_time_is_still_json(project):
    import json

    result = _invoke("status", "--json", "--current-time", "2025-05-01T00:00:00")

    assert json.loads(result.stdout)["current_time"] == "2025-05-01T00:00:00"


def test_status_json_with_broken_config_is_json_with_the_error(project):
    import json

    (project / "automata.yaml").write_text("website: 3\n")

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 1
    error = json.loads(result.stdout)["error"]
    assert error.startswith(f"{project / 'automata.yaml'}:1: website: ")


# check ================================================================================


def test_check_with_no_problems(project):
    result = _invoke("check")

    assert "No problems found." in result.output


def test_check_reports_every_problem_and_fails(project):
    (project / "content" / "a.md").write_text("{% if %}\n")
    (project / "content" / "b.md").write_text("---\nvars: [1]\n---\n")

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1
    assert str(project / "content" / "a.md") in result.output
    assert str(project / "content" / "b.md") in result.output
    assert "2 problems found." in result.output


def test_check_json_gives_the_problems(project):
    import json

    (project / "content" / "a.md").write_text("{% if %}\n")

    result = runner.invoke(app, ["check", "--json"])

    assert result.exit_code == 1
    (problem,) = json.loads(result.stdout)["problems"]
    assert problem["area"] == "pages"


def test_check_reports_broken_config_as_a_problem(project):
    import json

    (project / "automata.yaml").write_text("website: 3\n")

    result = runner.invoke(app, ["check", "--json"])

    assert result.exit_code == 1
    (problem,) = json.loads(result.stdout)["problems"]
    assert problem["area"] == "configuration"
    assert problem["message"].startswith(f"{project / 'automata.yaml'}:1: website: ")


# calendar =============================================================================


def _add_calendar(project):
    """Give the homework a due date, and show due dates on the calendar."""
    config = project / "automata.yaml"
    text = config.read_text()
    text = text.replace(
        "                  required_artifacts:\n",
        "                  metadata_schema:\n"
        "                    required_keys:\n"
        "                      due: {type: datetime}\n"
        "                  required_artifacts:\n",
    )
    lines = []
    for line in text.splitlines():
        lines.append(line)
        if line.strip() == "hw01:":
            indent = line[: len(line) - len(line.lstrip())]
            lines.append(f"{indent}  metadata: {{due: 2025-01-06 09:00:00}}")
    config.write_text(
        "calendar:\n  homeworks:\n    dates:\n      due:\n" + "\n".join(lines) + "\n"
    )


def test_calendar_prints_a_table(project):
    _add_calendar(project)

    # wide enough that labels don't wrap
    result = runner.invoke(app, ["calendar", "--all"], env={"COLUMNS": "200"})

    assert "hw01 due 09:00" in result.output


def test_calendar_filters_by_collection_and_key(project):
    _add_calendar(project)

    result = _invoke(
        "calendar", "--all", "--collection", "homeworks", "--key", "released"
    )

    assert "hw01 due" not in result.output
    assert "Nothing to show: there are no released dates in homeworks." in result.output


def test_calendar_says_when_there_is_nothing_from_this_week_on(project):
    _add_calendar(project)

    # Feb 1, 2025 is a Saturday; the only date is Jan 6
    result = _invoke("calendar", "--current-time", "2025-02-01T12:00:00")

    assert (
        "Nothing to show: there are no dates from this week (starting Sun Jan 26, "
        "2025) on. Use --all to include earlier weeks." in result.output
    )


def test_calendar_says_when_there_is_nothing_in_the_requested_dates(project):
    _add_calendar(project)

    result = _invoke("calendar", "--from", "2025-03-01")

    assert "Nothing to show: there are no dates on or after Sat Mar 1, 2025." in (
        result.output
    )


def test_calendar_writes_icalendar(project, tmp_path):
    _add_calendar(project)
    ics = tmp_path / "calendar.ics"

    result = _invoke("calendar", "--all", "--ics", str(ics))

    assert f"Wrote {ics} (1 event)" in result.output
    assert "SUMMARY:hw01 due" in ics.read_text()


def test_calendar_writes_html_and_pdf(project, tmp_path):
    _add_calendar(project)
    html, pdf = tmp_path / "calendar.html", tmp_path / "calendar.pdf"

    result = _invoke("calendar", "--all", "--html", str(html), "--pdf", str(pdf))

    assert "hw01 due" in html.read_text()
    assert pdf.read_bytes().startswith(b"%PDF")
    assert f"Wrote {html}" in result.output
    assert f"Wrote {pdf}" in result.output


def test_calendar_json(project):
    import json

    _add_calendar(project)

    result = _invoke("calendar", "--all", "--json")

    data = json.loads(result.stdout)
    assert data["weeks"][0]["start"] == "2025-01-05"  # a Sunday


def test_calendar_weeks_can_start_on_monday(project):
    import json

    _add_calendar(project)

    result = _invoke("calendar", "--all", "--json", "--week-start", "monday")

    assert json.loads(result.stdout)["weeks"][0]["start"] == "2025-01-06"


def test_calendar_without_configuration_is_an_error(project):
    result = runner.invoke(app, ["calendar"])

    assert result.exit_code == 1
    assert 'has no "calendar" section' in result.output


def test_calendar_shows_from_the_current_week_by_default(project):
    import json

    _add_calendar(project)  # due 2025-01-06

    before = _invoke("calendar", "--json", "--current-time", "2025-01-01T00:00:00")
    after = _invoke("calendar", "--json", "--current-time", "2025-02-01T00:00:00")

    assert json.loads(before.stdout)["weeks"] != []
    assert json.loads(after.stdout)["weeks"] == []


def test_calendar_can_leave_today_unhighlighted(project, tmp_path):
    _add_calendar(project)
    html = tmp_path / "calendar.html"

    _invoke(
        "calendar",
        "--current-time",
        "2025-01-06T08:00:00",
        "--no-highlight-today",
        "--html",
        str(html),
    )

    assert 'class="today"' not in html.read_text()


def test_build_progress_is_colorful_on_a_terminal(project):
    import io

    from rich.console import Console

    from automata import Automata
    from automata.cli import _BuildProgress

    _recipes_project(project)
    automata = Automata(project)
    console = Console(file=io.StringIO(), force_terminal=True, width=200)
    _BuildProgress(automata, echo=console.print, verbose=True)

    automata.build()

    output = console.file.getvalue()
    assert "\x1b[" in output  # styled
    assert "✓ Built 2 artifacts (1 by its recipe)." in _strip_ansi(output)
    assert "▶ Running the recipe for notes/01-intro/notes.pdf" in _strip_ansi(output)


def _strip_ansi(text):
    import re

    return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", text)


def test_lines_printed_while_the_spinner_shows_are_on_lines_of_their_own():
    import io

    from rich.console import Console

    from automata.cli import _TerminalStatus

    console = Console(file=io.StringIO(), force_terminal=True, width=80)
    status = _TerminalStatus(console)

    status("Building materials…")
    status.print("[green]✓[/] Built 3 artifacts.")
    status(None)

    # what's left on each line of the screen, after carriage returns
    lines = [
        line.split("\r")[-1]
        for line in _strip_ansi(console.file.getvalue()).split("\n")
    ]
    assert "✓ Built 3 artifacts." in lines
    assert not any("Building materials…" in line and "✓" in line for line in lines)


@pytest.mark.parametrize("args", [[], ["pipeline"]], ids=["automata", "pipeline"])
def test_a_command_without_a_subcommand_prints_its_help(project, args):
    from automata.cli import app_for_directory

    full, _ = app_for_directory(project)

    result = runner.invoke(full, args)

    assert "Usage:" in result.output
    assert "Commands" in result.output
    assert "Missing command" not in result.output


@pytest.mark.parametrize(
    "delta, expected",
    [
        (datetime.timedelta(seconds=30), "in less than a minute"),
        (datetime.timedelta(minutes=1), "in a minute"),
        (datetime.timedelta(minutes=45), "in 45 minutes"),
        (datetime.timedelta(hours=1, minutes=20), "in an hour"),
        (datetime.timedelta(hours=2), "in 2 hours"),
        (datetime.timedelta(days=1, hours=3), "in a day"),
        (datetime.timedelta(days=3), "in 3 days"),
        (datetime.timedelta(days=13), "in 13 days"),
        (datetime.timedelta(days=14), "in 2 weeks"),
        (datetime.timedelta(days=72), "in 10 weeks"),
        (datetime.timedelta(hours=-2), "2 hours ago"),
        (datetime.timedelta(days=-7), "7 days ago"),
    ],
)
def test_times_are_described_relative_to_now(delta, expected):
    from automata.cli import _relative

    now = datetime.datetime(2025, 1, 15, 12, 0)

    assert _relative(now + delta, now) == expected
