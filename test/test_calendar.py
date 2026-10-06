"""Tests for Automata.calendar(all_weeks=True) and its renderings."""

import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from rich.console import Console
from rich.style import Style

from automata import Automata, Calendar
from automata.exceptions import Error

_CALENDAR_CONFIG = """\
calendar:
  collections:
    homeworks:
      dates:
        released: !template "Homework ${ publication.metadata.number } released"
        due:
    labs:
      color: "#123456"
      dates:
        date:
"""

_WEBSITE_CONFIG = """\
website:
  theme:
    use: default
    config: {short_title: T, long_title: Test, rebuild_tailwind: false}
  content_directory: content
  build_directory: _build
course:
  name: Test
  title: Test Course
  term: Winter 2025
  first_week_start: 2025-01-06
"""


def _publication(path: Path, metadata: dict[str, object]) -> None:
    path.mkdir(parents=True)
    (path / "hw.txt").write_text("x")
    lines = ["metadata:"] + [f"  {k}: {v}" for k, v in metadata.items()]
    if not metadata:
        lines = ["metadata: {}"]
    lines += ["artifacts:", "  hw.txt: {}"]
    (path / "publication.yaml").write_text("\n".join(lines) + "\n")


def write_calendar_project(project: Path, calendar_config: str = _CALENDAR_CONFIG):
    """A project with dates in the weeks of Jan 6 and Jan 20, 2025.

    - homeworks hw01: released Mon Jan 6 09:00, due Fri Jan 10 23:59
    - homeworks hw02: released Mon Jan 20 09:00, due Fri Jan 24 23:59
    - labs lab01: date Wed Jan 8; lab02 has no date
    - lectures lec01: date Tue Jan 7 (but lectures aren't in the calendar config)
    """
    project.mkdir(parents=True)
    (project / "automata.yaml").write_text(calendar_config + _WEBSITE_CONFIG)
    (project / "content").mkdir()
    (project / "content" / "index.md").write_text("# Home")

    def collection(name: str, metadata_schema: str) -> Path:
        (project / name).mkdir()
        (project / name / "collection.yaml").write_text(
            "publication_schema:\n"
            "  required_artifacts: [hw.txt]\n"
            "  metadata_schema:\n" + metadata_schema
        )
        return project / name

    homeworks = collection(
        "homeworks",
        "    required_keys:\n"
        "      number: {type: integer}\n"
        "      released: {type: datetime}\n"
        "      due: {type: datetime}\n",
    )
    _publication(
        homeworks / "hw01",
        {"number": 1, "released": "2025-01-06 09:00:00", "due": "2025-01-10 23:59:00"},
    )
    _publication(
        homeworks / "hw02",
        {"number": 2, "released": "2025-01-20 09:00:00", "due": "2025-01-24 23:59:00"},
    )
    labs = collection("labs", "    optional_keys:\n      date: {type: date}\n")
    _publication(labs / "lab01", {"date": "2025-01-08"})
    _publication(labs / "lab02", {})
    lectures = collection("lectures", "    required_keys:\n      date: {type: date}\n")
    _publication(lectures / "lec01", {"date": "2025-01-07"})
    return project


JAN_15 = datetime(2025, 1, 15, 12, 0)


@pytest.fixture
def calendar(tmp_path) -> Calendar:
    project = write_calendar_project(tmp_path / "project")
    return Automata(project).calendar(all_weeks=True, current_time=JAN_15)


def _days_with_entries(calendar):
    return {
        day.date: [entry.label for entry in day.entries]
        for week in calendar.weeks
        for day in week.days
        if day.entries
    }


# the calendar =========================================================================


def test_configured_dates_are_placed_on_their_days(calendar):
    assert _days_with_entries(calendar) == {
        date(2025, 1, 6): ["Homework 1 released"],
        date(2025, 1, 8): ["lab01 date"],
        date(2025, 1, 10): ["hw01 due"],
        date(2025, 1, 20): ["Homework 2 released"],
        date(2025, 1, 24): ["hw02 due"],
    }


