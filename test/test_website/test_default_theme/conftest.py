"""Shared fixtures for default theme tests."""

from pytest import fixture

import automata.website
from automata._extension import apply_extension
from automata.hooks import GenerateHooks
from automata._extension import extension_from_entry_point


@fixture
def config(tmpsite):
    return automata.website.WebsiteConfig(
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


def generate(config, tmpsite, **kwargs):
    """Helper that loads content and calls generate with pages/static_content."""
    pages, static_content = tmpsite.load_content()
    automata.website.generate(
        config,
        tmpsite.materials_directory,
        pages=pages,
        static_content=static_content,
        **kwargs,
    )
