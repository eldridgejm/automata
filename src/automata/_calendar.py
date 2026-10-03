"""A week-by-week calendar of the dates in the materials' metadata.

Which dates are shown is configured in the ``calendar`` section of
``automata.yaml``: for each collection, the metadata keys whose dates to show,
each with an optional label, and optionally the collection's color::

    calendar:
      homeworks:
        dates:
          released: !template "Homework ${ publication.metadata.number } released"
          due:
        color: "#e15759"

The calendar is made from the materials' metadata only, so it builds nothing,
and it works with discovered or exported materials alike. It renders as a table
in the terminal (with rich), as HTML (a page, or a fragment to embed), and as a
PDF.
"""

from __future__ import annotations

import dataclasses
import datetime
import fnmatch
import html
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import smartconfig.exceptions

from .config import course_week_number
from .exceptions import Error
from .materials import Universe
from .util.resolution import (
    describe_config_error,
    local_time,
    resolve,
    unwrap_templates,
)
from .util.yaml import SourceMap

# colors for collections without one configured, assigned in sorted order
# (Tableau 10)
PALETTE = (
    "#4e79a7",
    "#f28e2b",
    "#59a14f",
    "#e15759",
    "#b07aa1",
    "#76b7b2",
    "#edc948",
    "#ff9da7",
    "#9c755f",
    "#bab0ac",
)

# day names, Monday first (as datetime.date.weekday() numbers them)
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# the days weeks can start on, and their weekday() numbers
WEEK_STARTS = {"sunday": 6, "monday": 0}

_EXAMPLE = """calendar:
  homeworks:
    dates:
      due:
      released: !template "Homework ${ publication.metadata.number } released"
"""


@dataclasses.dataclass
class CalendarEntry:
    """A date from a publication's metadata, on the calendar.

    Attributes
    ----------
    collection, publication : str
        The keys of the publication and its collection.
    key : str
        The metadata key the date is under, e.g. ``"due"``.
    label : str
        The configured label (e.g. "Homework 1 due"), or "<publication> <key>".
    when : datetime.datetime
        The date and time (midnight, for an all-day entry).
    all_day : bool
        Whether the metadata value is a date (rather than a date and time).
    past : bool
        Whether it is before the calendar's current time (or, for an all-day
        entry, before its day).

    """

    collection: str
    publication: str
    key: str
    label: str
    when: datetime.datetime
    all_day: bool
    past: bool

    @property
    def time(self) -> str | None:
        """The time, as HH:MM, or None if it is all-day or at midnight."""
        if self.all_day or self.when.time() == datetime.time(0, 0):
            return None
        return f"{self.when:%H:%M}"

    @property
    def text(self) -> str:
        """The label, with the time unless it is all-day or at midnight."""
        return self.label if self.time is None else f"{self.label} {self.time}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection": self.collection,
            "publication": self.publication,
            "key": self.key,
            "label": self.label,
            "when": self.when.isoformat(),
            "all_day": self.all_day,
            "past": self.past,
        }


@dataclasses.dataclass
class CalendarDay:
    """A day of the calendar: its all-day entries, then the others by time."""

    date: datetime.date
    entries: list[CalendarEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclasses.dataclass
class CalendarWeek:
    """A week of the calendar, from its first day (Sunday or Monday)."""

    start: datetime.date
    days: list[CalendarDay]
    # the course week number, or None before the course's first week
    number: int | None = None

    @property
    def label(self) -> str:
        """e.g. "Week 3, Jan 19", or "Jan 19" for a week before the first."""
        date = f"{self.start:%b} {self.start.day}"
        return date if self.number is None else f"Week {self.number}, {date}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "number": self.number,
            "days": [day.to_dict() for day in self.days],
        }


@dataclasses.dataclass
class Calendar:
    """A week-by-week calendar of the dates in the materials' metadata.

    Attributes
    ----------
    current_time : datetime.datetime
        The time the calendar is for (it decides which entries are past).
    weeks : list[CalendarWeek]
        Every week from the first entry to the last (or the requested dates),
        including weeks without entries.
    collections : list[str]
        The collections shown, sorted.
    colors : dict[str, str]
        A color (``"#rrggbb"``) for each collection shown: the configured one,
        or one from a palette, which doesn't change with filtering.
    week_start : str
        The day weeks start on: ``"sunday"`` or ``"monday"``.

    """

    current_time: datetime.datetime
    weeks: list[CalendarWeek]
    collections: list[str]
    colors: dict[str, str]
    week_start: str = "sunday"
    # e.g. "DSC 40B, Fall 2026"
    title: str = "Calendar"
    # whether the renderings highlight today
    highlight_today: bool = True
    # the dates the calendar is limited to, if any: by default, it starts with
    # the current week
    start: datetime.date | None = None
    end: datetime.date | None = None

    @property
    def today(self) -> datetime.date | None:
        """The day to highlight: today, unless highlighting it is turned off."""
        return self.current_time.date() if self.highlight_today else None

    @property
    def max_entries(self) -> int:
        """The most entries on any one day: every week's row is drawn tall
        enough for this many, so that all rows have the same height."""
        return max(
            (len(day.entries) for week in self.weeks for day in week.days), default=0
        )

    @property
    def day_names(self) -> list[str]:
        """The names of the days of a week, in order, e.g. ``["Sun", "Mon", ...]``."""
        first = WEEK_STARTS[self.week_start]
        return [DAY_NAMES[(first + i) % 7] for i in range(7)]

    def to_dict(self) -> dict[str, Any]:
        """The calendar as JSON-ready data."""
        return {
            "title": self.title,
            "current_time": self.current_time.isoformat(),
            "collections": self.collections,
            "colors": self.colors,
            "week_start": self.week_start,
            "weeks": [week.to_dict() for week in self.weeks],
        }

    def rich_table(self) -> Any:
        """The calendar as a rich renderable (a table and a legend)."""
        return _rich_table(self)

    def to_html(self, standalone: bool = True) -> str:
        """The calendar as HTML: a whole page, or (if not *standalone*) a
        fragment to embed in a page that styles it."""
        return _html(self, standalone)

    def write_pdf(self, path: Path) -> int:
        """Write the calendar to a PDF at *path*. Returns the number of pages."""
        return _write_pdf(self, path)