def test_weeks_start_on_sunday_and_include_empty_weeks(calendar):
    assert [week.start for week in calendar.weeks] == [
        date(2025, 1, 5),
        date(2025, 1, 12),
        date(2025, 1, 19),
    ]
    assert all(len(week.days) == 7 for week in calendar.weeks)
    assert calendar.day_names == ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def test_weeks_can_start_on_monday(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True, week_start="monday", current_time=JAN_15
    )

    assert [week.start for week in calendar.weeks] == [
        date(2025, 1, 6),
        date(2025, 1, 13),
        date(2025, 1, 20),
    ]
    assert calendar.day_names == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def test_an_unknown_week_start_is_an_error(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    with pytest.raises(Error) as excinfo:
        Automata(project).calendar(
            all_weeks=True, week_start="tuesday", current_time=JAN_15
        )

    assert str(excinfo.value) == (
        'Weeks can start on "sunday" or "monday", not "tuesday".'
    )


def test_all_day_entries_come_first_then_entries_in_order_of_time(tmp_path):
    project = write_calendar_project(tmp_path / "project")
    (project / "labs" / "lab01" / "publication.yaml").write_text(
        "metadata:\n  date: 2025-01-10\nartifacts:\n  hw.txt: {}\n"
    )

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    days = [d for w in calendar.weeks for d in w.days if d.date == date(2025, 1, 10)]
    assert [(e.label, e.all_day) for e in days[0].entries] == [
        ("lab01 date", True),
        ("hw01 due", False),
    ]


def test_entries_know_whether_they_are_past(calendar):
    past = {
        entry.label: entry.past
        for week in calendar.weeks
        for day in week.days
        for entry in day.entries
    }

    assert past["hw01 due"] is True
    assert past["hw02 due"] is False


def test_labels_can_use_vars(tmp_path):
    label = '"${ vars.course } HW${ publication.metadata.number }"'
    config = _CALENDAR_CONFIG.replace(
        "        due:\n", f"        due: !template {label}\n"
    )
    project = write_calendar_project(
        tmp_path / "project", "vars: {course: DSC}\n" + config
    )

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert "DSC HW1" in str(_days_with_entries(calendar))


# filters ==============================================================================


def test_filtering_by_collection(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True, collections=["labs"], current_time=JAN_15
    )

    assert _days_with_entries(calendar) == {date(2025, 1, 8): ["lab01 date"]}
    assert calendar.collections == ["labs"]


def test_filtering_by_key(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True, keys=["due"], current_time=JAN_15
    )

    assert _days_with_entries(calendar) == {
        date(2025, 1, 10): ["hw01 due"],
        date(2025, 1, 24): ["hw02 due"],
    }


def test_filtering_by_dates(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True,
        start=date(2025, 1, 7),
        end=date(2025, 1, 21),
        current_time=JAN_15,
    )

    assert _days_with_entries(calendar) == {
        date(2025, 1, 8): ["lab01 date"],
        date(2025, 1, 10): ["hw01 due"],
        date(2025, 1, 20): ["Homework 2 released"],
    }
    # the weeks shown still start on Sunday
    assert calendar.weeks[0].start == date(2025, 1, 5)


def test_a_collection_not_in_the_calendar_config_is_an_error(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    with pytest.raises(Error) as excinfo:
        Automata(project).calendar(
            all_weeks=True, collections=["lectures"], current_time=JAN_15
        )

    assert str(excinfo.value) == (
        'Collection "lectures" isn\'t in the calendar configuration. The '
        "calendar's collections are: homeworks, labs."
    )


def test_a_calendar_with_no_dates_has_no_weeks(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True, keys=["nothing"], current_time=JAN_15
    )

    assert calendar.weeks == []


# configuration ========================================================================


def test_a_missing_calendar_config_is_an_error(tmp_path):
    project = write_calendar_project(tmp_path / "project", calendar_config="")

    with pytest.raises(Error) as excinfo:
        Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    message = str(excinfo.value)
    assert message.startswith(
        f'{project / "automata.yaml"} has no "calendar" section, which names the '
        f"dates to show: each collection's metadata dates, and events."
    )
    assert "calendar:\n  collections:\n    homeworks:\n      dates:\n" in message
    assert "  events:\n    exams:\n      dates:\n" in message


def test_a_calendar_collection_that_does_not_exist_is_an_error(tmp_path):
    config = _CALENDAR_CONFIG + "    homework:\n      dates:\n        due:\n"
    project = write_calendar_project(tmp_path / "project", config)

    with pytest.raises(Error) as excinfo:
        Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert str(excinfo.value) == (
        f"{project / 'automata.yaml'}:11: calendar.collections.homework: There is no "
        f'collection "homework". The collections are: homeworks, labs, lectures.'
    )


def test_a_key_that_no_publication_has_is_an_error(tmp_path):
    config = _CALENDAR_CONFIG.replace("        due:\n", "        dew:\n")
    project = write_calendar_project(tmp_path / "project", config)

    with pytest.raises(Error) as excinfo:
        Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert str(excinfo.value) == (
        f"{project / 'automata.yaml'}:6: calendar.collections.homeworks.dates.dew: No "
        f'publication in "homeworks" has the metadata key "dew".'
    )


def test_a_value_that_is_not_a_date_is_an_error(tmp_path):
    project = write_calendar_project(tmp_path / "project")
    (project / "labs" / "lab01" / "publication.yaml").write_text(
        "metadata: {date: someday}\nartifacts:\n  hw.txt: {}\n"
    )
    (project / "labs" / "collection.yaml").write_text(
        "publication_schema:\n  required_artifacts: [hw.txt]\n"
        "  metadata_schema:\n    optional_keys:\n      date: {type: string}\n"
    )

    with pytest.raises(Error) as excinfo:
        Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert str(excinfo.value) == (
        f"{project / 'automata.yaml'}:10: calendar.collections.labs.dates.date: In "
        f'publication "lab01", "date" is the string "someday", not a date.'
    )


def test_an_invalid_calendar_config_is_an_error(tmp_path):
    config = "calendar:\n  collections:\n    homeworks:\n      datez:\n        due:\n"
    project = write_calendar_project(tmp_path / "project", config)

    with pytest.raises(Error) as excinfo:
        Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert str(excinfo.value).startswith(f"{project / 'automata.yaml'}:")
    assert "calendar.collections.homeworks" in str(excinfo.value)


# colors ===============================================================================


def test_collections_have_their_configured_color_or_a_palette_color(calendar):
    colors = calendar.colors

    assert colors["labs"] == "#123456"
    assert colors["homeworks"].startswith("#")
    assert colors["homeworks"] != colors["labs"]


def test_colors_do_not_depend_on_filtering(tmp_path):
    project = write_calendar_project(tmp_path / "project")
    automata = Automata(project)

    all_colors = automata.calendar(all_weeks=True, current_time=JAN_15).colors
    homeworks_only = automata.calendar(
        all_weeks=True, collections=["homeworks"], current_time=JAN_15
    )

    assert homeworks_only.colors["homeworks"] == all_colors["homeworks"]


# renderings ===========================================================================


def test_the_calendar_as_a_dict_is_json(calendar):
    data = calendar.to_dict()

    assert json.loads(json.dumps(data)) == data
    assert data["weeks"][0]["start"] == "2025-01-05"
    assert data["weeks"][0]["days"][5]["entries"] == [
        {
            "collection": "homeworks",
            "publication": "hw01",
            "key": "due",
            "label": "hw01 due",
            "when": "2025-01-10T23:59:00",
            "all_day": False,
            "past": True,
            "end": None,
        }
    ]
    assert data["colors"]["labs"] == "#123456"


# the Powerline (Nerd Font) glyphs that round off the ends of a pill
_CAP_LEFT, _CAP_RIGHT = "\ue0b6", "\ue0b4"


def _terminal_text(calendar, width=220):
    console = Console(file=io.StringIO(), width=width, record=True)
    console.print(calendar.rich_table())
    return console.export_text()


def _segment(calendar, text, width=220):
    """The first rendered piece of the terminal calendar containing *text*."""
    console = Console(width=width, color_system="truecolor", force_terminal=True)
    return next(s for s in console.render(calendar.rich_table()) if text in s.text)


def test_the_calendar_renders_in_the_terminal(calendar):
    text = _terminal_text(calendar)

    assert "Mon" in text and "Sun" in text
    assert "Homework 1 released" in text
    assert "23:59" in text


def test_the_calendar_renders_as_an_html_page(calendar):
    html = calendar.to_html()

    assert html.startswith("<!doctype html>")
    assert "Homework 2 released" in html
    assert "#123456" in html


def test_the_calendar_renders_as_an_html_fragment(calendar):
    html = calendar.to_html(standalone=False)

    assert "<html" not in html
    assert "<table" in html
    assert "hw02 due" in html


def test_the_calendar_renders_as_a_pdf(calendar, tmp_path):
    path = tmp_path / "calendar.pdf"

    pages = calendar.write_pdf(path)

    assert pages == 1
    assert path.read_bytes().startswith(b"%PDF")


def test_a_long_calendar_renders_as_a_multi_page_pdf(tmp_path):
    project = write_calendar_project(tmp_path / "project")
    for n in range(3, 40):
        day = f"{datetime(2025, 1, 6) + timedelta(days=3 * n):%Y-%m-%d}"
        _publication(
            project / "homeworks" / f"hw{n:02}",
            {"number": n, "released": f"{day} 09:00:00", "due": f"{day} 23:59:00"},
        )

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert calendar.write_pdf(tmp_path / "calendar.pdf") > 1


# row heights ==========================================================================


def test_every_week_is_as_tall_as_the_busiest(calendar):
    assert calendar.max_entries == 1


def test_html_rows_are_the_same_height(calendar):
    import re

    heights = re.findall(
        r'<tr class="week-row" style="height: ([\d.]+)em">', calendar.to_html()
    )

    assert len(heights) == len(calendar.weeks)
    assert len(set(heights)) == 1


def test_terminal_rows_are_the_same_height(calendar):
    lines = _terminal_text(calendar).splitlines()
    # each week's row is between two separators (the first under the header)
    separators = [i for i, line in enumerate(lines) if line.startswith(("├", "╰"))]
    heights = {b - a for a, b in zip(separators, separators[1:], strict=False)}

    assert len(separators) == len(calendar.weeks) + 1
    assert len(heights) == 1


# which weeks are shown ================================================================


def test_by_default_the_calendar_starts_with_the_current_week(tmp_path):
    # Jan 15 is a Wednesday: its week starts on Sunday Jan 12
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(current_time=JAN_15)

    assert [week.start for week in calendar.weeks] == [
        date(2025, 1, 12),
        date(2025, 1, 19),
    ]
    assert _days_with_entries(calendar) == {
        date(2025, 1, 20): ["Homework 2 released"],
        date(2025, 1, 24): ["hw02 due"],
    }


def test_from_overrides_the_default_start(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(start=date(2025, 1, 1), current_time=JAN_15)

    assert calendar.weeks[0].start == date(2024, 12, 29)


def test_a_calendar_with_no_dates_from_this_week_on_has_no_weeks(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(current_time=datetime(2025, 3, 1))

    assert calendar.weeks == []


# the HTML legend ======================================================================


def test_html_entries_name_their_collection(calendar):
    import re

    html = calendar.to_html()

    assert re.search(r'<div class="entry[^"]*" data-collection="labs"', html)


def test_the_html_legend_toggles_collections(calendar):
    html = calendar.to_html(standalone=False)

    assert (
        '<button type="button" data-collection="homeworks" aria-pressed="true"' in html
    )
    # the script that hides and shows a collection's entries is in the fragment,
    # so that it works when the calendar is embedded in another page
    assert "<script>" in html
    assert "aria-pressed" in html.split("<script>")[1]


# today ================================================================================


def test_today_is_highlighted_by_default(calendar):
    html = calendar.to_html()

    # Jan 15 is today
    assert '<td class="today"><div class="date">Jan 15</div>' in html
    assert ".automata-calendar td.today { background:" in html


def test_highlighting_today_can_be_turned_off(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True, highlight_today=False, current_time=JAN_15
    )

    assert 'class="today"' not in calendar.to_html()
    assert f"{_CAP_LEFT}Jan 15" not in _terminal_text(calendar)


# past days ============================================================================


def test_past_days_are_grayed_out(calendar):
    html = calendar.to_html()

    # Jan 15 is today: Jan 14 is past, Jan 16 isn't
    assert '<td class="past-day"><div class="date">Jan 14</div>' in html
    assert '<td><div class="date">Jan 16</div>' in html
    assert ".automata-calendar td.past-day { background:" in html


def test_past_days_are_grayed_out_even_without_highlighting_today(tmp_path):
    project = write_calendar_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True, highlight_today=False, current_time=JAN_15
    )

    assert '<td class="past-day"><div class="date">Jan 14</div>' in calendar.to_html()


def test_html_week_numbers_are_bold_but_not_their_dates(tmp_path):
    from test_course import _calendar_project

    calendar = Automata(_calendar_project(tmp_path)).calendar(all_weeks=True)
    html = calendar.to_html()

    assert (
        '<th class="week">Week 1<br><span class="week-date">Jan 5</span></th>' in html
    )
    assert ".automata-calendar .week-date { font-weight: normal;" in html


def test_html_labels_are_darker_than_past_days(calendar):
    import re

    html = calendar.to_html()
    # (the light theme's colors, which come first)
    labels = re.search(r"--cal-label: (#\w+);", html)[1]
    past = re.search(r"--cal-past: (#\w+);", html)[1]

    def lightness(color):
        return sum(int(color[i : i + 2], 16) for i in (1, 3, 5))

    assert lightness(labels) < lightness(past)


def test_the_html_page_has_a_light_and_dark_toggle(calendar):
    html = calendar.to_html()

    assert '<button type="button" class="theme-toggle"' in html
    # the choice overrides the system's, in either direction
    assert ':root[data-theme="dark"]' in html
    assert ':root:not([data-theme="light"])' in html
    assert "localStorage" in html


def test_the_html_fragment_has_no_theme_toggle(calendar):
    # an embedded calendar follows its page's theme
    assert "theme-toggle" not in calendar.to_html(standalone=False)


# the terminal =========================================================================


def test_terminal_today_is_a_pill(calendar):
    assert f"{_CAP_LEFT}Jan 15{_CAP_RIGHT}" in _terminal_text(calendar)
    assert _segment(calendar, "Jan 15").style.bgcolor is not None


def test_terminal_past_days_are_dim(calendar):
    assert _segment(calendar, "Jan 14").style.dim
    assert not (_segment(calendar, "Jan 16").style or Style()).dim


def test_terminal_future_entries_are_pills_in_their_collections_color(calendar):
    from rich.color import Color

    segment = _segment(calendar, "Homework 2 released")

    assert segment.style.bgcolor == Color.parse(calendar.colors["homeworks"])
    assert f"{_CAP_LEFT}Homework 2 released" in _terminal_text(calendar)


def test_terminal_past_entries_are_dim_and_not_pills(calendar):
    segment = _segment(calendar, "Homework 1 released")

    assert segment.style.dim
    assert segment.style.bgcolor is None


def test_terminal_entries_are_shortened_at_word_boundaries(calendar):
    import re

    # at this width, "Homework 1 released 09:00" doesn't fit in a column
    text = _segment(calendar, "Homework", width=130).text.strip()

    assert re.fullmatch(r"Homework( \d)?…", text)


# iCalendar ============================================================================


def _events(ics):
    return [block for block in ics.split("BEGIN:VEVENT\r\n")[1:]]


def test_the_calendar_renders_as_icalendar(calendar):
    ics = calendar.to_ics()

    assert ics.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:")
    assert ics.endswith("END:VCALENDAR\r\n")
    assert "X-WR-CALNAME:Test\\, Winter 2025\r\n" in ics
    entries = [e for w in calendar.weeks for d in w.days for e in d.entries]
    assert len(_events(ics)) == len(entries)


def test_icalendar_timed_dates_are_in_utc(calendar):
    from datetime import timezone

    utc = datetime(2025, 1, 6, 9, 0).astimezone(timezone.utc)
    event = next(e for e in _events(calendar.to_ics()) if "hw01/released" in e)

    assert f"DTSTART:{utc:%Y%m%dT%H%M%SZ}\r\n" in event
    assert "SUMMARY:Homework 1 released\r\n" in event


def test_icalendar_dates_without_times_are_all_day(calendar):
    event = next(e for e in _events(calendar.to_ics()) if "lab01/date" in e)

    assert "DTSTART;VALUE=DATE:20250108\r\n" in event
    assert "DTEND;VALUE=DATE:20250109\r\n" in event


def test_icalendar_events_have_stable_ids(calendar, tmp_path):
    # so that a calendar app subscribed to the file updates events when dates
    # change, rather than duplicating them
    event = next(e for e in _events(calendar.to_ics()) if "lab01" in e)

    assert "UID:labs/lab01/date@automata\r\n" in event
    assert "CATEGORIES:labs\r\n" in event


def test_icalendar_text_is_escaped_and_long_lines_are_folded(tmp_path):
    label = "Lab: setup, tools; and a label long enough that its line must be folded"
    config = _CALENDAR_CONFIG.replace("        date:\n", f'        date: "{label}"\n')
    project = write_calendar_project(tmp_path / "project", config)

    ics = Automata(project).calendar(all_weeks=True, current_time=JAN_15).to_ics()

    lines = ics.split("\r\n")
    assert all(len(line.encode()) <= 75 for line in lines)
    unfolded = ics.replace("\r\n ", "")
    assert f"SUMMARY:{label.replace(',', '\\,').replace(';', '\\;')}\r\n" in unfolded


# standalone events ====================================================================

_EVENTS_CONFIG = """\
  events:
    exams:
      color: "#e15759"
      dates:
        - label: Midterm
          date: 2025-01-14
        - label: Final
          date: ${ vars.final } at 08:00:00
    holidays:
      dates:
        - label: Break
          date: 2025-01-16
          end: 2025-01-17
"""


def write_events_project(project: Path, events: str = _EVENTS_CONFIG) -> Path:
    """The calendar project, with exams on Jan 14 and Jan 23 (08:00), and a
    break from Jan 16 through Jan 17."""
    return write_calendar_project(
        project, "vars: {final: 2025-01-23}\n" + _CALENDAR_CONFIG + events
    )


def _entries(calendar):
    return [e for w in calendar.weeks for d in w.days for e in d.entries]


def _event_error(tmp_path, events: str) -> str:
    project = write_events_project(tmp_path / "project", events)
    with pytest.raises(Error) as excinfo:
        Automata(project).calendar(all_weeks=True, current_time=JAN_15)
    return str(excinfo.value).replace(str(project / "automata.yaml"), "automata.yaml")


def test_events_are_placed_on_their_days(tmp_path):
    project = write_events_project(tmp_path / "project")

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    days = _days_with_entries(calendar)
    assert days[date(2025, 1, 14)] == ["Midterm"]
    assert days[date(2025, 1, 23)] == ["Final"]
    # a multi-day event is on each of its days
    assert days[date(2025, 1, 16)] == ["Break"]
    assert days[date(2025, 1, 17)] == ["Break"]


def test_events_are_all_day_unless_given_a_time(tmp_path):
    project = write_events_project(tmp_path / "project")

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    entries = {e.label: e for e in _entries(calendar)}
    assert entries["Midterm"].all_day is True
    assert entries["Final"].all_day is False
    assert entries["Final"].when == datetime(2025, 1, 23, 8, 0)
    assert entries["Final"].text == "Final 08:00"


def test_event_entries_belong_to_their_group_and_no_publication(tmp_path):
    project = write_events_project(tmp_path / "project")

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    midterm = next(e for e in _entries(calendar) if e.label == "Midterm")
    assert (midterm.collection, midterm.publication, midterm.key) == (
        "exams",
        None,
        None,
    )
    assert midterm.past is True
    assert midterm.to_dict()["publication"] is None


def test_a_multi_day_event_is_past_only_after_its_last_day(tmp_path):
    project = write_events_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True, current_time=datetime(2025, 1, 17, 12, 0)
    )

    assert all(not e.past for e in _entries(calendar) if e.label == "Break")


def test_event_dates_can_be_phrases(tmp_path):
    events = (
        "  events:\n    exams:\n      dates:\n"
        "        - {label: Quiz, date: first monday after 2025-01-01}\n"
    )
    project = write_events_project(tmp_path / "project", events)

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    # (all-day, so before the homework's release at 09:00)
    assert _days_with_entries(calendar)[date(2025, 1, 6)] == [
        "Quiz",
        "Homework 1 released",
    ]


def test_event_labels_can_be_templates(tmp_path):
    events = (
        "  events:\n    exams:\n      dates:\n"
        '        - label: !template "${ course.name } Midterm"\n'
        "          date: 2025-01-14\n"
    )
    project = write_events_project(tmp_path / "project", events)

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert _days_with_entries(calendar)[date(2025, 1, 14)] == ["Test Midterm"]


def test_a_calendar_can_have_only_events(tmp_path):
    project = write_calendar_project(
        tmp_path / "project",
        "calendar:\n  events:\n    exams:\n      dates:\n"
        "        - {label: Midterm, date: 2025-01-14}\n",
    )

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert _days_with_entries(calendar) == {date(2025, 1, 14): ["Midterm"]}
    assert calendar.collections == ["exams"]


def test_event_groups_are_shown_and_colored_like_collections(tmp_path):
    project = write_events_project(tmp_path / "project")

    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert calendar.collections == ["exams", "holidays", "homeworks", "labs"]
    assert calendar.colors["exams"] == "#e15759"
    assert calendar.colors["holidays"].startswith("#")
    assert len(set(calendar.colors.values())) == 4


def test_filtering_by_an_event_group(tmp_path):
    project = write_events_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True, collections=["holidays"], current_time=JAN_15
    )

    assert _days_with_entries(calendar) == {
        date(2025, 1, 16): ["Break"],
        date(2025, 1, 17): ["Break"],
    }


def test_filtering_by_key_leaves_out_events(tmp_path):
    project = write_events_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True, keys=["due"], current_time=JAN_15
    )

    assert {e.label for e in _entries(calendar)} == {"hw01 due", "hw02 due"}


