"""Shared fixtures for default theme tests."""

from pytest import fixture

import automata.website
from automata.extensions import THEMES_GROUP, extension_from_entry_point


@fixture
def theme():
    return extension_from_entry_point(
        "default",
        config={
            "short_title": "DSC 40B",
            "long_title": "Theoretical Foundations of Data Science II",
            "navigation": [],
            "rebuild_tailwind": False,
        },
        group=THEMES_GROUP,
    )


def render(tmpsite, **kwargs):
    """Helper that loads content and calls render with pages/static_content."""
    pages, static_content = tmpsite.load_content()
    automata.website.render(
        tmpsite.build_directory,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        **kwargs,
    )
