import shutil

import jinja2
import pytest
import smartconfig
from pytest import fixture, raises

import automata.website
from automata.exceptions import Error
from automata.extensions import (
    THEMES_GROUP,
    Extension,
    apply_extension,
    extension_from_directory,
    extension_from_entry_point,
)
from automata.hooks import (
    RenderExtraPagesHookArgs,
    RenderHooks,
    RenderPostHookArgs,
    WebsiteInputs,
)
from automata.util.yaml import parse_yaml_with_source_map


def _make_theme(theme_dir=None, entry_point="default", config=None):
    """Load a theme extension from a directory or an entry point."""
    if theme_dir is not None:
        return extension_from_directory("test-theme", theme_dir, config=config)
    return extension_from_entry_point(entry_point, config=config, group=THEMES_GROUP)


def _render(tmpsite, **kwargs):
    """Helper: load content from tmpsite and call render()."""
    pages, static_content = tmpsite.load_content()
    return automata.website.render(
        tmpsite.build_directory,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        **kwargs,
    )


@fixture
def theme():
    return extension_from_entry_point(
        "default",
        config={
            "short_title": "DSC 40B",
            "long_title": "Theoretical Foundations of Data Science II",
            "navigation": [],
            "rebuild_tailwind": False,
        },
        group=THEMES_GROUP,
    )


@fixture
def hooks(theme):
    h = RenderHooks()
    apply_extension(theme, h)
    return h


# basic page rendering =================================================================


def test_converts_pages_from_markdown_to_html(tmpsite, theme):
    # given
    tmpsite.make_page("one.md", "# This is a header\n**this is bold!**")

    # when
    _render(tmpsite, theme=theme)

    # then
    assert "This is a header</h1>" in tmpsite.get_output("one.html")


def test_converts_pages_from_markdown_to_html_recursively(tmpsite, theme):
    # given
    tmpsite.make_page("index.md", "Home page")
    tmpsite.make_page("subdir/one.md", "# This is a header\n**this is bold!**")

    # when
    _render(tmpsite, theme=theme)

    # then
    assert "This is a header</h1>" in tmpsite.get_output("subdir/one.html")

    assert "Home page" in tmpsite.get_output("index.html")


def tests_renders_html_pages(tmpsite, theme):
    # given
    tmpsite.make_page(
        "about.html", "<h1>About this site</h1><p>This site is great.</p>"
    )

    # when
    _render(tmpsite, theme=theme)

    # then
    assert "<h1>About this site</h1>" in tmpsite.get_output("about.html")


def test_copies_files_from_content_to_output(tmpsite, theme):
    # given
    tmpsite.make_page("data/tabular/one.txt", "This is a text file in a subdir.")

    # when
    _render(tmpsite, theme=theme)

    # then
    assert "This is a text file in a subdir." in tmpsite.get_output(
        "data/tabular/one.txt"
    )


def test_vars_can_be_used_in_markdown_pages(tmpsite, theme):
    # given
    tmpsite.make_page("index.md", "The value of 'foo' is ${ vars.foo }.")

    # when
    _render(tmpsite, vars={"foo": "bar"}, theme=theme)

    # then
    assert "The value of 'foo' is bar." in tmpsite.get_output("index.html")


def test_vars_can_be_used_in_html_pages(tmpsite, theme):
    # given
    tmpsite.make_page("about.html", "<p>The value of 'foo' is ${ vars.foo }.</p>")

    # when
    _render(tmpsite, vars={"foo": "bar"}, theme=theme)

    # then
    assert "<p>The value of 'foo' is bar.</p>" in tmpsite.get_output("about.html")


def test_files_with_no_render_suffix_are_copied_with_no_render_suffix_removed(
    tmpsite, theme
):
    # given
    tmpsite.make_page("data/sample.txt.NO_RENDER", "This is a raw text file.")

    # when
    _render(tmpsite, theme=theme)

    # then
    assert "This is a raw text file." in tmpsite.get_output("data/sample.txt")


def test_html_files_with_no_render_suffix_are_not_rendered(tmpsite, theme):
    # given
    tmpsite.make_page(
        "info.html.NO_RENDER", "<h1>Info Page</h1><p>This is ${ vars.foo }.</p>"
    )

    # when
    _render(tmpsite, vars={"foo": "bar"}, theme=theme)

    # then
    assert "<h1>Info Page</h1><p>This is ${ vars.foo }.</p>" in tmpsite.get_output(
        "info.html"
    )


def test_markdown_files_with_no_render_suffix_are_not_rendered(tmpsite, theme):
    # given
    tmpsite.make_page("readme.md.NO_RENDER", "# Readme\nThis is ${ vars.foo }.")

    # when
    _render(tmpsite, vars={"foo": "bar"}, theme=theme)

    # then
    assert "# Readme\nThis is ${ vars.foo }." in tmpsite.get_output("readme.md")


def test_no_render_suffix_of_none_means_nothing_is_renamed(tmpsite, theme):
    # given
    tmpsite.make_page("data/sample.txt.NO_RENDER", "This is a raw text file.")

    # when: load content with no_render_suffix=None so nothing is renamed
    pages, static_content = tmpsite.load_content(no_render_suffix=None)
    automata.website.render(
        tmpsite.build_directory,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        theme=theme,
    )

    # then
    assert "This is a raw text file." in tmpsite.get_output("data/sample.txt.NO_RENDER")


# materials ============================================================================


def test_materials_are_loaded_and_available_in_rendering_contex(
    tmpsite, default_example_course, theme
):
    # given
    import automata.materials

    universe = automata.materials.discover(
        default_example_course.path,
    )
    universe = automata.materials.build(
        universe, ignore_ready=True, ignore_release_time=True
    )
    universe = automata.materials.export(universe, tmpsite.materials_directory)
    materials_json = automata.materials.serialize(universe)

    (tmpsite.materials_directory / "materials.json").write_text(materials_json)

    tmpsite.make_page(
        "materials.html",
        "<ul>"
        "{% for collection in materials.collections %}"
        "<li>${ collection }</li>"
        "{% endfor %}"
        "</ul>",
    )

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("materials.html")
    assert "<li>homeworks</li>" in output
    assert "<li>default</li>" in output


def test_exception_is_raised_if_materials_directory_missing(tmpsite, theme):
    # given

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
    with raises(automata.website.exceptions.WebsiteError) as exc:
        _render(tmpsite, theme=theme)

    assert "Materials directory not found at" in str(exc.value)


def test_exception_is_raised_if_materials_json_missing(tmpsite, theme):
    # given

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
    with raises(automata.website.exceptions.WebsiteError) as exc:
        _render(tmpsite, theme=theme)

    assert "materials.json not found at" in str(exc.value)


def _exported_example(default_example_course, tmpsite):
    """Discover, build, and export the example course into tmpsite (no json)."""
    import automata.materials

    universe = automata.materials.discover(default_example_course.path)
    universe = automata.materials.build(
        universe, ignore_ready=True, ignore_release_time=True
    )
    return automata.materials.export(universe, tmpsite.materials_directory)


def test_render_uses_given_materials_instead_of_materials_json(
    tmpsite, default_example_course, theme
):
    # given: materials exported, and no materials.json to fall back on
    universe = _exported_example(default_example_course, tmpsite)
    (tmpsite.materials_directory / "materials.json").unlink(missing_ok=True)
    tmpsite.make_page(
        "index.md", "{% for name in materials.collections %}[${ name }]{% endfor %}"
    )

    # when
    _render(tmpsite, theme=theme, materials=universe)

    # then
    for name in universe.collections:
        assert f"[{name}]" in tmpsite.get_output("index.html")


