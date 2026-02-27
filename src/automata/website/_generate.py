"""Generates a course website."""

import dataclasses
import datetime
import pathlib
import shutil
from importlib.resources.abc import Traversable
from typing import Any, Callable

import jinja2
import smartconfig.types

from ..hooks import GeneratePostHookArgs, GeneratePreHookArgs
from ..materials import ExportedArtifact, Universe
from ..resources import WebsiteResources
from ..util import markdown as markdown_util
from ._config import WebsiteConfig
from ._frontmatter import Frontmatter, read_frontmatter
from .exceptions import PageError, WebsiteError


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
        Mapping of relative paths to file content.
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
    elements: dict[str, type],
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


def _process_pages(
    pages: dict[str, str | bytes | Traversable],
    build_directory: pathlib.Path,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    render_markdown: Callable[[str], str],
) -> None:
    """Process pages and write them to the build directory.

    Each item is processed based on its type:
    - str: rendered through the full pipeline (frontmatter, interpolation,
      markdown, template)
    - bytes: written directly as binary
    - Traversable (including Path): read as text and rendered through the
      full pipeline

    """
    for relative_path, content in pages.items():
        output_path = build_directory / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            output_path.write_bytes(content)
        elif isinstance(content, str):
            rendered = _render_page(
                content,
                jinja_environment,
                context,
                markdown_renderer=render_markdown,
            )
            output_path.write_text(rendered)
        else:
            rendered = _render_page(
                content.read_text(),
                jinja_environment,
                context,
                markdown_renderer=render_markdown,
            )
            output_path.write_text(rendered)


def generate(
    config: WebsiteConfig,
    resources: WebsiteResources,
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
    resources : WebsiteResources
        Pre-loaded website resources containing everything needed for generation:

        - ``templates``: Jinja2 templates (must include ``page.html``).
        - ``static_files``: Static files to copy to the build directory.
        - ``elements``: Element classes available during rendering.
        - ``hooks``: ``GenerateHooks`` instance for pre/post generation hooks.
        - ``materials``: Must not be None. Its ``.universe`` is used as the
          materials data and its ``.root`` is used as the path to the materials
          directory (which will be copied to the build output).
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
    # set default values for optional parameters
    vars = vars or {}
    current_time = current_time or datetime.datetime.now()
    cwd = cwd or pathlib.Path.cwd()
    hooks = resources.hooks

    # resolve paths relative to cwd (absolute paths are unchanged)
    content_directory = cwd / config.content_directory
    build_directory = cwd / config.build_directory

    # validate resources
    if "page.html" not in resources.templates:
        raise ValueError('Resources templates must include a "page.html" file.')

    if resources.materials is None:
        raise WebsiteError("resources.materials must not be None")

    # run pre-generate hooks
    url_for = _create_url_for(config.base_path)
    pre_args = hooks.on_generate_pre(
        GeneratePreHookArgs(resources=resources, vars=vars)
    )
    resources = pre_args.resources
    vars = pre_args.vars

    # set up jinja environment and copy static files
    jinja_environment = jinja2.Environment(
        loader=jinja2.DictLoader(resources.templates),
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )
    _copy_static_files(resources.static_files, build_directory)

    # extract materials from resources
    assert resources.materials is not None
    materials = resources.materials.universe
    materials_root = resources.materials.root

    # create render context
    _fix_artifact_paths(materials, url_for)
    context = _create_render_context(
        config,
        materials,
        url_for,
        current_time,
        vars,
        resources.elements,
        jinja_environment,
    )

    # process content
    _process_content_directory(
        content_directory,
        materials_root,
        build_directory,
        jinja_environment,
        context,
        config,
        render_markdown,
    )
    if resources.pages:
        _process_pages(
            resources.pages,
            build_directory,
            jinja_environment,
            context,
            render_markdown,
        )

    # finalize build
    _copy_materials_to_build(materials_root, build_directory, config)
    hooks.on_generate_post(GeneratePostHookArgs(config=config))
