"""Generate a static site with abstract.abstract"""
import argparse
import datetime
import pathlib
import functools
import shutil

import cerberus
import jinja2
import markdown
import yaml

import automata.lib.materials

from . import elements
from . import exceptions


def load_published(published_path, output_path):
    """Load artifacts from ``materials.json`` and update their paths.

    The artifacts in ``materials.json`` have a ``path`` attribute that gives
    their path relative to ``materials.json``. But we need the path to the
    artifact from the website root: the ``output_path``. This function loads the
    artifacts and performs the update.

    Some artifacts have ``None`` as their path. This signals that the artifact is
    defined, but not yet released. This function leaves such paths as ``None``.

    Parameters
    ----------
    published_path : pathlib.Path
        Path to the directory containing ``materials.json``.
    output_path : pathlib.Path
        Path to the output directory. This should be a directory under the
        output path.

    Returns
    -------
    published.Universe
        The universe of published artifacts, with each artifact's path updated
        to be relative to ``output_path``.

    """

    # read the universe
    with (published_path / "materials.json").open() as fileobj:
        published = automata.lib.materials.deserialize(fileobj.read())

    # we need to update their paths to be relative to output directory; this function
    # will do it for one artifact
    def _update_path(artifact):
        if artifact.path is None:
            return artifact

        relative_path = published_path.relative_to(output_path) / artifact.path
        return artifact._replace(path=relative_path)

    # apply the function to all artifacts, modifying `published`
    for collection in published.collections.values():
        for publication in collection.publications.values():
            for artifact_key, artifact in publication.artifacts.items():
                publication.artifacts[artifact_key] = _update_path(artifact)

    return published


def load_config(path, context=None):
    """Read the configuration from a yaml file, performing interpolation.

    Parameters
    ----------
    path : pathlib.Path
        The path to the configuration file.

    Returns
    -------
    dict
        The configuration dictionary.

    Note
    ----

    This loader supports the ``!include`` tag, allowing the configuration file
    to be split into several files. For instance:

    .. code-block:: yaml

        # config.yaml
        theme:
            page_title: My Website

        schedule: !include schedule.yaml
        announcements: !include announcements.yaml

    """
    if context is None:
        context = {}

    variables = {"context": context}

    # perform template interpolation
    with path.open() as fileobj:
        template = jinja2.Template(fileobj.read(), undefined=jinja2.StrictUndefined)

    rendered_yaml = template.render(**variables)

    # we'll subclass yaml.Loader and add a constructor
    class IncludingLoader(yaml.Loader):
        def include(self, node):
            included_path = path.parent / self.construct_scalar(node)
            with included_path.open() as fileobj:
                return yaml.load(fileobj, IncludingLoader)

    IncludingLoader.add_constructor("!include", IncludingLoader.include)

    return yaml.load(rendered_yaml, Loader=IncludingLoader)


class Elements:
    """A class to create closures for page elements.

    Used in abstract(). We instantiate Elements with a universe and a
    template loader. When an attribute of the instance is accessed, the element
    with that name will be pulled in from the elements module and its
    "templates" and "published" arguments will be closed over. The result is a
    function of one argument: the configuration.

    """

    def __init__(self, environment, now):
        self.environment = environment
        self.now = now

    def __getattr__(self, attr):
        try:
            func = getattr(elements, attr)
        except AttributeError:
            raise RuntimeError(f'There is no element named "{attr}".')
        return jinja2.contextfunction(
            functools.partial(func, self.environment, now=self.now)
        )


def render_page(path, variables):
    """Given page path and dict of variables, perform Jinja2 interpolation.

    Parameters
    ----------
    path : str
        The page'spath.
    variables : dict
        A dictionary mapping variable names to values available during
        interpolation.

    Returns
    -------
    str
        The input string after interpolation.

    Notes
    -----
    Variables are delimited by ${ }, and blocks are delimited by ${%  %}.

    """
    with path.open() as fileobj:
        contents = fileobj.read()

    template = jinja2.Template(contents, undefined=jinja2.StrictUndefined)

    try:
        return template.render(**variables)
    except jinja2.UndefinedError as exc:
        raise exceptions.PageError(f'Problem rendering "{path}": {exc}')


def convert_markdown_to_html(contents):
    """Convert markdown to HTML.

    Parameters
    ----------
    contents : str
        The markdown string.

    Returns
    -------
    str
        The HTML.

    """
    return markdown.markdown(contents, extensions=["toc"])


def all_pages(input_path, output_path):
    """Generate all page contents and their output paths.

    Parameters
    ----------
    input_path : pathlib.Path
        The path to the input. ``input_path / 'pages'`` should contain the pages.
    output_path : pathlib.Path
        The path to the directory where the rendered pages will be placed.

    Yields
    ------
    (str, pathlib.Path)
        The contents of the input page, along with the path to where the rendered
        page should be placed.

    """
    for page_path in (input_path / "pages").iterdir():
        root = input_path / "pages"
        new_path = output_path / page_path.relative_to(root).with_suffix(".html")

        yield page_path, new_path


def render_base(base_environment, body_html, config):
    return base_environment.get_template("page.html").render(
        body=body_html, config=config
    )


def validate_theme_schema(input_path, config):
    """Validate a config against the theme's schema."""
    with (input_path / "theme" / "schema.yaml").open() as fileobj:
        theme_schema = yaml.load(fileobj, Loader=yaml.Loader)

    validator = cerberus.Validator(theme_schema, allow_unknown=True, require_all=True)
    result = validator.validate(config)
    if not result:
        raise RuntimeError(f"Invalid theme config: {validator.errors}")


def create_element_environment(input_path):
    """Create the element environment and its custom filters."""
    element_environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(input_path / "theme" / "elements"),
        undefined=jinja2.StrictUndefined,
    )

    def evaluate(s, **kwargs):
        _DELIMITER_KWARGS = dict(
            variable_start_string="${",
            variable_end_string="}",
            block_start_string="${%",
            block_end_string="%}",
        )

        try:
            return jinja2.Template(
                s, **_DELIMITER_KWARGS, undefined=jinja2.StrictUndefined
            ).render(**kwargs)
        except jinja2.UndefinedError as exc:
            raise exceptions.ElementError(
                f'Unknown variable in template string "{s}": {exc}'
            )

    element_environment.filters["evaluate"] = evaluate
    element_environment.filters["markdown_to_html"] = convert_markdown_to_html

    return element_environment


def create_base_template_environment(input_path):
    """Create the base template environment."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(input_path / "theme" / "base_templates"),
        undefined=jinja2.StrictUndefined,
    )