# making the calendar ==================================================================


def _describe(value: Any) -> str:
    if isinstance(value, str):
        return f'the string "{value}"'
    return f"a {type(value).__name__}"


class _ConfigErrors:
    """Errors in the calendar configuration, located in automata.yaml."""

    def __init__(self, config_path: Path, source_map: SourceMap | None):
        self.config_path = config_path
        self.source_map = source_map

    def __call__(self, reason: str, *keypath: str) -> Error:
        return Error(
            describe_config_error(
                reason,
                ("calendar", *keypath),
                file=self.config_path,
                source_map=self.source_map,
            )
        )


def _check_config(config: Mapping[str, Any], error: _ConfigErrors) -> None:
    """Check the shape of the calendar configuration."""
    for name, entry in config.items():
        if not isinstance(entry, Mapping):
            raise error(
                f'Expected a mapping with "dates" (and optionally "color"), but got '
                f"{_describe(entry)}.",
                name,
            )
        for key in entry:
            if key not in ("dates", "color"):
                raise error(
                    f'Unknown key "{key}". A collection has "dates" (the metadata '
                    f'keys whose dates to show) and, optionally, "color".',
                    name,
                    key,
                )
        dates = entry.get("dates")
        if not isinstance(dates, Mapping) or not dates:
            raise error(
                "Expected a mapping of metadata keys (whose dates to show) to "
                f"labels, but got {_describe(dates) if dates is not None else 'none'}.",
                name,
                "dates",
            )
        color = entry.get("color")
        if color is not None and not (
            isinstance(color, str)
            and len(color) == 7
            and color.startswith("#")
            and all(c in "0123456789abcdefABCDEF" for c in color[1:])
        ):
            raise error(
                f'Expected a color like "#4e79a7", but got {_describe(color)}.',
                name,
                "color",
            )


