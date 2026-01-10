"""Tests for automata.util.markdown module."""

from automata.util.markdown import render


def test_render_basic():
    """Test that basic markdown rendering works."""
    result = render("# Heading")
    # Mistune renders basic headings without IDs by default
    assert "<h1>Heading</h1>" in result


def test_render_with_toc():
    """Test that TOC directive works."""
    markdown_text = """# Main Title

.. toc::

## Section 1

Some content.

## Section 2

More content.
"""
    result = render(markdown_text)

    # Should have TOC section
    assert '<details class="toc"' in result


def test_render_without_toc_directive():
    """Test that rendering works without .. toc:: directive."""
    markdown_text = """# Title

Content here.
"""
    result = render(markdown_text)

    assert '<details class="toc"' not in result


def test_render_with_admonition():
    """Test that admonition directives work."""
    markdown_text = """# Test

.. note::
   This is a note.

.. warning::
   This is a warning!
"""
    result = render(markdown_text)

    # Should have note admonition
    assert '<section class="admonition note">' in result
    assert '<p class="admonition-title">Note</p>' in result
    assert "This is a note." in result

    # Should have warning admonition
    assert '<section class="admonition warning">' in result
    assert '<p class="admonition-title">Warning</p>' in result
    assert "This is a warning!" in result


def test_render_with_details():
    """Test that details directive works."""
    markdown_text = """# Test

.. details:: **Bold title** with *italic* and a [link](http://example.com)

   This is the content inside.

   - Item 1
   - Item 2
"""
    result = render(markdown_text)

    # Should have details/summary structure
    assert "<details>" in result
    assert "<summary>" in result
    assert "</summary>" in result
    assert "</details>" in result

    # Should have markdown rendered in title
    assert "<strong>Bold title</strong>" in result
    assert "<em>italic</em>" in result
    assert '<a href="http://example.com">link</a>' in result

    # Should have content
    assert "This is the content inside." in result
    assert "<li>Item 1</li>" in result


def test_render_with_details_default_title():
    """Test that details directive uses default title when none provided."""
    markdown_text = """
.. details::

   Content here.
"""
    result = render(markdown_text)

    assert "<summary>Click to expand</summary>" in result
    assert "Content here." in result
