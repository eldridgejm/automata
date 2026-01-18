"""Tests for the Extension class and merge_extensions function."""

from pathlib import Path

import pytest

from automata import Extension, merge_extensions

# Extension.from_directory ========================================================


def test_from_directory_reads_templates_and_static_files(tmp_path: Path) -> None:
    """Test that from_directory reads templates and static files."""
    extension_dir = tmp_path / "extension"
    templates_dir = extension_dir / "templates"
    static_dir = extension_dir / "static"

    (templates_dir / "partials").mkdir(parents=True)
    static_dir.mkdir(parents=True)

    (templates_dir / "index.html").write_text("Index template")
    (templates_dir / "partials" / "nav.html").write_text("Nav template")
    (static_dir / "style.css").write_text("body { color: black; }")
    (static_dir / "images").mkdir()
    (static_dir / "images" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    extension = Extension.from_directory(extension_dir)

    assert extension.templates == {
        "index.html": "Index template",
        "partials/nav.html": "Nav template",
    }
    assert set(extension.static_files.keys()) == {"style.css", "images/logo.png"}
    assert extension.static_files["style.css"].read_text() == "body { color: black; }"
    assert (
        extension.static_files["images/logo.png"].read_bytes() == b"\x89PNG\r\n\x1a\n"
    )


def test_from_directory_skips_hidden_files_and_directories(tmp_path: Path) -> None:
    """Test that hidden files and directories are skipped."""
    extension_dir = tmp_path / "extension"
    templates_dir = extension_dir / "templates"
    static_dir = extension_dir / "static"

    (templates_dir / ".hidden").mkdir(parents=True)
    static_dir.mkdir(parents=True)

    (templates_dir / ".hidden.html").write_text("Hidden template")
    (templates_dir / ".hidden" / "secret.html").write_text("Secret template")
    (templates_dir / "visible.html").write_text("Visible template")

    (static_dir / ".hidden.txt").write_text("Hidden static")
    (static_dir / ".hidden").mkdir()
    (static_dir / ".hidden" / "secret.txt").write_text("Secret static")
    (static_dir / "visible.txt").write_text("Visible static")

    extension = Extension.from_directory(extension_dir)

    assert extension.templates == {"visible.html": "Visible template"}
    assert set(extension.static_files.keys()) == {"visible.txt"}


def test_from_directory_allows_missing_templates_by_default(tmp_path: Path) -> None:
    """Test that templates/ is optional by default."""
    extension_dir = tmp_path / "extension"
    static_dir = extension_dir / "static"
    static_dir.mkdir(parents=True)
    (static_dir / "style.css").write_text("body {}")

    extension = Extension.from_directory(extension_dir)

    assert extension.templates == {}
    assert "style.css" in extension.static_files


def test_from_directory_requires_templates_when_specified(tmp_path: Path) -> None:
    """Test that templates/ is required when require_templates=True."""
    extension_dir = tmp_path / "extension"
    extension_dir.mkdir()

    with pytest.raises(ValueError, match="templates"):
        Extension.from_directory(extension_dir, require_templates=True)


def test_from_directory_allows_missing_static_directory(tmp_path: Path) -> None:
    """Test that static/ is optional."""
    extension_dir = tmp_path / "extension"
    templates_dir = extension_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "index.html").write_text("Index template")

    extension = Extension.from_directory(extension_dir)

    assert extension.templates == {"index.html": "Index template"}
    assert extension.static_files == {}


def test_from_directory_loads_elements_package(tmp_path: Path) -> None:
    """Test that elements are loaded from elements/__init__.py."""
    extension_dir = tmp_path / "extension"
    templates_dir = extension_dir / "templates"
    elements_dir = extension_dir / "elements"
    templates_dir.mkdir(parents=True)
    elements_dir.mkdir(parents=True)

    (templates_dir / "base.html").write_text("<html>${ body }</html>")
    (elements_dir / "__init__.py").write_text(
        "def simple_element(config, context):\n"
        "    return f\"Hello {config['label']}\"\n"
        "\n"
        'elements = {"simple": simple_element}\n'
    )

    extension = Extension.from_directory(extension_dir)

    assert "simple" in extension.elements
    assert extension.elements["simple"]({"label": "World"}, None) == "Hello World"


def test_from_directory_loads_schema_from_schema_json(tmp_path: Path) -> None:
    """Test that schema is loaded from schema.json if present."""
    extension_dir = tmp_path / "extension"
    extension_dir.mkdir(parents=True)

    schema = {
        "type": "dict",
        "required_keys": {"title": {"type": "string"}},
        "optional_keys": {"subtitle": {"type": "string", "default": "Default"}},
    }
    (extension_dir / "schema.json").write_text(
        '{"type": "dict", "required_keys": {"title": {"type": "string"}}, '
        '"optional_keys": {"subtitle": {"type": "string", "default": "Default"}}}'
    )

    extension = Extension.from_directory(extension_dir)

    assert extension.schema == schema


