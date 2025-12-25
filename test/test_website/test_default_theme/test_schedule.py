"""Tests for the schedule element."""

import automata.materials
import automata.website


def test_schedule_element_renders_basic_week(tmpsite):
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
            "lecture": {
                "collection": "lectures",
                "metadata_key_for_released": "date",
                "title": "Lecture {{ publication.metadata.number }}",
                "resources": []
            },
            "assignments": [],
            "discussions": []
        }) }
        """,
    )

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Week" in output
    assert "Introduction" in output


def test_schedule_element_renders_multiple_weeks(tmpsite):
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
            "lecture": {
                "collection": "lectures",
                "metadata_key_for_released": "date",
                "title": "Lecture",
                "resources": []
            },
            "assignments": [],
            "discussions": []
        }) }
        """,
    )

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert "Intro" in output
    assert "Python" in output
    assert "Data" in output
