"""Tests for Automata.check()."""

from datetime import datetime
from pathlib import Path
from textwrap import dedent

from automata import Automata, Problem

_JAN_15 = datetime(2025, 1, 15, 12, 0)


def _write_project(project: Path, website_extra: str = "", top_extra: str = "") -> Path:
    """A valid project with one collection, hw, and a home page."""
    project.mkdir(parents=True)
    (project / "automata.yaml").write_text(
        top_extra
        + dedent("""\
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            website:
              theme:
                use: default
                config: {short_title: T, long_title: Test, rebuild_tailwind: false}
              content_directory: content
              build_directory: _build
        """)
        + website_extra
    )
    (project / "content").mkdir()
    (project / "content" / "index.md").write_text("# Home\n\n${ vars | length }")
    _write_collection(project / "hw")
    return project


def _write_collection(directory: Path, collection_yaml: str | None = None) -> None:
    (directory / "01").mkdir(parents=True)
    (directory / "collection.yaml").write_text(
        collection_yaml or "publication_schema:\n  required_artifacts: [hw.txt]\n"
    )
    (directory / "01" / "publication.yaml").write_text(
        "artifacts:\n  hw.txt: {release_time: 2025-01-01 00:00:00}\n"
    )
    (directory / "01" / "hw.txt").write_text("hw")


def _messages(problems, area):
    return [p.message for p in problems if p.area == area]


def test_a_valid_project_has_no_problems(tmp_path):
    project = _write_project(tmp_path / "project")

    assert Automata(project).check(current_time=_JAN_15) == []


def test_problems_in_each_collection_are_all_reported(tmp_path):
    project = _write_project(tmp_path / "project")
    bad = "publication_schema:\n  required_artifacts: [hw.txt]\n  is_orderd: true\n"
    _write_collection(project / "labs", bad)
    _write_collection(project / "zlabs", bad)

    problems = Automata(project).check(current_time=_JAN_15)

    assert _messages(problems, "materials") == [
        f"{project / 'labs' / 'collection.yaml'}:3: publication_schema.is_orderd: "
        'Dictionary contains unexpected extra key "is_orderd".',
        f"{project / 'zlabs' / 'collection.yaml'}:3: publication_schema.is_orderd: "
        'Dictionary contains unexpected extra key "is_orderd".',
    ]


def test_a_released_artifact_without_its_file_is_a_problem(tmp_path):
    project = _write_project(tmp_path / "project")
    (project / "hw" / "01" / "hw.txt").unlink()

    problems = Automata(project).check(current_time=_JAN_15)

    assert _messages(problems, "materials") == [
        f"Artifact hw/01/hw.txt has no recipe, and its file "
        f"{project / 'hw' / '01' / 'hw.txt'} does not exist."
    ]


def test_an_unreleased_artifact_without_its_file_is_not_a_problem(tmp_path):
    # its file may not have been written yet
    project = _write_project(tmp_path / "project")
    (project / "hw" / "01" / "hw.txt").unlink()

    problems = Automata(project).check(current_time=datetime(2024, 12, 1))

    assert problems == []


def test_problems_in_each_page_are_all_reported(tmp_path):
    project = _write_project(tmp_path / "project")
    content = project / "content"
    (content / "a.md").write_text("---\nvars: [1, 2]\n---\n# A\n")
    (content / "b.md").write_text("# B\n\n{% if %}\n")

    problems = Automata(project).check(current_time=_JAN_15)

    messages = _messages(problems, "pages")
    assert len(messages) == 2
    assert (
        messages[0] == f"{content / 'a.md'}:2: vars: Expected a dict, but got a list."
    )
    assert messages[1].startswith(f"{content / 'b.md'}:3: ")


def test_a_template_syntax_error_in_an_extension_is_a_problem(tmp_path):
    project = _write_project(
        tmp_path / "project", top_extra="extensions: [extensions/broken]\n"
    )
    templates = project / "extensions" / "broken" / "templates"
    templates.mkdir(parents=True)
    (templates / "bad.html").write_text("<p>\n{% if %}\n</p>\n")

    problems = Automata(project).check(current_time=_JAN_15)

    messages = _messages(problems, "templates")
    assert len(messages) == 1
    assert messages[0].startswith("template bad.html, line 2: ")


def test_invalid_element_config_is_a_problem_even_if_no_page_uses_it(tmp_path):
    project = _write_project(
        tmp_path / "project",
        website_extra="  elements:\n    button:\n      label: Go\n",
    )

    problems = Automata(project).check(current_time=_JAN_15)

    assert _messages(problems, "elements") == [
        f"{project / 'automata.yaml'}:13: website.elements.button.url: "
        'Dictionary is missing required key "url".'
    ]


def test_an_unknown_element_is_a_problem(tmp_path):
    project = _write_project(
        tmp_path / "project",
        website_extra="  elements:\n    buton:\n      label: Go\n",
    )

    problems = Automata(project).check(current_time=_JAN_15)

    messages = _messages(problems, "elements")
    assert len(messages) == 1
    assert messages[0].startswith(
        "website.elements configures unknown element(s): buton."
    )


def test_an_unknown_publish_strategy_is_a_problem(tmp_path):
    project = _write_project(
        tmp_path / "project", top_extra="publish:\n  site:\n    strategy: ftp\n"
    )

    problems = Automata(project).check(current_time=_JAN_15)

    assert _messages(problems, "publish") == [
        "publish.site: Unknown publish strategy: 'ftp'. Available: gh-pages, git, rsync"
    ]


def test_check_builds_nothing_and_runs_no_recipes(tmp_path):
    project = _write_project(tmp_path / "project")
    (project / "hw" / "01" / "publication.yaml").write_text(
        "artifacts:\n  hw.txt:\n    recipe: touch ran.txt && touch hw.txt\n"
    )

    Automata(project).check(current_time=_JAN_15)

    assert not (project / "hw" / "01" / "ran.txt").exists()
    assert not (project / "_build").exists()


def test_a_problem_as_a_dict_is_json_ready():
    assert Problem("pages", "a.md:1: oops").to_dict() == {
        "area": "pages",
        "message": "a.md:1: oops",
    }
