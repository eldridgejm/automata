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


def _themed(**options):
    from automata.extensions import THEMES_GROUP, extension_from_entry_point

    config = {
        "short_title": "T",
        "long_title": "Test",
        "navigation": [],
        "rebuild_tailwind": False,
    }
    return extension_from_entry_point(
        "default", config={**config, **options}, group=THEMES_GROUP
    )


def _page(tmpsite, theme):
    tmpsite.make_page("index.md", "# Home")
    render(tmpsite, theme=theme)
    return tmpsite.get_output("index.html")


def test_math_and_highlighting_are_off_by_default(tmpsite, theme):
    output = _page(tmpsite, theme)

    assert "mathjax" not in output.lower()
    assert "highlight" not in output.lower()


def test_math_loads_mathjax_with_its_delimiters(tmpsite):
    output = _page(tmpsite, _themed(math=True))

    assert re.search(
        r'<script[^>]*id="MathJax-script"[^>]*src="https://cdn.jsdelivr.net/npm/'
        r'mathjax@4[^"]*/tex-mml-chtml.js"',
        output,
    )
    # \( \) inline, and \[ \] and $$ $$ displayed (MathJax's defaults)
    assert r"inlineMath: [['\\(', '\\)']]" in output
    assert r"displayMath: [['\\[', '\\]'], ['$$', '$$']]" in output


def test_highlighting_loads_highlight_js_and_highlights_code_blocks(tmpsite):
    output = _page(tmpsite, _themed(highlight_code=True))

    script = re.search(r'<script[^>]*src="[^"]*highlight\.js/[^"]*"[^>]*>', output)
    assert script is not None
    assert "defer" in script[0]
    assert re.search(r"highlight\.js/\d+\.\d+\.\d+/", script[0])
    assert "hljs.highlightAll()" in output


def test_the_prebuilt_css_has_what_the_theme_uses():
    # the theme's own classes are in the CSS shipped with it (used when
    # Tailwind isn't rebuilt)
    from pathlib import Path

    import automata.builtin.themes.default as default

    css = (
        Path(default.__file__).parent / "static" / "static" / "style.css"
    ).read_text()

    # the people element's layout
    for name in [".size-32", ".object-cover", ".shrink-0"]:
        assert name in css
    # (not-prose is no class of its own: prose's rules leave its contents out)
    assert 'not(:where([class~="not-prose"]' in css
    # highlighted code, light and dark
    assert ".hljs-keyword" in css
    assert ".dark" in css.split(".hljs-keyword", 1)[1]
    # no backticks around inline code
    assert re.search(r"code::before[^}]*content:\s*none", css)
