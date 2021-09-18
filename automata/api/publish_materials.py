import argparse
import datetime
import pathlib
import textwrap

import yaml


from automata.lib.materials._discover import DiscoverCallbacks, discover
from automata.lib.materials._build import BuildCallbacks, build
from automata.lib.materials._filter import FilterCallbacks, filter_nodes
from automata.lib.materials._publish import PublishCallbacks, publish
from automata.lib.materials._serialize import serialize
from automata.lib.materials.types import UnbuiltArtifact


# cli
# --------------------------------------------------------------------------------------


def publish_materials(args):
    if args.now is None:
        now = datetime.datetime.now
    else:
        try:
            n_days = int(args.now)
            _now = datetime.datetime.now() + datetime.timedelta(days=n_days)
        except ValueError:
            _now = datetime.datetime.fromisoformat(args.now)

        def now():
            return _now

    if args.vars is None:
        external_variables = None
    else:
        name, path = args.vars
        with open(path) as fileobj:
            values = yaml.load(fileobj, Loader=yaml.Loader)
        external_variables = {name: values}

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

    class CLIDiscoverCallbacks(DiscoverCallbacks):
        def on_publication(self, path):
            publication_name = str(path.parent)
            print(f"{_normal(publication_name)}")

        def on_skip(self, path):
            relpath = path.relative_to(args.input_directory)
            print(_warning(f"Skipping directory {relpath}"))

    class CLIBuildCallbacks(BuildCallbacks):
        def on_build(self, key, node):
            if isinstance(node, UnbuiltArtifact):
                relative_workdir = node.workdir.relative_to(
                    args.input_directory.absolute()
                )
                path = relative_workdir / key
                msg = _normal(str(path))
                print(msg, end="")

        def on_too_soon(self, node):
            msg = (
                f"   Release time {node.release_time} has not yet been reached. "
                "Skipping."
            )
            if isinstance(node, UnbuiltArtifact):
                print(_warning(msg))

            else:
                for key, artifact in node.artifacts.items():
                    relative_workdir = artifact.workdir.relative_to(
                        args.input_directory.absolute()
                    )
                    path = relative_workdir / key
                    print(str(path) + " " + _warning(msg))

        def on_missing(self, node):
            print(_warning(" file missing, but missing_ok=True"))

        def on_not_ready(self, node):
            msg = f"not ready → skipping"

            if isinstance(node, UnbuiltArtifact):
                print(_warning(f" {msg}"))

            else:
                for key, artifact in node.artifacts.items():
                    relative_workdir = artifact.workdir.relative_to(
                        args.input_directory.absolute()
                    )
                    path = relative_workdir / key
                    print(str(path) + " " + _warning(msg))

        def on_success(self, output):
            print(_success("   build was successful ✓"))

    class CLIFilterCallbacks(FilterCallbacks):
        def on_miss(self, x):
            key = f"{x.collection_key}/{x.publication_key}/{x.artifact_key}"
            print(_warning(f"\tRemoving {key}"))

        def on_hit(self, x):
            key = f"{x.collection_key}/{x.publication_key}/{x.artifact_key}"
            print(_success(f"\tKeeping {key}"))

    class CLIPublishCallbacks(PublishCallbacks):
        def on_copy(self, src, dst):
            src = src.relative_to(args.input_directory.absolute())
            dst = dst.relative_to(args.output_directory)
            msg = f"<input_directory>/{src} to <output_directory>/{dst}."
            print(_normal(msg))

    # begin the discover -> build -> publish process

    print()
    print(_header("Discovered publications:"))

    discovered = discover(
        args.input_directory,
        skip_directories=args.skip_directories,
        external_variables=external_variables,
        callbacks=CLIDiscoverCallbacks(),
    )

    if args.artifact_filter is not None:
        # filter out artifacts whose keys do not match this string

        def keep(k, v):
            if not isinstance(v, UnbuiltArtifact):
                return True
            else:
                return k == args.artifact_filter

        discovered = filter_nodes(
            discovered, keep, remove_empty_nodes=True, callbacks=CLIFilterCallbacks()
        )

    print()
    print(_header("Building:"))

    built = build(
        discovered,
        callbacks=CLIBuildCallbacks(),
        ignore_release_time=args.ignore_release_time,
        verbose=args.verbose,
        now=now,
    )

    print()
    print(_header("Copying:"))
    published = publish(built, args.output_directory, callbacks=CLIPublishCallbacks())

    # serialize the results
    with (args.output_directory / "materials.json").open("w") as fileobj:
        fileobj.write(serialize(published))