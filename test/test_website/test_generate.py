from dataclasses import replace

import smartconfig
from pytest import fixture, raises

import automata.materials
import automata.website
from automata.hooks import GenerateHooks, GeneratePostHookArgs, GeneratePreHookArgs
from automata.resources import WebsiteResources

MINIMAL_TEMPLATE = "<html><body>${ content }</body></html>"


def make_resources(tmpsite, **overrides) -> WebsiteResources:
    """Build a WebsiteResources with a minimal toy theme and tmpsite materials."""
    return WebsiteResources(
        templates=overrides.get("templates", {"page.html": MINIMAL_TEMPLATE}),
        pages=overrides.get("pages", {}),
        static_files=overrides.get("static_files", {}),
        elements=overrides.get("elements", {}),
        materials=overrides.get("materials", tmpsite.resources.materials),
        hooks=overrides.get("hooks", GenerateHooks()),
    )


@fixture
def config(tmpsite):
    return automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )


# basic page rendering =================================================================


def test_converts_pages_from_markdown_to_html(tmpsite, config):
    # given
    tmpsite.make_page("one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(config, make_resources(tmpsite))

    # then
    assert "This is a header</h1>" in tmpsite.get_output("one.html")


def test_converts_pages_from_markdown_to_html_recursively(tmpsite, config):
    # given
    tmpsite.make_page("index.md", "Home page")
    tmpsite.make_page("subdir/one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(config, make_resources(tmpsite))

    # then
    assert "This is a header</h1>" in tmpsite.get_output("subdir/one.html")

    assert "Home page" in tmpsite.get_output("index.html")


def tests_renders_html_pages(tmpsite, config):
    # given
    tmpsite.make_page(
        "about.html", "<h1>About this site</h1><p>This site is great.</p>"
    )

    # when
    automata.website.generate(config, make_resources(tmpsite))

    # then
    assert "<h1>About this site</h1>" in tmpsite.get_output("about.html")


def test_copies_files_from_content_to_output(tmpsite, config):
    # given
    tmpsite.make_page("data/tabular/one.txt", "This is a text file in a subdir.")

    # when
    automata.website.generate(config, make_resources(tmpsite))

    # then
    assert "This is a text file in a subdir." in tmpsite.get_output(
        "data/tabular/one.txt"
    )


def test_vars_can_be_used_in_markdown_pages(tmpsite, config):
    # given
    tmpsite.make_page("index.md", "The value of 'foo' is ${ vars.foo }.")

    # when
    automata.website.generate(config, make_resources(tmpsite), vars={"foo": "bar"})

    # then
    assert "The value of 'foo' is bar." in tmpsite.get_output("index.html")


def test_vars_can_be_used_in_html_pages(tmpsite, config):
    # given
    tmpsite.make_page("about.html", "<p>The value of 'foo' is ${ vars.foo }.</p>")

    # when
    automata.website.generate(config, make_resources(tmpsite), vars={"foo": "bar"})

    # then
    assert "<p>The value of 'foo' is bar.</p>" in tmpsite.get_output("about.html")


def test_files_with_no_render_suffix_are_copied_with_no_render_suffix_removed(
    tmpsite, config
):
    # given
    tmpsite.make_page("data/sample.txt.NO_RENDER", "This is a raw text file.")

    # when
    automata.website.generate(config, make_resources(tmpsite))

    # then
    assert "This is a raw text file." in tmpsite.get_output("data/sample.txt")


def test_html_files_with_no_render_suffix_are_not_rendered(tmpsite, config):
    # given
    tmpsite.make_page(
        "info.html.NO_RENDER", "<h1>Info Page</h1><p>This is ${ vars.foo }.</p>"
    )

    # when
    automata.website.generate(config, make_resources(tmpsite), vars={"foo": "bar"})

    # then
    assert "<h1>Info Page</h1><p>This is ${ vars.foo }.</p>" in tmpsite.get_output(
        "info.html"
    )


def test_markdown_files_with_no_render_suffix_are_not_rendered(tmpsite, config):
    # given
    tmpsite.make_page("readme.md.NO_RENDER", "# Readme\nThis is ${ vars.foo }.")

    # when
    automata.website.generate(config, make_resources(tmpsite), vars={"foo": "bar"})

    # then
    assert "# Readme\nThis is ${ vars.foo }." in tmpsite.get_output("readme.md")


def test_no_render_suffix_of_none_means_nothing_is_renamed(tmpsite, config):
    # given
    tmpsite.make_page("data/sample.txt.NO_RENDER", "This is a raw text file.")

    config.no_render_suffix = None

    # when
    automata.website.generate(config, make_resources(tmpsite))

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
    automata.website.generate(config, make_resources(tmpsite))

    # then
    output = tmpsite.get_output("materials.html")
    assert "<li>homeworks</li>" in output
    assert "<li>default</li>" in output


# error handling =======================================================================


def test_missing_variable_in_markdown_page_raises_error(tmpsite, config):
    """Test that missing variables in markdown pages raise an error."""
    # given
    tmpsite.make_page("test.md", "# Page\nThe value is ${ missing_var }.")

    # when / then
    with raises(Exception) as exc_info:
        automata.website.generate(config, make_resources(tmpsite))

    assert "missing_var" in str(exc_info.value)


def test_missing_variable_in_html_page_raises_error(tmpsite, config):
    """Test that missing variables in HTML pages raise an error."""
    # given
    tmpsite.make_page("test.html", "<p>The value is ${ missing_var }.</p>")

    # when / then
    with raises(Exception) as exc_info:
        automata.website.generate(config, make_resources(tmpsite))

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
        config, make_resources(tmpsite), render_markdown=custom_markdown_engine
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
    automata.website.generate(config, make_resources(tmpsite))

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
    automata.website.generate(config, make_resources(tmpsite))

    # then
    output = tmpsite.get_output("info.html")
    assert "<h1>Info Page</h1>" in output
    assert "<p>By Test Author</p>" in output


def test_pages_without_frontmatter_still_work(tmpsite, config):
    """Test backward compatibility - pages without frontmatter work as before."""
    # given
    tmpsite.make_page("legacy.md", "# Legacy Page\n\nNo frontmatter here.")

    # when
    automata.website.generate(config, make_resources(tmpsite))

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
        automata.website.generate(config, make_resources(tmpsite))

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
        automata.website.generate(config, make_resources(tmpsite))

    assert "bad_key.md" in str(exc.value)


def test_empty_frontmatter(tmpsite, config):
    """Test that empty frontmatter block is handled correctly."""
    # given
    tmpsite.make_page(
        "empty.md",
        "---\n---\n\n# Page with empty frontmatter",
    )

    # when
    automata.website.generate(config, make_resources(tmpsite))

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
    automata.website.generate(config, make_resources(tmpsite))

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
    automata.website.generate(config, make_resources(tmpsite))

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
    automata.website.generate(config, make_resources(tmpsite))

    # then
    output = tmpsite.get_output("index.html")
    assert '<a href="/course/about.html">About</a>' in output
    assert '<a href="/course/contact.html">Contact</a>' in output


# templates ============================================================================


def test_generate_uses_custom_template(tmpsite):
    """Test that generate() uses templates from resources."""
    # given
    tmpsite.make_page("index.md", "# Custom Theme Test")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(
        tmpsite,
        templates={
            "page.html": (
                '<html><body data-custom-theme="yes">${ content }</body></html>'
            )
        },
    )

    # when
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("index.html")
    assert 'data-custom-theme="yes"' in output
    assert "Custom Theme Test" in output


def test_generate_supports_template_inheritance(tmpsite):
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: layout.html\n---\nHello from layout",
    )

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(
        tmpsite,
        templates={
            "page.html": (
                "<html><body><header>Header</header>"
                "{% block body %}{% endblock %}"
                "<footer>Footer</footer></body></html>"
            ),
            "layout.html": (
                '{% extends "page.html" %}'
                "{% block body %}Layout:${ content }{% endblock %}"
            ),
        },
    )

    # when
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("index.html")
    assert "<header>Header</header>" in output
    assert "<footer>Footer</footer>" in output
    assert "Layout:" in output
    assert "Hello from layout" in output


def test_generate_uses_frontmatter_template(tmpsite):
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: alt.html\n---\nHello from alt template",
    )

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(
        tmpsite,
        templates={
            "page.html": "<html><body>BASE:${ content }</body></html>",
            "alt.html": "<html><body>ALT:${ content }</body></html>",
        },
    )

    # when
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("index.html")
    assert "ALT:" in output
    assert "Hello from alt template" in output
    assert "BASE:" not in output