def test_from_directory_allows_missing_schema_json(tmp_path: Path) -> None:
    """Test that schema is None when schema.json is missing."""
    extension_dir = tmp_path / "extension"
    extension_dir.mkdir()

    extension = Extension.from_directory(extension_dir)

    assert extension.schema is None


def test_from_directory_raises_on_invalid_json_in_schema_json(tmp_path: Path) -> None:
    """Test that ValueError is raised for malformed JSON."""
    extension_dir = tmp_path / "extension"
    extension_dir.mkdir(parents=True)

    (extension_dir / "schema.json").write_text('{"type": "dict"')

    with pytest.raises(ValueError, match="Invalid JSON in schema.json"):
        Extension.from_directory(extension_dir)


def test_from_directory_raises_on_invalid_schema_in_schema_json(tmp_path: Path) -> None:
    """Test that ValueError is raised for invalid schema."""
    extension_dir = tmp_path / "extension"
    extension_dir.mkdir(parents=True)

    (extension_dir / "schema.json").write_text('{"invalid_key": "value"}')

    with pytest.raises(ValueError, match="Extension configuration schema is invalid"):
        Extension.from_directory(extension_dir)


def test_from_directory_raises_on_nonexistent_directory() -> None:
    """Test that ValueError is raised for nonexistent directory."""
    with pytest.raises(ValueError, match="does not exist"):
        Extension.from_directory(Path("/nonexistent/path"))


# Extension.from_entry_point ======================================================


def test_from_entry_point_loads_default_theme() -> None:
    """Test that from_entry_point can load the default theme."""
    extension = Extension.from_entry_point("default", group="automata.website.themes")

    assert "base.html" in extension.templates
    assert extension.templates["base.html"]  # Should have content


def test_from_entry_point_raises_on_unknown_entry_point() -> None:
    """Test that KeyError is raised for unknown entry point."""
    with pytest.raises(KeyError):
        Extension.from_entry_point("nonexistent-extension")


# Extension.from_spec =============================================================


def test_from_spec_loads_from_path_with_separator(tmp_path: Path) -> None:
    """Test that from_spec loads from directory when path contains separator."""
    extension_dir = tmp_path / "extension"
    templates_dir = extension_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "test.html").write_text("Test template")

    # Use the full path (which contains separators)
    extension = Extension.from_spec(str(extension_dir))

    assert extension.templates == {"test.html": "Test template"}


def test_from_spec_loads_from_entry_point_when_no_separator() -> None:
    """Test that from_spec loads from entry point when no path separator."""
    extension = Extension.from_spec("default", group="automata.website.themes")

    assert "base.html" in extension.templates


# merge_extensions ================================================================


def test_merge_extensions_combines_templates() -> None:
    """Test that merge_extensions combines templates from multiple extensions."""
    extension_a = Extension(templates={"a.html": "A", "shared.html": "A's shared"})
    extension_b = Extension(templates={"b.html": "B", "shared.html": "B's shared"})

    merged = merge_extensions([extension_a, extension_b])

    assert merged.templates == {
        "a.html": "A",
        "b.html": "B",
        "shared.html": "B's shared",  # B overrides A
    }


def test_merge_extensions_combines_static_files() -> None:
    """Test that merge_extensions combines static files from multiple extensions."""
    extension_a = Extension(static_files={"a.css": "A", "shared.css": "A's shared"})
    extension_b = Extension(static_files={"b.css": "B", "shared.css": "B's shared"})

    merged = merge_extensions([extension_a, extension_b])

    assert merged.static_files == {
        "a.css": "A",
        "b.css": "B",
        "shared.css": "B's shared",  # B overrides A
    }


def test_merge_extensions_combines_elements() -> None:
    """Test that merge_extensions combines elements from multiple extensions."""

    def element_a():
        return "A"

    def element_b():
        return "B"

    def shared_a():
        return "A's shared"

    def shared_b():
        return "B's shared"

    extension_a = Extension(elements={"a": element_a, "shared": shared_a})
    extension_b = Extension(elements={"b": element_b, "shared": shared_b})

    merged = merge_extensions([extension_a, extension_b])

    assert set(merged.elements.keys()) == {"a", "b", "shared"}
    assert merged.elements["a"]() == "A"
    assert merged.elements["b"]() == "B"
    assert merged.elements["shared"]() == "B's shared"  # B overrides A


def test_merge_extensions_returns_none_schema() -> None:
    """Test that merged extension has no schema."""
    extension_a = Extension(schema={"type": "string"})
    extension_b = Extension(schema={"type": "number"})

    merged = merge_extensions([extension_a, extension_b])

    assert merged.schema is None


