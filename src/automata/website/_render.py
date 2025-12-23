"""Functions for rendering pages in a course website."""

import dataclasses
import datetime
from typing import Any

import jinja2
import markdown

from ..materials import ExportedArtifact, Universe
from ._config import Config


@dataclasses.dataclass
class RenderContext:
    """Context available at the time of rendering."""

    config: Config
    materials: Universe[ExportedArtifact]
    now: datetime.datetime = dataclasses.field(default_factory=datetime.datetime.now)
    vars: dict[str, Any] = dataclasses.field(default_factory=dict)


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
    ).render(**dataclasses.asdict(context))


def render_page_from_markdown(
    markdown_content: str,
    context: RenderContext,
    markdown_renderer=markdown.markdown,
) -> str:
    """Renders a page from markdown.

    Parameters
    ----------
    markdown_content : str
        The markdown content to render.

    context : RenderContext
        The rendering context.

    markdown_renderer : Callable[[str], str], optional
        The function to use for rendering markdown to HTML. Should take markdown
        content (str) and return HTML (str). Defaults to :func:`markdown.markdown`.

    Returns
    -------
    str
        The rendered HTML content.
    """
    interpolated_markdown = _interpolate(
        markdown_content,
        context,
    )

    return markdown_renderer(interpolated_markdown)


def render_page_from_html(
    html_content: str,
    context: RenderContext,
) -> str:
    """Renders a page from HTML.

    Parameters
    ----------
    html_content : str
        The HTML content to render.

    context : RenderContext
        The rendering context.

    Returns
    -------
    str
        The rendered HTML content.
    """
    return _interpolate(
        html_content,
        context,
    )
