"""Generates a course website."""

import dataclasses
import datetime
import pathlib
import shutil
from functools import partial
from typing import Any, Callable, cast

import jinja2
import markdown
import smartconfig
import smartconfig.exceptions
import smartconfig.types

from ..materials import ExportedArtifact, Universe, deserialize
from ..util.resolution import resolve
from ._config import WebsiteConfig
from ._frontmatter import read_frontmatter
from ._render import RenderContext, render_page_from_html, render_page_from_markdown
from ._theme import Theme
from .exceptions import PageError, WebsiteError


def _resolve_theme_config(
    theme_config: dict[str, Any],
    schema: smartconfig.types.Schema | None,
) -> dict[str, Any]:
    """Resolve and validate theme configuration against schema.

    Parameters
    ----------
    theme_config : dict[str, Any]
        The raw theme configuration dictionary.
    schema : smartconfig.types.Schema | None
        The smartconfig schema to validate against. If None, no validation is performed.

    Returns
    -------
    Any
        The resolved configuration with defaults applied.

    Raises
    ------
    WebsiteError
        If the configuration does not match the schema.

    """
    if schema is None:
        return theme_config

    try:
        return resolve(theme_config, schema)
    except smartconfig.exceptions.ResolutionError as exc:
        raise WebsiteError(f"Invalid theme configuration: {exc}") from exc


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


def _get_theme(
    config: WebsiteConfig,
    extra_themes: dict[str, Theme] | None = None,
    cwd: pathlib.Path | None = None,
) -> Theme:
    """Creates a Jinja2 environment from the theme configuration.

    Loads the theme based on config.theme.use (either from entry point or directory
    path), applies any overrides from config.theme.overrides, and creates a Jinja2
    environment with the theme's templates.

    Parameters
    ----------
    config : WebsiteConfig
        The configuration containing theme settings.
    extra_themes : dict[str, Theme], optional
        Extra themes to search before entry points.
    cwd : pathlib.Path, optional
        Working directory for resolving relative paths. If None, uses current directory.

    Returns
    -------
    Theme
        The theme to use for rendering.

    """
    if cwd is None:
        cwd = pathlib.Path.cwd()

    # Load theme based on config - either from entry point or directory path
    if "/" in config.theme.use or "\\" in config.theme.use:
        # Path to custom theme directory (resolve relative to cwd)
        theme = Theme.from_directory(cwd / config.theme.use)
    else:
        # Entry point name (extra themes take priority)
        if extra_themes is not None and config.theme.use in extra_themes:
            theme = extra_themes[config.theme.use]
        else:
            theme = Theme.from_entry_point(config.theme.use)

    # Apply overrides if specified
    if config.theme.overrides is not None:
        overrides_dir = cwd / config.theme.overrides
        if overrides_dir.exists():
            # Allow override directories to have only static files
            override_theme = Theme.from_directory(
                overrides_dir, require_templates=False
            )
            # Merge overrides into base theme (overrides take precedence)
            theme.templates.update(override_theme.templates)
            theme.static_files.update(override_theme.static_files)

    if "page.html" not in theme.templates:
        raise ValueError('Theme templates must include a "page.html" file.')

    return theme


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
        frontmatter, content = read_frontmatter(
            raw_content, base_path=input_path.parent
        )
    except Exception as e:
        # Wrap any parsing errors with file path context
        raise PageError(str(e), input_path) from e

    # create a new context with the frontmatter
    context = dataclasses.replace(context, frontmatter=frontmatter)

    # render the content (without frontmatter)
    rendered_content = renderer(content, context)

    base_path = context.website_config.base_path
    if not base_path.endswith("/"):
        base_path = f"{base_path}/"

    template_name = context.frontmatter.template
    if template_name not in jinja_environment.list_templates():
        raise PageError(f'Template "{template_name}" not found.', input_path)

    wrapped_content = jinja_environment.get_template(template_name).render(
        **context.to_dict(),
        base_url_path=base_path,
        content=rendered_content,
    )
    output_path.write_text(wrapped_content)


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


def generate(
    config: WebsiteConfig,
    vars: dict[str, Any] | None = None,
    extra_themes: dict[str, Theme] | None = None,
    current_time: datetime.datetime | None = None,
    render_markdown: Callable[[str], str] = markdown.markdown,
    cwd: pathlib.Path | None = None,
):
    """Generates a static website from course materials.

    Parameters
    ----------
    config : WebsiteConfig
        The configuration for the website generation. Contains information about
        the location of the content and build directories, among other settings.
        See :class:`WebsiteConfig` for more details.
    vars : dict[str, Any], optional
        A dictionary of variables to be used during rendering.
    extra_themes : dict[str, Theme], optional
        A mapping of theme names to Theme instances that should be searched before
        entry points when resolving config.theme.use.
    current_time : datetime.datetime, optional
        The current date and time to be used during rendering.
    render_markdown : Callable[[str], str], optional
        A function that converts markdown content to HTML. Should take markdown
        text (str) and return HTML (str). Defaults to :func:`markdown.markdown`.
        This allows for customization of the markdown rendering engine, such as
        using a different markdown library or adding custom extensions.
    cwd : pathlib.Path, optional
        Working directory for resolving relative paths in config. All relative paths
        in the configuration (content_directory, build_directory, theme paths) will
        be resolved relative to this directory. If None, uses the current working
        directory. Absolute paths in config are used as-is regardless of cwd.

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

    When ``extra_themes`` is provided to :func:`generate`, it is checked before entry
    points when resolving ``config.theme.use``.

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

        config = WebsiteConfig(
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

    if current_time is None:
        current_time = datetime.datetime.now()

    if cwd is None:
        cwd = pathlib.Path.cwd()

    # Resolve paths relative to cwd (absolute paths are unchanged)
    content_dirpath = cwd / config.content_directory
    materials_dirpath = content_dirpath / config.materials_directory_name
    build_dirpath = cwd / config.build_directory

    # create url_for function based on config.base_path
    def url_for(path: str) -> str:
        return f"{config.base_path.rstrip('/')}/{path.lstrip('/')}"

    theme = _get_theme(config, extra_themes=extra_themes, cwd=cwd)

    # Resolve and validate theme configuration
    config.theme.config = _resolve_theme_config(
        theme_config=config.theme.config,
        schema=theme.schema,
    )

    jinja_environment = theme.create_jinja_environment()

    _copy_theme_static_files(theme, build_dirpath)

    materials = _load_materials(materials_dirpath)
    _fix_artifact_paths(materials, url_for)

    context = RenderContext(
        website_config=config,
        materials=materials,
        url_for=url_for,
        current_time=current_time,
        vars=vars,
    )

    context.elements = {
        name: element(jinja_environment, context)
        for name, element in theme.elements.items()
    }

    for path in _paths_outside_materials_directory(content_dirpath, materials_dirpath):
        relative_path = path.relative_to(content_dirpath)
        output_path = build_dirpath / relative_path

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

    # copy the built materials
    materials_output_path = build_dirpath / config.materials_directory_name
    materials_output_path.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        materials_dirpath,
        materials_output_path,
        dirs_exist_ok=True,
    )
