from datetime import datetime

from conftest import generate


def test_date_pill_uses_now_for_current_date(tmpsite, hooks):
    # given
    tmpsite.make_page(
        "index.html",
        (
            '${ elements.date_pill({"date": "2024-06-16", '
            '"text_before": "Before!", "text_after": "After!"}) }'
        ),
    )

    # when
    generate(tmpsite, current_time=datetime(2024, 6, 15), hooks=hooks)

    # then
    output = tmpsite.get_output("index.html")
    assert "Before!" in output

    # when
    generate(tmpsite, current_time=datetime(2024, 6, 17), hooks=hooks)
    output = tmpsite.get_output("index.html")
    assert "After!" in output


def test_date_pill_with_template_variables(tmpsite, hooks):
    # given
    tmpsite.make_page(
        "index.html",
        (
            '${ elements.date_pill({"date": "2024-06-16", '
            '"text_before": vars.foo, "text_after": "After!"}) }'
        ),
    )

    # when
    generate(
        tmpsite,
        current_time=datetime(2024, 6, 15),
        vars={"foo": "BAR"},
        hooks=hooks,
    )

    # then
    output = tmpsite.get_output("index.html")
    assert "BAR" in output
