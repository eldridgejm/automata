import shutil

import smartconfig
from pytest import fixture, raises

import automata.materials
import automata.website


@fixture
def config(tmpsite):
    return automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use="default",
            config={
                "short_title": "DSC 40B",
                "long_title": "Theoretical Foundations of Data Science II",
                "navigation": [],
                "rebuild_tailwind": False,  # Disable for faster tests
            },
        ),
    )


# basic page rendering =================================================================


def test_converts_pages_from_markdown_to_html(tmpsite, config):
    # given
    tmpsite.make_page("one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    assert "This is a header</h1>" in tmpsite.get_output("one.html")


def test_converts_pages_from_markdown_to_html_recursively(tmpsite, config):
    # given
    tmpsite.make_page("index.md", "Home page")
    tmpsite.make_page("subdir/one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    assert "This is a header</h1>" in tmpsite.get_output("subdir/one.html")

    assert "Home page" in tmpsite.get_output("index.html")


def tests_renders_html_pages(tmpsite, config):
    # given
    tmpsite.make_page(
        "about.html", "<h1>About this site</h1><p>This site is great.</p>"
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    assert "<h1>About this site</h1>" in tmpsite.get_output("about.html")


def test_copies_files_from_content_to_output(tmpsite, config):
    # given
    tmpsite.make_page("data/tabular/one.txt", "This is a text file in a subdir.")

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    assert "This is a text file in a subdir." in tmpsite.get_output(
        "data/tabular/one.txt"
    )


def test_vars_can_be_used_in_markdown_pages(tmpsite, config):
    # given
    tmpsite.make_page("index.md", "The value of 'foo' is ${ vars.foo }.")

    # when
    automata.website.generate(config, tmpsite.materials_directory, vars={"foo": "bar"})

    # then
    assert "The value of 'foo' is bar." in tmpsite.get_output("index.html")


def test_vars_can_be_used_in_html_pages(tmpsite, config):
    # given
    tmpsite.make_page("about.html", "<p>The value of 'foo' is ${ vars.foo }.</p>")

    # when
    automata.website.generate(config, tmpsite.materials_directory, vars={"foo": "bar"})

    # then
    assert "<p>The value of 'foo' is bar.</p>" in tmpsite.get_output("about.html")


def test_files_with_no_render_suffix_are_copied_with_no_render_suffix_removed(
    tmpsite, config
):
    # given
    tmpsite.make_page("data/sample.txt.NO_RENDER", "This is a raw text file.")

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    assert "This is a raw text file." in tmpsite.get_output("data/sample.txt")


def test_html_files_with_no_render_suffix_are_not_rendered(tmpsite, config):
    # given
    tmpsite.make_page(
        "info.html.NO_RENDER", "<h1>Info Page</h1><p>This is ${ vars.foo }.</p>"
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory, vars={"foo": "bar"})

    # then
    assert "<h1>Info Page</h1><p>This is ${ vars.foo }.</p>" in tmpsite.get_output(
        "info.html"
    )


def test_markdown_files_with_no_render_suffix_are_not_rendered(tmpsite, config):
    # given
    tmpsite.make_page("readme.md.NO_RENDER", "# Readme\nThis is ${ vars.foo }.")

    # when
    automata.website.generate(config, tmpsite.materials_directory, vars={"foo": "bar"})

    # then
    assert "# Readme\nThis is ${ vars.foo }." in tmpsite.get_output("readme.md")


def test_no_render_suffix_of_none_means_nothing_is_renamed(tmpsite, config):
    # given
    tmpsite.make_page("data/sample.txt.NO_RENDER", "This is a raw text file.")

    config.no_render_suffix = None

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    assert "This is a raw text file." in tmpsite.get_output("data/sample.txt.NO_RENDER")


# materials ============================================================================


def test_materials_are_loaded_and_available_in_rendering_contex(
    tmpsite, default_example_course, config
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
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("materials.html")
    assert "<li>homeworks</li>" in output
    assert "<li>default</li>" in output


def test_exception_is_raised_if_materials_directory_missing(tmpsite, config):
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
        automata.website.generate(config, tmpsite.materials_directory)

    assert "Materials directory not found at" in str(exc.value)


def test_exception_is_raised_if_materials_json_missing(tmpsite, config):
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
        automata.website.generate(config, tmpsite.materials_directory)

    assert "materials.json not found at" in str(exc.value)


# error handling =======================================================================


def test_missing_variable_in_markdown_page_raises_error(tmpsite, config):
    """Test that missing variables in markdown pages raise an error."""
    # given
    tmpsite.make_page("test.md", "# Page\nThe value is ${ missing_var }.")

    # when / then
    with raises(Exception) as exc_info:
        automata.website.generate(config, tmpsite.materials_directory)

    assert "missing_var" in str(exc_info.value)


def test_missing_variable_in_html_page_raises_error(tmpsite, config):
    """Test that missing variables in HTML pages raise an error."""
    # given
    tmpsite.make_page("test.html", "<p>The value is ${ missing_var }.</p>")

    # when / then
    with raises(Exception) as exc_info:
        automata.website.generate(config, tmpsite.materials_directory)

    assert "missing_var" in str(exc_info.value)


# dependency injection =================================================================


def test_custom_markdown_engine_can_be_injected(tmpsite, config):
    """Test that a custom markdown engine can be injected via render_markdown."""
    # given
    tmpsite.make_page("test.md", "# Header\nContent")

    # custom markdown engine that adds a marker
    def custom_markdown_engine(markdown_text):
        return f"[CUSTOM]{markdown_text}[/CUSTOM]"

    # when
    automata.website.generate(
        config, tmpsite.materials_directory, render_markdown=custom_markdown_engine
    )

    # then
    output = tmpsite.get_output("test.html")
    assert "[CUSTOM]" in output
    assert "[/CUSTOM]" in output


# frontmatter ==========================================================================


def test_frontmatter_in_markdown_page(tmpsite, config):
    # given
    tmpsite.make_page(
        "info.md",
        "---\nvars:\n  title: Info Page\n  author: Test Author\n---\n\n"
        "# ${ frontmatter.vars.title }\n\nBy ${ frontmatter.vars.author }",
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("info.html")
    assert "<h1>Info Page</h1>" in output
    assert "By Test Author" in output


def test_frontmatter_in_html_page(tmpsite, config):
    # given
    tmpsite.make_page(
        "info.html",
        "---\nvars:\n  title: Info Page\n  author: Test Author\n---\n\n"
        "<h1>${ frontmatter.vars.title }</h1>\n<p>By ${ frontmatter.vars.author }</p>",
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("info.html")
    assert "<h1>Info Page</h1>" in output
    assert "<p>By Test Author</p>" in output


def test_pages_without_frontmatter_still_work(tmpsite, config):
    """Test backward compatibility - pages without frontmatter work as before."""
    # given
    tmpsite.make_page("legacy.md", "# Legacy Page\n\nNo frontmatter here.")

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("legacy.html")
    assert "Legacy Page</h1>" in output
    assert "No frontmatter here" in output


def test_invalid_yaml_raises_page_error(tmpsite, config):
    """Test error handling for invalid YAML in frontmatter."""
    # given
    tmpsite.make_page(
        "bad.md",
        "---\nvars:\n  invalid: [unclosed list\n---\n\n# Content",
    )

    # when / then
    with raises(automata.website.PageError) as exc:
        automata.website.generate(config, tmpsite.materials_directory)

    assert "bad.md" in str(exc.value)


def test_invalid_frontmatter_key_raises_page_error(tmpsite, config):
    """Test that invalid frontmatter keys raise an error."""
    # given
    tmpsite.make_page(
        "bad_key.md",
        "---\ninvalid_key: some value\nvars:\n  title: Test\n---\n\n# Content",
    )

    # when / then
    with raises(automata.website.PageError) as exc:
        automata.website.generate(config, tmpsite.materials_directory)

    assert "bad_key.md" in str(exc.value)


def test_empty_frontmatter(tmpsite, config):
    """Test that empty frontmatter block is handled correctly."""
    # given
    tmpsite.make_page(
        "empty.md",
        "---\n---\n\n# Page with empty frontmatter",
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("empty.html")
    assert "Page with empty frontmatter</h1>" in output


def test_frontmatter_with_nested_vars_structures(tmpsite, config):
    """Test that nested structures in vars work correctly."""
    # given
    tmpsite.make_page(
        "nested.md",
        "---\nvars:\n  metadata:\n    title: Nested Title\n    tags:\n"
        "      - python\n      - tutorial\n---\n\n"
        "# ${ frontmatter.vars.metadata.title }",
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("nested.html")
    assert "Nested Title</h1>" in output


# url_for ============================================================================


def test_url_for_with_default_base_path(tmpsite, config):
    """Test that url_for works correctly with the default base_path of '/'."""
    # given
    tmpsite.make_page(
        "index.html",
        '<a href="${ url_for("about.html") }">About</a>\n'
        '<a href="${ url_for("docs/guide.html") }">Guide</a>',
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("index.html")
    assert '<a href="/about.html">About</a>' in output
    assert '<a href="/docs/guide.html">Guide</a>' in output


def test_url_for_with_custom_base_path(tmpsite, config):
    """Test that url_for correctly prepends a custom base_path."""
    # given
    tmpsite.make_page(
        "index.html",
        '<a href="${ url_for("about.html") }">About</a>\n'
        '<a href="${ url_for("/contact.html") }">Contact</a>',
    )

    config.base_path = "/course"

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("index.html")
    assert '<a href="/course/about.html">About</a>' in output
    assert '<a href="/course/contact.html">Contact</a>' in output


# themes ===============================================================================


def test_generate_uses_default_theme_by_default(tmpsite, config):
    tmpsite.make_page("index.md", "Home page")

    automata.website.generate(config, tmpsite.materials_directory)

    # Expect default theme to add a recognizable marker to the rendered page.
    assert 'data-automata-theme="default"' in tmpsite.get_output("index.html")


def test_generate_can_use_custom_theme_via_directory_path(tmpsite, tmp_path):
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

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(use=str(custom_theme_dir)),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("index.html")
    assert 'data-custom-theme="yes"' in output
    assert "Custom Theme Test" in output


def test_generate_supports_template_inheritance(tmpsite, tmp_path):
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

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(use=str(custom_theme_dir)),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("index.html")
    assert "<header>Header</header>" in output
    assert "<footer>Footer</footer>" in output
    assert "Layout:" in output
    assert "Hello from layout" in output


def test_generate_uses_frontmatter_template(tmpsite, tmp_path):
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

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(use=str(custom_theme_dir)),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("index.html")
    assert "ALT:" in output
    assert "Hello from alt template" in output
    assert "BASE:" not in output


def test_generate_errors_for_missing_frontmatter_template(tmpsite, tmp_path):
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: missing.html\n---\nHello",
    )

    custom_theme_dir = tmp_path / "custom_theme"
    templates_dir = custom_theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html><body>${ content }</body></html>")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(use=str(custom_theme_dir)),
    )

    # when / then
    with raises(automata.website.PageError, match="missing.html") as exc_info:
        automata.website.generate(config, tmpsite.materials_directory)

    assert exc_info.value.path == tmpsite.content_directory / "index.md"


def test_generate_requires_base_template_in_theme(tmpsite, tmp_path):
    # given
    tmpsite.make_page("index.md", "# Missing Base")

    custom_theme_dir = tmp_path / "custom_theme"
    templates_dir = custom_theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "index.html").write_text("<html>${ content }</html>")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(use=str(custom_theme_dir)),
    )

    # when / then
    with raises(ValueError, match="page.html"):
        automata.website.generate(config, tmpsite.materials_directory)


def test_generate_can_override_theme_template(tmpsite, tmp_path, config):
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

    config.theme.overrides = str(overrides_dir)

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("index.html")
    assert 'data-override="yes"' in output
    assert "Override Test" in output


def test_generate_overrides_template_can_extend_builtin_template(tmpsite, tmp_path):
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

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use="default",
            overrides=str(overrides_dir),
            config={
                "short_title": "DSC 40B",
                "long_title": "Theoretical Foundations of Data Science II",
                "navigation": [],
            },
        ),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("index.html")
    assert 'data-automata-theme="default"' in output
    assert "Override:" in output
    assert "Hello from override" in output


def test_generate_can_override_only_static_files(tmpsite, tmp_path):
    """Test that only static files can be overridden without templates."""
    # given
    tmpsite.make_page("index.md", "# Static Override Test")

    # Create overrides directory with ONLY static files (no templates)
    overrides_dir = tmp_path / "overrides"
    static_dir = overrides_dir / "static"
    static_dir.mkdir(parents=True)
    (static_dir / "custom.css").write_text("body { color: red; }")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use="default",
            overrides=str(overrides_dir),
            config={
                "short_title": "DSC 40B",
                "long_title": "Theoretical Foundations of Data Science II",
                "navigation": [],
            },
        ),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then - verify the custom static file was copied to output
    custom_css = tmpsite.get_output("custom.css")
    assert "body { color: red; }" in custom_css


def test_generate_copies_static_files_from_theme(tmpsite, config):
    """Test that static files from the theme are copied to output."""
    # given
    tmpsite.make_page("index.md", "# Test Page")

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then - verify default theme's static CSS file was copied
    style_css = tmpsite.get_output("static/style.css")
    assert "tailwindcss" in style_css  # default theme uses Tailwind CSS


def test_generate_handles_all_static_file_types(tmpsite, tmp_path, config):
    """Test that generate() handles str, bytes, and Traversable static files."""
    # given
    tmpsite.make_page("index.md", "# Test Page")

    # Create a file to use as Traversable (Path objects have read_bytes())
    traversable_file = tmp_path / "traversable.txt"
    traversable_file.write_bytes(b"traversable content")

    # Create a theme with all three types of static files
    theme = automata.website.Theme(
        templates={"page.html": "<html><body>${ content }</body></html>"},
        static_files={
            "string.txt": "string content",
            "bytes.bin": b"bytes content",
            "traversable.txt": traversable_file,
        },
    )

    # when
    automata.website.generate(
        config, tmpsite.materials_directory, extra_themes={"default": theme}
    )

    # then - verify all three types were copied correctly
    assert tmpsite.get_output("string.txt") == "string content"
    assert tmpsite.get_output("bytes.bin") == "bytes content"
    assert tmpsite.get_output("traversable.txt") == "traversable content"


# elements =============================================================================


def test_generate_supports_theme_elements(tmpsite):
    """Test using a simple class as a theme element."""
    tmpsite.make_page(
        "index.html",
        '${ elements.simple({"label": "Hello"}) }',
    )

    class SimpleElement(automata.website.Element):
        def __call__(self, config):
            return f'<span data-element="simple">{config["label"]}</span>'

    theme = automata.website.Theme(
        templates={"page.html": "<html><body>${ content }</body></html>"},
        elements={"simple": SimpleElement},
    )

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(use="extra"),
    )

    automata.website.generate(
        config, tmpsite.materials_directory, extra_themes={"extra": theme}
    )

    output = tmpsite.get_output("index.html")
    assert '<span data-element="simple">Hello</span>' in output


def test_generate_with_template_element(tmpsite):
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
            return {"suffix": f"{self.context.website_config.build_directory}"}

    theme = automata.website.Theme(
        templates={
            "page.html": "<html><body>${ content }</body></html>",
            "badge.html": (
                '<span class="badge ${ element_config.tone }">'
                "${ element_config.label }:${ suffix }</span>"
            ),
        },
        elements={"badge": BadgeElement},
    )

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(use="extra"),
    )

    automata.website.generate(
        config, tmpsite.materials_directory, extra_themes={"extra": theme}
    )

    output = tmpsite.get_output("index.html")
    assert '<span class="badge warning">Welcome:' in output
    assert str(tmpsite.build_directory) in output


# theme config validation ==========================================================


def test_generate_validates_theme_config_against_schema(tmp_path, tmpsite):
    """Test that generate() validates theme config and applies defaults."""
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

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir), config={"site_name": "My Site"}
        ),
    )

    # This should succeed and apply defaults
    automata.website.generate(config, tmpsite.materials_directory)

    # Verify config was updated with defaults
    assert config.theme.config["site_name"] == "My Site"
    assert config.theme.config["show_footer"] is True
    assert config.theme.config["copyright_year"] == 2024


