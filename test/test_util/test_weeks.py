"""Unit tests for the automata.util.weeks module."""

import datetime

from automata import materials
from automata.util.weeks import (
    Week,
    find_week,
    make_n_weeks,
    order_weeks_by_recency,
    place_into_weeks,
)

# ============================================================================
# Week class tests
# ============================================================================


def test_week_initialization():
    """Test that Week is initialized correctly."""
    start = datetime.date(2024, 1, 1)
    week = Week(number=1, start_date=start)

    assert week.number == 1
    assert week.start_date == start


def test_week_contains_date_within_week():
    """Test that contains() returns True for dates within the week."""
    start = datetime.date(2024, 1, 1)  # Monday
    week = Week(number=1, start_date=start)

    # Test dates within the week (7 days from start, exclusive end)
    assert week.contains(datetime.date(2024, 1, 1))  # First day
    assert week.contains(datetime.date(2024, 1, 3))  # Middle of week
    assert week.contains(datetime.date(2024, 1, 7))  # Last day (Sunday)


def test_week_contains_date_outside_week():
    """Test that contains() returns False for dates outside the week."""
    start = datetime.date(2024, 1, 1)  # Monday
    week = Week(number=1, start_date=start)

    # Test dates outside the week
    assert not week.contains(datetime.date(2023, 12, 31))  # Day before
    assert not week.contains(datetime.date(2024, 1, 8))  # Next week


def test_week_contains_boundary_conditions():
    """Test boundary conditions for contains()."""
    start = datetime.date(2024, 1, 1)
    week = Week(number=1, start_date=start)

    # Exactly at start (inclusive)
    assert week.contains(start)

    # Exactly 7 days later (exclusive)
    end = start + datetime.timedelta(weeks=1)
    assert not week.contains(end)


def test_week_filter_with_date_metadata():
    """Test filtering publications by week using date metadata."""
    # Create publications with different due dates
    pub1 = materials.Publication(
        metadata={"due": datetime.date(2024, 1, 3)},
        artifacts={},
    )
    pub2 = materials.Publication(
        metadata={"due": datetime.date(2024, 1, 10)},
        artifacts={},
    )

    # Create collection
    schema = materials.PublicationSchema(required_artifacts=[])
    collection = materials.Collection(
        publication_schema=schema,
        publications={"hw1": pub1, "hw2": pub2},
    )

    # Filter by week 1 (Jan 1-7, 2024)
    week1 = Week(number=1, start_date=datetime.date(2024, 1, 1))
    filtered = week1.filter(collection, date_key="due")

    # hw1 should be in week 1, hw2 should not
    assert "hw1" in filtered.publications
    assert "hw2" not in filtered.publications


def test_week_filter_with_datetime_metadata():
    """Test filtering publications by week using datetime metadata."""
    # Create publication with datetime due date
    pub1 = materials.Publication(
        metadata={"due": datetime.datetime(2024, 1, 3, 23, 59, 0)},
        artifacts={},
    )

    # Create collection
    schema = materials.PublicationSchema(required_artifacts=[])
    collection = materials.Collection(
        publication_schema=schema,
        publications={"hw1": pub1},
    )

    week1 = Week(number=1, start_date=datetime.date(2024, 1, 1))
    filtered = week1.filter(collection, date_key="due")

    assert "hw1" in filtered.publications


def test_week_filter_excludes_publications_without_date_key():
    """Test that filter excludes publications without the specified date key."""
    # Create publication without 'due' key
    pub1 = materials.Publication(
        metadata={},
        artifacts={},
    )

    # Create collection
    schema = materials.PublicationSchema(required_artifacts=[])
    collection = materials.Collection(
        publication_schema=schema,
        publications={"hw1": pub1},
    )

    week1 = Week(number=1, start_date=datetime.date(2024, 1, 1))
    filtered = week1.filter(collection, date_key="due")

    # Publication without 'due' key should be filtered out
    assert "hw1" not in filtered.publications


# ============================================================================
# make_n_weeks() tests
# ============================================================================


def test_make_n_weeks_with_correct_numbers():
    """Test that weeks are generated with incrementing numbers."""
    start = datetime.date(2024, 1, 1)
    weeks = make_n_weeks(start, n=3, first_week_number=1)

    assert weeks[0].number == 1
    assert weeks[1].number == 2
    assert weeks[2].number == 3


def test_make_n_weeks_with_correct_dates():
    """Test that weeks are generated with incrementing dates."""
    start = datetime.date(2024, 1, 1)
    weeks = make_n_weeks(start, n=3, first_week_number=1)

    assert weeks[0].start_date == datetime.date(2024, 1, 1)
    assert weeks[1].start_date == datetime.date(2024, 1, 8)
    assert weeks[2].start_date == datetime.date(2024, 1, 15)