def test_generate_errors_for_missing_frontmatter_template(tmpsite):
    # given
    tmpsite.make_page(
        "index.md",
        "---\ntemplate: missing.html\n---\nHello",
    )

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite)

    # when / then
    with raises(automata.website.PageError, match="missing.html") as exc_info:
        automata.website.generate(config, resources)

    assert exc_info.value.path == tmpsite.content_directory / "index.md"


def test_generate_requires_page_template_in_resources(tmpsite):
    """Test that generate() raises when resources lack a page.html template."""
    # given
    tmpsite.make_page("index.md", "# Missing Base")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(
        tmpsite,
        templates={"index.html": "<html>${ content }</html>"},
    )

    # when / then
    with raises(ValueError, match="page.html"):
        automata.website.generate(config, resources)


# static files =========================================================================


def test_generate_copies_static_files_from_resources(tmpsite, config):
    """Test that static files from resources are copied to output."""
    # given
    tmpsite.make_page("index.md", "# Test Page")

    resources = make_resources(
        tmpsite,
        static_files={"static/style.css": "body { color: red; }"},
    )

    # when
    automata.website.generate(config, resources)

    # then
    style_css = tmpsite.get_output("static/style.css")
    assert "body { color: red; }" in style_css


def test_generate_handles_all_static_file_types(tmpsite, tmp_path, config):
    """Test that generate() handles str, bytes, and Traversable static files."""
    # given
    tmpsite.make_page("index.md", "# Test Page")

    # Create a file to use as Traversable (Path objects have read_bytes())
    traversable_file = tmp_path / "traversable.txt"
    traversable_file.write_bytes(b"traversable content")

    resources = make_resources(
        tmpsite,
        static_files={
            "string.txt": "string content",
            "bytes.bin": b"bytes content",
            "traversable.txt": traversable_file,
        },
    )

    # when
    automata.website.generate(config, resources)

    # then - verify all three types were copied correctly
    assert tmpsite.get_output("string.txt") == "string content"
    assert tmpsite.get_output("bytes.bin") == "bytes content"
    assert tmpsite.get_output("traversable.txt") == "traversable content"


