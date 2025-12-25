import importlib.metadata as metadata
from pathlib import Path

import pytest

from automata.website._theme import Theme

# from_directory ==============================================================


def test_from_directory_reads_templates_and_static_files(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    static_dir = theme_dir / "static"

    (templates_dir / "partials").mkdir(parents=True)
    static_dir.mkdir(parents=True)

    (templates_dir / "index.html").write_text("Index template")
    (templates_dir / "partials" / "nav.html").write_text("Nav template")
    (static_dir / "style.css").write_text("body { color: black; }")
    (static_dir / "images").mkdir()
    (static_dir / "images" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    theme = Theme.from_directory(theme_dir)

    assert theme.templates == {
        "index.html": "Index template",
        "partials/nav.html": "Nav template",
    }
    assert set(theme.static_files.keys()) == {"style.css", "images/logo.png"}
    assert theme.static_files["style.css"].read_text() == "body { color: black; }"
    assert theme.static_files["images/logo.png"].read_bytes() == b"\x89PNG\r\n\x1a\n"


def test_from_directory_skips_hidden_files_and_directories(
    tmp_path: Path,
) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    static_dir = theme_dir / "static"

    (templates_dir / ".hidden").mkdir(parents=True)
    static_dir.mkdir(parents=True)

    (templates_dir / ".hidden.html").write_text("Hidden template")
    (templates_dir / ".hidden" / "secret.html").write_text("Secret template")
    (templates_dir / "visible.html").write_text("Visible template")

    (static_dir / ".hidden.txt").write_text("Hidden static")
    (static_dir / ".hidden").mkdir()
    (static_dir / ".hidden" / "secret.txt").write_text("Secret static")
    (static_dir / "visible.txt").write_text("Visible static")

    theme = Theme.from_directory(theme_dir)

    assert theme.templates == {"visible.html": "Visible template"}
    assert set(theme.static_files.keys()) == {"visible.txt"}


def test_from_directory_allows_missing_static_directory(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "index.html").write_text("Index template")

    theme = Theme.from_directory(theme_dir)

    assert theme.templates == {"index.html": "Index template"}
    assert theme.static_files == {}


def test_from_directory_requires_templates_directory(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()

    with pytest.raises(ValueError):
        Theme.from_directory(theme_dir)


# from_entry_point =====================================================================


def test_default_entry_point_is_registered() -> None:
    """Test that the 'default' theme entry point is registered."""
    # Verify the entry point exists
    entry_points = metadata.entry_points()
    theme_eps = entry_points.select(group="automata.website.themes")

    # Check that "default" is in the registered entry points
    default_ep = theme_eps["default"]
    assert default_ep is not None

    # Verify we can load the theme via the entry point
    theme = Theme.from_entry_point("default")

    # Verify the theme has expected content
    assert "base.html" in theme.templates
    assert theme.templates["base.html"]  # Should have content


# require_templates parameter ==========================================================


def test_from_directory_requires_templates_directory_by_default(tmp_path) -> None:
    """Test that from_directory requires templates/ when require_templates=True."""
    # given
    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()
    # No templates directory at all

    # when / then
    with pytest.raises(ValueError, match="templates"):
        Theme.from_directory(theme_dir)


def test_from_directory_allows_missing_templates_when_not_required(tmp_path) -> None:
    """Test that templates/ is optional when require_templates=False."""
    # given
    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()
    static_dir = theme_dir / "static"
    static_dir.mkdir()
    (static_dir / "style.css").write_text("body {}")

    # when
    theme = Theme.from_directory(theme_dir, require_templates=False)

    # then
    assert theme.templates == {}
    assert "style.css" in theme.static_files
