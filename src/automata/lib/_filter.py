"""Provides filter(), which selects materials according to a predicate."""

from typing import Callable, Optional, TypeVar, overload

from ._types import (
    Artifact,
    BuiltArtifact,
    Collection,
    ExportedArtifact,
    Publication,
    UnbuiltArtifact,
    Universe,
)


class FilterCallbacks:
    """Callbacks used by :func:`filter`."""

    def on_hit(self, key: str, node: Universe | Collection | Publication | Artifact):
        """Called when a node matches the predicate."""
        return key, node

    def on_miss(self, key: str, node: Universe | Collection | Publication | Artifact):
        """Called when a node does not match the predicate."""
        return key, node


# overloads for filter() ---------------------------------------------------------------

# The following overloads are used to provide type hints for the filter()
# function. Standard generics won't work here because union types are too
# loose.


ArtifactType = TypeVar(
    "ArtifactType",
    UnbuiltArtifact,
    BuiltArtifact,
    ExportedArtifact,
    UnbuiltArtifact | BuiltArtifact,
    BuiltArtifact | ExportedArtifact,
    UnbuiltArtifact | ExportedArtifact,
    UnbuiltArtifact | BuiltArtifact | ExportedArtifact,
)

Predicate = Callable[[str, Universe | Collection | Publication | Artifact], bool]


@overload
def filter(
    root: Universe[ArtifactType],
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    callbacks: Optional[FilterCallbacks] = ...,
) -> Universe[ArtifactType]: ...


@overload
def filter(
    root: Collection[ArtifactType],
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    callbacks: Optional[FilterCallbacks] = ...,
) -> Collection[ArtifactType]: ...


@overload
def filter(
    root: Publication[ArtifactType],
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    callbacks: Optional[FilterCallbacks] = ...,
) -> Publication[ArtifactType]: ...


@overload
def filter(
    root: ArtifactType,
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    callbacks: Optional[FilterCallbacks] = ...,
) -> ArtifactType: ...


# filter() =============================================================================


def filter(
    root: Universe[ArtifactType]
    | Collection[ArtifactType]
    | Publication[ArtifactType]
    | Artifact,
    predicate: Callable[[str, Universe | Collection | Publication | Artifact], bool],
    remove_empty_nodes: bool = False,
    callbacks: Optional[FilterCallbacks] = None,
) -> (
    Universe[ArtifactType]
    | Collection[ArtifactType]
    | Publication[ArtifactType]
    | Artifact
):
    """Remove nodes from a Universe/Collection/Publication according to a predicate.

    Parameters
    ----------
    root : Universe | Collection | Publication | Artifact
        The root of the course materials tree whose nodes are to be filtered.
    predicate : Callable[[str, Universe | Collection | Publication | Artifact], bool]
        A function which takes in two arguments: the key of the node and the
        node itself, and returns True if the node should be kept.
    remove_empty_nodes : bool
        Whether nodes without children should be removed (True) or preserved
        (False). The exception is the root node: if all of its children are
        removed, it remains. Default: False.
    callbacks : Optional[FilterCallbacks]
        Callbacks to be invoked during the filtering. If None, no callbacks
        are invoked.

    Returns
    -------
    Universe | Collection | Publication | Artifact
        An object of the same type as the root, but with all filtered nodes
        removed. This is a new object, and the original root is unchanged.

    """
    # bottom up -- by the time the predicate is applied to publication, its artifacts
    # have been filtered

    if isinstance(root, Artifact):
        return root

    if callbacks is None:
        callbacks = FilterCallbacks()

    def predicate_with_callbacks(key, node):
        result = predicate(key, node)
        if result:
            callbacks.on_hit(key, node)
        else:
            callbacks.on_miss(key, node)
        return result

    new_children = {}
    for child_key, child in root._children.items():
        new_child = filter(
            child, predicate, remove_empty_nodes=remove_empty_nodes, callbacks=callbacks
        )
        is_artifact = isinstance(new_child, Artifact)
        if is_artifact or (not remove_empty_nodes) or new_child._children:
            new_children[child_key] = new_child

    new_children = {
        k: v for (k, v) in new_children.items() if predicate_with_callbacks(k, v)
    }

    return root._replace_children(new_children)