def test_filtering_by_dates_keeps_the_days_of_a_multi_day_event_in_range(tmp_path):
    project = write_events_project(tmp_path / "project")

    calendar = Automata(project).calendar(
        all_weeks=True,
        start=date(2025, 1, 17),
        end=date(2025, 1, 17),
        current_time=JAN_15,
    )

    assert _days_with_entries(calendar) == {date(2025, 1, 17): ["Break"]}


def test_an_event_is_one_icalendar_event_even_over_several_days(tmp_path):
    project = write_events_project(tmp_path / "project")
    calendar = Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    breaks = [e for e in _events(calendar.to_ics()) if "SUMMARY:Break" in e]

    assert len(breaks) == 1
    assert "DTSTART;VALUE=DATE:20250116\r\n" in breaks[0]
    assert "DTEND;VALUE=DATE:20250118\r\n" in breaks[0]
    assert "UID:holidays/0@automata\r\n" in breaks[0]
    assert "CATEGORIES:holidays\r\n" in breaks[0]


def test_html_event_entries_name_their_group(tmp_path):
    project = write_events_project(tmp_path / "project")

    html = Automata(project).calendar(all_weeks=True, current_time=JAN_15).to_html()

    assert 'data-collection="exams"' in html
    assert 'title="exams"' in html


