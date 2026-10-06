"""Tests for the example projects in examples/, which the documentation shows.

These check what the quickstart says about the examples, so that the two
can't disagree.
"""

import datetime
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from automata import Automata

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"
DOCS = ROOT / "doc" / "source"


def _copy(name, tmp_path):
    """A copy of the example *name*, without anything an earlier build left."""
    project = tmp_path / name
    shutil.copytree(EXAMPLES / name, project, ignore=shutil.ignore_patterns("_build"))
    return project


def _at(*args):
    return datetime.datetime(*args)


@pytest.fixture
def fake_latexmk(tmp_path, monkeypatch):
    """A latexmk, first on the PATH, that writes a stand-in PDF for the .tex
    file it's given, and logs each call; returns the log."""
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    log = tmp_path / "latexmk.log"
    script = bin_directory / "latexmk"
    script.write_text(
        "#!/bin/sh\n"
        'for arg; do tex="$arg"; done\n'
        f'echo "$PWD/$tex" >> "{log}"\n'
        'echo "%PDF" > "${tex%.tex}.pdf"\n'
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_directory}:{os.environ['PATH']}")
    return log


# every example ========================================================================


@pytest.mark.parametrize("name", ["simple-course", "latex-course", "full-course"])
def test_the_example_has_no_problems(name, tmp_path):
    project = Automata(_copy(name, tmp_path))

    assert project.check(current_time=_at(2026, 10, 1, 12)) == []


# simple-course ========================================================================


def test_simple_course_lectures_are_dated_from_the_first(tmp_path):
    lectures = (
        Automata(_copy("simple-course", tmp_path)).discover().collections["lectures"]
    )

    dates = {key: p.metadata["date"] for key, p in lectures.publications.items()}
    assert dates == {
        "01-introduction": datetime.date(2026, 9, 22),
        "02-linear-regression": datetime.date(2026, 9, 24),
        "03-gradient-descent": datetime.date(2026, 9, 29),
    }


def test_simple_course_slides_are_released_on_the_morning_of_the_lecture(tmp_path):
    lectures = (
        Automata(_copy("simple-course", tmp_path)).discover().collections["lectures"]
    )

    slides = lectures.publications["02-linear-regression"].artifacts["slides.pptx"]
    assert slides.release_time == _at(2026, 9, 24, 8)


def test_simple_course_site_has_only_the_released_slides(tmp_path):
    project = _copy("simple-course", tmp_path)

    Automata(project).build(current_time=_at(2026, 9, 25, 12))

    index = (project / "_build" / "index.html").read_text()
    assert "materials/lectures/01-introduction/slides.pptx" in index
    assert "materials/lectures/02-linear-regression/slides.pptx" in index
    assert "03-gradient-descent" not in index
    lectures = project / "_build" / "materials" / "lectures"
    assert not (lectures / "03-gradient-descent").exists()


def test_simple_course_syllabus_fills_in_the_course(tmp_path):
    project = _copy("simple-course", tmp_path)

    Automata(project).build(current_time=_at(2026, 9, 25, 12))

    syllabus = (project / "_build" / "syllabus.html").read_text()
    assert "DSC 101: Introduction to Data Science" in syllabus
    assert "Fall 2026" in syllabus
    assert "${" not in syllabus
    assert "<h2>Grading</h2>" in syllabus
    # the lectures section links to the schedule, on the home page
    assert '<a href="./index.html">schedule</a>' in syllabus


def _git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _with_github(name, tmp_path):
    """A copy of the example *name* in a git repository whose origin is a
    local bare repository, standing in for the course's repository on GitHub.
    Returns the project and the remote."""
    remote = tmp_path / "remote.git"
    _git("init", "--bare", "--quiet", str(remote), cwd=tmp_path)
    project = _copy(name, tmp_path)
    _git("init", "--quiet", cwd=project)
    _git("remote", "add", "origin", str(remote), cwd=project)
    _git("config", "user.name", "Instructor", cwd=project)
    _git("config", "user.email", "instructor@example.com", cwd=project)
    return project, remote


def test_simple_course_publishes_to_github_pages(tmp_path):
    project, remote = _with_github("simple-course", tmp_path)

    published = Automata(project).publish(current_time=_at(2026, 9, 25, 12))

    assert list(published) == ["github"]
    assert "index.html" in [c.path for c in published["github"].changes]
    files = _git("ls-tree", "-r", "--name-only", "gh-pages", cwd=remote).split()
    assert "index.html" in files
    assert "materials/lectures/01-introduction/slides.pptx" in files


# latex-course =========================================================================


