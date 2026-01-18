"""Generates a course website."""

import dataclasses
import datetime
import pathlib
import shutil
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING, Any, Callable, Mapping, cast

import jinja2
import smartconfig.types

from ..materials import ExportedArtifact, Universe, deserialize
from ..util import markdown as markdown_util
from ._frontmatter import Frontmatter, read_frontmatter
from .exceptions import WebsiteError

if TYPE_CHECKING:
    from ._elements import Element


@dataclasses.dataclass
class RenderContext:
    """Context available at the time of rendering."""

    # the course materials universe
    materials: Universe[ExportedArtifact]

    # function to generate URLs for given paths
    url_for: Callable[[str], str]

    # base path for URL generation (e.g., "/" or "/course/")
    base_path: str

    # elements avaiable during rendering. These should be already bound to the render
    # context, so that they only require one argument: the element configuration.
    elements: dict[str, Callable[[smartconfig.types.Configuration], str]] = (
        dataclasses.field(default_factory=dict)
    )

    # the current date and time
    current_time: datetime.datetime = dataclasses.field(
        default_factory=datetime.datetime.now
    )

    # variables available for interpolation in the content
    vars: dict[str, Any] = dataclasses.field(default_factory=dict)

    # frontmatter for the current page
    frontmatter: Frontmatter = dataclasses.field(
        default_factory=lambda: Frontmatter(vars={})
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert the context to a dictionary for use in Jinja2.

        This performs a shallow conversion of the context's fields, which is
        necessary to avoid deepcopy issues with Jinja2 objects and callables
        that occur with 'dataclasses.asdict'.
        """
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}


def _interpolate(
    content: str,
    context: RenderContext,
) -> str:
    """Uses Jinja2 to interpolate content with the given rendering context."""

    return jinja2.Template(
        content,
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    ).render(**context.to_dict())


def _load_materials(
    materials_directory_path: pathlib.Path,
) -> Universe[ExportedArtifact]:
    """Loads the materials from the given path.

    This looks for a ``materials.json`` file in the given path and loads the
    materials universe from it.

    """
    materials_json_path = materials_directory_path / "materials.json"

    if not materials_directory_path.exists():
        raise WebsiteError(
            f'Materials directory not found at "{materials_directory_path}".'
        )

    if not materials_json_path.exists():
        raise WebsiteError(f'materials.json not found at "{materials_json_path}".')

    return cast(
        Universe[ExportedArtifact], deserialize(materials_json_path.read_text())
    )


def _copy_static_files(
    static_files: Mapping[str, str | bytes | Traversable],
    build_directory: pathlib.Path,
) -> None:
    """Copies static files to the build directory.

    Handles three types of static file content:
    - str: written as text
    - bytes: written as binary
    - Traversable (or any object with read_bytes()): read then written as binary

    Parameters
    ----------
    static_files : dict[str, str | bytes | Traversable]
        Dictionary mapping relative paths to file content.
    build_directory : pathlib.Path
        The directory to copy static files to.

    """
    for static_path, static_content in static_files.items():
        output_path = build_directory / static_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Handle different types of static content
        if isinstance(static_content, bytes):
            output_path.write_bytes(static_content)
        elif isinstance(static_content, str):
            output_path.write_text(static_content)
        else:
            # Traversable - read and write bytes
            output_path.write_bytes(static_content.read_bytes())


def _create_url_for(base_path: str) -> Callable[[str], str]:
    """Create a url_for function that respects the site's base path."""

    def url_for(path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{base_path.rstrip('/')}/{path.lstrip('/')}"

    return url_for


def _create_render_context(
    materials: Universe[ExportedArtifact],
    url_for: Callable[[str], str],
    base_path: str,
    current_time: datetime.datetime,
    vars: Mapping[str, Any],
    elements: Mapping[str, type["Element"]],
    jinja_environment: jinja2.Environment,
) -> RenderContext:
    """Create the render context with elements bound."""
    context = RenderContext(
        materials=materials,
        url_for=url_for,
        base_path=base_path,
        current_time=current_time,
        vars=dict(vars),
    )

    context.elements = {
        name: element(jinja_environment, context) for name, element in elements.items()
    }

    return context


def _copy_materials_to_build(
    materials_directory: pathlib.Path,
    build_directory: pathlib.Path,
    materials_directory_name: str,
) -> None:
    """Copy the materials directory to the build directory."""
    materials_output_path = build_directory / materials_directory_name

    # Only copy if source and destination are different
    # (resolve both paths to handle relative paths and symlinks correctly)
    if materials_directory.resolve() != materials_output_path.resolve():
        materials_output_path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            materials_directory,
            materials_output_path,
            dirs_exist_ok=True,
        )


def _render_page(
    content: str,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    markdown_renderer: Callable[[str], str] | None = None,
    base_path: pathlib.Path | None = None,
) -> str:
    """Renders page content to HTML.

    Parameters
    ----------
    content : str
        The raw content (with optional frontmatter).
    jinja_environment : jinja2.Environment
        The Jinja2 environment for template rendering.
    context : RenderContext
        The rendering context.
    markdown_renderer : Callable[[str], str] | None
        If provided, content is treated as markdown and rendered to HTML.
    base_path : pathlib.Path | None
        Base path for resolving relative paths in frontmatter. If None,
        uses current working directory.

    Returns
    -------
    str
        The rendered HTML content.
    """
    frontmatter, content = read_frontmatter(content, base_path=base_path)

    # create a new context with the frontmatter
    context = dataclasses.replace(context, frontmatter=frontmatter)

    # interpolate variables in the content
    rendered_content = _interpolate(content, context)

    # render markdown to HTML if a markdown renderer is provided
    if markdown_renderer is not None:
        rendered_content = markdown_renderer(rendered_content)

    base_url_path = context.base_path
    if not base_url_path.endswith("/"):
        base_url_path = f"{base_url_path}/"

    template_name = context.frontmatter.template
    if template_name not in jinja_environment.list_templates():
        raise ValueError(f'Template "{template_name}" not found.')

    return jinja_environment.get_template(template_name).render(
        **context.to_dict(),
        base_url_path=base_url_path,
        content=rendered_content,
    )


def _change_extension_to_html(path: str) -> str:
    """Change the extension of a path to .html if it isn't already.

    Parameters
    ----------
    path : str
        The relative path (e.g., "about.md", "index.html", "page").

    Returns
    -------
    str
        The path with .html extension.
    """
    p = pathlib.PurePosixPath(path)
    if p.suffix.lower() != ".html":
        return str(p.with_suffix(".html"))
    return path


def _fix_artifact_paths(
    materials: Universe[ExportedArtifact],
    url_for: Callable[[str], str],
) -> None:
    """Fixes the path attribute so that it takes into account the website's base path.

    This helper function simply applies `url_for` to each artifact's path.

    Parameters
    ----------
    materials : Universe[ExportedArtifact]
        The materials universe containing artifacts.
    url_for : Callable[[str], str]
        A function that generates URLs based on paths.

    """
    for collection in materials.collections.values():
        for publication in collection.publications.values():
            for artifact in publication.artifacts.values():
                artifact.path = url_for(str(artifact.path))


def _read_content(content: str | bytes | Traversable) -> str:
    """Read content from various sources into a string.

    Parameters
    ----------
    content : str | bytes | Traversable
        The content to read. Can be a string (returned as-is), bytes (decoded
        as UTF-8), or a Traversable (read as text).

    Returns
    -------
    str
        The content as a string.
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, bytes):
        return content.decode("utf-8")
    else:
        return content.read_text()


def _process_content(
    content: Mapping[str, str | bytes | Traversable],
    build_directory: pathlib.Path,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    render_markdown: Callable[[str], str],
) -> None:
    """Process content files and write them to the build directory.

    Each content file is rendered through the full pipeline (frontmatter parsing,
    variable interpolation, markdown rendering if applicable, and template wrapping).

    Parameters
    ----------
    content : dict[str, str | bytes | Traversable]
        Dictionary mapping relative paths to content. Keys are paths relative to
        the output directory root. Values can be strings, bytes, or Traversables
        containing markdown or HTML content. If the path doesn't end in .html,
        the extension will be changed to .html in the output. Markdown files
        (paths ending in .md) are rendered to HTML.
    build_directory : pathlib.Path
        The directory to write content to.
    jinja_environment : jinja2.Environment
        The Jinja2 environment for template rendering.
    context : RenderContext
        The rendering context.
    render_markdown : Callable[[str], str]
        Function to render markdown to HTML.

    """
    for relative_path, content_value in content.items():
        # Determine if this is markdown based on original extension
        original_path = pathlib.PurePosixPath(relative_path)
        is_markdown = original_path.suffix.lower() == ".md"

        # Change extension to .html if needed
        output_relative_path = _change_extension_to_html(relative_path)
        output_path = build_directory / output_relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Read content from the source
        content_str = _read_content(content_value)

        # Render the page
        rendered = _render_page(
            content_str,
            jinja_environment,
            context,
            markdown_renderer=render_markdown if is_markdown else None,
        )
        output_path.write_text(rendered)


def generate(
    materials_directory: pathlib.Path,
    templates: Mapping[str, str],
    build_directory: pathlib.Path | str,
    base_path: str = "/",
    materials_directory_name: str = "materials",
    elements: Mapping[str, type["Element"]] | None = None,
    pages: Mapping[str, str | bytes | Traversable] | None = None,
    assets: Mapping[str, str | bytes | Traversable] | None = None,
    static_files: Mapping[str, str | bytes | Traversable] | None = None,
    vars: Mapping[str, Any] | None = None,
    current_time: datetime.datetime | None = None,
    render_markdown: Callable[[str], str] = markdown_util.render,
    cwd: pathlib.Path | None = None,
):
    """Generates a static website from course materials.

    Parameters
    ----------
    materials_directory : pathlib.Path
        The path to the directory containing the exported materials. This directory
        should contain a materials.json file and associated artifact files, as
        produced by :func:`automata.materials.export`. The directory will be copied
        to the build directory at the location specified by materials_directory_name.
    templates : dict[str, str]
        Dictionary mapping template names to their content. Must include at least
        a "page.html" template which serves as the base template for all pages.
    build_directory : pathlib.Path | str
        The directory where the generated website will be written. If a relative
        path, it will be resolved relative to ``cwd``.
    base_path : str, optional
        The base URL path for the site. Used for generating URLs when the site
        is deployed to a subdirectory. Defaults to "/".
    materials_directory_name : str, optional
        The name of the subdirectory within build_directory where materials
        will be copied. Defaults to "materials".
    elements : dict[str, type[Element]], optional
        Dictionary mapping element names to Element classes. Elements are
        callable components that can be used in templates to generate HTML.
    pages : dict[str, str | bytes | Traversable], optional
        Page files to render and include in the generated output. Each key is
        a relative path from the build directory root. Values can be strings,
        bytes, or Traversables containing markdown or HTML content. Files with
        a ``.md`` extension are rendered as markdown; all others are treated as
        HTML. Output paths will have their extension changed to ``.html`` if not
        already. Each page file is processed through the full rendering pipeline
        (frontmatter parsing, variable interpolation, markdown rendering if
        applicable, and template wrapping).
    assets : dict[str, str | bytes | Traversable], optional
        Asset files to copy directly to the build directory. Each key is a
        relative path from the build directory root. Values can be:

        - A string: written as text
        - A bytes object: written as binary
        - A Traversable: read and written as binary

        These files are copied directly without any rendering.
    static_files : dict[str, str | bytes | Traversable], optional
        Static files to copy directly to the build directory. Same format as
        ``assets``. Typically used for CSS, JavaScript, fonts, etc.
    vars : dict[str, Any], optional
        A dictionary of variables to be used during rendering.
    current_time : datetime.datetime, optional
        The current date and time to be used during rendering.
    render_markdown : Callable[[str], str], optional
        A function that converts markdown content to HTML. Should take markdown
        text (str) and return HTML (str). Defaults to
        :func:`automata.util.markdown.render`, which wraps
        :func:`markdown.markdown` with the TOC extension enabled.
    cwd : pathlib.Path, optional
        Working directory for resolving relative paths. The build_directory path
        will be resolved relative to this directory. If None, uses the current
        working directory. Absolute paths are used as-is regardless of cwd.

    Raises
    ------
    ValueError
        If templates does not include a "page.html" template.

    Notes
    -----

    Build Process
    ~~~~~~~~~~~~~

    This function requires that course materials have already been exported to the
    directory specified by the ``materials_directory`` parameter. This directory
    should be of the same format as produced by the :func:`automata.materials.export`
    function; namely, there should be a ``materials.json`` file in the root of the
    materials directory, along with subdirectories containing the actual artifact files.
    If this materials directory is not found or is missing required files, an error
    will be raised.

    Pages are provided via the ``pages`` parameter as a dictionary mapping relative
    paths to page content. Each page file is processed through the full rendering
    pipeline:

    - Frontmatter is parsed and made available to templates
    - Variables are interpolated using Jinja2 syntax
    - Markdown files (those with ``.md`` extension) are converted to HTML
    - The result is wrapped in the appropriate template

    Static files (``assets`` and ``static_files``) are copied directly to the output
    without any processing.

    The materials directory will be copied to the build directory at the location
    specified by ``materials_directory_name`` (default: ``materials``).

    Rendering Context
    ~~~~~~~~~~~~~~~~~

    During rendering, a context is created that contains information that may be useful
    for templating. This context is represented by the :class:`RenderContext` class.
    In particular, the ``vars`` parameter passed to this function will be made available
    in the rendering context, allowing for dynamic content generation based on these
    variables. The render context also includes a ``materials`` attribute that provides
    access to the course materials, if applicable.

    The context also provides a ``url_for`` function that can be used to generate URLs
    that respect the site's ``base_path``. This is useful when a site is deployed to a
    subdirectory rather than the root of a domain. For example::

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
    # validate templates
    if "page.html" not in templates:
        raise ValueError('Templates must include a "page.html" template.')

    # set default values for optional parameters
    elements = elements or {}
    pages = pages or {}
    assets = assets or {}
    static_files = static_files or {}
    vars = vars or {}
    current_time = current_time or datetime.datetime.now()
    cwd = cwd or pathlib.Path.cwd()

    # resolve paths relative to cwd (absolute paths are unchanged)
    build_directory_path = cwd / build_directory

    # set up url_for and jinja environment
    url_for = _create_url_for(base_path)
    jinja_environment = jinja2.Environment(
        loader=jinja2.DictLoader(templates),
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )

    # copy static files and assets
    _copy_static_files(assets, build_directory_path)
    _copy_static_files(static_files, build_directory_path)

    # load materials and create render context
    materials = _load_materials(materials_directory)
    _fix_artifact_paths(materials, url_for)
    context = _create_render_context(
        materials, url_for, base_path, current_time, vars, elements, jinja_environment
    )

    # process pages
    _process_content(
        pages,
        build_directory_path,
        jinja_environment,
        context,
        render_markdown,
    )

    # finalize build
    _copy_materials_to_build(
        materials_directory, build_directory_path, materials_directory_name
    )
