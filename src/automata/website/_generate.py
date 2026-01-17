"""Generates a course website."""

import dataclasses
import datetime
import pathlib
import shutil
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING, Any, Callable, cast

import jinja2
import smartconfig.types

from .._config import WebsiteConfig
from ..materials import ExportedArtifact, Universe, deserialize
from ..util import markdown as markdown_util
from ._frontmatter import Frontmatter, read_frontmatter
from .exceptions import PageError, WebsiteError

if TYPE_CHECKING:
    from ._elements import Element


@dataclasses.dataclass
class RenderContext:
    """Context available at the time of rendering."""

    # website configuration
    website_config: WebsiteConfig

    # the course materials universe
    materials: Universe[ExportedArtifact]

    # function to generate URLs for given paths
    url_for: Callable[[str], str]

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
    static_files: dict[str, str | bytes | Traversable],
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
    config: WebsiteConfig,
    materials: Universe[ExportedArtifact],
    url_for: Callable[[str], str],
    current_time: datetime.datetime,
    vars: dict[str, Any],
    elements: dict[str, type["Element"]],
    jinja_environment: jinja2.Environment,
) -> RenderContext:
    """Create the render context with elements bound."""
    context = RenderContext(
        website_config=config,
        materials=materials,
        url_for=url_for,
        current_time=current_time,
        vars=vars,
    )

    context.elements = {
        name: element(jinja_environment, context) for name, element in elements.items()
    }

    return context


def _copy_materials_to_build(
    materials_directory: pathlib.Path,
    build_directory: pathlib.Path,
    config: WebsiteConfig,
) -> None:
    """Copy the materials directory to the build directory."""
    materials_output_path = build_directory / config.materials_directory_name

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

    base_url_path = context.website_config.base_path
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


def _generate_single_page(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    markdown_renderer: Callable[[str], str] | None = None,
) -> None:
    """Reads a file, renders it, and writes the output."""
    try:
        rendered = _render_page(
            input_path.read_text(),
            jinja_environment,
            context,
            markdown_renderer=markdown_renderer,
            base_path=input_path.parent,
        )
    except Exception as e:
        raise PageError(str(e), input_path) from e

    output_path.write_text(rendered)