def test_render_does_not_modify_given_materials(tmpsite, default_example_course, theme):
    # given
    import automata.materials

    universe = _exported_example(default_example_course, tmpsite)
    before = automata.materials.serialize(universe)
    tmpsite.make_page("index.md", "Home")

    # when: base_path causes artifact paths to be rewritten for rendering
    _render(tmpsite, theme=theme, materials=universe, base_path="/course/")

    # then
    assert automata.materials.serialize(universe) == before


# relative base paths =================================================================


def _universe_with_one_artifact():
    import automata.materials

    return automata.materials.Universe(
        collections={
            "hw": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "hw01": automata.materials.Publication(
                        metadata={},
                        artifacts={
                            "hw.pdf": automata.materials.ExportedArtifact(
                                path="materials/hw/hw01/hw.pdf"
                            )
                        },
                    )
                },
            )
        }
    )


_LINKS = (
    "[css](${ url_for('static/style.css') }) "
    "[hw](${ materials.collections.hw.publications.hw01.artifacts['hw.pdf'].path })"
)


@pytest.mark.parametrize(
    "page, css, hw",
    [
        ("index.md", "./static/style.css", "./materials/hw/hw01/hw.pdf"),
        ("notes/week1.md", "../static/style.css", "../materials/hw/hw01/hw.pdf"),
        ("a/b/c.md", "../../static/style.css", "../../materials/hw/hw01/hw.pdf"),
    ],
)
def test_a_relative_base_path_is_relative_to_each_page(tmpsite, theme, page, css, hw):
    tmpsite.make_page(page, _LINKS)

    _render(
        tmpsite, theme=theme, materials=_universe_with_one_artifact(), base_path="."
    )

    output = tmpsite.get_output(page.replace(".md", ".html"))
    assert f'href="{css}"' in output
    assert f'href="{hw}"' in output


def test_an_absolute_base_path_is_the_same_on_every_page(tmpsite, theme):
    tmpsite.make_page("notes/week1.md", _LINKS)

    _render(
        tmpsite,
        theme=theme,
        materials=_universe_with_one_artifact(),
        base_path="/course/",
    )

    output = tmpsite.get_output("notes/week1.html")
    assert 'href="/course/static/style.css"' in output
    assert 'href="/course/materials/hw/hw01/hw.pdf"' in output


# error handling =======================================================================


def test_missing_variable_in_markdown_page_raises_error(tmpsite, theme):
    """Test that missing variables in markdown pages raise an error."""
    # given
    tmpsite.make_page("test.md", "# Page\nThe value is ${ missing_var }.")

    # when / then
    with raises(Exception) as exc_info:
        _render(tmpsite, theme=theme)

    assert "missing_var" in str(exc_info.value)


def test_missing_variable_in_html_page_raises_error(tmpsite, theme):
    """Test that missing variables in HTML pages raise an error."""
    # given
    tmpsite.make_page("test.html", "<p>The value is ${ missing_var }.</p>")

    # when / then
    with raises(Exception) as exc_info:
        _render(tmpsite, theme=theme)

    assert "missing_var" in str(exc_info.value)


# dependency injection =================================================================


def test_custom_markdown_engine_can_be_injected(tmpsite, theme):
    """Test that a custom markdown engine can be injected via render_markdown."""
    # given
    tmpsite.make_page("test.md", "# Header\nContent")

    # custom markdown engine that adds a marker
    def custom_markdown_engine(markdown_text):
        return f"[CUSTOM]{markdown_text}[/CUSTOM]"

    # when
    _render(tmpsite, render_markdown=custom_markdown_engine, theme=theme)

    # then
    output = tmpsite.get_output("test.html")
    assert "[CUSTOM]" in output
    assert "[/CUSTOM]" in output


# frontmatter ==========================================================================


def test_frontmatter_in_markdown_page(tmpsite, theme):
    # given
    tmpsite.make_page(
        "info.md",
        "---\nvars:\n  title: Info Page\n  author: Test Author\n---\n\n"
        "# ${ frontmatter.vars.title }\n\nBy ${ frontmatter.vars.author }",
    )

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("info.html")
    assert "<h1>Info Page</h1>" in output
    assert "By Test Author" in output


def test_frontmatter_in_html_page(tmpsite, theme):
    # given
    tmpsite.make_page(
        "info.html",
        "---\nvars:\n  title: Info Page\n  author: Test Author\n---\n\n"
        "<h1>${ frontmatter.vars.title }</h1>\n<p>By ${ frontmatter.vars.author }</p>",
    )

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("info.html")
    assert "<h1>Info Page</h1>" in output
    assert "<p>By Test Author</p>" in output


def test_pages_without_frontmatter_still_work(tmpsite, theme):
    """Test backward compatibility - pages without frontmatter work as before."""
    # given
    tmpsite.make_page("legacy.md", "# Legacy Page\n\nNo frontmatter here.")

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("legacy.html")
    assert "Legacy Page</h1>" in output
    assert "No frontmatter here" in output


def test_invalid_yaml_raises_page_error(tmpsite, theme):
    """Test error handling for invalid YAML in frontmatter."""
    # given
    tmpsite.make_page(
        "bad.md",
        "---\nvars:\n  invalid: [unclosed list\n---\n\n# Content",
    )

    # when / then
    with raises(automata.website.PageError) as exc:
        _render(tmpsite, theme=theme)

    assert "bad.md" in str(exc.value)


def test_frontmatter_yaml_errors_give_the_line_in_the_page(tmpsite, theme):
    # the bad line is line 3 of the page (line 2 of the frontmatter)
    tmpsite.make_page("bad.md", "---\ntitle: a\n  bad: indent\n---\n\n# Content")

    with raises(automata.website.PageError) as exc:
        _render(tmpsite, theme=theme)

    assert "line 3" in str(exc.value)


def _page_error(tmpsite, **kwargs) -> str:
    with raises(automata.website.PageError) as exc:
        _render(tmpsite, **kwargs)
    return str(exc.value)


def test_page_errors_name_the_source_file_and_line(tmpsite, theme):
    tmpsite.make_page("notes/page.md", "# Notes\n\n${ nope }\n")
    source = tmpsite.content_directory / "notes" / "page.md"

    message = _page_error(tmpsite, theme=theme)

    assert message == f"{source}:3: 'nope' is undefined"


def test_page_undefined_key_errors_suggest_a_close_key(tmpsite, theme):
    tmpsite.make_page("index.md", "${ vars.cours }")
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, theme=theme, vars={"course": "DSC 40B"})

    assert message == f'{source}:1: The dict has no key "cours". Did you mean "course"?'


def test_theme_template_undefined_key_errors_suggest_a_close_key(tmpsite, tmp_path):
    tmpsite.make_page("index.md", "ok")
    theme = _theme_with_page_template(tmp_path, "<title>${ vars.cours }</title>")

    message = _page_error(tmpsite, theme=theme, vars={"course": "DSC 40B"})

    assert message.endswith(
        'template page.html, line 1: The dict has no key "cours". '
        'Did you mean "course"?'
    )


