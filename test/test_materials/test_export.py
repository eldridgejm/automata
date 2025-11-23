import pathlib
from textwrap import dedent

from pytest import fixture, raises

import automata.lib


@fixture
def outdir(tmpdir):
    outdir = pathlib.Path(tmpdir) / "out"
    outdir.mkdir()
    return outdir


def test_export(default_example_course, outdir):
    # given
    discovered = automata.lib.discover(default_example_course.path)
    builts = automata.lib.build(discovered)

    # when
    exported = automata.lib.export(builts, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert not (outdir / "homeworks" / "02-python" / "solution.pdf").exists()

    assert (
        "homework.pdf"
        in exported.collections["homeworks"].publications["01-intro"].artifacts
    )


def test_artifact_not_copied_if_not_released(default_example_course, outdir):
    # given
    discovered = automata.lib.discover(default_example_course.path)
    built = automata.lib.build(discovered)
    publication = built.collections["homeworks"].publications["02-python"]

    # when
    automata.lib.export(built, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert not (outdir / "homeworks" / "02-python" / "solution.pdf").exists()

    assert "solution.pdf" not in (publication.artifacts)


def test_capable_of_exporting_entire_directories(temporary_course, outdir):
    collection_yaml = dedent(
        """
        publication_schema:
            required_artifacts:
                - problems/

            optional_artifacts:
                - template.zip

            metadata_schema:
                required_keys:
                  name:
                      type: string
                  date:
                      type: datetime

            is_ordered: true
    """
    )

    publication_yaml = dedent(
        """
        artifacts:
            problems/:
                recipe: mkdir problems && touch problems/{one,two}.pdf
        metadata:
            name: Homework
            date: 2021-10-05 23:59:00
        """
    )

    temporary_course.create_collection("homeworks", collection_yaml)
    temporary_course.create_publication("homeworks", "01-testing", publication_yaml)

    discovered = automata.lib.discover(temporary_course.path)
    built = automata.lib.build(discovered)
    _ = automata.lib.export(built, outdir)

    assert (outdir / "homeworks" / "01-testing" / "problems").is_dir()
    assert (outdir / "homeworks" / "01-testing" / "problems" / "one.pdf").is_file()
    assert (outdir / "homeworks" / "01-testing" / "problems" / "two.pdf").is_file()


def test_export_raises_when_artifact_not_built(outdir):
    """Test that export() raises ValueError when given an unbuilt artifact."""
    # given: a publication containing an unbuilt artifact
    unbuilt_artifact = automata.lib.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="touch foo.pdf",
    )
    publication = automata.lib.Publication(
        metadata={},
        artifacts={"foo.pdf": unbuilt_artifact},
    )

    # when/then: exporting should raise ValueError
    with raises(ValueError) as exc_info:
        automata.lib.export(publication, outdir)

    assert "Cannot export an unbuilt artifact" in str(exc_info.value)
