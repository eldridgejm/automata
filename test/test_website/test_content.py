"""Tests for loading pages and static content from a content directory."""

import pytest

from automata.exceptions import Error
from automata.website import Page, load_content_directory


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def test_markdown_and_html_files_are_pages_keyed_by_output_path(tmp_path):
    content = tmp_path / "content"
    _write(content / "index.md", "# Home")
    _write(content / "about.html", "<h1>About</h1>")
    _write(content / "notes" / "week-01.md", "# Week 1")

    pages, static = load_content_directory(content, content / "materials")

    assert pages == {
        "index.html": Page("# Home", content / "index.md"),
        "about.html": Page("<h1>About</h1>", content / "about.html"),
        "notes/week-01.html": Page("# Week 1", content / "notes" / "week-01.md"),
    }
    assert static == {}


def test_other_files_are_static_content_read_as_bytes(tmp_path):
    content = tmp_path / "content"
    _write(content / "images" / "logo.png", b"\x89PNG\r\n")
    _write(content / "style.css", "body {}")

    pages, static = load_content_directory(content, content / "materials")

    assert pages == {}
    assert static == {"images/logo.png": b"\x89PNG\r\n", "style.css": b"body {}"}


def test_no_render_files_are_static_with_the_suffix_removed(tmp_path):
    content = tmp_path / "content"
    _write(content / "raw.html.no_render", "<p>${ not interpolated }</p>")

    pages, static = load_content_directory(content, content / "materials")

    assert pages == {}
    assert static == {"raw.html": b"<p>${ not interpolated }</p>"}


def test_a_file_named_only_with_the_no_render_suffix_is_static_as_is(tmp_path):
    content = tmp_path / "content"
    _write(content / ".no_render", "x")
    _write(content / "notes.no_render", "x")

    _, static = load_content_directory(content, content / "materials")

    # "notes.no_render" has only one suffix, so it is not a no-render file
    assert "notes.no_render" in static


def test_no_render_suffix_of_none_renders_everything_by_extension(tmp_path):
    content = tmp_path / "content"
    _write(content / "raw.html.no_render", "x")

    pages, static = load_content_directory(
        content, content / "materials", no_render_suffix=None
    )

    assert pages == {}
    assert static == {"raw.html.no_render": b"x"}


def test_the_materials_directory_is_skipped(tmp_path):
    content = tmp_path / "content"
    _write(content / "index.md", "# Home")
    _write(content / "materials" / "materials.json", "{}")
    _write(content / "materials" / "hw01" / "homework.md", "# HW")

    pages, static = load_content_directory(content, content / "materials")

    assert pages == {"index.html": Page("# Home", content / "index.md")}
    assert static == {}


@pytest.mark.parametrize(
    "first, second, output",
    [
        ("about.md", "about.html", "about.html"),
        ("data.csv", "data.csv.no_render", "data.csv"),
        ("page.html.no_render", "page.md", "page.html"),
    ],
)
def test_two_files_with_the_same_output_path_are_an_error(
    tmp_path, first, second, output
):
    content = tmp_path / "content"
    _write(content / first, "one")
    _write(content / second, "two")

    with pytest.raises(Error) as excinfo:
        load_content_directory(content, content / "materials")

    message = str(excinfo.value)
    assert str(content / first) in message
    assert str(content / second) in message
    assert f"would both become {output}" in message
