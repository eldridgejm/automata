import datetime
import pathlib
from unittest.mock import Mock

from pytest import raises

import automata.materials
from automata.hooks import (
    BuildArtifactHookArgs,
    BuildHooks,
    BuildNodeHookArgs,
    BuildSuccessHookArgs,
)


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


# build hooks tests
# --------------------------------------------------------------------------------------


def _fake_run_success(cmd, **kwargs):
    """Fake subprocess.run that always succeeds."""

    class FakeProc:
        returncode = 0
        stdout = b""
        stderr = b""

    return FakeProc()


def _fake_exists_true(path):
    """Fake Path.exists that always returns True."""
    return True


def _fake_exists_false(path):
    """Fake Path.exists that always returns False."""
    return False


def test_build_invokes_on_build_node_hook(default_example_course):
    """Test that on_build_node hook is invoked for each node."""
    # given
    nodes = []
    hooks = BuildHooks()

    @hooks.on_build_node.register()
    def track_nodes(args: BuildNodeHookArgs) -> None:
        nodes.append((args.key, args.node_type))

    universe = automata.materials.discover(default_example_course.path)

    # when
    automata.materials.build(universe, hooks=hooks)

    # then
    assert len(nodes) > 0
    node_types = {node_type for _, node_type in nodes}
    assert "collection" in node_types
    assert "publication" in node_types


def test_build_invokes_on_build_too_soon_hook():
    """Test that on_build_too_soon hook is invoked when release time hasn't passed."""
    # given
    too_soon_artifacts = []
    hooks = BuildHooks()

    @hooks.on_build_too_soon.register()
    def track_too_soon(args: BuildArtifactHookArgs) -> None:
        too_soon_artifacts.append(args.path)

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
    )
    current_time = datetime.datetime(2020, 1, 1, 0, 0, 0)

    # when
    automata.materials.build(artifact, current_time=current_time, hooks=hooks)

    # then
    assert len(too_soon_artifacts) == 1
    assert too_soon_artifacts[0] == "foo.pdf"


def test_build_invokes_on_build_not_ready_hook():
    """Test that on_build_not_ready hook is invoked when artifact is not ready."""
    # given
    not_ready_artifacts = []
    hooks = BuildHooks()

    @hooks.on_build_not_ready.register()
    def track_not_ready(args: BuildArtifactHookArgs) -> None:
        not_ready_artifacts.append(args.path)

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        ready=False,
    )

    # when
    automata.materials.build(artifact, hooks=hooks)

    # then
    assert len(not_ready_artifacts) == 1
    assert not_ready_artifacts[0] == "foo.pdf"


def test_build_invokes_on_build_missing_hook():
    """Test that on_build_missing hook is invoked when artifact is missing but ok."""
    # given
    missing_artifacts = []
    hooks = BuildHooks()

    @hooks.on_build_missing.register()
    def track_missing(args: BuildArtifactHookArgs) -> None:
        missing_artifacts.append(args.path)

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe=None,
        missing_ok=True,
    )

    # when
    automata.materials.build(artifact, exists=_fake_exists_false, hooks=hooks)

    # then
    assert len(missing_artifacts) == 1
    assert missing_artifacts[0] == "foo.pdf"


def test_build_invokes_on_build_recipe_hook():
    """Test that on_build_recipe hook is invoked when running a recipe."""
    # given
    recipe_artifacts = []
    hooks = BuildHooks()

    @hooks.on_build_recipe.register()
    def track_recipe(args: BuildArtifactHookArgs) -> None:
        recipe_artifacts.append((args.path, args.recipe))

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
    )

    # when
    automata.materials.build(
        artifact, run=_fake_run_success, exists=_fake_exists_true, hooks=hooks
    )

    # then
    assert len(recipe_artifacts) == 1
    assert recipe_artifacts[0] == ("foo.pdf", "echo hi")