def make_calendar(
    materials: Universe[Any],
    config: Mapping[str, Any],
    current_time: datetime.datetime,
    vars: Mapping[str, Any] | None = None,
    collections: Sequence[str] | None = None,
    keys: Sequence[str] | None = None,
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    week_start: str = "sunday",
    all_weeks: bool = False,
    highlight_today: bool = True,
    course: Mapping[str, Any] | None = None,
    config_path: Path = Path("automata.yaml"),
    source_map: SourceMap | None = None,
) -> Calendar:
    """The calendar of the dates in the *materials*' metadata.

    Parameters
    ----------
    materials : Universe
        The materials (discovered or exported: only metadata is used).
    config : Mapping[str, Any]
        The ``calendar`` section of ``automata.yaml``.
    current_time : datetime.datetime
        The time that decides which entries are past.
    vars : Mapping[str, Any] | None
        The variables available to labels as ``vars``.
    collections : Sequence[str] | None
        Show only these collections (from the configuration). If None, all are.
    keys : Sequence[str] | None
        Show only dates under metadata keys matching one of these glob patterns
        (e.g. ``"due"``). If None, all configured keys are shown.
    start, end : datetime.date | None
        Show only entries on or after *start* and on or before *end*. Unless
        *all_weeks*, *start* is by default the first day of the current week.
    all_weeks : bool
        Show every week, not just the current one and later ones (when no
        *start* is given).
    highlight_today : bool
        Whether the renderings highlight today.
    week_start : str
        The day weeks start on: ``"sunday"`` (the default) or ``"monday"``.
    course : Mapping[str, Any] | None
        The course (see :func:`automata.config.course_variables`): it titles the
        calendar and numbers its weeks, and labels can use it.
    config_path, source_map
        Where the configuration was read from, to locate errors in it.

    Raises
    ------
    automata.exceptions.Error
        If the configuration is missing or invalid, names a collection that
        doesn't exist or a key no publication has, or a value isn't a date.

    """
    if week_start not in WEEK_STARTS:
        raise Error(f'Weeks can start on "sunday" or "monday", not "{week_start}".')
    error = _ConfigErrors(config_path, source_map)
    if not config:
        raise Error(
            f'{config_path} has no "calendar" section, which names, for each '
            f"collection, the metadata dates to show. For example:\n\n{_EXAMPLE}\n"
            f'shows each homework\'s due date (labeled like "hw01 due") and its '
            f"release date (labeled by the template)."
        )
    _check_config(config, error)

    existing = sorted(
        name
        for name, collection in materials.collections.items()
        if collection.publications
    )
    for name in config:
        if name not in materials.collections:
            raise error(
                f'There is no collection "{name}". The collections are: '
                f"{', '.join(existing)}.",
                name,
            )
    for name in collections or ():
        if name not in config:
            raise Error(
                f'Collection "{name}" isn\'t in the calendar configuration. The '
                f"calendar's collections are: {', '.join(sorted(config))}."
            )

    palette = iter(PALETTE * (1 + len(config) // len(PALETTE)))
    all_colors = {
        name: config[name].get("color") or next(palette) for name in sorted(config)
    }

    current_time = local_time(current_time)
    if start is None and not all_weeks:
        # by default, from the current week on
        start = _week_of(current_time.date(), WEEK_STARTS[week_start])
    entries = []
    for name in sorted(config):
        if collections is not None and name not in collections:
            continue
        publications = materials.collections[name].publications
        for key, label in config[name]["dates"].items():
            if not any(key in p.metadata for p in publications.values()):
                raise error(
                    f'No publication in "{name}" has the metadata key "{key}".',
                    name,
                    "dates",
                    key,
                )
            if keys is not None and not any(fnmatch.fnmatchcase(key, k) for k in keys):
                continue
            for publication_key, publication in publications.items():
                entry = _entry(
                    name,
                    publication_key,
                    publication,
                    key,
                    label,
                    {"vars": vars or {}, "course": course or {}},
                    current_time,
                    error,
                )
                if entry is None:
                    continue
                day = entry.when.date()
                if (start is None or day >= start) and (end is None or day <= end):
                    entries.append(entry)
    entries.sort(key=lambda e: (e.when.date(), not e.all_day, e.when, e.label))

    shown = sorted(collections) if collections is not None else sorted(config)
    weeks = _weeks(entries, start, end, WEEK_STARTS[week_start])
    title = "Calendar"
    if course:
        title = f"{course['name']}, {course['term']}"
        for week in weeks:
            # the course week containing the middle of this week (the two may
            # start on different days)
            week.number = course_week_number(
                course["first_week_start"],
                course["first_week_number"],
                week.start + datetime.timedelta(days=3),
            )
    return Calendar(
        current_time=current_time,
        weeks=weeks,
        collections=shown,
        colors={name: all_colors[name] for name in shown},
        week_start=week_start,
        title=title,
        highlight_today=highlight_today,
        start=start,
        end=end,
    )


def _entry(
    collection: str,
    publication_key: str,
    publication: Any,
    key: str,
    label: Any,
    variables: Mapping[str, Any],
    current_time: datetime.datetime,
    error: _ConfigErrors,
) -> CalendarEntry | None:
    """The entry for a publication's date under *key*, or None if it has none."""
    value = publication.metadata.get(key)
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        when, all_day = local_time(value), False
        past = when < current_time
    elif isinstance(value, datetime.date):
        when, all_day = datetime.datetime.combine(value, datetime.time()), True
        past = value < current_time.date()
    else:
        raise error(
            f'In publication "{publication_key}", "{key}" is {_describe(value)}, '
            f"not a date.",
            collection,
            "dates",
            key,
        )

    if label is None:
        text = f"{publication_key} {key}"
    else:
        try:
            text = str(
                resolve(
                    unwrap_templates(label),
                    {"type": "string"},
                    global_variables={**variables, "publication": publication},
                )
            )
        except smartconfig.exceptions.ResolutionError as e:
            raise error(
                f'In publication "{publication_key}": {e.reason}',
                collection,
                "dates",
                key,
            ) from None

    return CalendarEntry(
        collection=collection,
        publication=publication_key,
        key=key,
        label=text,
        when=when,
        all_day=all_day,
        past=past,
    )


def _week_of(day: datetime.date, first_weekday: int) -> datetime.date:
    """The first day of *day*'s week, for weeks starting on *first_weekday*."""
    return day - datetime.timedelta(days=(day.weekday() - first_weekday) % 7)


def _weeks(
    entries: list[CalendarEntry],
    start: datetime.date | None,
    end: datetime.date | None,
    first_weekday: int,
) -> list[CalendarWeek]:
    """The weeks from the first entry (or *start*) to the last (or *end*)."""
    if not entries and (start is None or end is None):
        return []
    first = start or entries[0].when.date()
    last = end or entries[-1].when.date()

    by_date: dict[datetime.date, list[CalendarEntry]] = {}
    for entry in entries:
        by_date.setdefault(entry.when.date(), []).append(entry)

    weeks = []
    week = _week_of(first, first_weekday)
    while week <= last:
        days = [week + datetime.timedelta(days=i) for i in range(7)]
        weeks.append(
            CalendarWeek(
                start=week,
                days=[CalendarDay(day, by_date.get(day, [])) for day in days],
            )
        )
        week += datetime.timedelta(weeks=1)
    return weeks


# the terminal =========================================================================


# the Powerline (Nerd Font) glyphs that round off the ends of a pill
_CAP_LEFT, _CAP_RIGHT = "\ue0b6", "\ue0b4"
_TERMINAL_ACCENT = "#6366f1"


def _shorten(text: str, fits: Callable[[str], bool], ellipsis: str = "...") -> str:
    """*text*, shortened with *ellipsis* if needed so that it *fits*: by whole
    words, unless even its first word doesn't fit."""
    if fits(text):
        return text
    words = text.split(" ")
    while len(words) > 1:
        words.pop()
        shortened = " ".join(words).rstrip(":,;-") + ellipsis
        if fits(shortened):
            return shortened
    while text and not fits(text + ellipsis):
        text = text[:-1]
    return text + ellipsis


def _on(color: str) -> str:
    """Black or white: whichever is more legible on *color*."""

    def luminance(c: int) -> float:
        c_ = c / 255
        return c_ / 12.92 if c_ <= 0.04045 else ((c_ + 0.055) / 1.055) ** 2.4

    r, g, b = (luminance(c) for c in _rgb(color))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#000000" if (lum + 0.05) / 0.05 > 1.05 / (lum + 0.05) else "#ffffff"


def _terminal_pill(text: str, color: str, bold: bool = False) -> Any:
    """*text* on a pill of *color*, its ends rounded off by Powerline caps."""
    from rich.style import Style
    from rich.text import Text

    return Text.assemble(
        (_CAP_LEFT, Style(color=color)),
        (text, Style(color=_on(color), bgcolor=color, bold=bold)),
        (_CAP_RIGHT, Style(color=color)),
        no_wrap=True,
    )


class _TerminalEntry:
    """An entry in the terminal: a pill in its collection's color (or, if it's
    past, dim text after a dot of it), shortened to fit its column."""

    # the width of what surrounds the label: the caps, or the dot and a space
    _EXTRA = 2

    def __init__(self, entry: CalendarEntry, color: str):
        self.entry, self.color = entry, color
        self.time = f" {entry.time}" if entry.time else ""

    def __rich_measure__(self, console: Any, options: Any) -> Any:
        from rich.cells import cell_len
        from rich.measure import Measurement

        full = self._EXTRA + cell_len(self.entry.label + self.time)
        return Measurement(min(full, self._EXTRA + 4), full)

    def __rich_console__(self, console: Any, options: Any) -> Any:
        from rich.cells import cell_len
        from rich.style import Style
        from rich.text import Text

        time = self.time
        room = options.max_width - self._EXTRA
        if cell_len(self.entry.label + time) > room:
            # drop the time if the whole label then fits, or if keeping it would
            # leave the label less than a word or so
            if cell_len(self.entry.label) <= room or room - cell_len(time) < 8:
                time = ""
        room -= cell_len(time)
        label = _shorten(self.entry.label, lambda t: cell_len(t) <= room, "…")

        if self.entry.past:
            yield Text.assemble(
                ("● ", Style(color=self.color, dim=True)),
                (label, Style(dim=True)),
                (time, Style(dim=True)),
                no_wrap=True,
            )
            return
        pill = Style(color=_on(self.color), bgcolor=self.color)
        yield Text.assemble(
            (_CAP_LEFT, Style(color=self.color)),
            (label, pill),
            (time, pill),
            (_CAP_RIGHT, Style(color=self.color)),
            no_wrap=True,
        )


def _rich_table(calendar: Calendar) -> Any:
    from rich import box
    from rich.console import Group
    from rich.table import Table
    from rich.text import Text

    today = calendar.today
    table = Table(
        box=box.ROUNDED,
        show_lines=True,
        expand=True,
        border_style="bright_black",
        header_style="bold",
        title=calendar.title,
        title_style="bold",
        title_justify="left",
        caption=f"As of {calendar.current_time:%Y-%m-%d %H:%M}",
        caption_style="dim",
        caption_justify="left",
    )
    table.add_column("Week", no_wrap=True)
    for name in calendar.day_names:
        table.add_column(name, ratio=1)

    for week in calendar.weeks:
        cells = []
        for day in week.days:
            date = f"{day.date:%b} {day.date.day}"
            if day.date == today:
                heading = _terminal_pill(date, _TERMINAL_ACCENT, bold=True)
            elif day.date < calendar.current_time.date():
                heading = Text(date, style="dim")
            else:
                heading = Text(date)
            entries = [
                _TerminalEntry(entry, calendar.colors[entry.collection])
                for entry in day.entries
            ]
            # pad the cell, so that every row has the same height
            padding = [Text("")] * (calendar.max_entries - len(day.entries))
            cells.append(Group(heading, *entries, *padding))
        number, _, date = week.label.rpartition(", ")
        label = Text.assemble((number, "bold"), "\n" if number else "", (date, "dim"))
        table.add_row(label, *cells)

    legend = Text("  ").join(
        _terminal_pill(name, calendar.colors[name]) for name in calendar.collections
    )
    return Group(table, legend)


# HTML =================================================================================

# the colors are tokens, so that dark mode only has to redefine them
_STYLE = """
:root {
  --cal-page: #f6f7f9; --cal-cell: #ffffff; --cal-text: #1e293b;
  --cal-muted: #64748b; --cal-faint: #94a3b8;
  --cal-line: #e2e8f0; --cal-frame: #cbd5e1;
  /* the labels (days and weeks): slate, darker than past days' neutral gray */
  --cal-label: #e9eef4; --cal-label-text: #475569;
  --cal-past: #f5f6f8; --cal-today: #eef2ff; --cal-accent: #4f46e5;
  --cal-on-accent: #ffffff; color-scheme: light;
}
"""

# the dark theme's colors: used when the system is dark (unless the viewer chose
# light), or when the viewer chose dark
_DARK = """
  --cal-page: #0b0f17; --cal-cell: #111827; --cal-text: #e2e8f0;
  --cal-muted: #94a3b8; --cal-faint: #64748b;
  --cal-line: #1f2937; --cal-frame: #334155;
  --cal-label: #1a2232; --cal-label-text: #cbd5e1;
  --cal-past: #0d131e; --cal-today: #191c35; --cal-accent: #818cf8;
  --cal-on-accent: #0b0f17;
  color-scheme: dark;
"""

_STYLE += f"""
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{{_DARK}}}
}}
:root[data-theme="dark"] {{{_DARK}}}
"""

_STYLE += """
body { margin: 0; background: var(--cal-page); color: var(--cal-text);
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1280px; margin: 0 auto; padding: 32px 24px 48px; }
h1 { font-size: 1.6rem; font-weight: 650; letter-spacing: -0.01em;
  margin: 0 0 4px; }
.as-of { color: var(--cal-muted); font-size: 0.9rem; margin: 0 0 20px; }
.page-header { display: flex; justify-content: space-between;
  align-items: flex-start; gap: 16px; }
.theme-toggle { display: grid; place-items: center; width: 36px; height: 36px;
  padding: 0; border: 1px solid var(--cal-line); border-radius: 50%;
  background: var(--cal-cell); color: var(--cal-muted); cursor: pointer; }
.theme-toggle:hover { background: var(--cal-label); color: var(--cal-text); }
.theme-toggle:focus-visible { outline: 2px solid var(--cal-accent);
  outline-offset: 2px; }
.theme-toggle svg { width: 18px; height: 18px; }
.automata-calendar { font-variant-numeric: tabular-nums; }
.automata-calendar table { width: 100%; table-layout: fixed;
  border-collapse: separate; border-spacing: 0; overflow: hidden;
  border: 1px solid var(--cal-frame); border-radius: 12px;
  background: var(--cal-cell);
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.05), 0 6px 20px rgb(15 23 42 / 0.05); }
.automata-calendar th, .automata-calendar td { vertical-align: top;
  padding: 6px; text-align: left; border-right: 1px solid var(--cal-line);
  border-bottom: 1px solid var(--cal-line); }
.automata-calendar tr > :last-child { border-right: none; }
.automata-calendar tbody tr:last-child > * { border-bottom: none; }
.automata-calendar th { background: var(--cal-label);
  color: var(--cal-label-text); }
.automata-calendar thead th { font-size: 0.7rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.08em; text-align: center;
  padding: 9px 6px; border-bottom-color: var(--cal-frame); }
.automata-calendar .week { width: 5.5em; white-space: nowrap;
  border-right-color: var(--cal-frame); }
.automata-calendar tbody th.week { font-size: 0.8rem; font-weight: 650;
  color: var(--cal-text); padding: 8px 10px; line-height: 1.4; }
.automata-calendar .week-date { font-weight: normal; color: var(--cal-muted);
  font-size: 0.75rem; }
.automata-calendar .date { display: inline-block; font-size: 0.72rem;
  font-weight: 500; color: var(--cal-muted); padding: 1px 4px;
  margin-bottom: 2px; }
.automata-calendar td.past-day { background: var(--cal-past); }
.automata-calendar td.past-day .date { color: var(--cal-faint); }
.automata-calendar td.today { background: var(--cal-today); }
.automata-calendar td.today .date { background: var(--cal-accent);
  color: var(--cal-on-accent); font-weight: 650; padding: 1px 8px;
  border-radius: 999px; }
.automata-calendar .entry { display: flex; gap: 6px; align-items: baseline;
  margin-top: 3px; padding: 3px 6px; border-radius: 6px;
  border-left: 3px solid var(--color);
  background: color-mix(in srgb, var(--color) 14%, var(--cal-cell));
  font-size: 0.78rem; line-height: 1.3; }
.automata-calendar .entry[hidden] { display: none; }
.automata-calendar .entry:hover {
  background: color-mix(in srgb, var(--color) 24%, var(--cal-cell)); }
.automata-calendar .entry .label { flex: 1; min-width: 0;
  overflow-wrap: break-word; }
.automata-calendar .entry .time { color: var(--cal-muted); font-size: 0.7rem;
  white-space: nowrap; }
.automata-calendar .entry.past { opacity: 0.55; }
.automata-calendar .legend { display: flex; flex-wrap: wrap; gap: 8px;
  align-items: center; margin: 0 0 14px; }
.automata-calendar .legend button { display: inline-flex; align-items: center;
  gap: 7px; padding: 4px 12px 4px 10px; border: 1px solid var(--cal-line);
  border-radius: 999px; background: var(--cal-cell); color: inherit;
  font: inherit; font-size: 0.8rem; cursor: pointer;
  transition: opacity 0.15s, background 0.15s; }
.automata-calendar .legend button:hover { background: var(--cal-label); }
.automata-calendar .legend button:focus-visible {
  outline: 2px solid var(--cal-accent); outline-offset: 2px; }
.automata-calendar .legend i { width: 10px; height: 10px; border-radius: 50%;
  background: var(--color); }
.automata-calendar .legend button[aria-pressed="false"] { opacity: 0.5; }
.automata-calendar .legend button[aria-pressed="false"] i {
  background: transparent; box-shadow: inset 0 0 0 2px var(--color); }
.automata-calendar .legend .hint { color: var(--cal-faint); font-size: 0.75rem; }
"""


# clicking a legend item hides (or shows again) its collection's entries. The
# script finds its own calendar, so that several can be on a page.
_SCRIPT = """<script>
(function (calendar) {
  calendar.querySelectorAll(".legend button").forEach(function (button) {
    button.addEventListener("click", function () {
      var shown = button.getAttribute("aria-pressed") !== "true";
      button.setAttribute("aria-pressed", String(shown));
      var name = CSS.escape(button.dataset.collection);
      var selector = '.entry[data-collection="' + name + '"]';
      calendar.querySelectorAll(selector).forEach(function (entry) {
        entry.hidden = !shown;
      });
    });
  });
})(document.currentScript.closest(".automata-calendar"));
</script>
"""


# the standalone page's light/dark toggle. The viewer's choice is remembered
# (where the browser allows it), and restored in the head, before the page is
# drawn, so that it doesn't flash in the other theme.
_THEME_KEY = "automata-calendar-theme"
_RESTORE_THEME = f"""<script>
try {{
  var theme = localStorage.getItem("{_THEME_KEY}");
  if (theme) document.documentElement.dataset.theme = theme;
}} catch (e) {{}}
</script>
"""
_SUN = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 '
    "20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 "
    '6.3l1.4-1.4"/></svg>'
)
_MOON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 '
    '9.8z"/></svg>'
)
_THEME_TOGGLE = f"""<script>
(function (button) {{
  var root = document.documentElement;
  var system = matchMedia("(prefers-color-scheme: dark)");
  function dark() {{
    var theme = root.dataset.theme;
    return theme ? theme === "dark" : system.matches;
  }}
  // the button shows the theme it switches to
  function update() {{
    button.innerHTML = dark() ? '{_SUN}' : '{_MOON}';
    var label = dark() ? "Switch to light mode" : "Switch to dark mode";
    button.setAttribute("aria-label", label);
    button.title = label;
  }}
  button.addEventListener("click", function () {{
    root.dataset.theme = dark() ? "light" : "dark";
    try {{ localStorage.setItem("{_THEME_KEY}", root.dataset.theme); }}
    catch (e) {{}}
    update();
  }});
  system.addEventListener("change", update);
  update();
}})(document.querySelector(".theme-toggle"));
</script>
"""


