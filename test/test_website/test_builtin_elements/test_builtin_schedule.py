"""Tests for the schedule element functionality.

These tests focus on the internal logic and functionality of the Schedule element,
testing it directly rather than through the full render() pipeline.
"""

import datetime

import jinja2
import pytest
import smartconfig.exceptions
import smartconfig.types

import automata.materials
import automata.website
from automata.builtin.elements import Schedule
from automata.util.resolution import format_keypath
from automata.website import RenderContext

# Fixtures ===========================================================================


@pytest.fixture
def render_context():
    """Create a minimal RenderContext for testing."""
    # Create empty materials universe
    materials = automata.materials.Universe(collections={})

    # Simple url_for function
    def url_for(path):
        return f"/{path}"

    return RenderContext(
        materials=materials,
        url_for=url_for,
        current_time=datetime.datetime(2024, 1, 15, 12, 0, 0),
    )


@pytest.fixture
def jinja_env():
    """Create a minimal Jinja2 environment for testing."""
    return jinja2.Environment(loader=jinja2.DictLoader({}))


@pytest.fixture
def schedule_element(jinja_env, render_context):
    """Create a Schedule element instance for testing."""
    return Schedule(jinja_env, render_context)


# validation and error handling ========================================================


def test_schedule_element_raises_on_missing_resource_type(
    schedule_element, render_context
):
    """Test that missing 'type' field in resource config raises ResolutionError."""
    # Create a materials universe with a lecture
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": "2024-01-08",
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": {
                        "__template__": "${ publication.metadata.date }"
                    },
                    "title": "Lecture",
                    "resources": [{"html": "<p>Content</p>"}],  # Missing 'type' field
                },
            }
        ],
        "secondary_activity_collections": [],
    }

    with pytest.raises(
        smartconfig.exceptions.ResolutionError,
        match="Resource config missing required 'type' field",
    ):
        # Call the element itself which goes through resolution
        schedule_element(config)


def test_schedule_element_raises_on_invalid_resource_type(
    schedule_element, render_context
):
    """Test that invalid 'type' field in resource config raises ResolutionError."""
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": "2024-01-08",
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": {
                        "__template__": "${ publication.metadata.date }"
                    },
                    "title": "Lecture",
                    "resources": [{"type": "invalid_type", "content": "Some content"}],
                },
            }
        ],
        "secondary_activity_collections": [],
    }

    with pytest.raises(
        smartconfig.exceptions.ResolutionError,
        match="Unsupported resource type: invalid_type",
    ):
        schedule_element(config)


def test_schedule_validates_html_resource_config(schedule_element):
    """Test that HTML resource config is validated (missing 'html' field)."""
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": "2024-01-08",
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": {
                        "__template__": "${ publication.metadata.date }"
                    },
                    "title": "Lecture",
                    "resources": [
                        {"type": "html", "title": "Materials"}  # Missing 'html' field
                    ],
                },
            }
        ],
        "secondary_activity_collections": [],
    }

    with pytest.raises(Exception):  # Should raise validation error
        schedule_element(config)


def test_schedule_validates_markdown_resource_config(schedule_element):
    """Test that Markdown resource config is validated (missing 'markdown' field)."""
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": "2024-01-08",
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": {
                        "__template__": "${ publication.metadata.date }"
                    },
                    "title": "Lecture",
                    "resources": [
                        {
                            "type": "markdown",
                            "title": "Reading",
                        }  # Missing 'markdown' field
                    ],
                },
            }
        ],
        "secondary_activity_collections": [],
    }

    with pytest.raises(Exception):  # Should raise validation error
        schedule_element(config)


def test_schedule_validates_metadata_links_resource_config(schedule_element):
    """Test that metadata links resource config is validated.

    Tests validation when required fields are missing.
    """
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": "2024-01-08",
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": {
                        "__template__": "${ publication.metadata.date }"
                    },
                    "title": "Lecture",
                    "resources": [
                        {
                            "type": "metadata_links",
                            "title": "Videos",
                        }  # Missing required fields
                    ],
                },
            }
        ],
        "secondary_activity_collections": [],
    }

    with pytest.raises(Exception):  # Should raise validation error
        schedule_element(config)


