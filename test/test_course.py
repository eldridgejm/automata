"""Tests for the course section of automata.yaml, and where it is used."""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from automata import Automata
from automata.config import read_config
from automata.exceptions import Error

_COURSE = """\
course:
  name: DSC 40B
  title: Theoretical Foundations of Data Science II
  term: Winter 2025
  first_week_start: 2025-01-06
  timezone: America/Los_Angeles
"""

_WEBSITE = """\
website:
  theme: {use: default, config: {rebuild_tailwind: false}}
  content_directory: content
  build_directory: _build
"""


def _project(tmp_path: Path, config: str = _COURSE + _WEBSITE) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "automata.yaml").write_text(config)
    (project / "content").mkdir()
    (project / "content" / "index.md").write_text("# Home")
    return project


# the configuration ====================================================================


def test_the_course_section_is_read(tmp_path):
    project = _project(tmp_path)

    course = read_config(project / "automata.yaml").course

    assert course.name == "DSC 40B"
    assert course.title == "Theoretical Foundations of Data Science II"
    assert course.term == "Winter 2025"
    assert course.first_week_start == datetime.date(2025, 1, 6)
    assert course.first_week_number == 1
    assert course.timezone == "America/Los_Angeles"
    assert course.instructors == []
    assert course.url is None


def test_the_course_section_is_required(tmp_path):
    project = _project(tmp_path, _WEBSITE)

    with pytest.raises(Error) as excinfo:
        read_config(project / "automata.yaml")

    assert 'missing required key "course"' in str(excinfo.value)


@pytest.mark.parametrize(
    "key", ["name", "title", "term", "first_week_start", "timezone"]
)
def test_the_core_course_fields_are_required(tmp_path, key):
    lines = [line for line in _COURSE.splitlines() if not line.startswith(f"  {key}:")]
    project = _project(tmp_path, "\n".join(lines) + "\n" + _WEBSITE)

    with pytest.raises(Error) as excinfo:
        read_config(project / "automata.yaml")

    assert f'course.{key}: Dictionary is missing required key "{key}".' in str(
        excinfo.value
    )


def test_the_course_timezone_must_be_a_time_zone(tmp_path):
    config = _COURSE.replace("America/Los_Angeles", "Pacific")
    project = _project(tmp_path, config + _WEBSITE)

    with pytest.raises(Error) as excinfo:
        read_config(project / "automata.yaml")

    assert str(excinfo.value) == (
        f'{project / "automata.yaml"}:6: course.timezone: "Pacific" isn\'t a time '
        'zone. Use a name from the IANA time zone database, like "America/Los_Angeles".'
    )


# times are in the course's time zone ==================================================


def _release_project(tmp_path: Path, release_time: str, timezone: str) -> Path:
    """A project with one artifact, hw.pdf, released at *release_time*."""
    course = _COURSE.replace("America/Los_Angeles", timezone)
    project = _project(tmp_path, course + _WEBSITE)
    (project / "hw").mkdir()
    (project / "hw" / "publication.yaml").write_text(
        "artifacts:\n"
        "  hw.pdf:\n"
        "    recipe: touch hw.pdf\n"
        f"    release_time: {release_time}\n"
    )
    return project


def _released(project: Path) -> bool:
    return any((project / "_build").rglob("hw.pdf"))


_UTC = datetime.timezone.utc


@pytest.mark.parametrize("hour, released", [(18, False), (20, True)])
def test_release_times_are_in_the_course_time_zone(
    tmp_path, machine_in_utc, hour, released
):
    # given: a release at noon in Los Angeles, which is 19:00 UTC
    project = _release_project(tmp_path, "2026-10-29 12:00:00", "America/Los_Angeles")

    # when: built at a time given in UTC
    Automata(project).build(
        current_time=datetime.datetime(2026, 10, 29, hour, 0, tzinfo=_UTC)
    )

    # then
    assert _released(project) is released


