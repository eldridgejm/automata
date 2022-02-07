import typing
import pathlib
import datetime

from typing import Optional, Mapping

from ruamel.yaml import YAML


yaml = YAML()


# types
# --------------------------------------------------------------------------------------


class UnbuiltArtifact(typing.NamedTuple):
    """The inputs needed to build an artifact.

    Attributes
    ----------
    workdir : pathlib.Path
        Absolute path to the working directory used to build the artifact.
    path : str
        Path (relative to the workdir) of the path produced by the build.
    recipe : Union[str, None]
        Command used to build the artifact. If None, no command is necessary.
    release_time: Union[datetime.datetime, None]
        Time/date the artifact should be made public. If None, it is always available.
    ready : bool
        Whether or not the artifact is ready for publication. Default: True.
    missing_ok : bool
        If True and the path is missing after building, then no error is raised and the
        result of the build is `None`.

    """

    workdir: pathlib.Path
    path: str
    recipe: Optional[str] = None
    release_time: Optional[datetime.datetime] = None
    ready: bool = True
    missing_ok: bool = False


class BuiltArtifact(typing.NamedTuple):
    """The results of building an artifact.

    Attributes
    ----------
    workdir : pathlib.Path
        Absolute path to the working directory used to build the artifact.
    path : str
        Path (relative to the workdir) of the path produced by the build.
    returncode : int
        The build process's return code. If None, there was no process.
    stdout : str
        The build process's stdout. If None, there was no process.
    stderr : str
        The build process's stderr. If None, there was no process.

    """

    workdir: pathlib.Path
    path: str
    returncode: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class PublishedArtifact(typing.NamedTuple):
    """A published artifact.

    Attributes
    ----------
    path : str
        The path to the artifact's path relative to the output directory.

    """

    path: str


Artifact = typing.Union[UnbuiltArtifact, BuiltArtifact, PublishedArtifact]


def _artifact_from_dict(dct):
    """Infers the artifact type from the dictionary and performs conversion."""
    if "recipe" in dct:
        type_ = UnbuiltArtifact
    elif "returncode" in dct:
        type_ = BuiltArtifact
    else:
        type_ = PublishedArtifact

    return type_(**dct)


# the following are "Internal Nodes" of the collection -> publication ->
# artifact hierarchy. they all have _children attributes and _deep_asdict
# and _replace_children methods>


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
    ready: Optional[bool] = None
    release_time: Optional[datetime.datetime] = None

    def _deep_asdict(self):
        """A dictionary representation of the publication and its children."""
        return {
            "metadata": self.metadata,
            "artifacts": {k: a._asdict() for (k, a) in self.artifacts.items()},
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
    publication_spec : PublicationSchema
        The schema used to validate the publications within the collection.
    publications : Mapping[str, Publication]
        The publications contained in the collection.

    """

    publication_spec: "PublicationSchema"
    publications: typing.Mapping[str, Publication]
    ordered: bool = True

    def _deep_asdict(self):
        """A dictionary representation of the collection and its children."""
        return {
            "publication_spec": self.publication_spec._asdict(),
            "publications": {
                k: p._deep_asdict() for (k, p) in self.publications.items()
            },
        }

    @classmethod
    def _deep_fromdict(cls, dct):
        return cls(
            publication_spec=PublicationSchema(**dct["publication_spec"]),
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

# --------- new stuff ------------

class DiscoveredCollection(Mapping):

    def __init__(self, filepath: pathlib.Path, config: dict, publications=None):
        self.filepath = filepath
        self._config = config
        self._children = publications or {}

    def __getitem__(self, key):
        return self._children[key]

    def __iter__(self, key, value):
        return iter(self._children)

    def __len__(self):
        return len(self._children)

    def _add_child(self, key, value):
        self._children[key] = value

    @classmethod
    def from_file(cls, path):
        with path.open() as fileobj:
            config = yaml.load(fileobj)

        return cls(path, config)

    @property
    def publication_spec(self):
        return self._config['publication_spec']

    @publication_spec.setter
    def publication_spec(self, new_value):
        self._config['publication_spec'] = new_value

    @property
    def ordered(self):
        return self._config['ordered']

    @ordered.setter
    def ordered(self, new_value):
        self._config['ordered'] = new_value

    def write(self):
        with self.filepath.open('w') as fileobj:
            yaml.dump(self._config, fileobj)


class DiscoveredPublication(Mapping):

    def __init__(self, filepath: pathlib.Path, config: dict, publications=None):
        self.filepath = filepath
        self._config = config
        self._children = publications or {}

    def __getitem__(self, key):
        return self._children[key]

    def __iter__(self, key, value):
        return iter(self._children)

    def __len__(self):
        return len(self._children)

    def _add_child(self, key, value):
        self._children[key] = value

    @classmethod
    def from_file(cls, path):
        with path.open() as fileobj:
            config = yaml.load(fileobj)

        return cls(path, config)

    @property
    def metadata(self):
        return self._config['metadata']

    @metadata.setter
    def metadata(self, new_value):
        self._config['metadata'] = new_value

    @property
    def ready(self):
        return self._config['ready']

    @ready.setter
    def ready(self, new_value):
        self._config['ready'] = new_value

    @property
    def release_time(self):
        return self._config['release_time']

    @release_time.setter
    def release_time(self, new_value):
        self._config['release_time'] = new_value

    def write(self):
        with self.filepath.open('w') as fileobj:
            yaml.dump(self._config, fileobj)
