import shutil

import smartconfig
from pytest import raises

import automata.materials
import automata.website

# Minimal templates for testing - simple template that just wraps content
MINIMAL_TEMPLATES = {"page.html": "<html><body>${ content }</body></html>"}


# basic page rendering =================================================================


def test_converts_pages_from_markdown_to_html(tmpsite):
    # given
    tmpsite.make_page("one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    assert "This is a header</h1>" in tmpsite.get_output("one.html")


def test_converts_pages_from_markdown_to_html_recursively(tmpsite):
    # given
    tmpsite.make_page("index.md", "Home page")
    tmpsite.make_page("subdir/one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    assert "This is a header</h1>" in tmpsite.get_output("subdir/one.html")

    assert "Home page" in tmpsite.get_output("index.html")


def tests_renders_html_pages(tmpsite):
    # given
    tmpsite.make_page(
        "about.html", "<h1>About this site</h1><p>This site is great.</p>"
    )

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    assert "<h1>About this site</h1>" in tmpsite.get_output("about.html")


def test_vars_can_be_used_in_markdown_pages(tmpsite):
    # given
    tmpsite.make_page("index.md", "The value of 'foo' is ${ vars.foo }.")

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
        vars={"foo": "bar"},
    )

    # then
    assert "The value of 'foo' is bar." in tmpsite.get_output("index.html")


def test_vars_can_be_used_in_html_pages(tmpsite):
    # given
    tmpsite.make_page("about.html", "<p>The value of 'foo' is ${ vars.foo }.</p>")

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
        vars={"foo": "bar"},
    )

    # then
    assert "<p>The value of 'foo' is bar.</p>" in tmpsite.get_output("about.html")


# materials ============================================================================


def test_materials_are_loaded_and_available_in_rendering_contex(
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

    tmpsite.make_page(
        "materials.html",
        "<ul>"
        "{% for collection in materials.collections %}"
        "<li>${ collection }</li>"
        "{% endfor %}"
        "</ul>",
    )

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("materials.html")
    assert "<li>homeworks</li>" in output
    assert "<li>default</li>" in output


def test_exception_is_raised_if_materials_directory_missing(tmpsite):
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
        automata.website.generate(
            tmpsite.materials_directory,
            MINIMAL_TEMPLATES,
            build_directory=tmpsite.build_directory,
            pages=tmpsite.pages,
        )

    assert "Materials directory not found at" in str(exc.value)


def test_exception_is_raised_if_materials_json_missing(tmpsite):
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
        automata.website.generate(
            tmpsite.materials_directory,
            MINIMAL_TEMPLATES,
            build_directory=tmpsite.build_directory,
            pages=tmpsite.pages,
        )

    assert "materials.json not found at" in str(exc.value)


# error handling =======================================================================


def test_missing_variable_in_markdown_page_raises_error(tmpsite):
    """Test that missing variables in markdown pages raise an error."""
    # given
    tmpsite.make_page("test.md", "# Page\nThe value is ${ missing_var }.")

    # when / then
    with raises(Exception) as exc_info:
        automata.website.generate(
            tmpsite.materials_directory,
            MINIMAL_TEMPLATES,
            build_directory=tmpsite.build_directory,
            pages=tmpsite.pages,
        )

    assert "missing_var" in str(exc_info.value)


def test_missing_variable_in_html_page_raises_error(tmpsite):
    """Test that missing variables in HTML pages raise an error."""
    # given
    tmpsite.make_page("test.html", "<p>The value is ${ missing_var }.</p>")

    # when / then
    with raises(Exception) as exc_info:
        automata.website.generate(
            tmpsite.materials_directory,
            MINIMAL_TEMPLATES,
            build_directory=tmpsite.build_directory,
            pages=tmpsite.pages,
        )

    assert "missing_var" in str(exc_info.value)


# dependency injection =================================================================


def test_custom_markdown_engine_can_be_injected(tmpsite):
    """Test that a custom markdown engine can be injected via render_markdown."""
    # given
    tmpsite.make_page("test.md", "# Header\nContent")

    # custom markdown engine that adds a marker
    def custom_markdown_engine(markdown_text):
        return f"[CUSTOM]{markdown_text}[/CUSTOM]"

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
        render_markdown=custom_markdown_engine,
    )

    # then
    output = tmpsite.get_output("test.html")
    assert "[CUSTOM]" in output
    assert "[/CUSTOM]" in output


