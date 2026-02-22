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
                "rebuild_tailwind": False,  # Disable for faster tests
            },
        ),
    )


def test_people_element_renders_single_group(tmpsite, config):
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
    automata.website.generate(config, tmpsite.resources)

    # then
    output = tmpsite.get_output("index.html")
    assert "<h2>Instructors</h2>" in output
    assert "Alice Smith" in output
    assert "Professor" in output
    assert "/images/alice.jpg" in output
    assert "https://alice.example.com" in output
    assert "Alice is an expert in algorithms." in output


def test_people_element_renders_multiple_groups(tmpsite, config):
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
    automata.website.generate(config, tmpsite.resources)

    # then
    output = tmpsite.get_output("index.html")
    assert "<h2>Instructors</h2>" in output
    assert "Alice Smith" in output
    assert "Bob Jones" in output
    assert "<h2>Teaching assistants</h2>" in output
    assert "Charlie Brown" in output


def test_people_element_person_without_optional_fields(tmpsite, config):
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
    automata.website.generate(config, tmpsite.resources)

    # then
    output = tmpsite.get_output("index.html")
    assert "Jane Doe" in output
    assert "<h2>Students</h2>" in output


def test_people_element_person_with_website_creates_link(tmpsite, config):
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
    automata.website.generate(config, tmpsite.resources)

    # then
    output = tmpsite.get_output("index.html")
    assert '<a href="https://john.example.com">John Doe</a>' in output


def test_people_element_displays_photo_when_provided(tmpsite, config):
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
    automata.website.generate(config, tmpsite.resources)

    # then
    output = tmpsite.get_output("index.html")
    assert '<img src="/photos/sarah.png"' in output
