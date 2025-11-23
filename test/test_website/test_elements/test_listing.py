"""Tests for listing element rendering."""

from textwrap import dedent

import pytest
import smartconfig

import automata.website


def test_listing_renders_publications_in_order(site):
    site.make_page(
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
    materials_path = site.use_example_published()

    automata.website.generate(site.path, site.builddir, materials_path)

    output = site.get_output("listing.html")
    assert "Name" in output and "Due" in output
    assert output.index("Homework 01") < output.index("Homework 02")


def test_listing_supports_numbered_rows(site):
    site.make_page(
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
    materials_path = site.use_example_published()

    automata.website.generate(site.path, site.builddir, materials_path)

    output = site.get_output("listing.html")
    assert '<th scope="row"> 1' in output
    assert '<th scope="row"> 2' in output


def test_listing_uses_fallback_when_requirements_missing(site):
    """Missing artifacts/metadata trigger fallback cell content via requires."""
    materials_path = site.write_materials(
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

    site.make_page(
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

    automata.website.generate(site.path, site.builddir, materials_path)

    output = site.get_output("listing.html")
    assert "Missing info" in output


def test_listing_requires_non_null_metadata(site):
    """Fallback triggers when non-null metadata is missing (value is None)."""
    materials_path = site.write_materials(
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

    site.make_page(
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

    automata.website.generate(site.path, site.builddir, materials_path)

    output = site.get_output("listing.html")
    assert "Due date missing" in output


def test_listing_requires_missing_metadata_key(site):
    """Fallback triggers when required metadata key is absent."""
    materials_path = site.write_materials(
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

    site.make_page(
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

    automata.website.generate(site.path, site.builddir, materials_path)

    output = site.get_output("listing.html")
    assert "Required metadata missing" in output


def test_listing_validates_schema(site):
    # Missing required "columns" field should fail schema resolution.
    site.make_page(
        "listing.md",
        dedent(
            """
            ${ elements.listing({
                'collection': 'homeworks'
            }) }
            """
        ),
    )
    materials_path = site.use_example_published()

    with pytest.raises(smartconfig.exceptions.ResolutionError):
        automata.website.generate(site.path, site.builddir, materials_path)
