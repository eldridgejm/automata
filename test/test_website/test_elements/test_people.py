"""Tests for people element rendering and validation."""

from textwrap import dedent

import pytest
import smartconfig

import automata.website


def test_people_renders_minimal_group(site):
    """Render a group with required fields only."""
    site.make_page(
        "people.md",
        dedent(
            """
            ${ elements.people({
                'groups': [
                    {'name': 'Instructors', 'members': [{'name': 'Ada'}]}
                ]
            }) }
            """
        ),
    )

    automata.website.generate(site.path, site.builddir)

    output = site.get_output("people.html")
    assert "Instructors" in output
    assert "Ada" in output
    assert "role" not in output  # optional fields omitted


def test_people_validates_required_member_fields(site):
    """Missing required member field triggers schema resolution error."""
    site.make_page(
        "people.md",
        dedent(
            """
            ${ elements.people({
                'groups': [
                    {'name': 'TAs', 'members': [{}]}
                ]
            }) }
            """
        ),
    )

    with pytest.raises(smartconfig.exceptions.ResolutionError):
        automata.website.generate(site.path, site.builddir)
