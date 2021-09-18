from automata.cli import cli

import shutil
import json
import pathlib
from textwrap import dedent

from pytest import fixture


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


def test_build_materials_simple_example(make_input_directory, output_directory):
    # given
    input_directory = make_input_directory("example_1")

    # when
    cli(["build-materials", str(input_directory), str(output_directory)])

    # then
    assert (output_directory / "homeworks" / "01-intro" / "homework.pdf").exists()


def test_build_materials_with_example_using_external_variables(
    make_input_directory, output_directory
):
    # given
    input_directory = make_input_directory("example_9")

    contents = dedent(
        """
        name: this is a test
        start_date: 2020-01-01
    """
    )
    with (input_directory / "myvars.yaml").open("w") as fileobj:
        fileobj.write(contents)

    # when
    cli(
        [
            "build-materials",
            str(input_directory),
            str(output_directory),
            "--ignore-release-time",
            "--vars",
            f"course:{input_directory}/myvars.yaml",
        ]
    )

    # then
    assert (output_directory / "homeworks" / "01-intro").exists()


def test_build_materials_creates_materials_json(
    make_input_directory, output_directory
):
    input_directory = make_input_directory("example_1")

    # when
    cli(["build-materials", str(input_directory), str(output_directory)])

    # then
    assert (output_directory / "materials.json").exists()
    released = json.load((output_directory / "materials.json").open())

    # assert that an unreleased artifact is still present in materials.json
    assert 'homework.pdf' in released['collections']['homeworks']['publications']['02-python']['artifacts']



def test_build_materials_then_build_coursepage_with_example(
    make_input_directory, output_directory
):
    # given
    input_directory = make_input_directory("example_class")

    # when
    cli(
        [
            "build-materials",
            str(input_directory),
            str(output_directory / "materials"),
            "--skip-directories",
            "template",
        ]
    )
    cli(
        [
            "build-coursepage",
            "--published",
            str(output_directory / "materials"),
            str(input_directory / "website"),
            str(output_directory),
            "--context",
            str(input_directory / "course.yaml"),
        ]
    )

    # then
    assert (output_directory / "index.html").exists()
