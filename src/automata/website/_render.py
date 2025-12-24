"""Functions for rendering pages in a course website."""

import dataclasses
import datetime
from typing import Any, Callable

import jinja2
import markdown

from ..materials import ExportedArtifact, Universe
from ._config import Config
from ._frontmatter import Frontmatter


def DEFAULT_URL_FOR(path: str) -> str:
    """A placeholder for the default URL generation function."""
    # we need to know the base path from the config to implement this,
    # and we will do that in RenderContext.__post_init__.
    raise NotImplementedError("Default URL generation function is not set.")


@dataclasses.dataclass
class RenderContext:
    """Context available at the time of rendering."""

    # website configuration
    config: Config

    # the course materials universe
    materials: Universe[ExportedArtifact]

    # function to generate URLs for given paths. If None, a default
    # function will be provided that prepends the base_path from the config.
    url_for: Callable[[str], str] = DEFAULT_URL_FOR

    # function that returns the current date and time
    now: datetime.datetime = dataclasses.field(default_factory=datetime.datetime.now)

    # variables available for interpolation in the content
    vars: dict[str, Any] = dataclasses.field(default_factory=dict)

    # frontmatter for the current page
    frontmatter: Frontmatter = dataclasses.field(
        default_factory=lambda: Frontmatter(vars={})
    )

    def __post_init__(self):
        """Set the default url_for function."""

        if self.url_for is DEFAULT_URL_FOR:

            def url_for(path: str) -> str:
                return f"{self.config.base_path.rstrip('/')}/{path.lstrip('/')}"

            self.url_for = url_for


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
