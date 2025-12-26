from pytest import fixture

import automata.website


@fixture
def config(tmpsite):
    return automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
        theme=automata.website.ThemeConfig(
            use="default",
            config={
                "short_title": "DSC 40B",
                "long_title": "Theoretical Foundations of Data Science II",
                "navigation": [],
            },
        ),
    )


def test_announcement_box_default(tmpsite, config):
    """Test announcement box with default urgent=False."""
    # given
    tmpsite.make_page(
        "index.html",
        '${ elements.announcement_box({"content": "Important notice!"}) }',
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert '<div class="announcement">' in output
    assert "Important notice!" in output
    assert "urgent" not in output


def test_announcement_box_urgent(tmpsite, config):
    """Test announcement box with urgent=True."""
    # given
    tmpsite.make_page(
        "index.html",
        '${ elements.announcement_box({"content": "Urgent alert!", "urgent": true}) }',
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert '<div class="announcement urgent">' in output
    assert "Urgent alert!" in output
