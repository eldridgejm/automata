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