def test_generate_raises_on_invalid_theme_config(tmp_path, tmpsite):
    """Test that generate() raises Error when config doesn't match schema."""
    # Create a theme directory with a schema
    theme_dir = tmp_path / "custom_theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    # Schema requiring site_name
    (theme_dir / "schema.json").write_text(
        '{"type": "dict", "required_keys": {"site_name": {"type": "string"}}}'
    )

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir),
            config={},  # Missing required site_name
        ),
    )

    # Should raise Error with descriptive message
    with raises(
        automata.website.exceptions.WebsiteError, match="Invalid theme configuration"
    ):
        automata.website.generate(config, tmpsite.materials_directory)


def test_generate_skips_validation_when_schema_is_none(tmp_path, tmpsite):
    """Test that generate() allows any config when theme has no schema."""
    tmpsite.make_page("index.md", "# Home")

    # Create a custom theme without a schema
    theme_dir = tmp_path / "custom_theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")
    # No schema.json file - theme has no schema

    # Theme has no schema, so any config should be allowed
    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir),
            config={
                "arbitrary_key": "arbitrary_value",
                "another_key": 123,
            },
        ),
    )

    # This should succeed without validation
    automata.website.generate(config, tmpsite.materials_directory)

    # Config should remain unchanged (no defaults applied since no schema)
    assert config.theme.config["arbitrary_key"] == "arbitrary_value"
    assert config.theme.config["another_key"] == 123


