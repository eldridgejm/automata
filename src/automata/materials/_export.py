"""Provides export(), which publishes materials by copying them to a new directory."""

import pathlib
import shutil
from typing import Optional

from ._types import (
    BuiltArtifact,
    ExportedArtifact,
    Universe,
    Collection,
    Publication,
    Artifact,
)


# exporting
# --------------------------------------------------------------------------------------


class ExportCallbacks:
    """Callbacks used by :func:`export`."""

    def on_copy(self, src: pathlib.Path, dst: pathlib.Path):
        """Called when copying a file."""
        return src, dst

    def on_export(self, key: str, node: Universe | Collection | Publication | Artifact):
        """When export is called on a node."""
        return key, node


def _export_artifact(
    built_artifact: BuiltArtifact,
    outdir: pathlib.Path,
    filename: str,
    callbacks: ExportCallbacks,
):
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
    callbacks : ExportCallbacks
        Callbacks to be invoked during the publication.

    """
    # actually copy the artifact
    full_dst = outdir / filename
    full_dst.parent.mkdir(parents=True, exist_ok=True)
    full_src = built_artifact.workdir / built_artifact.path
    callbacks.on_copy(full_src, full_dst)

    if full_src.is_dir():
        shutil.copytree(full_src, full_dst)
    else:
        shutil.copy(full_src, full_dst)

    return ExportedArtifact(path=str(full_dst.relative_to(outdir)))


def export(
    root: Universe | Collection | Publication | BuiltArtifact,
    outdir: pathlib.Path,
    prefix: str = "",
    callbacks: Optional[ExportCallbacks] = None,
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
    callbacks : Optional[ExportCallbacks]
        Callbacks to be invoked during the publication. If omitted, no
        callbacks are executed. See :class:`ExportCallbacks` for the possible
        callbacks and their arguments.

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
    if callbacks is None:
        callbacks = ExportCallbacks()

    if isinstance(root, BuiltArtifact):
        return _export_artifact(root, outdir, prefix, callbacks)

    if isinstance(root, Artifact) and not isinstance(root, BuiltArtifact):
        raise ValueError("Cannot export an unbuilt artifact.")

    new_children = {}
    for child_key, child in root._children.items():
        callbacks.on_export(child_key, child)
        new_prefix = str(pathlib.Path(prefix) / child_key)

        assert isinstance(child, (Universe, Collection, Publication, BuiltArtifact))
        new_children[child_key] = export(child, outdir, new_prefix, callbacks)

    return root._replace_children(new_children)
