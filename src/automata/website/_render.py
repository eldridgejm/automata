"""Functions for rendering pages in a course website."""

import dataclasses
import datetime
from typing import Any, Callable

import jinja2
import markdown
import smartconfig

from ..materials import ExportedArtifact, Universe
from ._config import WebsiteConfig
from ._frontmatter import Frontmatter


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
        When called from :func:`automata.website.generate`, this is passed
        :func:`automata.util.markdown.render` which enables the TOC extension.

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
