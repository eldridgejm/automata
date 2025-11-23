"""Tests for site generator functionality."""

from textwrap import dedent

from pytest import raises

import automata.website


def test_converts_pages_from_markdown_to_html(site):
    # given
    site.make_page("one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(site.path, site.builddir)

    # then
    assert '<h1 id="this-is-a-header">This is a header</h1>' in site.get_output(
        "one.html"
    )


def test_pages_have_access_to_published_artifacts(site):
    # given
    contents = (
        '${ materials.collections.homeworks.publications["01-intro"]'
        '.artifacts["homework.pdf"].path }'
    )
    site.make_page("one.md", contents)
    site.use_example_published("basic_published")

    # when
    automata.website.generate(
        site.path, site.builddir, materials_path=site.builddir / "published"
    )

    # then
    assert "published/homeworks/01-intro/homework.pdf" in site.get_output("one.html")


def test_pages_have_access_to_elements(site):
    # given
    site.make_page("one.md", "${ elements.announcement_box(config['announcement']) }")
    config = dedent(
        """
        announcement:
            content: This is a test.
            urgent: true
        """
    )
    site.add_to_config(config)

    # when
    automata.website.generate(site.path, site.builddir)

    # then
    assert "This is a test" in site.get_output("one.html")


def test_pages_are_rendered_in_base_template(site):
    # given
    site.make_page("one.md", "this is the page")

    # when
    automata.website.generate(site.path, site.builddir)

    # then
    assert "<html>" in site.get_output("one.html")


def test_raises_if_an_unknown_variable_is_accessed_during_page_render(site):
    # given
    site.make_page("one.md", "${ foo }")

    # when
    with raises(automata.website.PageError) as excinfo:
        automata.website.generate(site.path, site.builddir)

    assert "one.md" in str(excinfo.value)


def test_raises_if_an_unknown_attribute_is_accessed_during_page_render(site):
    # given
    site.make_page("one.md", "${ config.this_dont_exist }")

    # when
    with raises(automata.website.PageError) as excinfo:
        automata.website.generate(site.path, site.builddir)

    assert "one.md" in str(excinfo.value)


def test_raises_if_an_unknown_attribute_is_accessed_during_element_render(site):
    # given

    # x is in the element evaluation context, but y is not
    site.add_to_config(
        dedent(
            """
        announcement:
            contents: Here ${ y } is
        """
        )
    )
    site.make_page("one.md", "${ elements.announcement_box(config['announcement']) }")

    # when
    with raises(Exception):
        automata.website.generate(site.path, site.builddir)


def test_accepts_vars(site):
    # given
    site.make_page("test.md", "${ vars.foo }")

    # when
    automata.website.generate(site.path, site.builddir, vars={"foo": "barbaz"})

    # then
    assert "barbaz" in site.get_output("test.html")


def test_vars_available_in_config_file(site):
    # given
    site.add_to_config(
        dedent(
            """
                announcement:
                    content: My name is ${ vars.name }
                """
        )
    )
    site.make_page("one.md", "${ elements.announcement_box(config['announcement']) }")

    # when
    automata.website.generate(
        site.path, site.builddir, vars={"name": "Zaphod Beeblebrox"}
    )

    # then
    assert "Zaphod Beeblebrox" in site.get_output("one.html")


def test_raises_on_invalid_theme_config(site):
    """Test that invalid theme configuration raises RuntimeError."""
    # given
    site.make_page("one.md", "hello")

    # overwrite config without required page_title
    with (site.path / "config.yaml").open("w") as f:
        f.write("theme:\n  not_page_title: foo\n")

    # when/then
    with raises(RuntimeError) as excinfo:
        automata.website.generate(site.path, site.builddir)

    assert "Invalid theme config" in str(excinfo.value)


def test_config_includes_are_resolved_via_generate(site):
    """Ensure config.yaml !include directives are honored through generate."""
    parts = site.path / "config_parts"
    parts.mkdir()
    (parts / "theme.yaml").write_text("page_title: from include\n")
    (parts / "announcement.yaml").write_text("content: Included announcement!\n")
    with (site.path / "config.yaml").open("w") as fileobj:
        fileobj.write(
            dedent(
                """
                theme: !include config_parts/theme.yaml
                announcement: !include config_parts/announcement.yaml
                """
            )
        )

    site.make_page("one.md", "${ config['announcement']['content'] }")

    automata.website.generate(site.path, site.builddir)

    assert "Included announcement!" in site.get_output("one.html")
