import json
import datetime
import pathlib

import automata.materials


def test_serialize_deserialize_universe_roundtrip():
    # given
    collection = automata.materials.Collection(
        schema=automata.materials.PublicationSchema(required_artifacts=["foo", "bar"]),
        publications={},
    )

    collection.publications["01-intro"] = automata.materials.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
            "released": datetime.date(2020, 2, 28),
        },
        artifacts={"homework": automata.materials.PublishedArtifact("foo/bar")},
    )

    original = automata.materials.Universe({"homeworks": collection})

    # when
    s = automata.materials.serialize(original)
    result = automata.materials.deserialize(s)

    # then
    assert original == result


def test_serialize_deserialize_built_publication_roundtrip():
    # given
    publication = automata.materials.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
            "released": datetime.date(2020, 2, 28),
        },
        artifacts={
            "homework": automata.materials.BuiltArtifact(workdir=None, file="foo/bar")
        },
    )

    # when
    s = automata.materials.serialize(publication)
    result = automata.materials.deserialize(s)

    # then
    assert publication == result


# misc.
# --------------------------------------------------------------------------------------


def test_collection_as_dict():
    # given
    collection = automata.materials.Collection(
        schema=automata.materials.PublicationSchema(required_artifacts=["foo", "bar"]),
        publications={},
    )

    collection.publications["01-intro"] = automata.materials.Publication(
        metadata={"name": "testing"},
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
                workdir=None, file="homework.pdf", recipe="make", release_time=None
            ),
        },
    )

    # when
    d = collection._deep_asdict()

    # then
    assert d["schema"]["required_artifacts"] == ["foo", "bar"]
    assert (
        d["publications"]["01-intro"]["artifacts"]["homework"]["file"] == "homework.pdf"
    )