# elements =============================================================================


def test_generate_supports_elements(tmpsite):
    """Test using a simple class as an element."""
    tmpsite.make_page(
        "index.html",
        '${ elements.simple({"label": "Hello"}) }',
    )

    class SimpleElement(automata.website.Element):
        def __call__(self, config):
            return f'<span data-element="simple">{config["label"]}</span>'

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite, elements={"simple": SimpleElement})

    automata.website.generate(config, resources)

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

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(
        tmpsite,
        templates={
            "page.html": MINIMAL_TEMPLATE,
            "badge.html": (
                '<span class="badge ${ element_config.tone }">'
                "${ element_config.label }:${ suffix }</span>"
            ),
        },
        elements={"badge": BadgeElement},
    )

    automata.website.generate(config, resources)

    output = tmpsite.get_output("index.html")
    assert '<span class="badge warning">Welcome:' in output
    assert str(tmpsite.build_directory) in output


# hooks ================================================================================


def test_generate_executes_pre_generate_hook(tmpsite, tmp_path):
    """Test that generate() executes pre_generate hook."""
    marker_file = tmp_path / "pre_generate_marker.txt"

    hooks = GenerateHooks()

    @hooks.on_generate_pre.register()
    def my_pre_hook(args: GeneratePreHookArgs) -> GeneratePreHookArgs:
        marker_file.write_text("pre_generate executed")
        return args

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite, hooks=hooks)

    # when
    automata.website.generate(config, resources)

    # then
    assert marker_file.exists()
    assert marker_file.read_text() == "pre_generate executed"


def test_pre_generate_hook_can_add_pages(tmpsite):
    """Test that pre_generate hook can add pages via resources."""
    hooks = GenerateHooks()

    @hooks.on_generate_pre.register()
    def add_hook_page(args: GeneratePreHookArgs) -> GeneratePreHookArgs:
        args.resources.pages["hook-page.html"] = "# Generated by hook"
        return args

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite, hooks=hooks)

    # when
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("hook-page.html")
    assert "<h1>Generated by hook</h1>" in output


