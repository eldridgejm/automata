"""Functions for rendering pages in a course website."""

import dataclasses
import datetime
from typing import Any, Callable

import jinja2
import markdown
import smartconfig

from ..materials import ExportedArtifact, Universe
from ._config import Config
from ._frontmatter import Frontmatter
from ._theme import Theme


@dataclasses.dataclass
class RenderContext:
    """Context available at the time of rendering."""

    # website configuration
    config: Config

    # the course materials universe
    materials: Universe[ExportedArtifact]

    # function to generate URLs for given paths
    url_for: Callable[[str], str]

    # the theme being used to render the page
    theme: Theme

    # elements avaiable during rendering. These should be already bound to the render
    # context, so that they only require one argument: the element configuration.
    elements: dict[str, Callable[[smartconfig.types.Configuration], str]] = (
        dataclasses.field(default_factory=dict)
    )

    # function that returns the current date and time
    now: datetime.datetime = dataclasses.field(default_factory=datetime.datetime.now)

    # variables available for interpolation in the content
    vars: dict[str, Any] = dataclasses.field(default_factory=dict)

    # frontmatter for the current page
    frontmatter: Frontmatter = dataclasses.field(
        default_factory=lambda: Frontmatter(vars={})
    )


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
    markdown_renderer: Callable[[str], str] = markdown.markdown,
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
