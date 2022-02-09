from automata._types import Artifact, Publication, Collection, Materials, InternalNode


def test_descendant_methods():
    artifact_1 = Artifact()
    artifact_2 = Artifact()
    artifact_3 = Artifact()

    publication_1 = Publication(
        artifacts={"homework.pdf": artifact_1, "solution.pdf": artifact_2},
    )

    publication_2 = Publication(
          artifacts={"homework.pdf": artifact_3}
    )

    collection_1 = Collection(
        ordered=True, publications={"p1": publication_1}
    )

    collection_2 = Collection(
        ordered=True, publications={"p2": publication_2}
    )

    materials = Materials(collections={"foo": collection_1, "bar": collection_2})

    assert len(materials.collections) == 2
    assert len(materials.publications) == 2
    assert len(materials.artifacts) == 3

    assert ("foo", "p1", "solution.pdf") in materials.artifacts
    assert ("foo", "p1") in materials.publications

    assert len(collection_1.publications) == 1
    assert len(collection_2.publications) == 1
    assert len(collection_1.artifacts) == 2

    assert len(publication_1.artifacts) == 2
    assert len(publication_2.artifacts) == 1


def test_dictionary_like():
    p1 = Publication()
    a1 = Artifact()
    a2 = Artifact()
    c1 = Collection()

    p1['test'] = a1
    p1['this'] = a2
    c1['foo'] = p1

    assert c1['foo']['this'] == a2

    del p1['this']

    assert 'this' not in p1
