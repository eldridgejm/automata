"""Generates a course website."""

import copy
import dataclasses
import datetime
import pathlib
import posixpath
import shutil
from importlib.resources.abc import Traversable
from typing import Any, Callable, Container, Mapping, Sequence, cast

import jinja2
import smartconfig
import smartconfig.exceptions
import smartconfig.types

from ..extensions import Extension, apply_extensions
from ..extensions._apply import all_extensions
from ..hooks import (
    RenderExtraPagesHookArgs,
    RenderHooks,
    RenderPostHookArgs,
    WebsiteInputs,
)
from ..materials import ExportedArtifact, Universe, deserialize
from ..util import markdown as markdown_util
from ..util.resolution import describe_config_error, format_keypath
from ..util.yaml import SourceMap
from ._content import Page
from ._frontmatter import Frontmatter, FrontmatterError, read_frontmatter
from .exceptions import PageError, WebsiteError


@dataclasses.dataclass
class RenderContext:
    """Context available at the time of rendering."""

    # the course materials universe
    materials: Universe[ExportedArtifact]

    # function to generate URLs for given paths
    url_for: Callable[[str], str]

    # elements avaiable during rendering. These should be already bound to the render
    # context, so that they take at most one argument: the element configuration.
    # If the configuration is omitted, the element's configured default is used.
    elements: dict[str, Callable[..., str]] = dataclasses.field(default_factory=dict)

    # the current date and time
    current_time: datetime.datetime = dataclasses.field(
        default_factory=datetime.datetime.now
    )

    # variables available for interpolation in the content
    vars: dict[str, Any] = dataclasses.field(default_factory=dict)

    # the course (name, title, term, first week), from automata.yaml
    course: dict[str, Any] = dataclasses.field(default_factory=dict)

    # base URL path for the site
    base_path: str = "/"

    # frontmatter for the current page
    frontmatter: Frontmatter = dataclasses.field(
        default_factory=lambda: Frontmatter(vars={})
    )

    # the site's theme, if known; templates read its config as theme.config
    theme: Extension | None = None

    # all loaded extensions (including the theme and dependencies), keyed by name
    extensions: dict[str, Extension] = dataclasses.field(default_factory=dict)

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
        undefined=smartconfig.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    ).render(**context.to_dict())


class _NamedDictLoader(jinja2.DictLoader):
    """A DictLoader that gives each template its name as its filename.

    Jinja reports errors in a template at its filename, so this lets error
    messages name the theme template and line.

    """

    def get_source(self, environment, template):
        source, _, uptodate = super().get_source(environment, template)
        return source, template, uptodate


def _template_line(
    traceback: Any, filenames: Container[str], outermost: bool = False
) -> tuple[str, int] | None:
    """The template and line at which a Jinja rendering error occurred.

    Jinja rewrites tracebacks so that frames in template code have the
    template's filename and line. This returns the innermost (or outermost)
    such frame whose filename is in *filenames*, or None if there is none.

    """
    found = None
    while traceback is not None:
        filename = traceback.tb_frame.f_code.co_filename
        if filename in filenames:
            found = (filename, traceback.tb_lineno)
            if outermost:
                break
        traceback = traceback.tb_next
    return found


def _create_jinja_environment(templates: dict[str, str]) -> jinja2.Environment:
    """Create a Jinja2 environment from a dictionary of templates."""
    return jinja2.Environment(
        loader=_NamedDictLoader(templates),
        undefined=smartconfig.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )


def _load_materials(
    materials_directory_path: pathlib.Path,
) -> Universe[ExportedArtifact]:
    """Loads the materials from the given path."""
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


def _write_static_files(
    static_files: dict[str, str | bytes | Traversable],
    build_directory: pathlib.Path,
) -> None:
    """Write static files to the build directory.

    Handles three types of static file content:
    - str: written as text
    - bytes: written as binary
    - Traversable (or any object with read_bytes()): read then written as binary

    """
    for static_path, static_content in static_files.items():
        output_path = build_directory / static_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(static_content, bytes):
            output_path.write_bytes(static_content)
        elif isinstance(static_content, str):
            output_path.write_text(static_content)
        else:
            # Traversable - read and write bytes
            output_path.write_bytes(static_content.read_bytes())


def _page_base_path(base_path: str, page_path: str) -> str:
    """The base path to use in the page at *page_path* (relative to the site).

    An absolute base path (``/`` or ``/course/``) or a URL is the same on every
    page. A relative one (e.g. ``.``) is relative to the site's root, so a page
    in a subdirectory reaches it through ``..``.
    """
    if base_path.startswith("/") or "://" in base_path:
        return base_path
    depth = page_path.count("/")
    return posixpath.normpath(posixpath.join(*([".."] * depth), base_path))


