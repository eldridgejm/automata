"""Utilities for rendering markdown content."""

import markdown


def render(text: str) -> str:
    """Renders markdown content to HTML with TOC extension enabled.

    This is a wrapper around :func:`markdown.markdown` that enables the
    Table of Contents (TOC) extension by default. The TOC can be included
    in markdown content using the ``[TOC]`` directive.

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
    >>> render("# Heading\\n\\n[TOC]\\n\\n## Section 1")
    '<h1>Heading</h1>\\n<div class="toc">...</div>\\n<h2>Section 1</h2>'

    """
    return markdown.markdown(text, extensions=["toc"])