def _copy_file_to_output(
    path: pathlib.Path, output_path: pathlib.Path, config: WebsiteConfig
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


def _paths_outside_materials_directory(
    content_directory: pathlib.Path,
    materials_path: pathlib.Path,
):
    """Yields all paths in content_directory that are not in the materials directory."""
    for dirpath, dirnames, filenames in content_directory.walk(top_down=True):
        dirpath = pathlib.Path(dirpath)

        # skip the materials directory itself
        if dirpath == materials_path:
            dirnames.clear()  # don't recurse into materials
            continue

        for dirname in dirnames:
            yield dirpath / dirname

        for filename in filenames:
            yield dirpath / filename


def _process_content_directory(
    content_directory: pathlib.Path,
    materials_directory: pathlib.Path,
    build_directory: pathlib.Path,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    config: WebsiteConfig,
    render_markdown: Callable[[str], str],
) -> None:
    """Process all files in the content directory.

    Walks through the content directory and processes each file:
    - Directories are created in the build directory
    - Markdown files are rendered to HTML
    - HTML files are rendered (with variable interpolation)
    - Other files are copied as-is

    """
    for path in _paths_outside_materials_directory(
        content_directory, materials_directory
    ):
        relative_path = path.relative_to(content_directory)
        output_path = build_directory / relative_path

        if path.is_dir():
            output_path.mkdir(parents=True, exist_ok=True)
        elif path.suffix.lower() == ".md":
            output_path = output_path.with_suffix(".html")
            _generate_single_page(
                path,
                output_path,
                jinja_environment,
                context,
                markdown_renderer=render_markdown,
            )
        elif path.suffix.lower() == ".html":
            _generate_single_page(path, output_path, jinja_environment, context)
        else:
            _copy_file_to_output(path, output_path, config)


def _process_extra_pages(
    extra_pages: dict[str, str],
    build_directory: pathlib.Path,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    render_markdown: Callable[[str], str],
) -> None:
    """Process extra pages and write them to the build directory.

    Each page is rendered through the full pipeline (frontmatter, interpolation,
    markdown, template).

    Parameters
    ----------
    extra_pages : dict[str, str]
        Dictionary mapping relative paths to page content (as strings).
    build_directory : pathlib.Path
        The directory to write pages to.
    jinja_environment : jinja2.Environment
        The Jinja2 environment for template rendering.
    context : RenderContext
        The rendering context.
    render_markdown : Callable[[str], str]
        Function to render markdown to HTML.

    """
    for relative_path, content in extra_pages.items():
        output_path = build_directory / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        rendered = _render_page(
            content,
            jinja_environment,
            context,
            markdown_renderer=render_markdown,
        )
        output_path.write_text(rendered)


def generate(
    config: WebsiteConfig,
    materials_directory: pathlib.Path,
    templates: dict[str, str],
    elements: dict[str, type["Element"]] | None = None,
    extra_assets: dict[str, str | bytes | Traversable] | None = None,
    extra_pages: dict[str, str] | None = None,
    vars: dict[str, Any] | None = None,
    current_time: datetime.datetime | None = None,
    render_markdown: Callable[[str], str] = markdown_util.render,
    cwd: pathlib.Path | None = None,
):
    """Generates a static website from course materials.

    Parameters
    ----------
    config : WebsiteConfig
        The configuration for the website generation. Contains information about
        the location of the content and build directories, among other settings.
        See :class:`WebsiteConfig` for more details.
    materials_directory : pathlib.Path
        The path to the directory containing the exported materials. This directory
        should contain a materials.json file and associated artifact files, as
        produced by :func:`automata.materials.export`. The directory will be copied
        to the build directory at the location specified by
        config.materials_directory_name.
    templates : dict[str, str]
        Dictionary mapping template names to their content. Must include at least
        a "page.html" template which serves as the base template for all pages.
    elements : dict[str, type[Element]], optional
        Dictionary mapping element names to Element classes. Elements are
        callable components that can be used in templates to generate HTML.
    extra_assets : dict[str, str | bytes | Traversable], optional
        Additional static files to copy to the build directory. Each key is a
        relative path from the build directory root. Values can be:

        - A string: written as text
        - A bytes object: written as binary
        - A Traversable: read and written as binary

        These files are copied directly without any rendering.
    extra_pages : dict[str, str], optional
        Additional pages to include in the generated output. Each key is a relative
        path from the build directory root. Values must be strings containing
        markdown or HTML content. Each page is processed through the full rendering
        pipeline (frontmatter parsing, variable interpolation, markdown rendering,
        and template wrapping).
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
        Working directory for resolving relative paths in config. All relative paths
        in the configuration (content_directory, build_directory) will be resolved
        relative to this directory. If None, uses the current working directory.
        Absolute paths in config are used as-is regardless of cwd.

    Raises
    ------
    ValueError
        If templates does not include a "page.html" template.

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

    This function requires that course materials have already been exported to the
    directory specified by the ``materials_directory`` parameter. This directory
    should be of the same format as produced by the :func:`automata.materials.export`
    function; namely, there should be a ``materials.json`` file in the root of the
    materials directory, along with subdirectories containing the actual artifact files.
    If this materials directory is not found or is missing required files, an error
    will be raised.

    Content will be copied to the ``config.build_directory``, preserving the directory
    structure found in the content directory. The materials directory will be copied
    to the build directory at the location specified by
    ``config.materials_directory_name`` (by default, this is ``materials``).

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
    # validate templates
    if "page.html" not in templates:
        raise ValueError('Templates must include a "page.html" template.')

    # set default values for optional parameters
    elements = elements or {}
    extra_assets = extra_assets or {}
    vars = vars or {}
    current_time = current_time or datetime.datetime.now()
    cwd = cwd or pathlib.Path.cwd()

    # resolve paths relative to cwd (absolute paths are unchanged)
    content_directory = cwd / config.content_directory
    build_directory = cwd / config.build_directory

    # set up url_for and jinja environment
    url_for = _create_url_for(config.base_path)
    jinja_environment = jinja2.Environment(
        loader=jinja2.DictLoader(templates),
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )

    # copy static files
    _copy_static_files(extra_assets, build_directory)

    # load materials and create render context
    materials = _load_materials(materials_directory)
    _fix_artifact_paths(materials, url_for)
    context = _create_render_context(
        config, materials, url_for, current_time, vars, elements, jinja_environment
    )

    # process content
    _process_content_directory(
        content_directory,
        materials_directory,
        build_directory,
        jinja_environment,
        context,
        config,
        render_markdown,
    )
    if extra_pages is not None:
        _process_extra_pages(
            extra_pages,
            build_directory,
            jinja_environment,
            context,
            render_markdown,
        )

    # finalize build
    _copy_materials_to_build(materials_directory, build_directory, config)
