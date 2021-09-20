import argparse
import datetime
import pathlib
import textwrap

import yaml


import automata.lib.materials as mlib

# cli
# --------------------------------------------------------------------------------------


def publish(
    input_directory,
    output_directory,
    ignore_release_time=False,
    artifact_filter=None,
    vars=None,
    skip_directories=None,
    verbose=False,
    now=None,
):

    input_directory = pathlib.Path(input_directory)
    output_directory = pathlib.Path(output_directory)

    if now is None:
        now = datetime.datetime.now
    else:
        _now = now

        def now():
            return _now

    # construct callbacks for printing information to the screen. start with
    # helper functions for formatting terminal output

    def _header(message):
        return "\u001b[1m" + message + "\u001b[0m"

    def _normal(message):
        return message

    def _body(message):
        return "\u001b[2m" + message + "\u001b[0m"

    def _warning(message):
        return "\u001b[33m" + message + "\u001b[0m"

    def _success(message):
        return "\u001b[32m" + message + "\u001b[0m"

    def _error(message):
        return "\u001b[31m" + message + "\u001b[0m"

    # the callbacks

    class CLIDiscoverCallbacks(mlib.DiscoverCallbacks):
        def on_publication(self, path):
            publication_name = str(path.parent)
            print(f"{_normal(publication_name)}")

        def on_skip(self, path):
            relpath = path.relative_to(input_directory)
            print(_warning(f"Skipping directory {relpath}"))

    class CLIBuildCallbacks(mlib.BuildCallbacks):
        def on_build(self, key, node):
            if isinstance(node, mlib.UnbuiltArtifact):
                relative_workdir = node.workdir.relative_to(input_directory.absolute())
                path = relative_workdir / key
                msg = _normal(str(path))
                print(msg, end="")

        def on_too_soon(self, node):
            msg = (
                f"   Release time {node.release_time} has not yet been reached. "
                "Skipping."
            )
            if isinstance(node, mlib.UnbuiltArtifact):
                print(_warning(msg))

            else:
                for key, artifact in node.artifacts.items():
                    relative_workdir = artifact.workdir.relative_to(
                        input_directory.absolute()
                    )
                    path = relative_workdir / key
                    print(str(path) + " " + _warning(msg))

        def on_missing(self, node):
            print(_warning(" file missing, but missing_ok=True"))

        def on_not_ready(self, node):
            msg = f"not ready → skipping"

            if isinstance(node, mlib.UnbuiltArtifact):
                print(_warning(f" {msg}"))

            else:
                for key, artifact in node.artifacts.items():
                    relative_workdir = artifact.workdir.relative_to(
                        input_directory.absolute()
                    )
                    path = relative_workdir / key
                    print(str(path) + " " + _warning(msg))

        def on_success(self, output):
            print(_success("   build was successful ✓"))

    class CLIFilterCallbacks(mlib.FilterCallbacks):
        def on_miss(self, x):
            key = f"{x.collection_key}/{x.publication_key}/{x.artifact_key}"
            print(_warning(f"\tRemoving {key}"))

        def on_hit(self, x):
            key = f"{x.collection_key}/{x.publication_key}/{x.artifact_key}"
            print(_success(f"\tKeeping {key}"))

    class CLIPublishCallbacks(mlib.PublishCallbacks):
        def on_copy(self, src, dst):
            src = src.relative_to(input_directory.absolute())
            dst = dst.relative_to(output_directory)
            msg = f"<input_directory>/{src} to <output_directory>/{dst}."
            print(_normal(msg))

    # begin the discover -> build -> publish process

    print()
    print(_header("Discovered publications:"))

    discovered = mlib.discover(
        input_directory,
        skip_directories=skip_directories,
        vars=vars,
        callbacks=CLIDiscoverCallbacks(),
    )

    if artifact_filter is not None:
        # filter out artifacts whose keys do not match this string

        def keep(k, v):
            if not isinstance(v, mlib.UnbuiltArtifact):
                return True
            else:
                return k == artifact_filter

        discovered = mlib.filter_nodes(
            discovered, keep, remove_empty_nodes=True, callbacks=CLIFilterCallbacks()
        )

    print()
    print(_header("Building:"))

    built = mlib.build(
        discovered,
        callbacks=CLIBuildCallbacks(),
        ignore_release_time=ignore_release_time,
        verbose=verbose,
        now=now,
    )

    print()
    print(_header("Copying:"))
    published = mlib.publish(built, output_directory, callbacks=CLIPublishCallbacks())

    # serialize the results
    with (output_directory / "materials.json").open("w") as fileobj:
        fileobj.write(mlib.serialize(published))
