"""Generates a course website."""

import dataclasses
import datetime
import pathlib
import shutil
from importlib.resources.abc import Traversable
from typing import Any, Callable, cast

import jinja2
import smartconfig
import smartconfig.types

from ..hooks import (
    GenerateHooks,
    GeneratePostHookArgs,
    GeneratePreHookArgs,
    WebsiteInputs,
)
from ..materials import ExportedArtifact, Universe, deserialize
from ..util import markdown as markdown_util
from ._frontmatter import Frontmatter, read_frontmatter
from .exceptions import PageError, WebsiteError


@dataclasses.dataclass
class RenderContext:
    """Context available at the time of rendering."""

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

    # base URL path for the site
    base_path: str = "/"

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


def _create_jinja_environment(templates: dict[str, str]) -> jinja2.Environment:
    """Create a Jinja2 environment from a dictionary of templates."""
    return jinja2.Environment(
        loader=jinja2.DictLoader(templates),
        undefined=jinja2.StrictUndefined,
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
    current_time: datetime.datetime,
    vars: dict[str, Any],
    base_path: str,
    elements: dict[str, type],
    jinja_environment: jinja2.Environment,
) -> RenderContext:
    """Create the render context with elements bound."""
    context = RenderContext(
        materials=materials,
        url_for=url_for,
        current_time=current_time,
        vars=vars,
        base_path=base_path,
    )

    context.elements = {
        name: element(jinja_environment, context)
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
    content: str,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    markdown_renderer: Callable[[str], str] | None = None,
    base_path: pathlib.Path | None = None,
) -> str:
    """Renders page content to HTML."""
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


def _fix_artifact_paths(
    materials: Universe[ExportedArtifact],
    url_for: Callable[[str], str],
) -> None:
    """Fixes the path attribute so that it takes into account the website's base path."""
    for collection in materials.collections.values():
        for publication in collection.publications.values():
            for artifact in publication.artifacts.values():
                artifact.path = url_for(str(artifact.path))


def _process_pages(
    pages: dict[str, str],
    build_directory: pathlib.Path,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    render_markdown: Callable[[str], str],
) -> None:
    """Process page content and write rendered HTML to the build directory.

    All pages are rendered as Markdown, interpolated, and wrapped in a
    template.  Keys are output paths (should end in ``.html``).

    """
    for relative_path, content in pages.items():
        output_path = build_directory / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            rendered = _render_page(
                content,
                jinja_environment,
                context,
                markdown_renderer=render_markdown,
            )
        except Exception as e:
            raise PageError(str(e), pathlib.Path(relative_path)) from e

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


def generate(
    build_directory: pathlib.Path,
    materials_directory: pathlib.Path,
    pages: dict[str, str] | None = None,
    static_content: dict[str, str | bytes] | None = None,
    vars: dict[str, Any] | None = None,
    current_time: datetime.datetime | None = None,
    render_markdown: Callable[[str], str] = markdown_util.render,
    hooks: GenerateHooks | None = None,
    base_path: str = "/",
    materials_directory_name: str = "materials",
):
    """Generates a static website from course materials.

    Extensions contribute website inputs (templates, static files, elements,
    pages, variables) by registering hooks on ``on_website_collect``. The
    generation pipeline collects these inputs, renders pages, and produces the
    final website.

    Parameters
    ----------
    build_directory : pathlib.Path
        Path to the output directory.
    materials_directory : pathlib.Path
        The path to the directory containing the exported materials.
    pages : dict[str, str], optional
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
    hooks : GenerateHooks, optional
        Hooks instance. Extensions should already be registered on this
        before calling generate.
    base_path : str, optional
        URL base path for the site (default ``"/"``).
    materials_directory_name : str, optional
        Name of the materials subdirectory in the build directory
        (default ``"materials"``).

    """
    # set default values for optional parameters
    pages = pages or {}
    static_content = static_content or {}
    vars = vars or {}
    current_time = current_time or datetime.datetime.now()
    hooks = hooks or GenerateHooks()

    # gather website inputs from extensions
    inputs = hooks.on_website_collect(WebsiteInputs())

    if "page.html" not in inputs.templates:
        raise ValueError('No extension provided a "page.html" template.')

    # merge vars: extension defaults < explicit vars
    merged_vars = {**inputs.vars, **vars}

    # run pre-generate hooks
    url_for = _create_url_for(base_path)
    pre_args = hooks.on_generate_pre(
        GeneratePreHookArgs(build_directory=build_directory, extra_content=None)
    )

    # collect extra pages from extensions and pre-generate hooks
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

    # load materials and create render context
    materials = _load_materials(materials_directory)
    _fix_artifact_paths(materials, url_for)
    context = _create_render_context(
        materials, url_for, current_time, merged_vars, base_path,
        inputs.elements, jinja_environment,
    )

    # process pages and static content
    _process_pages(
        all_pages,
        build_directory,
        jinja_environment,
        context,
        render_markdown,
    )
    _write_static_content(static_content, build_directory)

    # write binary extra content from pre-generate hooks
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
    _copy_materials_to_build(materials_directory, build_directory, materials_directory_name)
    hooks.on_generate_post(GeneratePostHookArgs(build_directory=build_directory))
