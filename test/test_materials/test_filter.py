import automata.materials
from automata.hooks import FilterHookArgs, FilterHooks
from automata.materials import UnbuiltArtifact, discover, filter


def test_basic(default_example_course):
    # when
    universe = discover(default_example_course.path)

    def keep(k, v):
        if not isinstance(v, UnbuiltArtifact):
            return True

        return k == "solution.pdf"

    universe = filter(universe, keep)

    # then
    assert (
        "homework.pdf"
        not in universe.collections["homeworks"].publications["01-intro"].artifacts
    )
    assert (
        "solution.pdf"
        in universe.collections["homeworks"].publications["01-intro"].artifacts
    )


def test_removes_nodes_without_children(default_example_course):
    # when
    universe = discover(default_example_course.path)

    def keep(k, v):
        if not isinstance(v, UnbuiltArtifact):
            return True

        return k not in {"solution.pdf", "homework.pdf"}

    universe = filter(universe, keep, remove_empty_nodes=True)

    # then
    assert "homeworks" not in universe.collections


def test_preserves_nodes_without_children_by_default(default_example_course):
    # when
    universe = discover(default_example_course.path)

    def keep(k, v):
        if not isinstance(v, UnbuiltArtifact):
            return True

        return k not in {"solution.pdf", "homework.pdf"}

    universe = filter(universe, keep)

    # then
    assert "homeworks" in universe.collections


def test_if_all_children_of_root_are_removed_then(default_example_course):
    # when
    universe = discover(default_example_course.path)

    def keep(*_):
        return False

    universe = filter(universe, keep)

    # then
    assert not universe.collections
    assert isinstance(universe, automata.materials.Universe)


# filter hooks tests
# --------------------------------------------------------------------------------------


def test_filter_invokes_on_filter_hit_hook(default_example_course):
    """Test that on_filter_hit hook is invoked for matching nodes."""
    # given
    hits = []
    hooks = FilterHooks()

    @hooks.on_filter_hit.register()
    def track_hits(args: FilterHookArgs) -> None:
        hits.append((args.key, args.node_type))

    universe = discover(default_example_course.path)

    def keep_all(k, v):
        return True

    # when
    filter(universe, keep_all, hooks=hooks)

    # then
    assert len(hits) > 0
    node_types = {node_type for _, node_type in hits}
    assert "collection" in node_types
    assert "publication" in node_types


def test_filter_invokes_on_filter_miss_hook(default_example_course):
    """Test that on_filter_miss hook is invoked for non-matching nodes."""
    # given
    misses = []
    hooks = FilterHooks()

    @hooks.on_filter_miss.register()
    def track_misses(args: FilterHookArgs) -> None:
        misses.append((args.key, args.node_type))

    universe = discover(default_example_course.path)

    def keep_none(k, v):
        return False

    # when
    filter(universe, keep_none, hooks=hooks)

    # then
    assert len(misses) > 0
    node_types = {node_type for _, node_type in misses}
    assert "collection" in node_types
    assert "publication" in node_types


def test_on_filter_hit_shell_script_receives_json(default_example_course, tmp_path):
    """Test that shell script on on_filter_hit receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.jsonl"
    hooks = FilterHooks()
    hooks.on_filter_hit.register_shell_script(
        f"cat >> {output_file} && echo >> {output_file}"
    )

    universe = discover(default_example_course.path)

    def keep_all(k, v):
        return True

    # when
    filter(universe, keep_all, hooks=hooks)

    # then
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) > 0
    for line in lines:
        content = json.loads(line)
        assert "key" in content
        assert "node_type" in content
        assert content["node_type"] in ("collection", "publication", "artifact")


def test_on_filter_miss_shell_script_receives_json(default_example_course, tmp_path):
    """Test that shell script on on_filter_miss receives JSON payload."""
    # given
    import json

    output_file = tmp_path / "output.jsonl"
    hooks = FilterHooks()
    hooks.on_filter_miss.register_shell_script(
        f"cat >> {output_file} && echo >> {output_file}"
    )

    universe = discover(default_example_course.path)

    def keep_none(k, v):
        return False

    # when
    filter(universe, keep_none, hooks=hooks)

    # then
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) > 0
    for line in lines:
        content = json.loads(line)
        assert "key" in content
        assert "node_type" in content
        assert content["node_type"] in ("collection", "publication", "artifact")
