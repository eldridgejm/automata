import pytest

import automata.materials


def _make_collection(**kwargs):
    """Create a simple Collection for testing."""
    return automata.materials.Collection(
        publication_schema=automata.materials.PublicationSchema(required_artifacts=[]),
        publications={},
        **kwargs,
    )


class TestMergeOnto:
    def test_merge_disjoint_universes(self):
        """Merging two universes with disjoint keys produces their union."""
        a = automata.materials.Universe({"hw": _make_collection()})
        b = automata.materials.Universe({"labs": _make_collection()})

        result = a.merge(b)

        assert set(result.collections.keys()) == {"hw", "labs"}

    def test_merge_preserves_collection_identity(self):
        """The merged universe contains the original collection objects."""
        hw = _make_collection()
        labs = _make_collection()
        a = automata.materials.Universe({"hw": hw})
        b = automata.materials.Universe({"labs": labs})

        result = a.merge(b)

        assert result.collections["hw"] is hw
        assert result.collections["labs"] is labs

    def test_merge_returns_new_universe(self):
        """merge returns a new Universe; it does not mutate either input."""
        a = automata.materials.Universe({"hw": _make_collection()})
        b = automata.materials.Universe({"labs": _make_collection()})

        result = a.merge(b)

        assert result is not a
        assert result is not b

    def test_merge_with_empty_universe(self):
        """Merging with an empty universe returns collections from the non-empty one."""
        a = automata.materials.Universe({"hw": _make_collection()})
        b = automata.materials.Universe({})

        result = a.merge(b)

        assert set(result.collections.keys()) == {"hw"}

    def test_merge_both_empty(self):
        """Merging two empty universes produces an empty universe."""
        a = automata.materials.Universe({})
        b = automata.materials.Universe({})

        result = a.merge(b)

        assert result.collections == {}

    def test_merge_overlapping_keys_raises(self):
        """Overlapping collection keys raise an error."""
        a = automata.materials.Universe({"hw": _make_collection()})
        b = automata.materials.Universe({"hw": _make_collection()})

        with pytest.raises(KeyError):
            a.merge(b)
