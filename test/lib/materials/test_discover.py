import datetime
import pathlib
from textwrap import dedent

from pytest import raises, fixture, mark

from automata.lib.materials import discover, UnbuiltArtifact, DiscoveryError


# good example; simple
EXAMPLES_ROOT = pathlib.Path(__file__).parent.parent.parent / 'examples'

EXAMPLE_1_DIRECTORY = EXAMPLES_ROOT / "example_1"

# bad: bad collection file
EXAMPLE_2_DIRECTORY = EXAMPLES_ROOT / "example_2"

# bad: mismatched publication metadata
EXAMPLE_3_DIRECTORY = EXAMPLES_ROOT / "example_3"

# bad: nested collections
EXAMPLE_4_DIRECTORY = EXAMPLES_ROOT / "example_4"

# good: relative paths as keys
EXAMPLE_5_DIRECTORY = EXAMPLES_ROOT / "example_5"

# bad: publication metadata doesn't match schema
EXAMPLE_6_DIRECTORY = EXAMPLES_ROOT / "example_6"

# good: ordered collection
EXAMPLE_7_DIRECTORY = EXAMPLES_ROOT / "example_7"

# good: ordered collection with dates relating to previous
EXAMPLE_8_DIRECTORY = EXAMPLES_ROOT / "example_8"

# good: collection with context variables
EXAMPLE_9_DIRECTORY = EXAMPLES_ROOT / "example_9"


def test_finds_collections():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    # then
    assert universe.collections.keys() == {"homeworks", "default"}


def test_finds_publications():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    # then
    assert universe.collections["homeworks"].publications.keys() == {
        "01-intro",
        "02-python",
        "03-not_ready",
        "04-normal_publication",
    }


def test_finds_singleton_publications_and_places_them_in_default_collection():
    # a "singleton" is a publication that does not exist in a collection
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    # then
    assert universe.collections["default"].publications.keys() == {
        "textbook",
    }


def test_reads_publication_metadata():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["name"]
        == "Homework 01"
    )


def test_loads_artifacts():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
        .recipe
        == "touch solution.pdf"
    )


def test_loads_dates_as_dates():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    # then
    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["due"],
        datetime.datetime,
    )

    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["released"],
        datetime.date,
    )


def test_reads_ready():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        not universe.collections["homeworks"]
        .publications["03-not_ready"]
        .artifacts["homework.pdf"]
        .ready
    )


def test_validates_collection_schema():
    # when run on a malformed collection.yaml
    with raises(DiscoveryError):
        discover(EXAMPLE_2_DIRECTORY)


def test_validates_publication_schema():
    with raises(DiscoveryError):
        discover(EXAMPLE_3_DIRECTORY)


def test_validates_publication_metadata_schema():
    with raises(DiscoveryError):
        discover(EXAMPLE_6_DIRECTORY)


def test_raises_when_nested_collections_discovered():
    with raises(DiscoveryError):
        discover(EXAMPLE_4_DIRECTORY)


def test_uses_relative_paths_as_keys():
    # when
    universe = discover(EXAMPLE_5_DIRECTORY)

    # then
    assert "foo/bar" in universe.collections
    assert "baz/bazinga" in universe.collections["foo/bar"].publications


def test_skip_directories():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY, skip_directories={"textbook"})

    # then
    assert "textbook" not in universe.collections["default"].publications


def test_key_used_for_file_if_file_not_provided():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    # then
    assert (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["homework.pdf"]
        .file
        == "homework.pdf"
    )


def test_sorts_publications_lexicographically_if_collection_is_ordered():
    # when
    universe = discover(EXAMPLE_7_DIRECTORY)

    # then
    assert list(universe.collections["homeworks"].publications) == [
        "01-intro",
        "02-python",
        "03-not_ready",
        "04-normal_publication",
        "10-late_homework",
        "11-later_homework",
    ]


def test_with_dates_relating_to_previous():
    # when
    universe = discover(EXAMPLE_8_DIRECTORY)

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


def test_interpolates_external_variables():
    # given
    external_variables = {
        "course": {
            "name": "my favorite homework",
            "start_date": datetime.date(2020, 1, 1),
        }
    }

    # when
    universe = discover(EXAMPLE_9_DIRECTORY, external_variables=external_variables)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["name"]
        == "my favorite homework"
    )
    assert universe.collections["homeworks"].publications["01-intro"].metadata[
        "due"
    ] == datetime.date(2020, 1, 1)
