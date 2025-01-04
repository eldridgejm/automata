import datetime
import pathlib
from textwrap import dedent

from pytest import raises, fixture, mark

from automata.materials import discover, UnbuiltArtifact, DiscoveryError


def test_finds_collections(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert universe.collections.keys() == {"homeworks", "default"}


def test_finds_publications(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert universe.collections["homeworks"].publications.keys() == {
        "01-intro",
        "02-python",
        "03-not_ready",
        "04-normal_publication",
    }


def test_finds_singleton_publications_and_places_them_in_default_collection(
    temporary_course,
):
    # a "singleton" is a publication that does not exist in a collection
    # given
    temporary_course.create_publication(
        "",  # there's no collection
        "textbook",
        """
            metadata:
                name: Textbook

            artifacts:
                textbook.pdf:
                    recipe: touch textbook.pdf
        """,
    )

    # when
    universe = discover(temporary_course.path)

    # then
    assert universe.collections["default"].publications.keys() == {
        "textbook",
    }


def test_reads_publication_metadata(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["name"]
        == "Homework 01"
    )


def test_loads_artifacts(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
        .recipe
        == "touch solution.pdf"
    )


def test_loads_dates_as_dates(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["due"],
        datetime.datetime,
    )

    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["released"],
        datetime.date,
    )


def test_reads_ready(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert (
        not universe.collections["homeworks"]
        .publications["03-not_ready"]
        .artifacts["homework.pdf"]
        .ready
    )


def test_validates_collection_schema(temporary_course):
    # given a collection with a malformed collection.yaml
    temporary_course.create_collection(
        "homeworks",
        """
            foo: bar
            schema: 42
        """,
    )

    # when run on a malformed collection.yaml
    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_validates_publication_schema(temporary_course):
    # given a publication with a malformed publication.yaml
    temporary_course.create_publication(
        "",
        "textbook",
        # missing metadata
        """
            name: hello
            artifacts:
                homework:
                    path: ./build/nothing.pdf
                    recipe: make
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_validates_publication_metadata_schema(temporary_course):

    # given a publication with metadata that doesn't match the schema in the
    # collection.yaml
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework
                    - solution

                optional_artifacts:
                    - template

                metadata_schema:
                    required_keys:
                        name:
                            type: string
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
            metadata:
                what: ok

            artifacts:
                homework:
                    path: ./build/nothing.pdf
                    recipe: make
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_raises_when_nested_collections_discovered(temporary_course):

    # given a collection "bar" nested in a collection "foo"
    BASIC_COLLECTION_YAML = """
        publication_schema:
            required_artifacts: []

            metadata_schema:
                name:
                    type: string
                author:
                    type: string
    """

    temporary_course.create_collection("foo", BASIC_COLLECTION_YAML)
    temporary_course.create_collection("foo/bar", BASIC_COLLECTION_YAML)

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_uses_relative_paths_as_keys(temporary_course):
    # given a collection with publications/collections more than one level deep in the
    # directory hierarchy
    temporary_course.create_collection(
        "foo/bar",
        """
            publication_schema:
                required_artifacts: ["foo"]
        """,
    )

    temporary_course.create_publication(
        "foo/bar",
        "baz/bazinga",
        """
            artifacts:
                foo:
                    path: filename
                    recipe: ok
        """,
    )

    # when
    universe = discover(temporary_course.path)

    # then
    assert "foo/bar" in universe.collections
    assert "baz/bazinga" in universe.collections["foo/bar"].publications


def test_skip_directories(default_example_course):
    # when
    universe = discover(default_example_course.path, skip_directories={"textbook"})

    # then
    assert "textbook" not in universe.collections["default"].publications


def test_key_used_for_path_if_path_not_provided(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["homework.pdf"]
        .path
        == "homework.pdf"
    )


def test_sorts_publications_lexicographically_if_collection_is_ordered(
    default_example_course,
):
    # given the default example, with a few more publications with a gap in their
    # numbering
    BASIC_PUBLICATION_YAML = """
        metadata:
            name: "Late Homework"
            due: 2020-09-10 23:59:00
            released: 2020-09-01
        artifacts:
            homework.pdf:
                recipe: touch homework.pdf
            solution.pdf:
                recipe: touch solution.pdf
    """
    publication_names = ["10-late_homework", "11-later_homework"]
    for publication_name in publication_names:
        default_example_course.create_publication(
            "homeworks",
            publication_name,
            BASIC_PUBLICATION_YAML,
        )

    # when
    universe = discover(default_example_course.path)

    # then
    assert list(universe.collections["homeworks"].publications) == [
        "01-intro",
        "02-python",
        "03-not_ready",
        "04-normal_publication",
        "10-late_homework",
        "11-later_homework",
    ]


def test_with_dates_relating_to_previous(temporary_course):
    # given a collection with dates that are relative to the previous publication
    temporary_course.create_collection(
        "lectures",
        """
            publication_schema:
                required_artifacts: []

                optional_artifacts:
                    - template.zip

                metadata_schema:
                    required_keys:
                      name:
                          type: string
                      date:
                          type: datetime

                is_ordered: true
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "01-intro",
        """
            metadata:
                name: Lecture 01
                date: 2021-01-05 23:00:00

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "02-foo",
        """
            metadata:
                name: Lecture 01
                date: first tuesday or thursday after ${previous.metadata.date}

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "03-bar",
        """
            metadata:
                name: Lecture 01
                date: first tuesday or thursday after ${previous.metadata.date}

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "04-baz",
        """
            metadata:
                name: Lecture 01
                date: 2021-01-19 23:00:00

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "05-conclusion",
        """
            metadata:
                name: Lecture 01
                date: first tuesday or thursday after ${previous.metadata.date}

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    # when
    universe = discover(temporary_course.path)

    # then
    publications = universe.collections["lectures"].publications

    assert publications["01-intro"].metadata["date"] == datetime.datetime(
        2021, 1, 5, 23, 0
    )
    assert publications["02-foo"].metadata["date"] == datetime.datetime(
        2021, 1, 7, 23, 0
    )
    assert publications["03-bar"].metadata["date"] == datetime.datetime(
        2021, 1, 12, 23, 0
    )
    # suppose lecture 4 had to be moved; it is manually set in the file
    assert publications["04-baz"].metadata["date"] == datetime.datetime(
        2021, 1, 19, 23, 0
    )
    assert publications["05-conclusion"].metadata["date"] == datetime.datetime(
        2021, 1, 21, 23, 0
    )


def test_interpolates_vars(temporary_course):
    # given
    vars = {
        "course": {
            "name": "my favorite homework",
            "start_date": datetime.date(2020, 1, 1),
        }
    }

    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework.pdf
                    - solution.pdf

                optional_artifacts:
                    - template.zip

                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: date
                        released:
                            type: date

                is_ordered: true
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
            metadata:
                name: ${ vars.course.name }
                due: ${ vars.course.start_date }
                released: 2020-09-01

            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
                solution.pdf:
                    recipe: touch solution.pdf
        """,
    )

    # when
    universe = discover(temporary_course.path, vars=vars)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["name"]
        == "my favorite homework"
    )
    assert universe.collections["homeworks"].publications["01-intro"].metadata[
        "due"
    ] == datetime.date(2020, 1, 1)
