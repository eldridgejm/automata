import pathlib
from textwrap import dedent

from pytest import fixture


DEFAULT_COLLECTION_YAML = dedent("""
publication_schema:
    required_artifacts: []
    metadata_schema: {}
""")


DEFAULT_PUBLICATION_YAML = dedent("""
metadata: {}
artifacts: {}
""")


class ExampleCourse:

    def __init__(self, root):
        self.root = pathlib.Path(root)

    def create_collection(self, name, collection_yaml=DEFAULT_COLLECTION_YAML):
        return ExampleCollection.new(self.root, name, collection_yaml)

    def create_singleton_publication(self, name, publication_yaml=DEFAULT_PUBLICATION_YAML):
        return ExamplePublication.new(self.root, name, publication_yaml)


class ExampleCollection:

    def __init__(self, root):
        self.root = root

    @classmethod
    def new(cls, parent_directory, name, collection_yaml):
        (parent_directory / name).mkdir(parents=True)

        with (parent_directory / name / "collection.yaml").open('w') as fileobj:
            fileobj.write(collection_yaml)

        return cls(parent_directory / name)

    def create_publication(self, name, publication_yaml=DEFAULT_PUBLICATION_YAML):
        return ExamplePublication.new(self.root, name, publication_yaml)


class ExamplePublication:

    def __init__(self, root):
        self.root = root

    @classmethod
    def new(cls, parent_directory, name, publication_yaml):
        (parent_directory / name).mkdir(parents=True)

        with (parent_directory / name / "publication.yaml").open('w') as fileobj:
            fileobj.write(publication_yaml)

        return cls(parent_directory / name)


@fixture
def example(tmpdir_factory):
    test_root = pathlib.Path(tmpdir_factory.mktemp("tmp"))
    return ExampleCourse(test_root)
