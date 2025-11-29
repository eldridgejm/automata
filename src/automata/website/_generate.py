"""Static site generation for course websites.

This module provides the core site generation logic. The main entry point is
:func:`generate`, which transforms a source directory containing markdown pages,
a theme, and configuration into a static HTML website.

Pipeline
--------
1. Load published materials from ``materials.json`` (if provided)
2. Load and interpolate ``config.yaml`` (supports ``!include`` directives)
3. Validate configuration against the theme's schema
4. Render each markdown page: interpolate variables → convert to HTML → wrap in template
5. Copy static assets from theme and ``static/`` directory

"""

import collections
import dataclasses
import datetime
import pathlib
import shutil
from collections.abc import Callable
from functools import partial
from typing import Any, cast

import jinja2
import markdown  # type: ignore
import smartconfig
import yaml  # type: ignore

import automata.materials

from . import elements, exceptions
from ._config import Config
from ._types import RenderContext
from ._util import load_yaml


def _load_materials(output_path: pathlib.Path) -> automata.materials.Universe:
    """Load artifacts from ``materials.json`` and update their paths.

    The artifacts in ``materials.json`` have a ``path`` attribute that gives
    their path relative to ``materials.json``. But we need the path to the
    artifact from the website root: the ``output_path``. This function loads the
    artifacts and performs the update.

    Parameters
    ----------
    output_path : pathlib.Path
        Path to the output directory. The ``materials.json`` file is expected to be
        located at ``<output_path>/materials/materials.json``.

    Returns
    -------
    materials.Universe
        The universe of materials artifacts, with each artifact's path updated
        to be relative to ``output_path``.

    """
    materials_path = output_path / "materials"

    # read the universe
    with (materials_path / "materials.json").open() as fileobj:
        materials = automata.materials.deserialize(fileobj.read())

    assert isinstance(materials, automata.materials.Universe)

    # we need to update their paths to be relative to output directory; this function
    # will do it for one artifact
    def _update_path(artifact: automata.materials.ExportedArtifact):
        relative_path = materials_path.relative_to(output_path) / artifact.path
        return dataclasses.replace(artifact, path=str(relative_path))

    # apply the function to all artifacts, modifying `materials`
    for collection in materials.collections.values():
        for publication in collection.publications.values():
            for artifact_key, artifact in publication.artifacts.items():
                publication.artifacts[artifact_key] = _update_path(artifact)

    return materials


