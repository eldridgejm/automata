from typing import cast
from unittest.mock import Mock

import pytest

from automata.website._config import Config
from automata.website._render import RenderContext
from automata.website._theme import Theme
from automata.website.themes.default.elements import (
    announcement_box,
)


@pytest.fixture
def default_theme():
    """Load the default theme from the entry point."""
    return Theme.from_entry_point("default")


@pytest.fixture
def render_context(default_theme):
    """Create a real RenderContext with the default theme."""
    # We need to mock things that aren't easily instantiated or relevant
    # for this specific test, like the Universe and Config
    config = cast(Config, Mock(spec=Config))
    materials = Mock()
    url_for = Mock(return_value="/")

    return RenderContext(
        config=config,
        materials=materials,
        url_for=url_for,
        theme=default_theme,
    )


def test_announcement_box_default(render_context):
    """Test announcement box with default urgent=False."""
    config = {"content": "Hello, world!"}

    # Render the element
    result = announcement_box(config, render_context)

    # Verify the output
    assert '<div class="announcement">' in result
    assert "Hello, world!" in result
    # Ensure "urgent" is not in the class list
    assert 'class="announcement urgent"' not in result


def test_announcement_box_urgent(render_context):
    """Test announcement box with urgent=True."""
    config = {"content": "Important update!", "urgent": True}

    # Render the element
    result = announcement_box(config, render_context)

    # Verify the output
    assert '<div class="announcement urgent">' in result
    assert "Important update!" in result
