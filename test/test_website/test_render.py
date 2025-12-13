"""Tests for the automata.website.render module."""

from pytest import raises

from automata.materials import Universe
from automata.website import (
    Config,
    RenderContext,
    render_page_from_html,
    render_page_from_markdown,
)

# markdown =============================================================================


def test_from_markdown_converts_markdown_to_html(tmpsite):
    # given
    markdown_content = "# Hello, world!"
    config = Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )
    context = RenderContext(config=config, materials=Universe(collections={}))

    # when
    rendered_content = render_page_from_markdown(
        markdown_content,
        context,
    )

    # then
    assert "<h1>Hello, world!</h1>" in rendered_content


def test_from_markdown_interpolates(tmpsite):
    """Tests that the rendering context is provided."""

    # given
    markdown_content = "The value of 'foo' is ${ vars.foo }."
    config = Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )
    context = RenderContext(
        config=config, vars={"foo": "bar"}, materials=Universe(collections={})
    )

    # when
    rendered_content = render_page_from_markdown(
        markdown_content,
        context,
    )

    # then
    assert "The value of 'foo' is bar." in rendered_content


def test_from_markdown_raises_for_missing_variable(tmpsite):
    """Tests that missing variables raise an error."""

    # given
    markdown_content = "The value of 'foo' is ${ foo }."
    config = Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )
    context = RenderContext(config=config, materials=Universe(collections={}))

    # when / then
    with raises(Exception) as exc_info:
        render_page_from_markdown(
            markdown_content,
            context,
        )

    assert "foo" in str(exc_info.value)


# html =================================================================================


def test_from_html_interpolates(tmpsite):
    """Tests that the rendering context is provided."""

    # given
    html_content = "<p>The value of 'foo' is ${ vars.foo }.</p>"
    config = Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )
    context = RenderContext(
        config=config, vars={"foo": "bar"}, materials=Universe(collections={})
    )

    # when
    rendered_content = render_page_from_html(
        html_content,
        context,
    )

    # then
    assert "<p>The value of 'foo' is bar.</p>" in rendered_content


def test_from_html_raises_for_missing_variable(tmpsite):
    """Tests that missing variables raise an error."""

    # given
    html_content = "<p>The value of 'foo' is ${ foo }.</p>"
    config = Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )
    context = RenderContext(config=config, materials=Universe(collections={}))

    # when / then
    with raises(Exception) as exc_info:
        render_page_from_html(
            html_content,
            context,
        )

    assert "foo" in str(exc_info.value)