def _load_config(path: pathlib.Path, vars: dict[str, Any]) -> dict[str, Any]:
    """Read the configuration from a yaml file, performing interpolation.

    Parameters
    ----------
    path : pathlib.Path
        The path to the configuration file.
    vars : dict[str, Any]
        Variables to make available during interpolation.

    Returns
    -------
    dict[str, Any]
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
    variables = {"vars": vars}

    dct = load_yaml(path)

    schema = {"type": "dict", "extra_keys_schema": {"type": "any"}}
    result = smartconfig.resolve(dct, spec=schema, global_variables=variables)
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
        smartconfig.resolve(config["config"], theme_schema)
    except smartconfig.exceptions.ResolutionError as exc:
        raise RuntimeError(f"Invalid theme config: {exc}")


def _interpolate(
    contents: str, variables: dict[str, Any], path: pathlib.Path | None = None
) -> str:
    """Render a Jinja2 template string with the given variables.

    Uses custom delimiters: ``${ }`` for variables, ``{% %}`` for blocks.

    Raises
    ------
    PageError
        If an undefined variable is accessed during rendering.

    """
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
    """Convert markdown content to HTML with table-of-contents support."""
    return cast(str, markdown.markdown(contents, extensions=["toc"]))


def _render_pages(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    theme_path: pathlib.Path,
    context: RenderContext,
) -> None:
    """Render each markdown page into an HTML file.

    For each file in ``input_path``:
    1. Interpolate Jinja2 variables (including elements)
    2. Convert markdown to HTML
    3. Wrap in the base template from the theme
    4. Write to ``output_path`` with ``.html`` extension

    """
    with (theme_path / "base.html").open() as fileobj:
        template = fileobj.read()

    _Elements = collections.namedtuple(
        "_Elements", ["announcement_box", "schedule", "listing", "people"]
    )

    elements_ = _Elements(
        announcement_box=partial(elements.announcement_box.element, context),
        schedule=partial(elements.schedule.element, context),
        listing=partial(elements.listing.element, context),
        people=partial(elements.people.element, context),
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


def _ensure_materials_in_output_path(
    output_path: pathlib.Path, materials_path: pathlib.Path | None
):
    """Ensures that the course materials are located under the output path.

    There are three cases:

        1. If ``materials_path`` is ``None`` or equal to ``<output_path>/materials``,
        we expect that the materials are located there already. We check to make sure.
        If they are missing, we raise automata.website.Error.

        2. If ``materials_path`` is an absolute path outside of ``output_path``, we copy
        the materials directory to ``<output_path>/materials``.

        3. If ``materials_path`` is a relative path or an absolute path within
        ``output_path`` (but not equal to ``<output_path>/materials``), we raise
        automata.website.Error.

    Parameters
    ----------
    output_path : pathlib.Path
        Path to the output directory.
    materials_path : pathlib.Path
        Path to the materials directory.

    Raises
    ------
    automata.website.Error
        If the materials are missing or located in an invalid location.

    """
    expected_materials_path = output_path / "materials"

    if materials_path is None or materials_path == expected_materials_path:
        if not expected_materials_path.exists():
            raise exceptions.Error(
                f"Expected materials to be located at "
                f"{expected_materials_path}, but they are missing."
            )
        return

    if materials_path.is_absolute() and not materials_path.is_relative_to(output_path):
        shutil.copytree(materials_path, expected_materials_path, dirs_exist_ok=True)
        return

    raise exceptions.Error(
        f"Materials path {materials_path} is invalid. Materials must be located "
        f"either at {expected_materials_path} or at an absolute path outside "
        f"of the output directory."
    )


def generate(
    config: Config,
    materials_path: pathlib.Path | None = None,
    vars: dict[str, Any] | None = None,
    now: Callable[[], datetime.datetime] = datetime.datetime.now,
) -> None:
    """Generate a static course website.

    Expected input directory structure::

        input_path/
        ├── pages/              # Markdown pages (converted to HTML)
        ├── static/             # Static assets (copied as-is)
        └── theme/
            ├── base.html       # Base template wrapping all pages
            ├── schema.yaml     # Theme configuration schema
            ├── style/          # CSS/JS (copied to output)
            └── elements/       # Element HTML templates

    Parameters
    ----------
    config : Config
        The website generation configuration.
    materials_path : pathlib.Path | None, optional
        Path to the directory containing ``materials.json``. By default, this is
        ``output_path/materials``. If this path is provided and points to a directory
        outside of ``output_path``, the directory will be copied to
        ``output_path/materials``. In both cases, ``materials.json`` will be loaded and
        the artifact paths updated to be relative to ``output_path``. Default is
        ``None``.

    Raises
    ------
    automata.website.Error
        If there is an error during site generation.

    """
    if vars is None:
        vars = {}

    input_path = pathlib.Path(config.input_path)
    output_path = pathlib.Path(config.output_path)

    # create the output path, if it doesn't already exist
    output_path.mkdir(exist_ok=True)

    _ensure_materials_in_output_path(output_path, materials_path)

    published = _load_materials(output_path)

    # validate the config against the theme's schema
    _validate_theme_schema(input_path, config.theme._as_dict())

    context = RenderContext(
        input_path=input_path,
        output_path=output_path,
        theme_path=input_path / "theme",
        materials_path=materials_path,
        materials=published,
        config=config._as_dict(),
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
