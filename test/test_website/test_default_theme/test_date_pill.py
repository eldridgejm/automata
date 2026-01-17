from datetime import datetime

from pytest import fixture

import automata.website
from automata.website import PluginConfig


@fixture
def config(tmpsite):
    return automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=PluginConfig(
            use="default",
            config={
                "short_title": "DSC 40B",
                "long_title": "Theoretical Foundations of Data Science II",
                "navigation": [],
                "rebuild_tailwind": False,  # Disable for faster tests
            },
        ),
    )


def test_date_pill_uses_now_for_current_date(tmpsite, config, default_theme_kwargs):
    # given
    tmpsite.make_page(
        "index.html",
        (
            '${ elements.date_pill({"date": "2024-06-16", '
            '"text_before": "Before!", "text_after": "After!"}) }'
        ),
    )

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        **default_theme_kwargs,
        current_time=datetime(2024, 6, 15),
    )

    # then
    output = tmpsite.get_output("index.html")
    assert "Before!" in output

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        **default_theme_kwargs,
        current_time=datetime(2024, 6, 17),
    )
    output = tmpsite.get_output("index.html")
    assert "After!" in output


def test_date_pill_with_template_variables(tmpsite, config, default_theme_kwargs):
    # given
    tmpsite.make_page(
        "index.html",
        (
            '${ elements.date_pill({"date": "2024-06-16", '
            '"text_before": vars.foo, "text_after": "After!"}) }'
        ),
    )

    # when
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        **default_theme_kwargs,
        current_time=datetime(2024, 6, 15),
        vars={"foo": "BAR"},
    )

    # then
    output = tmpsite.get_output("index.html")
    assert "BAR" in output
