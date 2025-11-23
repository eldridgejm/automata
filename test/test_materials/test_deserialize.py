import datetime
import pathlib

import automata.materials


def test_serialize_deserialize_universe_roundtrip():
    # given
    collection = automata.materials.Collection(
        publication_schema=automata.materials.PublicationSchema(
            required_artifacts=["foo", "bar"]
        ),
        publications={},
    )

    collection.publications["01-intro"] = automata.materials.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
            "released": datetime.date(2020, 2, 28),
        },
        artifacts={"homework": automata.materials.ExportedArtifact("foo/bar")},
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
            "homework": automata.materials.BuiltArtifact(
                workdir=pathlib.Path.cwd(), path="foo/bar"
            )
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
        publication_schema=automata.materials.PublicationSchema(
            required_artifacts=["foo", "bar"]
        ),
        publications={},
    )

    collection.publications["01-intro"] = automata.materials.Publication(
        metadata={"name": "testing"},
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
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


def test_serialize_deserialize_unbuilt_publication_roundtrip():
    """Test publications with UnbuiltArtifacts can be serialized and deserialized."""
    # given
    publication = automata.materials.Publication(
        metadata={
            "name": "testing",
            "due": datetime.datetime(2020, 2, 28, 23, 59, 0),
        },
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                path="homework.pdf",
                recipe="make homework",
                release_time=datetime.datetime(2020, 2, 28, 12, 0, 0),
            )
        },
    )

    # when
    s = automata.materials.serialize(publication)
    result = automata.materials.deserialize(s)

    # then
    assert publication == result
    assert isinstance(result.artifacts["homework"], automata.materials.UnbuiltArtifact)


def test_serialize_deserialize_artifact_directly():
    """Test that artifacts can be serialized and deserialized directly (not wrapped)."""
    # given
    artifact = automata.materials.BuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="homework.pdf",
        returncode=0,
        stdout="build output",
        stderr="",
    )

    # when
    s = automata.materials.serialize(artifact)
    result = automata.materials.deserialize(s)

    # then
    assert artifact == result
    assert isinstance(result, automata.materials.BuiltArtifact)


def test_serialize_deserialize_collection_directly():
    """Test that collections can be serialized and deserialized directly."""
    # given
    collection = automata.materials.Collection(
        publication_schema=automata.materials.PublicationSchema(
            required_artifacts=["homework.pdf"],
        ),
        publications={
            "01-intro": automata.materials.Publication(
                metadata={"name": "Intro"},
                artifacts={
                    "homework.pdf": automata.materials.ExportedArtifact(
                        path="homework.pdf"
                    )
                },
            )
        },
    )

    # when
    s = automata.materials.serialize(collection)
    result = automata.materials.deserialize(s)

    # then
    assert collection == result
    assert isinstance(result, automata.materials.Collection)
