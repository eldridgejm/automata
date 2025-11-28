"""Tests for announcement_box element via public generate API."""

from textwrap import dedent

import pytest

import automata.website


def test_announcement_box_raises_on_unknown_variable(site):
    """Undefined variable in content triggers ElementError from evaluate filter."""
    site.make_page(
        "bad.md",
        dedent(
            """
            ${ elements.announcement_box({
                'content': '$( missing_var )',
                'urgent': true
            }) }
            """
        ),
    )

    with pytest.raises(automata.website.ElementError):
        automata.website.generate(site.path, site.builddir)


def test_announcement_box_defaults_to_non_urgent(site):
    """Omitting urgent uses the Prototype default and renders non-urgent styling."""
    site.make_page(
        "default.md",
        dedent(
            """
            ${ elements.announcement_box({
                'content': 'Hello world'
            }) }
            """
        ),
    )

    automata.website.generate(site.path, site.builddir)

    output = site.get_output("default.html")
    assert "Hello world" in output
    assert 'class="announcement urgent"' not in output
    assert 'class="announcement">' in output


def test_announcement_box_renders_content_and_urgency(site):
    """Renders content and marks urgent announcements."""
    site.make_page(
        "ok.md",
        dedent(
            """
            ${ elements.announcement_box({
                'content': 'Hello world',
                'urgent': true
            }) }
            """
        ),
    )

    automata.website.generate(site.path, site.builddir)

    output = site.get_output("ok.html")
    assert "Hello world" in output
    assert 'class="announcement urgent"' in output