@pytest.mark.parametrize(
    "minute, released", [(14 * 60 + 30, False), (15 * 60 + 30, True)]
)
def test_release_times_with_an_offset_are_converted_to_the_course_time_zone(
    tmp_path, minute, released
):
    # given: a release at noon at UTC-7, which is 15:00 in New York
    project = _release_project(
        tmp_path, "2026-10-29T12:00:00-07:00", "America/New_York"
    )

    # when: built at a time without an offset, so in the course's time zone
    current_time = datetime.datetime(2026, 10, 29) + datetime.timedelta(minutes=minute)
    Automata(project).build(current_time=current_time)

    # then
    assert _released(project) is released


def test_the_current_time_is_the_courses_not_the_machines(tmp_path, machine_in_utc):
    # given: a release three hours from now in Los Angeles, which is already
    # past in UTC (always 7 or 8 hours ahead)
    zone = ZoneInfo("America/Los_Angeles")
    release = datetime.datetime.now(zone) + datetime.timedelta(hours=3)
    project = _release_project(
        tmp_path, f"{release:%Y-%m-%d %H:%M:%S}", "America/Los_Angeles"
    )

    # when
    Automata(project).build()

    # then
    assert not _released(project)


def test_status_is_in_the_course_time_zone(tmp_path, machine_in_utc):
    project = _release_project(tmp_path, "2026-10-29 12:00:00", "America/Los_Angeles")

    status = Automata(project).status(
        current_time=datetime.datetime(2026, 10, 29, 18, 0, tzinfo=_UTC)
    )

    assert status.current_time == datetime.datetime(2026, 10, 29, 11, 0)
    assert status.counts == {"scheduled": 1}


# where course is available ============================================================


def test_course_is_available_in_automata_yaml(tmp_path):
    config = _COURSE + 'vars:\n  heading: "${ course.name }, ${ course.term }"\n'
    project = _project(tmp_path, config + _WEBSITE)

    vars = read_config(project / "automata.yaml").vars

    assert vars["heading"] == "DSC 40B, Winter 2025"


def test_course_is_available_in_publication_yaml(tmp_path):
    project = _project(tmp_path)
    (project / "hw" / "01").mkdir(parents=True)
    (project / "hw" / "collection.yaml").write_text(
        "publication_schema:\n  required_artifacts: []\n"
    )
    (project / "hw" / "01" / "publication.yaml").write_text(
        'metadata:\n  term: "${ course.term }"\nartifacts: {}\n'
    )

    universe = Automata(project).discover()

    assert universe.collections["hw"].publications["01"].metadata == {
        "term": "Winter 2025"
    }


def test_course_is_available_in_pages_and_their_frontmatter(tmp_path):
    project = _project(tmp_path)
    (project / "content" / "index.md").write_text(
        '---\nvars:\n  heading: "${ course.title }"\n---\n'
        "# ${ frontmatter.vars.heading } (${ course.name })\n"
    )

    Automata(project).build()

    html = (project / "_build" / "index.html").read_text()
    assert "Theoretical Foundations of Data Science II (DSC 40B)" in html


def test_the_theme_titles_default_to_the_course(tmp_path):
    project = _project(tmp_path)

    Automata(project).build()

    html = (project / "_build" / "index.html").read_text()
    assert "<title>DSC 40B</title>" in html
    assert "Theoretical Foundations of Data Science II" in html


def test_the_theme_titles_can_still_be_set(tmp_path):
    website = _WEBSITE.replace(
        "  theme: {use: default, config: {rebuild_tailwind: false}}\n",
        "  theme:\n"
        "    use: default\n"
        "    config: {short_title: 40B, long_title: Algs, rebuild_tailwind: false}\n",
    )
    project = _project(tmp_path, _COURSE + website)

    Automata(project).build()

    assert "<title>40B</title>" in (project / "_build" / "index.html").read_text()


# the calendar =========================================================================


