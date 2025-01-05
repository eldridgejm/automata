"""Core types for representing materials in an automata course."""

import typing
import pathlib
import datetime
import dataclasses

# material hierarchy nodes =============================================================

# These types represent nodes in the "materials hierarchy".

# artifacts ----------------------------------------------------------------------------

@dataclasses.dataclass
class Artifact:
    """Base class for all artifact types."""


@dataclasses.dataclass
class UnbuiltArtifact(Artifact):
    """The inputs needed to build an artifact.

    Attributes
    ----------
    workdir : pathlib.Path
        Absolute path to the working directory used to build the artifact.
    path : str
        Path (relative to the workdir) of the path produced by the build.
    recipe : Optional[str]
        Command used to build the artifact. If None, no command is necessary.
    release_time: Union[datetime.datetime, None]
        Time/date the artifact should be made public. If None, it is always
        available.
    ready : bool
        Whether or not the artifact is ready for publication. Default: True.
    missing_ok : bool
        If True and no file exists at the above path after building, then no
        error is raised and the result of the build is `None`. Default: True.

    """

    workdir: pathlib.Path
    path: str
    recipe: typing.Optional[str] = None
    release_time: typing.Optional[datetime.datetime] = None
    ready: bool = True
    missing_ok: bool = False


@dataclasses.dataclass
class BuiltArtifact(Artifact):
    """The result of building an artifact.

    Attributes
    ----------
    workdir : pathlib.Path
        Absolute path to the working directory used to build the artifact.
    path : str
        Path (relative to the workdir) of the artifact produced by the build.
    returncode : int
        The build process's return code. If None, there was no process. Default: None.
    stdout : str
        The build process's stdout. If None, there was no process. Default: None.
    stderr : str
        The build process's stderr. If None, there was no process. Default: None.

    """

    workdir: pathlib.Path
    path: str
    returncode: typing.Optional[int] = None
    stdout: typing.Optional[str] = None
    stderr: typing.Optional[str] = None


@dataclasses.dataclass
class ExportedArtifact(Artifact):
    """An exported artifact.

    Attributes
    ----------
    path : str
        The path to the artifact relative to the output directory.

    """

    path: str


def _artifact_from_dict(
    dct,
) -> typing.Union[UnbuiltArtifact, BuiltArtifact, ExportedArtifact]:
    """Given a dictionary representing an artifact, converts it to the appropriate type.

    Works by inferring the artifact type (UnbuiltArtifact, BuiltArtifact, or
    ExportedArtifact) from the dictionary's keys.


    Parameters
    ----------
    dct : Dict
        A dictionary containing the attributes of an artifact. Must be either
        an UnbuiltArtifact, BuiltArtifact, or ExportedArtifact.

    Returns
    -------
    UnbuiltArtifact, ExportedArtifact, BuiltArtifact

    """
    if "recipe" in dct:
        type_ = UnbuiltArtifact
    elif "returncode" in dct:
        type_ = BuiltArtifact
    else:
        type_ = ExportedArtifact

    return type_(**dct)


# publication, collection, universe ----------------------------------------------------

# the following are "Internal Nodes" of the universe -> collection ->
# publication -> artifact hierarchy. They all share the following attributes
# and methods:
#
#   ._children: the nodes directly under the node in question in the hierarchy
#   ._replace_children(new_children): replaces the node's current children with
#       new children, creating a new node.
#   ._deep_asdict(): returns a dictionary of all of the node's attributes.


class Publication(typing.NamedTuple):
    """A publication.

    Attributes
    ----------
    artifacts : Dict[str, Artifact]
        The artifacts contained in the publication.
    metadata: Dict[str, Any]
        The metadata dictionary.

    """

    metadata: typing.Mapping[str, typing.Any]
    artifacts: typing.Mapping[str, Artifact]

    def _deep_asdict(self):
        """A dictionary representation of the publication and its children."""
        return {
            "metadata": self.metadata,
            "artifacts": {
                k: dataclasses.asdict(a) for (k, a) in self.artifacts.items()
            },
        }

    @classmethod
    def _deep_fromdict(cls, dct):
        return cls(
            metadata=dct["metadata"],
            artifacts={
                k: _artifact_from_dict(d) for (k, d) in dct["artifacts"].items()
            },
        )

    @property
    def _children(self):
        return self.artifacts

    def _replace_children(self, new_children):
        return self._replace(artifacts=new_children)


class Collection(typing.NamedTuple):
    """A collection.

    Attributes
    ----------
    publication_schema : PublicationSchema
        The schema used to validate the publications within the collection.
    publications : Mapping[str, Publication]
        The publications contained in the collection.

    """

    publication_schema: "PublicationSchema"
    publications: typing.Mapping[str, Publication]

    def _deep_asdict(self):
        """A dictionary representation of the collection and its children."""
        return {
            "publication_schema": self.publication_schema._asdict(),
            "publications": {
                k: p._deep_asdict() for (k, p) in self.publications.items()
            },
        }

    @classmethod
    def _deep_fromdict(cls, dct):
        return cls(
            publication_schema=PublicationSchema(**dct["publication_schema"]),
            publications={
                k: Publication._deep_fromdict(d)
                for (k, d) in dct["publications"].items()
            },
        )

    @property
    def _children(self):
        return self.publications

    def _replace_children(self, new_children):
        return self._replace(publications=new_children)


class Universe(typing.NamedTuple):
    """Container of all collections.

    Attributes
    ----------

    collections : Dict[str, Collection]
        The collections.

    """

    collections: typing.Mapping[str, Collection]

    @property
    def _children(self):
        return self.collections

    def _replace_children(self, new_children):
        return self._replace(collections=new_children)

    def _deep_asdict(self):
        """A dictionary representation of the universe and its children."""
        return {
            "collections": {k: p._deep_asdict() for (k, p) in self.collections.items()},
        }

    @classmethod
    def _deep_fromdict(cls, dct):
        return cls(
            collections={
                k: Collection._deep_fromdict(d) for (k, d) in dct["collections"].items()
            },
        )

# other ================================================================================

# publication schema -------------------------------------------------------------------

class PublicationSchema(typing.NamedTuple):
    """Rules governing publications.

    Attributes
    ----------
    required_artifacts : typing.Collection[str]
        Names of artifacts that publications must contain.
    optional_artifacts : typing.Collection[str], optional
        Names of artifacts that publication are permitted to contain. Default: empty
        list.
    metadata_schema : Mapping[str, Any], optional
        A dictionary describing a schema used to validate publication metadata. In the
        style of cerberus. If None, no validation will be performed. Default: None.
    allow_unspecified_artifacts : Optional[Boolean]
        Is it permissible for a publication to have unknown artifacts? Default: False.
    is_ordered : Optional[Boolean]
        Should the publications be considered ordered by their keys? Default: False

    """

    required_artifacts: typing.Collection[str]
    optional_artifacts: typing.Optional[typing.Collection[str]] = None
    metadata_schema: typing.Optional[typing.Mapping[str, typing.Mapping]] = None
    allow_unspecified_artifacts: typing.Optional[bool] = False
    is_ordered: bool = False

# date context -------------------------------------------------------------------------

class DateContext(typing.NamedTuple):
    """A context used to resolve smart dates.

    Attributes
    ----------
    known : Optional[Mapping[str, datetime]]
        A dictionary of known dates. If None, there are no known dates.
    start_of_week_one : Optional[datetime.date]
        What should be considered the start of "week 1". If None, smart dates referring
        to weeks cannot be used.

    """

    known: dict = None
    start_of_week_one: typing.Optional[datetime.date] = None