def test_generate_updates_config_with_resolved_theme_config(tmp_path, tmpsite):
    """Test that resolved config with defaults is in config.theme.config."""
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

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir),
            config={},  # No values provided, should all use defaults
        ),
    )

    automata.website.generate(config, tmpsite.materials_directory)

    # All defaults should be applied to config.theme.config
    assert config.theme.config["title"] == "Default Title"
    assert config.theme.config["count"] == 42
    assert config.theme.config["enabled"] is False


# hooks ===========================================================================


def test_generate_executes_pre_generate_hook(tmpsite, tmp_path):
    """Test that generate() executes pre_generate hook if defined."""
    # given: a theme with a pre_generate hook that creates a marker file
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    marker_file = tmp_path / "pre_generate_marker.txt"
    (theme_dir / "hooks.py").write_text(
        f"def pre_generate(config):\n"
        f"    with open('{marker_file}', 'w') as f:\n"
        f"        f.write('pre_generate executed')\n"
    )

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir),
            config={"short_title": "Test", "long_title": "Test Site", "navigation": []},
        ),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    assert marker_file.exists()
    assert marker_file.read_text() == "pre_generate executed"


def test_pre_generate_hook_can_return_extra_content(tmpsite, tmp_path):
    """Test that pre_generate hook can return extra content to be rendered."""
    # given: a theme with a pre_generate hook that returns extra content
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    (theme_dir / "hooks.py").write_text(
        "def pre_generate(config):\n"
        "    return {'hook-page.html': '# Generated by hook'}\n"
    )

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(use=str(theme_dir)),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("hook-page.html")
    assert "<h1>Generated by hook</h1>" in output


