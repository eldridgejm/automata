"""Tests for schedule element rendering."""

import datetime
from textwrap import dedent

import automata.materials as materials
import automata.website


def make_universe(now: datetime.datetime) -> materials.Universe:
    """Build a small universe with dates suited for schedule rendering."""
    schema = materials.PublicationSchema(
        required_artifacts=[],
        optional_artifacts=None,
        metadata_schema=None,
        allow_unspecified_artifacts=True,
    )

    lectures = materials.Collection(
        publication_schema=schema,
        publications={
            "lec1": materials.Publication(
                metadata={
                    "name": "Lecture 1",
                    "released": now,
                    "parts": [{"title": "Part A"}, {"title": "Part B"}],
                },
                artifacts={},
            )
        },
    )

    assignments = materials.Collection(
        publication_schema=schema,
        publications={
            "hw1": materials.Publication(
                metadata={
                    "name": "HW1",
                    "released": now,
                    "due": now + datetime.timedelta(days=5),
                },
                artifacts={
                    "homework.pdf": materials.ExportedArtifact(path="homework.pdf")
                },
            )
        },
    )

    discussions = materials.Collection(
        publication_schema=schema,
        publications={
            "disc1": materials.Publication(
                metadata={"name": "Discussion 1", "released": now},
                artifacts={},
            )
        },
    )

    return materials.Universe(
        collections={
            "lectures": lectures,
            "homeworks": assignments,
            "discussions": discussions,
        }
    )


def test_schedule_renders_current_and_future_weeks(site):
    """Render current/future weeks with resources, parts, and fallbacks."""
    now = datetime.datetime(2024, 1, 9, 12, 0, 0)
    site.write_materials(make_universe(now))

    site.make_page(
        "schedule.md",
        dedent(
            """
            ${ elements.schedule({
                'week_topics': ['Intro', 'Next'],
                'first_week_start_date': vars.first_week_start_date,
                'lecture': {
                    'collection': 'lectures',
                    'metadata_key_for_released': 'released',
                    'title': '$( publication.metadata["name"] )',
                    'resources': [
                        {
                            'title': 'Slides',
                            'text': 'Link to slides',
                            'requires': {
                                'artifacts': ['slides.pdf'],
                                'text_if_missing': 'No slides',
                            },
                        },
                        {
                            'text': 'Part: $( part["title"] )',
                            'key_for_parts': 'metadata.parts',
                        }
                    ],
                },
                'assignments': [
                    {
                        'collection': 'homeworks',
                        'metadata_key_for_released': 'released',
                        'metadata_key_for_due': 'due',
                        'title': '$( publication.metadata["name"] )',
                        'resources': [
                            {
                                'title': 'Homework',
                                'text': 'Submit',
                                'requires': {
                                    'artifacts': ['homework.pdf'],
                                    'text_if_missing': 'Missing hw',
                                },
                            },
                            {
                                'title': 'Solution',
                                'text': 'Solution link',
                                'requires': {
                                    'artifacts': ['solution.pdf'],
                                    'text_if_missing': 'Solution coming soon',
                                },
                            },
                        ],
                    },
                ],
                'discussions': [
                    {
                        'collection': 'discussions',
                        'metadata_key_for_released': 'released',
                        'title': '$( publication.metadata["name"] )',
                        'resources': [
                            {
                                'text': 'Notes',
                            },
                            {
                                'text': 'Hidden',
                                'requires': {
                                    'artifacts': ['notes.pdf'],
                                    'text_if_missing': None,
                                },
                            },
                        ],
                    }
                ],
                'exams': {'Midterm': vars.midterm_date},
                'week_announcements': [],
            }) }
            """
        ),
    )

    automata.website.generate(
        site.path,
        site.builddir,
        materials_path=site.builddir / "published",
        vars={
            "first_week_start_date": datetime.date(2024, 1, 8),
            "midterm_date": datetime.date(2024, 1, 9),
        },
        now=lambda: now,
    )

    output = site.get_output("schedule.html")
    assert "This Week" in output and "future weeks" in output
    assert "No slides" in output  # requires + text_if_missing path
    assert "Part: Part A" in output  # key_for_parts branch
    assert "Solution coming soon" in output  # missing artifact fallback


def test_schedule_handles_no_current_week_and_orders_last(site):
    """Handle no current week, ordering with this_week_last, and skip separators."""
    now = datetime.datetime(2023, 12, 1, 12, 0, 0)
    site.write_materials(make_universe(now=datetime.datetime(2024, 1, 8)))

    site.make_page(
        "schedule.md",
        dedent(
            """
            ${ elements.schedule({
                'week_topics': ['Intro', 'Next'],
                'first_week_start_date': vars.first_week_start_date,
                'week_order': 'this_week_last',
                'lecture': {
                    'collection': 'lectures',
                    'metadata_key_for_released': 'released',
                    'title': 'Lecture $( publication.metadata["name"] )',
                    'resources': [],
                },
                'assignments': [],
                'discussions': [],
                'exams': {},
                'week_announcements': [],
            }) }
            """
        ),
    )

    automata.website.generate(
        site.path,
        site.builddir,
        materials_path=site.builddir / "published",
        vars={"first_week_start_date": datetime.date(2024, 1, 8)},
        now=lambda: now,
    )

    output = site.get_output("schedule.html")
    assert "This Week" in output  # first week still labelled
    assert "future weeks" not in output  # this_week None path should skip separators
    assert output.index("Week 2") > output.index("This Week")  # ordered ascending


def test_schedule_renders_week_announcements(site):
    """Render week-specific announcements with urgent styling."""
    now = datetime.datetime(2024, 1, 9, 12, 0, 0)
    site.write_materials(make_universe(now))

    site.make_page(
        "schedule.md",
        dedent(
            """
            ${ elements.schedule({
                'week_topics': ['Intro'],
                'first_week_start_date': vars.first_week_start_date,
                'lecture': {
                    'collection': 'lectures',
                    'metadata_key_for_released': 'released',
                    'title': '$( publication.metadata["name"] )',
                    'resources': [],
                },
                'assignments': [],
                'discussions': [],
                'exams': {},
                'week_announcements': [
                    {'week': 1, 'content': 'Urgent note', 'urgent': True},
                ],
            }) }
            """
        ),
    )

    automata.website.generate(
        site.path,
        site.builddir,
        materials_path=site.builddir / "published",
        vars={"first_week_start_date": datetime.date(2024, 1, 8)},
        now=lambda: now,
    )

    output = site.get_output("schedule.html")
    assert "Urgent note" in output
    assert "alert-danger" in output
