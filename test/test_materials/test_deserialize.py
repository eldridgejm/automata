import datetime
import pathlib

import automata.lib


def test_serialize_deserialize_universe_roundtrip():
    # given
    collection = automata.lib.Collection(
        publication_schema=automata.lib.PublicationSchema(
            required_artifacts=["foo", "bar"]
        ),
        publications={},
    )

    collection.publications["01-intro"] = automata.lib.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
            "released": datetime.date(2020, 2, 28),
        },
        artifacts={
            "homework": automata.lib.ExportedArtifact("foo/bar")
        },
    )

    original = automata.lib.Universe({"homeworks": collection})

    # when
    s = automata.lib.serialize(original)
    result = automata.lib.deserialize(s)

    # then
    assert original == result


def test_serialize_deserialize_built_publication_roundtrip():
    # given
    publication = automata.lib.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
            "released": datetime.date(2020, 2, 28),
        },
        artifacts={
            "homework": automata.lib.BuiltArtifact(
                workdir=pathlib.Path.cwd(), path="foo/bar"
            )
        },
    )

    # when
    s = automata.lib.serialize(publication)
    result = automata.lib.deserialize(s)

    # then
    assert publication == result


# misc.
# --------------------------------------------------------------------------------------


def test_collection_as_dict():
    # given
    collection = automata.lib.Collection(
        publication_schema=automata.lib.PublicationSchema(
            required_artifacts=["foo", "bar"]
        ),
        publications={},
    )

    collection.publications["01-intro"] = automata.lib.Publication(
        metadata={"name": "testing"},
        artifacts={
            "homework": automata.lib.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                path="homework.pdf",
                recipe="make",
                release_time=None,
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