def _create_url_for(base_path: str) -> Callable[[str], str]:
    """Create a url_for function that respects the site's base path."""

    def url_for(path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{base_path.rstrip('/')}/{path.lstrip('/')}"

    return url_for


class _BoundElement:
    """An element instance whose configuration defaults to its configured value.

    Calling it without a configuration uses ``website.elements.<name>``, or an
    empty configuration if none is set. Calling it with a configuration uses that
    configuration alone; the configured value is ignored.

    """

    def __init__(
        self,
        name: str,
        element: Callable[[smartconfig.types.Configuration], str],
        configured: smartconfig.types.Configuration | None,
        config_source_map: SourceMap | None = None,
    ):
        self.name = name
        self.element = element
        self.configured = configured
        self.config_source_map = config_source_map

    def __call__(self, *args: smartconfig.types.Configuration) -> str:
        if len(args) > 1:
            raise WebsiteError(
                f"elements.{self.name} takes at most one argument (its "
                f"configuration), but was given {len(args)}."
            )
        config = args[0] if args else None
        key = ("website", "elements", self.name)

        # where the configuration came from, as a prefix for error messages
        note = ""
        source_map = None
        if config is not None:
            where = f"the configuration passed to elements.{self.name}"
            prefix: tuple = ()
            if self.configured is not None:
                note = (
                    f" ({format_keypath(key)} is ignored when a configuration is "
                    f"passed.)"
                )
        else:
            where = None
            prefix = key
            # the configuration is in automata.yaml (or a file it includes)
            source_map = self.config_source_map
            if self.configured is not None:
                config = self.configured
            else:
                config = {}
                note = (
                    f" ({format_keypath(key)} is not set, and the page passed no "
                    f"configuration.)"
                )

        try:
            return self.element(config)
        except smartconfig.exceptions.ResolutionError as e:
            message = describe_config_error(
                e.reason, (*prefix, *e.keypath), source_map=source_map
            )
            if where is not None:
                message = f"{where}: {message}"
            raise WebsiteError(message + note) from None
        except smartconfig.exceptions.Error as e:
            raise WebsiteError(
                f'Invalid configuration for element "{self.name}": {e}{note}'
            ) from e


def _create_render_context(
    materials: Universe[ExportedArtifact],
    url_for: Callable[[str], str],
    current_time: datetime.datetime,
    vars: dict[str, Any],
    base_path: str,
    elements: dict[str, type],
    jinja_environment: jinja2.Environment,
    element_configs: dict[str, smartconfig.types.Configuration],
    theme: Extension | None,
    extensions: dict[str, Extension],
    config_source_map: SourceMap | None = None,
    course: dict[str, Any] | None = None,
) -> RenderContext:
    """Create the render context with elements bound."""
    context = RenderContext(
        materials=materials,
        url_for=url_for,
        current_time=current_time,
        vars=vars,
        course=course if course is not None else {},
        base_path=base_path,
        theme=theme,
        extensions=extensions,
    )

    context.elements = {
        name: _BoundElement(
            name,
            element(jinja_environment, context),
            element_configs.get(name),
            config_source_map,
        )
        for name, element in elements.items()
    }

    return context


def _copy_materials_to_build(
    materials_directory: pathlib.Path,
    build_directory: pathlib.Path,
    materials_directory_name: str,
) -> None:
    """Copy the materials directory to the build directory."""
    materials_output_path = build_directory / materials_directory_name

    if materials_directory.resolve() != materials_output_path.resolve():
        materials_output_path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            materials_directory,
            materials_output_path,
            dirs_exist_ok=True,
        )


