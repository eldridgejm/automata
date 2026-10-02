"""Tests for reading page frontmatter."""

import pytest

from automata.website._frontmatter import Frontmatter, read_frontmatter


@pytest.mark.parametrize(
    "page, template, content",
    [
        # no frontmatter
        ("# Hi", "page.html", "# Hi"),
        # ordinary frontmatter
        ("---\ntemplate: x.html\n---\n# Hi", "x.html", "# Hi"),
        # empty frontmatter
        ("---\n---\n# Hi", "page.html", "# Hi"),
        # frontmatter that is only a comment
        ("---\n# just a note\n---\n# Hi", "page.html", "# Hi"),
        # frontmatter at the end of the file, without a final newline
        ("---\ntemplate: x.html\n---", "x.html", ""),
        # a --- that doesn't close the frontmatter on a line of its own
        ("---\ntemplate: x.html\n---\nA\n---\nB", "x.html", "A\n---\nB"),
    ],
)
def test_frontmatter_is_read(page, template, content):
    frontmatter, rest = read_frontmatter(page)

    assert frontmatter.template == template
    assert rest == content


def test_unclosed_frontmatter_is_content():
    frontmatter, rest = read_frontmatter("---\ntemplate: x.html\n# Hi")

    assert frontmatter == Frontmatter(vars={})
    assert rest == "---\ntemplate: x.html\n# Hi"
