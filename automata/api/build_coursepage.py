import datetime
import pathlib
import shutil

import yaml

from . import _coursepage


PageError = _coursepage.PageError


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

    abstract(
        args.input_path, args.output_path, args.materials, context=context, now=now
    )


def abstract(
    input_path,
    output_path,
    published_path=None,
    context=None,
    now=datetime.datetime.now,
):
    if context is None:
        context = {}

    input_path = pathlib.Path(input_path)
    output_path = pathlib.Path(output_path)
    if published_path is not None:
        published_path = pathlib.Path(published_path)

    # create the output path, if it doesn't already exist
    output_path.mkdir(exist_ok=True)

    # load the publications and update their paths
    if published_path is not None:
        published = _coursepage.load_published(published_path, output_path)
    else:
        published = None

    # load the configuration file
    config = _coursepage.load_config(input_path / "config.yaml", context=context)

    # validate the config against the theme's schema
    _coursepage.validate_theme_schema(input_path, config)

    # create environments for evaluation of base templates and element templates
    element_environment = _coursepage.create_element_environment(input_path)
    base_environment =_coursepage.create_base_template_environment(input_path)

    # construct the variables used during page rendering
    variables = {
        "context": context,
        "elements": _coursepage.Elements(environment=element_environment, now=now),
        "config": config,
        "published": published,
    }

    # convert user pages
    for old_path, new_path in _coursepage.all_pages(input_path, output_path):
        interpolated = _coursepage.render_page(old_path, variables)
        body_html = _coursepage.convert_markdown_to_html(interpolated)
        html = _coursepage.render_base(base_environment, body_html, config)

        with new_path.open("w") as fileobj:
            fileobj.write(html)

    # copy static files
    shutil.copytree(input_path / "theme" / "style", output_path / "style")
    shutil.copytree(input_path / "static", output_path / "static")
