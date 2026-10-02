"""Provides build(), which recursively builds artifacts."""

import dataclasses
import datetime
import pathlib
import subprocess
from typing import Any, Optional, TypedDict, Unpack, cast, overload

from automata.hooks import (
    BuildArtifactHookArgs,
    BuildArtifactSuccessHookArgs,
    BuildHooks,
    BuildMaterialsNodeHookArgs,
)

from ._types import (
    BuiltArtifact,
    Collection,
    ExportedArtifact,
    Publication,
    UnbuiltArtifact,
    Universe,
    node_type_name,
)
from .exceptions import BuildError


def _artifact_to_hook_args(artifact: UnbuiltArtifact) -> BuildArtifactHookArgs:
    """Convert an UnbuiltArtifact to BuildArtifactHookArgs."""
    release_time = artifact.release_time.isoformat() if artifact.release_time else None
    return BuildArtifactHookArgs(
        workdir=artifact.workdir,
        path=artifact.path,
        recipe=artifact.recipe,
        release_time=release_time,
        ready=artifact.ready,
        missing_ok=artifact.missing_ok,
    )


# how many lines of a failed recipe's output to show
_OUTPUT_LINES_SHOWN = 30


def _describe_output(output: str | None) -> str:
    """The end of a recipe's output, for an error message."""
    if output is None:
        return "\n(See the recipe's output shown above.)"
    lines = output.rstrip("\n").splitlines()
    if not lines:
        return "\n(The recipe printed no output.)"
    if len(lines) <= _OUTPUT_LINES_SHOWN:
        header = "Output:"
    else:
        header = f"Output (last {_OUTPUT_LINES_SHOWN} of {len(lines)} lines):"
    shown = lines[-_OUTPUT_LINES_SHOWN:]
    return f"\n{header}\n" + "\n".join(f"  {line}" for line in shown)


def _escape(value: object) -> str:
    """Escape braces so a value can go into a BuildError summary."""
    return str(value).replace("{", "{{").replace("}", "}}")


def _build_artifact(
    artifact: UnbuiltArtifact,
    *,
    ignore_release_time=False,
    ignore_ready=False,
    current_time: datetime.datetime | None = None,
    verbose=False,
    run=subprocess.run,
    exists=pathlib.Path.exists,
    hooks: BuildHooks,
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
    current_time : datetime.datetime | None
        The current time to use for release time comparisons.
        Default: None (uses system time).

    Returns
    -------
    Optional[BuiltArtifact]
        A summary of the build results. The result is `None` if the build time
        is in the future, or if the artifact was not created and missing_ok is
        True.

    """
    if current_time is None:
        current_time = datetime.datetime.now()

    output = BuiltArtifact(workdir=artifact.workdir, path=artifact.path)

    if (
        not ignore_release_time
        and artifact.release_time is not None
        and artifact.release_time > current_time
    ):
        hooks.on_build_artifact_too_soon(_artifact_to_hook_args(artifact))
        return None

    if not artifact.ready and not ignore_ready:
        hooks.on_build_artifact_not_ready(_artifact_to_hook_args(artifact))
        return None

    if artifact.recipe is None:
        stdout = None
        stderr = None
        returncode = None
    else:
        hooks.on_build_artifact_recipe(_artifact_to_hook_args(artifact))

        kwargs = {
            "cwd": artifact.workdir,
        }
        if not verbose:
            # one stream, so stdout and stderr stay in the order printed
            kwargs["stdout"] = subprocess.PIPE  # type: ignore
            kwargs["stderr"] = subprocess.STDOUT  # type: ignore

        proc = run(artifact.recipe, shell=True, **kwargs)
        if isinstance(proc.stdout, bytes):
            captured = proc.stdout.decode(errors="replace")
        elif isinstance(proc.stdout, str):
            captured = proc.stdout
        else:
            captured = None  # not captured (verbose): it went to the terminal

        if proc.returncode:
            raise BuildError(
                f"Building {{name}} failed (exit status {proc.returncode}).",
                fallback_name=_escape(artifact.workdir / artifact.path),
                details=(
                    f"\n  recipe: {artifact.recipe}\n  in: {artifact.workdir}"
                    + _describe_output(captured)
                ),
            )

        returncode = proc.returncode
        stdout = captured
        stderr = None

    path = artifact.workdir / artifact.path
    if not exists(path):
        if artifact.missing_ok:
            hooks.on_build_artifact_missing(_artifact_to_hook_args(artifact))
            return None
        elif artifact.recipe is not None:
            raise BuildError(
                f"Recipe for {{name}} finished, but {_escape(artifact.path)} was "
                f"not created (expected at {_escape(path)}).",
                fallback_name=_escape(path),
                details=(
                    f"\n  recipe: {artifact.recipe}\n  in: {artifact.workdir}"
                    + _describe_output(stdout)
                ),
            )
        else:
            raise BuildError(
                f"Artifact {{name}} has no recipe, and its file {_escape(path)} "
                f"does not exist.",
                fallback_name=_escape(path),
            )

    output = dataclasses.replace(
        output, returncode=returncode, stdout=stdout, stderr=stderr
    )
    hooks.on_build_artifact_success(
        BuildArtifactSuccessHookArgs(
            workdir=output.workdir,
            path=output.path,
            returncode=output.returncode,
        )
    )
    return output


# overloads for build() ----------------------------------------------------------------

# The following overloads are used to provide type hints for the build()
# function. Standard generics won't work here, because the return type of
# build() depends on the type of the input.


class BuildOptions(TypedDict, total=False):
    ignore_release_time: bool
    ignore_ready: bool
    verbose: bool
    hooks: Optional[BuildHooks]
    run: Any
    current_time: Optional[datetime.datetime]
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
    hooks: Optional[BuildHooks] = None,
    current_time: datetime.datetime | None = None,
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
    hooks : BuildHooks
        A :class:`Hooks` instance containing hooks to be invoked at various
        points during the build process. If not provided, a default instance
        with no registered implementations will be used.

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
    if hooks is None:
        hooks = BuildHooks()

    kwargs = dict(
        ignore_release_time=ignore_release_time,
        ignore_ready=ignore_ready,
        current_time=current_time,
        run=run,
        verbose=verbose,
        exists=exists,
        hooks=hooks,
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

        hook_args = BuildMaterialsNodeHookArgs(
            key=child_key, node_type=node_type_name(child)
        )
        hooks.on_build_materials_node(hook_args)

        try:
            result = build(child, **kwargs)  # type: ignore
        except BuildError as error:
            # record the artifact's name (e.g. homeworks/01-intro/homework.pdf)
            if child_key != ".":
                error.key_path.insert(0, child_key)
            raise
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
