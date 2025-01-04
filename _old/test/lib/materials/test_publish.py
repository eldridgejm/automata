import pathlib
import shutil
from textwrap import dedent

from pytest import fixture

import automata.lib.materials

EXAMPLES_ROOT = pathlib.Path(__file__).parent.parent.parent / "examples"
EXAMPLE_1_DIRECTORY = EXAMPLES_ROOT / "example_1"


@fixture
def example_1(tmpdir):
    path = pathlib.Path(tmpdir) / "example_1"
    shutil.copytree(EXAMPLE_1_DIRECTORY, path)
    return path


@fixture
def outdir(tmpdir):
    outdir = pathlib.Path(tmpdir) / "out"
    outdir.mkdir()
    return outdir

@fixture
def example_course(example_course_factory, tmpdir):
    default_collection_yaml = dedent("""
        publication_schema:
            required_artifacts:
                - homework.pdf

            optional_artifacts:
                - template.zip

            metadata_schema:
                required_keys:
                  name:
                      type: string
                  date:
                      type: datetime

            is_ordered: true
    """)

    default_publication_yaml = dedent("""
        artifacts:
            homework.pdf:
                recipe: touch homework.pdf
        metadata:
            name: Homework
            date: 2021-10-05 23:59:00
    """)

    return example_course_factory(tmpdir, default_collection_yaml, default_publication_yaml)


def test_publish(example_1, outdir):
    # given
    discovered = automata.lib.materials.discover(example_1)
    builts = automata.lib.materials.build(discovered)

    # when
    published = automata.lib.materials.publish(builts, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert not (outdir / "homeworks" / "02-python" / "solution.pdf").exists()

    assert (
        "homework.pdf"
        in published.collections["homeworks"].publications["01-intro"].artifacts
    )


def test_artifact_not_copied_if_not_released(example_1, outdir):
    # given
    discovered = automata.lib.materials.discover(example_1)
    built = automata.lib.materials.build(discovered)
    publication = built.collections["homeworks"].publications["02-python"]

    # when
    published = automata.lib.materials.publish(built, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert not (outdir / "homeworks" / "02-python" / "solution.pdf").exists()

    assert "solution.pdf" not in (publication.artifacts)


def test_capable_of_publishing_entire_directories(example_course, outdir):
    collection_yaml = dedent("""
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
    """)

    publication_yaml = dedent("""
        artifacts:
            problems/:
                recipe: mkdir problems && touch problems/one.pdf && touch problems/two.pdf
        metadata:
            name: Homework
            date: 2021-10-05 23:59:00
        """)

    example_course.create_collection('homeworks', collection_yaml)
    example_course.create_publication('homeworks', '01-testing', publication_yaml)

    discovered = automata.lib.materials.discover(example_course.path)
    built = automata.lib.materials.build(discovered)
    published = automata.lib.materials.publish(built, outdir)

    assert (outdir / 'homeworks' / '01-testing' / 'problems').is_dir()
    assert (outdir / 'homeworks' / '01-testing' / 'problems' / 'one.pdf').is_file()
    assert (outdir / 'homeworks' / '01-testing' / 'problems' / 'two.pdf').is_file()

