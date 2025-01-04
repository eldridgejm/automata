"""Common test fixtures for the automata package."""

import pathlib

from pytest import fixture


@fixture
def write_file(tmpdir):
    """A fixture providing a function that writes a file to a temporary directory."""
    tmpdir = pathlib.Path(tmpdir)

    def inner(filename, contents):
        path = tmpdir / filename
        with path.open("w") as fileobj:
            fileobj.write(contents)
        return path

    return inner


class CourseBuilder:
    """A class that helps in building an example course."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)

    def create_collection(self, name, collection_yaml):
        """Create a collection in the example course."""
        (self.path / name).mkdir()
        with (self.path / name / "collection.yaml").open("w") as fileobj:
            fileobj.write(collection_yaml)

    def create_publication(self, collection_name, publication_name, publication_yaml):
        """Create a publication in the example course."""
        publication_path = self.path / collection_name / publication_name
        publication_path.mkdir()

        with (publication_path / "publication.yaml").open("w") as fileobj:
            fileobj.write(publication_yaml)


@fixture
def temporary_course(tmpdir):
    """Creates an example course in a temporary directory."""
    return CourseBuilder(tmpdir)