def _render_page(
    page: Page,
    path: pathlib.Path,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    markdown_renderer: Callable[[str], str] | None = None,
) -> str:
    """Renders page content to HTML.

    Errors are raised as :class:`PageError` naming *path* and, where known,
    the line of the page or of the theme template.

    """
    base_path = page.source.parent if page.source is not None else None
    try:
        frontmatter, content = read_frontmatter(
            page.content, base_path=base_path, vars=context.vars, course=context.course
        )
    except FrontmatterError as e:
        raise PageError(e.message, path, e.line) from e
    except Exception as e:
        raise PageError(str(e), path) from e

    # lines before the content (the frontmatter), so that errors give the line of
    # the file rather than of the content
    offset = page.content[: len(page.content) - len(content)].count("\n")

    # create a new context with the frontmatter
    context = dataclasses.replace(context, frontmatter=frontmatter)

    # interpolate variables in the content
    try:
        rendered_content = _interpolate(content, context)
    except jinja2.TemplateSyntaxError as e:
        raise PageError(e.message or str(e), path, e.lineno + offset) from e
    except Exception as e:
        # the page is the outermost template; elements render their own inside it
        where = _template_line(e.__traceback__, {"<template>"}, outermost=True)
        line = where[1] + offset if where is not None else None
        raise PageError(str(e), path, line) from e

    # render markdown to HTML if a markdown renderer is provided
    if markdown_renderer is not None:
        rendered_content = markdown_renderer(rendered_content)

    base_url_path = context.base_path
    if not base_url_path.endswith("/"):
        base_url_path = f"{base_url_path}/"

    template_name = context.frontmatter.template
    if template_name not in jinja_environment.list_templates():
        raise WebsiteError(f'Template "{template_name}" not found.')

    try:
        return jinja_environment.get_template(template_name).render(
            **context.to_dict(),
            base_url_path=base_url_path,
            content=rendered_content,
        )
    except jinja2.TemplateSyntaxError as e:
        message = f"template {e.name}, line {e.lineno}: {e.message}"
        raise PageError(message, path) from e
    except Exception as e:
        where = _template_line(e.__traceback__, jinja_environment.list_templates())
        message = str(e)
        if where is not None:
            message = f"template {where[0]}, line {where[1]}: {message}"
        raise PageError(message, path) from e


def _fix_artifact_paths(
    materials: Universe[ExportedArtifact],
    url_for: Callable[[str], str],
) -> None:
    """Fixes artifact paths so that they take into account the website's base path."""
    for collection in materials.collections.values():
        for publication in collection.publications.values():
            for artifact in publication.artifacts.values():
                artifact.path = url_for(str(artifact.path))


def _process_pages(
    pages: dict[str, str | Page],
    build_directory: pathlib.Path,
    jinja_environment: jinja2.Environment,
    context_for: Callable[[str], RenderContext],
    render_markdown: Callable[[str], str],
) -> None:
    """Process page content and write rendered HTML to the build directory.

    Each page is interpolated, rendered as Markdown, and wrapped in a template,
    except that a page read from an ``.html`` file isn't rendered as Markdown
    (which would mangle it: an HTML block ends at a blank line, and an indented
    line after it would become code). Pages without a source file (such as
    extensions' pages) are rendered as Markdown. Keys are output paths (should
    end in ``.html``). *context_for* gives the render context for a page's
    output path.

    """
    for relative_path, page in pages.items():
        output_path = build_directory / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(page, str):
            page = Page(page)
        # errors name the source file, or the output path of pages without one
        path = page.source or pathlib.Path(relative_path)

        is_html = page.source is not None and page.source.suffix.lower() == ".html"
        try:
            rendered = _render_page(
                page,
                path,
                jinja_environment,
                context_for(relative_path),
                markdown_renderer=None if is_html else render_markdown,
            )
        except PageError:
            raise
        except Exception as e:
            raise PageError(str(e), path) from e

        output_path.write_text(rendered)


def _write_static_content(
    static_content: dict[str, str | bytes],
    build_directory: pathlib.Path,
) -> None:
    """Write user-provided static content to the build directory."""
    for relative_path, content in static_content.items():
        output_path = build_directory / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            output_path.write_bytes(content)
        else:
            output_path.write_text(content)


