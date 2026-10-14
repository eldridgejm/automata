"""Tests for the button element."""

from bs4 import BeautifulSoup
from conftest import render


def test_button_is_a_link_without_a_nested_button(tmpsite, theme):
    # given
    tmpsite.make_page(
        "index.html",
        '${ elements.button({"label": "Slides", "url": "slides.pdf"}) }',
    )

    # when
    render(tmpsite, theme=theme)

    # then: one <a>, since a <button> inside an <a> is invalid HTML
    soup = BeautifulSoup(tmpsite.get_output("index.html"), "html.parser")
    link = soup.find("a", href="slides.pdf")
    assert link is not None
    assert link.get_text(strip=True) == "Slides"
    assert soup.find("button", string=lambda s: s and "Slides" in s) is None
