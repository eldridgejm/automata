"""Tests for the schedule element."""

import datetime

import smartconfig.exceptions
from bs4 import BeautifulSoup, Tag
from pytest import fixture, raises

import automata.website
from automata.website.exceptions import WebsiteError


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


def find_week(html: str, week: int) -> Tag:
    """Helper to find a week section in the rendered HTML by week number."""
    soup = BeautifulSoup(html, "html.parser")
    # the week sections have IDs like "week-1", "week-2", etc.
    week_id = f"week-{week}"
    week_section = soup.find(id=week_id)
    assert week_section is not None, f"Week section with ID '{week_id}' not found."
    return week_section


def test_schedule_element_renders_basic_week(tmpsite, config):
    """Test rendering a basic schedule with one week."""
    # given: empty materials for now
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {},
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture {{ publication.metadata.number }}",
                        "resources": []
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Week" in output
    assert "Introduction" in output


def test_schedule_element_renders_multiple_weeks(tmpsite, config):
    """Test rendering multiple weeks with topics."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {},
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Intro", "Python", "Data"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture",
                        "resources": []
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Intro" in output
    assert "Python" in output
    assert "Data" in output


def test_schedule_element_renders_html_resource(tmpsite, config):
    """Test rendering HTML resource type."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture {{ publication.metadata.number }}",
                        "resources": [
                            {
                                "type": "html",
                                "title": "Materials",
                                "html": "<a href='slides.pdf'>Slides</a>"
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Materials" in output
    assert "Slides" in output
    assert "href='slides.pdf'" in output or 'href="slides.pdf"' in output


def test_schedule_element_renders_markdown_resource(tmpsite, config):
    """Test rendering Markdown resource type."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture {{ publication.metadata.number }}",
                        "resources": [
                            {
                                "type": "markdown",
                                "title": "Reading",
                                "markdown": (
                                    "Read **Chapter 1** in the [textbook](book.pdf)"
                                ),
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Reading" in output
    assert "<strong>Chapter 1</strong>" in output or "<b>Chapter 1</b>" in output
    assert "textbook" in output
    assert 'href="book.pdf"' in output or "href='book.pdf'" in output


def test_schedule_element_renders_metadata_links_resource(tmpsite, config):
    """Test rendering metadata links resource type."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {
                                "number": 1,
                                "date": "2024-01-08",
                                "videos": [
                                    {"text": "Introduction", "url": "intro.mp4"},
                                    {"text": "Setup Guide", "url": "setup.mp4"},
                                ],
                            },
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__raw__": "Lecture ${ publication.metadata.number }"
                        },
                        "resources": [
                            {
                                "type": "metadata_links",
                                "title": "Videos",
                                "metadata_key_for_links": "videos",
                                "for_each_link": {
                                    "text": {"__raw__": "${ link.text }"},
                                    "url": {"__raw__": "${ link.url }"}
                                }
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Videos" in output
    assert "Introduction" in output
    assert "Setup Guide" in output
    assert 'href="intro.mp4"' in output or "href='intro.mp4'" in output
    assert 'href="setup.mp4"' in output or "href='setup.mp4'" in output


def test_schedule_element_renders_artifact_links_resource(tmpsite, config):
    """Test rendering artifact links resource type when all artifacts exist."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {
                                "slides.pdf": {
                                    "path": "/lectures/lecture01/slides.pdf",
                                },
                                "slides.pptx": {
                                    "path": "/lectures/lecture01/slides.pptx",
                                },
                            },
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__raw__": "Lecture ${ publication.metadata.number }"
                        },
                        "resources": [
                            {
                                "type": "artifact_links",
                                "title": "Slides",
                                "links": [
                                    {"text": "pdf", "artifact": "slides.pdf"},
                                    {"text": "pptx", "artifact": "slides.pptx"}
                                ]
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Slides" in output
    assert "pdf" in output
    assert "pptx" in output
    assert "/lectures/lecture01/slides.pdf" in output
    assert "/lectures/lecture01/slides.pptx" in output


def test_schedule_element_artifact_links_only_shows_existing_artifacts(tmpsite, config):
    """Test that artifact links only shows links for artifacts that exist."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {
                                "slides.pdf": {
                                    "path": "/lectures/lecture01/slides.pdf",
                                },
                                "slides.pptx": {
                                    "path": "/lectures/lecture01/slides.pptx",
                                },
                                # slides.odp does NOT exist
                            },
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__raw__": "Lecture ${ publication.metadata.number }"
                        },
                        "resources": [
                            {
                                "type": "artifact_links",
                                "title": "Slides",
                                "links": [
                                    {"text": "pdf", "artifact": "slides.pdf"},
                                    {"text": "pptx", "artifact": "slides.pptx"},
                                    {"text": "odp", "artifact": "slides.odp"}
                                ]
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    # Title should appear since some artifacts exist
    assert "Slides" in output
    # Buttons for existing artifacts should appear
    assert "pdf" in output
    assert "pptx" in output
    assert "/lectures/lecture01/slides.pdf" in output
    assert "/lectures/lecture01/slides.pptx" in output
    # Button for non-existent artifact should NOT appear
    assert "odp" not in output.lower()


def test_schedule_element_raises_on_missing_resource_type(tmpsite, config):
    """Test that missing 'type' field in resource config raises ResolutionError."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture",
                        "resources": [
                            {
                                "html": "<p>Content</p>"
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when/then
    with raises(
        smartconfig.exceptions.ResolutionError,
        match="Resource config missing required 'type' field",
    ):
        automata.website.generate(config)


def test_schedule_element_raises_on_invalid_resource_type(tmpsite, config):
    """Test that invalid 'type' field in resource config raises ResolutionError."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture",
                        "resources": [
                            {
                                "type": "invalid_type",
                                "content": "Some content"
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when/then
    with raises(
        smartconfig.exceptions.ResolutionError,
        match="Unsupported resource type: invalid_type",
    ):
        automata.website.generate(config)


def test_schedule_element_validates_html_resource_config(tmpsite, config):
    """Test that HTML resource config is validated (missing 'html' field)."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture",
                        "resources": [
                            {
                                "type": "html",
                                "title": "Materials"
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when/then - should raise an error for missing 'html' field
    with raises(Exception):
        automata.website.generate(config)


def test_schedule_element_validates_markdown_resource_config(tmpsite, config):
    """Test that Markdown resource config is validated (missing 'markdown' field)."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture",
                        "resources": [
                            {
                                "type": "markdown",
                                "title": "Reading"
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when/then - should raise an error for missing 'markdown' field
    with raises(Exception):
        automata.website.generate(config)


def test_schedule_element_validates_metadata_links_resource_config(tmpsite, config):
    """
    Test that metadata links resource config is validated (missing required fields).
    """
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture",
                        "resources": [
                            {
                                "type": "items",
                                "title": "Videos"
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when/then - should raise error for missing required fields
    with raises(Exception):
        automata.website.generate(config)


def test_schedule_element_validates_artifact_links_resource_config(tmpsite, config):
    """Test that artifact links config is validated (missing 'links')."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture",
                        "resources": [
                            {
                                "type": "artifact_buttons",
                                "title": "Slides"
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when/then - should raise an error for missing 'buttons' field
    with raises(Exception):
        automata.website.generate(config)


def test_schedule_element_validates_artifact_link_config(tmpsite, config):
    """Test that ArtifactLinkConfig is validated (missing required fields)."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture",
                        "resources": [
                            {
                                "type": "artifact_buttons",
                                "title": "Slides",
                                "buttons": [
                                    {"text": "pdf"}
                                ]
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when/then - should raise an error for missing 'artifact' field in button
    with raises(Exception):
        automata.website.generate(config)


def test_schedule_element_html_resource_does_not_render_when_whitespace_only(
    tmpsite, config
):
    """Test that HTML resource with only whitespace does not render."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture {{ publication.metadata.number }}",
                        "resources": [
                            {
                                "type": "html",
                                "title": "Whitespace Resource",
                                "html": "   \\n\\t  "
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then - title should not appear since content is only whitespace
    output = tmpsite.get_output("index.html")
    assert "Whitespace Resource" not in output


def test_schedule_element_markdown_resource_does_not_render_when_whitespace_only(
    tmpsite, config
):
    """Test that Markdown resource with only whitespace does not render."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture {{ publication.metadata.number }}",
                        "resources": [
                            {
                                "type": "markdown",
                                "title": "Whitespace Reading",
                                "markdown": "\\n\\n   \\n\\t\\t  "
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then - title should not appear since content is only whitespace
    output = tmpsite.get_output("index.html")
    assert "Whitespace Reading" not in output


def test_schedule_element_metadata_links_resource_does_not_render_when_no_links(
    tmpsite, config
):
    """Test that metadata links resource does not render when there are no links."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {
                                "number": 1,
                                "date": "2024-01-08",
                                "videos": [],  # Empty list
                            },
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__raw__": "Lecture ${ publication.metadata.number }"
                        },
                        "resources": [
                            {
                                "type": "metadata_links",
                                "title": "Videos",
                                "metadata_key_for_links": "videos",
                                "for_each_link": {
                                    "text": {"__raw__": "${ link.text }"},
                                    "url": {"__raw__": "${ link.url }"}
                                }
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then - title should not appear since there are no items
    output = tmpsite.get_output("index.html")
    assert "Videos" not in output


def test_schedule_element_metadata_links_resource_no_render_when_missing_key(
    tmpsite, config
):
    """
    Test that metadata links resource does not render when metadata key is missing.
    """
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {
                                "number": 1,
                                "date": "2024-01-08",
                                # videos key is missing
                            },
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__raw__": "Lecture ${ publication.metadata.number }"
                        },
                        "resources": [
                            {
                                "type": "metadata_links",
                                "title": "Videos",
                                "metadata_key_for_links": "videos",
                                "for_each_link": {
                                    "text": {"__raw__": "${ link.text }"},
                                    "url": {"__raw__": "${ link.url }"}
                                }
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then - title should not appear since metadata key is missing
    output = tmpsite.get_output("index.html")
    assert "Videos" not in output


def test_schedule_element_artifact_links_does_not_render_when_no_artifacts(
    tmpsite, config
):
    """Test that artifact links does not render when no artifacts."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},  # No artifacts
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__raw__": "Lecture ${ publication.metadata.number }"
                        },
                        "resources": [
                            {
                                "type": "artifact_links",
                                "title": "Slides",
                                "links": [
                                    {"text": "pdf", "artifact": "slides.pdf"},
                                    {"text": "pptx", "artifact": "slides.pptx"}
                                ]
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then - title should not appear since there are no artifacts
    output = tmpsite.get_output("index.html")
    assert "Slides" not in output


def test_schedule_element_resource_with_icon(tmpsite, config):
    """Test that resources can display Lucide icons."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {
                        "lecture01": {
                            "metadata": {"number": 1, "date": "2024-01-08"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "lectures",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.date }"
                        },
                        "title": "Lecture {{ publication.metadata.number }}",
                        "resources": [
                            {
                                "type": "html",
                                "title": "Slides",
                                "html": "<p>Lecture content</p>",
                                "icon": "file-text"
                            }
                        ]
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Slides" in output
    assert 'data-lucide="file-text"' in output


def test_schedule_element_renders_extra_primary_listings(tmpsite, config):
    """Test rendering extra_primary_activities that are not tied to a publication."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {},
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [],
            "secondary_activity_collections": [],
            "extra_primary_activities": [
                {
                    "title": "Exam Review Session",
                    "start_displaying_on": "2024-01-10",
                    "resources": [
                        {
                            "type": "markdown",
                            "title": "Review Materials",
                            "icon": "file-text",
                            "markdown": "Review session on **Wednesday**"
                        }
                    ]
                }
            ]
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Exam Review Session" in output
    assert "Review Materials" in output
    assert "Review session on" in output
    assert "<strong>Wednesday</strong>" in output or "<b>Wednesday</b>" in output
    assert 'data-lucide="file-text"' in output


def test_schedule_element_renders_extra_secondary_listings(tmpsite, config):
    """Test rendering extra_secondary_activities (not tied to a publication)."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {},
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [],
            "secondary_activity_collections": [],
            "extra_secondary_activities": [
                {
                    "title": "Office Hours",
                    "start_displaying_on": "2024-01-09",
                    "resources": [
                        {
                            "type": "html",
                            "title": "Location",
                            "icon": "map-pin",
                            "html": "CSE Building Room 101"
                        }
                    ]
                }
            ]
        }) }
        """,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Office Hours" in output
    assert "Location" in output
    assert 'data-lucide="map-pin"' in output
    assert "CSE Building Room 101" in output


def test_schedule_element_rejects_artifact_links_in_extra_listings(tmpsite, config):
    """Test that artifact_links resources are rejected in extra activities."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {},
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [],
            "secondary_activity_collections": [],
            "extra_primary_activities": [
                {
                    "title": "Invalid Item",
                    "start_displaying_on": "2024-01-09",
                    "resources": [
                        {
                            "type": "artifact_links",
                            "links": []
                        }
                    ]
                }
            ]
        }) }
        """,
    )

    # when/then
    with raises(
        WebsiteError,
        match=r"Extra activities can only use 'html', 'markdown', or 'links'",
    ):
        automata.website.generate(config)


def test_schedule_element_rejects_metadata_links_in_extra_listings(tmpsite, config):
    """Test that metadata_links resources are rejected in extra activities."""
    # given
    tmpsite.write_materials_json(
        {
            "collections": {
                "lectures": {
                    "publication_schema": {
                        "required_artifacts": [],
                        "optional_artifacts": None,
                        "metadata_schema": None,
                        "allow_unspecified_artifacts": True,
                        "is_ordered": False,
                    },
                    "publications": {},
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Introduction"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [],
            "secondary_activity_collections": [],
            "extra_secondary_activities": [
                {
                    "title": "Invalid Item",
                    "start_displaying_on": "2024-01-09",
                    "resources": [
                        {
                            "type": "metadata_links",
                            "metadata_key_for_links": "test",
                            "for_each_link": {"text": "test", "url": "test"}
                        }
                    ]
                }
            ]
        }) }
        """,
    )

    # when/then
    with raises(
        WebsiteError,
        match=r"Extra activities can only use 'html', 'markdown', or 'links'",
    ):
        automata.website.generate(config)


# schedule placement logic (start_displaying_on, week_range_start, week_range_end)
# ======================================================================================


def test_schedule_with_only_start_displaying_on_uses_that_week(tmpsite, config):
    """Test that with only start_displaying_on, publication appears in that week."""
    # given: homework released Jan 15 (Week 2)
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
                            "metadata": {"number": 1, "released": "2024-01-15"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Week 1", "Week 2", "Week 3"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "homeworks",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.released }"
                        },
                        "title": {
                            "__raw__": "Homework ${ publication.metadata.number }"
                        },
                        "resources": []
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # Test 1: During Week 1 (Jan 12) - before release, should not appear
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-12T12:00:00"),
    )

    assert "Homework 1" not in tmpsite.get_output("index.html")

    # Test 2: During Week 2 (Jan 16) - should appear in Week 2
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-16T12:00:00"),
    )

    output_week2 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output_week2, week=2).get_text()

    # Test 3: During Week 3 (Jan 23) - should still appear in Week 2
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-23T12:00:00"),
    )

    output_week3 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output_week3, week=2).get_text()
    assert "Homework 1" not in find_week(output_week3, week=1).get_text()
    assert "Homework 1" not in find_week(output_week3, week=3).get_text()


def test_schedule_with_week_range(tmpsite, config):
    """This tests using a week range (week_range_start and week_range_end).

    The placement logic is as follows:

    1. If the current date is before `week_range_start`, the publication appears in the
    week containing `week_range_start`.

    2. If the current date is after `week_range_end`, the publication appears
    in the week containing `week_range_end`.

    3. If the current date is between `week_range_start` and `week_range_end`, the
    publication appears in the week containing the current date.

    """

    # start of Week 1: Jan 8
    # start of Week 2: Jan 15
    # start of Week 3: Jan 22
    # start of Week 4: Jan 29
    # given: homework released Jan 14 (end of Week 1)
    # range from Jan 14 (Week 2) to Jan 28 (Week 3)
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
                            "metadata": {
                                "number": 1,
                                "released": "2024-01-14",
                                "range_start": "2024-01-14",
                                "range_end": "2024-01-28",
                            },
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Week 1", "Week 2", "Week 3", "Week 4"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "homeworks",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.released }"
                        },
                        "week_range_start": {
                            "__raw__": "${ publication.metadata.range_start }"
                        },
                        "week_range_end": {
                            "__raw__": "${ publication.metadata.range_end }"
                        },
                        "title": {
                            "__raw__": "Homework ${ publication.metadata.number }"
                        },
                        "resources": []
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # given:
    # start of Week 1: Jan 8
    # start of Week 2: Jan 15
    # start of Week 3: Jan 22
    # start of Week 4: Jan 29
    # given: homework released Jan 14 (end of Week 1)
    # range from Jan 14 (Week 2) to Jan 28 (Week 3)

    # Test 1: Jan 10 - before release. Should not appear
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-10T12:00:00"),
    )

    assert "Homework 1" not in tmpsite.get_output("index.html")

    # Test 2: Jan 14 - on release date. Should appear only in Week 1
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-14T12:00:00"),
    )

    output2 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output2, week=1).get_text()
    assert "Homework 1" not in find_week(output2, week=2).get_text()

    # Test 3: Jan 22 - start of Week 3. Should appear only in Week 3
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-22T12:00:00"),
    )

    output3 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output3, week=3).get_text()
    assert "Homework 1" not in find_week(output3, week=1).get_text()
    assert "Homework 1" not in find_week(output3, week=2).get_text()

    # Test 4: Jan 28 - end of range. Should appear only in Week 3
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-28T12:00:00"),
    )

    output4 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output4, week=3).get_text()
    assert "Homework 1" not in find_week(output4, week=1).get_text()
    assert "Homework 1" not in find_week(output4, week=2).get_text()

    # Test 5: Jan 30 - after range. Should appear only in Week 3
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-30T12:00:00"),
    )

    output5 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output5, week=3).get_text()
    assert "Homework 1" not in find_week(output5, week=1).get_text()
    assert "Homework 1" not in find_week(output5, week=2).get_text()
    assert "Homework 1" not in find_week(output5, week=4).get_text()


def test_schedule_without_week_range_start_defaults_to_start_displaying_on(
    tmpsite, config
):
    """Test that when week_range_start is missing, it defaults to
    start_displaying_on."""
    # given: homework released Jan 15 (Week 2)
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
                            "metadata": {"number": 1, "released": "2024-01-15"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Week 1", "Week 2", "Week 3"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "homeworks",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.released }"
                        },
                        "title": {
                            "__raw__": "Homework ${ publication.metadata.number }"
                        },
                        "resources": []
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when/then - during Week 2 (Jan 16) - should appear in Week 2
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-16T12:00:00"),
    )

    output_week2 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output_week2, week=2).get_text()


def test_schedule_without_week_range_end_defaults_to_week_range_start(tmpsite, config):
    """Test that when week_range_end is missing, it defaults to week_range_start."""
    # given: homework released Jan 15 (Week 2)
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
                            "metadata": {"number": 1, "released": "2024-01-15"},
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Week 1", "Week 2", "Week 3"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "homeworks",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.released }"
                        },
                        "week_range_start": {
                            "__raw__": "${ publication.metadata.released }"
                        },
                        "title": {
                            "__raw__": "Homework ${ publication.metadata.number }"
                        },
                        "resources": []
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # when/then - during Week 2 (Jan 16) - should appear in Week 2
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-16T12:00:00"),
    )

    output_week2 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output_week2, week=2).get_text()

    # when/then - during Week 3 (Jan 23) - should still appear in Week 2
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-23T12:00:00"),
    )

    output_week3 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output_week3, week=2).get_text()


def test_schedule_with_range_that_is_in_the_future(tmpsite, config):
    """Here, the publication is released well before the week range starts."""
    # given: we release the publication at the beginning of Week 1, but the week range
    # is from the beginning of Week 3 to the end of Week 4.

    # start of Week 1: Jan 8
    # start of Week 2: Jan 15
    # start of Week 3: Jan 22
    # start of Week 4: Jan 29
    # start of Week 5: Feb 5
    # given: homework released Jan 8 (Week 1)
    # range from Jan 22 (Week 3) to Feb 4 (Week 4)
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
                            "metadata": {
                                "number": 1,
                                "released": "2024-01-08",
                                "range_start": "2024-01-22",
                                "range_end": "2024-02-04",
                            },
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "homeworks",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ publication.metadata.released }"
                        },
                        "week_range_start": {
                            "__raw__": "${ publication.metadata.range_start }"
                        },
                        "week_range_end": {
                            "__raw__": "${ publication.metadata.range_end }"
                        },
                        "title": {
                            "__raw__": "Homework ${ publication.metadata.number }"
                        },
                        "resources": []
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # Test 1: Jan 10 (Week 1, after release, before range) - should appear in Week 3
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-10T12:00:00"),
    )

    output1 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output1, week=3).get_text()
    assert "Homework 1" not in find_week(output1, week=1).get_text()
    assert "Homework 1" not in find_week(output1, week=2).get_text()

    # Test 2: Jan 18 (Week 2, still before range) - should appear in Week 3
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-18T12:00:00"),
    )

    output2 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output2, week=3).get_text()
    assert "Homework 1" not in find_week(output2, week=1).get_text()
    assert "Homework 1" not in find_week(output2, week=2).get_text()

    # Test 3: Jan 24 (Week 3, within range) - should appear in Week 3
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-24T12:00:00"),
    )

    output3 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output3, week=3).get_text()
    assert "Homework 1" not in find_week(output3, week=1).get_text()
    assert "Homework 1" not in find_week(output3, week=2).get_text()

    # Test 4: Jan 30 (Week 4, within range) - should appear in Week 4
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-30T12:00:00"),
    )

    output4 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output4, week=4).get_text()
    assert "Homework 1" not in find_week(output4, week=1).get_text()
    assert "Homework 1" not in find_week(output4, week=2).get_text()
    assert "Homework 1" not in find_week(output4, week=3).get_text()

    # Test 5: Feb 6 (Week 5, after range) - should stay pinned to Week 4
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-02-06T12:00:00"),
    )

    output5 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output5, week=4).get_text()
    assert "Homework 1" not in find_week(output5, week=1).get_text()
    assert "Homework 1" not in find_week(output5, week=2).get_text()
    assert "Homework 1" not in find_week(output5, week=3).get_text()
    assert "Homework 1" not in find_week(output5, week=5).get_text()


def test_schedule_date_fields_are_resolved(tmpsite, config):
    """For example, start_displaying_on can be a string of the form:

    start_displaying_on: 2 days before ${ publication.metadata.due_date }

    """
    # given: homework with due date Jan 22 (Week 3), released 7 days before
    # start of Week 1: Jan 8
    # start of Week 2: Jan 15 (this is 7 days before Jan 22)
    # start of Week 3: Jan 22
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
                            "metadata": {
                                "number": 1,
                                "due_date": "2024-01-22",
                                "released": "2024-01-15",
                            },
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Week 1", "Week 2", "Week 3"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "homeworks",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "2 days before ${publication.metadata.released}"
                        },
                        "title": {
                            "__raw__": "Homework ${ publication.metadata.number }"
                        },
                        "resources": []
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # Test 1: Jan 12 (Week 1, before resolved release date) - should not appear
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-10T12:00:00"),
    )

    assert "Homework 1" not in tmpsite.get_output("index.html")

    # Test 2: Jan 13 (Week 1, on resolved release date) - should appear in Week 1
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-16T12:00:00"),
    )

    output2 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output2, week=1).get_text()


def test_schedule_date_fields_can_use_vars(tmpsite, config):
    """Check date fields can use variables passed to generate() through vars kwarg"""
    # given: homework that uses a variable passed to generate()
    # start of Week 1: Jan 8
    # start of Week 2: Jan 15
    # start of Week 3: Jan 22
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
                            "metadata": {
                                "number": 1,
                            },
                            "artifacts": {},
                        }
                    },
                }
            }
        }
    )

    tmpsite.make_page(
        "index.html",
        """
        ${ elements.schedule({
            "week_topics": ["Week 1", "Week 2", "Week 3"],
            "first_week_start_date": "2024-01-08",
            "primary_activity_collections": [
                {
                    "collection": "homeworks",
                    "for_each_publication": {
                        "start_displaying_on": {
                            "__raw__": "${ vars.hw_release_date }"
                        },
                        "title": {
                            "__raw__": "Homework ${ publication.metadata.number }"
                        },
                        "resources": []
                    }
                }
            ],
            "secondary_activity_collections": []
        }) }
        """,
    )

    # Test 1: Jan 10 (Week 1, before vars.hw_release_date) - should not appear
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-10T12:00:00"),
        vars={"hw_release_date": "2024-01-16"},
    )

    assert "Homework 1" not in tmpsite.get_output("index.html")

    # Test 2: Jan 17 (Week 2, after vars.hw_release_date) - should appear in Week 2
    automata.website.generate(
        config,
        current_time=datetime.datetime.fromisoformat("2024-01-17T12:00:00"),
        vars={"hw_release_date": "2024-01-16"},
    )

    output2 = tmpsite.get_output("index.html")
    assert "Homework 1" in find_week(output2, week=2).get_text()