def test_schedule_validates_artifact_links_resource_config(schedule_element):
    """Test that artifact links config is validated (missing 'links')."""
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": "2024-01-08",
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": {
                        "__template__": "${ publication.metadata.date }"
                    },
                    "title": "Lecture",
                    "resources": [
                        {
                            "type": "artifact_links",
                            "title": "Slides",
                        }  # Missing 'links' field
                    ],
                },
            }
        ],
        "secondary_activity_collections": [],
    }

    with pytest.raises(Exception):  # Should raise validation error
        schedule_element(config)


def test_schedule_validates_artifact_link_config(schedule_element):
    """Test that ArtifactLinkConfig is validated (missing required fields)."""
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": "2024-01-08",
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": {
                        "__template__": "${ publication.metadata.date }"
                    },
                    "title": "Lecture",
                    "resources": [
                        {
                            "type": "artifact_links",
                            "title": "Slides",
                            "links": [
                                {"text": "pdf"}  # Missing 'artifact' field
                            ],
                        }
                    ],
                },
            }
        ],
        "secondary_activity_collections": [],
    }

    with pytest.raises(Exception):  # Should raise validation error
        schedule_element(config)


# activity placement logic =============================================================


def test_activities_placed_in_correct_week(schedule_element):
    """Test that activities are placed in the correct week based on display date."""

    # 1) make a fake context with a few lecture publications, each in a different week
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={
                            "number": 1,
                            "date": datetime.date(2024, 1, 8),  # Week 1
                        },
                        artifacts={},
                    ),
                    "lecture02": automata.materials.Publication(
                        metadata={
                            "number": 2,
                            "date": datetime.date(2024, 1, 17),  # Week 2
                        },
                        artifacts={},
                    ),
                },
            )
        }
    )

    # 2) create a schedule element and set its context to be the one we just made
    schedule_element.context.materials = materials
    schedule_element.context.current_time = datetime.datetime(2024, 1, 20, 12, 0, 0)

    # 3) create a schedule element config
    config = {
        "week_topics": ["Introduction", "Advanced Topics", "Even More Advanced Topics"],
        "first_week_start_date": datetime.date(2024, 1, 8),
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": {
                        "__template__": "${ publication.metadata.date }"
                    },
                    "title": "Lecture",
                    "resources": [],
                },
            }
        ],
        "secondary_activity_collections": [],
        "extra_primary_activities": [],
        "extra_secondary_activities": [],
        "events": [],
        "announcements": [],
    }

    # 4) call template_vars to process the activities and check that they are in the
    # expected weeks
    tvars = schedule_element.template_vars(config)

    # Lecture 1 (Jan 8) should be in week 1, Lecture 2 (Jan 17) should be in week 2
    assert len(tvars["primary_activities"][1]) == 1
    assert len(tvars["primary_activities"][2]) == 1


def test_activities_outside_week_range_placed_in_none_week(schedule_element):
    """Test that activities with dates outside all weeks are placed under None."""
    # Create a materials universe with a lecture outside the defined weeks
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={
                            "number": 1,
                            "date": datetime.date(2024, 1, 20),  # After week 1
                        },
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials
    schedule_element.context.current_time = datetime.datetime(2024, 1, 25, 12, 0, 0)

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": datetime.date(2024, 1, 8),  # Week 1: Jan 8-14
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": {
                        "__template__": "${ publication.metadata.date }"
                    },
                    "title": "Lecture",
                    "resources": [],
                },
            }
        ],
        "secondary_activity_collections": [],
        "extra_primary_activities": [],
        "extra_secondary_activities": [],
        "events": [],
        "announcements": [],
    }

    tvars = schedule_element.template_vars(config)

    # Activity should be in None week (date is outside all defined weeks)
    assert None in tvars["primary_activities"]
    assert len(tvars["primary_activities"][None]) == 1
    assert len(tvars["primary_activities"][1]) == 0