# frontmatter ==========================================================================


def test_frontmatter_in_markdown_page(tmpsite):
    # given
    tmpsite.make_page(
        "info.md",
        "---\nvars:\n  title: Info Page\n  author: Test Author\n---\n\n"
        "# ${ frontmatter.vars.title }\n\nBy ${ frontmatter.vars.author }",
    )

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("info.html")
    assert "<h1>Info Page</h1>" in output
    assert "By Test Author" in output


def test_frontmatter_in_html_page(tmpsite):
    # given
    tmpsite.make_page(
        "info.html",
        "---\nvars:\n  title: Info Page\n  author: Test Author\n---\n\n"
        "<h1>${ frontmatter.vars.title }</h1>\n<p>By ${ frontmatter.vars.author }</p>",
    )

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("info.html")
    assert "<h1>Info Page</h1>" in output
    assert "<p>By Test Author</p>" in output


def test_pages_without_frontmatter_still_work(tmpsite):
    """Test backward compatibility - pages without frontmatter work as before."""
    # given
    tmpsite.make_page("legacy.md", "# Legacy Page\n\nNo frontmatter here.")

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("legacy.html")
    assert "Legacy Page</h1>" in output
    assert "No frontmatter here" in output


def test_invalid_yaml_raises_error(tmpsite):
    """Test error handling for invalid YAML in frontmatter."""
    # given
    tmpsite.make_page(
        "bad.md",
        "---\nvars:\n  invalid: [unclosed list\n---\n\n# Content",
    )

    # when / then
    with raises(Exception):
        automata.website.generate(
            tmpsite.materials_directory,
            MINIMAL_TEMPLATES,
            build_directory=tmpsite.build_directory,
            pages=tmpsite.pages,
        )


def test_invalid_frontmatter_key_raises_error(tmpsite):
    """Test that invalid frontmatter keys raise an error."""
    # given
    tmpsite.make_page(
        "bad_key.md",
        "---\ninvalid_key: some value\nvars:\n  title: Test\n---\n\n# Content",
    )

    # when / then
    with raises(Exception):
        automata.website.generate(
            tmpsite.materials_directory,
            MINIMAL_TEMPLATES,
            build_directory=tmpsite.build_directory,
            pages=tmpsite.pages,
        )


def test_empty_frontmatter(tmpsite):
    """Test that empty frontmatter block is handled correctly."""
    # given
    tmpsite.make_page(
        "empty.md",
        "---\n---\n\n# Page with empty frontmatter",
    )

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("empty.html")
    assert "Page with empty frontmatter</h1>" in output


def test_frontmatter_with_nested_vars_structures(tmpsite):
    """Test that nested structures in vars work correctly."""
    # given
    tmpsite.make_page(
        "nested.md",
        "---\nvars:\n  metadata:\n    title: Nested Title\n    tags:\n"
        "      - python\n      - tutorial\n---\n\n"
        "# ${ frontmatter.vars.metadata.title }",
    )

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("nested.html")
    assert "Nested Title</h1>" in output


# url_for ============================================================================


def test_url_for_with_default_base_path(tmpsite):
    """Test that url_for works correctly with the default base_path of '/'."""
    # given
    tmpsite.make_page(
        "index.html",
        '<a href="${ url_for("about.html") }">About</a>\n'
        '<a href="${ url_for("docs/guide.html") }">Guide</a>',
    )

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("index.html")
    assert '<a href="/about.html">About</a>' in output
    assert '<a href="/docs/guide.html">Guide</a>' in output


