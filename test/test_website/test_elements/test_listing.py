"""Tests for listing element rendering."""

from textwrap import dedent

import pytest
import smartconfig

import automata.website


def test_listing_renders_publications_in_order(tmpsite):
    tmpsite.make_page(
        "listing.md",
        dedent(
            """
            ${ elements.listing({
                'collection': 'homeworks',
                'columns': [
                    {'heading': 'Name',
                     'cell_content': '$( publication.metadata["name"] )'},
                    {'heading': 'Due',
                     'cell_content': '$( publication.metadata["due"] )'},
                ],
            }) }
            """
        ),
    )
    materials_path = tmpsite.use_example_materials()

    automata.website.generate(tmpsite.content_path, tmpsite.output_path, materials_path)

    output = tmpsite.get_output("listing.html")
    assert "Name" in output and "Due" in output
    assert output.index("Homework 01") < output.index("Homework 02")


def test_listing_supports_numbered_rows(tmpsite):
    tmpsite.make_page(
        "listing.md",
        dedent(
            """
            ${ elements.listing({
                'collection': 'homeworks',
                'numbered': true,
                'columns': [
                    {'heading': 'Name',
                     'cell_content': '$( publication.metadata["name"] )'},
                ],
            }) }
            """
        ),
    )
    materials_path = tmpsite.use_example_materials()

    automata.website.generate(tmpsite.content_path, tmpsite.output_path, materials_path)

    output = tmpsite.get_output("listing.html")
    assert '<th scope="row"> 1' in output
    assert '<th scope="row"> 2' in output


def test_listing_uses_fallback_when_requirements_missing(tmpsite):
    """Missing artifacts/metadata trigger fallback cell content via requires."""
    materials_path = tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                    },
                    "publications": {
                        "01": {
                            "metadata": {"name": "HW1", "due": None},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "listing.md",
        dedent(
            """
            ${ elements.listing({
                'collection': 'homeworks',
                'columns': [
                    {
                        'heading': 'Status',
                        'cell_content': '$( publication.metadata.get("name") )',
                        'requires': {
                            'artifacts': ['homework.pdf'],
                            'metadata': ['name'],
                            'non_null_metadata': ['due'],
                            'cell_content_if_missing': 'Missing info',
                        },
                    },
                ],
            }) }
            """
        ),
    )

    automata.website.generate(tmpsite.content_path, tmpsite.output_path, materials_path)

    output = tmpsite.get_output("listing.html")
    assert "Missing info" in output


def test_listing_requires_non_null_metadata(tmpsite):
    """Fallback triggers when non-null metadata is missing (value is None)."""
    materials_path = tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                    },
                    "publications": {
                        "01": {
                            "metadata": {"name": "HW1", "due": None},
                            "artifacts": {
                                "homework.pdf": {"path": "homeworks/01/hw.pdf"}
                            },
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "listing.md",
        dedent(
            """
            ${ elements.listing({
                'collection': 'homeworks',
                'columns': [
                    {
                        'heading': 'Status',
                        'cell_content': '$( publication.metadata.get("name") )',
                        'requires': {
                            'artifacts': [],
                            'metadata': [],
                            'non_null_metadata': ['due'],
                            'cell_content_if_missing': 'Due date missing',
                        },
                    },
                ],
            }) }
            """
        ),
    )

    automata.website.generate(tmpsite.content_path, tmpsite.output_path, materials_path)

    output = tmpsite.get_output("listing.html")
    assert "Due date missing" in output


def test_listing_requires_missing_metadata_key(tmpsite):
    """Fallback triggers when required metadata key is absent."""
    materials_path = tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                    },
                    "publications": {
                        "01": {
                            "metadata": {"name": "HW1"},
                            "artifacts": {
                                "homework.pdf": {"path": "homeworks/01/hw.pdf"}
                            },
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "listing.md",
        dedent(
            """
            ${ elements.listing({
                'collection': 'homeworks',
                'columns': [
                    {
                        'heading': 'Status',
                        'cell_content': '$( publication.metadata.get("name") )',
                        'requires': {
                            'artifacts': [],
                            'metadata': ['foo'],
                            'non_null_metadata': [],
                            'cell_content_if_missing': 'Required metadata missing',
                        },
                    },
                ],
            }) }
            """
        ),
    )

    automata.website.generate(tmpsite.content_path, tmpsite.output_path, materials_path)

    output = tmpsite.get_output("listing.html")
    assert "Required metadata missing" in output


def test_listing_validates_schema(tmpsite):
    # Missing required "columns" field should fail schema resolution.
    tmpsite.make_page(
        "listing.md",
        dedent(
            """
            ${ elements.listing({
                'collection': 'homeworks'
            }) }
            """
        ),
    )
    materials_path = tmpsite.use_example_materials()

    with pytest.raises(smartconfig.exceptions.ResolutionError):
        automata.website.generate(
            tmpsite.content_path, tmpsite.output_path, materials_path
        )
