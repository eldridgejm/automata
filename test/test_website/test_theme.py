import importlib.metadata as metadata
from pathlib import Path

import pytest

from automata._extension import Extension, apply_extension
from automata.hooks import GenerateHooks, WebsiteInputs
from automata._extension import extension_from_directory, extension_from_entry_point


def _collect(ext: Extension) -> WebsiteInputs:
    """Helper: apply extension to hooks, fire on_website_collect, return inputs."""
    hooks = GenerateHooks()
    apply_extension(ext, hooks)
    return hooks.on_website_collect(WebsiteInputs())


# extension_from_directory =============================================================


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

    ext = extension_from_directory("test", theme_dir)
    inputs = _collect(ext)

    assert inputs.templates == {
        "index.html": "Index template",
        "partials/nav.html": "Nav template",
    }
    assert set(inputs.static_files.keys()) == {"style.css", "images/logo.png"}
    assert inputs.static_files["style.css"].read_text() == "body { color: black; }"
    assert inputs.static_files["images/logo.png"].read_bytes() == b"\x89PNG\r\n\x1a\n"


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

    ext = extension_from_directory("test", theme_dir)
    inputs = _collect(ext)

    assert inputs.templates == {"visible.html": "Visible template"}
    assert set(inputs.static_files.keys()) == {"visible.txt"}


def test_from_directory_allows_missing_static_directory(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "index.html").write_text("Index template")

    ext = extension_from_directory("test", theme_dir)
    inputs = _collect(ext)

    assert inputs.templates == {"index.html": "Index template"}
    assert inputs.static_files == {}


def test_from_directory_loads_elements_package(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    elements_dir = theme_dir / "elements"
    templates_dir.mkdir(parents=True)
    elements_dir.mkdir(parents=True)

    (templates_dir / "base.html").write_text("<html>${ body }</html>")
    (elements_dir / "__init__.py").write_text(
        "def simple_element(config, context):\n"
        "    return f\"Hello {config['label']}\"\n"
        "\n"
        'elements = {"simple": simple_element}\n'
    )

    ext = extension_from_directory("test", theme_dir)
    inputs = _collect(ext)

    assert "simple" in inputs.elements
    assert inputs.elements["simple"]({"label": "World"}, None) == "Hello World"


def test_from_directory_requires_templates_directory(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()

    with pytest.raises(ValueError):
        extension_from_directory("test", theme_dir)


# extension_from_entry_point ===========================================================


def test_default_entry_point_is_registered() -> None:
    """Test that the 'default' theme entry point is registered."""
    entry_points = metadata.entry_points()
    theme_eps = entry_points.select(group="automata.themes")

    default_ep = theme_eps["default"]
    assert default_ep is not None

    ext = extension_from_entry_point("default")
    inputs = _collect(ext)

    assert "base.html" in inputs.templates
    assert inputs.templates["base.html"]


# require_templates parameter ==========================================================


def test_from_directory_requires_templates_directory_by_default(tmp_path) -> None:
    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()

    with pytest.raises(ValueError, match="templates"):
        extension_from_directory("test", theme_dir)


def test_from_directory_allows_missing_templates_when_not_required(tmp_path) -> None:
    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()
    static_dir = theme_dir / "static"
    static_dir.mkdir()
    (static_dir / "style.css").write_text("body {}")

    ext = extension_from_directory("test", theme_dir, require_templates=False)
    inputs = _collect(ext)

    assert inputs.templates == {}
    assert "style.css" in inputs.static_files


# schema.json loading ==========================================================


def test_from_directory_loads_schema_from_schema_json(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    schema = {
        "type": "dict",
        "required_keys": {"title": {"type": "string"}},
        "optional_keys": {"subtitle": {"type": "string", "default": "Default"}},
    }
    (theme_dir / "schema.json").write_text(
        '{"type": "dict", "required_keys": {"title": {"type": "string"}}, '
        '"optional_keys": {"subtitle": {"type": "string", "default": "Default"}}}'
    )

    ext = extension_from_directory("test", theme_dir)

    assert ext.schema == schema


def test_from_directory_allows_missing_schema_json(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    ext = extension_from_directory("test", theme_dir)

    assert ext.schema is None


def test_from_directory_raises_on_invalid_json_in_schema_json(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    (theme_dir / "schema.json").write_text('{"type": "dict"')

    with pytest.raises(ValueError, match="Invalid JSON in schema.json"):
        extension_from_directory("test", theme_dir)


def test_from_directory_raises_on_invalid_schema_in_schema_json(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    (theme_dir / "schema.json").write_text('{"invalid_key": "value"}')

    with pytest.raises(ValueError, match="Theme configuration schema is invalid"):
        extension_from_directory("test", theme_dir)


# hooks.py loading =============================================================


def test_from_directory_loads_post_generate_hook(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    (theme_dir / "hooks.py").write_text(
        "def post_generate(config, extension_config):\n    pass\n"
    )

    ext = extension_from_directory("test", theme_dir)

    assert "on_generate_post" in ext.hooks


def test_from_directory_allows_missing_hooks_py(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    ext = extension_from_directory("test", theme_dir)

    assert "on_generate_post" not in ext.hooks


def test_from_directory_raises_on_malformed_hooks_py(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    (theme_dir / "hooks.py").write_text("def pre_generate(config)\n    pass\n")

    with pytest.raises(ValueError, match="Error loading hooks"):
        extension_from_directory("test", theme_dir)


def test_from_directory_raises_on_non_callable_post_generate(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    (theme_dir / "hooks.py").write_text("post_generate = 42\n")

    with pytest.raises(ValueError, match="post_generate.*must be callable"):
        extension_from_directory("test", theme_dir)
