"""Provides build(), which recursively builds artifacts."""

import dataclasses
import datetime
import pathlib
import subprocess
from typing import Any, Optional, TypedDict, Union, Unpack, cast, overload

from ._types import (
    BuiltArtifact,
    Collection,
    ExportedArtifact,
    Publication,
    UnbuiltArtifact,
    Universe,
)
from .exceptions import BuildError


class BuildCallbacks:
    """Callbacks used by :func:`build`.

    To provide callbacks to :func:`build`, subclass this class and override
    the methods you want to use. The methods that are not overridden will be
    no-ops.

    """

    def on_build(self, key: str, node: Union[Collection, Publication, UnbuiltArtifact]):
        """Called when building a collection/publication/artifact.

        Parameters
        ----------
        key : str
            The key of the node. Generally, this is the relative path to the
            node from the root.
        node : Collection | Publication | UnbuiltArtifact
            The node whose artifacts are being built.

        """
        return key, node

    def on_too_soon(self, artifact: UnbuiltArtifact):
        """Called when it is too soon to release the artifact."""
        return artifact

    def on_not_ready(self, artifact: UnbuiltArtifact):
        """Called when the artifact is not ready."""
        return artifact

    def on_missing(self, artifact: UnbuiltArtifact):
        """Called when the artifact is missing, but missing is OK."""
        return artifact

    def on_recipe(self, artifact: UnbuiltArtifact):
        """Called when artifact is being built using its recipe."""
        return artifact

    def on_success(self, artifact: BuiltArtifact):
        """Called when the build succeeded."""
        return artifact


def _build_artifact(
    artifact: UnbuiltArtifact,
    *,
    ignore_release_time=False,
    ignore_ready=False,
    now=datetime.datetime.now,
    verbose=False,
    run=subprocess.run,
    exists=pathlib.Path.exists,
    callbacks: BuildCallbacks,
):
    """Build an artifact using its recipe.

    This private helper function is used by :func:`build` to build an artifact.
    It is not intended to be called by the user directly.

    Parameters
    ----------
    artifact : UnbuiltArtifact
        The artifact to build.
    ignore_release_time : bool
        If True, the release time of the artifact will be ignored, and it will
        be built anyways. Default: False.
    ignore_ready : bool
        If True, the readiness of an artifact will be ignored, and it will
        be built anyways. Default: False.
    now : Callable[[], datetime.datetime]
        A function which returns the current time. Default: datetime.datetime.now.
        This can be used to mock the current time for testing.

    Returns
    -------
    Optional[BuiltArtifact]
        A summary of the build results. The result is `None` if the build time
        is in the future, or if the artifact was not created and missing_ok is
        True.

    """
    output = BuiltArtifact(workdir=artifact.workdir, path=artifact.path)

    if (
        not ignore_release_time
        and artifact.release_time is not None
        and artifact.release_time > now()
    ):
        callbacks.on_too_soon(artifact)
        return None

    if not artifact.ready and not ignore_ready:
        callbacks.on_not_ready(artifact)
        return None

    if artifact.recipe is None:
        stdout = None
        stderr = None
        returncode = None
    else:
        callbacks.on_recipe(artifact)

        kwargs = {
            "cwd": artifact.workdir,
        }
        if not verbose:
            kwargs["stdout"] = subprocess.PIPE  # type: ignore
            kwargs["stderr"] = subprocess.PIPE  # type: ignore

        proc = run(artifact.recipe, shell=True, **kwargs)

        if proc.returncode:
            msg = "There was a problem while building the artifact"
            if proc.stderr is not None:
                msg += f":\n{proc.stderr.decode()}"
            raise BuildError(msg)

        returncode = proc.returncode
        stdout = None if proc.stdout is None else proc.stdout.decode()
        stderr = None if proc.stderr is None else proc.stderr.decode()

    path = artifact.workdir / artifact.path
    if not exists(path):
        if artifact.missing_ok:
            callbacks.on_missing(artifact)
            return None
        else:
            raise BuildError(f"Artifact {path} does not exist at {path}.")

    output = dataclasses.replace(
        output, returncode=returncode, stdout=stdout, stderr=stderr
    )
    callbacks.on_success(output)
    return output


# overloads for build() ----------------------------------------------------------------

# The following overloads are used to provide type hints for the build()
# function. Standard generics won't work here, because the return type of
# build() depends on the type of the input.