def test_page_error_lines_count_the_frontmatter(tmpsite, theme):
    # the frontmatter is lines 1-4, so the bad line is line 7 of the file
    tmpsite.make_page("index.md", "---\nvars:\n  a: 1\n---\nok\n\n${ nope }\n")
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, theme=theme)

    assert message.startswith(f"{source}:7: ")


def test_page_syntax_errors_give_the_line(tmpsite, theme):
    tmpsite.make_page("index.md", "---\ntemplate: page.html\n---\nok\n{% if %}\n")
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, theme=theme)

    assert message.startswith(f"{source}:5: ")


def test_frontmatter_errors_name_the_file_and_keypath(tmpsite, theme):
    tmpsite.make_page("index.md", "---\ntemplate: page.html\nvars: [1, 2]\n---\nok\n")
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, theme=theme)

    assert message == f"{source}:3: vars: Expected a dict, but got a list."


def test_frontmatter_can_use_global_vars(tmpsite, theme):
    tmpsite.make_page(
        "index.md",
        '---\nvars:\n  title: "${ vars.course } Syllabus"\n---\n'
        "# ${ frontmatter.vars.title }\n",
    )

    _render(tmpsite, theme=theme, vars={"course": "DSC 40B"})

    assert "DSC 40B Syllabus" in tmpsite.get_output("index.html")


def test_frontmatter_errors_give_the_keypath_without_this(tmpsite, theme):
    tmpsite.make_page(
        "index.md", '---\ntemplate: page.html\nvars:\n  title: "${ vars.nope }"\n---\n'
    )
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, theme=theme, vars={"course": "DSC 40B"})

    # vars are the global variables: "nope" isn't one of them
    assert message == (
        f'{source}:4: vars.title: The dict has no key "nope". Its keys are "course".'
    )


def test_frontmatter_errors_at_an_include_give_the_line_of_the_include(tmpsite, theme):
    (tmpsite.content_directory / "data.yaml").write_text("a: 1\nb: [1, 2]\n")
    tmpsite.make_page(
        "index.md", "---\nvars: {}\ntemplate:\n  __include__: data.yaml\n---\nok\n"
    )
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, theme=theme)

    assert message.startswith(f"{source}:3: template: Expected a string, ")


def test_frontmatter_yaml_errors_name_the_file(tmpsite, theme):
    tmpsite.make_page("bad.md", "---\ntitle: a\n  bad: indent\n---\n\n# Content")
    source = tmpsite.content_directory / "bad.md"

    message = _page_error(tmpsite, theme=theme)

    assert message.startswith(f"{source}: Invalid YAML, line 3, ")


def test_frontmatter_include_is_relative_to_the_page(tmpsite, theme):
    (tmpsite.content_directory / "notes").mkdir()
    (tmpsite.content_directory / "notes" / "data.yaml").write_text("greeting: hi\n")
    tmpsite.make_page(
        "notes/page.md",
        "---\nvars:\n  __include__: data.yaml\n---\n${ frontmatter.vars.greeting }",
    )

    _render(tmpsite, theme=theme)

    assert "hi" in (tmpsite.build_directory / "notes" / "page.html").read_text()


def _theme_with_page_template(tmp_path, template):
    theme_dir = tmp_path / "custom_theme"
    (theme_dir / "templates").mkdir(parents=True)
    (theme_dir / "templates" / "page.html").write_text(template)
    return _make_theme(theme_dir=theme_dir)


def test_theme_template_errors_name_the_template_and_line(tmpsite, tmp_path):
    tmpsite.make_page("index.md", "ok")
    theme = _theme_with_page_template(tmp_path, "<html>\n${ content }\n${ nope }\n")
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, theme=theme)

    assert message == f"{source}: template page.html, line 3: 'nope' is undefined"


def test_errors_in_an_element_give_the_line_of_the_page_that_calls_it(tmpsite):
    # the element's template fails on its own line 2; the page calls it on line 3
    class BoomElement(automata.website.TemplateElement):
        template = "boom.html"
        schema = None

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(
            {
                "page.html": "<html><body>${ content }</body></html>",
                "boom.html": "<span>\n${ nope }\n</span>",
            }
        )
        inputs.elements.update({"boom": BoomElement})
        return inputs

    hooks = RenderHooks()
    apply_extension(
        Extension(name="test-theme", hooks={"on_render_collect": collect}), hooks
    )
    tmpsite.make_page("index.md", "# Title\n\n${ elements.boom() }\n")
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, hooks=hooks)

    assert message == f"{source}:3: 'nope' is undefined"


def test_errors_in_an_element_s_own_jinja_template_give_the_page_line(tmpsite):
    # an element may render a template string itself, which Jinja also reports
    # as "<template>"; the line is still the page's (3), not the element's (4)
    class InlineElement(automata.website.BasicElement):
        schema = None

        def render(self, config):
            return jinja2.Template(
                "a\nb\nc\n{{ nope }}", undefined=jinja2.StrictUndefined
            ).render()

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates["page.html"] = "<html><body>${ content }</body></html>"
        inputs.elements["inline"] = InlineElement
        return inputs

    hooks = RenderHooks()
    apply_extension(
        Extension(name="test-theme", hooks={"on_render_collect": collect}), hooks
    )
    tmpsite.make_page("index.md", "# Title\n\n${ elements.inline() }\n")
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, hooks=hooks)

    assert message == f"{source}:3: 'nope' is undefined"


def test_errors_in_an_included_template_name_that_template(tmpsite, tmp_path):
    tmpsite.make_page("index.md", "ok")
    theme_dir = tmp_path / "custom_theme"
    (theme_dir / "templates").mkdir(parents=True)
    (theme_dir / "templates" / "page.html").write_text(
        "<html>\n${ content }\n{% include 'footer.html' %}\n</html>\n"
    )
    (theme_dir / "templates" / "footer.html").write_text(
        "<footer>\n<p>\n${ nope }\n</p>\n</footer>\n"
    )
    theme = _make_theme(theme_dir=theme_dir)
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, theme=theme)

    assert message == f"{source}: template footer.html, line 3: 'nope' is undefined"


def test_theme_template_syntax_errors_name_the_template_and_line(tmpsite, tmp_path):
    tmpsite.make_page("index.md", "ok")
    theme = _theme_with_page_template(tmp_path, "<html>\n{% if %}\n</html>\n")
    source = tmpsite.content_directory / "index.md"

    message = _page_error(tmpsite, theme=theme)

    assert message.startswith(f"{source}: template page.html, line 2: ")


def test_calling_an_element_with_too_many_arguments_is_reported(tmpsite, theme):
    tmpsite.make_page("index.md", "${ elements.button({}, {}) }")

    with raises(automata.website.PageError) as exc:
        _render(tmpsite, theme=theme)

    message = str(exc.value)
    assert "elements.button takes at most one argument" in message
    assert "positional arguments" not in message


def test_invalid_frontmatter_key_raises_page_error(tmpsite, theme):
    """Test that invalid frontmatter keys raise an error."""
    # given
    tmpsite.make_page(
        "bad_key.md",
        "---\ninvalid_key: some value\nvars:\n  title: Test\n---\n\n# Content",
    )

    # when / then
    with raises(automata.website.PageError) as exc:
        _render(tmpsite, theme=theme)

    assert "bad_key.md" in str(exc.value)


def test_empty_frontmatter(tmpsite, theme):
    """Test that empty frontmatter block is handled correctly."""
    # given
    tmpsite.make_page(
        "empty.md",
        "---\n---\n\n# Page with empty frontmatter",
    )

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("empty.html")
    assert "Page with empty frontmatter</h1>" in output


