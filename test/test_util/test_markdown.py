"""Tests for automata.util.markdown module."""

from automata.util.markdown import render


def test_render_basic():
    """Test that basic markdown rendering works."""
    result = render("# Heading")
    assert '<h1 id="heading">Heading</h1>' in result


def test_render_with_toc():
    """Test that TOC directive works."""
    markdown_text = """# Main Title

[TOC]

## Section 1

Some content.

## Section 2

More content.
"""
    result = render(markdown_text)

    # Should have headings with IDs
    assert '<h1 id="main-title">Main Title</h1>' in result
    assert '<h2 id="section-1">Section 1</h2>' in result
    assert '<h2 id="section-2">Section 2</h2>' in result

    # Should have TOC
    assert '<div class="toc">' in result


def test_render_without_toc_directive():
    """Test that rendering works without [TOC] directive."""
    markdown_text = """# Title

Content here.
"""
    result = render(markdown_text)

    # Should still have heading with ID
    assert '<h1 id="title">Title</h1>' in result

    # Should not have TOC div
    assert '<div class="toc">' not in result