def test_make_n_weeks_with_custom_first_week_number():
    """Test that first_week_number parameter works correctly."""
    start = datetime.date(2024, 1, 1)
    weeks = make_n_weeks(start, n=2, first_week_number=5)

    assert weeks[0].number == 5
    assert weeks[1].number == 6


# ============================================================================
# order_weeks_by_recency() tests
# ============================================================================


def test_order_weeks_by_recency_past_weeks_most_recent_first():
    """Test that past weeks are ordered with most recent first."""
    weeks = [
        Week(1, datetime.date(2024, 1, 1)),
        Week(2, datetime.date(2024, 1, 8)),
        Week(3, datetime.date(2024, 1, 15)),
    ]

    current = datetime.date(2024, 1, 20)
    past, future = order_weeks_by_recency(weeks, current)

    # All weeks are in the past, should be reversed
    assert len(past) == 3
    assert len(future) == 0
    assert past[0].number == 3
    assert past[1].number == 2
    assert past[2].number == 1


def test_order_weeks_by_recency_future_weeks_soonest_first():
    """Test that future weeks are ordered with soonest first."""
    weeks = [
        Week(1, datetime.date(2024, 1, 15)),
        Week(2, datetime.date(2024, 1, 8)),
        Week(3, datetime.date(2024, 1, 1)),
    ]

    current = datetime.date(2023, 12, 31)
    past, future = order_weeks_by_recency(weeks, current)

    # All weeks are in the future, should be sorted ascending
    assert len(past) == 0
    assert len(future) == 3
    assert future[0].number == 3
    assert future[1].number == 2
    assert future[2].number == 1


def test_order_weeks_by_recency_mixed_past_and_future():
    """Test ordering with mix of past and future weeks."""
    weeks = [
        Week(1, datetime.date(2024, 1, 1)),
        Week(2, datetime.date(2024, 1, 8)),
        Week(3, datetime.date(2024, 1, 15)),
        Week(4, datetime.date(2024, 1, 22)),
        Week(5, datetime.date(2024, 1, 29)),
    ]

    current = datetime.date(2024, 1, 16)
    past, future = order_weeks_by_recency(weeks, current)

    # Week 3 (Jan 15) is past, weeks 4, 5 are future
    assert len(past) == 3  # weeks 1, 2, 3
    assert len(future) == 2  # weeks 4, 5

    # Past weeks should be most recent first
    assert past[0].number == 3
    assert past[1].number == 2
    assert past[2].number == 1

    # Future weeks should be soonest first
    assert future[0].number == 4
    assert future[1].number == 5


def test_order_weeks_by_recency_empty_list():
    """Test ordering an empty list of weeks."""
    weeks = []
    current = datetime.date(2024, 1, 1)
    past, future = order_weeks_by_recency(weeks, current)

    assert past == []
    assert future == []


def test_order_weeks_by_recency_single_week():
    """Test ordering a single week."""
    weeks = [Week(1, datetime.date(2024, 1, 1))]
    current = datetime.date(2024, 1, 5)
    past, future = order_weeks_by_recency(weeks, current)

    assert len(past) == 1
    assert len(future) == 0
    assert past[0].number == 1


# ============================================================================
# find_week() tests
# ============================================================================


def test_find_week_finds_current():
    """Test finding the week that contains current_date."""
    weeks = [
        Week(1, datetime.date(2024, 1, 1)),
        Week(2, datetime.date(2024, 1, 8)),
        Week(3, datetime.date(2024, 1, 15)),
    ]

    current = datetime.date(2024, 1, 10)
    current_week = find_week(weeks, current)

    assert current_week is not None
    assert current_week.number == 2


def test_find_week_returns_none_when_not_found():
    """Test that None is returned when date is outside all weeks."""
    weeks = [
        Week(1, datetime.date(2024, 1, 1)),
        Week(2, datetime.date(2024, 1, 8)),
    ]

    current = datetime.date(2024, 2, 1)
    current_week = find_week(weeks, current)

    assert current_week is None


def test_find_week_on_start_date():
    """Test finding week when current_date is exactly the start date."""
    weeks = [
        Week(1, datetime.date(2024, 1, 1)),
        Week(2, datetime.date(2024, 1, 8)),
    ]

    current = datetime.date(2024, 1, 1)
    current_week = find_week(weeks, current)

    assert current_week is not None
    assert current_week.number == 1


def test_find_week_empty_weeks_list():
    """Test with empty weeks list."""
    weeks = []
    current = datetime.date(2024, 1, 1)
    current_week = find_week(weeks, current)

    assert current_week is None