def _week_header(week: CalendarWeek) -> str:
    """The HTML for a week's label: its number (bold, as a header) and date."""
    date = f'<span class="week-date">{week.start:%b} {week.start.day}</span>'
    if week.number is None:
        return date
    return f"Week {week.number}<br>{date}"


def _html(calendar: Calendar, standalone: bool) -> str:
    e = html.escape
    today = calendar.today
    # every row is as tall as the busiest week's: the date's line, and a line
    # for each entry
    row_height = round(2.0 + 1.8 * calendar.max_entries, 1)
    rows = []
    for week in calendar.weeks:
        cells = []
        for day in week.days:
            entries = "".join(
                f'<div class="entry{" past" if entry.past else ""}" '
                f'data-collection="{e(entry.collection)}" '
                f'style="--color: {calendar.colors[entry.collection]}" '
                f'title="{e(entry.collection)}/{e(entry.publication)}: '
                f'{e(entry.key)}"><span class="label">{e(entry.label)}</span>'
                + (f'<span class="time">{entry.time}</span>' if entry.time else "")
                + "</div>"
                for entry in day.entries
            )
            if day.date == today:
                today_class = ' class="today"'
            elif day.date < calendar.current_time.date():
                today_class = ' class="past-day"'
            else:
                today_class = ""
            cells.append(
                f'<td{today_class}><div class="date">{day.date:%b} {day.date.day}'
                f"</div>{entries}</td>"
            )
        rows.append(
            f'<tr class="week-row" style="height: {row_height}em">'
            f'<th class="week">{_week_header(week)}</th>'
            f"{''.join(cells)}</tr>"
        )

    header = "".join(f"<th>{name}</th>" for name in calendar.day_names)
    # each legend item is a button that hides or shows its collection's entries
    legend = "".join(
        f'<button type="button" data-collection="{e(name)}" aria-pressed="true" '
        f'style="--color: {calendar.colors[name]}"><i></i>{e(name)}</button>'
        for name in calendar.collections
    )
    fragment = (
        '<div class="automata-calendar">\n'
        f'<div class="legend">{legend}'
        '<span class="hint">Click to show or hide</span></div>\n'
        f'<table>\n<thead><tr><th class="week">Week</th>{header}</tr></thead>\n'
        "<tbody>\n" + "\n".join(rows) + f"\n</tbody>\n</table>\n{_SCRIPT}</div>\n"
    )
    if not standalone:
        return fragment
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{e(calendar.title)}</title>\n"
        f"<style>{_STYLE}</style>\n{_RESTORE_THEME}</head>\n<body>\n<main>\n"
        f'<header class="page-header">\n<div>\n<h1>{e(calendar.title)}</h1>\n'
        f'<p class="as-of">As of {calendar.current_time:%Y-%m-%d %H:%M}</p>\n'
        "</div>\n"
        '<button type="button" class="theme-toggle" aria-label="Toggle dark mode">'
        "</button>\n</header>\n"
        f"{fragment}{_THEME_TOGGLE}</main>\n</body>\n</html>\n"
    )


