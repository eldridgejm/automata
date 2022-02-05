import pathlib
from pytest import fixture


class Example:

    def __init__(self, root):
        self.root = root

    def create_collection(self, name):
        pass


@fixture
def example(tmpdir_factory):
    test_root = pathlib.Path(tmpdir_factory.mktemp("tmp"))
    return Example(test_root)
