import datetime
from textwrap import dedent

from pytest import raises

from automata.core import discover, DiscoveryError, MalformedFileError

# we've got some fancy formatting below, so turn off formatter
# fmt: off

def test_finds_collections(example):
    # given
    example.create_collection('homeworks')
    example.create_collection('labs')

    # when
    universe = discover(example.root)

    # then
    assert universe.collections.keys() == {"homeworks", "default", "labs"}


def test_finds_publications(example):
    # given
    homeworks = example.create_collection("homeworks")
    homeworks.create_publication("01-intro")
    homeworks.create_publication("02-python")
    homeworks.create_publication("03-something")

    # when
    universe = discover(example.root)

    # then
    assert universe.collections["homeworks"].publications.keys() == {
        "01-intro",
        "02-python",
        "03-something",
    }


def test_finds_singleton_publications_and_places_them_in_default_collection(example):
    """a "singleton" is a publication that does not exist in a collection"""
    # given
    example.create_singleton_publication("foo")

    # when
    universe = discover(example.root)

    # then
    assert universe.collections["default"].publications.keys() == {
        "foo",
    }


def test_reads_publication_metadata(example):
    # given
    homeworks = example.create_collection("homeworks", collection_yaml=dedent("""
        publication_spec:
            required_artifacts: []
            metadata_schema:
                extra_keys_schema:
                    type: any
    """))

    publication_yaml = """
        metadata:
            foo: testing
            bar: 3

        artifacts: {}
    """
    homeworks.create_publication("01-intro", publication_yaml)

    # when
    universe = discover(example.root)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["foo"]
        == "testing"
    )


def test_loads_artifacts(example):
    # given
    homeworks = example.create_collection("homeworks", collection_yaml=dedent("""
        publication_spec:
            required_artifacts: []
            optional_artifacts:
                - solution.pdf
    """))
    publication_yaml=dedent("""
        metadata: {}
        artifacts:
            solution.pdf:
                recipe: touch solution.pdf
    """)
    pub01 = homeworks.create_publication("01-intro", publication_yaml=publication_yaml)

    # when
    universe = discover(example.root)

    # then
    assert (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
        .recipe
        == "touch solution.pdf"
    )


def test_loads_dates_as_dates_in_metadata(example):
    # given
    homeworks = example.create_collection("homeworks", collection_yaml=dedent("""
        publication_spec:
            metadata_schema:
                required_keys:
                    due:
                        type: datetime
                    released:
                        type: date
            required_artifacts: []
            optional_artifacts:
                - solution.pdf
    """))

    pub01 = homeworks.create_publication("01-intro", publication_yaml=dedent("""
        metadata:
            due: 2022-02-22T23:59:00
            released: 2022-02-22
        artifacts:
            solution.pdf:
                recipe: touch solution.pdf
    """))

    # when
    universe = discover(example.root)

    # then
    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["due"],
        datetime.datetime,
    )

    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["released"],
        datetime.date,
    )


def test_reads_ready(example):
    # given
    homeworks = example.create_collection("homeworks", collection_yaml=dedent("""
        publication_spec:
            required_artifacts: []
            optional_artifacts:
                - solution.pdf
    """))

    pub01 = homeworks.create_publication("01-intro", publication_yaml=dedent("""
        artifacts:
            solution.pdf:
                recipe: touch solution.pdf
                ready: false
    """))

    # when
    universe = discover(example.root)

    # then
    assert (
        not universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
        .ready
    )


def test_validates_collection_schema(example):
    # given
    homeworks = example.create_collection("homeworks", collection_yaml=dedent("""
        kdjsadkjas
    """))

    pub01 = homeworks.create_publication("01-intro")

    # when run on a malformed collection.yaml
    with raises(MalformedFileError):
        discover(example.root)


def test_validates_publication_schema(example):
    # given
    homeworks = example.create_collection("homeworks")
    pub01 = homeworks.create_publication("01-intro", publication_yaml=dedent("""
        asdksajdjla
    """))

    with raises(MalformedFileError):
        discover(example.root)


def test_validates_publication_metadata_schema(example):
    # given
    homeworks = example.create_collection("homeworks", collection_yaml=dedent("""
        publication_spec:
            metadata_schema:
                required_keys:
                    due:
                        type: datetime
            required_artifacts: []
    """))

    pub01 = homeworks.create_publication("01-intro", publication_yaml=dedent("""
        metadata:
            due: testing
        artifacts: {}
    """))

    # when
    with raises(MalformedFileError):
        discover(example.root)


