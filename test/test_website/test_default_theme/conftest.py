"""Shared fixtures for default theme tests."""

from pytest import fixture

import automata.website


@fixture
def default_theme_kwargs():
    """Fixture that returns the default theme's components for generate().

    Returns a dictionary containing templates, elements, and extra_assets
    that can be splatted into generate().
    """
    theme = automata.website.Theme.from_entry_point("default")
    return {
        "templates": theme.templates,
        "elements": theme.elements,
        "extra_assets": theme.static_files,
    }