# PDF ==================================================================================


def _latin1(text: str) -> str:
    """*text* in the characters the PDF's built-in fonts have."""
    return text.encode("latin-1", "replace").decode("latin-1")


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _fit(pdf: Any, text: str, width: float) -> str:
    """*text*, shortened with "..." if needed to fit in *width*."""
    return _shorten(_latin1(text), lambda t: pdf.get_string_width(t) <= width)


def _tint(color: str, amount: float) -> tuple[int, int, int]:
    """*color* mixed with white: *amount* of the color, the rest white."""
    r, g, b = (round(255 + (c - 255) * amount) for c in _rgb(color))
    return r, g, b


# the PDF's colors, as in the HTML's (light) style
_TEXT = (30, 41, 59)  # #1e293b
_MUTED = (100, 116, 139)  # #64748b
_FAINT = (148, 163, 184)  # #94a3b8
_LINE = (226, 232, 240)  # #e2e8f0
_FRAME = (203, 213, 225)  # #cbd5e1
_LABEL = (233, 238, 244)  # #e9eef4
_LABEL_TEXT = (71, 85, 105)  # #475569
_PAST_DAY = (245, 246, 248)  # #f5f6f8
_TODAY = (238, 242, 255)  # #eef2ff
_ACCENT = (79, 70, 229)  # #4f46e5