def test_frontmatter_with_nested_vars_structures(tmpsite, theme):
    """Test that nested structures in vars work correctly."""
    # given
    tmpsite.make_page(
        "nested.md",
        "---\nvars:\n  metadata:\n    title: Nested Title\n    tags:\n"
        "      - python\n      - tutorial\n---\n\n"
        "# ${ frontmatter.vars.metadata.title }",
    )

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("nested.html")
    assert "Nested Title</h1>" in output


# url_for ============================================================================


def test_url_for_with_default_base_path(tmpsite, theme):
    """Test that url_for works correctly with the default base_path of '/'."""
    # given
    tmpsite.make_page(
        "index.html",
        '<a href="${ url_for("about.html") }">About</a>\n'
        '<a href="${ url_for("docs/guide.html") }">Guide</a>',
    )

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert '<a href="/about.html">About</a>' in output
    assert '<a href="/docs/guide.html">Guide</a>' in output


def test_url_for_with_custom_base_path(tmpsite, theme):
    """Test that url_for correctly prepends a custom base_path."""
    # given
    tmpsite.make_page(
        "index.html",
        '<a href="${ url_for("about.html") }">About</a>\n'
        '<a href="${ url_for("/contact.html") }">Contact</a>',
    )

    # when
    _render(tmpsite, theme=theme, base_path="/course")

    # then
    output = tmpsite.get_output("index.html")
    assert '<a href="/course/about.html">About</a>' in output
    assert '<a href="/course/contact.html">Contact</a>' in output


# themes ===============================================================================


def test_render_uses_default_theme_by_default(tmpsite, theme):
    tmpsite.make_page("index.md", "Home page")

    _render(tmpsite, theme=theme)

    # Expect default theme to add a recognizable marker to the rendered page.
    assert 'data-automata-theme="default"' in tmpsite.get_output("index.html")


def test_render_can_use_custom_theme_via_directory_path(tmpsite, tmp_path):
    # given
    tmpsite.make_page("index.md", "# Custom Theme Test")

    # Create a custom theme directory
    custom_theme_dir = tmp_path / "custom_theme"
    templates_dir = custom_theme_dir / "templates"
    templates_dir.mkdir(parents=True)

    # Create a custom page.html template with a marker
    (templates_dir / "page.html").write_text(
        '<html><body data-custom-theme="yes">${ content }</body></html>'
    )

    theme = _make_theme(theme_dir=custom_theme_dir)

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert 'data-custom-theme="yes"' in output
    assert "Custom Theme Test" in output


def test_render_supports_template_inheritance(tmpsite, tmp_path):
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: layout.html\n---\nHello from layout",
    )

    custom_theme_dir = tmp_path / "custom_theme"
    templates_dir = custom_theme_dir / "templates"
    templates_dir.mkdir(parents=True)

    (templates_dir / "page.html").write_text(
        "<html><body><header>Header</header>"
        "{% block body %}{% endblock %}"
        "<footer>Footer</footer></body></html>"
    )
    (templates_dir / "layout.html").write_text(
        '{% extends "page.html" %}{% block body %}Layout:${ content }{% endblock %}'
    )

    theme = _make_theme(theme_dir=custom_theme_dir)

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert "<header>Header</header>" in output
    assert "<footer>Footer</footer>" in output
    assert "Layout:" in output
    assert "Hello from layout" in output


def test_render_uses_frontmatter_template(tmpsite, tmp_path):
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: alt.html\n---\nHello from alt template",
    )

    custom_theme_dir = tmp_path / "custom_theme"
    templates_dir = custom_theme_dir / "templates"
    templates_dir.mkdir(parents=True)

    (templates_dir / "page.html").write_text(
        "<html><body>BASE:${ content }</body></html>"
    )
    (templates_dir / "alt.html").write_text(
        "<html><body>ALT:${ content }</body></html>"
    )

    theme = _make_theme(theme_dir=custom_theme_dir)

    # when
    _render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert "ALT:" in output
    assert "Hello from alt template" in output
    assert "BASE:" not in output


def test_render_errors_for_missing_frontmatter_template(tmpsite, tmp_path):
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: missing.html\n---\nHello",
    )

    custom_theme_dir = tmp_path / "custom_theme"
    templates_dir = custom_theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html><body>${ content }</body></html>")

    theme = _make_theme(theme_dir=custom_theme_dir)

    # when / then
    with raises(automata.website.PageError, match="missing.html") as exc_info:
        _render(tmpsite, theme=theme)

    assert exc_info.value.path == tmpsite.content_directory / "index.md"
    assert isinstance(
        exc_info.value.__cause__, automata.website.exceptions.WebsiteError
    )


def test_render_requires_base_template_in_theme(tmpsite, tmp_path):
    # given
    tmpsite.make_page("index.md", "# Missing Base")

    custom_theme_dir = tmp_path / "custom_theme"
    templates_dir = custom_theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "index.html").write_text("<html>${ content }</html>")

    theme = _make_theme(theme_dir=custom_theme_dir)

    # when / then
    with raises(automata.website.exceptions.WebsiteError, match="page.html"):
        _render(tmpsite, theme=theme)


def test_render_can_override_theme_template(tmpsite, tmp_path, hooks, theme):
    """Test that theme templates can be overridden."""
    # given
    tmpsite.make_page("index.md", "# Override Test")

    # Create overrides directory with custom page.html
    overrides_dir = tmp_path / "overrides"
    templates_dir = overrides_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text(
        '<html><body data-override="yes">${ content }</body></html>'
    )

    override_ext = extension_from_directory(
        "overrides", overrides_dir, require_templates=False
    )
    apply_extension(override_ext, hooks, priority=1)

    # when
    _render(tmpsite, hooks=hooks, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert 'data-override="yes"' in output
    assert "Override Test" in output


def test_render_overrides_template_can_extend_builtin_template(tmpsite, tmp_path):
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: layout.html\n---\nHello from override",
    )

    overrides_dir = tmp_path / "overrides"
    templates_dir = overrides_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "layout.html").write_text(
        '{% extends "base.html" %}{% block main %}Override:${ content }{% endblock %}'
    )

    theme = _make_theme(
        config={
            "short_title": "DSC 40B",
            "long_title": "Theoretical Foundations of Data Science II",
            "navigation": [],
        }
    )
    override_ext = extension_from_directory(
        "overrides", overrides_dir, require_templates=False
    )

    # when
    _render(tmpsite, theme=theme, extensions=[override_ext])

    # then
    output = tmpsite.get_output("index.html")
    assert 'data-automata-theme="default"' in output
    assert "Override:" in output
    assert "Hello from override" in output


def test_render_can_override_only_static_files(tmpsite, tmp_path):
    """Test that only static files can be overridden without templates."""
    # given
    tmpsite.make_page("index.md", "# Static Override Test")

    # Create overrides directory with ONLY static files (no templates)
    overrides_dir = tmp_path / "overrides"
    static_dir = overrides_dir / "static"
    static_dir.mkdir(parents=True)
    (static_dir / "custom.css").write_text("body { color: red; }")

    theme = _make_theme(
        config={
            "short_title": "DSC 40B",
            "long_title": "Theoretical Foundations of Data Science II",
            "navigation": [],
        }
    )
    override_ext = extension_from_directory(
        "overrides", overrides_dir, require_templates=False
    )

    # when
    _render(tmpsite, theme=theme, extensions=[override_ext])

    # then - verify the custom static file was copied to output
    custom_css = tmpsite.get_output("custom.css")
    assert "body { color: red; }" in custom_css


