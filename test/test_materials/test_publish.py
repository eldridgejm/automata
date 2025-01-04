import pathlib
from textwrap import dedent

from pytest import fixture

import automata.materials

@fixture
def outdir(tmpdir):
    outdir = pathlib.Path(tmpdir) / "out"
    outdir.mkdir()
    return outdir


def test_publish(default_example_course, outdir):
    # given
    discovered = automata.materials.discover(default_example_course.path)
    builts = automata.materials.build(discovered)

    # when
    published = automata.materials.publish(builts, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert not (outdir / "homeworks" / "02-python" / "solution.pdf").exists()

    assert (
        "homework.pdf"
        in published.collections["homeworks"].publications["01-intro"].artifacts
    )


def test_artifact_not_copied_if_not_released(default_example_course, outdir):
    # given
    discovered = automata.materials.discover(default_example_course.path)
    built = automata.materials.build(discovered)
    publication = built.collections["homeworks"].publications["02-python"]

    # when
    published = automata.materials.publish(built, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert not (outdir / "homeworks" / "02-python" / "solution.pdf").exists()

    assert "solution.pdf" not in (publication.artifacts)


def test_capable_of_publishing_entire_directories(temporary_course, outdir):
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
                recipe: mkdir problems && touch problems/one.pdf && touch problems/two.pdf
        metadata:
            name: Homework
            date: 2021-10-05 23:59:00
        """
    )

    temporary_course.create_collection("homeworks", collection_yaml)
    temporary_course.create_publication("homeworks", "01-testing", publication_yaml)

    discovered = automata.materials.discover(temporary_course.path)
    built = automata.materials.build(discovered)
    published = automata.materials.publish(built, outdir)

    assert (outdir / "homeworks" / "01-testing" / "problems").is_dir()
    assert (outdir / "homeworks" / "01-testing" / "problems" / "one.pdf").is_file()
    assert (outdir / "homeworks" / "01-testing" / "problems" / "two.pdf").is_file()
