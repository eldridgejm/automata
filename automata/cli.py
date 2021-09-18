import argparse
import datetime
import pathlib

from automata.api.publish_materials import publish_materials
from automata.api.build_coursepage import build_coursepage


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


def _arg_vars_file(s):
    try:
        name, path = s.split(":")
    except ValueError:
        raise argparse.ArgumentTypeError(
            'Vars file argument must be of form "name:path"'
        )
    return name, path


def cli(argv=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    publish_materials = subparsers.add_parser("publish-materials")
    _register_publish_materials(publish_materials)

    build_coursepage_parser = subparsers.add_parser("build-coursepage")
    _register_build_coursepage_parser(build_coursepage_parser)

    args = parser.parse_args(argv)
    args.cmd(args)


def _register_publish_materials(parser):
    """The command line interface.

    Parameters
    ----------
    argv : List[str]
        A list of command line arguments. If None, the arguments will be read from the
        command line passed to the process by the shell.
    now : Callable[[], datetime.datetime]
        A callable producing the current datetime. This is useful when testing, as it
        allows you to inject a fixed, known time.

    """
    parser.set_defaults(cmd=publish_materials)
    parser.add_argument("input_directory", type=_arg_directory)
    parser.add_argument("output_directory", type=_arg_output_directory)
    parser.add_argument(
        "--skip-directories",
        type=str,
        nargs="+",
        help="directories that will be ignored during discovery",
    )
    parser.add_argument(
        "--ignore-release-time",
        action="store_true",
        help="if provided, all artifacts will be built and published regardless of release time",
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
        type=_arg_vars_file,
        default=None,
        help="A yaml file whose contents will be available in discovery as template variables.",
    )


def _register_build_coursepage_parser(parser):
    parser.add_argument("input_path")
    parser.add_argument("output_path")
    parser.add_argument("--published")
    parser.add_argument("--now")
    parser.add_argument("--context", type=pathlib.Path)
    parser.set_defaults(cmd=build_coursepage)
