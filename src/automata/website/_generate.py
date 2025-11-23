"""Generate a static site with the site generator."""

import collections
import dataclasses
import datetime
import pathlib
import shutil
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any, NamedTuple, cast

import jinja2
import markdown  # type: ignore
import smartconfig
import yaml  # type: ignore

import automata.materials

from . import elements, exceptions
from ._util import load_yaml


class RenderContext(NamedTuple):
    """Information that might be useful during the rendering of pages."""

    input_path: pathlib.Path
    output_path: pathlib.Path
    theme_path: pathlib.Path
    materials_path: pathlib.Path | None
    materials: automata.materials.Universe | None
    config: dict[str, Any]
    vars: dict[str, Any]
    now: datetime.datetime


def _load_materials(
    materials_path: pathlib.Path, output_path: pathlib.Path
) -> automata.materials.Universe:
    """Load artifacts from ``materials.json`` and update their paths.

    The artifacts in ``materials.json`` have a ``path`` attribute that gives
    their path relative to ``materials.json``. But we need the path to the
    artifact from the website root: the ``output_path``. This function loads the
    artifacts and performs the update.

    Some artifacts have ``None`` as their path. This signals that the artifact is
    defined, but not yet released. This function leaves such paths as ``None``.

    Parameters
    ----------
    materials_path : pathlib.Path
        Path to the directory containing ``materials.json``.
    output_path : pathlib.Path
        Path to the output directory. This should be a directory under the
        output path.

    Returns
    -------
    materials.Universe
        The universe of materials artifacts, with each artifact's path updated
        to be relative to ``output_path``.

    """

    # read the universe
    with (materials_path / "materials.json").open() as fileobj:
        materials = automata.materials.deserialize(fileobj.read())

    assert isinstance(materials, automata.materials.Universe)

    # we need to update their paths to be relative to output directory; this function
    # will do it for one artifact
    def _update_path(artifact):
        if artifact.path is None:
            return artifact

        relative_path = materials_path.relative_to(output_path) / artifact.path
        return dataclasses.replace(artifact, path=relative_path)

    # apply the function to all artifacts, modifying `materials`
    for collection in materials.collections.values():
        for publication in collection.publications.values():
            for artifact_key, artifact in publication.artifacts.items():
                publication.artifacts[artifact_key] = _update_path(artifact)

    return materials


def _load_config(
    path: pathlib.Path, vars: dict[str, Any] | None = None
) -> dict[str, Any]:
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
        template:
            page_title: My Website

        schedule: !include schedule.yaml
        announcements: !include announcements.yaml

    """
    if vars is None:
        vars = {}

    variables = {"vars": vars}

    dct = load_yaml(path)

    schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}
    result = smartconfig.resolve(dct, schema=schema, global_variables=variables)
    return cast(dict[str, Any], result)


def _validate_theme_schema(input_path: pathlib.Path, config: dict[str, Any]) -> None:
    """Validate a config against the theme's schema.

    Raises
    ------
    RuntimeError
        If the config is invalid according to the theme's schema.

    """
    with (input_path / "theme" / "schema.yaml").open() as fileobj:
        theme_schema = yaml.load(fileobj, Loader=yaml.Loader)

    try:
        smartconfig.resolve(config["theme"], theme_schema)
    except smartconfig.exceptions.ResolutionError as exc:
        raise RuntimeError(f"Invalid theme config: {exc}")


def _find_input_pages(
    input_path: pathlib.Path,
) -> Iterator[tuple[str, pathlib.Path]]:
    """Generate all page contents and their output paths.

    Parameters
    ----------
    input_path
        The path to the directory containing the pages.

    Yields
    ------
    tuple[str, pathlib.Path]
        The contents of the input page, along with the path to the page relative
        to the input path.

    """
    for page_path in input_path.iterdir():
        with page_path.open() as fileobj:
            contents = fileobj.read()

        relpath = page_path.relative_to(input_path)

        yield contents, relpath


def _interpolate(
    contents: str, variables: dict[str, Any], path: pathlib.Path | None = None
) -> str:
    template = jinja2.Template(
        contents,
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )
    try:
        return template.render(**variables)
    except jinja2.UndefinedError as exc:
        raise exceptions.PageError(f"Problem rendering {path}: {exc}")


def _to_html(contents: str) -> str:
    return cast(str, markdown.markdown(contents, extensions=["toc"]))


def _render_pages(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    theme_path: pathlib.Path,
    context: RenderContext,
) -> None:
    """Render each file in the input path into an HTML file in the output path."""
    with (theme_path / "base.html").open() as fileobj:
        template = fileobj.read()

    _Elements = collections.namedtuple(
        "_Elements", ["announcement_box", "schedule", "listing", "people"]
    )

    elements_ = _Elements(
        announcement_box=partial(elements.announcement_box, context),
        schedule=partial(elements.schedule, context),
        listing=partial(elements.listing, context),
        people=partial(elements.people, context),
    )

    for input_page_abspath in input_path.iterdir():
        with input_page_abspath.open() as fileobj:
            input_page_contents = fileobj.read()

        input_page_relpath = input_page_abspath.relative_to(input_path)

        body_interpolated = _interpolate(
            input_page_contents,
            {"elements": elements_, **context._asdict()},
            path=input_page_abspath,
        )
        body_html = _to_html(body_interpolated)
        page_html = _interpolate(template, {"body": body_html, **context._asdict()})

        output_page_abspath = (output_path / input_page_relpath).with_suffix(".html")
        with output_page_abspath.open("w") as fileobj:
            fileobj.write(page_html)


def generate(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    materials_path: pathlib.Path | None = None,
    vars: dict[str, Any] | None = None,
    now: Callable[[], datetime.datetime] = datetime.datetime.now,
) -> None:
    """Generate a static course website.

    Parameters
    ----------
    input_path
        Path to the source directory containing config.yaml, pages/, theme/, etc.
    output_path
        Path to the output directory where the generated site will be written.
    materials_path
        Optional path to a directory containing materials.json from automata.materials.
    vars
        Optional dictionary of variables accessible in templates as `vars`.
    now
        Callable returning the current datetime. Defaults to datetime.datetime.now.

    """
    if vars is None:
        vars = {}

    # create the output path, if it doesn't already exist
    output_path.mkdir(exist_ok=True)

    # load the publications and update their paths
    if materials_path is not None:
        published = _load_materials(materials_path, output_path)
    else:
        published = None

    # load the configuration file
    config = _load_config(input_path / "config.yaml", vars=vars)

    # validate the config against the theme's schema
    _validate_theme_schema(input_path, config)

    context = RenderContext(
        input_path=input_path,
        output_path=output_path,
        theme_path=input_path / "theme",
        materials_path=materials_path,
        materials=published,
        config=config,
        vars=vars,
        now=now(),
    )

    # convert user pages
    _render_pages(input_path / "pages", output_path, input_path / "theme", context)

    # copy static files
    shutil.copytree(
        input_path / "theme" / "style", output_path / "style", dirs_exist_ok=True
    )
    if (input_path / "static").exists():
        shutil.copytree(
            input_path / "static", output_path / "static", dirs_exist_ok=True
        )