_PILL_HEIGHT = 11


def _pill(pdf: Any, x: float, y: float, width: float, color: str, entry: Any) -> None:
    """An entry: a rounded rectangle tinted with its collection's *color*, with a
    stripe of it at the left, its label, and its time at the right (all fainter,
    if it is past), as the HTML shows it."""
    stripe, past = 2.5, entry.past
    pdf.set_fill_color(*_tint(color, 0.45) if past else _rgb(color))
    pdf.rect(
        x, y, width, _PILL_HEIGHT, style="F", round_corners=True, corner_radius=2.5
    )
    pdf.set_fill_color(*_tint(color, 0.07 if past else 0.15))
    pdf.rect(
        x + stripe,
        y,
        width - stripe,
        _PILL_HEIGHT,
        style="F",
        round_corners=("TOP_RIGHT", "BOTTOM_RIGHT"),
        corner_radius=2.5,
    )
    right = x + width - 3
    if entry.time is not None:
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*(_FAINT if past else _MUTED))
        right -= pdf.get_string_width(entry.time)
        pdf.text(right, y + 7.8, entry.time)
        right -= 3
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*(_FAINT if past else _TEXT))
    left = x + stripe + 3
    pdf.text(left, y + 7.8, _fit(pdf, entry.label, right - left))


