"""Schedule element for displaying course calendar.

A schedule element renders a week-by-week course calendar showing lectures,
assignments, discussions, and exams. Each week displays its topic and all
associated materials, with resources linked conditionally based on their
release status.

Features
--------
- Week-based organization with configurable topics
- Automatic filtering of materials to their release weeks
- Flexible week ordering: current week first or chronological
- Support for multiple assignment and discussion collections
- Conditional resource links based on artifact/metadata availability
- Optional per-week announcements with urgent styling
- Exam date markers

Schema
------
week_topics (list[str]): List of topic names, one per week. The length
    determines the number of weeks displayed.
first_week_start_date (date): The Monday of the first week.
first_week_number (int, optional): Starting week number. Defaults to 1.
week_order (str, optional): How to order weeks in the display. Options:
    - "this_week_first": Current week first, then future, then past (default).
    - "this_week_last": Chronological order, oldest to newest.
lecture (dict): Configuration for lectures:
    - collection (str): Name of the lecture collection.
    - metadata_key_for_released (str): Metadata key containing release date.
    - title (str): Display title (e.g., "Lecture").
    - resources (list): Resource link definitions (see below).
assignments (list[dict]): List of assignment configurations, each containing:
    - collection (str): Name of the assignment collection.
    - metadata_key_for_released (str): Metadata key for release date.
    - metadata_key_for_due (str | None): Metadata key for due date.
    - title (str): Display title (e.g., "Homework", "Lab").
    - resources (list): Resource link definitions.
discussions (list[dict]): List of discussion configurations, each containing:
    - collection (str): Name of the discussion collection.
    - metadata_key_for_released (str): Metadata key for release date.
    - title (str): Display title (e.g., "Discussion").
    - resources (list): Resource link definitions.
exams (dict[str, date], optional): Mapping of exam names to dates.
week_announcements (list[dict], optional): Per-week announcements:
    - week (int): Week number to display the announcement.
    - content (str): Announcement text (supports markdown).
    - urgent (bool, optional): Style as urgent. Defaults to False.

Resource Definitions
--------------------
Each resource in a ``resources`` list contains:

text (str): Jinja2 template for the link text/content.
title (str, optional): Tooltip text for the link.
key_for_parts (str, optional): Metadata key for multi-part publications.
requires (dict, optional): Conditions for rendering:
    - artifacts (list[str]): Required artifact names.
    - metadata (list[str]): Required metadata keys.
    - non_null_metadata (list[str]): Metadata keys that must be non-null.
    - text_if_missing (str | None): Fallback text if requirements not met.

Example YAML configuration
--------------------------
::

    schedule:
      first_week_start_date: 2024-09-23
      first_week_number: 1
      week_order: this_week_first
      week_topics:
        - Introduction to Python
        - Data Types and Variables
        - Control Flow
        - Functions
      lecture:
        collection: lecture
        metadata_key_for_released: date
        title: Lecture
        resources:
          - text: "[Slides]({{ artifacts['slides.pdf'].path }})"
            requires:
              artifacts: [slides.pdf]
          - text: "[Code]({{ artifacts['code.zip'].path }})"
            requires:
              artifacts: [code.zip]
              text_if_missing: "(no code)"
      assignments:
        - collection: homework
          metadata_key_for_released: released
          metadata_key_for_due: due
          title: Homework
          resources:
            - text: "[PDF]({{ artifacts['homework.pdf'].path }})"
              requires:
                artifacts: [homework.pdf]
        - collection: lab
          metadata_key_for_released: released
          metadata_key_for_due: due
          title: Lab
          resources:
            - text: "[Instructions]({{ artifacts['lab.pdf'].path }})"
              requires:
                artifacts: [lab.pdf]
      discussions:
        - collection: discussion
          metadata_key_for_released: date
          title: Discussion
          resources:
            - text: "[Worksheet]({{ artifacts['worksheet.pdf'].path }})"
              requires:
                artifacts: [worksheet.pdf]
      exams:
        Midterm: 2024-10-21
        Final: 2024-12-09
      week_announcements:
        - week: 3
          content: "**Midterm review** session on Friday!"
          urgent: true
"""

import datetime
from typing import Any, Callable, Sequence, cast

import smartconfig
import smartconfig.types
from smartconfig import NotRequired, Prototype

import automata.materials

from .._types import RenderContext
from ._common import is_something_missing, render_element_template

