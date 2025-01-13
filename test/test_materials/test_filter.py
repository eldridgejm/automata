import automata.materials
from automata.materials import discover, filter
from automata.materials import UnbuiltArtifact


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