class BuildOptions(TypedDict, total=False):
    ignore_release_time: bool
    ignore_ready: bool
    verbose: bool
    callbacks: Optional[BuildCallbacks]
    run: Any
    now: Any
    exists: Any


@overload
def build(
    root: Universe[UnbuiltArtifact], **kwargs: Unpack[BuildOptions]
) -> Universe[BuiltArtifact]: ...


@overload
def build(
    root: Collection[UnbuiltArtifact], **kwargs: Unpack[BuildOptions]
) -> Collection[BuiltArtifact]: ...


@overload
def build(
    root: Publication[UnbuiltArtifact], **kwargs: Unpack[BuildOptions]
) -> Publication[BuiltArtifact]: ...


@overload
def build(root: UnbuiltArtifact, **kwargs: Unpack[BuildOptions]) -> BuiltArtifact: ...


# build() ==============================================================================


def build(
    root: Universe[UnbuiltArtifact]
    | Collection[UnbuiltArtifact]
    | Publication[UnbuiltArtifact]
    | UnbuiltArtifact,
    *,
    ignore_release_time: bool = False,
    ignore_ready: bool = False,
    verbose: bool = False,
    callbacks: Optional[BuildCallbacks] = None,
    now=datetime.datetime.now,
    run=subprocess.run,
    exists=pathlib.Path.exists,
) -> (
    Universe[BuiltArtifact]
    | Collection[BuiltArtifact]
    | Publication[BuiltArtifact]
    | BuiltArtifact
):
    """Build all artifacts contained under the given root node.

    Parameters
    ----------
    root : Universe | Collection | Publication | UnbuiltArtifact
        The thing to build. Operates recursively, so if given a
        universe, collection, or publication, it will build all of the
        artifacts within. All of the artifacts must be instances of
        :class:`UnbuiltArtifact`.
    ignore_release_time : bool
        If ``True``, all artifacts will be built, even if their release time
        has not yet passed.
    ignore_ready : bool
        If ``True``, all artifacts will be built, even if they are marked as
        not ready.
    callbacks : BuildCallbacks
        An instance of :class:`BuildCallbacks` that contains methods that will
        be invoked as callbacks at various points during the build process. See
        :class:`BuildCallbacks` for the possible methods and their meanings. If
        this argument is not provided, a default set of no-op callbacks will be
        used.

    Returns
    -------
    Optional[type(root)]
        A copy of the root where each leaf artifact is replaced with
        an instance of :class:`BuiltArtifact`. If the thing to be built is not
        built due to being unreleased, ``None`` is returned.

    Note
    ----
    If a publication or artifact is not yet released, either due to its release
    time being in the future or because it is marked as not ready, its recipe
    will not be run. If the root node is a publication or artifact that is not
    built, the result of this function is None. If the root node is a
    collection or universe, all of the unbuilt publications and artifacts
    within are recursively removed from the tree, so that all leaf nodes in the
    tree are in fact :class:`BuiltArtifact` instances.

    If an artifact is encountered that isn't an instance of :class:`UnbuiltArtifact`,
    an exception is raised.

    """
    if callbacks is None:
        callbacks = BuildCallbacks()

    kwargs = dict(
        ignore_release_time=ignore_release_time,
        ignore_ready=ignore_ready,
        now=now,
        run=run,
        verbose=verbose,
        exists=exists,
        callbacks=callbacks,
    )

    if isinstance(root, UnbuiltArtifact):
        return _build_artifact(root, **kwargs)  # type: ignore

    # recursively build the children
    new_children = {}
    for child_key, child in root._children.items():
        # check if it is already built, and skip it if so
        if isinstance(child, BuiltArtifact) or isinstance(child, ExportedArtifact):
            raise ValueError("Cannot build an already built artifact.")

        assert isinstance(child, (Collection, Publication, UnbuiltArtifact))

        callbacks.on_build(child_key, child)
        result = build(child, **kwargs)  # type: ignore
        # if a node is not built (perhaps due to it not being ready), the
        # result is None. this next conditional prevents such nodes from
        # appearing in the tree
        if result is not None:
            new_children[child_key] = result

    result = root._replace_children(new_children)
    return cast(
        Universe[BuiltArtifact]
        | Collection[BuiltArtifact]
        | Publication[BuiltArtifact],
        result,
    )
