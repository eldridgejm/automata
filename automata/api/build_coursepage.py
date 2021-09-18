import datetime
import pathlib

import yaml

import automata.lib.coursepage


def build_coursepage(args):
    context = {}
    if args.context is not None:
        with args.context.open() as fileobj:
            context[args.context.stem] = yaml.load(fileobj, Loader=yaml.Loader)

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

    automata.lib.coursepage.abstract(
        args.input_path, args.output_path, args.published, context=context, now=now
    )
