import datetime
import collections
import pathlib
import shutil
from functools import partial

import yaml

from . import _coursepage


PageError = _coursepage.PageError



def build_coursepage(
    input_path,
    output_path,
    materials_path=None,
    vars=None,
    now=datetime.datetime.now,
):
    if vars is None:
        vars = {}

    input_path = pathlib.Path(input_path)
    output_path = pathlib.Path(output_path)
    if materials_path is not None:
        materials_path = pathlib.Path(materials_path)

    # create the output path, if it doesn't already exist
    output_path.mkdir(exist_ok=True)

    # load the publications and update their paths
    if materials_path is not None:
        published = _coursepage.load_published(materials_path, output_path)
    else:
        published = None

    # load the configuration file
    config = _coursepage.load_config(input_path / "config.yaml", vars=vars)

    # validate the config against the theme's schema
    _coursepage.validate_theme_schema(input_path, config)

    # create environments for evaluation of base templates and element templates
    element_environment = _coursepage.create_element_environment(input_path)
    base_environment =_coursepage.create_base_template_environment(input_path)


    context = _coursepage.RenderContext(
            input_path=input_path,
            output_path=output_path,
            theme_path=input_path / 'theme',
            materials_path=materials_path,
            materials=published,
            config=config,
            vars=vars,
            now=now,
            environment=element_environment
    )

    Elements = collections.namedtuple('Elements', [
        'announcement_box',
        'button_bar',
        'schedule',
        'listing'
    ])

    elements = Elements(
        announcement_box=partial(_coursepage.elements.announcement_box, context),
        button_bar=partial(_coursepage.elements.button_bar, context),
        schedule=partial(_coursepage.elements.schedule, context),
        listing=partial(_coursepage.elements.listing, context),
    )

    # construct the variables used during page rendering
    variables = {
        "vars": vars,
        "elements": elements,
        "config": config,
        "published": published,
    }

    # convert user pages
    _coursepage.render_pages(input_path / 'pages', output_path, input_path / 'theme', elements, context)

    # copy static files
    shutil.copytree(input_path / "theme" / "style", output_path / "style")
    shutil.copytree(input_path / "static", output_path / "static")