def test_the_old_calendar_shape_is_an_error(tmp_path):
    config = "calendar:\n  homeworks:\n    dates:\n      due:\n"
    project = write_calendar_project(tmp_path / "project", config)

    with pytest.raises(Error) as excinfo:
        Automata(project).calendar(all_weeks=True, current_time=JAN_15)

    assert str(excinfo.value) == (
        f"{project / 'automata.yaml'}:2: calendar.homeworks: Unknown key "
        f'"homeworks". The calendar has "collections" (whose metadata dates to '
        f'show) and "events" (dates of their own).'
    )


def test_an_event_group_named_like_a_collection_is_an_error(tmp_path):
    events = (
        "  events:\n    labs:\n      dates:\n        - {label: X, date: 2025-01-14}\n"
    )

    assert _event_error(tmp_path, events) == (
        "automata.yaml:13: calendar.events.labs: The calendar has both a collection "
        'and an event group named "labs".'
    )


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (
            "{date: 2025-01-14}",
            'calendar.events.exams.dates.0: Expected "label" and "date" (and '
            'optionally "end"), but there is no "label".',
        ),
        (
            "{label: X, date: 2025-01-14, time: noon}",
            'calendar.events.exams.dates.0.time: Unknown key "time". An event has '
            '"label", "date" and, optionally, "end".',
        ),
        (
            "{label: X, date: someday}",
            'calendar.events.exams.dates.0.date: Cannot read "someday" as a date',
        ),
        (
            "{label: X, date: 2025-01-14, end: 2025-01-13}",
            "calendar.events.exams.dates.0.end: The event ends (2025-01-13) before "
            "it starts (2025-01-14).",
        ),
        (
            '{label: X, date: "2025-01-14 09:00:00", end: 2025-01-15}',
            "calendar.events.exams.dates.0.end: An event with an end is all-day, "
            'but "date" has a time.',
        ),
    ],
)
def test_an_invalid_event_is_an_error(tmp_path, event, expected):
    events = f"  events:\n    exams:\n      dates:\n        - {event}\n"

    assert expected in _event_error(tmp_path, events)


def test_event_dates_must_be_a_list(tmp_path):
    events = "  events:\n    exams:\n      dates:\n        midterm: 2025-01-14\n"

    assert _event_error(tmp_path, events).endswith(
        "calendar.events.exams.dates: Expected a list of events, each with a "
        '"label" and a "date", but got a dict.'
    )