def test_render_copies_static_files_from_theme(tmpsite, theme):
    """Test that static files from the theme are copied to output."""
    # given
    tmpsite.make_page("index.md", "# Test Page")

    # when
    _render(tmpsite, theme=theme)

    # then - verify default theme's static CSS file was copied
    style_css = tmpsite.get_output("static/style.css")
    assert "tailwindcss" in style_css  # default theme uses Tailwind CSS


def test_render_handles_all_static_file_types(tmpsite, tmp_path):
    """Test that render() handles str, bytes, and Traversable static files."""
    # given
    tmpsite.make_page("index.md", "# Test Page")

    # Create a file to use as Traversable (Path objects have read_bytes())
    traversable_file = tmp_path / "traversable.txt"
    traversable_file.write_bytes(b"traversable content")

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update({"page.html": "<html><body>${ content }</body></html>"})
        inputs.static_files.update(
            {
                "string.txt": "string content",
                "bytes.bin": b"bytes content",
                "traversable.txt": traversable_file,
            }
        )
        return inputs

    hooks = RenderHooks()
    apply_extension(
        Extension(name="test-theme", hooks={"on_render_collect": collect}), hooks
    )

    # when
    _render(tmpsite, hooks=hooks)

    # then - verify all three types were copied correctly
    assert tmpsite.get_output("string.txt") == "string content"
    assert tmpsite.get_output("bytes.bin") == "bytes content"
    assert tmpsite.get_output("traversable.txt") == "traversable content"


# elements =============================================================================


def test_render_supports_theme_elements(tmpsite):
    """Test using a simple class as a theme element."""
    tmpsite.make_page(
        "index.html",
        '${ elements.simple({"label": "Hello"}) }',
    )

    class SimpleElement(automata.website.Element):
        def __call__(self, config):
            return f'<span data-element="simple">{config["label"]}</span>'

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update({"page.html": "<html><body>${ content }</body></html>"})
        inputs.elements.update({"simple": SimpleElement})
        return inputs

    hooks = RenderHooks()
    apply_extension(
        Extension(name="test-theme", hooks={"on_render_collect": collect}), hooks
    )

    _render(tmpsite, hooks=hooks)

    output = tmpsite.get_output("index.html")
    assert '<span data-element="simple">Hello</span>' in output


def test_render_with_template_element(tmpsite):
    tmpsite.make_page(
        "index.html",
        '${ elements.badge({"label": "Welcome", "tone": "warning"}) }',
    )

    class BadgeConfig(smartconfig.Prototype):
        label: str
        tone: str = "info"

    class BadgeElement(automata.website.TemplateElement):
        """Template element implementation using the TemplateElement protocol."""

        schema = BadgeConfig._schema()
        template = "badge.html"

        def template_vars(self, config):
            return {"suffix": f"{self.context.base_path}"}

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(
            {
                "page.html": "<html><body>${ content }</body></html>",
                "badge.html": (
                    '<span class="badge ${ element_config.tone }">'
                    "${ element_config.label }:${ suffix }</span>"
                ),
            }
        )
        inputs.elements.update({"badge": BadgeElement})
        return inputs

    hooks = RenderHooks()
    apply_extension(
        Extension(name="test-theme", hooks={"on_render_collect": collect}), hooks
    )

    _render(tmpsite, hooks=hooks)

    output = tmpsite.get_output("index.html")
    assert '<span class="badge warning">Welcome:/' in output


# configured elements ==================================================================


class _BadgeConfig(smartconfig.Prototype):
    label: str = "default label"
    tone: str = "info"


class _RequiredBadgeConfig(smartconfig.Prototype):
    label: str


def _badge_hooks(schema=_BadgeConfig._schema()):
    """Hooks providing a page.html template and a "badge" TemplateElement."""

    class BadgeElement(automata.website.TemplateElement):
        template = "badge.html"

    BadgeElement.schema = schema

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(
            {
                "page.html": "<html><body>${ content }</body></html>",
                "badge.html": (
                    "<span class=\"badge ${ element_config.tone | default('') }\">"
                    "${ element_config.label }</span>"
                ),
            }
        )
        inputs.elements.update({"badge": BadgeElement})
        return inputs

    hooks = RenderHooks()
    apply_extension(
        Extension(name="test-theme", hooks={"on_render_collect": collect}), hooks
    )
    return hooks


def test_element_called_without_config_uses_configured_config(tmpsite):
    tmpsite.make_page("index.html", "${ elements.badge() }")

    _render(
        tmpsite,
        hooks=_badge_hooks(),
        element_configs={"badge": {"label": "From YAML", "tone": "warning"}},
    )

    output = tmpsite.get_output("index.html")
    assert '<span class="badge warning">From YAML</span>' in output


def test_element_called_without_config_and_none_configured_uses_empty_config(tmpsite):
    tmpsite.make_page("index.html", "${ elements.badge() }")

    _render(tmpsite, hooks=_badge_hooks())

    output = tmpsite.get_output("index.html")
    assert '<span class="badge info">default label</span>' in output


def test_element_called_with_config_ignores_configured_config(tmpsite):
    # the explicit config replaces the configured one entirely; no merging
    tmpsite.make_page("index.html", '${ elements.badge({"label": "From page"}) }')

    _render(
        tmpsite,
        hooks=_badge_hooks(),
        element_configs={"badge": {"label": "From YAML", "tone": "warning"}},
    )

    output = tmpsite.get_output("index.html")
    assert '<span class="badge info">From page</span>' in output


def test_element_called_with_empty_config_ignores_configured_config(tmpsite):
    tmpsite.make_page("index.html", "${ elements.badge({}) }")

    _render(
        tmpsite,
        hooks=_badge_hooks(),
        element_configs={"badge": {"label": "From YAML", "tone": "warning"}},
    )

    output = tmpsite.get_output("index.html")
    assert '<span class="badge info">default label</span>' in output


def test_unconfigured_element_error_mentions_website_elements(
    tmpsite,
):
    tmpsite.make_page("index.html", "${ elements.badge() }")

    with raises(automata.website.exceptions.PageError) as excinfo:
        _render(tmpsite, hooks=_badge_hooks(_RequiredBadgeConfig._schema()))

    message = str(excinfo.value)
    assert "index.html" in message
    assert "website.elements.badge" in message
    assert "label" in message


def test_element_with_invalid_configured_config_error_mentions_website_elements(
    tmpsite,
):
    tmpsite.make_page("index.html", "${ elements.badge() }")

    with raises(automata.website.exceptions.PageError) as excinfo:
        _render(
            tmpsite,
            hooks=_badge_hooks(_RequiredBadgeConfig._schema()),
            element_configs={"badge": {"tone": "warning"}},
        )

    message = str(excinfo.value)
    assert "website.elements.badge" in message
    assert "label" in message


def test_configured_element_errors_give_the_website_elements_keypath(tmpsite):
    tmpsite.make_page("index.html", "${ elements.badge() }")

    with raises(automata.website.exceptions.PageError) as excinfo:
        _render(
            tmpsite,
            hooks=_badge_hooks(),
            element_configs={"badge": {"label": ["a", "list"]}},
        )

    assert str(excinfo.value).endswith(
        "website.elements.badge.label: Expected a string, but got a list."
    )


