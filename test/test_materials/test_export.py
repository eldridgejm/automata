import pathlib
from textwrap import dedent

from pytest import fixture, raises

import automata.materials
from automata.hooks import ExportCopyHookArgs, ExportHooks, ExportNodeHookArgs


@fixture
def outdir(tmpdir):
    outdir = pathlib.Path(tmpdir) / "out"
    outdir.mkdir()
    return outdir


def test_export(default_example_course, outdir):
    # given
    discovered = automata.materials.discover(default_example_course.path)
    builts = automata.materials.build(discovered)

    # when
    exported = automata.materials.export(builts, outdir)

    # then
    assert (outdir / "homeworks" / "01-intro" / "homework.pdf").exists()
    assert not (outdir / "homeworks" / "02-python" / "solution.pdf").exists()

    assert (
        "homework.pdf"
        in exported.collections["homeworks"].publications["01-intro"].artifacts
    )


def test_artifact_not_copied_if_not_released(default_example_course, outdir):
    # given
    discovered = automata.materials.discover(default_example_course.path)
    built = automata.materials.build(discovered)
    publication = built.collections["homeworks"].publications["02-python"]

    # when
    automata.materials.export(built, outdir)

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
                recipe: mkdir problems && touch problems/a.pdf problems/b.pdf
        metadata:
            name: Homework
            date: 2021-10-05 23:59:00
        """
    )

    temporary_course.create_collection("homeworks", collection_yaml)
    temporary_course.create_publication("homeworks", "01-testing", publication_yaml)

    discovered = automata.materials.discover(temporary_course.path)
    built = automata.materials.build(discovered)
    _ = automata.materials.export(built, outdir)

    assert (outdir / "homeworks" / "01-testing" / "problems").is_dir()
    assert (outdir / "homeworks" / "01-testing" / "problems" / "a.pdf").is_file()
    assert (outdir / "homeworks" / "01-testing" / "problems" / "b.pdf").is_file()


def test_export_raises_when_artifact_not_built(outdir):
    """Test that export() raises ValueError when given an unbuilt artifact."""
    # given: a publication containing an unbuilt artifact
    unbuilt_artifact = automata.materials.UnbuiltArtifact(
        workdir=pathlib.Path.cwd(),
        path="foo.pdf",
        recipe="touch foo.pdf",
    )
    publication = automata.materials.Publication(
        metadata={},
        artifacts={"foo.pdf": unbuilt_artifact},
    )

    # when/then: exporting should raise ValueError
    with raises(ValueError) as exc_info:
        automata.materials.export(publication, outdir)

    assert "Cannot export an unbuilt artifact" in str(exc_info.value)


# export hooks tests
# --------------------------------------------------------------------------------------


def test_export_invokes_on_export_node_hook(default_example_course, outdir):
    """Test that on_export_node hook is invoked for each node."""
    # given
    nodes = []
    hooks = ExportHooks()

    @hooks.on_export_node.register()
    def track_nodes(args: ExportNodeHookArgs) -> None:
        nodes.append((args.key, args.node_type))

    discovered = automata.materials.discover(default_example_course.path)
    built = automata.materials.build(discovered)

    # when
    automata.materials.export(built, outdir, hooks=hooks)

    # then
    assert len(nodes) > 0
    node_types = {node_type for _, node_type in nodes}
    assert "collection" in node_types
    assert "publication" in node_types


def test_export_invokes_on_export_copy_hook(default_example_course, outdir):
    """Test that on_export_copy hook is invoked when copying files."""
    # given
    copies = []
    hooks = ExportHooks()

    @hooks.on_export_copy.register()
    def track_copies(args: ExportCopyHookArgs) -> None:
        copies.append((args.src, args.dst))

    discovered = automata.materials.discover(default_example_course.path)
    built = automata.materials.build(discovered)

    # when
    automata.materials.export(built, outdir, hooks=hooks)

    # then
    assert len(copies) > 0
    # Check that all destinations are under outdir
    assert all(str(dst).startswith(str(outdir)) for _, dst in copies)


def test_on_export_node_shell_script_receives_json(
    default_example_course, outdir, tmp_path
):
    """Test that shell script on on_export_node receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.jsonl"
    hooks = ExportHooks()
    hooks.on_export_node.register_shell_script(
        f"cat >> {output_file} && echo >> {output_file}"
    )

    discovered = automata.materials.discover(default_example_course.path)
    built = automata.materials.build(discovered)

    # when
    automata.materials.export(built, outdir, hooks=hooks)

    # then
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) > 0
    for line in lines:
        content = json.loads(line)
        assert "key" in content
        assert "node_type" in content
        assert content["node_type"] in ("collection", "publication", "artifact")


def test_on_export_copy_shell_script_receives_json(
    default_example_course, outdir, tmp_path
):
    """Test that shell script on on_export_copy receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.jsonl"
    hooks = ExportHooks()
    hooks.on_export_copy.register_shell_script(
        f"cat >> {output_file} && echo >> {output_file}"
    )

    discovered = automata.materials.discover(default_example_course.path)
    built = automata.materials.build(discovered)

    # when
    automata.materials.export(built, outdir, hooks=hooks)

    # then
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) > 0
    for line in lines:
        content = json.loads(line)
        assert "src" in content
        assert "dst" in content