def test_find_week_first_matching():
    """Test that it returns the first week when multiple weeks could match."""
    # Edge case: overlapping weeks (shouldn't happen normally but test behavior)
    weeks = [
        Week(1, datetime.date(2024, 1, 1)),
        Week(2, datetime.date(2024, 1, 3)),  # Overlapping week
    ]

    current = datetime.date(2024, 1, 5)
    current_week = find_week(weeks, current)

    # Should return the first matching week
    assert current_week.number == 1


# ============================================================================
# place_into_weeks() tests
# ============================================================================


def test_place_into_weeks_places_correctly():
    """Test that items are placed into correct weeks."""
    weeks = [
        Week(1, datetime.date(2024, 1, 1)),
        Week(2, datetime.date(2024, 1, 8)),
        Week(3, datetime.date(2024, 1, 15)),
    ]

    items = [
        {"name": "item1", "date": datetime.date(2024, 1, 3)},
        {"name": "item2", "date": datetime.date(2024, 1, 10)},
        {"name": "item3", "date": datetime.date(2024, 1, 17)},
    ]

    result = place_into_weeks(weeks, items, date=lambda item: item["date"])

    assert len(result[weeks[0]]) == 1
    assert result[weeks[0]][0]["name"] == "item1"

    assert len(result[weeks[1]]) == 1
    assert result[weeks[1]][0]["name"] == "item2"

    assert len(result[weeks[2]]) == 1
    assert result[weeks[2]][0]["name"] == "item3"


def test_place_into_weeks_multiple_items_same_week():
    """Test that multiple items can be placed in the same week."""
    weeks = [Week(1, datetime.date(2024, 1, 1))]

    items = [
        {"name": "item1", "date": datetime.date(2024, 1, 2)},
        {"name": "item2", "date": datetime.date(2024, 1, 3)},
        {"name": "item3", "date": datetime.date(2024, 1, 4)},
    ]

    result = place_into_weeks(weeks, items, date=lambda item: item["date"])

    assert len(result[weeks[0]]) == 3


def test_place_into_weeks_on_miss_none():
    """Test that items not fitting in any week are ignored when on_miss=None."""
    weeks = [Week(1, datetime.date(2024, 1, 1))]

    items = [
        {"name": "item1", "date": datetime.date(2024, 1, 3)},  # In week
        {"name": "item2", "date": datetime.date(2024, 2, 1)},  # Outside
    ]

    result = place_into_weeks(
        weeks, items, date=lambda item: item["date"], on_miss=None
    )

    assert len(result[weeks[0]]) == 1
    assert result[weeks[0]][0]["name"] == "item1"


def test_place_into_weeks_on_miss_callback():
    """Test that on_miss callback is called for items that don't fit in any week."""
    weeks = [Week(1, datetime.date(2024, 1, 1))]
    items = [
        {"name": "item1", "date": datetime.date(2024, 1, 3)},  # In week
        {"name": "item2", "date": datetime.date(2024, 2, 1)},  # Outside
    ]

    missed_items = []

    def record_miss(item):
        missed_items.append(item)

    result = place_into_weeks(
        weeks, items, date=lambda item: item["date"], on_miss=record_miss
    )

    assert len(result[weeks[0]]) == 1
    assert result[weeks[0]][0]["name"] == "item1"
    assert len(missed_items) == 1
    assert missed_items[0]["name"] == "item2"


def test_place_into_weeks_empty_lists():
    """Test that weeks without items have empty lists."""
    weeks = [
        Week(1, datetime.date(2024, 1, 1)),
        Week(2, datetime.date(2024, 1, 8)),
        Week(3, datetime.date(2024, 1, 15)),
    ]

    items = [
        {"name": "item1", "date": datetime.date(2024, 1, 3)},
    ]

    result = place_into_weeks(weeks, items, date=lambda item: item["date"])

    assert len(result[weeks[0]]) == 1
    assert len(result[weeks[1]]) == 0
    assert len(result[weeks[2]]) == 0


def test_place_into_weeks_empty_items():
    """Test with empty items list."""
    weeks = [Week(1, datetime.date(2024, 1, 1))]
    items = []

    result = place_into_weeks(weeks, items, date=lambda item: item["date"])

    assert len(result[weeks[0]]) == 0


def test_place_into_weeks_empty_weeks():
    """Test with empty weeks list."""
    weeks = []
    items = [{"name": "item1", "date": datetime.date(2024, 1, 3)}]

    result = place_into_weeks(weeks, items, date=lambda item: item["date"])

    assert result == {}
