"""Tests for the publish system."""

from unittest import mock

import pytest

from automata.hooks import PublisherRegistryArgs
from automata.publish import registry
from automata.publish._gh_pages import publish as gh_pages_publish
from automata.publish._scp import publish as scp_publish

# publisher registry ===================================================================


def test_registry_has_builtin_strategies():
    """gh-pages and scp should be registered at import time."""
    all_publishers = registry.all()
    assert "gh-pages" in all_publishers
    assert "scp" in all_publishers


def test_registry_register_and_get():
    """Custom strategies can be registered and retrieved."""

    def sentinel(build_dir, config):
        return None

    registry.register("test-strategy", sentinel)
    assert registry.get("test-strategy") is sentinel
    # clean up
    del registry._registry["test-strategy"]


def test_registry_get_unknown_raises():
    with pytest.raises(KeyError):
        registry.get("nonexistent-strategy")


def test_registry_all_returns_copy():
    """all() returns a copy, not the internal dict."""
    copy = registry.all()
    copy["bogus"] = None
    assert "bogus" not in registry.all()


# gh-pages strategy ====================================================================


def test_gh_pages_publish_calls_git_commands(tmp_path):
    """gh-pages strategy should run git commands to push to a branch."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<h1>Test</h1>")

    calls = []

    def mock_run(*args, **kwargs):
        calls.append(args[0] if args else kwargs.get("args"))
        result = mock.Mock(
            returncode=0, stdout="https://github.com/test/repo.git\n", stderr=""
        )
        # git diff --cached --quiet returns 1 when there are changes
        if args and "diff" in args[0]:
            result.returncode = 1
        return result

    with mock.patch("automata.publish._gh_pages.subprocess.run", side_effect=mock_run):
        gh_pages_publish(build_dir, {"branch": "gh-pages", "remote": "origin"})

    # Should have called git init, remote add, fetch, etc.
    git_commands = [
        c[1] if isinstance(c, (list, tuple)) and len(c) > 1 else None for c in calls
    ]
    assert "init" in git_commands
    assert "push" in git_commands


def test_gh_pages_publish_uses_default_config(tmp_path):
    """gh-pages strategy should use default branch and remote."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<h1>Test</h1>")

    calls = []

    def mock_run(*args, **kwargs):
        calls.append(args[0] if args else kwargs.get("args"))
        result = mock.Mock(
            returncode=0, stdout="https://github.com/test/repo.git\n", stderr=""
        )
        if args and "diff" in args[0]:
            result.returncode = 1
        return result

    with mock.patch("automata.publish._gh_pages.subprocess.run", side_effect=mock_run):
        gh_pages_publish(build_dir, {})

    # The push command should reference gh-pages branch
    push_calls = [c for c in calls if isinstance(c, (list, tuple)) and "push" in c]
    assert len(push_calls) == 1
    assert "gh-pages" in push_calls[0]


# scp strategy =========================================================================


def test_scp_publish_with_rsync(tmp_path):
    """scp strategy should use rsync when available."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    config = {
        "host": "example.com",
        "remote_path": "/var/www/site/",
        "user": "deploy",
    }

    with mock.patch(
        "automata.publish._scp.shutil.which", return_value="/usr/bin/rsync"
    ):
        with mock.patch("automata.publish._scp.subprocess.run") as mock_run:
            scp_publish(build_dir, config)

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "rsync"
            assert "deploy@example.com:/var/www/site/" in cmd
            assert "--delete" in cmd


def test_scp_publish_with_rsync_no_delete(tmp_path):
    """delete=False should omit --delete."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    config = {
        "host": "example.com",
        "remote_path": "/var/www/",
        "delete": False,
    }

    with mock.patch(
        "automata.publish._scp.shutil.which", return_value="/usr/bin/rsync"
    ):
        with mock.patch("automata.publish._scp.subprocess.run") as mock_run:
            scp_publish(build_dir, config)

            cmd = mock_run.call_args[0][0]
            assert "--delete" not in cmd


def test_scp_publish_falls_back_to_scp(tmp_path):
    """Should fall back to scp if rsync is not available."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    config = {"host": "example.com", "remote_path": "/var/www/"}

    def which(name):
        return "/usr/bin/scp" if name == "scp" else None

    with mock.patch("automata.publish._scp.shutil.which", side_effect=which):
        with mock.patch("automata.publish._scp.subprocess.run") as mock_run:
            scp_publish(build_dir, config)

            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "scp"


def test_scp_publish_raises_if_no_tools(tmp_path):
    """Should raise if neither rsync nor scp is available."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    config = {"host": "example.com", "remote_path": "/var/www/"}

    with mock.patch("automata.publish._scp.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="Neither rsync nor scp"):
            scp_publish(build_dir, config)


def test_scp_publish_requires_host_and_path(tmp_path):
    """Should raise ValueError if host or remote_path is missing."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    with pytest.raises(ValueError, match="host"):
        scp_publish(build_dir, {"remote_path": "/var/www/"})

    with pytest.raises(ValueError, match="remote_path"):
        scp_publish(build_dir, {"host": "example.com"})


def test_scp_publish_without_user(tmp_path):
    """Destination should omit user@ when not specified."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    config = {"host": "example.com", "remote_path": "/var/www/"}

    with mock.patch(
        "automata.publish._scp.shutil.which", return_value="/usr/bin/rsync"
    ):
        with mock.patch("automata.publish._scp.subprocess.run") as mock_run:
            scp_publish(build_dir, config)

            cmd = mock_run.call_args[0][0]
            assert "example.com:/var/www/" in cmd
            assert "@" not in cmd[-1]


# on_register_publishers hook ==========================================================


def test_extensions_can_register_publishers():
    """Extensions should be able to register publishers via hook args."""

    def sentinel(build_dir, config):
        return None

    args = PublisherRegistryArgs(publishers={"gh-pages": gh_pages_publish})
    args.publishers["custom"] = sentinel
    assert args.publishers["custom"] is sentinel
    assert args.publishers["gh-pages"] is gh_pages_publish
