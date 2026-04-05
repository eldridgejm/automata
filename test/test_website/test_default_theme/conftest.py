"""Shared fixtures for default theme tests."""

from pytest import fixture

import automata.website
from automata._extension import apply_extension
from automata.hooks import GenerateHooks
from automata.website._theme import extension_from_entry_point


@fixture
def config(tmpsite):
    return automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )


@fixture
def hooks():
    h = GenerateHooks()
    ext = extension_from_entry_point("default", config={
        "short_title": "DSC 40B",
        "long_title": "Theoretical Foundations of Data Science II",
        "navigation": [],
        "rebuild_tailwind": False,
    })
    apply_extension(ext, h)
    return h
