"""Tests for the schedule element rendering in the default theme.

These tests focus on how the default theme renders the schedule element,
testing through the full generate() pipeline and inspecting HTML output.
"""

from bs4 import BeautifulSoup, Tag
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
                            "__template__": "${ publication.metadata.date }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__template__": "Lecture ${ publication.metadata.number }"
                        },
                        "resources": [
                            {
                                "type": "metadata_links",
                                "title": "Videos",
                                "metadata_key_for_links": "videos",
                                "for_each_link": {
                                    "text": {"__template__": "${ link.text }"},
                                    "url": {"__template__": "${ link.url }"}
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__template__": "Lecture ${ publication.metadata.number }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__template__": "Lecture ${ publication.metadata.number }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__template__": "Lecture ${ publication.metadata.number }"
                        },
                        "resources": [
                            {
                                "type": "metadata_links",
                                "title": "Videos",
                                "metadata_key_for_links": "videos",
                                "for_each_link": {
                                    "text": {"__template__": "${ link.text }"},
                                    "url": {"__template__": "${ link.url }"}
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__template__": "Lecture ${ publication.metadata.number }"
                        },
                        "resources": [
                            {
                                "type": "metadata_links",
                                "title": "Videos",
                                "metadata_key_for_links": "videos",
                                "for_each_link": {
                                    "text": {"__template__": "${ link.text }"},
                                    "url": {"__template__": "${ link.url }"}
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
                        },
                        "title": {
                            "__template__": "Lecture ${ publication.metadata.number }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
                            "__template__": "${ publication.metadata.date }"
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
    automata.website.generate(config, tmpsite.materials_directory)

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
    automata.website.generate(config, tmpsite.materials_directory)

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
    automata.website.generate(config, tmpsite.materials_directory)

    # then
    output = tmpsite.get_output("index.html")
    assert "Office Hours" in output
    assert "Location" in output
    assert 'data-lucide="map-pin"' in output
    assert "CSE Building Room 101" in output
