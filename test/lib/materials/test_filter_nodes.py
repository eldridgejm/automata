import pathlib

from automata.lib.materials import discover, UnbuiltArtifact, filter_nodes


# good example; simple
EXAMPLES_ROOT = pathlib.Path(__file__).parent.parent.parent / 'examples'

EXAMPLE_1_DIRECTORY = EXAMPLES_ROOT / "example_1"


def test_basic():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    def keep(k, v):
        if not isinstance(v, UnbuiltArtifact):
            return True

        return k == "solution.pdf"

    universe = filter_nodes(universe, keep)

    # then
    assert (
        "homework.pdf"
        not in universe.collections["homeworks"].publications["01-intro"].artifacts
    )
    assert (
        "solution.pdf"
        in universe.collections["homeworks"].publications["01-intro"].artifacts
    )


def test_removes_nodes_without_children():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    def keep(k, v):
        if not isinstance(v, UnbuiltArtifact):
            return True

        return k not in {"solution.pdf", "homework.pdf"}

    universe = filter_nodes(universe, keep, remove_empty_nodes=True)

    # then
    assert "homeworks" not in universe.collections


def test_preserves_nodes_without_children_by_default():
    # when
    universe = discover(EXAMPLE_1_DIRECTORY)

    def keep(k, v):
        if not isinstance(v, UnbuiltArtifact):
            return True

        return k not in {"solution.pdf", "homework.pdf"}

    universe = filter_nodes(universe, keep)

    # then
    assert "homeworks" in universe.collections
