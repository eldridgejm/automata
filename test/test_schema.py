import pathlib
import datetime

from pytest import raises

import automata.materials


EXAMPLE_1_DIRECTORY = pathlib.Path(__file__).parent / "example_1"


# validate_publication
# -----------------------------------------------------------------------------


def test_validate_publication_checks_required_artifacts():
    # given
    publication = automata.materials.Publication(
        metadata={
            "name": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
        },
    )

    schema = automata.materials.PublicationSchema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=False,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when / then
    with raises(automata.materials.ValidationError):
        automata.materials.validate(publication, against=schema)


def test_validate_publication_does_not_allow_extra_artifacts(write_file):
    # given
    publication = automata.materials.Publication(
        metadata={
            "name": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
            "extra": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = automata.materials.PublicationSchema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=False,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when / then
    with raises(automata.materials.ValidationError):
        automata.materials.validate(publication, against=schema)


def test_validate_publication_allow_unspecified_artifacts(write_file):
    # given
    publication = automata.materials.Publication(
        metadata={
            "name": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
            "extra": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = automata.materials.PublicationSchema(
        required_artifacts=[],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when
    automata.materials.validate(publication, against=schema)


def test_validate_publication_validates_metadata(write_file):
    # given
    publication = automata.materials.Publication(
        metadata={
            "thisisclearlywrong": "Homework 01",
            "due": datetime.datetime(2020, 9, 4, 23, 59, 00),
            "released": datetime.date(2020, 9, 1),
        },
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = automata.materials.PublicationSchema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when
    with raises(automata.materials.ValidationError):
        automata.materials.validate(publication, against=schema)


def test_validate_publication_requires_metadata_if_schema_provided(write_file):
    # given
    publication = automata.materials.Publication(
        metadata={},
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = automata.materials.PublicationSchema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema={
            "name": {"type": "string"},
            "due": {"type": "datetime"},
            "released": {"type": "date"},
        },
    )

    # when
    with raises(automata.materials.ValidationError):
        automata.materials.validate(publication, against=schema)


def test_validate_publication_doesnt_require_metadata_if_schema_not_provided(
    write_file,
):
    # given
    publication = automata.materials.Publication(
        metadata={},
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = automata.materials.PublicationSchema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema={},
    )

    # when
    automata.materials.validate(publication, against=schema)


def test_validate_publication_accepts_metadata_if_schema_not_provided(write_file):
    # given
    publication = automata.materials.Publication(
        metadata={"name": "foo"},
        artifacts={
            "homework": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./homework.pdf",
                recipe="make homework",
            ),
            "solution": automata.materials.UnbuiltArtifact(
                workdir=pathlib.Path.cwd(),
                file="./solution.pdf",
                recipe="make solution",
            ),
        },
    )

    schema = automata.materials.PublicationSchema(
        required_artifacts=["homework", "solution"],
        optional_artifacts=[],
        allow_unspecified_artifacts=True,
        metadata_schema=None,
    )

    # when
    automata.materials.validate(publication, against=schema)

    # then
    assert publication.metadata["name"] == "foo"
