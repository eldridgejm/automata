from conftest import render


def test_people_element_renders_single_group(tmpsite, theme):
    """Test rendering a single group with one person."""
    # given
    tmpsite.make_page(
        "index.html",
        """
        ${ elements.people([
            {
                "group": "instructors",
                "members": [
                    {
                        "name": "Alice Smith",
                        "role": "professor",
                        "photo": "/images/alice.jpg",
                        "website": "https://alice.example.com",
                        "about": "Alice is an expert in algorithms."
                    }
                ]
            }
        ]) }
        """,
    )

    # when
    render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert "<h2>Instructors</h2>" in output
    assert "Alice Smith" in output
    assert "Professor" in output
    assert "/images/alice.jpg" in output
    assert "https://alice.example.com" in output
    assert "Alice is an expert in algorithms." in output


def test_people_element_renders_multiple_groups(tmpsite, theme):
    """Test rendering multiple groups with multiple people."""
    # given
    tmpsite.make_page(
        "index.html",
        """
        ${ elements.people([
            {
                "group": "instructors",
                "members": [
                    {"name": "Alice Smith", "role": "professor"},
                    {"name": "Bob Jones", "role": "lecturer"}
                ]
            },
            {
                "group": "teaching assistants",
                "members": [
                    {"name": "Charlie Brown"}
                ]
            }
        ]) }
        """,
    )

    # when
    render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert "<h2>Instructors</h2>" in output
    assert "Alice Smith" in output
    assert "Bob Jones" in output
    assert "<h2>Teaching assistants</h2>" in output
    assert "Charlie Brown" in output


def test_people_element_person_without_optional_fields(tmpsite, theme):
    """Test rendering a person with only required fields."""
    # given
    tmpsite.make_page(
        "index.html",
        """
        ${ elements.people([
            {
                "group": "students",
                "members": [
                    {"name": "Jane Doe"}
                ]
            }
        ]) }
        """,
    )

    # when
    render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert "Jane Doe" in output
    assert "<h2>Students</h2>" in output


def test_people_element_person_with_website_creates_link(tmpsite, theme):
    """Test that person with website gets a linked name."""
    # given
    tmpsite.make_page(
        "index.html",
        """
        ${ elements.people([
            {
                "group": "staff",
                "members": [
                    {"name": "John Doe", "website": "https://john.example.com"}
                ]
            }
        ]) }
        """,
    )

    # when
    render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert '<a href="https://john.example.com">John Doe</a>' in output


def test_people_element_displays_photo_when_provided(tmpsite, theme):
    """Test that photo is displayed when provided."""
    # given
    tmpsite.make_page(
        "index.html",
        """
        ${ elements.people([
            {
                "group": "team",
                "members": [
                    {"name": "Sarah Lee", "photo": "/photos/sarah.png"}
                ]
            }
        ]) }
        """,
    )

    # when
    render(tmpsite, theme=theme)

    # then
    output = tmpsite.get_output("index.html")
    assert '<img src="/photos/sarah.png"' in output


def _people(tmpsite, theme, group="TAs", role="TA"):
    tmpsite.make_page(
        "index.html",
        "${ elements.people([{'group': '%s', 'members': [{'name': 'Bo Li', "
        "'role': '%s', 'photo': '/images/bo.jpg', 'about': 'Hi.'}]}]) }"
        % (group, role),
    )
    render(tmpsite, theme=theme)
    return tmpsite.get_output("index.html")


def test_people_keeps_the_capitals_of_roles_and_groups(tmpsite, theme):
    # .capitalize() would make "TA" "Ta", and "TAs" "Tas"
    output = _people(tmpsite, theme)

    assert "<b>TA</b>" in output
    assert "<h2>TAs</h2>" in output


def test_people_capitalizes_the_first_letter_of_lowercase_roles(tmpsite, theme):
    output = _people(tmpsite, theme, group="tutors", role="tutor")

    assert "<b>Tutor</b>" in output
    assert "<h2>Tutors</h2>" in output


def test_people_lays_out_with_tailwind_not_bootstrap(tmpsite, theme):
    # the theme doesn't load Bootstrap, so its grid classes did nothing, and
    # photos stretched to the page's width
    import re

    output = _people(tmpsite, theme)

    assert not re.search(r'class="[^"]*\b(row|col-\d+)\b', output)
    photo = re.search(r'<img[^>]*src="/images/bo.jpg"[^>]*>', output)[0]
    for name in ["size-32", "object-cover", "rounded-full"]:
        assert name in photo
    assert 'alt="Bo Li"' in photo
