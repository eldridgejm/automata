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
    return theme_dir


@pytest.fixture
def build_dir(tmp_path):
    build_dir = tmp_path / "_build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text('<p class="bg-fuchsia-500">Hi</p>')
    return build_dir


@pytest.fixture
def warnings(caplog):
    """Warnings logged by the Tailwind rebuild."""
    caplog.set_level(logging.WARNING, logger=_tailwind.__name__)
    return lambda: [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]


# rebuild_css ==========================================================================


def test_rebuild_css_runs_the_tailwind_cli_from_the_build_directory(
    build_dir, theme_dir
):
    run = _Recorder()

    rebuild_css(build_dir, {}, run=run, theme_directory=theme_dir)

    ((cmd, kwargs),) = run.calls
    assert cmd == [
        "npx",
        "@tailwindcss/cli",
        "-i",
        str(theme_dir / "style.input.css"),
        "-o",
        str(build_dir / "static" / "style.css"),
    ]
    assert kwargs["cwd"] == str(build_dir)
    assert kwargs["check"] is True


def test_rebuild_css_creates_the_output_directory(build_dir, theme_dir):
    rebuild_css(build_dir, {}, run=_Recorder(), theme_directory=theme_dir)

    assert (build_dir / "static").is_dir()


def test_rebuild_css_does_nothing_when_disabled(build_dir, theme_dir, warnings):
    run = _Recorder()

    rebuild_css(
        build_dir, {"rebuild_tailwind": False}, run=run, theme_directory=theme_dir
    )

    assert run.calls == []
    assert warnings() == []


def test_rebuild_css_without_npx_warns_and_keeps_the_prebuilt_css(
    build_dir, theme_dir, warnings
):
    rebuild_css(
        build_dir,
        {},
        run=_raising(FileNotFoundError(2, "No such file or directory", "npx")),
        theme_directory=theme_dir,
    )

    assert any("npx not found" in message for message in warnings())


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, "npx", stderr="bad css"),
        subprocess.TimeoutExpired("npx", 30),
    ],
)
def test_rebuild_css_warns_when_the_cli_fails(build_dir, theme_dir, warnings, error):
    rebuild_css(build_dir, {}, run=_raising(error), theme_directory=theme_dir)

    assert any("Failed to rebuild Tailwind CSS" in m for m in warnings())


def test_rebuild_css_without_input_css_warns_and_does_not_run(
    build_dir, tmp_path, warnings
):
    empty_theme = tmp_path / "empty_theme"
    empty_theme.mkdir()
    run = _Recorder()

    rebuild_css(build_dir, {}, run=run, theme_directory=empty_theme)

    assert run.calls == []
    assert any("style.input.css" in message for message in warnings())


def test_theme_directory_is_the_default_theme_and_has_its_input_css():
    assert (THEME_DIRECTORY / "style.input.css").is_file()
    assert (THEME_DIRECTORY / "templates" / "page.html").is_file()


# real Tailwind ========================================================================


@pytest.mark.integration
@pytest.mark.skipif(
    shutil.which("npx") is None or not (THEME_DIRECTORY / "node_modules").is_dir(),
    reason="needs npx and the theme's Node packages (run `npm install` in the theme)",
)
def test_rebuild_css_includes_classes_used_in_the_built_pages(build_dir):
    rebuild_css(build_dir, {})

    assert "bg-fuchsia-500" in (build_dir / "static" / "style.css").read_text()