def test_pre_generate_hook_can_modify_vars(tmpsite):
    """Test that pre_generate hook can modify vars."""
    hooks = GenerateHooks()

    @hooks.on_generate_pre.register()
    def add_var(args: GeneratePreHookArgs) -> GeneratePreHookArgs:
        args.vars = {**args.vars, "injected": "from hook"}
        return args

    tmpsite.make_page("index.md", "# ${ vars.injected }")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite, hooks=hooks)

    # when
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("index.html")
    assert "<h1>from hook</h1>" in output


def test_generate_executes_post_generate_hook(tmpsite, tmp_path):
    """Test that generate() executes post_generate hook."""
    marker_file = tmp_path / "post_generate_marker.txt"

    hooks = GenerateHooks()

    @hooks.on_generate_post.register()
    def my_post_hook(args: GeneratePostHookArgs) -> None:
        marker_file.write_text("post_generate executed")

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite, hooks=hooks)

    # when
    automata.website.generate(config, resources)

    # then
    assert marker_file.exists()
    assert marker_file.read_text() == "post_generate executed"


def test_generate_executes_both_hooks_in_order(tmpsite, tmp_path):
    """Test that generate() executes pre_generate before post_generate."""
    log_file = tmp_path / "hooks_log.txt"

    hooks = GenerateHooks()

    @hooks.on_generate_pre.register()
    def my_pre_hook(args: GeneratePreHookArgs) -> GeneratePreHookArgs:
        with open(log_file, "a") as f:
            f.write("pre_generate\n")
        return args

    @hooks.on_generate_post.register()
    def my_post_hook(args: GeneratePostHookArgs) -> None:
        with open(log_file, "a") as f:
            f.write("post_generate\n")

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite, hooks=hooks)

    # when
    automata.website.generate(config, resources)

    # then
    assert log_file.exists()
    log_content = log_file.read_text()
    assert log_content == "pre_generate\npost_generate\n"


def test_generate_continues_without_hooks(tmpsite):
    """Test that generate() works normally when no hooks are registered."""
    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite)

    # when / then: should not raise
    automata.website.generate(config, resources)
    assert "Home" in tmpsite.get_output("index.html")


def test_pre_generate_hook_error_propagates(tmpsite):
    """Test that errors in pre_generate hooks propagate."""
    hooks = GenerateHooks()

    @hooks.on_generate_pre.register()
    def failing_hook(args: GeneratePreHookArgs) -> GeneratePreHookArgs:
        raise RuntimeError("Hook failed!")

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite, hooks=hooks)

    # when / then
    with raises(RuntimeError, match="Hook failed!"):
        automata.website.generate(config, resources)


def test_post_generate_hook_error_propagates(tmpsite):
    """Test that errors in post_generate hooks propagate."""
    hooks = GenerateHooks()

    @hooks.on_generate_post.register()
    def failing_hook(args: GeneratePostHookArgs) -> None:
        raise RuntimeError("Hook failed!")

    tmpsite.make_page("index.md", "# Home")

    config = automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    resources = make_resources(tmpsite, hooks=hooks)

    # when / then
    with raises(RuntimeError, match="Hook failed!"):
        automata.website.generate(config, resources)


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

    # when - pass a WebsiteResources with materials rooted in the build directory
    from automata.materials import ExportedMaterials, Universe

    resources = WebsiteResources(
        templates={"page.html": MINIMAL_TEMPLATE},
        materials=ExportedMaterials(
            root=materials_in_build,
            universe=Universe(collections={}),
        ),
    )
    automata.website.generate(config, resources)

    # then - verify the page was generated and materials are still there
    assert "Test Page" in tmpsite.get_output("index.html")
    assert (materials_in_build / "materials.json").exists()
    assert test_file.read_text() == "original content"


# resources.pages =====================================================================


def test_pages_with_string_renders_through_full_pipeline(tmpsite, config):
    """String page content goes through full pipeline."""
    # given
    markdown_content = "# Extra Page\n\nThis is **bold** text."

    # when
    resources = make_resources(tmpsite, pages={"extra.html": markdown_content})
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("extra.html")
    assert "<h1>Extra Page</h1>" in output
    assert "<strong>bold</strong>" in output


