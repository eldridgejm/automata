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
import importlib.resources
import pathlib
import shutil
from collections.abc import Callable
from functools import partial
from types import ModuleType
from typing import Any, Mapping, Optional, cast

import jinja2
import markdown  # type: ignore

import automata.materials

from . import elements, exceptions, themes
from ._types import RenderContext, Theme


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


def _get_template_from_module(templates: ModuleType, template_name: str) -> str:
    """Get a template string from a module using importlib.resources."""
    return importlib.resources.read_text(templates, template_name)


def _interpolate(
    template: str,
    variables: dict[str, Any],
    path: pathlib.Path | None = None,
) -> str:
    """Render a Jinja2 template string with the given variables.

    Uses custom delimiters: ``${ }`` for variables, ``{% %}`` for blocks.

    Raises
    ------
    PageError
        If an undefined variable is accessed during rendering.

    """

    jinja_template = jinja2.Template(
        template,
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )

    try:
        return jinja_template.render(**variables)
    except jinja2.UndefinedError as exc:
        raise exceptions.PageError(f"Problem rendering {path}: {exc}")


def _to_html(contents: str) -> str:
    """Convert markdown content to HTML with table-of-contents support."""
    return cast(str, markdown.markdown(contents, extensions=["toc"]))


def _interpolate_using_template(
    theme: Theme,
    template_name: str,
    variables: dict[str, Any],
    template_overrides: Mapping[str, str] | None,
) -> str:
    """Get a template string from the theme's templates module."""
    if template_overrides is None:
        template_overrides = {}

    load_from_module = jinja2.FunctionLoader(
        lambda name: _get_template_from_module(theme.templates, name)
    )

    load_from_overrides = jinja2.DictLoader(template_overrides)

    loader = jinja2.ChoiceLoader([load_from_overrides, load_from_module])

    environment = jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )

    return environment.get_template(template_name).render(**variables)


def _render_page(
    content_root: pathlib.Path,
    relative_path_to_page: pathlib.Path,
    output_root: pathlib.Path,
    theme: Theme,
    context: RenderContext,
) -> None:
    """Render a single markdown page into an HTML file in the output directory.

    This function processes a single markdown page, rendering it into an HTML file
    in the output directory. The rendered HTML file preserves the directory structure
    relative to the content directory.

    1. Interpolate Jinja2 variables (including elements)
    2. Convert markdown to HTML
    3. Wrap in the base template from the theme
    4. Write to ``output_path`` with ``.html`` extension

    """
    with (content_root / relative_path_to_page).open() as fileobj:
        input_page_contents = fileobj.read()

    _Elements = collections.namedtuple(
        "_Elements", ["announcement_box", "schedule", "listing", "people"]
    )

    elements_ = _Elements(
        announcement_box=partial(elements.announcement_box.element, context),
        schedule=partial(elements.schedule.element, context),
        listing=partial(elements.listing.element, context),
        people=partial(elements.people.element, context),
    )

    body_interpolated = _interpolate(
        input_page_contents,
        variables={
            "content": input_page_contents,
            "elements": elements_,
            **context._asdict(),
        },
        path=relative_path_to_page,
    )
    body_html = _to_html(body_interpolated)
    page_html = _interpolate_using_template(
        theme,
        "base.html",
        {"body": body_html, **context._asdict()},
        theme.template_overrides,
    )

    output_page_abspath = (output_root / relative_path_to_page).with_suffix(".html")
    output_page_abspath.parent.mkdir(parents=True, exist_ok=True)
    with output_page_abspath.open("w") as fileobj:
        fileobj.write(page_html)


def _generate_from_content(
    content_path: pathlib.Path,
    output_path: pathlib.Path,
    theme,
    context: RenderContext,
) -> None:
    """Generate the static site from the content directory.

    This function recursively processes the content directory, rendering each markdown
    page into an HTML file in the output directory. Any other files (non-markdown) are
    copied directly to the output directory, preserving the directory structure.

    """
    for path in content_path.rglob("*"):
        relative_path = path.relative_to(content_path)
        if path.is_dir():
            # create corresponding directory in output_path
            (output_path / relative_path).mkdir(parents=True, exist_ok=True)
        elif path.suffix.lower() == ".md":
            # render markdown pages
            _render_page(content_path, relative_path, output_path, theme, context)
        else:
            # copy other, non-markdown files directly
            dest_file = output_path / relative_path
            shutil.copy(path, dest_file)


def _ensure_valid_materials_in_output_path(
    output_path: pathlib.Path, materials_path: pathlib.Path | None
):
    """Ensures that the course materials are located under the output path.


    If ``materials_path`` is ``None`` or equal to ``<output_path>/materials``, we expect
    that the materials are located there already. We check to make sure. If they are
    missing, we raise automata.website.Error.

    Otherwise, we copy the materials to ``<output_path>/materials``.

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
        materials_path = expected_materials_path
        if not materials_path.exists():
            raise exceptions.Error(
                f"Expected materials to be located at "
                f"{materials_path}, but they are missing."
            )
    else:
        shutil.copytree(materials_path, expected_materials_path, dirs_exist_ok=True)

    if not (materials_path / "materials.json").is_file():
        raise exceptions.Error(
            f"Expected to find materials.json in materials path "
            f"{materials_path}, but it is missing."
        )


def generate(
    content_path: pathlib.Path,
    output_path: pathlib.Path,
    materials_path: Optional[pathlib.Path] = None,
    theme: Theme = themes.default,
    vars: dict[str, Any] | None = None,
    now: Callable[[], datetime.datetime] = datetime.datetime.now,
) -> None:
    """Generate a static site from course materials."""
    if vars is None:
        vars = {}

    output_path.mkdir(exist_ok=True)

    # copy materials to output path, if necessary
    _ensure_valid_materials_in_output_path(output_path, materials_path)
    materials_path = output_path / "materials"

    # load the universe of exported materials from materials.json
    universe = _load_materials(output_path)

    context = RenderContext(
        content_path=content_path,
        materials_path=materials_path,
        output_path=output_path,
        materials=universe,
        vars=vars,
        now=now(),
    )

    _generate_from_content(content_path, output_path, theme, context)