def test_build_invokes_on_build_success_hook():
    """Test that on_build_success hook is invoked when build succeeds."""
    # given
    success_artifacts = []
    hooks = BuildHooks()

    @hooks.on_build_success.register()
    def track_success(args: BuildSuccessHookArgs) -> None:
        success_artifacts.append((args.path, args.returncode))

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
    )

    # when
    automata.materials.build(
        artifact, run=_fake_run_success, exists=_fake_exists_true, hooks=hooks
    )

    # then
    assert len(success_artifacts) == 1
    assert success_artifacts[0] == ("foo.pdf", 0)


def test_on_build_success_shell_script_receives_json(tmp_path):
    """Test that shell script on on_build_success receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.json"
    hooks = BuildHooks()
    hooks.on_build_success.register_shell_script(f"cat > {output_file}")

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
    )

    # when
    automata.materials.build(
        artifact, run=_fake_run_success, exists=_fake_exists_true, hooks=hooks
    )

    # then
    content = json.loads(output_file.read_text())
    assert "path" in content
    assert content["path"] == "foo.pdf"
    assert content["returncode"] == 0


def test_on_build_node_shell_script_receives_json(default_example_course, tmp_path):
    """Test that shell script on on_build_node receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.jsonl"
    hooks = BuildHooks()
    hooks.on_build_node.register_shell_script(
        f"cat >> {output_file} && echo >> {output_file}"
    )

    universe = automata.materials.discover(default_example_course.path)

    # when
    automata.materials.build(universe, hooks=hooks)

    # then
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) > 0
    for line in lines:
        content = json.loads(line)
        assert "key" in content
        assert "node_type" in content
        assert content["node_type"] in ("collection", "publication", "artifact")


def test_on_build_too_soon_shell_script_receives_json(tmp_path):
    """Test that shell script on on_build_too_soon receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.json"
    hooks = BuildHooks()
    hooks.on_build_too_soon.register_shell_script(f"cat > {output_file}")

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        release_time=datetime.datetime(2020, 2, 28, 23, 59, 0),
    )
    current_time = datetime.datetime(2020, 1, 1, 0, 0, 0)

    # when
    automata.materials.build(artifact, current_time=current_time, hooks=hooks)

    # then
    content = json.loads(output_file.read_text())
    assert content["path"] == "foo.pdf"
    assert content["recipe"] == "echo hi"
    assert "release_time" in content


def test_on_build_not_ready_shell_script_receives_json(tmp_path):
    """Test that shell script on on_build_not_ready receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.json"
    hooks = BuildHooks()
    hooks.on_build_not_ready.register_shell_script(f"cat > {output_file}")

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
        ready=False,
    )

    # when
    automata.materials.build(artifact, hooks=hooks)

    # then
    content = json.loads(output_file.read_text())
    assert content["path"] == "foo.pdf"
    assert content["ready"] is False


def test_on_build_missing_shell_script_receives_json(tmp_path):
    """Test that shell script on on_build_missing receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.json"
    hooks = BuildHooks()
    hooks.on_build_missing.register_shell_script(f"cat > {output_file}")

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe=None,
        missing_ok=True,
    )

    # when
    automata.materials.build(artifact, exists=_fake_exists_false, hooks=hooks)

    # then
    content = json.loads(output_file.read_text())
    assert content["path"] == "foo.pdf"
    assert content["missing_ok"] is True


def test_on_build_recipe_shell_script_receives_json(tmp_path):
    """Test that shell script on on_build_recipe receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.json"
    hooks = BuildHooks()
    hooks.on_build_recipe.register_shell_script(f"cat > {output_file}")

    artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="echo hi",
    )

    # when
    automata.materials.build(
        artifact, run=_fake_run_success, exists=_fake_exists_true, hooks=hooks
    )

    # then
    content = json.loads(output_file.read_text())
    assert content["path"] == "foo.pdf"
    assert content["recipe"] == "echo hi"
