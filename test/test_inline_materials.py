"""Tests for inline materials defined in automata.yaml."""

import datetime
from textwrap import dedent

import pytest

from automata import Automata
from automata.exceptions import Error


@pytest.fixture
def project_with_inline_materials(tmp_path):
    """Create a project with materials defined inline in automata.yaml."""
    project = tmp_path / "project"
    project.mkdir()

    (project / "automata.yaml").write_text(
        dedent("""\
            materials:
              homeworks:
                schema:
                  required_artifacts:
                    - homework.pdf
                  metadata_schema:
                    required_keys:
                      name:
                        type: string
                      due:
                        type: date
                publications:
                  hw01:
                    metadata:
                      name: Homework 1
                      due: 2025-01-15
                    artifacts:
                      homework.pdf:
                        path: homeworks/hw01/homework.pdf
                        release_time: 2025-01-10 12:00:00
                  hw02:
                    metadata:
                      name: Homework 2
                      due: 2025-01-22
                    artifacts:
                      homework.pdf:
                        path: homeworks/hw02/homework.pdf
                        release_time: 2025-01-20 12:00:00

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

    # Create the actual artifact files
    (project / "homeworks" / "hw01").mkdir(parents=True)
    (project / "homeworks" / "hw01" / "homework.pdf").write_text("hw1 content")
    (project / "homeworks" / "hw02").mkdir(parents=True)
    (project / "homeworks" / "hw02" / "homework.pdf").write_text("hw2 content")

    # Create minimal content directory
    content = project / "content"
    content.mkdir()
    (content / "index.md").write_text("# Home")

    return project


# discovery ============================================================================


def test_inline_materials_are_discovered(project_with_inline_materials):
    project = Automata(project_with_inline_materials)
    universe = project.discover()
    assert "homeworks" in universe.collections
    assert "hw01" in universe.collections["homeworks"].publications
    assert "hw02" in universe.collections["homeworks"].publications


def test_inline_materials_have_metadata(project_with_inline_materials):
    project = Automata(project_with_inline_materials)
    universe = project.discover()
    hw01 = universe.collections["homeworks"].publications["hw01"]
    assert hw01.metadata["name"] == "Homework 1"
    assert hw01.metadata["due"] == datetime.date(2025, 1, 15)


def test_inline_materials_have_release_times(project_with_inline_materials):
    project = Automata(project_with_inline_materials)
    universe = project.discover()
    hw01 = universe.collections["homeworks"].publications["hw01"]
    artifact = hw01.artifacts["homework.pdf"]
    assert artifact.release_time == datetime.datetime(2025, 1, 10, 12, 0, 0)


def test_inline_materials_have_no_recipe(project_with_inline_materials):
    project = Automata(project_with_inline_materials)
    universe = project.discover()
    hw01 = universe.collections["homeworks"].publications["hw01"]
    artifact = hw01.artifacts["homework.pdf"]
    assert artifact.recipe is None


def test_inline_materials_release_time_filtering(project_with_inline_materials):
    """Materials with future release times are filtered during build."""
    project = Automata(project_with_inline_materials)
    universe = project.discover()

    # Build at a time when hw01 is released but hw02 is not
    built = project.build_materials(
        universe, current_time=datetime.datetime(2025, 1, 15)
    )

    hw01 = built.collections["homeworks"].publications["hw01"]
    hw02 = built.collections["homeworks"].publications["hw02"]

    # hw01's artifact should be present (released on Jan 10)
    assert "homework.pdf" in hw01.artifacts
    # hw02's artifact should be filtered (releases on Jan 20)
    assert "homework.pdf" not in hw02.artifacts


def test_inline_materials_fire_discover_hooks(project_with_inline_materials):
    # given
    project = Automata(project_with_inline_materials)
    collections, publications = [], []

    @project.hooks.on_discover_collection.register()
    def on_collection(args):
        collections.append((args.path.name, args.key))

    @project.hooks.on_discover_publication.register()
    def on_publication(args):
        publications.append((args.path.name, args.key))

    # when
    project.discover()

    # then
    assert collections == [("automata.yaml", "homeworks")]
    assert publications == [
        ("automata.yaml", "hw01"),
        ("automata.yaml", "hw02"),
    ]


def test_inline_publications_keep_their_order(project_with_inline_materials):
    universe = Automata(project_with_inline_materials).discover()

    assert list(universe.collections["homeworks"].publications) == ["hw01", "hw02"]


# variables ============================================================================


def test_inline_materials_can_use_vars(tmp_path):
    """Inline materials can reference vars from automata.yaml."""
    project = tmp_path / "project"
    project.mkdir()

    yaml = (
        "vars:\n"
        "  base_due: 2025-01-15\n"
        "\n"
        "materials:\n"
        "  homeworks:\n"
        "    schema:\n"
        "      required_artifacts: []\n"
        "      metadata_schema:\n"
        "        required_keys:\n"
        "          due:\n"
        "            type: date\n"
        "    publications:\n"
        "      hw01:\n"
        "        metadata:\n"
        "          due: ${ vars.base_due }\n"
        "        artifacts: {}\n"
        "\n"
        "website:\n"
        "  theme:\n"
        '    use: "default"\n'
        "    config:\n"
        '      short_title: "Test"\n'
        '      long_title: "Test Course"\n'
        '  content_directory: "content"\n'
        '  build_directory: "_build"\n'
    )
    (project / "automata.yaml").write_text(yaml)

    content = project / "content"
    content.mkdir()
    (content / "index.md").write_text("# Home")

    a = Automata(project)
    universe = a.discover()
    hw01 = universe.collections["homeworks"].publications["hw01"]
    assert hw01.metadata["due"] == datetime.date(2025, 1, 15)


def test_inline_materials_cannot_have_recipes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "automata.yaml").write_text(
        dedent("""\
            materials:
              homeworks:
                schema:
                  required_artifacts: [homework.pdf]
                publications:
                  hw01:
                    artifacts:
                      homework.pdf:
                        recipe: make homework.pdf

            website:
              theme:
                use: "default"
                config: {short_title: "T", long_title: "Test"}
              content_directory: "content"
              build_directory: "_build"
        """)
    )

    with pytest.raises(Error) as excinfo:
        Automata(project).discover()

    message = str(excinfo.value)
    assert "recipe" in message
    assert "homework.pdf" in message


@pytest.mark.parametrize(
    "materials, expected",
    [
        ("{exams: [1]}", "materials.exams must be a mapping"),
        (
            "{exams: {shema: {}, publications: {}}}",
            'materials.exams has unknown key "shema"',
        ),
        (
            "{exams: {publications: [1]}}",
            "materials.exams.publications must be a mapping",
        ),
        (
            "{exams: {publications: {midterm: [1]}}}",
            "materials.exams.publications.midterm must be a mapping",
        ),
    ],
)
def test_malformed_inline_materials_are_reported(tmp_path, materials, expected):
    project = tmp_path / "project"
    project.mkdir()
    (project / "automata.yaml").write_text(
        f"materials: {materials}\n"
        + dedent("""\
            website:
              theme:
                use: "default"
                config: {short_title: "T", long_title: "Test"}
              content_directory: "content"
              build_directory: "_build"
        """)
    )

    with pytest.raises(Error) as excinfo:
        Automata(project).discover()

    assert expected in str(excinfo.value)