def test_configured_element_errors_give_the_file_and_line_of_the_config(
    tmpsite, tmp_path
):
    config_file = tmp_path / "automata.yaml"
    _, source_map = parse_yaml_with_source_map(
        "website:\n  elements:\n    badge:\n      label: [a, list]\n",
        source=config_file,
    )
    tmpsite.make_page("index.md", "${ elements.badge() }")
    source = tmpsite.content_directory / "index.md"

    with raises(automata.website.exceptions.PageError) as excinfo:
        _render(
            tmpsite,
            hooks=_badge_hooks(),
            element_configs={"badge": {"label": ["a", "list"]}},
            config_source_map=source_map,
        )

    assert str(excinfo.value) == (
        f"{source}:1: {config_file}:4: website.elements.badge.label: Expected a "
        "string, but got a list."
    )


def test_passed_element_config_errors_name_the_element(tmpsite):
    tmpsite.make_page("index.html", '${ elements.badge({"label": ["a"]}) }')

    with raises(automata.website.exceptions.PageError) as excinfo:
        _render(tmpsite, hooks=_badge_hooks())

    assert str(excinfo.value).endswith(
        "the configuration passed to elements.badge: label: Expected a string, "
        "but got a list."
    )


def test_configuring_unknown_element_raises(tmpsite):
    tmpsite.make_page("index.html", "Hello")

    with raises(automata.website.exceptions.WebsiteError) as excinfo:
        _render(
            tmpsite,
            hooks=_badge_hooks(),
            element_configs={"bagde": {"label": "Typo"}},
        )

    assert "bagde" in str(excinfo.value)


# theme and extensions in templates ====================================================


def _page_theme(name="test-theme", config=None, dependencies=()):
    """A theme extension providing a minimal page.html template."""

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates["page.html"] = "<html><body>${ content }</body></html>"
        return inputs

    return Extension(
        name=name,
        hooks={"on_render_collect": collect},
        config=config or {},
        dependencies=list(dependencies),
    )


def test_render_makes_theme_available_in_templates(tmpsite):
    tmpsite.make_page("index.md", "${ theme.name }: ${ theme.config.title }")

    _render(tmpsite, theme=_page_theme(config={"title": "My Course"}))

    assert "test-theme: My Course" in tmpsite.get_output("index.html")


def test_render_makes_extensions_available_in_templates_by_name(tmpsite):
    dep = Extension(name="dep-ext", hooks={}, config={"b": "from dep"})
    ext = Extension(
        name="my-ext", hooks={}, config={"a": "from ext"}, dependencies=[dep]
    )
    tmpsite.make_page(
        "index.md",
        '${ extensions["my-ext"].config.a } / ${ extensions["dep-ext"].config.b }',
    )

    _render(tmpsite, theme=_page_theme(), extensions=[ext])

    assert "from ext / from dep" in tmpsite.get_output("index.html")


def test_render_includes_theme_and_its_dependencies_in_extensions(tmpsite):
    dep = Extension(name="theme-dep", hooks={})
    tmpsite.make_page("index.md", "${ extensions | sort | join(',') }")

    _render(tmpsite, theme=_page_theme(dependencies=[dep]))

    assert "test-theme,theme-dep" in tmpsite.get_output("index.html")


def test_render_applies_theme_and_extensions_when_hooks_omitted(tmpsite):
    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.pages["extra.html"] = "Extra page"
        return inputs

    ext = Extension(name="pages-ext", hooks={"on_render_collect": collect})

    _render(tmpsite, theme=_page_theme(), extensions=[ext])

    assert "Extra page" in tmpsite.get_output("extra.html")


def test_render_does_not_add_extension_config_to_vars(tmpsite, tmp_path):
    theme_dir = tmp_path / "custom_theme"
    (theme_dir / "templates").mkdir(parents=True)
    (theme_dir / "templates" / "page.html").write_text("${ content }")
    ext = extension_from_directory("custom", theme_dir, config={"title": "My Course"})
    tmpsite.make_page("index.md", "${ vars | length }")

    _render(tmpsite, theme=ext, vars={})

    assert tmpsite.get_output("index.html").strip() == "<p>0</p>"


# theme config validation ==========================================================


def test_extension_from_directory_validates_config_against_schema(tmp_path):
    """Test that extension_from_directory() validates config and applies defaults."""
    # Create a theme directory with a schema
    theme_dir = tmp_path / "custom_theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    # Schema with required and optional keys
    (theme_dir / "schema.json").write_text(
        '{"type": "dict", "required_keys": {"site_name": {"type": "string"}}, '
        '"optional_keys": {"show_footer": {"type": "boolean", "default": true}, '
        '"copyright_year": {"type": "integer", "default": 2024}}}'
    )

    # This should succeed and apply defaults
    ext = extension_from_directory(
        "test-theme", theme_dir, config={"site_name": "My Site"}
    )

    # Verify config was updated with defaults
    assert ext.config["site_name"] == "My Site"
    assert ext.config["show_footer"] is True
    assert ext.config["copyright_year"] == 2024


def test_extension_from_directory_raises_on_invalid_config(tmp_path):
    """Test that extension_from_directory() raises when config doesn't match schema."""
    # Create a theme directory with a schema
    theme_dir = tmp_path / "custom_theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    # Schema requiring site_name
    (theme_dir / "schema.json").write_text(
        '{"type": "dict", "required_keys": {"site_name": {"type": "string"}}}'
    )

    with raises(Error) as excinfo:
        extension_from_directory("test-theme", theme_dir, config={})

    assert "test-theme" in str(excinfo.value)
    assert "site_name" in str(excinfo.value)


def test_extension_from_directory_validates_config_when_config_omitted(tmp_path):
    theme_dir = tmp_path / "custom_theme"
    (theme_dir / "templates").mkdir(parents=True)
    (theme_dir / "schema.json").write_text(
        '{"type": "dict", "required_keys": {"site_name": {"type": "string"}}}'
    )

    with raises(Error) as excinfo:
        extension_from_directory("test-theme", theme_dir)

    assert "site_name" in str(excinfo.value)


def test_extension_from_directory_applies_defaults_when_config_omitted(tmp_path):
    theme_dir = tmp_path / "custom_theme"
    (theme_dir / "templates").mkdir(parents=True)
    (theme_dir / "schema.json").write_text(
        '{"type": "dict", "optional_keys": '
        '{"title": {"type": "string", "default": "Default Title"}}}'
    )

    ext = extension_from_directory("test-theme", theme_dir)

    assert ext.config == {"title": "Default Title"}


def test_extension_from_directory_skips_validation_when_no_schema(tmp_path):
    """Test that extension_from_directory() allows any config without a schema."""
    # Create a custom theme without a schema
    theme_dir = tmp_path / "custom_theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")
    # No schema.json file - theme has no schema

    # Theme has no schema, so any config should be allowed
    ext = extension_from_directory(
        "test-theme",
        theme_dir,
        config={
            "arbitrary_key": "arbitrary_value",
            "another_key": 123,
        },
    )

    # Config should remain unchanged (no defaults applied since no schema)
    assert ext.config["arbitrary_key"] == "arbitrary_value"
    assert ext.config["another_key"] == 123


