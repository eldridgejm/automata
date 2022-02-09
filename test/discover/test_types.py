import datetime
import pathlib
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
    collection = DiscoveredCollection(pathlib.Path.cwd(), dct)

    # then
    assert collection.ordered


def test_collection_acts_like_mapping():
    dct = {
        "publication_spec": {
            "required_artifacts": ["foo.pdf", "bar.txt"],
            "metadata_schema": {"required_keys": {"due": {"type": "string"}}},
        },
        "ordered": True,
    }

    # when
    collection = DiscoveredCollection(pathlib.Path.cwd(), dct)
    collection["foo"] = 1
    collection["bar"] = 2
    collection["baz"] = 3

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
            "homework.pdf": {
                "path": None,
                "release_time": None,
                "ready": True,
                "missing_ok": True,
                "recipe": "touch homework.pdf"
            },
        },
        "metadata": {"due": "2022-01-01"},
        "release_time": "2022-01-01",
        "ready": True
    }

    # when
    publication = DiscoveredPublication(pathlib.Path.cwd(), dct)

    # then
    assert publication.metadata["due"] == "2022-01-01"


def test_create_publication_from_dict_creates_artifacts():
    # given
    dct = {
        "artifacts": {
            "homework.pdf": {
                "path": None,
                "release_time": None,
                "ready": True,
                "missing_ok": True,
                "recipe": "touch homework.pdf"
            },
        },
        "metadata": {"due": "2022-01-01"},
        "release_time": "2022-01-01",
        "ready": True
    }

    # when
    publication = DiscoveredPublication(pathlib.Path.cwd(), dct)

    # then
    assert publication['homework.pdf'].recipe == "touch homework.pdf"


def test_publication_acts_like_mapping():
    dct = {
        "artifacts": {
            "homework.pdf": {
                "path": None,
                "release_time": None,
                "ready": True,
                "missing_ok": True,
                "recipe": "make"
            },
            "solution.pdf": {
                "path": None,
                "release_time": None,
                "ready": True,
                "missing_ok": True,
                "recipe": "make solution"
            }
        },
        "metadata": {
            "due": "2021-01-01"
        },
        "release_time": "2022-01-01",
        "ready": True
    }

    # when
    publication = DiscoveredPublication(pathlib.Path.cwd(), dct)

    # then
    assert publication["homework.pdf"].recipe == "make"
    assert publication["solution.pdf"].recipe == "make solution"
    assert len(publication) == 2


# artifacts
# =========