def test_pre_generate_extra_content_is_overridden_by_explicit_extra_content(
    tmpsite, tmp_path
):
    """Test that explicit extra_content takes precedence over hook content."""
    # given: a theme with a pre_generate hook that returns extra content
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    (theme_dir / "hooks.py").write_text(
        "def pre_generate(config):\n    return {'page.html': '# From hook'}\n"
    )

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(use=str(theme_dir)),
    )

    # when: explicit extra_content should override hook content
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        extra_content={"page.html": "# From explicit"},
    )

    # then: explicit content wins
    output = tmpsite.get_output("page.html")
    assert "<h1>From explicit</h1>" in output
    assert "From hook" not in output


def test_generate_executes_post_generate_hook(tmpsite, tmp_path):
    """Test that generate() executes post_generate hook if defined."""
    # given: a theme with a post_generate hook that creates a marker file
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    marker_file = tmp_path / "post_generate_marker.txt"
    (theme_dir / "hooks.py").write_text(
        f"def post_generate(config):\n"
        f"    with open('{marker_file}', 'w') as f:\n"
        f"        f.write('post_generate executed')\n"
    )

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir),
            config={"short_title": "Test", "long_title": "Test Site", "navigation": []},
        ),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    assert marker_file.exists()
    assert marker_file.read_text() == "post_generate executed"