def test_extension_from_directory_applies_defaults(tmp_path):
    """Test that resolved config with defaults is in extension.config."""
    # Create a theme directory with a schema that has defaults
    theme_dir = tmp_path / "custom_theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    # Schema with multiple defaults
    (theme_dir / "schema.json").write_text(
        '{"type": "dict", "optional_keys": {'
        '"title": {"type": "string", "default": "Default Title"}, '
        '"count": {"type": "integer", "default": 42}, '
        '"enabled": {"type": "boolean", "default": false}}}'
    )

    ext = extension_from_directory("test-theme", theme_dir, config={})

    # All defaults should be applied to extension.config
    assert ext.config["title"] == "Default Title"
    assert ext.config["count"] == 42
    assert ext.config["enabled"] is False


# hooks ===========================================================================


def test_render_executes_script_hook_from_theme(tmpsite, tmp_path):
    """Test that script hooks run and receive hook args as JSON on stdin."""
    # given: a theme with a script hook that saves stdin (the JSON args) to a file
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    hooks_dir = theme_dir / "hooks"
    templates_dir.mkdir(parents=True)
    hooks_dir.mkdir()
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    captured_file = tmp_path / "captured_args.json"
    (hooks_dir / "on_render_post").write_text(f"cat > '{captured_file}'")

    tmpsite.make_page("index.md", "# Home")

    theme = _make_theme(theme_dir=theme_dir)

    # when
    _render(tmpsite, theme=theme)

    # then: the script ran and received the hook args as JSON
    import json

    assert captured_file.exists()
    args = json.loads(captured_file.read_text())
    assert "build_directory" in args


def test_render_continues_without_hooks(tmpsite, tmp_path):
    """Test that render() works normally when theme has no hooks."""
    # given: a theme without a hooks/ directory
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    tmpsite.make_page("index.md", "# Home")

    theme = _make_theme(theme_dir=theme_dir)

    # when / then: should not raise
    _render(tmpsite, theme=theme)
    assert "Home" in tmpsite.get_output("index.html")


def test_render_handles_materials_already_in_build_directory(tmpsite, theme):
    """Test that render() works when materials directory is already in build dir."""
    # given - create materials directly in the build directory
    materials_in_build = tmpsite.build_directory / "materials"
    materials_in_build.mkdir(parents=True, exist_ok=True)

    # Write materials.json
    (materials_in_build / "materials.json").write_text('{"collections": {}}')

    # Create a test file to verify it doesn't get duplicated
    test_file = materials_in_build / "test.txt"
    test_file.write_text("original content")

    tmpsite.make_page("index.md", "# Test Page")

    # when - pass the materials directory that's already in the build directory
    # This should not raise an error and should not try to copy to itself
    pages, static_content = tmpsite.load_content()
    automata.website.render(
        tmpsite.build_directory,
        materials_in_build,
        pages=pages,
        static_content=static_content,
        theme=theme,
    )

    # then - verify the page was generated and materials are still there
    assert "Test Page" in tmpsite.get_output("index.html")
    assert (materials_in_build / "materials.json").exists()
    assert test_file.read_text() == "original content"


# default theme tailwind rebuild ================================================


def _default_theme_with_runner(run):
    """The default theme, built with an injected command runner for Tailwind."""
    from automata.builtin.themes.default import make_extension

    config = {
        "short_title": "Test",
        "long_title": "Test Site",
        "navigation": [],
        "rebuild_tailwind": True,
    }
    return make_extension(config, run=run)


def test_default_theme_rebuilds_tailwind_after_pages_are_rendered(tmpsite):
    # given: a runner that records the command, and what was built at that time
    import subprocess

    calls = []

    def run(cmd, **kwargs):
        index_written = (tmpsite.build_directory / "index.html").exists()
        calls.append((cmd, kwargs["cwd"], index_written))
        return subprocess.CompletedProcess(cmd, 0)

    tmpsite.make_page("index.md", "<div class='bg-fuchsia-500'>custom</div>")

    # when
    _render(tmpsite, theme=_default_theme_with_runner(run))

    # then
    ((cmd, cwd, index_written),) = calls
    assert cmd[:2] == ["npx", "@tailwindcss/cli"]
    assert cwd == str(tmpsite.build_directory.resolve())
    assert index_written


def test_default_theme_renders_without_npx(tmpsite, caplog):
    # given: a runner for a machine without npx
    import logging

    def run(cmd, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "npx")

    tmpsite.make_page("index.md", "# Test Page")

    # when
    with caplog.at_level(logging.WARNING):
        _render(tmpsite, theme=_default_theme_with_runner(run))

    # then
    assert "Test Page" in tmpsite.get_output("index.html")
    assert any("npx not found" in record.getMessage() for record in caplog.records)


# url_for and extra pages from hooks ==================================================


def test_url_for_leaves_absolute_urls_unchanged(tmpsite, theme):
    tmpsite.make_page(
        "index.md",
        "${ url_for('https://example.com/a') } ${ url_for('http://x.org') } "
        "${ url_for('syllabus.html') }",
    )

    _render(tmpsite, theme=theme, base_path="/course/")

    output = tmpsite.get_output("index.html")
    assert "https://example.com/a http://x.org /course/syllabus.html" in output


def test_on_render_extra_pages_can_add_binary_files_and_copy_paths(
    tmpsite, hooks, theme, tmp_path
):
    # given: a hook that adds bytes and a file path as extra content
    source = tmp_path / "handout.pdf"
    source.write_bytes(b"%PDF-1.4 handout")

    @hooks.on_render_extra_pages.register()
    def add_files(args):
        extra = dict(args.extra_content or {})
        extra["logo.png"] = b"\x89PNG"
        extra["handouts/handout.pdf"] = source
        return automata.hooks.RenderExtraPagesHookArgs(
            build_directory=args.build_directory, extra_content=extra
        )

    tmpsite.make_page("index.md", "# Home")

    # when
    _render(tmpsite, hooks=hooks, theme=theme)

    # then
    build = tmpsite.build_directory
    assert (build / "logo.png").read_bytes() == b"\x89PNG"
    assert (build / "handouts" / "handout.pdf").read_bytes() == b"%PDF-1.4 handout"


# errors in element templates ==========================================================


def _greeting_hooks(template, schema=None):
    """Hooks providing a page template and a 'greeting' element using *template*.

    With no *schema*, the element's config reaches the template unresolved, so
    ``${ ... }`` in it is first evaluated by the template's ``resolve()``.
    """

    class Greeting(automata.website.TemplateElement):
        template = "greeting.html"

    Greeting.schema = schema

    def collect(inputs):
        inputs.templates.update(
            {"page.html": "${ content }", "greeting.html": template}
        )
        inputs.elements["greeting"] = Greeting
        return inputs

    h = RenderHooks()
    apply_extension(Extension(name="t", hooks={"on_render_collect": collect}), h)
    return h


def test_element_template_resolving_an_undefined_variable_names_it(tmpsite):
    tmpsite.make_page("index.md", '${ elements.greeting({"text": "Hi ${ nobody }"}) }')

    with raises(automata.website.exceptions.PageError) as excinfo:
        _render(tmpsite, hooks=_greeting_hooks("${ resolve(element_config.text) }"))

    assert "nobody" in str(excinfo.value)
    assert type(excinfo.value.__cause__) is automata.website.exceptions.WebsiteError


