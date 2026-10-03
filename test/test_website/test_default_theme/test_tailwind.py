"""Tests for the default theme's Tailwind CSS rebuild."""

import logging
import shutil
import subprocess

import pytest

from automata.builtin.themes.default import _tailwind
from automata.builtin.themes.default._tailwind import THEME_DIRECTORY, rebuild_css


class _Recorder:
    """A fake command runner that records each command and its options."""

    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def _raising(exception):
    """A fake command runner that raises the given exception."""

    def run(cmd, **kwargs):
        raise exception

    return run


@pytest.fixture
def theme_dir(tmp_path):
    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()
    (theme_dir / "style.input.css").write_text('@import "tailwindcss";')
    (theme_dir / "package.json").write_text('{"dependencies": {"tailwindcss": "4"}}')
    return theme_dir


@pytest.fixture
def build_dir(tmp_path):
    build_dir = tmp_path / "_build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text('<p class="bg-fuchsia-500">Hi</p>')
    return build_dir


@pytest.fixture
def rebuild(build_dir, theme_dir, tmp_path):
    """Rebuild the CSS with the given runner, caching in a temporary directory."""
    cache = tmp_path / "cache"

    def rebuild(run, config=None):
        rebuild_css(
            build_dir,
            config or {},
            run=run,
            theme_directory=theme_dir,
            cache_directory=cache,
        )

    rebuild.cache = cache / "default-theme"
    return rebuild


@pytest.fixture
def warnings(caplog):
    """Warnings logged by the Tailwind rebuild."""
    caplog.set_level(logging.WARNING, logger=_tailwind.__name__)
    return lambda: [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]


# rebuild_css ==========================================================================


def test_rebuild_css_installs_the_themes_packages_into_the_cache(rebuild, theme_dir):
    # (the theme's directory may not be writable, as when automata is installed)
    run = _Recorder()

    rebuild(run)

    install, _ = run.calls
    cmd, kwargs = install
    assert cmd[:2] == ["npm", "install"]
    assert kwargs["cwd"] == str(rebuild.cache)
    assert (rebuild.cache / "package.json").read_text() == (
        theme_dir / "package.json"
    ).read_text()


def test_rebuild_css_runs_tailwind_from_the_build_directory(rebuild, build_dir):
    run = _Recorder()

    rebuild(run)

    _, (cmd, kwargs) = run.calls
    # the input CSS is copied next to the packages, so that its imports resolve
    assert cmd == [
        str(rebuild.cache / "node_modules" / ".bin" / "tailwindcss"),
        "-i",
        str(rebuild.cache / "style.input.css"),
        "-o",
        str(build_dir / "static" / "style.css"),
    ]
    assert (rebuild.cache / "style.input.css").read_text() == '@import "tailwindcss";'
    # Tailwind looks for classes in the directory it runs in
    assert kwargs["cwd"] == str(build_dir)
    assert kwargs["check"] is True


def test_rebuild_css_installs_the_packages_only_once(rebuild):
    rebuild(_Recorder())
    run = _Recorder()

    rebuild(run)

    ((cmd, _),) = run.calls
    assert cmd[0].endswith("tailwindcss")


def test_rebuild_css_reinstalls_when_the_themes_packages_change(rebuild, theme_dir):
    rebuild(_Recorder())
    (theme_dir / "package.json").write_text('{"dependencies": {"tailwindcss": "5"}}')
    run = _Recorder()

    rebuild(run)

    assert run.calls[0][0][:2] == ["npm", "install"]


def test_rebuild_css_retries_a_failed_install(rebuild, warnings):
    rebuild(_raising(subprocess.CalledProcessError(1, "npm", stderr="offline")))
    run = _Recorder()

    rebuild(run)

    assert any("Failed to rebuild Tailwind CSS" in m for m in warnings())
    assert run.calls[0][0][:2] == ["npm", "install"]


def test_rebuild_css_creates_the_output_directory(rebuild, build_dir):
    rebuild(_Recorder())

    assert (build_dir / "static").is_dir()


def test_rebuild_css_does_nothing_when_disabled(rebuild, warnings):
    run = _Recorder()

    rebuild(run, {"rebuild_tailwind": False})

    assert run.calls == []
    assert warnings() == []


def test_rebuild_css_without_npm_warns_and_keeps_the_prebuilt_css(rebuild, warnings):
    rebuild(_raising(FileNotFoundError(2, "No such file or directory", "npm")))

    assert any("npm not found" in message for message in warnings())


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, "tailwindcss", stderr="bad css"),
        subprocess.TimeoutExpired("tailwindcss", 30),
    ],
)
def test_rebuild_css_warns_when_tailwind_fails(rebuild, warnings, error):
    rebuild(_raising(error))

    assert any("Failed to rebuild Tailwind CSS" in m for m in warnings())


def test_rebuild_css_without_input_css_warns_and_does_not_run(
    build_dir, tmp_path, warnings
):
    empty_theme = tmp_path / "empty_theme"
    empty_theme.mkdir()
    run = _Recorder()

    rebuild_css(
        build_dir,
        {},
        run=run,
        theme_directory=empty_theme,
        cache_directory=tmp_path / "cache",
    )

    assert run.calls == []
    assert any("style.input.css" in message for message in warnings())


def test_theme_directory_is_the_default_theme_and_has_its_input_css():
    assert (THEME_DIRECTORY / "style.input.css").is_file()
    assert (THEME_DIRECTORY / "package.json").is_file()
    assert (THEME_DIRECTORY / "templates" / "page.html").is_file()


# real Tailwind ========================================================================


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("npm") is None, reason="needs npm")
def test_rebuild_css_includes_classes_used_in_the_built_pages(build_dir, tmp_path):
    rebuild_css(build_dir, {}, cache_directory=tmp_path / "cache")

    assert "bg-fuchsia-500" in (build_dir / "static" / "style.css").read_text()