def test_merge_extensions_with_empty_list() -> None:
    """Test that merge_extensions with empty list returns empty extension."""
    merged = merge_extensions([])

    assert merged.templates == {}
    assert merged.static_files == {}
    assert merged.elements == {}
    assert merged.schema is None


def test_merge_extensions_with_single_extension() -> None:
    """Test that merge_extensions with single extension returns equivalent extension."""
    extension = Extension(
        templates={"a.html": "A"},
        static_files={"a.css": "A"},
        elements={"a": lambda: "A"},
    )

    merged = merge_extensions([extension])

    assert merged.templates == extension.templates
    assert merged.static_files == extension.static_files
    assert set(merged.elements.keys()) == set(extension.elements.keys())
    assert merged.schema is None  # Even if original had schema, merged doesn't


def test_merge_extensions_preserves_order() -> None:
    """Test that later extensions override earlier ones."""
    extension_1 = Extension(templates={"file.html": "1"})
    extension_2 = Extension(templates={"file.html": "2"})
    extension_3 = Extension(templates={"file.html": "3"})

    merged = merge_extensions([extension_1, extension_2, extension_3])

    assert merged.templates["file.html"] == "3"


# Python package extensions =======================================================


def test_from_directory_loads_python_package_extension(tmp_path: Path) -> None:
    """Test that from_directory loads a Python package with a extension attribute.

    When a directory contains __init__.py and exports a `extension` attribute,
    it should be loaded as a Python package rather than using the filesystem
    extension structure (templates/, static/, etc.).
    """
    extension_dir = tmp_path / "my_extension"
    extension_dir.mkdir()

    # Create foo.py with a templates dictionary
    (extension_dir / "foo.py").write_text(
        "templates = {\n"
        '    "page.html": "<html><body>{{ content }}</body></html>",\n'
        '    "header.html": "<header>My Site</header>",\n'
        "}\n"
    )

    # Create __init__.py that imports from foo.py and creates a Extension instance
    (extension_dir / "__init__.py").write_text(
        "from automata import Extension\n"
        "from .foo import templates\n"
        "\n"
        "extension = Extension(templates=templates)\n"
    )

    extension = Extension.from_directory(extension_dir)

    assert extension.templates == {
        "page.html": "<html><body>{{ content }}</body></html>",
        "header.html": "<header>My Site</header>",
    }
    assert extension.static_files == {}
    assert extension.elements == {}


def test_from_directory_raises_if_package_has_no_extension_attribute(
    tmp_path: Path,
) -> None:
    """Test that from_directory raises if __init__.py has no extension attribute.

    When a directory contains __init__.py but does NOT export an `extension`
    attribute, a ValueError should be raised.
    """
    extension_dir = tmp_path / "my_extension"
    extension_dir.mkdir()

    # Create __init__.py without an extension attribute
    (extension_dir / "__init__.py").write_text(
        "# This package does not export an extension attribute\nVERSION = '1.0.0'\n"
    )

    with pytest.raises(ValueError, match="must export an 'extension' attribute"):
        Extension.from_directory(extension_dir)


# _load_site_extension =============================================================


def test_load_site_extension_splits_content_by_file_type(tmp_path: Path) -> None:
    """Test that _load_site_extension splits content files by extension.

    Files in content/ with .md or .html extension should go to pages.
    All other files in content/ should go to static_files.
    All files in assets/ should go to static_files.
    """
    from automata._api._load import _load_site_extension

    site_dir = tmp_path / "site"
    content_dir = site_dir / "content"
    assets_dir = site_dir / "assets"

    content_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True)

    # Create various content files
    (content_dir / "index.md").write_text("# Home")
    (content_dir / "about.html").write_text("<h1>About</h1>")
    (content_dir / "data.json").write_text('{"key": "value"}')
    (content_dir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (content_dir / "readme.txt").write_text("Read me!")

    # Create a subdirectory with mixed content
    (content_dir / "docs").mkdir()
    (content_dir / "docs" / "guide.md").write_text("# Guide")
    (content_dir / "docs" / "config.yaml").write_text("key: value")

    # Create asset files
    (assets_dir / "logo.svg").write_text("<svg></svg>")
    (assets_dir / "styles.css").write_text("body {}")

    # Load the site extension
    extension = _load_site_extension(site_dir)

    # Verify pages contains only .md and .html files
    assert set(extension.pages.keys()) == {
        "index.md",
        "about.html",
        "docs/guide.md",
    }

    # Verify static_files contains non-renderable content files and all assets
    assert set(extension.static_files.keys()) == {
        "data.json",
        "image.png",
        "readme.txt",
        "docs/config.yaml",
        "logo.svg",
        "styles.css",
    }

    # Verify the content is accessible
    assert extension.pages["index.md"].read_text() == "# Home"
    assert extension.static_files["data.json"].read_text() == '{"key": "value"}'
    assert extension.static_files["logo.svg"].read_text() == "<svg></svg>"
