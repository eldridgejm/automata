"""This module provides types for representing materials in an `automata` course.

Types for representing nodes in the materials hierarchy
-------------------------------------------------------

`automata` conceptually organizes course materials into a hierarchy. At the
bottom of the hierarchy are "artifacts" (files). Artifacts are grouped into
"publications", which are in turn grouped into "collections". At the root of
the hierarchy is the "universe", which contains all of the collections. The
types in this module are used to represent the nodes in this hierarchy.

Artifacts
~~~~~~~~~

There are three types of artifacts: :class:`UnbuiltArtifact`,
:class:`BuiltArtifact`, and :class:`ExportedArtifact`. These represent artifacts
at different stages of the build/export process.

.. autoclass:: UnbuiltArtifact
.. autoclass:: BuiltArtifact
.. autoclass:: ExportedArtifact

These three classes are all subclasses of :class:`Artifact`:

.. autoclass:: Artifact

Publications, Collections, and Universes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Artifacts are the "leaf" nodes in the materials hierarchy. On the other hand, the
"internal" nodes of the hierarchy are represented by :class:`Publication`,
:class:`Collection`, and :class:`Universe`. These classes are all containers for
nodes of the next level down in the hierarchy. 

The unique attributes of each of these classes are documented below. However, all
three classes share the following attributes and methods:

.. attribute:: ._children

    The nodes directly under the node in question in the hierarchy. Their type will
    depend on the class in question.

.. method:: ._replace_children(new_children:)

    Replaces the node's current children with new children, creating a new node.

.. method:: ._deep_asdict()

    Returns a dictionary of all of the node's attributes, including its
    children. Operates recursively.

.. method:: ._deep_fromdict(dct:)

    Given a dictionary representation of the node, returns a new node. Round-trip
    compatible with :meth:`_deep_asdict`.

The unique attributes of each class are:

.. autoclass:: Publication
.. autoclass:: Collection
.. autoclass:: Universe

Types for schemas and dates
---------------------------

.. autoclass:: PublicationSchema
.. autoclass:: DateContext

"""

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
    """Represents an unbuilt artifact and the information necessary to build it.

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
    """Represents the result of building an artifact.

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
    """Represents an exported artifact.

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
    """Represents a schema used to validate publications.

    Collections can have a schema that defines the required and optional
    artifacts and metadata that the publications within the collection must
    contain. This class is used to represent that schema.

    Attributes
    ----------
    required_artifacts : typing.Collection[str]
        Names of artifacts that publications must contain.
    optional_artifacts : typing.Collection[str], optional
        Names of artifacts that publication are permitted to contain. Default: empty
        list.
    metadata_schema : Mapping[str, Any], optional
        A dictionary describing a schema used to validate publication metadata.
        In the style of the cerberus library
        (https://docs.python-cerberus.org/en/stable/). If None, no validation
        will be performed. Default: None.
    allow_unspecified_artifacts : Optional[Boolean]
        Is it permissible for a publication to have unknown artifacts? Default: False.
    is_ordered : Optional[Boolean]
        Should the publications be considered ordered by their keys? Default: False

    Example
    -------

    The following schema requires that all publications contain a "homework.pdf"
    artifact and a "solution.pdf" artifact. The metadata for each publication must
    contain a "due_date" key with a value that is a string.

    >>> schema = PublicationSchema(
    ...     required_artifacts=["homework.pdf", "solution.pdf"],
    ...     metadata_schema={
    ...         "due_date": {"type": "string"}
    ...     }
    ... )

    """

    required_artifacts: typing.Collection[str]
    optional_artifacts: typing.Optional[typing.Collection[str]] = None
    metadata_schema: typing.Optional[typing.Mapping[str, typing.Mapping]] = None
    allow_unspecified_artifacts: typing.Optional[bool] = False
    is_ordered: bool = False

# date context -------------------------------------------------------------------------

class DateContext(typing.NamedTuple):
    """a context used when resolving dates.

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
