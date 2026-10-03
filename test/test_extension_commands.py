"""Tests for commands that extensions add to the CLI (automata NAME)."""

from pathlib import Path
from textwrap import dedent

import pytest
from typer.testing import CliRunner

from automata.cli import app_for_directory, requested_command

runner = CliRunner()


def _project(tmp_path: Path, extensions: dict[str, dict[str, str]]) -> Path:
    """A project with local extensions, each given as its files."""
    project = tmp_path / "project"
    project.mkdir()
    for name, files in extensions.items():
        for relative, content in files.items():
            path = project / "extensions" / name / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dedent(content))
    listed = "".join(f"  - extensions/{name}\n" for name in extensions)
    (project / "automata.yaml").write_text(
        "course:\n"
        "  name: DSC 40B\n"
        "  title: Theoretical Foundations of Data Science II\n"
        "  term: Fall 2025\n"
        "  first_week_start: 2025-09-22\n"
        + (f"extensions:\n{listed}" if listed else "")
        + "website:\n"
        "  theme: {use: default, config: {rebuild_tailwind: false}}\n"
        "  content_directory: content\n"
        "  build_directory: _build\n"
    )
    (project / "content").mkdir(parents=True, exist_ok=True)
    return project


_GREET = {
    "extension.py": '''\
        from automata.extensions import Extension

        def greet(project, name: str = "world"):
            """Greet someone, from the course."""
            print(f"Hello, {name}, from {project.config.course.name}!")

        def fail(project):
            """Fail with an automata error."""
            from automata.exceptions import Error
            raise Error("It didn't work.")

        extension = Extension(
            name="greet", hooks={}, commands={"greet": greet, "fail": fail}
        )
        ''',
}


def _invoke(project: Path, *args: str):
    app, problem = app_for_directory(project)
    assert problem is None
    return runner.invoke(app, list(args))


# Python commands ======================================================================


def test_an_extension_adds_a_command(tmp_path):
    project = _project(tmp_path, {"greet": _GREET})

    result = _invoke(project, "greet", "--name", "Justin")

    assert result.exit_code == 0, result.output
    assert "Hello, Justin, from DSC 40B!" in result.output


def test_extension_commands_are_listed_in_the_help(tmp_path):
    project = _project(tmp_path, {"greet": _GREET})

    result = _invoke(project, "--help")

    assert "Extensions" in result.output
    assert "greet" in result.output
    assert "Greet someone, from the course." in result.output
    assert "build" in result.output  # the built-in commands are still there


def test_project_is_not_a_command_line_option(tmp_path):
    project = _project(tmp_path, {"greet": _GREET})

    result = _invoke(project, "greet", "--help")

    assert "--name" in result.output
    assert "--project" not in result.output


def test_errors_from_extension_commands_are_reported_without_a_traceback(tmp_path):
    project = _project(tmp_path, {"greet": _GREET})

    result = _invoke(project, "fail")

    assert result.exit_code == 1
    assert "Error: It didn't work." in result.output


# script commands ======================================================================


# (scripts write straight to the terminal, so their output is read with capfd)


def test_a_directory_extension_adds_script_commands(tmp_path, capfd):
    project = _project(
        tmp_path, {"tools": {"commands/count": "echo counting:\n", "README": "x"}}
    )

    result = _invoke(project, "count", "a", "b c", "--week", "3")

    assert result.exit_code == 0, result.output
    assert "counting: a b c --week 3" in capfd.readouterr().out


def test_script_commands_run_in_the_project_directory(tmp_path, capfd):
    project = _project(tmp_path, {"tools": {"commands/where": "pwd -P\n"}})

    _invoke(project, "where")

    assert str(project.resolve()) in capfd.readouterr().out


def test_a_script_command_exits_with_its_status(tmp_path):
    project = _project(tmp_path, {"tools": {"commands/nope": "exit 3\n"}})

    assert _invoke(project, "nope").exit_code == 3


def test_a_script_commands_first_comment_is_its_help(tmp_path):
    project = _project(
        tmp_path,
        {"tools": {"commands/count": "# Count the homeworks.\necho counting\n"}},
    )

    assert "Count the homeworks." in _invoke(project, "--help").output


# problems =============================================================================


@pytest.mark.parametrize("name", ["build", "pipeline"])
def test_an_extension_command_cannot_replace_a_built_in_one(tmp_path, name):
    project = _project(tmp_path, {"tools": {f"commands/{name}": "echo mine\n"}})

    app, problem = app_for_directory(project)

    assert problem is not None
    assert f'Extension "tools" adds a command named "{name}"' in str(problem)
    # the built-in commands still work
    assert runner.invoke(app, ["build", "--help"]).exit_code == 0


def test_two_extensions_cannot_add_the_same_command(tmp_path):
    project = _project(
        tmp_path,
        {"one": {"commands/go": "echo 1\n"}, "two": {"commands/go": "echo 2\n"}},
    )

    _, problem = app_for_directory(project)

    assert 'Extensions "one" and "two" both add a command named "go"' in str(problem)


