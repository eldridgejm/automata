"""Tests for the publish system."""

import contextlib
import subprocess
from pathlib import Path

import pytest

from automata.exceptions import Error
from automata.publish import registry
from automata.publish._gh_pages import publish as gh_pages_publish
from automata.publish._rsync import publish as rsync_publish

# publisher registry ===================================================================


def test_registry_has_builtin_strategies():
    """gh-pages and rsync should be registered at import time."""
    assert set(registry.all()) == {"gh-pages", "rsync"}


def test_registry_register_and_get():
    """Custom strategies can be registered and retrieved."""

    def sentinel(build_dir, config, project_dir):
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
#
# These run real git against a local bare repository standing in for GitHub.


def _git(*args, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout


@pytest.fixture
def git_project(tmp_path, monkeypatch):
    """A git project whose `origin` is a local bare repository.

    Returns (project, build_dir, remote). The build directory holds a small site.
    """
    # commits need an identity; don't depend on the machine's git config
    for var in ["GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"]:
        monkeypatch.setenv(var, "Automata Tests")
    for var in ["GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"]:
        monkeypatch.setenv(var, "tests@example.com")

    remote = tmp_path / "remote.git"
    _git("init", "--bare", "--quiet", str(remote), cwd=tmp_path)

    project = tmp_path / "project"
    project.mkdir()
    _git("init", "--quiet", cwd=project)
    _git("remote", "add", "origin", str(remote), cwd=project)

    build_dir = project / "_build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<h1>Home</h1>")
    (build_dir / "materials").mkdir()
    (build_dir / "materials" / "hw01.pdf").write_text("hw01")

    return project, build_dir, remote


def _branch_files(remote: Path, branch: str) -> list[str]:
    return _git("ls-tree", "-r", "--name-only", branch, cwd=remote).split()


def _branch_commits(remote: Path, branch: str) -> int:
    return int(_git("rev-list", "--count", branch, cwd=remote))


@pytest.mark.integration
def test_gh_pages_pushes_the_build_directory_to_a_new_branch(git_project):
    project, build_dir, remote = git_project

    gh_pages_publish(build_dir, {}, project)

    assert _branch_files(remote, "gh-pages") == ["index.html", "materials/hw01.pdf"]
    assert _git("show", "gh-pages:index.html", cwd=remote) == "<h1>Home</h1>"


@pytest.mark.integration
def test_gh_pages_replaces_previous_contents(git_project):
    # given: a first publish
    project, build_dir, remote = git_project
    gh_pages_publish(build_dir, {}, project)

    # when: a file is removed from the site and another changed
    (build_dir / "materials" / "hw01.pdf").unlink()
    (build_dir / "index.html").write_text("<h1>Updated</h1>")
    gh_pages_publish(build_dir, {}, project)

    # then
    assert _branch_files(remote, "gh-pages") == ["index.html"]
    assert _git("show", "gh-pages:index.html", cwd=remote) == "<h1>Updated</h1>"
    assert _branch_commits(remote, "gh-pages") == 2


@pytest.mark.integration
def test_gh_pages_makes_no_commit_when_nothing_changed(git_project):
    project, build_dir, remote = git_project

    gh_pages_publish(build_dir, {}, project)
    gh_pages_publish(build_dir, {}, project)

    assert _branch_commits(remote, "gh-pages") == 1


@pytest.mark.integration
def test_gh_pages_honors_branch_remote_and_message(git_project):
    project, build_dir, remote = git_project
    _git("remote", "add", "deploy", str(remote), cwd=project)

    gh_pages_publish(
        build_dir,
        {"branch": "site", "remote": "deploy", "message": "Publish week 3"},
        project,
    )

    assert _branch_files(remote, "site") == ["index.html", "materials/hw01.pdf"]
    assert _git("log", "-1", "--format=%s", "site", cwd=remote).strip() == (
        "Publish week 3"
    )


@pytest.mark.integration
def test_gh_pages_resolves_the_remote_in_the_project_not_the_cwd(git_project, tmp_path):
    # given: the process runs outside the project's repository
    project, build_dir, remote = git_project
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    # when
    with contextlib.chdir(elsewhere):
        gh_pages_publish(build_dir, {}, project)

    # then
    assert _branch_files(remote, "gh-pages") == ["index.html", "materials/hw01.pdf"]


# rsync strategy =======================================================================


class _Recorder:
    """A fake command runner that records the commands it is given."""

    def __init__(self):
        self.commands = []

    def __call__(self, cmd, **kwargs):
        self.commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)


def _not_installed(cmd, **kwargs):
    """A fake command runner for a machine without the program."""
    raise FileNotFoundError(2, "No such file or directory", cmd[0])


def test_rsync_mirrors_the_build_directory_deleting_stale_files(tmp_path):
    run = _Recorder()

    rsync_publish(
        tmp_path / "build",
        {"host": "example.com", "remote_path": "/var/www/course", "user": "deploy"},
        tmp_path,
        run=run,
    )

    assert run.commands == [
        [
            "rsync",
            "-az",
            "--info=progress2",
            "--delete",
            f"{tmp_path / 'build'}/",
            "deploy@example.com:/var/www/course",
        ]
    ]


def test_rsync_with_delete_false_keeps_stale_files(tmp_path):
    run = _Recorder()

    rsync_publish(
        tmp_path / "build",
        {"host": "example.com", "remote_path": "/srv", "delete": False},
        tmp_path,
        run=run,
    )

    assert "--delete" not in run.commands[0]


def test_rsync_without_user_uses_host_only(tmp_path):
    run = _Recorder()

    rsync_publish(
        tmp_path / "build",
        {"host": "example.com", "remote_path": "/srv"},
        tmp_path,
        run=run,
    )

    assert run.commands[0][-1] == "example.com:/srv"


def test_rsync_not_installed_is_a_clear_error(tmp_path):
    with pytest.raises(Error) as excinfo:
        rsync_publish(
            tmp_path / "build",
            {"host": "example.com", "remote_path": "/srv"},
            tmp_path,
            run=_not_installed,
        )

    assert "rsync" in str(excinfo.value)


@pytest.mark.parametrize("missing", ["host", "remote_path"])
def test_rsync_requires_host_and_remote_path(tmp_path, missing):
    config = {"host": "example.com", "remote_path": "/srv"}
    del config[missing]

    with pytest.raises(Error, match=missing):
        rsync_publish(tmp_path / "build", config, tmp_path, run=_Recorder())
