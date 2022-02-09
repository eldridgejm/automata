"""Base types used to represent nodes in the materials hierarchy.

Automata organizes all course materials into a hierarchy with the following levels:

    Materials
    ↓
    Collections (e.g., "homeworks")
    ↓
    Publications (e.g., "Homework 01")
    ↓
    Artifacts (e.g., "solutions.pdf")

This module provides base classes for each level of this hierarchy. Typically these base
classes are subclassed in order to provide task-specific behavior.

Materials, Collections, and Publications are internal nodes in this hierarchy. They
derive from an InternalNode class that implements the MutableMapping interface.
Therefore, instances of these classes behave like dictionaries, allowing us to write
things like `materials["homeworks"]["01-intro"]["solutions.pdf"]` to retrieve a specific
artifact.

"""
from typing import MutableMapping


def _flatten(container, attr):
    """For each element in the container, get the arr and flatten into a dict."""
    dct = {}
    for outer_key, outer_element in container.items():
        for inner_key, inner_element in getattr(outer_element, attr).items():
            if not isinstance(inner_key, tuple):
                inner_key = tuple([inner_key])
            key = tuple([outer_key, *inner_key])
            dct[key] = inner_element
    return dct


class InternalNode(MutableMapping):
    """Represents an internal node of the materials hierarchy.

    Implements the MutableMapping interface, allowing instances to behave like
    dictionaries.

    """

    def __init__(self, children=None):
        self.children = children or {}

    def __getitem__(self, key):
        return self.children[key]

    def __setitem__(self, key, value):
        self.children[key] = value

    def __delitem__(self, key):
        del self.children[key]

    def __iter__(self, key, value):
        return iter(self.children)

    def __len__(self):
        return len(self.children)


class Materials(InternalNode):
    """Represents a set of materials."""

    def __init__(self, collections):
        super().__init__(collections)

    @property
    def collections(self):
        """A dictionary of all collections contained within."""
        return self.children

    @property
    def publications(self):
        """A dictionary of all publications contained within."""
        return _flatten(self.collections, "publications")

    @property
    def artifacts(self):
        """A dictionary of all artifacts contained within."""
        return _flatten(self.collections, "artifacts")


class Collection(InternalNode):
    """Represents a collection. Children are Publications."""

    def __init__(self, *, ordered=False, publication_spec=None, publications=None):
        self.ordered = ordered
        self.publication_spec = publication_spec or {}
        super().__init__(publications)

    @property
    def publications(self):
        """A dictionary of all publications contained within."""
        return self.children

    @property
    def artifacts(self):
        """A dictionary of all artifacts contained within."""
        return _flatten(self.publications, "artifacts")


class Publication(InternalNode):
    """Represents a publication. Children are Artifacts."""

    def __init__(self, *, metadata=None, release_time=None, ready=True, artifacts=None):
        self.metadata = metadata or {}
        self.release_time = release_time
        self.ready = ready

        super().__init__(artifacts)

    @property
    def artifacts(self):
        return self.children


class Artifact:
    """Represents an artifact."""