def test_raises_when_nested_collections_discovered(example):
    # given
    example.create_collection("homeworks")
    foo_path = (example.root / "homeworks" / "foo")
    foo_path.mkdir()
    with (foo_path / "collection.yaml").open('w') as fileobj:
        fileobj.write(': (')

    # when
    with raises(DiscoveryError):
        discover(example.root)


def test_uses_relative_paths_as_keys(example):
    foobar = example.create_collection("foo/bar")
    foobar.create_publication("baz/bazinga")

    # when
    universe = discover(example.root)

    # then
    assert "foo/bar" in universe.collections
    assert "baz/bazinga" in universe.collections["foo/bar"].publications


def test_skip_directories(example):
    # when
    universe = discover(example.root, skip_directories={"textbook"})

    # then
    assert "textbook" not in universe.collections["default"].publications


def test_key_used_for_path_if_path_not_provided(example):
    # given
    homeworks = example.create_collection("homeworks", collection_yaml=dedent("""
        publication_spec:
            required_artifacts: []
            optional_artifacts:
                - solution.pdf
    """))

    pub01 = homeworks.create_publication("01-intro", publication_yaml=dedent("""
        artifacts:
            solution.pdf:
                recipe: touch solution.pdf
                ready: false
    """))

    # when
    universe = discover(example.root)

    # then
    assert (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
        .path
        == "solution.pdf"
    )


def test_sorts_publications_lexicographically_if_collection_is_ordered(example):
    homeworks = example.create_collection("homeworks", collection_yaml=dedent("""
        publication_spec:
            is_ordered: true
            required_artifacts: []
    """))
    names = [
        "01-intro",
        "02-python",
        "03-not_ready",
        "04-normal_publication",
        "10-late_homework",
        "11-later_homework",
    ]
    for name in names:
        homeworks.create_publication(name)

    # when
    universe = discover(example.root)

    # then
    assert list(universe.collections["homeworks"].publications) == [
        "01-intro",
        "02-python",
        "03-not_ready",
        "04-normal_publication",
        "10-late_homework",
        "11-later_homework",
    ]


def test_with_dates_relating_to_previous(example):
    # given
    lectures = example.create_collection("lectures", collection_yaml=dedent("""
        publication_spec:
            required_artifacts: []
            metadata_schema:
                required_keys:
                    date:
                        type: datetime
            is_ordered: true
    """))

    pub01 = lectures.create_publication("01-intro", publication_yaml=dedent("""
        metadata:
            date: 2021-01-05 23:00:00

        artifacts: {}
    """))

    pub02 = lectures.create_publication("02-foo", publication_yaml=dedent("""
        metadata:
            date: first tuesday or thursday after ${previous.metadata.date}

        artifacts: {}
    """))

    pub03 = lectures.create_publication("03-bar", publication_yaml=dedent("""
        metadata:
            date: first tuesday or thursday after ${previous.metadata.date}

        artifacts: {}
    """))

    pub04 = lectures.create_publication("04-baz", publication_yaml=dedent("""
        metadata:
            date: 2021-01-19 23:00:00

        artifacts: {}
    """))

    pub05 = lectures.create_publication("05-conclusion", publication_yaml=dedent("""
        metadata:
            date: first tuesday or thursday after ${previous.metadata.date}

        artifacts: {}
    """))

    # when
    universe = discover(example.root)

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


def test_interpolates_vars(example):
    # given
    homeworks = example.create_collection("homeworks", collection_yaml=dedent("""
        publication_spec:
            required_artifacts: []
            metadata_schema:
                required_keys:
                    name:
                        type: string
                    due:
                        type: date
    """))

    pub01 = homeworks.create_publication("01-intro", publication_yaml=dedent("""
        artifacts: {}
        metadata:
            name: ${ vars.course.name }
            due: ${ vars.course.start_date }
    """))

    # given
    vars = {
        "course": {
            "name": "my favorite homework",
            "start_date": datetime.date(2020, 1, 1),
        }
    }

    # when
    universe = discover(example.root, vars=vars)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["name"]
        == "my favorite homework"
    )
    assert universe.collections["homeworks"].publications["01-intro"].metadata[
        "due"
    ] == datetime.date(2020, 1, 1)
