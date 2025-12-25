"""Generates a course website."""

import dataclasses
import datetime
import pathlib
from functools import partial
from typing import Any, Callable, cast

import jinja2
import markdown

from ..materials import ExportedArtifact, Universe, deserialize
from ._config import Config
from ._frontmatter import read_frontmatter
from ._render import RenderContext, render_page_from_html, render_page_from_markdown
from ._theme import Theme
from .exceptions import Error, PageError


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


def _get_theme_and_jinja_environment(
    config: Config,
) -> tuple[Theme, jinja2.Environment]:
    """Creates a Jinja2 environment from the theme configuration.

    Loads the theme based on config.theme.use (either from entry point or directory
    path), applies any overrides from config.theme.overrides, and creates a Jinja2
    environment with the theme's templates.

    Parameters
    ----------
    config : Config
        The configuration containing theme settings.

    Returns
    -------
    tuple[Theme, jinja2.Environment]
        A tuple of (theme, jinja_environment). The theme is returned so that
        its static files can be copied to the output directory.

    """
    # Load theme based on config - either from entry point or directory path
    if "/" in config.theme.use or "\\" in config.theme.use:
        # Path to custom theme directory
        theme = Theme.from_directory(pathlib.Path(config.theme.use))
    else:
        # Entry point name
        theme = Theme.from_entry_point(config.theme.use)

    # Apply overrides if specified
    if config.theme.overrides is not None:
        overrides_dir = pathlib.Path(config.theme.overrides)
        if overrides_dir.exists():
            # Allow override directories to have only static files
            override_theme = Theme.from_directory(
                overrides_dir, require_templates=False
            )
            # Merge overrides into base theme (overrides take precedence)
            theme.templates.update(override_theme.templates)
            theme.static_files.update(override_theme.static_files)

    if "base.html" not in theme.templates:
        raise ValueError('Theme templates must include a "base.html" file.')

    jinja_environment = jinja2.Environment(
        loader=jinja2.DictLoader(theme.templates),
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )

    return theme, jinja_environment


def _copy_theme_static_files(theme: Theme, build_directory: pathlib.Path) -> None:
    """Copies static files from the theme to the build directory.

    Handles three types of static file content:
    - str: written as text
    - bytes: written as binary
    - Traversable (or any object with read_bytes()): read then written as binary

    Parameters
    ----------
    theme : Theme
        The theme containing static files to copy.
    build_directory : pathlib.Path
        The directory to copy static files to.

    """
    for static_path, static_content in theme.static_files.items():
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

    base_path = context.config.base_path
    if not base_path.endswith("/"):
        base_path = f"{base_path}/"

    template_name = context.frontmatter.template
    if template_name not in jinja_environment.list_templates():
        raise PageError(f'Template "{template_name}" not found.', input_path)

    wrapped_content = jinja_environment.get_template(template_name).render(
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
    render_markdown: Callable[[str], str] = markdown.markdown,
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
    render_markdown : Callable[[str], str], optional
        A function that converts markdown content to HTML. Should take markdown
        text (str) and return HTML (str). Defaults to :func:`markdown.markdown`.
        This allows for customization of the markdown rendering engine, such as
        using a different markdown library or adding custom extensions.

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

    Themes
    ~~~~~~

    The website's appearance is controlled by themes specified via ``config.theme.use``.
    Themes can be loaded in two ways:

    1. **Entry Point Name** (default): If ``config.theme.use`` does not contain slashes,
       it is treated as an entry point name in the ``"automata.website.themes"`` group.
       The default theme is ``"default"``. Custom themes can be registered as entry
       points in a package's ``pyproject.toml``::

           [project.entry-points."automata.website.themes"]
           my-theme = "my_package.themes.custom"

       The referenced module can either export a ``theme`` variable containing a
       ``Theme`` instance, or it can be a package with ``templates/`` and optionally
       ``static/`` subdirectories. If a ``theme`` variable is present, it will be used;
       otherwise, the module's resources will be loaded automatically.

    2. **Directory Path**: If ``config.theme.use`` contains slashes, it is treated as a
       filesystem path to a theme directory. The directory must contain a ``templates/``
       subdirectory with at least a ``base.html`` template, and optionally a ``static/``
       subdirectory for static assets.

    Theme Overrides
    ^^^^^^^^^^^^^^^

    Individual templates or static files can be overridden without creating a complete
    custom theme by specifying ``config.theme.overrides``. This should be a path to a
    directory containing ``templates/`` and/or ``static/`` subdirectories with files
    that should override those in the base theme.

    For example, to customize only the ``base.html`` template while using the default
    theme::

        overrides/
        └── templates/
            └── base.html

        config = Config(
            ...,
            theme=ThemeConfig(use="default", overrides="./overrides")
        )

    Files in the overrides directory take precedence over those in the base theme.
    Non-overridden files continue to use the base theme's versions. The overrides
    directory can contain only templates, only static files, or both.

    """

    # set default values for optional parameters
    if vars is None:
        vars = {}

    if now is None:
        now = datetime.datetime.now()

    materials_path = (
        pathlib.Path(config.content_directory) / config.materials_directory_name
    )

    # create url_for function based on config.base_path
    def url_for(path: str) -> str:
        return f"{config.base_path.rstrip('/')}/{path.lstrip('/')}"

    context = RenderContext(
        config=config,
        materials=_load_materials(materials_path),
        url_for=url_for,
        now=now,
        vars=vars,
    )

    theme, jinja_environment = _get_theme_and_jinja_environment(config)
    _copy_theme_static_files(theme, pathlib.Path(config.build_directory))

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
                partial(render_page_from_markdown, markdown_renderer=render_markdown),
                context,
            )
        elif path.suffix.lower() == ".html":
            _generate_single_page(
                path, output_path, jinja_environment, render_page_from_html, context
            )
        else:
            _copy_file_to_output(path, output_path, config)