# schemata -------------------------------------------------------------------


class Requires(Prototype):
    artifacts: list[str] = []
    metadata: list[str] = []
    non_null_metadata: list[str] = []
    text_if_missing: str | None = None


class Resource(Prototype):
    text: str
    title: str | None = None
    key_for_parts: NotRequired[str]
    requires: Requires | None = None


class LectureConfig(Prototype):
    collection: str
    metadata_key_for_released: str
    title: str
    resources: list[Resource]


class AssignmentConfig(Prototype):
    collection: str
    metadata_key_for_released: str
    metadata_key_for_due: str | None
    title: str
    resources: list[Resource]


class DiscussionConfig(Prototype):
    collection: str
    metadata_key_for_released: str
    title: str
    resources: list[Resource]


class WeekAnnouncement(Prototype):
    week: int
    content: str
    urgent: bool = False


class Config(Prototype):
    week_topics: list[str]
    first_week_start_date: datetime.date
    lecture: LectureConfig
    assignments: list[AssignmentConfig]
    discussions: list[DiscussionConfig]
    week_order: str = "this_week_first"
    exams: NotRequired[dict[str, datetime.date]]
    week_announcements: NotRequired[list[WeekAnnouncement]]
    first_week_number: int = 1


# constants ------------------------------------------------------------------

_ONE_WEEK = datetime.timedelta(weeks=1)


# week class -----------------------------------------------------------------


class _Week:
    """Container for week metadata and filtering helpers.

    Represents a single week in the course schedule, storing its number,
    start date, and topic. Provides methods to filter materials collections
    to only include publications released during this week.

    Attributes
    ----------
    number : int
        The week number (e.g., 1 for the first week of the course).
    start_date : datetime.date
        The first day of the week (typically a Monday).
    topic : str
        The topic or title for this week (e.g., "Introduction to Python").
    """

    def __init__(self, number: int, start_date: datetime.date, topic: str):
        self.number = number
        self.start_date = start_date
        self.topic = topic

    def filter(
        self, collection: automata.materials.Collection, date_key: str
    ) -> automata.materials.Collection:
        """Filter a collection to publications released within this week.

        Parameters
        ----------
        collection : automata.materials.Collection
            The materials collection to filter.
        date_key : str
            The metadata key containing each publication's release date.

        Returns
        -------
        automata.materials.Collection
            A new collection containing only publications released during
            this week's date range.
        """
        return automata.materials.filter(
            collection, _is_publication_within_week_predicate(self.start_date, date_key)
        )

    def contains(self, date: datetime.date) -> bool:
        """Check if a date falls within this week's span.

        Parameters
        ----------
        date : datetime.date
            The date to check.

        Returns
        -------
        bool
            True if the date is on or after the start date and before
            the start of the following week.
        """
        return self.start_date <= date < self.start_date + _ONE_WEEK


# week helpers ---------------------------------------------------------------


def _is_publication_within_week_predicate(
    start_date: datetime.date, date_key: str
) -> Callable[[str, Any], bool]:
    """Build a predicate that checks if a publication falls within a week.

    Creates a filter function suitable for use with ``automata.materials.filter``
    that returns True for publications whose release date falls within the
    seven-day span starting from ``start_date``.

    Parameters
    ----------
    start_date : datetime.date
        The first day of the week (typically a Monday).
    date_key : str
        The metadata key containing the publication's date (e.g., "released").

    Returns
    -------
    Callable[[str, Any], bool]
        A predicate function that accepts a key and node, returning True if
        the node is not a Publication or if the publication's date falls
        within the week.
    """

    def predicate(key: str, node: Any) -> bool:
        if not isinstance(node, automata.materials.Publication):
            return True
        else:
            date_value = node.metadata[date_key]
            if isinstance(date_value, datetime.datetime):
                date_value = date_value.date()

            date_value = cast(datetime.date, date_value)
            return start_date <= date_value < start_date + _ONE_WEEK

    return predicate


