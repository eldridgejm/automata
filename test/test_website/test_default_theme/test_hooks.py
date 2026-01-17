"""Tests for default theme's post-build hook."""

import pathlib
import subprocess
from unittest import mock

import pytest

from automata.website.themes.default import hooks

# _is_npx_available tests ==================================================


def test_is_npx_available_returns_true_when_npx_exists():
    """Test that _is_npx_available returns True when npx is available."""
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0)
        assert hooks._is_npx_available() is True
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["npx", "--version"]


def test_is_npx_available_returns_false_when_npx_not_found():
    """Test that _is_npx_available returns False when npx is not found."""
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        assert hooks._is_npx_available() is False


def test_is_npx_available_returns_false_on_subprocess_error():
    """Test that _is_npx_available returns False on subprocess errors."""
    with mock.patch("subprocess.run", side_effect=subprocess.SubprocessError):
        assert hooks._is_npx_available() is False


def test_is_npx_available_returns_false_on_timeout():
    """Test that _is_npx_available returns False on timeout."""
    with mock.patch("subprocess.run", side_effect=TimeoutError):
        assert hooks._is_npx_available() is False


# _get_theme_directory tests ================================================


def test_get_theme_directory_returns_path():
    """Test that _get_theme_directory returns a valid path."""
    theme_dir = hooks._get_theme_directory()
    assert theme_dir is not None
    assert isinstance(theme_dir, pathlib.Path)
    assert theme_dir.exists()
    assert theme_dir.is_dir()


def test_get_theme_directory_contains_style_input():
    """Test that the theme directory contains style.input.css."""
    theme_dir = hooks._get_theme_directory()
    assert theme_dir is not None
    style_input = theme_dir / "style.input.css"
    assert style_input.exists()


# _rebuild_tailwind tests ===================================================


def test_rebuild_tailwind_calls_npx_with_correct_args(tmp_path):
    """Test that _rebuild_tailwind calls npx with correct arguments."""
    input_css = tmp_path / "input.css"
    output_css = tmp_path / "output" / "style.css"
    content_dir = tmp_path / "content"

    input_css.write_text("@import 'tailwindcss';")
    content_dir.mkdir()

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0, stderr="")

        hooks._rebuild_tailwind(input_css, output_css, content_dir)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "npx"
        assert args[1] == "@tailwindcss/cli"
        assert "-i" in args
        assert str(input_css) in args
        assert "-o" in args
        assert str(output_css) in args
        # Verify cwd is set to content_dir for Tailwind v4 scanning
        assert mock_run.call_args.kwargs["cwd"] == str(content_dir)


def test_rebuild_tailwind_creates_output_directory(tmp_path):
    """Test that _rebuild_tailwind creates output directory if it doesn't exist."""
    input_css = tmp_path / "input.css"
    output_css = tmp_path / "nested" / "output" / "style.css"
    content_dir = tmp_path / "content"

    input_css.write_text("@import 'tailwindcss';")
    content_dir.mkdir()

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0, stderr="")

        hooks._rebuild_tailwind(input_css, output_css, content_dir)

        assert output_css.parent.exists()
        assert output_css.parent.is_dir()


def test_rebuild_tailwind_raises_on_cli_failure(tmp_path):
    """Test that _rebuild_tailwind raises RuntimeError when CLI fails."""
    input_css = tmp_path / "input.css"
    output_css = tmp_path / "output" / "style.css"
    content_dir = tmp_path / "content"

    input_css.write_text("@import 'tailwindcss';")
    content_dir.mkdir()

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=1, stderr="Error occurred")

        with pytest.raises(RuntimeError, match="Tailwind CLI failed"):
            hooks._rebuild_tailwind(input_css, output_css, content_dir)


def test_rebuild_tailwind_raises_on_subprocess_check_error(tmp_path):
    """Test that _rebuild_tailwind raises when subprocess.run raises."""
    input_css = tmp_path / "input.css"
    output_css = tmp_path / "output" / "style.css"
    content_dir = tmp_path / "content"

    input_css.write_text("@import 'tailwindcss';")
    content_dir.mkdir()

    with mock.patch(
        "subprocess.run", side_effect=subprocess.CalledProcessError(1, "npx")
    ):
        with pytest.raises(subprocess.CalledProcessError):
            hooks._rebuild_tailwind(input_css, output_css, content_dir)


# post_generate integration tests ==============================================