def test_generate_executes_both_hooks_in_order(tmpsite, tmp_path):
    """Test that generate() executes pre_generate before post_generate."""
    # given: a theme with both hooks that append to a file
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    log_file = tmp_path / "hooks_log.txt"
    (theme_dir / "hooks.py").write_text(
        f"def pre_generate(config):\n"
        f"    with open('{log_file}', 'a') as f:\n"
        f"        f.write('pre_generate\\n')\n"
        f"\n"
        f"def post_generate(config):\n"
        f"    with open('{log_file}', 'a') as f:\n"
        f"        f.write('post_generate\\n')\n"
    )

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir),
            config={"short_title": "Test", "long_title": "Test Site", "navigation": []},
        ),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    assert log_file.exists()
    log_content = log_file.read_text()
    assert log_content == "pre_generate\npost_generate\n"


def test_generate_continues_without_hooks(tmpsite, tmp_path):
    """Test that generate() works normally when theme has no hooks."""
    # given: a theme without hooks.py
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir),
            config={"short_title": "Test", "long_title": "Test Site", "navigation": []},
        ),
    )

    # when / then: should not raise
    automata.website.generate(config, tmpsite.materials_directory)
    assert "Home" in tmpsite.get_output("index.html")


def test_generate_raises_on_pre_generate_hook_error(tmpsite, tmp_path):
    """Test that generate() raises WebsiteError when pre_generate hook fails."""
    # given: a theme with a pre_generate hook that raises an exception
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    (theme_dir / "hooks.py").write_text(
        "def pre_generate(config):\n    raise RuntimeError('Hook failed!')\n"
    )

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir),
            config={"short_title": "Test", "long_title": "Test Site", "navigation": []},
        ),
    )

    # when / then
    with raises(automata.website.exceptions.WebsiteError, match="pre_generate hook"):
        automata.website.generate(config, tmpsite.materials_directory)