def render(
    build_directory: pathlib.Path,
    materials_directory: pathlib.Path,
    pages: Mapping[str, str | Page] | None = None,
    static_content: dict[str, str | bytes] | None = None,
    vars: dict[str, Any] | None = None,
    course: dict[str, Any] | None = None,
    current_time: datetime.datetime | None = None,
    render_markdown: Callable[[str], str] = markdown_util.render,
    hooks: RenderHooks | None = None,
    base_path: str = "/",
    materials_directory_name: str = "materials",
    element_configs: dict[str, smartconfig.types.Configuration] | None = None,
    config_source_map: SourceMap | None = None,
    theme: Extension | None = None,
    extensions: Sequence[Extension] = (),
    materials: Universe[ExportedArtifact] | None = None,
):
    """Generates a static website from course materials.

    Extensions contribute website inputs (templates, static files, elements,
    pages) by registering hooks on ``on_render_collect``. The generation
    pipeline collects these inputs, renders pages, and produces the final
    website.

    Parameters
    ----------
    build_directory : pathlib.Path
        Path to the output directory.
    materials_directory : pathlib.Path
        The path to the directory containing the exported materials. Its
        ``materials.json`` is read unless *materials* is given.
    pages : Mapping[str, str | Page], optional
        Pre-loaded page content. Keys are output paths (e.g.,
        ``"index.html"``). Values are page content (Markdown or HTML).
        All pages are rendered as Markdown, interpolated, and wrapped
        in a template.
    static_content : dict[str, str | bytes], optional
        Pre-loaded static content. Keys are output paths; values are
        string or bytes content written directly to the build directory.
    vars : dict[str, Any], optional
        A dictionary of variables to be used during rendering.
    current_time : datetime.datetime, optional
        The current date and time to be used during rendering.
    render_markdown : Callable[[str], str], optional
        A function that converts markdown content to HTML.
    hooks : RenderHooks, optional
        Hooks instance. If given, *theme* and *extensions* should already be
        registered on it; they are not registered again. If omitted, hooks
        are created and *theme* and *extensions* are registered on them.
    base_path : str, optional
        URL base path for the site (default ``"/"``).
    materials_directory_name : str, optional
        Name of the materials subdirectory in the build directory
        (default ``"materials"``).
    element_configs : dict[str, Configuration], optional
        Configurations for elements, keyed by element name. An element called
        without a configuration uses its entry here (or an empty configuration
        if it has none).
    config_source_map : SourceMap, optional
        The source map of the file the element configurations were read from
        (``automata.yaml``, keyed from its root), used to give the file and line
        of element configuration errors.
    theme : Extension, optional
        The site's theme, available in templates as ``theme``.
    extensions : Sequence[Extension], optional
        The site's other extensions. These, the theme, and their dependencies
        are available in templates as ``extensions``, keyed by name.
    materials : Universe[ExportedArtifact], optional
        The exported materials to render with, in place of reading
        ``materials.json`` from *materials_directory*. It is not modified.

    """
    # set default values for optional parameters
    pages = pages or {}
    static_content = static_content or {}
    vars = vars or {}
    element_configs = element_configs or {}
    current_time = current_time or datetime.datetime.now()
    loaded = [ext for ext in (theme, *extensions) if ext is not None]
    if hooks is None:
        hooks = RenderHooks()
        apply_extensions(loaded, hooks)

    # gather website inputs from extensions
    inputs = hooks.on_render_collect(WebsiteInputs())

    if "page.html" not in inputs.templates:
        raise WebsiteError('No extension provided a "page.html" template.')

    unknown_elements = sorted(set(element_configs) - set(inputs.elements))
    if unknown_elements:
        raise WebsiteError(
            f"website.elements configures unknown element(s): "
            f"{', '.join(unknown_elements)}. "
            f"Available elements: {', '.join(sorted(inputs.elements)) or 'none'}."
        )

    # run on_render_extra_pages hooks
    pre_args = hooks.on_render_extra_pages(
        RenderExtraPagesHookArgs(build_directory=build_directory, extra_content=None)
    )

    # collect extra pages from extensions and on_render_extra_pages hooks
    all_pages = dict(pages)
    if inputs.pages:
        # extension pages go first; explicit pages override
        all_pages = {**inputs.pages, **all_pages}
    if pre_args.extra_content:
        for key, value in pre_args.extra_content.items():
            if isinstance(value, str):
                all_pages[key] = value

    # set up jinja environment and write extension static files
    jinja_environment = _create_jinja_environment(inputs.templates)
    _write_static_files(inputs.static_files, build_directory)

    # load materials. Their artifact paths are rewritten for each page's base
    # path, so the given materials are copied rather than modified
    if materials is None:
        materials = _load_materials(materials_directory)

    # a render context for each base path (one, unless the base path is
    # relative, in which case it depends on the depth of the page)
    contexts: dict[str, RenderContext] = {}

    def context_for(page_path: str) -> RenderContext:
        page_base_path = _page_base_path(base_path, page_path)
        if page_base_path not in contexts:
            url_for = _create_url_for(page_base_path)
            page_materials = copy.deepcopy(materials)
            _fix_artifact_paths(page_materials, url_for)
            contexts[page_base_path] = _create_render_context(
                page_materials,
                url_for,
                current_time,
                vars,
                page_base_path,
                inputs.elements,
                jinja_environment,
                element_configs,
                theme,
                all_extensions(loaded),
                config_source_map,
                course=course,
            )
        return contexts[page_base_path]

    # process pages and static content
    _process_pages(
        all_pages,
        build_directory,
        jinja_environment,
        context_for,
        render_markdown,
    )
    _write_static_content(static_content, build_directory)

    # write binary extra content from on_render_extra_pages hooks
    if pre_args.extra_content:
        binary_extra: dict[str, str | bytes] = {}
        for key, value in pre_args.extra_content.items():
            if isinstance(value, bytes):
                binary_extra[key] = value
            elif isinstance(value, pathlib.Path):
                binary_extra[key] = value.read_bytes()
        if binary_extra:
            _write_static_content(binary_extra, build_directory)

    # finalize build
    _copy_materials_to_build(
        materials_directory, build_directory, materials_directory_name
    )
    hooks.on_render_post(RenderPostHookArgs(build_directory=build_directory))