# resources ============================================================================


def test_metadata_links_resources_are_expanded(schedule_element):
    """Test that metadata_links resources are expanded correctly via template_vars."""
    # Create a materials universe with a lecture that has videos metadata
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={
                            "number": 1,
                            "date": "2024-01-08",
                            "videos": [
                                {"text": "Introduction", "url": "intro.mp4"},
                                {"text": "Setup Guide", "url": "setup.mp4"},
                            ],
                        },
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": datetime.date(2024, 1, 8),
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": datetime.date(2024, 1, 8),
                    "title": "Lecture",
                    "resources": [
                        {
                            "type": "metadata_links",
                            "title": "Videos",
                            "icon": "video",
                            "style": "buttons",
                            "metadata_key_for_links": "videos",
                            "for_each_link": {
                                "text": {"__template__": "${ link.text }"},
                                "url": {"__template__": "${ link.url }"},
                            },
                        }
                    ],
                },
            }
        ],
        "secondary_activity_collections": [],
        "extra_primary_activities": [],
        "extra_secondary_activities": [],
        "events": [],
        "announcements": [],
    }

    # Get template vars which processes the activities
    tvars = schedule_element.template_vars(config)

    # Check that we have primary activities
    activities = tvars["primary_activities"][1]
    activity = activities[0]

    # Check that the metadata_links resource was converted to links
    assert len(activity.resources) == 1
    resource = activity.resources[0]
    assert resource["type"] == "links"
    assert resource["title"] == "Videos"
    assert resource["icon"] == "video"
    assert resource["style"] == "buttons"
    assert len(resource["links"]) == 2
    assert resource["links"][0]["text"] == "Introduction"
    assert resource["links"][0]["url"] == "intro.mp4"
    assert resource["links"][1]["text"] == "Setup Guide"
    assert resource["links"][1]["url"] == "setup.mp4"


def test_metadata_links_with_missing_metadata_key(schedule_element):
    """Test that metadata_links returns empty list when metadata key is missing."""
    # Create a materials universe with a lecture that has NO videos metadata
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={},
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": datetime.date(2024, 1, 8),
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": datetime.date(2024, 1, 8),
                    "title": "Lecture",
                    "resources": [
                        {
                            "type": "metadata_links",
                            "title": "Videos",
                            "metadata_key_for_links": "videos",
                            "for_each_link": {
                                "text": {"__template__": "${ link.text }"},
                                "url": {"__template__": "${ link.url }"},
                            },
                        }
                    ],
                },
            }
        ],
        "secondary_activity_collections": [],
        "extra_primary_activities": [],
        "extra_secondary_activities": [],
        "events": [],
        "announcements": [],
    }

    # Get template vars which processes the activities
    tvars = schedule_element.template_vars(config)

    # Check that the resource has empty links
    activities = tvars["primary_activities"][1]
    activity = activities[0]
    resource = activity.resources[0]
    assert resource["type"] == "links"
    assert resource["links"] == []


