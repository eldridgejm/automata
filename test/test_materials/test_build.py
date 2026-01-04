import datetime
import pathlib
from unittest.mock import Mock

from pytest import raises

import automata.materials


def test_build_artifact_integration(default_example_course):
    # given
    universe = automata.materials.discover(default_example_course.path)
    artifact = (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
    )

    # when
    result = automata.materials.build(artifact)

    # then
    assert (
        default_example_course.path / "homeworks" / "01-intro" / "solution.pdf"
    ).exists()
    assert result.workdir == artifact.workdir
    assert result.path == artifact.path
    assert result.path


def test_build_artifact_when_release_time_is_in_future():
    # given
    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
    )

    proc = Mock()
    proc.returncode = 0
    run = Mock(return_value=proc)
    current_time = datetime.datetime(2020, 1, 1, 0, 0, 0)

    # when
    result = automata.materials.build(artifact, run=run, current_time=current_time)

    # then
    assert result is None
    assert not run.called


def test_build_artifact_when_not_ready():
    # given
    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
        ready=False,
    )

    proc = Mock()
    proc.returncode = 0
    run = Mock(return_value=proc)
    current_time = datetime.datetime(2020, 3, 1, 0, 0, 0)

    # when
    result = automata.materials.build(artifact, run=run, current_time=current_time)

    # then
    assert result is None
    assert not run.called


def test_build_artifact_when_release_time_is_in_future_ignore_release_time():
    # given
    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
    )

    proc = Mock()
    proc.returncode = 0
    run = Mock(return_value=proc)
    current_time = datetime.datetime(2020, 1, 1, 0, 0, 0)
    exists = Mock(return_value=True)

    # when
    result = automata.materials.build(
        artifact,
        run=run,
        current_time=current_time,
        exists=exists,
        ignore_release_time=True,
    )

    # then
    assert result.path
    assert run.called


def test_build_artifact_when_recipe_is_none():
    # given
    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(), path="foo.pdf", recipe=None
    )

    run = Mock()
    exists = Mock(return_value=True)

    # when
    result = automata.materials.build(artifact, run=run, exists=exists)

    # then
    assert result.path
    assert not run.called


def test_build_artifact_when_recipe_is_none_raises_if_no_path():
    # given
    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(), path="foo.pdf", recipe=None
    )

    run = Mock()
    exists = Mock(return_value=False)

    # when
    with raises(automata.materials.exceptions.BuildError):
        automata.materials.build(artifact, run=run, exists=exists)


def test_build_artifact_when_recipe_is_none_does_not_raise_if_missing_ok():
    # given
    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(), path="foo.pdf", recipe=None, missing_ok=True
    )

    run = Mock()
    exists = Mock(return_value=False)

    # when
    result = automata.materials.build(artifact, run=run, exists=exists)
    assert result is None


def test_build_artifact_raises_if_no_file():
    # given
    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(), path="foo.pdf", recipe="touch bar"
    )

    run = Mock()
    exists = Mock(return_value=False)

    # when
    with raises(automata.materials.exceptions.BuildError):
        automata.materials.build(artifact, run=run, exists=exists)


def test_build_collection(default_example_course):
    # given
    universe = automata.materials.discover(default_example_course.path)

    # when
    built_universe = automata.materials.build(universe)

    # then
    assert (
        default_example_course.path / "homeworks" / "01-intro" / "solution.pdf"
    ).exists()
    build_result = (
        built_universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
    )

    assert build_result.path

    # check that a deep copy is made
    del universe.collections["homeworks"]
    assert "homeworks" in built_universe.collections

    # check that artifacts that have not been released are not built
    assert (
        "solution.pdf"
        not in built_universe.collections["homeworks"]
        .publications["02-python"]
        .artifacts
    )

    # check that publications that have not been released are not build
    assert (
        "04-publication_not_released"
        not in built_universe.collections["homeworks"].publications
    )


# build error message tests
# --------------------------------------------------------------------------------------


def test_build_error_message_includes_stderr_on_recipe_failure(temporary_course):
    """Test that build errors include stderr output when a recipe fails."""
    temporary_course.create_collection(
        "homeworks",
        """
        publication_schema:
            required_artifacts:
                - homework.pdf
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
        metadata: {}
        artifacts:
            homework.pdf:
                recipe: echo "custom error message from recipe" >&2 && exit 1
        """,
    )

    universe = automata.materials.discover(temporary_course.path)

    with raises(automata.materials.exceptions.BuildError) as exc_info:
        automata.materials.build(universe)

    error_message = str(exc_info.value)
    assert "custom error message from recipe" in error_message


def test_build_error_message_on_missing_artifact(temporary_course):
    """Test that build errors clearly indicate when an artifact file is missing."""
    temporary_course.create_collection(
        "homeworks",
        """
        publication_schema:
            required_artifacts:
                - homework.pdf
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
        metadata: {}
        artifacts:
            homework.pdf:
                recipe: echo "this does not create homework.pdf"
        """,
    )

    universe = automata.materials.discover(temporary_course.path)

    with raises(automata.materials.exceptions.BuildError) as exc_info:
        automata.materials.build(universe)

    error_message = str(exc_info.value)
    assert "homework.pdf" in error_message
    assert "does not exist" in error_message


def test_build_error_message_includes_artifact_path(temporary_course):
    """Test that build errors include the full path to the artifact."""
    temporary_course.create_collection(
        "homeworks",
        """
        publication_schema:
            required_artifacts:
                - output/homework.pdf
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
        metadata: {}
        artifacts:
            output/homework.pdf:
                path: output/homework.pdf
                recipe: mkdir -p output && echo "not creating the file"
        """,
    )

    universe = automata.materials.discover(temporary_course.path)

    with raises(automata.materials.exceptions.BuildError) as exc_info:
        automata.materials.build(universe)

    error_message = str(exc_info.value)
    assert "output/homework.pdf" in error_message


def test_build_raises_when_artifact_already_built():
    """Test that build() raises ValueError when given an already-built artifact."""
    # given: a publication containing an already-built artifact
    built_artifact = automata.materials.BuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        returncode=0,
        stdout="",
        stderr="",
    )
    publication = automata.materials.Publication(
        metadata={},
        artifacts={"foo.pdf": built_artifact},
    )

    # when/then: building should raise ValueError
    with raises(ValueError) as exc_info:
        automata.materials.build(publication)

    assert "Cannot build an already built artifact" in str(exc_info.value)
