import pathlib
import collections
import datetime

import automata.lib.materials as materials


_ArtifactLocation = collections.namedtuple(
    "ArtifactLocation",
    [
        "artifact_key",
        "artifact",
        "publication_key",
        "publication",
        "collection_key",
        "collection",
    ],
)


def _all_artifacts(universe):
    for collection_key, collection in universe.collections.items():
        for publication_key, publication in collection.publications.items():
            for artifact_key, artifact in publication.artifacts.items():
                yield _ArtifactLocation(
                    artifact_key,
                    artifact,
                    publication_key,
                    publication,
                    collection_key,
                    collection,
                )


def _print_artifact(a, cwd):
    artifact_path = (a.artifact.workdir / a.artifact.path).relative_to(cwd)
    print(artifact_path, a.artifact.release_time)


def status(skip_directories=None, now=None):
    if now is None:
        now = datetime.datetime.now()

    def _is_published(a):
        return a.artifact.ready and (a.artifact.release_time is None or a.artifact.release_time <= now)

    def _is_pending(a):
        return a.artifact.ready and (a.artifact.release_time is not None and a.artifact.release_time > now)

    def _is_overdue(a):
        return not a.artifact.ready and (a.artifact.release_time is not None and a.artifact.release_time <= now)

    cwd = pathlib.Path.cwd()
    universe = materials.discover(cwd, skip_directories=skip_directories)

    artifacts = list(_all_artifacts(universe))

    print("pending:")
    for a in filter(_is_pending, artifacts):
        _print_artifact(a, cwd)

    print()

    print("overdue:")
    for a in filter(_is_overdue, artifacts):
        _print_artifact(a, cwd)
