"""Tests for the listing element."""

from pytest import fixture

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


def test_listing_element_renders_simple_table(tmpsite, config):
    """Test rendering a simple listing with one column."""
    # given: a course with homeworks
    tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "hw01": {
                            "metadata": {"name": "Homework 1", "due": "2024-01-15"},
                            "artifacts": {
                                "homework.pdf": {"path": "homeworks/hw01/homework.pdf"}
                            },
                        },
                        "hw02": {
                            "metadata": {"name": "Homework 2", "due": "2024-01-22"},
                            "artifacts": {
                                "homework.pdf": {"path": "homeworks/hw02/homework.pdf"}
                            },
                        },
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.listing({
            "collection": "homeworks",
            "columns": [
                {
                    "heading": "Assignment",
                    "cell_content": {"__raw__": "${ publication.metadata.name }"}
                }
            ]
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "<table" in output
    assert "Assignment" in output
    assert "Homework 1" in output
    assert "Homework 2" in output


def test_listing_element_renders_multiple_columns(tmpsite, config):
    """Test rendering a listing with multiple columns."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "hw01": {
                            "metadata": {"name": "Homework 1", "due": "2024-01-15"},
                            "artifacts": {
                                "homework.pdf": {"path": "homeworks/hw01/homework.pdf"}
                            },
                        },
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.listing({
            "collection": "homeworks",
            "columns": [
                {
                    "heading": "Assignment",
                    "cell_content": {"__raw__": "${ publication.metadata.name }"}
                },
                {
                    "heading": "Due Date",
                    "cell_content": {"__raw__": "${ publication.metadata.due }"}
                }
            ]
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Assignment" in output
    assert "Due Date" in output
    assert "Homework 1" in output
    assert "2024-01-15" in output


def test_listing_element_with_numbered_rows(tmpsite, config):
    """Test that numbered=true adds row numbers."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "hw01": {
                            "metadata": {"name": "Homework 1"},
                            "artifacts": {},
                        },
                        "hw02": {
                            "metadata": {"name": "Homework 2"},
                            "artifacts": {},
                        },
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.listing({
            "collection": "homeworks",
            "numbered": true,
            "columns": [
                {
                    "heading": "Assignment",
                    "cell_content": {"__raw__": "${ publication.metadata.name }"}
                }
            ]
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    # Should have a # header for the row number column
    assert "<th" in output and "#" in output


def test_listing_element_with_artifact_links(tmpsite, config):
    """Test listing with links to artifacts."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "hw01": {
                            "metadata": {"name": "Homework 1"},
                            "artifacts": {"hw.pdf": {"path": "homeworks/hw01/hw.pdf"}},
                        },
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.listing({
            "collection": "homeworks",
            "columns": [{
                "heading": "Problems",
                "cell_content": {"__raw__": "${ publication.metadata.name }"}
            }]
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then: artifacts should be accessible in templates
    output = tmpsite.get_output("index.html")
    assert "Homework 1" in output


def test_listing_element_conditional_content_when_artifact_missing(tmpsite, config):
    """Test that missing artifacts show fallback content."""
    # given: hw01 has artifact, hw02 does not
    tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "hw01": {
                            "metadata": {"name": "Homework 1"},
                            "artifacts": {
                                "solution.pdf": {"path": "homeworks/hw01/solution.pdf"}
                            },
                        },
                        "hw02": {
                            "metadata": {"name": "Homework 2"},
                            "artifacts": {},
                        },
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.listing({
            "collection": "homeworks",
            "columns": [
                {
                    "heading": "Solutions",
                    "cell_content": "Available",
                    "requires": {
                        "artifacts": ["solution.pdf"],
                        "cell_content_if_missing": "Not yet released"
                    }
                }
            ]
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Available" in output  # hw01 has the artifact
    assert "Not yet released" in output  # hw02 doesn't


def test_listing_element_conditional_content_when_metadata_missing(tmpsite, config):
    """Test that missing metadata shows fallback content."""
    # given: hw01 has due date, hw02 does not
    tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "hw01": {
                            "metadata": {"name": "Homework 1", "due": "2024-01-15"},
                            "artifacts": {},
                        },
                        "hw02": {
                            "metadata": {"name": "Homework 2"},
                            "artifacts": {},
                        },
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.listing({
            "collection": "homeworks",
            "columns": [
                {
                    "heading": "Due",
                    "cell_content": {"__raw__": "${ publication.metadata.due }"},
                    "requires": {
                        "metadata": ["due"],
                        "cell_content_if_missing": "TBD"
                    }
                }
            ]
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "2024-01-15" in output  # hw01 has due date
    assert "TBD" in output  # hw02 doesn't


def test_listing_element_conditional_content_non_null_metadata(tmpsite, config):
    """Test that null metadata values show fallback content."""
    # given: hw01 has non-null due date, hw02 has null due date
    tmpsite.write_materials_json(
        {
            "collections": {
                "homeworks": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "hw01": {
                            "metadata": {"name": "Homework 1", "due": "2024-01-15"},
                            "artifacts": {},
                        },
                        "hw02": {
                            "metadata": {"name": "Homework 2", "due": None},
                            "artifacts": {},
                        },
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.listing({
            "collection": "homeworks",
            "columns": [
                {
                    "heading": "Due",
                    "cell_content": {"__raw__": "${ publication.metadata.due }"},
                    "requires": {
                        "non_null_metadata": ["due"],
                        "cell_content_if_missing": "TBD"
                    }
                }
            ]
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "2024-01-15" in output  # hw01 has due date
    assert "TBD" in output  # hw02 has null due date
