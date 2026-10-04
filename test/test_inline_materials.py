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
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
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
        "course:\n"
        "  name: Test\n"
        "  title: Test Course\n"
        "  term: Fall 2025\n"
        "  first_week_start: 2025-01-06\n"
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
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
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
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
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


@pytest.mark.parametrize(
    "materials, expected",
    [
        (
            "{exams: {schema: {required_artifacts: [], metadata_schema: "
            "{required_keys: {date: {type: date}}}}, "
            "publications: {midterm: {metadata: {date: someday}, artifacts: {}}}}}",
            ":1: materials.exams.publications.midterm.metadata.date: ",
        ),
        (
            "{exams: {schema: {required_artifact: []}, publications: {}}}",
            ":1: materials.exams.schema.required_artifact: Dictionary contains "
            'unexpected extra key "required_artifact".',
        ),
    ],
)
def test_inline_materials_errors_give_the_keypath_in_automata_yaml(
    tmp_path, materials, expected
):
    project = tmp_path / "project"
    project.mkdir()
    config_file = project / "automata.yaml"
    config_file.write_text(
        f"materials: {materials}\n"
        + dedent("""\
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
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

    assert str(excinfo.value).startswith(f"{config_file}{expected}")


def test_an_inline_collection_named_default_is_an_error(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config_file = project / "automata.yaml"
    config_file.write_text(
        "materials:\n"
        "  default:\n"
        "    schema: {required_artifacts: []}\n"
        + dedent("""\
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
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

    assert str(excinfo.value) == (
        f'{config_file}:2: materials.default: The collection name "default" is '
        "reserved for publications that aren't in a collection. Rename it."
    )


@pytest.mark.parametrize("artifacts", ["null", "[hw.pdf]"])
def test_inline_artifacts_of_the_wrong_type_are_a_config_error(tmp_path, artifacts):
    project = tmp_path / "project"
    project.mkdir()
    config_file = project / "automata.yaml"
    config_file.write_text(
        "materials:\n"
        "  hw:\n"
        "    schema: {required_artifacts: []}\n"
        "    publications:\n"
        "      h1:\n"
        f"        artifacts: {artifacts}\n"
        + dedent("""\
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
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

    assert str(excinfo.value).startswith(
        f"{config_file}:6: materials.hw.publications.h1.artifacts: "
    )


# this and previous ====================================================================

# a project's automata.yaml, apart from its materials (and vars)
_REST_OF_CONFIG = dedent("""\
    course:
      name: Test
      title: Test Course
      term: Fall 2025
      first_week_start: 2025-01-06
    website:
      theme:
        use: "default"
        config: {short_title: "T", long_title: "Test"}
      content_directory: "content"
      build_directory: "_build"
""")

_LECTURES = dedent("""\
    lectures:
      schema:
        required_artifacts: [slides.pdf]
        metadata_schema:
          required_keys:
            date: { type: date }
        is_ordered: true
      publications:
        lec01:
          metadata:
            date: 2025-01-07
          artifacts:
            slides.pdf:
              path: lectures/lec01.pdf
              release_time: ${ this.metadata.date } at 08:00:00
        lec02:
          metadata:
            date: first tuesday, thursday after ${ previous.metadata.date }
          artifacts:
            slides.pdf:
              path: lectures/lec02.pdf
              release_time: ${ this.metadata.date } at 08:00:00
""")


def _project(tmp_path, config, files=None):
    """A project in *tmp_path* with automata.yaml *config* (and the rest of the
    configuration), and *files*: a dict of paths to contents."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "automata.yaml").write_text(config + _REST_OF_CONFIG)
    for path, contents in (files or {}).items():
        (project / path).write_text(contents)
    return project


def _indented(text, spaces):
    return "".join(
        " " * spaces + line if line.strip() else line for line in text.splitlines(True)
    )


def test_inline_publications_can_refer_to_the_previous_one(tmp_path):
    project = _project(tmp_path, "materials:\n" + _indented(_LECTURES, 2))

    lectures = Automata(project).discover().collections["lectures"]

    # the first tuesday or thursday after tuesday, january 7
    assert lectures.publications["lec02"].metadata["date"] == datetime.date(2025, 1, 9)


def test_inline_publications_can_refer_to_themselves(tmp_path):
    project = _project(tmp_path, "materials:\n" + _indented(_LECTURES, 2))

    lectures = Automata(project).discover().collections["lectures"]

    slides = lectures.publications["lec02"].artifacts["slides.pdf"]
    assert slides.release_time == datetime.datetime(2025, 1, 9, 8, 0, 0)


def test_previous_is_undefined_in_an_unordered_inline_collection(tmp_path):
    lectures = _LECTURES.replace("    is_ordered: true\n", "")
    project = _project(tmp_path, "materials:\n" + _indented(lectures, 2))

    with pytest.raises(Error) as excinfo:
        Automata(project).discover()

    message = str(excinfo.value)
    assert "'previous' is undefined" in message
    assert "is_ordered: true" in message
    assert "!template" not in message


def test_an_undefined_name_in_an_inline_publication_gives_its_line(tmp_path):
    lectures = _LECTURES.replace(
        "${ previous.metadata.date }", "${ prevous.metadata.date }"
    )
    project = _project(tmp_path, "materials:\n" + _indented(lectures, 2))

    with pytest.raises(Error) as excinfo:
        Automata(project).discover()

    assert str(excinfo.value).startswith(
        f"{project / 'automata.yaml'}:19: "
        "materials.lectures.publications.lec02.metadata.date: "
        "'prevous' is undefined"
    )


def test_the_configuration_cannot_refer_into_the_materials(tmp_path):
    config = (
        "vars:\n"
        "  first_lecture: ${ materials.lectures.publications.lec01.metadata.date }\n"
        "materials:\n" + _indented(_LECTURES, 2)
    )
    project = _project(tmp_path, config)

    with pytest.raises(Error) as excinfo:
        Automata(project)

    message = str(excinfo.value)
    assert message.startswith(f"{project / 'automata.yaml'}:2: vars.first_lecture: ")
    assert "the materials are read after the rest of automata.yaml" in message


def test_inline_materials_can_be_included_from_another_file(tmp_path):
    project = _project(
        tmp_path,
        'materials:\n  __include__: "materials.yaml"\n',
        files={"materials.yaml": _LECTURES},
    )

    lectures = Automata(project).discover().collections["lectures"]

    assert lectures.publications["lec02"].metadata["date"] == datetime.date(2025, 1, 9)


def test_an_inline_collection_can_be_included_from_another_file(tmp_path):
    project = _project(
        tmp_path,
        'materials:\n  lectures:\n    __include__: "lectures.yaml"\n',
        files={"lectures.yaml": _LECTURES.split("\n", 1)[1].replace("\n  ", "\n")[2:]},
    )

    lectures = Automata(project).discover().collections["lectures"]

    assert lectures.publications["lec02"].metadata["date"] == datetime.date(2025, 1, 9)


def test_errors_in_included_inline_materials_give_the_included_file(tmp_path):
    lectures = _LECTURES.replace(
        "${ previous.metadata.date }", "${ prevous.metadata.date }"
    )
    project = _project(
        tmp_path,
        'materials:\n  __include__: "materials.yaml"\n',
        files={"materials.yaml": lectures},
    )

    with pytest.raises(Error) as excinfo:
        Automata(project).discover()

    assert str(excinfo.value).startswith(
        f"{project / 'materials.yaml'}:18: "
        "materials.lectures.publications.lec02.metadata.date: "
    )


@pytest.mark.parametrize(
    "materials, expected",
    [
        ("[lectures]", "materials must be a mapping"),
        ('{__include__: "${ vars.file }"}', "__include__ must be a path"),
        ('{__include__: "missing.yaml"}', "not found"),
    ],
)
def test_malformed_materials_are_a_config_error(tmp_path, materials, expected):
    project = _project(tmp_path, f"materials: {materials}\n")

    with pytest.raises(Error, match=expected):
        Automata(project)