def test_url_for_with_custom_base_path(tmpsite):
    """Test that url_for correctly prepends a custom base_path."""
    # given
    tmpsite.make_page(
        "index.html",
        '<a href="${ url_for("about.html") }">About</a>\n'
        '<a href="${ url_for("/contact.html") }">Contact</a>',
    )

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        base_path="/course",
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("index.html")
    assert '<a href="/course/about.html">About</a>' in output
    assert '<a href="/course/contact.html">Contact</a>' in output


# templates ============================================================================


def test_generate_supports_template_inheritance(tmpsite):
    """Test that templates can use Jinja2 inheritance."""
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: layout.html\n---\nHello from layout",
    )

    templates = {
        "page.html": (
            "<html><body><header>Header</header>"
            "{% block body %}{% endblock %}"
            "<footer>Footer</footer></body></html>"
        ),
        "layout.html": (
            '{% extends "page.html" %}{% block body %}Layout:${ content }{% endblock %}'
        ),
    }

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        templates,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("index.html")
    assert "<header>Header</header>" in output
    assert "<footer>Footer</footer>" in output
    assert "Layout:" in output
    assert "Hello from layout" in output


def test_generate_uses_frontmatter_template(tmpsite):
    """Test that frontmatter can specify an alternate template."""
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: alt.html\n---\nHello from alt template",
    )

    templates = {
        "page.html": "<html><body>BASE:${ content }</body></html>",
        "alt.html": "<html><body>ALT:${ content }</body></html>",
    }

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        templates,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then
    output = tmpsite.get_output("index.html")
    assert "ALT:" in output
    assert "Hello from alt template" in output
    assert "BASE:" not in output


def test_generate_errors_for_missing_frontmatter_template(tmpsite):
    """Test that generate raises an error for missing frontmatter template."""
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: missing.html\n---\nHello",
    )

    templates = {"page.html": "<html><body>${ content }</body></html>"}

    # when / then
    with raises(Exception, match="missing.html"):
        automata.website.generate(
            tmpsite.materials_directory,
            templates,
            build_directory=tmpsite.build_directory,
            pages=tmpsite.pages,
        )


def test_generate_requires_page_html_template(tmpsite):
    """Test that generate requires a page.html template."""
    # given
    tmpsite.make_page("index.md", "# Missing Base")

    # Only provide a different template, not page.html
    templates = {"index.html": "<html>${ content }</html>"}

    # when / then
    with raises(ValueError, match="page.html"):
        automata.website.generate(
            tmpsite.materials_directory,
            templates,
            build_directory=tmpsite.build_directory,
            pages=tmpsite.pages,
        )


def test_generate_handles_all_asset_types(tmpsite, tmp_path):
    """Test that generate() handles str, bytes, and Traversable assets."""
    # given
    tmpsite.make_page("index.md", "# Test Page")

    # Create a file to use as Traversable (Path objects have read_bytes())
    traversable_file = tmp_path / "traversable.txt"
    traversable_file.write_bytes(b"traversable content")

    assets = {
        "string.txt": "string content",
        "bytes.bin": b"bytes content",
        "traversable.txt": traversable_file,
    }

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
        assets=assets,
    )

    # then - verify all three types were copied correctly
    assert tmpsite.get_output("string.txt") == "string content"
    assert tmpsite.get_output("bytes.bin") == "bytes content"
    assert tmpsite.get_output("traversable.txt") == "traversable content"


def test_generate_copies_static_files(tmpsite):
    """Test that generate() copies static_files to the build directory."""
    # given
    tmpsite.make_page("index.md", "# Test Page")

    static_files = {
        "css/style.css": "body { color: red; }",
        "js/app.js": b"console.log('hello');",
    }

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
        static_files=static_files,
    )

    # then
    assert "body { color: red; }" in tmpsite.get_output("css/style.css")
    assert "console.log('hello');" in tmpsite.get_output("js/app.js")


# elements =============================================================================


