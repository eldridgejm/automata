import automata.website

# basic page rendering =================================================================


def test_converts_pages_from_markdown_to_html(tmpsite):
    # given
    tmpsite.make_page("one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(tmpsite.content_path, tmpsite.website_path)

    # then
    assert "This is a header</h1>" in tmpsite.get_output("one.html")


def test_converts_pages_from_markdown_to_html_recursively(tmpsite):
    # given
    tmpsite.make_page("index.md", "Home page")
    tmpsite.make_page("subdir/one.md", "# This is a header\n**this is bold!**")

    # when
    automata.website.generate(tmpsite.content_path, tmpsite.website_path)

    # then
    assert "This is a header</h1>" in tmpsite.get_output("subdir/one.html")

    assert "Home page" in tmpsite.get_output("index.html")


def test_copies_files_from_content_to_output(tmpsite):
    # given
    tmpsite.make_page("data/tabular/one.txt", "This is a text file in a subdir.")

    # when
    automata.website.generate(tmpsite.content_path, tmpsite.website_path)

    # then
    assert "This is a text file in a subdir." in tmpsite.get_output(
        "data/tabular/one.txt"
    )


def test_vars_can_be_used_in_markdown_pages(tmpsite):
    # given
    tmpsite.make_page("index.md", "The value of 'foo' is ${ vars.foo }.")

    # when
    automata.website.generate(
        tmpsite.content_path, tmpsite.website_path, vars={"foo": "bar"}
    )

    # then
    assert "The value of 'foo' is bar." in tmpsite.get_output("index.html")
