"""Generates a course website."""

import dataclasses
import datetime
import pathlib
from typing import Any, Callable, cast

import jinja2

from ..materials import ExportedArtifact, Universe, deserialize
from ._config import Config
from ._frontmatter import read_frontmatter
from ._render import RenderContext, render_page_from_html, render_page_from_markdown
from ._theme import Theme
from .exceptions import Error, PageError
from .themes import default as _default_theme


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


def _generate_single_page(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    jinja_environment: jinja2.Environment,
    renderer: Callable[[str, RenderContext], str],
    context: RenderContext,
) -> None:
    raw_content = input_path.read_text()

    # extract frontmatter from the content
    try:
        frontmatter, content = read_frontmatter(raw_content)
    except Exception as e:
        # Wrap any parsing errors with file path context
        raise PageError(str(e), input_path) from e

    # create a new context with the frontmatter
    context = dataclasses.replace(context, frontmatter=frontmatter)

    # render the content (without frontmatter)
    rendered_content = renderer(content, context)

    if "base.html" not in jinja_environment.list_templates():
        raise Error('Theme templates must include "base.html".')

    base_path = context.config.base_path
    if not base_path.endswith("/"):
        base_path = f"{base_path}/"

    wrapped_content = jinja_environment.get_template("base.html").render(
        **dataclasses.asdict(context),
        base_url_path=base_path,
        body=rendered_content,
        content=rendered_content,
    )
    output_path.write_text(wrapped_content)


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
    render_page_from_markdown : Callable[[str, RenderContext], str], optional
        The function to use for rendering markdown pages. Takes raw markdown
        content (str) and a render context, returns rendered HTML (str).
        Defaults to :func:`render_page_from_markdown`.
    render_page_from_html : Callable[[str, RenderContext], str], optional
        The function to use for rendering HTML pages. Takes raw HTML content
        (str) and a render context, returns rendered HTML (str). Defaults to
        :func:`render_page_from_html`.

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

    The context also provides a ``url_for`` function that can be used to generate URLs
    that respect the site's ``base_path`` configuration. This is useful when a site is
    deployed to a subdirectory rather than the root of a domain. For example::

        <a href="${ url_for('about.html') }">About</a>

    With the default ``base_path`` of ``"/"``, this generates ``/about.html``.
    With a ``base_path`` of ``"/course/"``, this generates ``/course/about.html``.
    The function automatically handles leading and trailing slashes, so both
    ``url_for('about.html')`` and ``url_for('/about.html')`` produce the same
    result.

    Frontmatter
    ~~~~~~~~~~~

    Pages can optionally include YAML frontmatter at the beginning of the file,
    delimited by ``---``::

        ---
        vars:
          title: "Page Title"
          author: "Author Name"
        ---

        # Page content here

    The only supported key in frontmatter is ``vars``, which should contain a dictionary
    of page-specific variables. These variables are accessible in templates via the
    ``frontmatter`` namespace (e.g., ``${ frontmatter.vars.title }``). Pages without
    frontmatter work as normal.

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
        config=config,
        materials=_load_materials(materials_path),
        now=now,
        vars=vars,
    )

    theme = Theme.from_package(_default_theme)
    jinja_environment = jinja2.Environment(
        loader=jinja2.DictLoader(theme.templates),
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )

    for path in pathlib.Path(config.content_directory).rglob("*"):
        relative_path = path.relative_to(config.content_directory)
        output_path = config.build_directory / relative_path

        if path.is_dir():
            output_path.mkdir(parents=True, exist_ok=True)
        elif path.suffix.lower() == ".md":
            output_path = output_path.with_suffix(".html")
            _generate_single_page(
                path,
                output_path,
                jinja_environment,
                render_page_from_markdown,
                context,
            )
        elif path.suffix.lower() == ".html":
            _generate_single_page(
                path, output_path, jinja_environment, render_page_from_html, context
            )
        else:
            _copy_file_to_output(path, output_path, config)
