from datetime import datetime

from bs4 import BeautifulSoup
from conftest import render


def test_date_pill_uses_now_for_current_date(tmpsite, theme):
    # given
    tmpsite.make_page(
        "index.html",
        (
            '${ elements.date_pill({"date": "2024-06-16", '
            '"text_before": "Before!", "text_after": "After!"}) }'
        ),
    )

    # when
    render(tmpsite, current_time=datetime(2024, 6, 15), theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert "Before!" in output

    # when
    render(tmpsite, current_time=datetime(2024, 6, 17), theme=theme)
    output = tmpsite.get_output("index.html")
    assert "After!" in output


def test_date_pill_with_template_variables(tmpsite, theme):
    # given
    tmpsite.make_page(
        "index.html",
        (
            '${ elements.date_pill({"date": "2024-06-16", '
            '"text_before": vars.foo, "text_after": "After!"}) }'
        ),
    )

    # when
    render(
        tmpsite,
        current_time=datetime(2024, 6, 15),
        vars={"foo": "BAR"},
        theme=theme,
    )

    # then
    output = tmpsite.get_output("index.html")
    assert "BAR" in output


def render_date_pill(tmpsite, theme, current_time):
    """Render a date pill for June 16, 2024 and return the parsed page."""
    tmpsite.make_page(
        "index.html",
        (
            '${ elements.date_pill({"date": "2024-06-16", '
            '"text_before": "Midterm on Sunday", '
            '"text_after": "Midterm was on Sunday"}) }'
        ),
    )
    render(tmpsite, current_time=current_time, theme=theme)
    return BeautifulSoup(tmpsite.get_output("index.html"), "html.parser")


def test_date_pill_marks_a_date_days_away_as_upcoming(tmpsite, theme):
    # when
    soup = render_date_pill(tmpsite, theme, datetime(2024, 6, 13))

    # then
    label = soup.find(class_="date-upcoming")
    assert label is not None
    assert "Midterm on Sunday" in label.get_text()


def test_date_pill_marks_todays_date_as_today(tmpsite, theme):
    # when
    soup = render_date_pill(tmpsite, theme, datetime(2024, 6, 16, 9, 0))

    # then
    label = soup.find(class_="date-today")
    assert label is not None
    assert "Midterm on Sunday" in label.get_text()
    assert soup.find(class_="date-upcoming") is None


def test_date_pill_marks_a_past_date_as_past(tmpsite, theme):
    # when
    soup = render_date_pill(tmpsite, theme, datetime(2024, 6, 17))

    # then
    label = soup.find(class_="date-past")
    assert label is not None
    assert "Midterm was on Sunday" in label.get_text()
