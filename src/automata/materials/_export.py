"""Provides export(), which publishes materials by copying them to a new directory."""

import pathlib
import shutil
from typing import Optional, cast, overload

from automata.hooks import ExportCopyHookArgs, ExportHooks, ExportNodeHookArgs

from ._types import (
    Artifact,
    BuiltArtifact,
    Collection,
    ExportedArtifact,
    Publication,
    Universe,
    node_type_name,
)


def _export_artifact(
    built_artifact: BuiltArtifact,
    outdir: pathlib.Path,
    filename: str,
    hooks: ExportHooks,
) -> ExportedArtifact:
    """Copies an artifact to another directory.

    Parameters
    ----------
    built_artifact : BuiltArtifact
        The artifact to copy.
    outdir : pathlib.Path
        The directory to copy the artifact to.
    filename : str
        The filename (or directory name) that will be given to the new file,
        including extension, if applicable.
    hooks : ExportHooks
        Hooks to be invoked during the export.

    """
    # actually copy the artifact
    full_dst = outdir / filename
    full_dst.parent.mkdir(parents=True, exist_ok=True)
    full_src = built_artifact.workdir / built_artifact.path
    hooks.on_export_copy(ExportCopyHookArgs(src=full_src, dst=full_dst))

    if full_src.is_dir():
        shutil.copytree(full_src, full_dst)
    else:
        shutil.copy(full_src, full_dst)

    return ExportedArtifact(path=str(full_dst.relative_to(outdir)))


# overloads for export() ---------------------------------------------------------------

# These are necessary to provide type hints for the export() function. Standard
# generics won't work here.


@overload
def export(
    root: Universe[BuiltArtifact],
    outdir: pathlib.Path,
    prefix: str = ...,
    hooks: Optional[ExportHooks] = ...,
) -> Universe[ExportedArtifact]: ...


@overload
def export(
    root: Collection[BuiltArtifact],
    outdir: pathlib.Path,
    prefix: str = "",
    hooks: Optional[ExportHooks] = None,
) -> Collection[ExportedArtifact]: ...


@overload
def export(
    root: Publication[BuiltArtifact],
    outdir: pathlib.Path,
    prefix: str = "",
    hooks: Optional[ExportHooks] = None,
) -> Publication[ExportedArtifact]: ...


@overload
def export(
    root: BuiltArtifact,
    outdir: pathlib.Path,
    prefix: str = "",
    hooks: Optional[ExportHooks] = None,
) -> ExportedArtifact: ...


# export() =============================================================================


def export(
    root: Universe[BuiltArtifact]
    | Collection[BuiltArtifact]
    | Publication[BuiltArtifact]
    | BuiltArtifact,
    outdir: pathlib.Path,
    prefix: str = "",
    hooks: Optional[ExportHooks] = None,
) -> (
    Universe[ExportedArtifact]
    | Collection[ExportedArtifact]
    | Publication[ExportedArtifact]
    | ExportedArtifact
):
    """Export a universe/collection/publication/artifact by copying it.

    An artifact is typically a file, but it can also be a directory. This is
    determined by whether the ``path'' attribute of the artifact is a file or a
    directory. If the artifact is a directory, it is copied recursively.

    The artifacts within must all be :class:`BuiltArtifact` instances. If an
    unbuilt artifact is encountered, a ``ValueError`` is raised.

    Parameters
    ----------
    root : Union[Universe, Collection, Publication, BuiltArtifact]
        The thing to export. The leaf nodes must all be :class:`BuiltArtifact`
        instances.
    outdir : pathlib.Path
        Path to the output directory where artifacts will be copied.
    prefix : str
        String to prepend between output directory path and the keys of the
        children. If the thing being exported is a :class:`BuiltArtifact`,
        this is simply the filename.
    hooks : Optional[ExportHooks]
        Hooks to be invoked during export. If not provided, a default instance
        with no registered implementations will be used.

    Returns
    -------
    type(root)
        A copy of the root, but with all leaf artifact nodes replace by
        :class:`ExportedArtifact` instances. Artifacts which have not yet
        been released are still converted to ExportedArtifact, but their ``path``
        is set to ``None``.

    Notes
    -----
    The prefix is build up recursively, so that calling this function on a
    universe will export each artifact to
    ``<prefix><collection_key>/<publication_key>/<artifact_key>``

    """
    if hooks is None:
        hooks = ExportHooks()

    if isinstance(root, BuiltArtifact):
        return _export_artifact(root, outdir, prefix, hooks)

    if isinstance(root, Artifact) and not isinstance(root, BuiltArtifact):
        raise ValueError("Cannot export an unbuilt artifact.")

    new_children = {}
    for child_key, child in root._children.items():
        hook_args = ExportNodeHookArgs(key=child_key, node_type=node_type_name(child))
        hooks.on_export_node(hook_args)
        new_prefix = str(pathlib.Path(prefix) / child_key)

        assert isinstance(child, (Universe, Collection, Publication, Artifact))
        new_children[child_key] = export(child, outdir, new_prefix, hooks)

    result = root._replace_children(new_children)
    return cast(
        Universe[ExportedArtifact]
        | Collection[ExportedArtifact]
        | Publication[ExportedArtifact]
        | ExportedArtifact,
        result,
    )
