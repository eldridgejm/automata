from automata.cli import cli

import shutil
import json
import pathlib
from textwrap import dedent

from pytest import fixture, mark


@fixture
def make_input_directory(tmpdir):
    def make_input_directory(example):
        input_path = pathlib.Path(tmpdir) / "input"
        example_path = pathlib.Path(__file__).parent / example
        shutil.copytree(example_path, input_path)
        return input_path

    return make_input_directory


@fixture
def output_directory(tmpdir):
    output_path = pathlib.Path(tmpdir) / "output"
    output_path.mkdir()
    return output_path


def test_publish_materials_simple_example(make_input_directory, output_directory):
    # given
    input_directory = make_input_directory("examples/example_1")

    # when
    cli(
        [
            "materials",
            "publish",
            "--input-directory",
            str(input_directory),
            str(output_directory),
        ]
    )

    # then
    assert (output_directory / "homeworks" / "01-intro" / "homework.pdf").exists()


def test_publish_materials_with_example_using_external_variables(
    make_input_directory, output_directory
):
    # given
    input_directory = make_input_directory("examples/example_9")

    contents = dedent(
        """
        course:
            name: this is a test
            start_date: 2020-01-01
    """
    )
    with (input_directory / "myvars.yaml").open("w") as fileobj:
        fileobj.write(contents)

    # when
    cli(
        [
            "materials",
            "publish",
            str(output_directory),
            "--input-directory",
            str(input_directory),
            "--ignore-release-time",
            "--vars",
            f"{input_directory}/myvars.yaml",
        ]
    )

    # then
    assert (output_directory / "homeworks" / "01-intro").exists()


def test_publish_materials_creates_materials_json(
    make_input_directory, output_directory
):
    input_directory = make_input_directory("examples/example_1")

    # when
    cli(
        [
            "materials",
            "publish",
            "--input-directory",
            str(input_directory),
            str(output_directory),
        ]
    )

    # then
    assert (output_directory / "materials.json").exists()
    released = json.load((output_directory / "materials.json").open())

    # assert that an unreleased artifact is still present in materials.json
    assert (
        "homework.pdf"
        in released["collections"]["homeworks"]["publications"]["02-python"][
            "artifacts"
        ]
    )


def test_publish_materials_then_build_coursepage_with_example(
    make_input_directory, output_directory
):
    # given
    input_directory = make_input_directory("examples/example_class")

    # when
    cli(
        [
            "materials",
            "publish",
            str(output_directory / "materials"),
            "--input-directory",
            str(input_directory),
            "--skip-directories",
            "template",
        ]
    )
    cli(
        [
            "coursepage",
            "build",
            str(output_directory),
            "--input-directory",
            str(input_directory / "website"),
            "--materials",
            str(output_directory / "materials"),
            "--vars",
            str(input_directory / "course.yaml"),
        ]
    )

    # then
    assert (output_directory / "index.html").exists()


@mark.slow
def test_coursepage_init(output_directory):

    # when
    cli(["coursepage", "init", str(output_directory / "there")])

    assert (output_directory / "there" / "config.yaml").exists()