def _make_hook_context(build_directory: str, vars: dict | None = None) -> dict:
    """Create a hook context dict for testing."""
    return {
        "config": {
            "content_directory": "website",
            "build_directory": build_directory,
            "materials_directory_name": "materials",
            "base_path": "/",
        },
        "materials": "{}",
        "current_time": "2024-01-01T00:00:00",
        "vars": vars or {},
        "build_directory": build_directory,
    }


def test_post_generate_skips_when_npx_not_available():
    """Test that post_generate gracefully skips when npx is not available."""
    context = _make_hook_context("/tmp/build")

    with mock.patch.object(hooks, "_is_npx_available", return_value=False):
        with mock.patch("automata.website.themes.default.hooks.logger") as mock_logger:
            # Should not raise, just warn
            result = hooks._post_generate(context)
            assert result == {}
            mock_logger.warning.assert_called_once()
            assert "npx not found" in mock_logger.warning.call_args[0][0]


def test_post_generate_skips_when_theme_dir_not_found():
    """Test that post_generate skips when theme directory cannot be found."""
    context = _make_hook_context("/tmp/build")

    with mock.patch.object(hooks, "_is_npx_available", return_value=True):
        with mock.patch.object(hooks, "_get_theme_directory", return_value=None):
            with mock.patch(
                "automata.website.themes.default.hooks.logger"
            ) as mock_logger:
                result = hooks._post_generate(context)
                assert result == {}
                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "Could not locate theme directory" in warning_msg


def test_post_generate_skips_when_input_css_missing(tmp_path):
    """Test that post_generate skips when style.input.css is missing."""
    build_dir = tmp_path / "build"
    context = _make_hook_context(str(build_dir))

    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()

    with mock.patch.object(hooks, "_is_npx_available", return_value=True):
        with mock.patch.object(hooks, "_get_theme_directory", return_value=theme_dir):
            with mock.patch(
                "automata.website.themes.default.hooks.logger"
            ) as mock_logger:
                result = hooks._post_generate(context)
                assert result == {}
                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "Tailwind input file not found" in warning_msg


def test_post_generate_handles_rebuild_errors_gracefully(tmp_path):
    """Test that post_generate handles errors during rebuild gracefully."""
    build_dir = tmp_path / "build"
    context = _make_hook_context(str(build_dir))

    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()
    (theme_dir / "style.input.css").write_text("@import 'tailwindcss';")

    with mock.patch.object(hooks, "_is_npx_available", return_value=True):
        with mock.patch.object(hooks, "_get_theme_directory", return_value=theme_dir):
            with mock.patch.object(
                hooks, "_rebuild_tailwind", side_effect=RuntimeError("Build failed")
            ):
                with mock.patch(
                    "automata.website.themes.default.hooks.logger"
                ) as mock_logger:
                    # Should not raise, just warn
                    result = hooks._post_generate(context)
                    assert result == {}
                    assert any(
                        "Failed to rebuild Tailwind CSS" in str(call)
                        for call in mock_logger.warning.call_args_list
                    )


def test_post_generate_calls_rebuild_with_correct_paths(tmp_path):
    """Test that post_generate calls _rebuild_tailwind with correct paths."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    context = _make_hook_context(str(build_dir))

    theme_dir = tmp_path / "theme"
    theme_dir.mkdir()
    input_css = theme_dir / "style.input.css"
    input_css.write_text("@import 'tailwindcss';")

    with mock.patch.object(hooks, "_is_npx_available", return_value=True):
        with mock.patch.object(hooks, "_get_theme_directory", return_value=theme_dir):
            with mock.patch.object(hooks, "_rebuild_tailwind") as mock_rebuild:
                result = hooks._post_generate(context)
                assert result == {}

                mock_rebuild.assert_called_once()
                call_args = mock_rebuild.call_args[0]
                assert call_args[0] == input_css
                assert call_args[1] == build_dir / "static" / "style.css"
                assert call_args[2] == build_dir


def test_post_generate_skips_when_rebuild_disabled_in_vars():
    """Test that post_generate skips rebuild when rebuild_tailwind is False in vars."""
    context = _make_hook_context("/tmp/build", vars={"rebuild_tailwind": False})

    with mock.patch.object(hooks, "_is_npx_available") as mock_npx:
        with mock.patch.object(hooks, "_rebuild_tailwind") as mock_rebuild:
            result = hooks._post_generate(context)
            assert result == {}

            # Should not check for npx or attempt rebuild
            mock_npx.assert_not_called()
            mock_rebuild.assert_not_called()
