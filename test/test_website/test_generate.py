"""Tests for site generator functionality."""

from pytest import mark, raises

import automata.website
import automata.website.elements


def test_converts_pages_from_markdown_to_html(site, config):
    # given
    site.make_page("one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(config)

    # then
    assert '<h1 id="this-is-a-header">This is a header</h1>' in site.get_output(
        "one.html"
    )


def test_pages_have_access_to_published_artifacts(site, config):
    # given
    contents = (
        '${ materials.collections.homeworks.publications["01-intro"]'
        '.artifacts["homework.pdf"].path }'
    )
    site.make_page("one.md", contents)
    site.use_example_materials("basic_published")

    # when
    automata.website.generate(config)

    # then
    assert "materials/homeworks/01-intro/homework.pdf" in site.get_output("one.html")


def test_pages_have_access_to_element_configs(site, config):
    # given
    site.make_page(
        "one.md",
        "${ elements.announcement_box(config['elements']['announcement_box']) }",
    )

    config = config._as_dict()
    config["elements"]["announcement_box"] = {
        "content": "This is a test",
        "urgent": False,
    }
    config = automata.website.Config._from_dict(config)

    # when
    automata.website.generate(config)

    # then
    assert "This is a test" in site.get_output("one.html")


@mark.xfail
def test_good_error_message_when_invalid_variable_in_element_config(site, config):
    # given
    site.make_page(
        "one.md",
        "${ elements.announcement_box(this_dont_exist) }",
    )

    config = config._as_dict()
    config["elements"]["announcement_box"] = {
        "content": "This is a test with ${ invalid_variable }",
        "urgent": False,
    }
    config = automata.website.Config._from_dict(config)

    # when
    with raises(automata.website.PageError) as excinfo:
        automata.website.generate(config)

    assert "this_doesnt_exist" in str(excinfo.value)


def test_pages_are_rendered_in_base_template(site, config):
    # given
    site.make_page("one.md", "this is the page")

    # when
    automata.website.generate(config)

    # then
    assert "<html>" in site.get_output("one.html")


def test_raises_if_an_unknown_variable_is_accessed_during_page_render(site, config):
    # given
    site.make_page("one.md", "${ foo }")

    # when
    with raises(automata.website.PageError) as excinfo:
        automata.website.generate(config)

    assert "one.md" in str(excinfo.value)


def test_raises_if_an_unknown_attribute_is_accessed_during_page_render(site, config):
    # given
    site.make_page("one.md", "${ config.this_dont_exist }")

    # when
    with raises(automata.website.PageError) as excinfo:
        automata.website.generate(config)

    assert "one.md" in str(excinfo.value)


@mark.xfail
def test_raises_if_an_unknown_attribute_is_accessed_during_element_render(site, config):
    # given

    config = config._as_dict()
    # x is in the element evaluation context, but y is not
    config["announcement"] = {"contents": "Here ${ y } is"}
    config = automata.website.Config._from_dict(config)

    site.make_page(
        "one.md", "${ elements.announcement_box(config['elements']['announcement']) }"
    )

    # when
    with raises(Exception) as excinfo:
        automata.website.generate(config)

    assert "one.md" in str(excinfo.value)


def test_accepts_vars(site, config):
    # given
    site.make_page("test.md", "${ vars.foo }")

    # when
    automata.website.generate(config, vars={"foo": "barbaz"})

    # then
    assert "barbaz" in site.get_output("test.html")
