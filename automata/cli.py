import argparse
import datetime
import pathlib

import yaml

import automata.api.materials
import automata.api.coursepage


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

    init_coursepage_parser = subparsers.add_parser("init-coursepage")
    _register_init_coursepage_parser(init_coursepage_parser)

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

    def _publish_materials(args):
        return automata.api.materials.publish(args.input_directory,
                args.output_directory,
                ignore_release_time=args.ignore_release_time,
                artifact_filter=args.artifact_filter,
                vars=args.vars,
                skip_directories=args.skip_directories,
                verbose=args.verbose,
                now=args.now
                )

    parser.set_defaults(cmd=_publish_materials)
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
    parser.add_argument("--materials")
    parser.add_argument("--now")
    parser.add_argument("--vars", type=pathlib.Path)
    parser.set_defaults(cmd=_build_coursepage_cli)


def _build_coursepage_cli(args):
    vars = {}
    if args.vars is not None:
        with args.vars.open() as fileobj:
            vars[args.vars.stem] = yaml.load(fileobj, Loader=yaml.Loader)

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
        args.input_path, args.output_path, args.materials, vars=vars, now=now
    )

def _register_init_coursepage_parser(parser):
    def _init_coursepage_cli(args):
        automata.api.coursepage.create(args.output_path)

    parser.add_argument('output_path')
    parser.set_defaults(cmd=_init_coursepage_cli)

