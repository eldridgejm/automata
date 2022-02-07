from automata.types import Artifact, Publication, Collection, Materials

# materials
# ===========

def test_materials_all_publications():
    artifact_1 = Artifact(
            parent=None
            )

    artifact_2 = Artifact(
            parent=None
            )

    artifact_3 = Artifact(
            parent=None
            )

    publication_1 = Publication(
            parent=None,
            release_time=None,
            ready=True,
            artifacts={"homework.pdf": artifact_1, "solution.pdf": artifact_2}
            )

    publication_2 = Publication(
            parent=None,
            release_time=None,
            ready=True,
            artifacts={"homework.pdf": artifact_3}
            )

    collection_1 = Collection(
            parent=None,
            ordered=True,
            publication_spec={},
            publications={"p1": publication_1}
    )

    collection_2 = Collection(
            parent=None,
            ordered=True,
            publication_spec={},
            publications={'p2': publication_2}
    )

    materials = Materials(collections={
        'foo': collection_1,
        'bar': collection_2
    })
