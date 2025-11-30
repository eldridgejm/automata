"""Tests for site generator functionality."""

from pytest import raises

import automata.website
import automata.website.elements

# basic page rendering =================================================================


def test_converts_pages_from_markdown_to_html(tmpsite):
    # given
    tmpsite.make_page("one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(tmpsite.content_path, tmpsite.output_path)

    # then
    assert '<h1 id="this-is-a-header">This is a header</h1>' in tmpsite.get_output(
        "one.html"
    )


def test_converts_pages_from_markdown_to_html_recursively(tmpsite):
    # given
    tmpsite.make_page("index.md", "Home page")
    tmpsite.make_page("subdir/one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(tmpsite.content_path, tmpsite.output_path)

    # then
    assert '<h1 id="this-is-a-header">This is a header</h1>' in tmpsite.get_output(
        "subdir/one.html"
    )

    assert "Home page" in tmpsite.get_output("index.html")


def test_copies_files_from_content_to_output(tmpsite):
    # given
    tmpsite.make_page("data/tabular/one.txt", "This is a text file in a subdir.")

    # when
    automata.website.generate(tmpsite.content_path, tmpsite.output_path)

    # then
    assert "This is a text file in a subdir." in tmpsite.get_output(
        "data/tabular/one.txt"
    )


# materials ============================================================================


def test_pages_have_access_to_materials(tmpsite):
    # given
    contents = (
        '${ materials.collections.homeworks.publications["01-intro"]'
        '.artifacts["homework.pdf"].path }'
    )
    tmpsite.make_page("one.md", contents)
    tmpsite.use_example_materials("basic_published")

    # when
    automata.website.generate(tmpsite.content_path, tmpsite.output_path)

    # then
    assert "materials/homeworks/01-intro/homework.pdf" in tmpsite.get_output("one.html")


def test_by_default_assumes_materials_path_in_output_directory(tmpsite):
    # given
    tmpsite.use_example_materials("basic_published")

    # when
    automata.website.generate(tmpsite.content_path, tmpsite.output_path)

    # then
    assert (tmpsite.output_path / "materials").is_dir()
    assert (tmpsite.output_path / "materials/materials.json").is_file()


def test_materials_are_copied_to_output_directory_if_necessary(tmpsite):
    # given
    # create some example materials outside of the output directory; we do this by
    # moving the materials path to a sibling directory
    tmpsite.use_example_materials("basic_published")
    outside_materials_path = tmpsite.output_path.parent / "external_materials"
    tmpsite.materials_path.rename(outside_materials_path)

    # when
    automata.website.generate(
        tmpsite.content_path, tmpsite.output_path, outside_materials_path
    )

    # then
    assert (tmpsite.output_path / "materials").is_dir()
    assert (tmpsite.output_path / "materials/materials.json").is_file()
    # we didn't change the original materials directory
    assert outside_materials_path.is_dir()


def test_raises_if_materials_json_is_missing(tmpsite):
    # given
    # delete the materials.json file
    (tmpsite.materials_path / "materials.json").unlink()

    # when
    with raises(automata.website.Error) as excinfo:
        automata.website.generate(tmpsite.content_path, tmpsite.output_path)

    assert "Expected to find materials.json" in str(excinfo.value)


# vars =================================================================================


def test_vars_are_available_at_render_time(tmpsite):
    # given
    tmpsite.make_page("test.md", "${ vars.foo }")

    # when
    automata.website.generate(
        tmpsite.content_path, tmpsite.output_path, vars={"foo": "barbaz"}
    )

    # then
    assert "barbaz" in tmpsite.get_output("test.html")


# themes ===============================================================================


def test_uses_default_theme_if_none_specified(tmpsite):
    # given
    tmpsite.make_page("one.md", "this is the page")

    # when
    automata.website.generate(tmpsite.content_path, tmpsite.output_path)

    # then
    assert "html>" in tmpsite.get_output("one.html")


def test_override_theme_templates(tmpsite):
    pass


"""

def test_pages_have_access_to_element_configs(tmpsite):
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
def test_good_error_message_when_invalid_variable_in_element_config(tmpsite):
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


def test_pages_are_rendered_in_base_template(tmpsite):
    # given
    site.make_page("one.md", "this is the page")

    # when
    automata.website.generate(config)

    # then
    assert "<html>" in site.get_output("one.html")


def test_raises_if_an_unknown_variable_is_accessed_during_page_render(tmpsite):
    # given
    site.make_page("one.md", "${ foo }")

    # when
    with raises(automata.website.PageError) as excinfo:
        automata.website.generate(config)

    assert "one.md" in str(excinfo.value)


def test_raises_if_an_unknown_attribute_is_accessed_during_page_render(tmpsite):
    # given
    site.make_page("one.md", "${ config.this_dont_exist }")

    # when
    with raises(automata.website.PageError) as excinfo:
        automata.website.generate(config)

    assert "one.md" in str(excinfo.value)


@mark.xfail
def test_raises_if_an_unknown_attribute_is_accessed_during_element_render(tmpsite):
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

"""
