"""Provides filter(), which selects materials according to a predicate."""

from ._types import (
    Universe,
    Collection,
    Publication,
    Artifact,
)
from typing import Optional, Callable


class FilterCallbacks:
    """Callbacks used by :func:`filter`."""

    def on_hit(self, key: str, node: Universe | Collection | Publication | Artifact):
        """Called when a node matches the predicate."""
        return key, node

    def on_miss(self, key: str, node: Universe | Collection | Publication | Artifact):
        """Called when a node does not match the predicate."""
        return key, node


def filter[NodeType: (Universe, Collection, Publication, Artifact)](
    root: NodeType,
    predicate: Callable[[str, Universe | Collection | Publication | Artifact], bool],
    remove_empty_nodes: bool = False,
    callbacks: Optional[FilterCallbacks] = None,
) -> NodeType:
    """Remove nodes from a Universe/Collection/Publication according to a predicate.

    Parameters
    ----------
    root : Union[Universe, Collection, Publication, Artifact]
        The root of the course materials tree whose nodes are to be filtered.
    predicate : Callable[[str, Union[Universe, Collection, Publication, Artifact]], bool]
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
    type(root)
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
