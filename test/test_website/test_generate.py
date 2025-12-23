import shutil

from pytest import raises

import automata.materials
import automata.website

# basic page rendering =================================================================


def test_converts_pages_from_markdown_to_html(tmpsite):
    # given
    tmpsite.make_page("one.md", "# This is a header\n**this is bold!**")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    assert "This is a header</h1>" in tmpsite.get_output("one.html")


def test_converts_pages_from_markdown_to_html_recursively(tmpsite):
    # given
    tmpsite.make_page("index.md", "Home page")
    tmpsite.make_page("subdir/one.md", "# This is a header\n**this is bold!**")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    assert "This is a header</h1>" in tmpsite.get_output("subdir/one.html")

    assert "Home page" in tmpsite.get_output("index.html")


def tests_renders_html_pages(tmpsite):
    # given
    tmpsite.make_page(
        "about.html", "<h1>About this site</h1><p>This site is great.</p>"
    )

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    assert "<h1>About this site</h1>" in tmpsite.get_output("about.html")


def test_copies_files_from_content_to_output(tmpsite):
    # given
    tmpsite.make_page("data/tabular/one.txt", "This is a text file in a subdir.")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    assert "This is a text file in a subdir." in tmpsite.get_output(
        "data/tabular/one.txt"
    )


def test_vars_can_be_used_in_markdown_pages(tmpsite):
    # given
    tmpsite.make_page("index.md", "The value of 'foo' is ${ vars.foo }.")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config, vars={"foo": "bar"})

    # then
    assert "The value of 'foo' is bar." in tmpsite.get_output("index.html")


def test_vars_can_be_used_in_html_pages(tmpsite):
    # given
    tmpsite.make_page("about.html", "<p>The value of 'foo' is ${ vars.foo }.</p>")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config, vars={"foo": "bar"})

    # then
    assert "<p>The value of 'foo' is bar.</p>" in tmpsite.get_output("about.html")


def test_files_with_raw_suffix_are_copied_with_raw_suffix_removed(tmpsite):
    # given
    tmpsite.make_page("data/sample.txt.NO_RENDER", "This is a raw text file.")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    assert "This is a raw text file." in tmpsite.get_output("data/sample.txt")


def test_html_files_with_raw_suffix_are_not_rendered(tmpsite):
    # given
    tmpsite.make_page(
        "info.html.NO_RENDER", "<h1>Info Page</h1><p>This is ${ vars.foo }.</p>"
    )

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config, vars={"foo": "bar"})

    # then
    assert "<h1>Info Page</h1><p>This is ${ vars.foo }.</p>" in tmpsite.get_output(
        "info.html"
    )


def test_markdown_files_with_raw_suffix_are_not_rendered(tmpsite):
    # given
    tmpsite.make_page("readme.md.NO_RENDER", "# Readme\nThis is ${ vars.foo }.")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config, vars={"foo": "bar"})

    # then
    assert "# Readme\nThis is ${ vars.foo }." in tmpsite.get_output("readme.md")


def test_raw_suffix_of_none_means_nothing_is_renamed(tmpsite):
    # given
    tmpsite.make_page("data/sample.txt.NO_RENDER", "This is a raw text file.")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        no_render_suffix=None,
    )

    # when
    automata.website.generate(config)

    # then
    assert "This is a raw text file." in tmpsite.get_output("data/sample.txt.NO_RENDER")


# materials ============================================================================


def test_materials_are_loaded_and_available_in_rendering_context(
    tmpsite, default_example_course
):
    # given
    universe = automata.materials.discover(
        default_example_course.path,
    )
    universe = automata.materials.build(
        universe, ignore_ready=True, ignore_release_time=True
    )
    universe = automata.materials.export(universe, tmpsite.materials_directory)
    materials_json = automata.materials.serialize(universe)

    (tmpsite.materials_directory / "materials.json").write_text(materials_json)

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    tmpsite.make_page(
        "materials.html",
        "<ul>"
        "{% for collection in materials.collections %}"
        "<li>${ collection }</li>"
        "{% endfor %}"
        "</ul>",
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("materials.html")
    assert "<li>homeworks</li>" in output
    assert "<li>default</li>" in output


def test_exception_is_raised_if_materials_directory_missing(tmpsite):
    # given
    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # delete the materials directory to simulate it being missing
    if tmpsite.materials_directory.exists():
        shutil.rmtree(tmpsite.materials_directory)

    tmpsite.make_page(
        "materials.html",
        "<ul>"
        "{% for collection in materials.collections %}"
        "<li>${ collection }</li>"
        "{% endfor %}"
        "</ul>",
    )

    # when / then
    with raises(automata.website.exceptions.Error) as exc:
        automata.website.generate(config)

    assert "Materials directory not found at" in str(exc.value)


def test_exception_is_raised_if_materials_json_missing(tmpsite):
    # given
    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # delete the materials.json to simulate it being missing
    materials_json_path = tmpsite.materials_directory / "materials.json"
    if materials_json_path.exists():
        materials_json_path.unlink()

    tmpsite.make_page(
        "materials.html",
        "<ul>"
        "{% for collection in materials.collections %}"
        "<li>${ collection }</li>"
        "{% endfor %}"
        "</ul>",
    )

    # when / then
    with raises(automata.website.exceptions.Error) as exc:
        automata.website.generate(config)

    assert "materials.json not found at" in str(exc.value)


# dependency injection =================================================================


def test_custom_markdown_renderer_can_be_injected(tmpsite):
    # given
    tmpsite.make_page("test.md", "# Header\nContent")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # custom renderer that adds a marker
    def custom_markdown_renderer(content, context):
        return f"[CUSTOM_MARKDOWN]{content}[/CUSTOM_MARKDOWN]"

    # when
    automata.website.generate(
        config, render_page_from_markdown=custom_markdown_renderer
    )

    # then
    output = tmpsite.get_output("test.html")
    assert "[CUSTOM_MARKDOWN]" in output
    assert "[/CUSTOM_MARKDOWN]" in output
    assert "# Header\nContent" in output


def test_custom_html_renderer_can_be_injected(tmpsite):
    # given
    tmpsite.make_page("test.html", "<h1>Header</h1><p>Content</p>")

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # custom renderer that adds a marker
    def custom_html_renderer(content, context):
        return f"[CUSTOM_HTML]{content}[/CUSTOM_HTML]"

    # when
    automata.website.generate(config, render_page_from_html=custom_html_renderer)

    # then
    output = tmpsite.get_output("test.html")
    assert "[CUSTOM_HTML]" in output
    assert "[/CUSTOM_HTML]" in output
    assert "<h1>Header</h1><p>Content</p>" in output


# frontmatter ==========================================================================


def test_frontmatter_in_markdown_page(tmpsite):
    # given
    tmpsite.make_page(
        "info.md",
        "---\nvars:\n\ttitle: Info Page\n\tauthor: Test Author\n---\n\n"
        "# ${ frontmatter.vars.title }\n\nBy ${ frontmatter.vars.author }",
    )

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("info.html")
    assert "<h1>Info Page</h1>" in output
    assert "By Test Author" in output


def test_frontmatter_in_html_page(tmpsite):
    # given
    tmpsite.make_page(
        "info.html",
        "---\nvars:\n\ttitle: Info Page\n\tauthor: Test Author\n---\n\n"
        "<h1>${ frontmatter.vars.title }</h1>\n<p>By ${ frontmatter.vars.author }</p>",
    )

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("info.html")
    assert "<h1>Info Page</h1>" in output
    assert "<p>By Test Author</p>" in output
