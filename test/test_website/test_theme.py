import importlib.metadata as metadata
from pathlib import Path

import pytest

from automata.exceptions import Error
from automata.extensions import (
    THEMES_GROUP,
    Extension,
    apply_extension,
    extension_from_directory,
    extension_from_entry_point,
)
from automata.hooks import RenderHooks, WebsiteInputs


def _collect(ext: Extension) -> WebsiteInputs:
    """Helper: apply extension to hooks, fire on_render_collect, return inputs."""
    hooks = RenderHooks()
    apply_extension(ext, hooks)
    return hooks.on_render_collect(WebsiteInputs())


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


def test_from_directory_requires_templates_directory(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()

    with pytest.raises(Error):
        extension_from_directory("test", theme_dir)


# extension_from_entry_point ===========================================================


_DEFAULT_THEME_CONFIG = {
    "short_title": "DSC 40B",
    "long_title": "Theoretical Foundations of Data Science II",
    "rebuild_tailwind": False,
}


def test_default_theme_is_registered_as_a_theme() -> None:
    theme_eps = metadata.entry_points().select(group=THEMES_GROUP)
    assert "default" in theme_eps.names

    ext = extension_from_entry_point(
        "default", config=_DEFAULT_THEME_CONFIG, group=THEMES_GROUP
    )
    inputs = _collect(ext)

    assert ext.name == "default"
    assert "page.html" in inputs.templates


def test_default_theme_requires_titles() -> None:
    with pytest.raises(Error) as excinfo:
        extension_from_entry_point("default", group=THEMES_GROUP)

    assert "short_title" in str(excinfo.value)


def test_default_theme_builds_independent_extensions_per_config() -> None:
    first = extension_from_entry_point(
        "default", config=_DEFAULT_THEME_CONFIG, group=THEMES_GROUP
    )
    second = extension_from_entry_point(
        "default",
        config={**_DEFAULT_THEME_CONFIG, "short_title": "DSC 80"},
        group=THEMES_GROUP,
    )

    assert first.config["short_title"] == "DSC 40B"
    assert second.config["short_title"] == "DSC 80"


# require_templates parameter ==========================================================


def test_from_directory_requires_templates_directory_by_default(tmp_path) -> None:
    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()

    with pytest.raises(Error, match="templates"):
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

    ext = extension_from_directory("test", theme_dir, config={"title": "Hi"})

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

    with pytest.raises(Error, match="Invalid JSON in schema.json"):
        extension_from_directory("test", theme_dir)


def test_from_directory_raises_on_invalid_schema_in_schema_json(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    (theme_dir / "schema.json").write_text('{"invalid_key": "value"}')

    with pytest.raises(Error, match="Theme configuration schema is invalid"):
        extension_from_directory("test", theme_dir)


# hooks.py loading =============================================================


def test_from_directory_loads_script_hooks(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    hooks_dir = theme_dir / "hooks"
    templates_dir.mkdir(parents=True)
    hooks_dir.mkdir()
    (templates_dir / "base.html").write_text("<html></html>")
    (hooks_dir / "on_render_post").write_text("cat > /dev/null")
    (hooks_dir / "on_build_artifact_success").write_text("cat > /dev/null")

    ext = extension_from_directory("test", theme_dir)

    assert "on_render_post" in ext.hooks
    assert "on_build_artifact_success" in ext.hooks


def test_from_directory_works_without_hooks_dir(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    ext = extension_from_directory("test", theme_dir)

    # only on_render_collect should be present (no script hooks)
    assert list(ext.hooks.keys()) == ["on_render_collect"]


def test_from_directory_ignores_empty_hook_scripts(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    templates_dir = theme_dir / "templates"
    hooks_dir = theme_dir / "hooks"
    templates_dir.mkdir(parents=True)
    hooks_dir.mkdir()
    (templates_dir / "base.html").write_text("<html></html>")
    (hooks_dir / "on_render_post").write_text("")  # empty script

    ext = extension_from_directory("test", theme_dir)

    assert "on_render_post" not in ext.hooks


def test_from_directory_raises_on_unknown_hook_script(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    (theme_dir / "templates").mkdir(parents=True)
    (theme_dir / "hooks").mkdir()
    (theme_dir / "hooks" / "on_generate_post").write_text("cat > /dev/null")

    with pytest.raises(Error) as excinfo:
        extension_from_directory("test", theme_dir)

    message = str(excinfo.value)
    assert "on_generate_post" in message
    assert "on_render_post" in message  # lists the valid names


def test_from_directory_raises_on_hook_script_for_pipeline_hook(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    (theme_dir / "templates").mkdir(parents=True)
    (theme_dir / "hooks").mkdir()
    (theme_dir / "hooks" / "on_render_collect").write_text("cat > /dev/null")

    with pytest.raises(Error) as excinfo:
        extension_from_directory("test", theme_dir)

    assert "on_render_collect" in str(excinfo.value)


def test_from_directory_loads_renamed_hook_scripts(tmp_path: Path) -> None:
    theme_dir = tmp_path / "theme"
    (theme_dir / "templates").mkdir(parents=True)
    (theme_dir / "hooks").mkdir()
    (theme_dir / "hooks" / "on_render_pre").write_text("cat > /dev/null")
    (theme_dir / "hooks" / "on_build_artifact_success").write_text("cat > /dev/null")

    ext = extension_from_directory("test", theme_dir)

    assert "on_render_pre" in ext.hooks
    assert "on_build_artifact_success" in ext.hooks


def _run_render_post(ext, build_directory):
    """Apply an extension to fresh hooks and fire on_render_post."""
    from automata.hooks import Hooks, RenderPostHookArgs

    hooks = Hooks()
    apply_extension(ext, hooks)
    hooks.on_render_post(RenderPostHookArgs(build_directory=build_directory))


def test_script_hooks_run_in_project_directory(tmp_path: Path, monkeypatch) -> None:
    # given: the process is running somewhere other than the project
    project = tmp_path / "project"
    ext_dir = project / "extensions" / "tools"
    (ext_dir / "hooks").mkdir(parents=True)
    (ext_dir / "hooks" / "on_render_post").write_text("cat > /dev/null && touch ran")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    ext = extension_from_directory(
        "tools", ext_dir, require_templates=False, project_directory=project
    )

    # when
    _run_render_post(ext, project / "_build")

    # then
    assert (project / "ran").exists()
    assert not (elsewhere / "ran").exists()


def test_script_hooks_receive_project_and_extension_directories(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    ext_dir = project / "extensions" / "tools"
    (ext_dir / "hooks").mkdir(parents=True)
    (ext_dir / "hooks" / "on_render_post").write_text(
        'cat > /dev/null && echo "$AUTOMATA_PROJECT_DIR" > project.txt '
        '&& echo "$AUTOMATA_EXTENSION_DIR" > extension.txt'
    )

    ext = extension_from_directory(
        "tools", ext_dir, require_templates=False, project_directory=project
    )
    _run_render_post(ext, project / "_build")

    assert (project / "project.txt").read_text().strip() == str(project)
    assert (project / "extension.txt").read_text().strip() == str(ext_dir)