def test_pages_with_string_supports_frontmatter(tmpsite, config):
    """String page content with frontmatter should have it parsed."""
    # given
    content_with_frontmatter = """---
vars:
  greeting: Hello World
---
# ${ frontmatter.vars.greeting }
"""

    # when
    resources = make_resources(
        tmpsite, pages={"greeting.html": content_with_frontmatter}
    )
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("greeting.html")
    assert "<h1>Hello World</h1>" in output


def test_pages_with_string_supports_variable_interpolation(tmpsite, config):
    """String page content should have access to render context variables."""
    # given
    content = "Base path: ${ website_config.base_path }"

    # when
    resources = make_resources(tmpsite, pages={"info.html": content})
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("info.html")
    assert "Base path: /" in output


def test_pages_with_bytes_writes_binary(tmpsite, config):
    """Bytes page content should be written directly as binary."""
    # given
    binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # PNG header bytes

    # when
    resources = make_resources(tmpsite, pages={"image.png": binary_content})
    automata.website.generate(config, resources)

    # then
    output_path = tmpsite.build_directory / "image.png"
    assert output_path.exists()
    assert output_path.read_bytes() == binary_content


def test_pages_with_traversable_renders_text(tmpsite, config, tmp_path):
    """Traversable page content should be read as text and rendered."""
    # given
    source_file = tmp_path / "source.html"
    source_file.write_text("# From Traversable")

    # when
    resources = make_resources(tmpsite, pages={"copied.html": source_file})
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("copied.html")
    assert "<h1>From Traversable</h1>" in output


def test_pages_creates_subdirectories(tmpsite, config):
    """Pages with nested paths should create parent directories."""
    # given
    content = "# Nested Page"

    # when
    resources = make_resources(tmpsite, pages={"deep/nested/page.html": content})
    automata.website.generate(config, resources)

    # then
    output = tmpsite.get_output("deep/nested/page.html")
    assert "<h1>Nested Page</h1>" in output


def test_pages_with_multiple_items(tmpsite, config):
    """Multiple page items of different types should all be processed."""
    # when
    resources = make_resources(
        tmpsite,
        pages={
            "page.html": "# A Page",
            "binary.bin": b"\x00\x01\x02",
        },
    )
    automata.website.generate(config, resources)

    # then
    assert "<h1>A Page</h1>" in tmpsite.get_output("page.html")
    assert (tmpsite.build_directory / "binary.bin").read_bytes() == b"\x00\x01\x02"


def test_pre_generate_pipeline_chains_transformations(tmpsite, config):
    """Test that pre-generate pipeline hooks chain their transformations."""
    hooks = GenerateHooks()

    @hooks.on_generate_pre.register()
    def add_page_a(args: GeneratePreHookArgs) -> GeneratePreHookArgs:
        return replace(
            args,
            resources=replace(
                args.resources,
                pages={**args.resources.pages, "a.html": "# Page A"},
            ),
        )

    @hooks.on_generate_pre.register()
    def add_page_b(args: GeneratePreHookArgs) -> GeneratePreHookArgs:
        return replace(
            args,
            resources=replace(
                args.resources,
                pages={**args.resources.pages, "b.html": "# Page B"},
            ),
        )

    tmpsite.make_page("index.md", "# Test")
    automata.website.generate(config, make_resources(tmpsite, hooks=hooks))

    # Both pages should be generated (pipeline chains results)
    assert "<h1>Page A</h1>" in tmpsite.get_output("a.html")
    assert "<h1>Page B</h1>" in tmpsite.get_output("b.html")


def test_hooks_receive_correct_config(tmpsite, config):
    """Test that hooks receive the correct WebsiteConfig."""
    hooks = GenerateHooks()
    received_config = []

    @hooks.on_generate_post.register()
    def capture_config(args: GeneratePostHookArgs) -> None:
        received_config.append(args.config)

    tmpsite.make_page("index.md", "# Test")
    automata.website.generate(config, make_resources(tmpsite, hooks=hooks))

    assert len(received_config) == 1
    assert received_config[0] is config