def _write_pdf(calendar: Calendar, path: Path) -> int:
    from fpdf import FPDF

    pdf = FPDF(orientation="landscape", unit="pt", format="letter")
    pdf.set_auto_page_break(False)
    margin = 36
    pdf.set_margins(margin, margin, margin)
    page_width = pdf.w - 2 * margin
    week_width = 54
    day_width = (page_width - week_width) / 7
    header_height = 18
    padding = 4
    date_line = 13
    entry_line = 13
    today = calendar.today

    def legend(y: float) -> None:
        """The collections, right-aligned on the title's line."""
        pdf.set_font("Helvetica", "", 8)
        names = [_latin1(name) for name in calendar.collections]
        widths = [pdf.get_string_width(name) + 22 for name in names]
        x = margin + page_width - sum(widths) - 6 * (len(names) - 1)
        for name, width, collection in zip(
            names, widths, calendar.collections, strict=True
        ):
            pdf.set_draw_color(*_LINE)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(x, y, width, 14, style="DF", round_corners=True, corner_radius=7)
            pdf.set_fill_color(*_rgb(calendar.colors[collection]))
            pdf.circle(x + 9, y + 7, 2.5, style="F")
            pdf.set_text_color(*_TEXT)
            pdf.text(x + 15, y + 9.8, name)
            x += width + 6

    def header() -> float:
        """The days' header row; returns the top of the table."""
        top = pdf.get_y()
        pdf.set_fill_color(*_LABEL)
        pdf.rect(margin, top, page_width, header_height, style="F")
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*_LABEL_TEXT)
        pdf.set_char_spacing(0.6)
        pdf.text(margin + padding + 4, top + 11.5, "WEEK")
        for i, name in enumerate(calendar.day_names):
            name = name.upper()
            left = margin + week_width + i * day_width
            center = left + (day_width - pdf.get_string_width(name)) / 2
            pdf.text(center, top + 11.5, name)
        pdf.set_char_spacing(0)
        pdf.set_y(top + header_height)
        return top

    def frame(top: float, bottom: float, row_tops: list[float]) -> None:
        """The table's lines: light ones between the cells, darker ones around
        the labels and the table."""
        pdf.set_line_width(0.5)
        pdf.set_draw_color(*_LINE)
        for row_top in row_tops[1:]:
            pdf.line(margin, row_top, margin + page_width, row_top)
        for i in range(1, 7):
            x = margin + week_width + i * day_width
            pdf.line(x, top + header_height, x, bottom)
        pdf.set_draw_color(*_FRAME)
        pdf.line(margin, top + header_height, margin + page_width, top + header_height)
        pdf.line(margin + week_width, top, margin + week_width, bottom)
        pdf.rect(margin, top, page_width, bottom - top)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*_TEXT)
    pdf.text(margin, margin + 14, _latin1(calendar.title))
    legend(margin + 2)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.text(margin, margin + 30, f"As of {calendar.current_time:%Y-%m-%d %H:%M}")
    pdf.set_y(margin + 42)
    top = header()
    row_tops: list[float] = []

    # every row is as tall as the busiest week's
    height = 2 * padding + date_line + calendar.max_entries * entry_line
    for week in calendar.weeks:
        if pdf.get_y() + height > pdf.h - margin:
            frame(top, pdf.get_y(), row_tops)
            pdf.add_page()
            top, row_tops = header(), []
        row = pdf.get_y()
        row_tops.append(row)

        pdf.set_fill_color(*_LABEL)
        pdf.rect(margin, row, week_width, height, style="F")
        number, _, date = week.label.rpartition(", ")
        pdf.set_text_color(*_TEXT)
        pdf.set_font("Helvetica", "B", 8.5)
        if number:
            pdf.text(margin + padding + 4, row + padding + 9, number)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*_MUTED)
        pdf.text(margin + padding + 4, row + padding + (19 if number else 9), date)

        for i, day in enumerate(week.days):
            left = margin + week_width + i * day_width
            if day.date == today:
                pdf.set_fill_color(*_TODAY)
                pdf.rect(left, row, day_width, height, style="F")
            elif day.date < calendar.current_time.date():
                pdf.set_fill_color(*_PAST_DAY)
                pdf.rect(left, row, day_width, height, style="F")

            date = f"{day.date:%b} {day.date.day}"
            if day.date == today:
                # today: its date on an accent-colored badge
                pdf.set_font("Helvetica", "B", 7)
                width = pdf.get_string_width(date) + 10
                pdf.set_fill_color(*_ACCENT)
                pdf.rect(
                    left + padding,
                    row + padding,
                    width,
                    10,
                    style="F",
                    round_corners=True,
                    corner_radius=4.9,
                )
                pdf.set_text_color(255, 255, 255)
                pdf.text(left + padding + 5, row + padding + 7.3, date)
            else:
                pdf.set_font("Helvetica", "", 7)
                past = day.date < calendar.current_time.date()
                pdf.set_text_color(*(_FAINT if past else _MUTED))
                pdf.text(left + padding + 2, row + padding + 7.3, date)

            for j, entry in enumerate(day.entries):
                _pill(
                    pdf,
                    left + padding,
                    row + padding + date_line + j * entry_line - 1,
                    day_width - 2 * padding,
                    calendar.colors[entry.collection],
                    entry,
                )
        pdf.set_y(row + height)
    frame(top, pdf.get_y(), row_tops)

    pdf.output(str(path))
    return pdf.pages_count