def test_artifact_links_are_converted_to_links(schedule_element):
    """Test that artifact_links are converted to regular links correctly."""
    # Create a materials universe with a lecture that has artifacts
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={
                            "slides.pdf": automata.materials.ExportedArtifact(
                                path="/lectures/lecture01/slides.pdf",
                            ),
                            "slides.pptx": automata.materials.ExportedArtifact(
                                path="/lectures/lecture01/slides.pptx",
                            ),
                        },
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": datetime.date(2024, 1, 8),
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": datetime.date(2024, 1, 8),
                    "title": "Lecture",
                    "resources": [
                        {
                            "type": "artifact_links",
                            "title": "Slides",
                            "icon": "file",
                            "style": "buttons",
                            "links": [
                                {"text": "pdf", "artifact": "slides.pdf"},
                                {"text": "pptx", "artifact": "slides.pptx"},
                            ],
                        }
                    ],
                },
            }
        ],
        "secondary_activity_collections": [],
        "extra_primary_activities": [],
        "extra_secondary_activities": [],
        "events": [],
        "announcements": [],
    }

    # Get template vars which processes the activities
    tvars = schedule_element.template_vars(config)

    # Check that the artifact_links resource was converted to links
    activities = tvars["primary_activities"][1]
    activity = activities[0]
    resource = activity.resources[0]
    assert resource["type"] == "links"
    assert resource["title"] == "Slides"
    assert resource["icon"] == "file"
    assert resource["style"] == "buttons"
    assert len(resource["links"]) == 2
    assert resource["links"][0]["text"] == "pdf"
    assert resource["links"][0]["url"] == "/lectures/lecture01/slides.pdf"
    assert resource["links"][1]["text"] == "pptx"
    assert resource["links"][1]["url"] == "/lectures/lecture01/slides.pptx"


def test_artifact_links_filters_nonexistent_artifacts(schedule_element):
    """Test that artifact_links only includes links for existing artifacts."""
    # Create a materials universe with a lecture that has only some artifacts
    materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"number": 1, "date": "2024-01-08"},
                        artifacts={
                            "slides.pdf": automata.materials.ExportedArtifact(
                                path="/lectures/lecture01/slides.pdf",
                            ),
                            # slides.pptx and slides.odp do not exist
                        },
                    )
                },
            )
        }
    )
    schedule_element.context.materials = materials

    config = {
        "week_topics": ["Introduction"],
        "first_week_start_date": datetime.date(2024, 1, 8),
        "primary_activity_collections": [
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": datetime.date(2024, 1, 8),
                    "title": "Lecture",
                    "resources": [
                        {
                            "type": "artifact_links",
                            "title": "Slides",
                            "links": [
                                {"text": "pdf", "artifact": "slides.pdf"},
                                {"text": "pptx", "artifact": "slides.pptx"},
                                {"text": "odp", "artifact": "slides.odp"},
                            ],
                        }
                    ],
                },
            }
        ],
        "secondary_activity_collections": [],
        "extra_primary_activities": [],
        "extra_secondary_activities": [],
        "events": [],
        "announcements": [],
    }

    # Get template vars which processes the activities
    tvars = schedule_element.template_vars(config)

    # Check that only the existing artifact link is included
    activities = tvars["primary_activities"][1]
    activity = activities[0]
    resource = activity.resources[0]
    assert len(resource["links"]) == 1  # Only pdf exists
    assert resource["links"][0]["text"] == "pdf"
    assert resource["links"][0]["url"] == "/lectures/lecture01/slides.pdf"


# week order ===========================================================================


def _weekly_config(**overrides):
    config = {
        "week_topics": ["One", "Two", "Three"],
        "first_week_start_date": datetime.date(2024, 1, 8),
        "primary_activity_collections": [],
        "secondary_activity_collections": [],
        "extra_primary_activities": [],
        "extra_secondary_activities": [],
        "events": [],
        "announcements": [],
    }
    config.update(overrides)
    return config


def test_chronological_week_order_lists_weeks_from_first_to_last(schedule_element):
    # current time is in week 2, so this_week_first would start with week 2
    schedule_element.context.current_time = datetime.datetime(2024, 1, 17)

    tvars = schedule_element.template_vars(_weekly_config(week_order="chronological"))

    assert [week.number for week in tvars["weeks"]] == [1, 2, 3]


def test_this_week_first_week_order_starts_with_the_current_week(schedule_element):
    schedule_element.context.current_time = datetime.datetime(2024, 1, 17)

    tvars = schedule_element.template_vars(_weekly_config(week_order="this_week_first"))

    assert [week.number for week in tvars["weeks"]][0] == 2


