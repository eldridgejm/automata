import pathlib
import shutil

from ._types import BuiltArtifact, ExportedArtifact


# exporting
# --------------------------------------------------------------------------------------


class ExportCallbacks:
    """Callbacks used by :func:`export`."""

    def on_copy(self, src, dst):
        """Called when copying a file."""

    def on_export(self, key, node):
        """When export is called on a node."""


def _export_artifact(built_artifact, outdir, filename, callbacks):

    # actually copy the artifact
    full_dst = outdir / filename
    full_dst.parent.mkdir(parents=True, exist_ok=True)
    full_src = built_artifact.workdir / built_artifact.path
    callbacks.on_copy(full_src, full_dst)

    if full_src.is_dir():
        shutil.copytree(full_src, full_dst)
    else:
        shutil.copy(full_src, full_dst)

    return ExportedArtifact(path=full_dst.relative_to(outdir))


def export(root, outdir, prefix="", callbacks=None):
    """Export a universe/collection/publication/artifact by copying it.

    Parameters
    ----------
    root : Union[Universe, Collection, Publication, BuiltArtifact]
        The thing to export.
    outdir : pathlib.Path
        Path to the output directory where artifacts will be copied.
    prefix : str
        String to prepend between output directory path and the keys of the
        children. If the thing being exported is a :class:`BuiltArtifact`,
        this is simply the filename.
    callbacks : ExportCallbacks
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

    new_children = {}
    for child_key, child in root._children.items():
        callbacks.on_export(child_key, child)
        new_prefix = pathlib.Path(prefix) / child_key
        new_children[child_key] = export(child, outdir, new_prefix, callbacks)

    return root._replace_children(new_children)
