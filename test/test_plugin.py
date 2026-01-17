"""Tests for the Plugin class and merge_plugins function."""

from pathlib import Path

import pytest

from automata import Plugin, merge_plugins

# Plugin.from_directory ========================================================


def test_from_directory_reads_templates_and_static_files(tmp_path: Path) -> None:
    """Test that from_directory reads templates and static files."""
    plugin_dir = tmp_path / "plugin"
    templates_dir = plugin_dir / "templates"
    static_dir = plugin_dir / "static"

    (templates_dir / "partials").mkdir(parents=True)
    static_dir.mkdir(parents=True)

    (templates_dir / "index.html").write_text("Index template")
    (templates_dir / "partials" / "nav.html").write_text("Nav template")
    (static_dir / "style.css").write_text("body { color: black; }")
    (static_dir / "images").mkdir()
    (static_dir / "images" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    plugin = Plugin.from_directory(plugin_dir)

    assert plugin.templates == {
        "index.html": "Index template",
        "partials/nav.html": "Nav template",
    }
    assert set(plugin.static_files.keys()) == {"style.css", "images/logo.png"}
    assert plugin.static_files["style.css"].read_text() == "body { color: black; }"
    assert plugin.static_files["images/logo.png"].read_bytes() == b"\x89PNG\r\n\x1a\n"


def test_from_directory_skips_hidden_files_and_directories(tmp_path: Path) -> None:
    """Test that hidden files and directories are skipped."""
    plugin_dir = tmp_path / "plugin"
    templates_dir = plugin_dir / "templates"
    static_dir = plugin_dir / "static"

    (templates_dir / ".hidden").mkdir(parents=True)
    static_dir.mkdir(parents=True)

    (templates_dir / ".hidden.html").write_text("Hidden template")
    (templates_dir / ".hidden" / "secret.html").write_text("Secret template")
    (templates_dir / "visible.html").write_text("Visible template")

    (static_dir / ".hidden.txt").write_text("Hidden static")
    (static_dir / ".hidden").mkdir()
    (static_dir / ".hidden" / "secret.txt").write_text("Secret static")
    (static_dir / "visible.txt").write_text("Visible static")

    plugin = Plugin.from_directory(plugin_dir)

    assert plugin.templates == {"visible.html": "Visible template"}
    assert set(plugin.static_files.keys()) == {"visible.txt"}


def test_from_directory_allows_missing_templates_by_default(tmp_path: Path) -> None:
    """Test that templates/ is optional by default."""
    plugin_dir = tmp_path / "plugin"
    static_dir = plugin_dir / "static"
    static_dir.mkdir(parents=True)
    (static_dir / "style.css").write_text("body {}")

    plugin = Plugin.from_directory(plugin_dir)

    assert plugin.templates == {}
    assert "style.css" in plugin.static_files


def test_from_directory_requires_templates_when_specified(tmp_path: Path) -> None:
    """Test that templates/ is required when require_templates=True."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    with pytest.raises(ValueError, match="templates"):
        Plugin.from_directory(plugin_dir, require_templates=True)


def test_from_directory_allows_missing_static_directory(tmp_path: Path) -> None:
    """Test that static/ is optional."""
    plugin_dir = tmp_path / "plugin"
    templates_dir = plugin_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "index.html").write_text("Index template")

    plugin = Plugin.from_directory(plugin_dir)

    assert plugin.templates == {"index.html": "Index template"}
    assert plugin.static_files == {}


def test_from_directory_loads_elements_package(tmp_path: Path) -> None:
    """Test that elements are loaded from elements/__init__.py."""
    plugin_dir = tmp_path / "plugin"
    templates_dir = plugin_dir / "templates"
    elements_dir = plugin_dir / "elements"
    templates_dir.mkdir(parents=True)
    elements_dir.mkdir(parents=True)

    (templates_dir / "base.html").write_text("<html>${ body }</html>")
    (elements_dir / "__init__.py").write_text(
        "def simple_element(config, context):\n"
        "    return f\"Hello {config['label']}\"\n"
        "\n"
        'elements = {"simple": simple_element}\n'
    )

    plugin = Plugin.from_directory(plugin_dir)

    assert "simple" in plugin.elements
    assert plugin.elements["simple"]({"label": "World"}, None) == "Hello World"


def test_from_directory_loads_schema_from_schema_json(tmp_path: Path) -> None:
    """Test that schema is loaded from schema.json if present."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir(parents=True)

    schema = {
        "type": "dict",
        "required_keys": {"title": {"type": "string"}},
        "optional_keys": {"subtitle": {"type": "string", "default": "Default"}},
    }
    (plugin_dir / "schema.json").write_text(
        '{"type": "dict", "required_keys": {"title": {"type": "string"}}, '
        '"optional_keys": {"subtitle": {"type": "string", "default": "Default"}}}'
    )

    plugin = Plugin.from_directory(plugin_dir)

    assert plugin.schema == schema


def test_from_directory_allows_missing_schema_json(tmp_path: Path) -> None:
    """Test that schema is None when schema.json is missing."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    plugin = Plugin.from_directory(plugin_dir)

    assert plugin.schema is None


def test_from_directory_raises_on_invalid_json_in_schema_json(tmp_path: Path) -> None:
    """Test that ValueError is raised for malformed JSON."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir(parents=True)

    (plugin_dir / "schema.json").write_text('{"type": "dict"')

    with pytest.raises(ValueError, match="Invalid JSON in schema.json"):
        Plugin.from_directory(plugin_dir)


def test_from_directory_raises_on_invalid_schema_in_schema_json(tmp_path: Path) -> None:
    """Test that ValueError is raised for invalid schema."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir(parents=True)

    (plugin_dir / "schema.json").write_text('{"invalid_key": "value"}')

    with pytest.raises(ValueError, match="Plugin configuration schema is invalid"):
        Plugin.from_directory(plugin_dir)


def test_from_directory_raises_on_nonexistent_directory() -> None:
    """Test that ValueError is raised for nonexistent directory."""
    with pytest.raises(ValueError, match="does not exist"):
        Plugin.from_directory(Path("/nonexistent/path"))


# Plugin.from_entry_point ======================================================


def test_from_entry_point_loads_default_theme() -> None:
    """Test that from_entry_point can load the default theme."""
    plugin = Plugin.from_entry_point("default", group="automata.website.themes")

    assert "base.html" in plugin.templates
    assert plugin.templates["base.html"]  # Should have content


def test_from_entry_point_raises_on_unknown_entry_point() -> None:
    """Test that KeyError is raised for unknown entry point."""
    with pytest.raises(KeyError):
        Plugin.from_entry_point("nonexistent-plugin")


# Plugin.from_spec =============================================================


def test_from_spec_loads_from_path_with_separator(tmp_path: Path) -> None:
    """Test that from_spec loads from directory when path contains separator."""
    plugin_dir = tmp_path / "plugin"
    templates_dir = plugin_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "test.html").write_text("Test template")

    # Use the full path (which contains separators)
    plugin = Plugin.from_spec(str(plugin_dir))

    assert plugin.templates == {"test.html": "Test template"}


def test_from_spec_loads_from_entry_point_when_no_separator() -> None:
    """Test that from_spec loads from entry point when no path separator."""
    plugin = Plugin.from_spec("default", group="automata.website.themes")

    assert "base.html" in plugin.templates


# merge_plugins ================================================================


def test_merge_plugins_combines_templates() -> None:
    """Test that merge_plugins combines templates from multiple plugins."""
    plugin_a = Plugin(templates={"a.html": "A", "shared.html": "A's shared"})
    plugin_b = Plugin(templates={"b.html": "B", "shared.html": "B's shared"})

    merged = merge_plugins([plugin_a, plugin_b])

    assert merged.templates == {
        "a.html": "A",
        "b.html": "B",
        "shared.html": "B's shared",  # B overrides A
    }


def test_merge_plugins_combines_static_files() -> None:
    """Test that merge_plugins combines static files from multiple plugins."""
    plugin_a = Plugin(static_files={"a.css": "A", "shared.css": "A's shared"})
    plugin_b = Plugin(static_files={"b.css": "B", "shared.css": "B's shared"})

    merged = merge_plugins([plugin_a, plugin_b])

    assert merged.static_files == {
        "a.css": "A",
        "b.css": "B",
        "shared.css": "B's shared",  # B overrides A
    }


def test_merge_plugins_combines_elements() -> None:
    """Test that merge_plugins combines elements from multiple plugins."""

    def element_a():
        return "A"

    def element_b():
        return "B"

    def shared_a():
        return "A's shared"

    def shared_b():
        return "B's shared"

    plugin_a = Plugin(elements={"a": element_a, "shared": shared_a})
    plugin_b = Plugin(elements={"b": element_b, "shared": shared_b})

    merged = merge_plugins([plugin_a, plugin_b])

    assert set(merged.elements.keys()) == {"a", "b", "shared"}
    assert merged.elements["a"]() == "A"
    assert merged.elements["b"]() == "B"
    assert merged.elements["shared"]() == "B's shared"  # B overrides A


def test_merge_plugins_returns_none_schema() -> None:
    """Test that merged plugin has no schema."""
    plugin_a = Plugin(schema={"type": "string"})
    plugin_b = Plugin(schema={"type": "number"})

    merged = merge_plugins([plugin_a, plugin_b])

    assert merged.schema is None


def test_merge_plugins_with_empty_list() -> None:
    """Test that merge_plugins with empty list returns empty plugin."""
    merged = merge_plugins([])

    assert merged.templates == {}
    assert merged.static_files == {}
    assert merged.elements == {}
    assert merged.schema is None


def test_merge_plugins_with_single_plugin() -> None:
    """Test that merge_plugins with single plugin returns equivalent plugin."""
    plugin = Plugin(
        templates={"a.html": "A"},
        static_files={"a.css": "A"},
        elements={"a": lambda: "A"},
    )

    merged = merge_plugins([plugin])

    assert merged.templates == plugin.templates
    assert merged.static_files == plugin.static_files
    assert set(merged.elements.keys()) == set(plugin.elements.keys())
    assert merged.schema is None  # Even if original had schema, merged doesn't


def test_merge_plugins_preserves_order() -> None:
    """Test that later plugins override earlier ones."""
    plugin_1 = Plugin(templates={"file.html": "1"})
    plugin_2 = Plugin(templates={"file.html": "2"})
    plugin_3 = Plugin(templates={"file.html": "3"})

    merged = merge_plugins([plugin_1, plugin_2, plugin_3])

    assert merged.templates["file.html"] == "3"
