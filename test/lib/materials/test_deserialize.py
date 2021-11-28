import json
import datetime
import pathlib

import automata.materials.lib


def test_serialize_deserialize_universe_roundtrip():
    # given
    collection = automata.materials.lib.Collection(
        publication_schema=automata.materials.lib.PublicationSchema(
            required_artifacts=["foo", "bar"]
        ),
        publications={},
    )

    collection.publications["01-intro"] = automata.materials.lib.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
            "released": datetime.date(2020, 2, 28),
        },
        artifacts={"homework": automata.materials.lib.PublishedArtifact("foo/bar")},
    )

    original = automata.materials.lib.Universe({"homeworks": collection})

    # when
    s = automata.materials.lib.serialize(original)
    result = automata.materials.lib.deserialize(s)

    # then
    assert original == result


def test_serialize_deserialize_built_publication_roundtrip():
    # given
    publication = automata.materials.lib.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
            "released": datetime.date(2020, 2, 28),
        },
        artifacts={
            "homework": automata.materials.lib.BuiltArtifact(
                workdir=None, path="foo/bar"
            )
        },
    )

    # when
    s = automata.materials.lib.serialize(publication)
    result = automata.materials.lib.deserialize(s)

    # then
    assert publication == result


# misc.
# --------------------------------------------------------------------------------------


def test_collection_as_dict():
    # given
    collection = automata.materials.lib.Collection(
        publication_schema=automata.materials.lib.PublicationSchema(
            required_artifacts=["foo", "bar"]
        ),
        publications={},
    )

    collection.publications["01-intro"] = automata.materials.lib.Publication(
        metadata={"name": "testing"},
        artifacts={
            "homework": automata.materials.lib.UnbuiltArtifact(
                workdir=None, path="homework.pdf", recipe="make", release_time=None
            ),
        },
    )

    # when
    d = collection._deep_asdict()

    # then
    assert d["publication_schema"]["required_artifacts"] == ["foo", "bar"]
    assert (
        d["publications"]["01-intro"]["artifacts"]["homework"]["path"] == "homework.pdf"
    )
