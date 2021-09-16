import argparse
import datetime
import pathlib

from automata.materials.api import build_materials


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

    build_materials_parser = subparsers.add_parser('build-materials')
    _register_build_materials_parser(build_materials_parser)

    args = parser.parse_args(argv)
    args.cmd(args)


def _register_build_materials_parser(parser):
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
    parser.set_defaults(cmd=build_materials)
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
        "--start-of-week-one",
        type=datetime.date.fromisoformat,
        default=None,
        help="the start of week one. used for smart dates in publication files.",
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