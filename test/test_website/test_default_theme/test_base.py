"""Tests for the default theme's page template (base.html)."""

import re

from conftest import render


def test_lucide_is_pinned_and_deferred(tmpsite, theme):
    # unpkg's @latest is a short-cached redirect, and a script that isn't
    # deferred blocks rendering the page
    tmpsite.make_page("index.md", "# Home")

    render(tmpsite, theme=theme)

    output = tmpsite.get_output("index.html")
    script = re.search(r'<script[^>]*src="https://unpkg.com/lucide[^"]*"[^>]*>', output)
    assert script is not None
    assert "defer" in script[0]
    assert "@latest" not in script[0]
    assert re.search(r"lucide@\d+\.\d+\.\d+/", script[0])


def test_lucide_icons_are_created_once_the_deferred_script_has_run(tmpsite, theme):
    tmpsite.make_page("index.md", "# Home")

    render(tmpsite, theme=theme)

    output = tmpsite.get_output("index.html")
    # DOMContentLoaded fires after deferred scripts have run
    assert re.search(
        r"addEventListener\(\s*['\"]DOMContentLoaded['\"],.*lucide\.createIcons\(\)",
        output,
    )
