import datetime
import shutil
import pathlib
from unittest.mock import Mock

from pytest import raises, fixture

import automata.lib.materials

# good example; simple
EXAMPLES_ROOT = pathlib.Path(__file__).parent.parent.parent / "examples"
EXAMPLE_1_DIRECTORY = EXAMPLES_ROOT / "example_1"


@fixture
def example_1(tmpdir):
    path = pathlib.Path(tmpdir) / "example_1"
    shutil.copytree(EXAMPLE_1_DIRECTORY, path)
    return path


def test_build_artifact_integration(example_1):
    # given
    universe = automata.lib.materials.discover(example_1)
    artifact = (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
    )

    # when
    result = automata.lib.materials.build(artifact)

    # then
    assert (example_1 / "homeworks" / "01-intro" / "solution.pdf").exists()
    assert result.workdir == artifact.workdir
    assert result.path == artifact.path
    assert result.path


def test_build_artifact_when_release_time_is_in_future():
    # given
    artifact = automata.lib.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
    )

    proc = Mock()
    proc.returncode = 0
    run = Mock(return_value=proc)
    now = Mock(return_value=datetime.datetime(2020, 1, 1, 0, 0, 0))

    # when
    result = automata.lib.materials.build(artifact, run=run, now=now)

    # then
    assert result is None
    assert not run.called


def test_build_artifact_when_not_ready():
    # given
    artifact = automata.lib.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
        ready=False,
    )

    proc = Mock()
    proc.returncode = 0
    run = Mock(return_value=proc)
    now = Mock(return_value=datetime.datetime(2020, 3, 1, 0, 0, 0))

    # when
    result = automata.lib.materials.build(artifact, run=run, now=now)

    # then
    assert result is None
    assert not run.called


def test_build_artifact_when_release_time_is_in_future_ignore_release_time():
    # given
    artifact = automata.lib.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
    )

    proc = Mock()
    proc.returncode = 0
    run = Mock(return_value=proc)
    now = Mock(return_value=datetime.datetime(2020, 1, 1, 0, 0, 0))
    exists = Mock(return_value=True)

    # when
    result = automata.lib.materials.build(
        artifact, run=run, now=now, exists=exists, ignore_release_time=True
    )

    # then
    assert result.path
    assert run.called


def test_build_artifact_when_recipe_is_none():
    # given
    artifact = automata.lib.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(), path="foo.pdf", recipe=None
    )

    run = Mock()
    exists = Mock(return_value=True)

    # when
    result = automata.lib.materials.build(artifact, run=run, exists=exists)

    # then
    assert result.path
    assert not run.called


def test_build_artifact_when_recipe_is_none_raises_if_no_path():
    # given
    artifact = automata.lib.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(), path="foo.pdf", recipe=None
    )

    run = Mock()
    exists = Mock(return_value=False)

    # when
    with raises(automata.lib.materials.BuildError):
        result = automata.lib.materials.build(artifact, run=run, exists=exists)


def test_build_artifact_when_recipe_is_none_does_not_raise_if_missing_ok():
    # given
    artifact = automata.lib.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(), path="foo.pdf", recipe=None, missing_ok=True
    )

    run = Mock()
    exists = Mock(return_value=False)

    # when
    result = automata.lib.materials.build(artifact, run=run, exists=exists)
    assert result is None


def test_build_artifact_raises_if_no_file():
    # given
    artifact = automata.lib.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(), path="foo.pdf", recipe="touch bar"
    )

    run = Mock()
    exists = Mock(return_value=False)

    # when
    with raises(automata.lib.materials.BuildError):
        result = automata.lib.materials.build(artifact, run=run, exists=exists)


def test_build_collection(example_1):
    # given
    universe = automata.lib.materials.discover(example_1)

    # when
    built_universe = automata.lib.materials.build(universe)

    # then
    assert (example_1 / "homeworks" / "01-intro" / "solution.pdf").exists()
    build_result = (
        built_universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
    )
    assert build_result.path
    assert (
        built_universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
        .path
    )

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
