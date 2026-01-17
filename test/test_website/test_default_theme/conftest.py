"""Shared fixtures for default theme tests."""

from pytest import fixture

import automata.website


@fixture
def default_theme_kwargs():
    """Fixture that returns the default theme's components for generate().

    Returns a dictionary containing templates, elements, and extra_assets
    that can be splatted into generate().
    """
    extension = automata.website.Extension.from_entry_point(
        "default", group="automata.website.themes"
    )
    return {
        "templates": extension.templates,
        "elements": extension.elements,
        "extra_assets": extension.static_files,
    }