def test_unknown_week_order_is_an_error_naming_the_choices(schedule_element):
    with pytest.raises(smartconfig.exceptions.ResolutionError) as excinfo:
        schedule_element.template_vars(_weekly_config(week_order="alphabetical"))

    assert format_keypath(excinfo.value.keypath) == "week_order"
    assert excinfo.value.reason == (
        'Must be "this_week_first" or "chronological", not "alphabetical".'
    )


# extra activities =====================================================================


def test_extra_activities_cannot_use_publication_resources(schedule_element):
    config = _weekly_config(
        extra_primary_activities=[
            {
                "title": "Review session",
                "start_displaying_on": datetime.date(2024, 1, 10),
                "resources": [
                    {"type": "artifact_links", "title": "Slides", "links": []}
                ],
            }
        ]
    )

    with pytest.raises(smartconfig.exceptions.ResolutionError) as excinfo:
        schedule_element.template_vars(config)

    assert format_keypath(excinfo.value.keypath) == (
        "extra_primary_activities.0.resources.0.type"
    )
    assert "artifact_links" in excinfo.value.reason


def test_extra_activity_errors_give_the_activity_index(schedule_element):
    good = {
        "title": "Review session",
        "start_displaying_on": datetime.date(2024, 1, 10),
        "resources": [],
    }
    bad = {**good, "start_displaying_on": "not a date"}
    config = _weekly_config(extra_secondary_activities=[good, bad])

    with pytest.raises(smartconfig.exceptions.ResolutionError) as excinfo:
        schedule_element.template_vars(config)

    assert format_keypath(excinfo.value.keypath) == (
        "extra_secondary_activities.1.start_displaying_on"
    )


# publication errors ===================================================================


def test_publication_errors_give_the_keypath_and_the_publication(schedule_element):
    def lecture(metadata):
        return automata.materials.Publication(metadata=metadata, artifacts={})

    schedule_element.context.materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": lecture({"date": "2024-01-08"}),
                    "lecture02": lecture({}),
                },
            )
        }
    )
    config = _weekly_config(
        primary_activity_collections=[
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": "${ publication.metadata.date }",
                    "title": "Lecture",
                    "resources": [],
                },
            }
        ]
    )

    with pytest.raises(smartconfig.exceptions.ResolutionError) as excinfo:
        schedule_element.template_vars(config)

    assert format_keypath(excinfo.value.keypath) == (
        "primary_activity_collections.0.for_each_publication.start_displaying_on"
    )
    assert excinfo.value.reason.endswith('(for publication "lecture02")')


def test_publication_metadata_typos_suggest_the_key(schedule_element):
    schedule_element.context.materials = automata.materials.Universe(
        collections={
            "lectures": automata.materials.Collection(
                publication_schema=None,
                publications={
                    "lecture01": automata.materials.Publication(
                        metadata={"topic": "Sorting"}, artifacts={}
                    ),
                },
            )
        }
    )
    config = _weekly_config(
        primary_activity_collections=[
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": "2024-01-08",
                    "title": "${ publication.metadata.topc }",
                    "resources": [],
                },
            }
        ]
    )

    with pytest.raises(smartconfig.exceptions.ResolutionError) as excinfo:
        schedule_element.template_vars(config)

    assert excinfo.value.reason == (
        'The dict has no key "topc". Did you mean "topic"? (for publication '
        '"lecture01")'
    )


def test_unknown_collection_in_schedule_is_reported(schedule_element):
    config = _weekly_config(
        primary_activity_collections=[
            {
                "collection": "lectures",
                "for_each_publication": {
                    "start_displaying_on": "2024-01-08",
                    "title": "Lecture",
                    "resources": [],
                },
            }
        ]
    )

    with pytest.raises(automata.website.exceptions.WebsiteError) as excinfo:
        schedule_element.template_vars(config)

    assert 'unknown collection "lectures"' in str(excinfo.value)
