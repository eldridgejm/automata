"""Generates a course website."""

import datetime
import pathlib
from typing import Any, Callable, cast

from ..materials import ExportedArtifact, Universe, deserialize
from ._config import Config
from ._render import RenderContext, render_page_from_html, render_page_from_markdown
from .exceptions import Error


def _load_materials(
    materials_directory_path: pathlib.Path,
) -> Universe[ExportedArtifact]:
    """Loads the materials from the given path.

    This looks for a ``materials.json`` file in the given path and loads the
    materials universe from it.

    """
    materials_json_path = materials_directory_path / "materials.json"

    if not materials_directory_path.exists():
        raise Error(f'Materials directory not found at "{materials_directory_path}".')

    if not materials_json_path.exists():
        raise Error(f'materials.json not found at "{materials_json_path}".')

    return cast(
        Universe[ExportedArtifact], deserialize(materials_json_path.read_text())
    )


def _render_and_write(
    input_path,
    output_path,
    renderer: Callable[[str, RenderContext], str],
    context: RenderContext,
) -> None:
    raw_content = input_path.read_text()
    rendered_content = renderer(raw_content, context)
    output_path.write_text(rendered_content)


def _copy_file_to_output(
    path: pathlib.Path, output_path: pathlib.Path, config: Config
) -> None:
    # if the file has a suffix designating that it is raw and should not be
    # rendered, remove that suffix (but only if there are multiple suffixes).
    # this means that a file named `data.csv.raw` will be copied to the output
    # as `data.csv`, but a file named `image.raw` will be copied as `image.raw`
    # (assuming `.raw` is the no_render_suffix)
    if path.suffix.lower() == config.no_render_suffix and len(path.suffixes) > 1:
        # remove .raw suffix
        output_path = output_path.with_suffix("")

    # copy other files as-is
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(path.read_bytes())


def generate(
    config: Config,
    vars: dict[str, Any] | None = None,
    now: datetime.datetime | None = None,
    render_page_from_markdown=render_page_from_markdown,
    render_page_from_html=render_page_from_html,
):
    """Generates a static website from course materials.

    Parameters
    ----------
    config : Config
        The configuration for the website generation. Contains information about
        the location of the content and build directories, among other settings.
        See :class:`Config` for more details.
    vars : dict[str, Any], optional
        A dictionary of variables to be used during rendering.
    now : datetime.datetime, optional
        The current date and time to be used during rendering.

    Notes
    -----

    Build Process
    ~~~~~~~~~~~~~

    When called, this function will look for content in the
    ``config.content_directory``. It is expected that this directory contains markdown
    files (``.md``) and/or HTML files, and possibly other static assets (like images,
    CSS files, etc.). The function will process each file as follows:

    - Markdown files (``.md``) will be converted to HTML
    - HTML files will be processed as-is
    - Other files will be copied directly to the output directory without modification

    Files with a suffix matching ``config.no_render_suffix`` (e.g., ``.raw``) will be
    copied to the output directory with that suffix removed. This allows for raw
    markdown and HTML files to be included in the output without rendering them.

    This function assumes that course materials have already been exported and are
    located in the content directory in a directory named
    ``config.materials_directory_name`` (by default, this is ``materials``).
    This directory should be of the same format as produced by the
    :func:`automata.materials.export` function; namely, there should be a
    ``materials.json`` file in the root of the materials directory, along with
    subdirectories containing the actual content files. If this materials directory
    is not found, an error will be raised.

    Content and materials will be copied to the ``config.build_directory``, preserving
    the directory structure found in the content directory.

    Rendering Context
    ~~~~~~~~~~~~~~~~~

    During rendering, a context is created that contains information that may be useful
    for templating. This context is represented by the :class:`RenderContext` class.
    In particular, the ``vars`` parameter passed to this function will be made available
    in the rendering context, allowing for dynamic content generation based on these
    variables. The render context also includes a ``materials`` attribute that provides
    access to the course materials, if applicable.

    """

    # set default values for optional parameters
    if vars is None:
        vars = {}

    if now is None:
        now = datetime.datetime.now()

    materials_path = (
        pathlib.Path(config.content_directory) / config.materials_directory_name
    )

    context = RenderContext(
        config=config, materials=_load_materials(materials_path), now=now, vars=vars
    )

    for path in pathlib.Path(config.content_directory).rglob("*"):
        relative_path = path.relative_to(config.content_directory)
        output_path = config.build_directory / relative_path

        if path.is_dir():
            output_path.mkdir(parents=True, exist_ok=True)
        elif path.suffix.lower() == ".md":
            output_path = output_path.with_suffix(".html")
            _render_and_write(path, output_path, render_page_from_markdown, context)
        elif path.suffix.lower() == ".html":
            _render_and_write(path, output_path, render_page_from_html, context)
        else:
            _copy_file_to_output(path, output_path, config)
