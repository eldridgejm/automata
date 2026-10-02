"""The status of a project's materials: what is released, scheduled, and built."""

from __future__ import annotations

import dataclasses
import datetime
from pathlib import Path
from typing import Any

from .materials import ExportedArtifact, UnbuiltArtifact, Universe
from .util.resolution import local_time

# the states an artifact can be in, in the order they are reported
STATES = ("released", "scheduled", "not ready", "missing")


@dataclasses.dataclass
class ArtifactStatus:
    """The status of one artifact.

    Attributes
    ----------
    collection, publication, artifact : str
        The keys of the artifact's collection, publication, and the artifact.
    state : str
        One of:

        - ``"released"``: it is released (its release time has passed, or it
          has none) and ready, so a build includes it;
        - ``"scheduled"``: its release time is in the future;
        - ``"not ready"``: it is marked ``ready: false``;
        - ``"missing"``: it has no recipe and its file doesn't exist.
    release_time : datetime.datetime | None
        When it is (or was) released, if it has a release time.
    on_site : bool
        Whether the last build put it on the site (it is in the build's
        ``materials.json``, with a path).

    """

    collection: str
    publication: str
    artifact: str
    state: str
    release_time: datetime.datetime | None
    on_site: bool

    @property
    def key(self) -> str:
        """The artifact's key path, e.g. ``"homeworks/hw01/homework.pdf"``."""
        return f"{self.collection}/{self.publication}/{self.artifact}"

    @property
    def out_of_date(self) -> bool:
        """Whether the site doesn't match: released but not on the site, or the
        reverse (e.g. its release time was moved later after a build)."""
        return (self.state == "released") != self.on_site

    def to_dict(self) -> dict[str, Any]:
        """The status as JSON-ready data."""
        return {
            "key": self.key,
            "collection": self.collection,
            "publication": self.publication,
            "artifact": self.artifact,
            "state": self.state,
            "release_time": _iso(self.release_time),
            "on_site": self.on_site,
            "out_of_date": self.out_of_date,
        }


@dataclasses.dataclass
class Status:
    """The status of a project's materials, as of a time.

    Attributes
    ----------
    current_time : datetime.datetime
        The time the status is for.
    artifacts : list[ArtifactStatus]
        Every artifact, ordered by key.
    last_built : datetime.datetime | None
        When the site was last built (when ``materials.json`` was written), or
        None if it hasn't been.

    """

    current_time: datetime.datetime
    artifacts: list[ArtifactStatus]
    last_built: datetime.datetime | None

    @property
    def counts(self) -> dict[str, int]:
        """The number of artifacts in each state (only states that occur)."""
        counts = {state: 0 for state in STATES}
        for artifact in self.artifacts:
            counts[artifact.state] += 1
        return {state: n for state, n in counts.items() if n}

    @property
    def next_releases(self) -> list[ArtifactStatus]:
        """The scheduled artifacts, soonest first."""
        scheduled = [a for a in self.artifacts if a.state == "scheduled"]
        return sorted(scheduled, key=lambda a: (a.release_time, a.key))

    @property
    def out_of_date(self) -> list[ArtifactStatus]:
        """The artifacts whose place on the site doesn't match their state."""
        return [a for a in self.artifacts if a.out_of_date]

    def to_dict(self) -> dict[str, Any]:
        """The status as JSON-ready data."""
        return {
            "current_time": _iso(self.current_time),
            "last_built": _iso(self.last_built),
            "counts": self.counts,
            "next_releases": [a.key for a in self.next_releases],
            "out_of_date": [a.key for a in self.out_of_date],
            "artifacts": [a.to_dict() for a in self.artifacts],
        }


def _iso(value: datetime.datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _state(artifact: UnbuiltArtifact, current_time: datetime.datetime) -> str:
    """The state of an artifact (see :class:`ArtifactStatus`)."""
    release_time = artifact.release_time
    if release_time is not None and local_time(release_time) > current_time:
        return "scheduled"
    if not artifact.ready:
        return "not ready"
    if artifact.recipe is None and not (artifact.workdir / artifact.path).exists():
        return "missing"
    return "released"


def _on_site(exported: Universe[ExportedArtifact] | None) -> set[tuple[str, str, str]]:
    """The (collection, publication, artifact) keys the last build put on the site."""
    if exported is None:
        return set()
    return {
        (collection_key, publication_key, artifact_key)
        for collection_key, collection in exported.collections.items()
        for publication_key, publication in collection.publications.items()
        for artifact_key, artifact in publication.artifacts.items()
        if artifact.path is not None
    }


def make_status(
    discovered: Universe[UnbuiltArtifact],
    materials_json: Path,
    exported: Universe[ExportedArtifact] | None,
    current_time: datetime.datetime,
) -> Status:
    """The status of the *discovered* materials, given the last build's *exported*
    materials (read from *materials_json*, or None if it doesn't exist)."""
    current_time = local_time(current_time)
    on_site = _on_site(exported)
    artifacts = [
        ArtifactStatus(
            collection=collection_key,
            publication=publication_key,
            artifact=artifact_key,
            state=_state(artifact, current_time),
            release_time=(
                None
                if artifact.release_time is None
                else local_time(artifact.release_time)
            ),
            on_site=(collection_key, publication_key, artifact_key) in on_site,
        )
        for collection_key, collection in discovered.collections.items()
        for publication_key, publication in collection.publications.items()
        for artifact_key, artifact in publication.artifacts.items()
    ]
    artifacts.sort(key=lambda a: a.key)

    last_built = None
    if exported is not None:
        last_built = datetime.datetime.fromtimestamp(materials_json.stat().st_mtime)

    return Status(current_time=current_time, artifacts=artifacts, last_built=last_built)