def test_generate_supports_elements(tmpsite):
    """Test using a simple class as an element."""
    tmpsite.make_page(
        "index.html",
        '${ elements.simple({"label": "Hello"}) }',
    )

    class SimpleElement(automata.website.Element):
        def __call__(self, element_config):
            return f'<span data-element="simple">{element_config["label"]}</span>'

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
        elements={"simple": SimpleElement},
    )

    output = tmpsite.get_output("index.html")
    assert '<span data-element="simple">Hello</span>' in output


def test_generate_with_template_element(tmpsite):
    """Test using a TemplateElement that renders via a template."""
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

    templates = {
        "page.html": "<html><body>${ content }</body></html>",
        "badge.html": (
            '<span class="badge ${ element_config.tone }">'
            "${ element_config.label }:${ suffix }</span>"
        ),
    }

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        templates,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
        elements={"badge": BadgeElement},
    )

    output = tmpsite.get_output("index.html")
    assert '<span class="badge warning">Welcome:' in output


# miscellaneous ======================================================================


def test_generate_handles_materials_already_in_build_directory(tmpsite):
    """Test that generate() works when materials directory is already in build dir."""
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
    automata.website.generate(
        materials_in_build,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages=tmpsite.pages,
    )

    # then - verify the page was generated and materials are still there
    assert "Test Page" in tmpsite.get_output("index.html")
    assert (materials_in_build / "materials.json").exists()
    assert test_file.read_text() == "original content"


# pages parameter =====================================================================


def test_pages_renders_through_full_pipeline(tmpsite):
    """Pages go through full pipeline: frontmatter, markdown, etc."""
    # given
    markdown_content = "# Extra Page\n\nThis is **bold** text."

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages={"extra.md": markdown_content},
    )

    # then
    output = tmpsite.get_output("extra.html")
    assert "<h1>Extra Page</h1>" in output
    assert "<strong>bold</strong>" in output


def test_pages_supports_frontmatter(tmpsite):
    """Pages with frontmatter should have it parsed."""
    # given
    content_with_frontmatter = """---
vars:
  greeting: Hello World
---
# ${ frontmatter.vars.greeting }
"""

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages={"greeting.md": content_with_frontmatter},
    )

    # then
    output = tmpsite.get_output("greeting.html")
    assert "<h1>Hello World</h1>" in output


def test_pages_supports_variable_interpolation(tmpsite):
    """Pages should have access to render context variables."""
    # given
    page_content = "Base path: ${ base_path }"

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        base_path="/my-course",
        pages={"info.html": page_content},
    )

    # then
    output = tmpsite.get_output("info.html")
    assert "Base path: /my-course" in output


def test_pages_creates_subdirectories(tmpsite):
    """Pages with nested paths should create parent directories."""
    # given
    page_content = "# Nested Page"

    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages={"deep/nested/page.md": page_content},
    )

    # then
    output = tmpsite.get_output("deep/nested/page.html")
    assert "<h1>Nested Page</h1>" in output


def test_pages_with_multiple_items(tmpsite):
    """Multiple pages should all be rendered."""
    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages={
            "page1.md": "# Page One",
            "page2.md": "# Page Two",
        },
    )

    # then
    assert "<h1>Page One</h1>" in tmpsite.get_output("page1.html")
    assert "<h1>Page Two</h1>" in tmpsite.get_output("page2.html")


def test_pages_changes_extension_to_html(tmpsite):
    """Pages paths without .html extension get changed to .html."""
    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages={
            "readme.md": "# Readme",
            "about.txt": "About page",  # Even non-md gets .html
        },
    )

    # then
    assert "<h1>Readme</h1>" in tmpsite.get_output("readme.html")
    assert "About page" in tmpsite.get_output("about.html")


def test_pages_html_extension_unchanged(tmpsite):
    """Pages paths with .html extension remain unchanged."""
    # when
    automata.website.generate(
        tmpsite.materials_directory,
        MINIMAL_TEMPLATES,
        build_directory=tmpsite.build_directory,
        pages={"index.html": "<h1>Index</h1>"},
    )

    # then
    assert "<h1>Index</h1>" in tmpsite.get_output("index.html")