def _generate_weeks(
    element_config: smartconfig.types.ConfigurationDict,
    published: automata.materials.Universe,
) -> list[_Week]:
    """Construct _Week instances from the element configuration.

    Creates a list of _Week objects based on the ``week_topics`` list in the
    configuration. Each week is assigned a sequential number starting from
    ``first_week_number`` and a start date offset by one week from the previous.

    Parameters
    ----------
    element_config : smartconfig.types.ConfigurationDict
        The resolved schedule element configuration containing ``week_topics``,
        ``first_week_number``, and ``first_week_start_date``.
    published : automata.materials.Universe
        The materials universe (currently unused but available for future use).

    Returns
    -------
    list[_Week]
        A list of _Week instances, one for each topic in ``week_topics``.
    """
    week_topics = cast(list[str], element_config["week_topics"])
    first_week_number = cast(int, element_config["first_week_number"])
    first_week_start_date = cast(datetime.date, element_config["first_week_start_date"])

    weeks = []
    for i, topic in enumerate(week_topics):
        week = _Week(
            number=first_week_number + i,
            topic=topic,
            start_date=first_week_start_date + i * _ONE_WEEK,
        )
        weeks.append(week)

    return weeks


def _order_this_week_first(weeks: Sequence[_Week], today: datetime.date) -> list[_Week]:
    """Order weeks with the current week first, then future, then past.

    Arranges weeks so that the most relevant content appears first: the current
    or most recent week is at the top, followed by upcoming weeks in
    chronological order, then past weeks in reverse chronological order.

    Parameters
    ----------
    weeks : Sequence[_Week]
        The weeks to order.
    today : datetime.date
        The current date used to determine which weeks are past/future.

    Returns
    -------
    list[_Week]
        The reordered list of weeks.
    """
    past_weeks = [w for w in weeks if w.start_date <= today]
    future_weeks = [w for w in weeks if w.start_date > today]

    past = sorted(past_weeks, key=lambda x: x.start_date, reverse=True)
    future = sorted(future_weeks, key=lambda x: x.start_date, reverse=False)

    return past + future


def _order_this_week_last(weeks: Sequence[_Week], today: datetime.date) -> list[_Week]:
    """Order weeks chronologically from oldest to newest.

    Arranges weeks in standard calendar order, with the first week of the
    course at the top and the most recent week at the bottom.

    Parameters
    ----------
    weeks : Sequence[_Week]
        The weeks to order.
    today : datetime.date
        The current date (unused, but accepted for interface consistency).

    Returns
    -------
    list[_Week]
        The chronologically ordered list of weeks.
    """
    return sorted(weeks, key=lambda x: x.start_date)


def _order_weeks(
    element_config: smartconfig.types.ConfigurationDict,
    weeks: Sequence[_Week],
    today: datetime.date,
) -> list[_Week]:
    """Order weeks according to the configured ordering strategy.

    Dispatches to the appropriate ordering function based on the ``week_order``
    configuration option.

    Parameters
    ----------
    element_config : smartconfig.types.ConfigurationDict
        The resolved schedule element configuration containing ``week_order``.
    weeks : Sequence[_Week]
        The weeks to order.
    today : datetime.date
        The current date, passed to the ordering function.

    Returns
    -------
    list[_Week]
        The ordered list of weeks according to the configured strategy.
    """
    week_order = cast(str, element_config.get("week_order", "this_week_first"))

    return {
        "this_week_first": _order_this_week_first,
        "this_week_last": _order_this_week_last,
    }[week_order](weeks, today)


# public API -----------------------------------------------------------------


def schedule(
    context: RenderContext, element_config: smartconfig.types.ConfigurationDict
) -> str:
    """Render the schedule element into HTML.

    The main entry point for the schedule element. Validates and resolves the
    configuration, generates week objects, orders them according to the
    configured strategy, and renders the schedule template.

    Parameters
    ----------
    context : RenderContext
        The rendering context providing theme path, materials, current time,
        and other page-level variables.
    element_config : smartconfig.types.ConfigurationDict
        The schedule element configuration from the page YAML.

    Returns
    -------
    str
        The rendered HTML string for the schedule element.
    """
    element_config = smartconfig.resolve(element_config, Config._schema())
    assert isinstance(element_config, dict)

    assert context.materials is not None
    weeks = _generate_weeks(element_config, context.materials)
    weeks = _order_weeks(element_config, weeks, context.now.date())

    try:
        [this_week] = [w for w in weeks if w.contains(context.now.date())]
    except ValueError:
        this_week = None

    return render_element_template(
        "schedule.html",
        context,
        extra_vars=dict(
            element_config=element_config,
            weeks=weeks,
            this_week=this_week,
            is_something_missing=is_something_missing,
        ),
    )