def test_element_resolving_a_missing_config_key_names_it(tmpsite):
    tmpsite.make_page("index.md", '${ elements.greeting({"text": "Hi"}) }')

    with raises(automata.website.exceptions.PageError) as excinfo:
        _render(tmpsite, hooks=_greeting_hooks("${ resolve(element_config.missing) }"))

    assert "missing" in str(excinfo.value)
    assert type(excinfo.value.__cause__) is automata.website.exceptions.WebsiteError


# extra_content =======================================================================


def test_extra_content_with_string_renders_through_full_pipeline(tmpsite, theme):
    """String content goes through full pipeline: frontmatter, interpolation, etc."""
    # given
    markdown_content = "# Extra Page\n\nThis is **bold** text."
    pages, static_content = tmpsite.load_content()
    pages["extra.html"] = markdown_content

    # when
    automata.website.render(
        tmpsite.build_directory,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        theme=theme,
    )

    # then
    output = tmpsite.get_output("extra.html")
    assert "<h1>Extra Page</h1>" in output
    assert "<strong>bold</strong>" in output
    # Should be wrapped in template (default theme marker)
    assert 'data-automata-theme="default"' in output


def test_extra_content_with_string_supports_frontmatter(tmpsite, theme):
    """String content with frontmatter should have it parsed."""
    # given
    content_with_frontmatter = """---
vars:
  greeting: Hello World
---
# ${ frontmatter.vars.greeting }
"""
    pages, static_content = tmpsite.load_content()
    pages["greeting.html"] = content_with_frontmatter

    # when
    automata.website.render(
        tmpsite.build_directory,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        theme=theme,
    )

    # then
    output = tmpsite.get_output("greeting.html")
    assert "<h1>Hello World</h1>" in output


def test_extra_content_with_bytes_writes_binary(tmpsite, theme):
    """Bytes content should be written directly as binary."""
    # given
    binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # PNG header bytes
    pages, static_content = tmpsite.load_content()
    static_content["image.png"] = binary_content

    # when
    automata.website.render(
        tmpsite.build_directory,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        theme=theme,
    )

    # then
    output_path = tmpsite.build_directory / "image.png"
    assert output_path.exists()
    assert output_path.read_bytes() == binary_content


def test_extra_content_with_path_copies_file(tmpsite, theme, tmp_path):
    """Path content should copy the source file to the destination."""
    # given
    source_file = tmp_path / "source.txt"
    source_file.write_text("Content from source file")
    pages, static_content = tmpsite.load_content()
    static_content["copied.txt"] = source_file.read_text()

    # when
    automata.website.render(
        tmpsite.build_directory,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        theme=theme,
    )

    # then
    assert tmpsite.get_output("copied.txt") == "Content from source file"


def test_extra_content_creates_subdirectories(tmpsite, theme):
    """Extra content with nested paths should create parent directories."""
    # given
    content = "# Nested Page"
    pages, static_content = tmpsite.load_content()
    pages["deep/nested/page.html"] = content

    # when
    automata.website.render(
        tmpsite.build_directory,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        theme=theme,
    )

    # then
    output = tmpsite.get_output("deep/nested/page.html")
    assert "<h1>Nested Page</h1>" in output


def test_extra_content_with_multiple_items(tmpsite, theme, tmp_path):
    """Multiple extra content items of different types should all be processed."""
    # given
    source_file = tmp_path / "data.json"
    source_file.write_text('{"key": "value"}')
    pages, static_content = tmpsite.load_content()
    pages["page.html"] = "# A Page"
    static_content["binary.bin"] = b"\x00\x01\x02"
    static_content["data.json"] = source_file.read_text()

    # when
    automata.website.render(
        tmpsite.build_directory,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        theme=theme,
    )

    # then
    assert "<h1>A Page</h1>" in tmpsite.get_output("page.html")
    assert (tmpsite.build_directory / "binary.bin").read_bytes() == b"\x00\x01\x02"
    assert tmpsite.get_output("data.json") == '{"key": "value"}'


# hooks parameter =====================================================================


def test_render_accepts_hooks_parameter(tmpsite, hooks, theme):
    """Test that render() accepts a hooks parameter."""
    tmpsite.make_page("index.md", "# Test")

    # should not raise
    _render(tmpsite, hooks=hooks, theme=theme)

    assert "Test" in tmpsite.get_output("index.html")


def test_user_render_extra_pages_hook_is_called(tmpsite, hooks, theme):
    """Test that user-registered on_render_extra_pages hooks are called."""
    call_log = []

    @hooks.on_render_extra_pages.register()
    def my_pre_hook(args: RenderExtraPagesHookArgs) -> RenderExtraPagesHookArgs:
        call_log.append("render_extra_pages called")
        return args

    tmpsite.make_page("index.md", "# Test")
    _render(tmpsite, hooks=hooks, theme=theme)

    assert "render_extra_pages called" in call_log


def test_user_post_render_hook_is_called(tmpsite, hooks, theme):
    """Test that user-registered on_render_post hooks are called."""
    call_log = []

    @hooks.on_render_post.register()
    def my_post_hook(args: RenderPostHookArgs) -> None:
        call_log.append("post_render called")

    tmpsite.make_page("index.md", "# Test")
    _render(tmpsite, hooks=hooks, theme=theme)

    assert "post_render called" in call_log


def test_user_render_extra_pages_hook_can_add_extra_content(tmpsite, hooks, theme):
    """Test that on_render_extra_pages hooks can add extra content."""

    @hooks.on_render_extra_pages.register()
    def add_extra_page(args: RenderExtraPagesHookArgs) -> RenderExtraPagesHookArgs:
        extra = args.extra_content or {}
        extra["from-hook.html"] = "# Added by hook"
        return RenderExtraPagesHookArgs(
            build_directory=args.build_directory, extra_content=extra
        )

    tmpsite.make_page("index.md", "# Test")
    _render(tmpsite, hooks=hooks, theme=theme)

    assert "<h1>Added by hook</h1>" in tmpsite.get_output("from-hook.html")


def test_render_extra_pages_pipeline_chains_transformations(tmpsite, hooks, theme):
    """Test that on_render_extra_pages hooks chain their transformations."""

    @hooks.on_render_extra_pages.register()
    def add_page_a(args: RenderExtraPagesHookArgs) -> RenderExtraPagesHookArgs:
        extra = dict(args.extra_content or {})
        extra["a.html"] = "# Page A"
        return RenderExtraPagesHookArgs(
            build_directory=args.build_directory, extra_content=extra
        )

    @hooks.on_render_extra_pages.register()
    def add_page_b(args: RenderExtraPagesHookArgs) -> RenderExtraPagesHookArgs:
        extra = dict(args.extra_content or {})
        extra["b.html"] = "# Page B"
        return RenderExtraPagesHookArgs(
            build_directory=args.build_directory, extra_content=extra
        )

    tmpsite.make_page("index.md", "# Test")
    _render(tmpsite, hooks=hooks, theme=theme)

    # Both pages should be generated (pipeline chains results)
    assert "<h1>Page A</h1>" in tmpsite.get_output("a.html")
    assert "<h1>Page B</h1>" in tmpsite.get_output("b.html")


def test_hooks_receive_build_directory(tmpsite, hooks, theme):
    """Test that hooks receive the build directory."""
    received = []

    @hooks.on_render_post.register()
    def capture(args: RenderPostHookArgs) -> None:
        received.append(args.build_directory)

    tmpsite.make_page("index.md", "# Test")
    _render(tmpsite, hooks=hooks, theme=theme)

    assert len(received) == 1
    assert received[0] == tmpsite.build_directory
