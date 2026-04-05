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


def _copy_static_files(
    static_files: dict[str, str | bytes | Traversable],
    build_directory: pathlib.Path,
) -> None:
    """Copies static files to the build directory.

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
        name: element(jinja_environment, context)
        for name, element in elements.items()
    }

    return context


def _copy_materials_to_build(
    materials_directory: pathlib.Path,
    build_directory: pathlib.Path,
    config: WebsiteConfig,
) -> None:
    """Copy the materials directory to the build directory."""
    materials_output_path = build_directory / config.materials_directory_name

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
    if path.suffix.lower() == config.no_render_suffix and len(path.suffixes) > 1:
        output_path = output_path.with_suffix("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(path.read_bytes())


def _fix_artifact_paths(
    materials: Universe[ExportedArtifact],
    url_for: Callable[[str], str],
) -> None:
    """Fixes the path attribute so that it takes into account the website's base path."""
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

        if dirpath == materials_path:
            dirnames.clear()
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
    """Process all files in the content directory."""
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


def _process_extra_content(
    extra_content: dict[str, str | bytes | pathlib.Path],
    build_directory: pathlib.Path,
    jinja_environment: jinja2.Environment,
    context: RenderContext,
    render_markdown: Callable[[str], str],
) -> None:
    """Process extra content items and write them to the build directory."""
    for relative_path, content in extra_content.items():
        output_path = build_directory / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            output_path.write_bytes(content)
        elif isinstance(content, pathlib.Path):
            shutil.copy2(content, output_path)
        else:
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
    vars: dict[str, Any] | None = None,
    current_time: datetime.datetime | None = None,
    render_markdown: Callable[[str], str] = markdown_util.render,
    cwd: pathlib.Path | None = None,
    extra_content: dict[str, str | bytes | pathlib.Path] | None = None,
    hooks: GenerateHooks | None = None,
):
    """Generates a static website from course materials.

    Extensions contribute website inputs (templates, static files, elements,
    pages, variables) by registering hooks on ``on_website_collect``. The
    generation pipeline collects these inputs, then processes the content
    directory and produces the final website.

    Parameters
    ----------
    config : WebsiteConfig
        The configuration for the website generation.
    materials_directory : pathlib.Path
        The path to the directory containing the exported materials.
    vars : dict[str, Any], optional
        A dictionary of variables to be used during rendering.
    current_time : datetime.datetime, optional
        The current date and time to be used during rendering.
    render_markdown : Callable[[str], str], optional
        A function that converts markdown content to HTML.
    cwd : pathlib.Path, optional
        Working directory for resolving relative paths in config.
    extra_content : dict[str, str | bytes | pathlib.Path], optional
        Additional content to include in the generated output.
    hooks : GenerateHooks, optional
        Hooks instance. Extensions should already be registered on this
        before calling generate.

    """
    # set default values for optional parameters
    vars = vars or {}
    current_time = current_time or datetime.datetime.now()
    cwd = cwd or pathlib.Path.cwd()
    hooks = hooks or GenerateHooks()

    # resolve paths relative to cwd (absolute paths are unchanged)
    content_directory = cwd / config.content_directory
    build_directory = cwd / config.build_directory

    # gather website inputs from extensions
    inputs = hooks.on_website_collect(WebsiteInputs())

    if "page.html" not in inputs.templates:
        raise ValueError('No extension provided a "page.html" template.')

    # merge vars: extension defaults < explicit vars
    merged_vars = {**inputs.vars, **vars}

    # run pre-generate hooks
    url_for = _create_url_for(config.base_path)
    pre_args = hooks.on_generate_pre(
        GeneratePreHookArgs(config=config, extra_content=extra_content)
    )

    # combine extension pages + pre-hook extra content + explicit extra content
    all_extra_content: dict[str, str | bytes | pathlib.Path] = {}
    if inputs.pages:
        all_extra_content.update(inputs.pages)
    if pre_args.extra_content:
        all_extra_content.update(pre_args.extra_content)

    # set up jinja environment and copy static files
    jinja_environment = _create_jinja_environment(inputs.templates)
    _copy_static_files(inputs.static_files, build_directory)

    # load materials and create render context
    materials = _load_materials(materials_directory)
    _fix_artifact_paths(materials, url_for)
    context = _create_render_context(
        config, materials, url_for, current_time, merged_vars,
        inputs.elements, jinja_environment,
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
    if all_extra_content:
        _process_extra_content(
            all_extra_content,
            build_directory,
            jinja_environment,
            context,
            render_markdown,
        )

    # finalize build
    _copy_materials_to_build(materials_directory, build_directory, config)
    hooks.on_generate_post(GeneratePostHookArgs(config=config))
