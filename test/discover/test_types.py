import datetime
from textwrap import dedent

from ruamel.yaml import YAML

from automata import DiscoveredCollection, DiscoveredPublication

yaml = YAML()


# collections
# ===========


def test_create_collection_from_dict():
    # given
    dct = {
        "publication_spec": {
            "required_artifacts": ["foo.pdf", "bar.txt"],
            "metadata_schema": {"required_keys": {"due": {"type": "string"}}},
        },
        "ordered": True,
    }

    # when
    collection = DiscoveredCollection(None, dct)

    # then
    assert collection.ordered


def test_create_collection_from_file(write_file):
    # given
    path = write_file(
        "collection.yaml",
        dedent(
            """
        # foooo
        publication_spec:
            required_artifacts: ['homework.pdf'] # barrrr

        ordered: true
    """
        ),
    )

    # when
    collection = DiscoveredCollection.from_file(path)

    # then
    assert collection.ordered
    assert collection.publication_spec["required_artifacts"] == ["homework.pdf"]


def test_write_collection_preserves_comments(write_file):
    # given
    path = write_file(
        "collection.yaml",
        dedent(
            """
        # foooo
        publication_spec:
            required_artifacts: {} # barrrr

        ordered: true
    """
        ),
    )

    # when
    collection = DiscoveredCollection.from_file(path)
    collection.write()

    with path.open() as fileobj:
        contents = fileobj.read()

    # then
    assert "# foooo" in contents
    assert "# barrrr" in contents


def test_set_ordered_then_write(write_file):
    # given
    path = write_file(
        "collection.yaml",
        dedent(
            """
        # foooo
        publication_spec:
            required_artifacts: {} # barrrr

        ordered: true
    """
        ),
    )

    # when
    collection = DiscoveredCollection.from_file(path)
    collection.ordered = False
    collection.write()

    with path.open() as fileobj:
        contents_dct = yaml.load(fileobj)

    # then
    assert contents_dct["ordered"] is False


def test_set_required_artifacts_then_write(write_file):
    # given
    path = write_file(
        "collection.yaml",
        dedent(
            """
        # foooo
        publication_spec:
            required_artifacts: [] # barrrr

        ordered: true
    """
        ),
    )

    # when
    collection = DiscoveredCollection.from_file(path)
    collection.publication_spec["required_artifacts"] = ["homework.pdf", "solution.pdf"]
    collection.write()

    with path.open() as fileobj:
        contents_dct = yaml.load(fileobj)

    # then
    assert contents_dct["publication_spec"]["required_artifacts"] == [
        "homework.pdf",
        "solution.pdf",
    ]


def test_set_publication_spec_then_write(write_file):
    # given
    path = write_file(
        "collection.yaml",
        dedent(
            """
        # foooo
        publication_spec:
            required_artifacts: [] # barrrr

        ordered: true
    """
        ),
    )

    # when
    collection = DiscoveredCollection.from_file(path)
    collection.publication_spec = {
        "required_artifacts": ["homework.pdf", "solution.pdf"]
    }
    collection.write()

    with path.open() as fileobj:
        contents_dct = yaml.load(fileobj)

    # then
    assert contents_dct["publication_spec"]["required_artifacts"] == [
        "homework.pdf",
        "solution.pdf",
    ]


def test_collection_acts_like_mapping():
    dct = {
        "publication_spec": {
            "required_artifacts": ["foo.pdf", "bar.txt"],
            "metadata_schema": {"required_keys": {"due": {"type": "string"}}},
        },
        "ordered": True,
    }

    # when
    collection = DiscoveredCollection(None, dct)
    collection._add_child("foo", 1)
    collection._add_child("bar", 2)
    collection._add_child("baz", 3)

    # then
    assert collection["foo"] == 1
    assert collection["bar"] == 2
    assert collection["baz"] == 3
    assert len(collection) == 3


# publications
# ============


def test_create_publication_from_dict():
    # given
    dct = {
        "artifacts": {
            "homework.pdf": {"recipe": "touch homework.pdf"},
        },
        "metadata": {"due": "2022-01-01"}
    }

    # when
    publication = DiscoveredPublication(None, dct)

    # then
    assert publication.metadata["due"] == "2022-01-01"


def test_create_publication_from_file(write_file):
    # given
    path = write_file(
        "publication.yaml",
        dedent(
            """
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
            metadata:
                due: 2022-01-01
        """
        ),
    )

    # when
    publication = DiscoveredPublication.from_file(path)

    # then
    assert publication.metadata['due'] == datetime.date(2022, 1, 1)


def test_write_publication_preserves_comments(write_file):
    # given
    path = write_file(
        "publication.yaml",
        dedent(
            """
            # fooo
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
            metadata:
                due: 2022-01-01
    """
        ),
    )

    # when
    publication = DiscoveredPublication.from_file(path)
    publication.write()

    with path.open() as fileobj:
        contents = fileobj.read()

    # then
    assert "# fooo" in contents


def test_set_metdata_member_then_write(write_file):
    # given
    path = write_file(
        "publication.yaml",
        dedent(
            """
            # fooo
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
            metadata:
                due: 2022-01-01
    """
        ),
    )

    # when
    publication = DiscoveredPublication.from_file(path)
    publication.metadata["due"] = "2022-01-02"
    publication.write()

    with path.open() as fileobj:
        contents_dct = yaml.load(fileobj)

    # then
    assert contents_dct["metadata"]["due"] == "2022-01-02"



def test_set_metadata_then_write(write_file):
    # given
    path = write_file(
        "publication.yaml",
        dedent(
            """
            # fooo
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
            metadata:
                due: 2022-01-01
    """
        ),
    )

    # when
    publication = DiscoveredPublication.from_file(path)
    publication.metadata = {
            "foo": 23
    }
    publication.write()

    with path.open() as fileobj:
        contents_dct = yaml.load(fileobj)

    # then
    assert contents_dct["metadata"] == {"foo": 23}


def test_set_ready_then_write(write_file):
    # given
    path = write_file(
        "publication.yaml",
        dedent(
            """
            # fooo
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
            metadata:
                due: 2022-01-01

            ready: false
    """
        ),
    )

    # when
    publication = DiscoveredPublication.from_file(path)
    publication.ready = True
    publication.write()

    with path.open() as fileobj:
        contents_dct = yaml.load(fileobj)

    # then
    assert contents_dct["ready"] is True


def test_set_release_time_then_write(write_file):
    # given
    path = write_file(
        "publication.yaml",
        dedent(
            """
            # fooo
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
            metadata:
                due: 2022-01-01

            release_time: 2022-01-01
    """
        ),
    )

    # when
    publication = DiscoveredPublication.from_file(path)
    publication.release_time = 55
    publication.write()

    with path.open() as fileobj:
        contents_dct = yaml.load(fileobj)

    # then
    assert contents_dct["release_time"] == 55

def test_publication_acts_like_mapping():
    dct = {
        "publication_spec": {
            "required_artifacts": ["foo.pdf", "bar.txt"],
            "metadata_schema": {"required_keys": {"due": {"type": "string"}}},
        },
        "ordered": True,
    }

    # when
    publication = DiscoveredPublication(None, dct)
    publication._add_child("foo", 1)
    publication._add_child("bar", 2)
    publication._add_child("baz", 3)

    # then
    assert publication["foo"] == 1
    assert publication["bar"] == 2
    assert publication["baz"] == 3
    assert len(publication) == 3


# artifacts
# =========