def test_generate_raises_on_post_generate_hook_error(tmpsite, tmp_path):
    """Test that generate() raises WebsiteError when post_generate hook fails."""
    # given: a theme with a post_generate hook that raises an exception
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "page.html").write_text("<html>${ content }</html>")

    (theme_dir / "hooks.py").write_text(
        "def post_generate(config):\n    raise RuntimeError('Hook failed!')\n"
    )

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use=str(theme_dir),
            config={"short_title": "Test", "long_title": "Test Site", "navigation": []},
        ),
    )

    # when / then
    with raises(automata.website.exceptions.WebsiteError, match="post_generate hook"):
        automata.website.generate(config, tmpsite.materials_directory)


def test_generate_handles_materials_already_in_build_directory(tmpsite, config):
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
    automata.website.generate(config, materials_in_build)

    # then - verify the page was generated and materials are still there
    assert "Test Page" in tmpsite.get_output("index.html")
    assert (materials_in_build / "materials.json").exists()
    assert test_file.read_text() == "original content"


# default theme tailwind rebuild ================================================


def test_default_theme_tailwind_rebuild_with_npx_available(tmpsite, monkeypatch):
    """Test that default theme rebuilds Tailwind CSS when npx is available."""
    # Mock subprocess to simulate successful Tailwind rebuild
    mock_run_calls = []

    def mock_run(*args, **kwargs):
        mock_run_calls.append((args, kwargs))
        # Return success for npx --version
        if args[0][0] == "npx" and args[0][1] == "--version":
            return fixture.Mock(returncode=0)
        # Return success for Tailwind CLI
        return fixture.Mock(returncode=0, stderr="")

    import subprocess
    from unittest import mock as fixture

    monkeypatch.setattr(subprocess, "run", mock_run)

    tmpsite.make_page(
        "index.md", "# Test\n\nThis uses <div class='bg-fuchsia-500'>custom</div>"
    )

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use="default",
            config={
                "short_title": "Test",
                "long_title": "Test Site",
                "rebuild_tailwind": True,  # Disable for faster tests
            },
        ),
    )

    # when
    automata.website.generate(config, tmpsite.materials_directory)

    # then - Tailwind CLI should have been called
    tailwind_calls = [c for c in mock_run_calls if "@tailwindcss/cli" in str(c)]
    assert len(tailwind_calls) > 0, "Tailwind CLI should have been called"