def test_a_broken_project_still_has_the_built_in_commands(tmp_path):
    project = _project(tmp_path, {})
    (project / "automata.yaml").write_text("course: {}\n")

    app, problem = app_for_directory(project)

    assert problem is not None
    assert runner.invoke(app, ["check", "--help"]).exit_code == 0


def test_outside_a_project_there_are_only_the_built_in_commands(tmp_path):
    app, problem = app_for_directory(tmp_path)

    assert problem is not None  # (no automata.yaml)
    assert runner.invoke(app, ["build", "--help"]).exit_code == 0


@pytest.mark.parametrize(
    "argv, command",
    [
        (["greet", "--name", "x"], "greet"),
        (["--help"], None),
        ([], None),
        (["pipeline", "clean"], "pipeline"),
    ],
)
def test_the_requested_command_is_the_first_argument_not_an_option(argv, command):
    assert requested_command(argv) == command


def test_an_unknown_command_in_a_broken_project_reports_the_problem(tmp_path, capsys):
    # the command may be an extension's that couldn't be loaded
    from automata.cli import main

    project = _project(tmp_path, {})
    (project / "automata.yaml").write_text("course: {}\n")

    with pytest.raises(SystemExit) as excinfo:
        main(["greet"], cwd=project)

    assert excinfo.value.code == 1
    assert 'missing required key "website"' in capsys.readouterr().err


# command groups =======================================================================

_GRADES = {
    "extension.py": '''\
        from automata.extensions import Extension

        def upload(project, file: str):
            """Upload the grades."""
            print(f"Uploading {file} for {project.config.course.name}.")

        def sync_all():
            """Sync every assignment."""
            print("Syncing all.")

        def roster():
            print("The roster.")

        extension = Extension(
            name="grades",
            hooks={},
            commands={
                "grades": {
                    "__doc__": "Work with grades.",
                    "upload": upload,
                    "sync": {"all": sync_all},
                },
                "people": {"roster": roster},
            },
        )
        ''',
}


def test_an_extension_adds_a_command_group(tmp_path):
    project = _project(tmp_path, {"grades": _GRADES})

    result = _invoke(project, "grades", "upload", "hw1.csv")

    assert result.exit_code == 0, result.output
    assert "Uploading hw1.csv for DSC 40B." in result.output


def test_command_groups_nest(tmp_path):
    project = _project(tmp_path, {"grades": _GRADES})

    result = _invoke(project, "grades", "sync", "all")

    assert result.exit_code == 0, result.output
    assert "Syncing all." in result.output


def test_a_command_groups_help_lists_its_commands(tmp_path):
    project = _project(tmp_path, {"grades": _GRADES})

    result = _invoke(project, "grades", "--help")

    assert "Work with grades." in result.output
    assert "upload" in result.output and "Upload the grades." in result.output
    assert "sync" in result.output


def test_command_groups_are_listed_with_the_extension_commands(tmp_path):
    project = _project(tmp_path, {"grades": _GRADES})

    output = _invoke(project, "--help").output

    extensions = output[output.index("Extensions") :]
    assert "grades" in extensions and "Work with grades." in extensions
    # without a __doc__, a group's help names its extension
    assert 'Commands from extension "grades".' in extensions


def test_a_directory_extension_adds_a_command_group(tmp_path, capfd):
    project = _project(
        tmp_path,
        {"tools": {"commands/grades/upload": "# Upload them.\necho uploading\n"}},
    )

    result = _invoke(project, "grades", "upload", "hw1.csv")

    assert result.exit_code == 0, result.output
    assert "uploading hw1.csv" in capfd.readouterr().out
    assert "Upload them." in _invoke(project, "grades", "--help").output


@pytest.mark.parametrize(
    "commands, message",
    [
        (
            '{"grades": {"Upload": upload}}',
            'Extension "bad" adds a command named "grades Upload"',
        ),
        ('{"grades": {}}', 'Extension "bad" adds an empty command group "grades"'),
        (
            '{"build": {"upload": upload}}',
            'Extension "bad" adds a command named "build"',
        ),
    ],
    ids=["bad name", "empty group", "built-in name"],
)
def test_bad_command_groups_are_errors(tmp_path, commands, message):
    extension = (
        "from automata.extensions import Extension\n\n"
        "def upload():\n    pass\n\n"
        f'extension = Extension(name="bad", hooks={{}}, commands={commands})\n'
    )
    project = _project(tmp_path, {"bad": {"extension.py": extension}})

    _, problem = app_for_directory(project)

    assert problem is not None
    assert message in str(problem)


# loading the project once =============================================================


def test_commands_reuse_the_project_loaded_at_startup(tmp_path):
    from automata.cli import main

    # importing extension.py (which loading the project does) leaves a mark
    counting = (
        "import pathlib\n"
        "from automata.extensions import Extension\n\n"
        'marks = pathlib.Path(__file__).parent / "marks"\n'
        'marks.write_text(marks.read_text() + "x" if marks.exists() else "x")\n'
        'extension = Extension(name="counting", hooks={})\n'
    )
    project = _project(tmp_path, {"counting": {"extension.py": counting}})

    with pytest.raises(SystemExit) as excinfo:
        main(["check"], cwd=project)

    assert excinfo.value.code == 0
    assert (project / "extensions" / "counting" / "marks").read_text() == "x"