def test_latex_course_dates(tmp_path):
    universe = Automata(_copy("latex-course", tmp_path)).discover()
    lectures = universe.collections["lectures"].publications
    homeworks = universe.collections["homeworks"].publications

    assert lectures["02-linear-regression"].metadata["date"] == datetime.date(
        2026, 9, 24
    )
    assert homeworks["01"].metadata["due"] == _at(2026, 9, 29, 23, 59)
    assert homeworks["02"].metadata["due"] == _at(2026, 10, 6, 23, 59)
    solution = homeworks["02"].artifacts["solution.pdf"]
    assert solution.release_time == _at(2026, 10, 7)


def test_latex_course_builds_only_what_is_released(tmp_path, fake_latexmk):
    project = _copy("latex-course", tmp_path)

    Automata(project).build(current_time=_at(2026, 10, 1, 12))

    materials = project / "_build" / "materials"
    built = sorted(
        str(path.relative_to(materials)) for path in materials.rglob("*.pdf")
    )
    assert built == [
        "homeworks/01/homework.pdf",
        "homeworks/01/solution.pdf",
        "homeworks/02/homework.pdf",
        "lectures/01-introduction/slides.pdf",
        "lectures/02-linear-regression/slides.pdf",
    ]
    # homework 2's solution isn't even compiled before it is released
    compiled = fake_latexmk.read_text().splitlines()
    assert str(project / "homeworks" / "02" / "solution.tex") not in compiled


def test_latex_course_site_shows_the_homework_due_dates(tmp_path, fake_latexmk):
    project = _copy("latex-course", tmp_path)

    Automata(project).build(current_time=_at(2026, 10, 1, 12))

    index = (project / "_build" / "index.html").read_text()
    assert "Due Tuesday, Oct. 6 at 11:59 PM" in index


def test_latex_course_publishes_to_github_pages(tmp_path, fake_latexmk):
    project, remote = _with_github("latex-course", tmp_path)

    published = Automata(project).publish(current_time=_at(2026, 10, 1, 12))

    assert list(published) == ["github"]
    files = _git("ls-tree", "-r", "--name-only", "gh-pages", cwd=remote).split()
    assert "materials/homeworks/01/solution.pdf" in files
    assert "materials/homeworks/02/solution.pdf" not in files


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("latexmk") is None, reason="needs latexmk")
def test_latex_course_builds_with_latex(tmp_path, monkeypatch):
    # without the user's latexmk configuration (which may, e.g., set an output
    # directory), as on a fresh installation
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    project = _copy("latex-course", tmp_path)

    Automata(project).build(current_time=_at(2026, 10, 1, 12))

    slides = project / "_build" / "materials" / "lectures" / "01-introduction"
    assert (slides / "slides.pdf").read_bytes().startswith(b"%PDF")


# the documentation's snippets =========================================================


def _literalincludes():
    """Each literalinclude in the documentation: its .rst file, the file it
    includes, and its options."""
    for rst in DOCS.rglob("*.rst"):
        text = rst.read_text()
        for match in re.finditer(
            r"^\.\. literalinclude:: (\S+)\n((?:[ \t]+:[\w-]+:.*\n)*)", text, re.M
        ):
            options = dict(re.findall(r"^[ \t]+:([\w-]+):[ \t]*(.*)$", match[2], re.M))
            yield rst, (rst.parent / match[1]).resolve(), options


def test_the_quickstart_shows_the_examples():
    included = {path for _, path, _ in _literalincludes()}

    assert any(EXAMPLES / "simple-course" in path.parents for path in included)
    assert any(EXAMPLES / "latex-course" in path.parents for path in included)


@pytest.mark.parametrize(
    "rst, path, options",
    list(_literalincludes()),
    ids=lambda value: value.name if isinstance(value, Path) else "",
)
def test_documentation_snippets_exist(rst, path, options):
    assert path.is_file(), f"{rst.name} includes {path}, which doesn't exist"
    text = path.read_text()
    for option in ("start-at", "start-after", "end-at", "end-before"):
        if option in options:
            assert options[option] in text, (
                f'{rst.name} includes {path.name} {option} "{options[option]}", '
                "which isn't in it"
            )


@pytest.mark.parametrize("name", ["simple-course", "latex-course"])
def test_lectures_are_numbered_from_the_previous_one(name, tmp_path):
    lectures = Automata(_copy(name, tmp_path)).discover().collections["lectures"]

    numbers = [p.metadata["number"] for p in lectures.publications.values()]
    assert numbers == list(range(1, len(numbers) + 1))
    for key, publication in list(lectures.publications.items())[1:]:
        raw = (
            EXAMPLES / name / "automata.yaml"
            if name == "simple-course"
            else EXAMPLES / name / "lectures" / key / "publication.yaml"
        ).read_text()
        assert "number: ${ previous.metadata.number + 1 }" in raw
