"""Shared fixtures for default theme tests."""

from pytest import fixture

import automata.website

# Default vars required by the default theme templates
DEFAULT_THEME_VARS = {
    "short_title": "Test Site",
    "long_title": "Test Site Long Title",
    "navigation": [],
    "rebuild_tailwind": False,
}


@fixture
def default_theme_kwargs():
    """Fixture that returns the default theme's components for generate().

    Returns a dictionary containing templates, elements, static_files, assets,
    and default vars that can be splatted into generate(). Note: pages is not
    included because tests provide their own pages via tmpsite.pages.
    """
    extension = automata.website.Extension.from_entry_point(
        "default", group="automata.website.themes"
    )
    return {
        "templates": extension.templates,
        "elements": extension.elements,
        "static_files": extension.static_files,
        "assets": extension.assets,
        "vars": DEFAULT_THEME_VARS.copy(),
    }
