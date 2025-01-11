from .types import UnbuiltArtifact, BuiltArtifact, ExportedArtifact


# filter()
# --------------------------------------------------------------------------------------


class FilterCallbacks:
    def on_hit(self, x):
        """On an artifact match."""

    def on_miss(self, x):
        """On an artifact miss."""


def filter(root, predicate, remove_empty_nodes=False, callbacks=None):
    """Remove nodes from a Universe/Collection/Publication according to a predicate.

    Parameters
    ----------
    root : Union[Universe, Collection, Publication, Artifact]
        The root of the tree whose nodes are to be filtered.
    predicate : Callable[[node], bool]
        A function which takes in a node and returns True/False whether it
        should be kept.
    remove_empty_nodes : bool
        Whether nodes without children should be removed (True) or preserved
        (False). Default: False.

    Returns
    -------
    type(root)
        An object of the same type as the root, but wth all filtered nodes
        removed. Furthermore, if a node has no children after filtering, it
        is removed.

    """
    # bottom up -- by the time the predicate is applied to publication, its artifacts
    # have been filtered

    if isinstance(root, (UnbuiltArtifact, BuiltArtifact, ExportedArtifact)):
        return root

    new_children = {}
    for child_key, child in root._children.items():
        new_child = filter(
            child, predicate, remove_empty_nodes=remove_empty_nodes, callbacks=callbacks
        )
        is_artifact = isinstance(
            new_child, (UnbuiltArtifact, BuiltArtifact, ExportedArtifact)
        )
        if is_artifact or (not remove_empty_nodes) or new_child._children:
            new_children[child_key] = new_child

    new_children = {k: v for (k, v) in new_children.items() if predicate(k, v)}

    return root._replace_children(new_children)
