from datetime import datetime

import automata.website


def test_date_pill_uses_now_for_current_date(tmpsite, default_theme_kwargs):
    # given
    tmpsite.make_page(
        "index.html",
        (
            '${ elements.date_pill({"date": "2024-06-16", '
            '"text_before": "Before!", "text_after": "After!"}) }'
        ),
    )

    # Extract templates for positional arg, use rest as kwargs
    templates = default_theme_kwargs.pop("templates")

    # when
    automata.website.generate(
        tmpsite.pages,
        tmpsite.materials_directory,
        templates,
        build_directory=tmpsite.build_directory,
        **default_theme_kwargs,
        current_time=datetime(2024, 6, 15),
    )

    # then
    output = tmpsite.get_output("index.html")
    assert "Before!" in output

    # when
    automata.website.generate(
        tmpsite.pages,
        tmpsite.materials_directory,
        templates,
        build_directory=tmpsite.build_directory,
        **default_theme_kwargs,
        current_time=datetime(2024, 6, 17),
    )
    output = tmpsite.get_output("index.html")
    assert "After!" in output


def test_date_pill_with_template_variables(tmpsite, default_theme_kwargs):
    # given
    tmpsite.make_page(
        "index.html",
        (
            '${ elements.date_pill({"date": "2024-06-16", '
            '"text_before": vars.foo, "text_after": "After!"}) }'
        ),
    )

    # Extract templates for positional arg, use rest as kwargs
    templates = default_theme_kwargs.pop("templates")
    # Merge test-specific vars with default theme vars
    default_theme_kwargs["vars"]["foo"] = "BAR"

    # when
    automata.website.generate(
        tmpsite.pages,
        tmpsite.materials_directory,
        templates,
        build_directory=tmpsite.build_directory,
        **default_theme_kwargs,
        current_time=datetime(2024, 6, 15),
    )

    # then
    output = tmpsite.get_output("index.html")
    assert "BAR" in output
