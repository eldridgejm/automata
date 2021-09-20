import pathlib
from textwrap import dedent

from pytest import fixture


@fixture
def write_file(tmpdir):
    tmpdir = pathlib.Path(tmpdir)

    def inner(filename, contents):
        path = tmpdir / filename
        with path.open("w") as fileobj:
            fileobj.write(contents)
        return path

    return inner


class ExampleCourse:
    """A class that helps to in creating an example course."""

    def __init__(self, path: pathlib.Path, default_collection_yaml, default_publication_yaml):
        self.path = pathlib.Path(path)
        self.default_collection_yaml = default_collection_yaml
        self.default_publication_yaml = default_publication_yaml

    def create_collection(self, name, collection_yaml=None):
        if collection_yaml is None:
            collection_yaml = self.default_collection_yaml

        (self.path / name).mkdir()
        with (self.path / name / 'collection.yaml').open('w') as fileobj:
            fileobj.write(collection_yaml)

    def create_publication(self, collection_name, publication_name, publication_yaml=None):
        if publication_yaml is None:
            publication_yaml = self.default_publication_yaml

        publication_path = (self.path / collection_name / publication_name)
        publication_path.mkdir()

        with (publication_path / 'publication.yaml').open('w') as fileobj:
            fileobj.write(publication_yaml)


@fixture
def example_course_factory():
    return ExampleCourse

