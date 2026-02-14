"""Provides filter(), which selects materials according to a predicate."""

from typing import Callable, Optional, TypeVar, overload

from automata.hooks import FilterHookArgs, FilterHooks

from ._types import (
    Artifact,
    BuiltArtifact,
    Collection,
    ExportedArtifact,
    Publication,
    UnbuiltArtifact,
    Universe,
    node_type_name,
)

# overloads for filter() ---------------------------------------------------------------

# The following overloads are used to provide type hints for the filter()
# function. Standard generics won't work here because union types are too
# loose.


ArtifactType = TypeVar(
    "ArtifactType",
    UnbuiltArtifact,
    BuiltArtifact,
    ExportedArtifact,
    UnbuiltArtifact | BuiltArtifact | ExportedArtifact,
)

Predicate = Callable[[str, Universe | Collection | Publication | Artifact], bool]


@overload
def filter(
    root: Universe[ArtifactType],
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    hooks: Optional[FilterHooks] = ...,
) -> Universe[ArtifactType]: ...


@overload
def filter(
    root: Collection[ArtifactType],
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    hooks: Optional[FilterHooks] = ...,
) -> Collection[ArtifactType]: ...


@overload
def filter(
    root: Publication[ArtifactType],
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    hooks: Optional[FilterHooks] = ...,
) -> Publication[ArtifactType]: ...


@overload
def filter(
    root: ArtifactType,
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    hooks: Optional[FilterHooks] = ...,
) -> ArtifactType: ...


# filter() =============================================================================


def filter(
    root: Universe[ArtifactType]
    | Collection[ArtifactType]
    | Publication[ArtifactType]
    | Artifact,
    predicate: Callable[[str, Universe | Collection | Publication | Artifact], bool],
    remove_empty_nodes: bool = False,
    hooks: Optional[FilterHooks] = None,
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
    hooks : Optional[FilterHooks]
        Hooks to be invoked during filtering. If not provided, a default
        instance with no registered implementations will be used.

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

    if hooks is None:
        hooks = FilterHooks()

    def predicate_with_hooks(key, node):
        result = predicate(key, node)
        hook_args = FilterHookArgs(key=key, node_type=node_type_name(node))
        if result:
            hooks.on_filter_hit(hook_args)
        else:
            hooks.on_filter_miss(hook_args)
        return result

    new_children = {}
    for child_key, child in root._children.items():
        new_child = filter(
            child, predicate, remove_empty_nodes=remove_empty_nodes, hooks=hooks
        )
        if (
            isinstance(new_child, Artifact)
            or (not remove_empty_nodes)
            or new_child._children
        ):
            new_children[child_key] = new_child

    new_children = {
        k: v for (k, v) in new_children.items() if predicate_with_hooks(k, v)
    }

    return root._replace_children(new_children)
