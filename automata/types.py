from typing import Mapping


class InternalNode(Mapping):

    def __init__(self, children=None):
        self._children = children or {}

    def __getitem__(self, key):
        return self._children[key]

    def __iter__(self, key, value):
        return iter(self._children)

    def __len__(self):
        return len(self._children)

    def _add_child(self, key, value):
        self._children[key] = value


class Materials(InternalNode):
    pass


class Collection(InternalNode):
    pass


class Publication(InternalNode):

    def _init__(self, *, parent, release_time, ready, artifacts):
        self.parent = parent
        self.release_time = release_time
        self.ready = ready

        super().__init__(artifacts)


class Artifact:

    def __init__(self, parent):
        self.parent = parent

