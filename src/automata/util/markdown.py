"""Utilities for rendering markdown content."""

from typing import Any, Dict, Match

import mistune
from mistune.directives import (
    Admonition,
    DirectivePlugin,
    RSTDirective,
    TableOfContents,
)

# details directive ====================================================================


class Details(DirectivePlugin):
    """Custom directive for creating collapsible sections using details/summary."""

    def parse(self, block, m: Match[str], state) -> Dict[str, Any]:
        """Parse the details directive."""
        title = self.parse_title(m)
        if not title:
            title = "Click to expand"

        content = self.parse_content(m)
        children = self.parse_tokens(block, content, state)

        return {
            "type": "details",
            "children": [
                {"type": "details_title", "text": title},
                {"type": "details_content", "children": children},
            ],
        }

    def __call__(self, directive, md) -> None:
        """Register the details directive with the markdown parser."""
        directive.register("details", self.parse)

        assert md.renderer is not None
        if md.renderer.NAME == "html":
            md.renderer.register("details", render_html_details)
            md.renderer.register("details_title", render_html_details_title)
            md.renderer.register("details_content", lambda _renderer, text: text)


def render_html_details(_renderer, text: str) -> str:
    """Render a details container as HTML details element."""
    return f"<details>\n{text}</details>\n"


def render_html_details_title(_renderer, text: str) -> str:
    """Render a details title as HTML summary element."""
    # Render the title as markdown to support bold, italic, links, etc.
    title_html = mistune.html(text)
    # Remove wrapping <p> tags if present
    is_wrapped = (
        isinstance(title_html, str)
        and title_html.startswith("<p>")
        and title_html.endswith("</p>\n")
    )
    if is_wrapped:
        title_html = title_html[3:-5]
    return f"<summary>{title_html}</summary>\n"


# render() =============================================================================


def render(text: str) -> str:
    """Renders markdown content to HTML with TOC, Admonition, and Details plugins.

    This is a wrapper around :func:`mistune.create_markdown` that enables the
    Table of Contents (TOC), Admonition, and Details plugins by default.

    - TOC: Use ``.. toc::`` directive
    - Admonitions: Use directives like ``.. note::``, ``.. warning::``, etc.
    - Details: Use ``.. details:: Title`` directive for collapsible sections

    The details directive supports markdown in the title, allowing for bold,
    italic, links, and other formatting.

    Parameters
    ----------
    text : str
        The markdown text to render.

    Returns
    -------
    str
        The rendered HTML content.

    Examples
    --------
    >>> render("# Heading\\n\\n.. toc::\\n\\n## Section 1")
    '<h1>Heading</h1>\\n<div class="toc">...</div>\\n<h2>Section 1</h2>'

    """
    # Type ignore needed due to mistune's plugin type annotations
    md = mistune.create_markdown(
        plugins=[RSTDirective([TableOfContents(), Admonition(), Details()])],  # type: ignore[list-item]
        escape=False,  # necessary to prevent escaping of HTML within the markdown
    )
    result = md(text)
    # mistune returns str when rendering, but type hints may be broad
    assert isinstance(result, str)
    return result
