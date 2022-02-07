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
        "metadata": {"due": "2022-01-01"},
    }

    # when
    publication = DiscoveredPublication(None, dct)

    # then
    assert publication.metadata["due"] == "2022-01-01"


def test_create_publication_from_dict_creates_artifacts():
    # given
    dct = {
        "artifacts": {
            "homework.pdf": {"recipe": "touch homework.pdf"},
        },
        "metadata": {"due": "2022-01-01"},
    }

    # when
    publication = DiscoveredPublication(None, dct)

    # then
    assert publication['homework.pdf'].recipe == "touch homework.pdf"


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
    assert publication.metadata["due"] == datetime.date(2022, 1, 1)


def test_publication_acts_like_mapping():
    dct = {
        "artifacts": {
            "homework.pdf": {"recipe": "make"},
            "solution.pdf": {"recipe": "make solution"}
        },
        "metadata": {
            "due": "2021-01-01"
        }
    }

    # when
    publication = DiscoveredPublication(None, dct)

    # then
    assert publication["homework.pdf"].recipe == "make"
    assert publication["solution.pdf"].recipe == "make solution"
    assert len(publication) == 2


# artifacts
# =========