def _calendar_project(tmp_path, course=_COURSE):
    config = (
        course
        + "calendar:\n  collections:\n    hw:\n      dates:\n        due:\n"
        + _WEBSITE
    )
    project = _project(tmp_path, config)
    (project / "hw").mkdir()
    (project / "hw" / "collection.yaml").write_text(
        "publication_schema:\n  required_artifacts: []\n"
    )
    for name, due in [("01", "2025-01-03"), ("02", "2025-01-10"), ("03", "2025-01-17")]:
        (project / "hw" / name).mkdir()
        (project / "hw" / name / "publication.yaml").write_text(
            f"metadata:\n  due: {due}\nartifacts: {{}}\n"
        )
    return project


def test_calendar_weeks_are_numbered_from_the_course_first_week(tmp_path):
    # the course's first week starts Monday Jan 6; the calendar's weeks start on
    # Sunday, so the week of Sunday Jan 5 is week 1
    project = _calendar_project(tmp_path)

    calendar = Automata(project).calendar(all_weeks=True)

    assert [(w.start, w.number) for w in calendar.weeks] == [
        (datetime.date(2024, 12, 29), None),  # before the course's first week
        (datetime.date(2025, 1, 5), 1),
        (datetime.date(2025, 1, 12), 2),
    ]


def test_calendar_week_numbers_can_start_at_zero(tmp_path):
    course = _COURSE + "  first_week_number: 0\n"
    project = _calendar_project(tmp_path, course)

    calendar = Automata(project).calendar(all_weeks=True)

    assert [w.number for w in calendar.weeks] == [None, 0, 1]


def test_the_calendar_is_titled_with_the_course(tmp_path):
    project = _calendar_project(tmp_path)

    calendar = Automata(project).calendar(all_weeks=True)

    assert calendar.title == "DSC 40B, Winter 2025"
    assert "DSC 40B, Winter 2025" in calendar.to_html()


def test_calendar_labels_can_use_course(tmp_path):
    project = _calendar_project(tmp_path)
    config = project / "automata.yaml"
    config.write_text(
        config.read_text().replace(
            "        due:\n",
            "        due: !template "
            '"${ course.name } HW ${ publication.metadata.due }"\n',
        )
    )

    calendar = Automata(project).calendar(all_weeks=True)

    labels = [e.label for w in calendar.weeks for d in w.days for e in d.entries]
    assert labels[0] == "DSC 40B HW 2025-01-03"


# the schedule element =================================================================


def test_the_schedule_takes_its_first_week_from_the_course(tmp_path):
    website = _WEBSITE + (
        "  elements:\n"
        "    schedule:\n"
        "      week_topics: [Intro, Sorting]\n"
        "      primary_activity_collections: []\n"
        "      secondary_activity_collections: []\n"
    )
    project = _project(tmp_path, _COURSE + website)
    (project / "content" / "index.md").write_text("${ elements.schedule() }")

    Automata(project).build(current_time=datetime.datetime(2025, 1, 8))

    html = (project / "_build" / "index.html").read_text()
    assert "Intro" in html and "Sorting" in html


@pytest.mark.parametrize(
    "key", ["first_week_start_date: 2025-01-06", "first_week_number: 1"]
)
def test_the_schedule_no_longer_configures_its_first_week(tmp_path, key):
    # the course's first_week_start and first_week_number are the only source
    website = _WEBSITE + (
        "  elements:\n"
        "    schedule:\n"
        f"      {key}\n"
        "      week_topics: [Intro, Sorting]\n"
        "      primary_activity_collections: []\n"
        "      secondary_activity_collections: []\n"
    )
    project = _project(tmp_path, _COURSE + website)
    (project / "content" / "index.md").write_text("${ elements.schedule() }")

    with pytest.raises(Error) as excinfo:
        Automata(project).build(current_time=datetime.datetime(2025, 1, 8))

    assert key.split(":")[0] in str(excinfo.value)