def test_default_theme_fallback_when_npx_not_available(tmpsite, monkeypatch, caplog):
    """Test that default theme falls back gracefully when npx is not available."""
    import subprocess

    def mock_run(*args, **kwargs):
        # Simulate npx not being available
        raise FileNotFoundError("npx not found")

    monkeypatch.setattr(subprocess, "run", mock_run)

    tmpsite.make_page("index.md", "# Test Page")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use="default",
            config={
                "short_title": "Test",
                "long_title": "Test Site",
                "rebuild_tailwind": True,
            },
        ),
    )

    # when
    import logging

    with caplog.at_level(logging.WARNING):
        automata.website.generate(config, tmpsite.materials_directory)

    # then - should have warned about npx not being available
    assert any("npx not found" in record.message for record in caplog.records)
    # Build should still succeed
    assert "Test Page" in tmpsite.get_output("index.html")


# extra_content =======================================================================


def test_extra_content_with_string_renders_through_full_pipeline(tmpsite, config):
    """String content goes through full pipeline: frontmatter, interpolation, etc."""
    # given
    markdown_content = "# Extra Page\n\nThis is **bold** text."

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        extra_content={"extra.html": markdown_content},
    )

    # then
    output = tmpsite.get_output("extra.html")
    assert "<h1>Extra Page</h1>" in output
    assert "<strong>bold</strong>" in output
    # Should be wrapped in template (default theme marker)
    assert 'data-automata-theme="default"' in output


def test_extra_content_with_string_supports_frontmatter(tmpsite, config):
    """String content with frontmatter should have it parsed."""
    # given
    content_with_frontmatter = """---
vars:
  greeting: Hello World
---
# ${ frontmatter.vars.greeting }
"""

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        extra_content={"greeting.html": content_with_frontmatter},
    )

    # then
    output = tmpsite.get_output("greeting.html")
    assert "<h1>Hello World</h1>" in output


def test_extra_content_with_string_supports_variable_interpolation(tmpsite, config):
    """String content should have access to render context variables."""
    # given
    content = "Site title: ${ website_config.theme.config.short_title }"

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        extra_content={"info.html": content},
    )

    # then
    output = tmpsite.get_output("info.html")
    assert "Site title: DSC 40B" in output


def test_extra_content_with_bytes_writes_binary(tmpsite, config):
    """Bytes content should be written directly as binary."""
    # given
    binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # PNG header bytes

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        extra_content={"image.png": binary_content},
    )

    # then
    output_path = tmpsite.build_directory / "image.png"
    assert output_path.exists()
    assert output_path.read_bytes() == binary_content


def test_extra_content_with_path_copies_file(tmpsite, config, tmp_path):
    """Path content should copy the source file to the destination."""
    # given
    source_file = tmp_path / "source.txt"
    source_file.write_text("Content from source file")

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        extra_content={"copied.txt": source_file},
    )

    # then
    assert tmpsite.get_output("copied.txt") == "Content from source file"


def test_extra_content_creates_subdirectories(tmpsite, config):
    """Extra content with nested paths should create parent directories."""
    # given
    content = "# Nested Page"

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        extra_content={"deep/nested/page.html": content},
    )

    # then
    output = tmpsite.get_output("deep/nested/page.html")
    assert "<h1>Nested Page</h1>" in output


def test_extra_content_with_multiple_items(tmpsite, config, tmp_path):
    """Multiple extra content items of different types should all be processed."""
    # given
    source_file = tmp_path / "data.json"
    source_file.write_text('{"key": "value"}')

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        extra_content={
            "page.html": "# A Page",
            "binary.bin": b"\x00\x01\x02",
            "data.json": source_file,
        },
    )

    # then
    assert "<h1>A Page</h1>" in tmpsite.get_output("page.html")
    assert (tmpsite.build_directory / "binary.bin").read_bytes() == b"\x00\x01\x02"
    assert tmpsite.get_output("data.json") == '{"key": "value"}'
