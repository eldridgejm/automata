"""Utilities for working with weeks in a course schedule."""

import datetime
from typing import Any, Callable, Collection, TypeVar

from .. import materials


class Week:
    """Represents a single week in the schedule."""

    def __init__(self, number: int, start_date: datetime.date):
        """
        Initialize the Week.

        Parameters
        ----------
        number : int
            The week number.
        start_date : datetime.date
            The starting date of the week.
        """
        self.number = number
        self.start_date = start_date

    def filter(
        self, collection: materials.Collection, date_key: str
    ) -> materials.Collection:
        """
        Filter publications in a collection that fall within this week.

        Parameters
        ----------
        collection : automata.materials.Collection
            The collection of publications to filter.
        date_key : str
            The metadata key containing the date to check against. If the key is not
            present in a publication's metadata, that publication is excluded and
            no exception is raised.

        Returns
        -------
        automata.materials.Collection
            A new collection containing only publications falling within this week.
        """
        end_date = self.start_date + datetime.timedelta(weeks=1)

        def _publication_within_week(key: str, node: Any) -> bool:
            if not isinstance(node, materials.Publication):
                return True

            if date_key not in node.metadata:
                return False

            date_value = node.metadata[date_key]
            if isinstance(date_value, datetime.datetime):
                date_value = date_value.date()

            return bool(self.start_date <= date_value < end_date)

        return materials.filter(collection, predicate=_publication_within_week)

    def contains(self, date: datetime.date) -> bool:
        """
        Check if a date falls within this week.

        Parameters
        ----------
        date : datetime.date
            The date to check.

        Returns
        -------
        bool
            True if the date is within this week, False otherwise.
        """
        return self.start_date <= date < self.start_date + datetime.timedelta(weeks=1)


def make_n_weeks(start_date: datetime.date, n: int, first_week_number=1) -> list[Week]:
    """Creates a list of weeks starting from a given date.

    Parameters
    ----------
    start_date : datetime.date
        The starting date for the first week.
    first_week_number : int, optional
        The number of the first week, by default 1.

    Returns
    -------
    list[Week]
        List of Week objects.
    """
    weeks = []
    for i in range(n):
        week = Week(
            number=first_week_number + i,
            start_date=start_date + datetime.timedelta(weeks=i),
        )
        weeks.append(week)

    return weeks


def order_weeks_by_recency(
    weeks: Collection[Week], current_date: datetime.date
) -> tuple[list[Week], list[Week]]:
    """
    Order weeks by recency, with the most recent week first.

    Parameters
    ----------
    weeks : Collection[Week]
        The list of weeks to order.
    current_date : datetime.date
        The current date used for ordering.

    Returns
    -------
    tuple[list[Week], list[Week]]
        A pair of lists, the first listing past weeks (most recent first),
        the second listing future weeks (soonest first).

    """
    past_weeks = [w for w in weeks if w.start_date <= current_date]
    future_weeks = [w for w in weeks if w.start_date > current_date]

    past = sorted(past_weeks, key=lambda w: w.start_date, reverse=True)
    future = sorted(future_weeks, key=lambda w: w.start_date)

    return past, future


def find_week(weeks: Collection[Week], current_date: datetime.date) -> Week | None:
    """
    Find the week that contains the given date.

    Parameters
    ----------
    weeks : Collection[Week]
        The list of weeks to search.
    current_date : datetime.date
        The current date.

    Returns
    -------
    Week | None
        The week containing the date if found, otherwise None.

    """
    for week in weeks:
        if week.contains(current_date):
            return week
    return None


T = TypeVar("T")


def place_into_weeks(
    weeks: Collection[Week],
    items: Collection[T],
    date: Callable[[T], datetime.date],
    on_miss: Callable[[T], None] | None = None,
):
    """Places items into their corresponding weeks based on a date function.

    Parameters
    ----------
    weeks : Collection[Week]
        The collection of weeks to place items into.
    items : Collection[T]
        The collection of items to be placed into weeks.
    date : Callable[[T], datetime.date]
        A function that extracts a date from an item.
    on_miss : Callable[[T]] | None, optional
        Function to call when an item does not fit into any week. If None, items that do
        not fit into any week are ignored.

    Returns
    -------
    dict[Week, list[T]]
        A dictionary mapping each week to a list of items that fall within that week.
    """
    week_map: dict[Week, list[T]] = {week: [] for week in weeks}

    for item in items:
        item_date = date(item)
        for week in weeks:
            if week.contains(item_date):
                week_map[week].append(item)
                break
        else:
            if on_miss is not None:
                on_miss(item)

    return week_map


def find_display_week(
    weeks: Collection[Week],
    start_displaying_on: datetime.date,
    week_range_start: datetime.date | None = None,
    week_range_end: datetime.date | None = None,
    current_date: datetime.date | None = None,
) -> Week | None:
    """
    Find which week to display a publication/listing in based on dates
    and current time.

    Logic:
    1. If current_date < start_displaying_on: don't show (return None)
    2. If current_date < week_range_start: show in week of week_range_start
    3. If current_date > week_range_end: show in week of week_range_end
    4. Otherwise: show in week of current_date

    Parameters
    ----------
    weeks : Collection[Week]
        List of all weeks in the schedule.
    start_displaying_on : datetime.date
        Date when the item should start appearing on the schedule.
    week_range_start : datetime.date | None
        Earliest date for week placement. If None, defaults to start_displaying_on.
    week_range_end : datetime.date | None
        Latest date for week placement. If None, defaults to week_range_start.
    current_date : datetime.date | None
        The current date used for determining placement.

    Returns
    -------
    Week | None
        The week to display in, or None if not yet visible.
    """
    if current_date is None:
        current_date = datetime.date.today()

    if week_range_start is None:
        week_range_start = start_displaying_on

    if week_range_end is None:
        week_range_end = week_range_start

    # Don't show if before start_displaying_on
    if current_date < start_displaying_on:
        return None

    # Determine target date based on current_time position relative to range
    if current_date < week_range_start:
        target_date = week_range_start
    elif current_date > week_range_end:
        target_date = week_range_end
    else:
        target_date = current_date

    # Find week containing target_date
    for week in weeks:
        if week.contains(target_date):
            return week

    return None


def place_into_display_weeks(
    items: Collection[T],
    weeks: Collection[Week],
    start_displaying_on: Callable[[T], datetime.date],
    week_range_start: Callable[[T], datetime.date | None],
    week_range_end: Callable[[T], datetime.date | None],
    current_date: datetime.date | None = None,
) -> dict[int | None, list[T]]:
    """Place items into weeks based on their display dates."""
    week_to_items: dict[int | None, list[Any]] = {week.number: [] for week in weeks}
    week_to_items[None] = []

    for item in items:
        display_week = find_display_week(
            weeks,
            start_displaying_on(item),
            week_range_start(item),
            week_range_end(item),
            current_date,
        )

        if display_week is not None:
            week_to_items[display_week.number].append(item)
        else:
            week_to_items[None].append(item)

    return week_to_items
