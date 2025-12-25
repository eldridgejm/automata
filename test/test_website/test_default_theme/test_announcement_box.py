import automata.website


def test_announcement_box_default(tmpsite):
    """Test announcement box with default urgent=False."""
    # given
    tmpsite.make_page(
        "index.html",
        '${ elements.announcement_box({"content": "Important notice!"}) }',
    )

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert '<div class="announcement">' in output
    assert "Important notice!" in output
    assert "urgent" not in output


def test_announcement_box_urgent(tmpsite):
    """Test announcement box with urgent=True."""
    # given
    tmpsite.make_page(
        "index.html",
        '${ elements.announcement_box({"content": "Urgent alert!", "urgent": true}) }',
    )

    config = automata.website.Config(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )

    # when
    automata.website.generate(config)

    # then
    output = tmpsite.get_output("index.html")
    assert '<div class="announcement urgent">' in output
    assert "Urgent alert!" in output
