"""Tests for people element rendering and validation."""

from textwrap import dedent

import pytest
import smartconfig

import automata.website


def test_people_renders_minimal_group(tmpsite):
    """Render a group with required fields only."""
    tmpsite.make_page(
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

    automata.website.generate(tmpsite.content_path, tmpsite.output_path)

    output = tmpsite.get_output("people.html")
    assert "Instructors" in output
    assert "Ada" in output
    assert "role" not in output  # optional fields omitted


def test_people_validates_required_member_fields(tmpsite):
    """Missing required member field triggers schema resolution error."""
    tmpsite.make_page(
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
        automata.website.generate(tmpsite.content_path, tmpsite.output_path)
