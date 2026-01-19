"""Provides filter(), which selects materials according to a predicate."""

from typing import Callable, TypeVar, overload

from ..hooks._base import Registry, define_hook
from ._types import (
    Artifact,
    BuiltArtifact,
    Collection,
    ExportedArtifact,
    Publication,
    UnbuiltArtifact,
    Universe,
)

# =============================================================================
# Hook Definitions
# =============================================================================


@define_hook("materials.filter:on_hit")
def FilterOnHitHook(
    key: str, node: Universe | Collection | Publication | Artifact
) -> None:
    """Called when predicate matches.

    Parameters
    ----------
    key : str
        The key of the matching node.
    node : Universe | Collection | Publication | Artifact
        The matching node.

    """
    ...


def _serialize_filter_hit_args(
    key: str, node: Universe | Collection | Publication | Artifact
) -> dict:
    """Serialize arguments for script execution (node serialized as type name)."""
    return {"key": key, "node_type": type(node).__name__}


FilterOnHitHook.serialize_args = _serialize_filter_hit_args


@define_hook("materials.filter:on_miss")
def FilterOnMissHook(
    key: str, node: Universe | Collection | Publication | Artifact
) -> None:
    """Called when predicate doesn't match.

    Parameters
    ----------
    key : str
        The key of the non-matching node.
    node : Universe | Collection | Publication | Artifact
        The non-matching node.

    """
    ...


def _serialize_filter_miss_args(
    key: str, node: Universe | Collection | Publication | Artifact
) -> dict:
    """Serialize arguments for script execution (node serialized as type name)."""
    return {"key": key, "node_type": type(node).__name__}


FilterOnMissHook.serialize_args = _serialize_filter_miss_args


# =============================================================================
# Filter Implementation
# =============================================================================

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
    hooks: Registry | None = ...,
) -> Universe[ArtifactType]: ...


@overload
def filter(
    root: Collection[ArtifactType],
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    hooks: Registry | None = ...,
) -> Collection[ArtifactType]: ...


@overload
def filter(
    root: Publication[ArtifactType],
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    hooks: Registry | None = ...,
) -> Publication[ArtifactType]: ...


@overload
def filter(
    root: ArtifactType,
    predicate: Predicate,
    remove_empty_nodes: bool = ...,
    hooks: Registry | None = ...,
) -> ArtifactType: ...


# filter() =============================================================================


def filter(
    root: Universe[ArtifactType]
    | Collection[ArtifactType]
    | Publication[ArtifactType]
    | Artifact,
    predicate: Callable[[str, Universe | Collection | Publication | Artifact], bool],
    remove_empty_nodes: bool = False,
    hooks: Registry | None = None,
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
    hooks : Registry | None
        Hooks to be invoked during the filtering. Supports:
        - ``materials.filter:on_hit``
        - ``materials.filter:on_miss``

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

    def predicate_with_hooks(key, node):
        result = predicate(key, node)
        if result:
            FilterOnHitHook.execute(hooks, {"key": key, "node": node})
        else:
            FilterOnMissHook.execute(hooks, {"key": key, "node": node})
        return result

    new_children = {}
    for child_key, child in root._children.items():
        new_child = filter(
            child,
            predicate,
            remove_empty_nodes=remove_empty_nodes,
            hooks=hooks,
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
