import argparse
import datetime
import json
import pathlib
import sys

import yaml

import automata.api.materials
import automata.api.coursepage
import automata.api.sync
import automata.lib.materials

from automata import util


def _arg_directory(s):
    path = pathlib.Path(s)
    if not path.is_dir():
        raise argparse.ArgumentTypeError("Not a directory.")
    return path


def _arg_output_directory(s):
    path = pathlib.Path(s)

    if not path.exists():
        path.mkdir(parents=True)
        return path

    return _arg_directory(path)


def cli(argv=None):
    args = _parse_args(argv)
    args.cmd(args)


def _usage_printer(parser):
    def print_usage(*args):
        parser.print_usage()
        sys.exit(128)

    return print_usage


def _parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.set_defaults(cmd=_usage_printer(parser))

    subparsers = parser.add_subparsers()

    _register_materials_parser(subparsers)
    _register_coursepage_parser(subparsers)
    _register_sync_parser(subparsers)

    args = parser.parse_args(argv)

    return args


def _register_materials_parser(subparsers):
    parser = subparsers.add_parser("materials")
    parser.set_defaults(cmd=_usage_printer(parser))

    subparsers = parser.add_subparsers()

    _register_materials_publish_parser(subparsers)
    _register_materials_resolve_parser(subparsers)
    _register_materials_status_parser(subparsers)


def _register_materials_publish_parser(subparsers):
    parser = subparsers.add_parser("publish")

    def cmd(args):
        if args.vars is not None:
            args.vars = util.load_yaml(args.vars)

        return automata.api.materials.publish(
            args.input_directory,
            args.output_directory,
            ignore_release_time=args.ignore_release_time,
            ignore_ready=args.ignore_ready,
            artifact_filter=args.artifact_filter,
            vars=args.vars,
            skip_directories=args.skip_directories,
            verbose=args.verbose,
            now=args.now,
        )

    parser.set_defaults(cmd=cmd)
    parser.add_argument("output_directory", type=_arg_output_directory)
    parser.add_argument(
        "--input-directory", type=_arg_directory, default=pathlib.Path.cwd()
    )
    parser.add_argument(
        "--skip-directories",
        type=str,
        nargs="+",
        help="directories that will be ignored during discovery",
    )
    parser.add_argument(
        "--ignore-release-time",
        action="store_true",
        help="if provided, artifacts whose release time is in the future will still be built and published",
    )
    parser.add_argument(
        "--ignore-ready",
        action="store_true",
        help="if provided, artifacts marked as unready will still be built and published",
    )
    parser.add_argument(
        "--artifact-filter",
        type=str,
        default=None,
        help="artifacts will be built and published only if their key matches this string",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="let stdout and stderr through when building artifacts",
    )
    parser.add_argument(
        "--now", default=None, help="run as if this is the current time"
    )
    parser.add_argument(
        "--vars",
        type=pathlib.Path,
        default=None,
        help="A yaml file whose contents will be available in discovery as template variables.",
    )


def _register_materials_resolve_parser(subparsers):
    parser = subparsers.add_parser("resolve")

    def cmd(args):
        if args.vars is not None:
            args.vars = util.load_yaml(args.vars)

        node = automata.api.materials.resolve(
            args.path,
            vars=args.vars,
        )

        if args.format == 'json':
            print(automata.lib.materials.serialize(node))
        elif args.format == 'yaml':
            print(yaml.dump(dct._deep_asdict(), Dumper=yaml.Dumper))

    parser.set_defaults(cmd=cmd)
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument(
        "--vars",
        type=pathlib.Path,
        default=None,
        help="A yaml file whose contents will be available in discovery as template variables.",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=['json', 'yaml'],
        default='json',
        help="The output format.",
    )


def _register_materials_status_parser(subparsers):
    parser = subparsers.add_parser("status")

    parser.add_argument(
        "--skip-directories",
        type=str,
        nargs="+",
        help="directories that will be ignored during discovery",
    )

    def cmd(args):
        automata.api.materials.status(
                skip_directories=args.skip_directories
        )

    parser.set_defaults(cmd=cmd)


def _register_coursepage_parser(subparsers):
    parser = subparsers.add_parser("coursepage")
    parser.set_defaults(cmd=_usage_printer(parser))

    subparsers = parser.add_subparsers()

    _register_coursepage_build_parser(subparsers)
    _register_coursepage_init_parser(subparsers)


def _register_coursepage_build_parser(subparsers):
    parser = subparsers.add_parser("build")

    parser.add_argument("output_directory")
    parser.add_argument("--input-directory", default=pathlib.Path.cwd())
    parser.add_argument("--materials")
    parser.add_argument("--now")
    parser.add_argument("--vars", type=pathlib.Path)

    def cmd(args):
        vars = {}
        if args.vars is not None:
            with args.vars.open() as fileobj:
                vars = yaml.load(fileobj, Loader=yaml.Loader)

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

            print(f"Running as if it is currently {_now}")

        automata.api.coursepage.build(
            args.input_directory,
            args.output_directory,
            args.materials,
            vars=vars,
            now=now,
        )

    parser.set_defaults(cmd=cmd)


def _register_coursepage_init_parser(subparsers):
    parser = subparsers.add_parser("init")

    def cmd(args):
        automata.api.coursepage.initialize(args.output_path)

    parser.add_argument("output_path")
    parser.set_defaults(cmd=cmd)

def _register_sync_parser(subparsers):
    parser = subparsers.add_parser("sync")
    parser.set_defaults(cmd=_usage_printer(parser))

    subparsers = parser.add_subparsers()

    _register_sync_git_branch_parser(subparsers)


def _register_sync_git_branch_parser(subparsers):
    parser = subparsers.add_parser('git')
    parser.add_argument('local_directory')
    parser.add_argument('git_repo_url')
    parser.add_argument('branch')

    def cmd(args):
        return automata.api.sync.git(args.local_directory, args.git_repo_url, args.branch)

    parser.set_defaults(cmd=cmd)

