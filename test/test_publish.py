"""Tests for the publish system."""

import contextlib
import subprocess
from pathlib import Path

import pytest

from automata.exceptions import Error
from automata.publish import Change, PublishResult, registry
from automata.publish._gh_pages import publish as gh_pages_publish
from automata.publish._gh_pages import repository_url
from automata.publish._git import publish as git_publish
from automata.publish._rsync import publish as rsync_publish

# publisher registry ===================================================================


def test_registry_has_builtin_strategies():
    """git, gh-pages and rsync should be registered at import time."""
    assert set(registry.all()) == {"git", "gh-pages", "rsync"}


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
def git_project(tmp_path):
    """A git project whose `origin` is a local bare repository.

    The project's own git config holds the committer identity. Returns
    (project, build_dir, remote). The build directory holds a small site.
    """
    remote = tmp_path / "remote.git"
    _git("init", "--bare", "--quiet", str(remote), cwd=tmp_path)

    project = tmp_path / "project"
    project.mkdir()
    _git("init", "--quiet", cwd=project)
    _git("remote", "add", "origin", str(remote), cwd=project)
    _git("config", "user.name", "Project Author", cwd=project)
    _git("config", "user.email", "author@example.com", cwd=project)

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
def test_gh_pages_honors_branch_and_message(git_project):
    project, build_dir, remote = git_project

    gh_pages_publish(
        build_dir, {"branch": "site", "message": "Publish week 3"}, project
    )

    assert _branch_files(remote, "site") == ["index.html", "materials/hw01.pdf"]
    assert _git("log", "-1", "--format=%s", "site", cwd=remote).strip() == (
        "Publish week 3"
    )


@pytest.mark.integration
def test_gh_pages_pushes_to_a_github_repository_by_name(git_project, tmp_path):
    # given: a stand-in for GitHub, holding org/site.git
    project, build_dir, remote = git_project
    github = tmp_path / "github"
    (github / "org").mkdir(parents=True)
    _git("init", "--bare", "--quiet", str(github / "org" / "site.git"), cwd=tmp_path)

    # when
    gh_pages_publish(
        build_dir, {"repository": "org/site"}, project, github=f"{github}/"
    )

    # then: the site goes there, not to origin
    assert _branch_files(github / "org" / "site.git", "gh-pages") == [
        "index.html",
        "materials/hw01.pdf",
    ]
    assert _git("branch", "--list", cwd=remote) == ""


def test_a_github_repository_is_pushed_to_over_ssh():
    assert repository_url("dsc-courses/dsc40b-2026-fa") == (
        "git@github.com:dsc-courses/dsc40b-2026-fa.git"
    )


@pytest.mark.parametrize("repository", ["site", "org/site/extra", "/site", "org/"])
def test_a_github_repository_must_be_org_slash_name(tmp_path, repository):
    with pytest.raises(Error) as excinfo:
        gh_pages_publish(tmp_path, {"repository": repository}, tmp_path)

    assert str(excinfo.value) == (
        f'The gh-pages publish strategy\'s "repository" is a GitHub repository, '
        f'written like "org/name", not "{repository}". To publish to another '
        f'repository, use the "git" strategy, with its "url".'
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


@pytest.mark.integration
def test_gh_pages_ignores_a_git_repository_in_the_build_directory(
    git_project, tmp_path
):
    # given: the build directory is itself a git checkout with another remote
    project, build_dir, remote = git_project
    other = tmp_path / "other.git"
    _git("init", "--bare", "--quiet", str(other), cwd=tmp_path)
    _git("init", "--quiet", cwd=build_dir)
    _git("remote", "add", "origin", str(other), cwd=build_dir)

    # when
    gh_pages_publish(build_dir, {}, project)

    # then: the site goes to the project's remote, without the build's .git
    assert _branch_files(remote, "gh-pages") == ["index.html", "materials/hw01.pdf"]
    assert _git("branch", "--list", cwd=other) == ""


@pytest.mark.integration
def test_gh_pages_accepts_a_remote_url_relative_to_the_project(git_project):
    project, build_dir, remote = git_project
    _git("remote", "set-url", "origin", "../remote.git", cwd=project)

    gh_pages_publish(build_dir, {}, project)

    assert _branch_files(remote, "gh-pages") == ["index.html", "materials/hw01.pdf"]


@pytest.mark.integration
def test_gh_pages_does_not_force_push_when_the_remote_cannot_be_read(git_project):
    # if the remote can't be read, publishing must not assume the branch is new
    # (which would force-push an orphan branch over its history)
    project, build_dir, remote = git_project
    _git("remote", "set-url", "origin", str(remote.parent / "missing.git"), cwd=project)

    with pytest.raises(Error) as excinfo:
        gh_pages_publish(build_dir, {}, project)

    message = str(excinfo.value)
    assert 'could not read branch "gh-pages"' in message
    assert "push" not in message


# git strategy =========================================================================


@pytest.mark.integration
def test_git_honors_branch_remote_and_message(git_project):
    project, build_dir, remote = git_project
    _git("remote", "add", "deploy", str(remote), cwd=project)

    git_publish(
        build_dir,
        {"branch": "site", "remote": "deploy", "message": "Publish week 3"},
        project,
    )

    assert _branch_files(remote, "site") == ["index.html", "materials/hw01.pdf"]
    assert _git("log", "-1", "--format=%s", "site", cwd=remote).strip() == (
        "Publish week 3"
    )


@pytest.mark.integration
def test_git_pushes_to_a_url_that_is_not_a_remote_of_the_project(git_project, tmp_path):
    # given: a repository that isn't one of the project's remotes
    project, build_dir, remote = git_project
    other = tmp_path / "other.git"
    _git("init", "--bare", "--quiet", str(other), cwd=tmp_path)

    # when
    git_publish(build_dir, {"branch": "gh-pages", "url": str(other)}, project)

    # then: the site goes there, not to origin
    assert _branch_files(other, "gh-pages") == ["index.html", "materials/hw01.pdf"]
    assert _git("branch", "--list", cwd=remote) == ""


@pytest.mark.integration
def test_git_url_can_be_relative_to_the_project(git_project, tmp_path):
    project, build_dir, remote = git_project
    other = tmp_path / "other.git"
    _git("init", "--bare", "--quiet", str(other), cwd=tmp_path)

    git_publish(build_dir, {"branch": "gh-pages", "url": "../other.git"}, project)

    assert _branch_files(other, "gh-pages") == ["index.html", "materials/hw01.pdf"]


@pytest.mark.integration
def test_git_url_works_outside_a_git_repository(tmp_path):
    # e.g. publishing from an export of the project, not a clone
    other = tmp_path / "other.git"
    _git("init", "--bare", "--quiet", str(other), cwd=tmp_path)
    build_dir = tmp_path / "_build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<h1>Home</h1>")

    git_publish(
        build_dir,
        {
            "branch": "gh-pages",
            "url": str(other),
            "user_name": "a",
            "user_email": "a@example.com",
        },
        tmp_path,
    )

    assert _branch_files(other, "gh-pages") == ["index.html"]


@pytest.mark.integration
def test_git_says_which_url_cannot_be_read(git_project, tmp_path):
    project, build_dir, remote = git_project
    missing = tmp_path / "missing.git"

    with pytest.raises(Error) as excinfo:
        git_publish(build_dir, {"branch": "gh-pages", "url": str(missing)}, project)

    message = str(excinfo.value)
    assert f'could not read branch "gh-pages" from {missing}:' in message
    assert "remote" not in message.split(":")[0]


def test_git_url_and_remote_together_is_an_error(tmp_path):
    with pytest.raises(Error) as excinfo:
        git_publish(
            tmp_path,
            {"branch": "site", "url": "git@github.com:a/b.git", "remote": "origin"},
            tmp_path,
        )

    assert str(excinfo.value) == (
        'The git publish strategy takes "remote" (a remote of the project\'s git '
        'repository) or "url" (any repository), not both.'
    )


def test_git_requires_a_branch(tmp_path):
    with pytest.raises(Error) as excinfo:
        git_publish(tmp_path, {"url": "git@github.com:a/b.git"}, tmp_path)

    assert str(excinfo.value) == (
        'The git publish strategy needs a "branch" to publish to (whose contents '
        "it replaces)."
    )


@pytest.mark.integration
def test_git_with_an_unknown_remote_is_a_clear_error(git_project):
    project, build_dir, remote = git_project

    with pytest.raises(Error) as excinfo:
        git_publish(build_dir, {"branch": "site", "remote": "upstream"}, project)

    assert 'git remote "upstream"' in str(excinfo.value)


# the commit's identity (the same for gh-pages and git) ================================


def _commit_author(remote: Path, branch: str) -> str:
    return _git("log", "-1", "--format=%an <%ae>", branch, cwd=remote).strip()


@pytest.mark.integration
def test_gh_pages_commits_with_the_projects_git_identity(git_project):
    project, build_dir, remote = git_project

    gh_pages_publish(build_dir, {}, project)

    assert _commit_author(remote, "gh-pages") == "Project Author <author@example.com>"


@pytest.mark.integration
def test_gh_pages_identity_can_be_set_in_the_strategy_config(git_project):
    project, build_dir, remote = git_project

    gh_pages_publish(
        build_dir,
        {"user_name": "github-actions[bot]", "user_email": "bot@example.com"},
        project,
    )

    assert _commit_author(remote, "gh-pages") == "github-actions[bot] <bot@example.com>"


@pytest.mark.integration
def test_gh_pages_without_any_identity_is_a_clear_error(
    git_project, tmp_path, monkeypatch
):
    # given: no identity in the project, and none from this machine's git
    # config or environment
    project, build_dir, remote = git_project
    _git("config", "--unset", "user.name", cwd=project)
    _git("config", "--unset", "user.email", cwd=project)
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ["NAME", "EMAIL"]:
        monkeypatch.delenv(f"GIT_AUTHOR_{var}", raising=False)
        monkeypatch.delenv(f"GIT_COMMITTER_{var}", raising=False)

    # when / then
    with pytest.raises(Error) as excinfo:
        gh_pages_publish(build_dir, {}, project)

    message = str(excinfo.value)
    assert "user_name" in message
    assert "user_email" in message


@pytest.mark.integration
def test_gh_pages_outside_a_git_repository_is_a_clear_error(tmp_path):
    build_dir = tmp_path / "_build"
    build_dir.mkdir()

    with pytest.raises(Error) as excinfo:
        gh_pages_publish(
            build_dir, {"user_name": "a", "user_email": "a@example.com"}, tmp_path
        )

    message = str(excinfo.value)
    assert 'git remote "origin"' in message
    assert str(tmp_path) in message


# dry runs of gh-pages and git ========================================================


@pytest.mark.integration
def test_a_dry_run_to_a_new_branch_adds_everything_and_pushes_nothing(git_project):
    project, build_dir, remote = git_project

    changes = gh_pages_publish(build_dir, {}, project, dry_run=True)

    assert changes == [
        Change("added", "index.html"),
        Change("added", "materials/hw01.pdf"),
    ]
    assert _git("branch", "--list", cwd=remote) == ""


@pytest.mark.integration
def test_a_dry_run_reports_what_would_be_added_changed_and_deleted(git_project):
    # given: a first publish, then a changed site
    project, build_dir, remote = git_project
    gh_pages_publish(build_dir, {}, project)
    (build_dir / "materials" / "hw01.pdf").unlink()
    (build_dir / "index.html").write_text("<h1>Updated</h1>")
    (build_dir / "CNAME").write_text("dsc40b.com")

    # when
    changes = gh_pages_publish(build_dir, {}, project, dry_run=True)

    # then: the changes, in order of path, and the branch is as it was
    assert changes == [
        Change("added", "CNAME"),
        Change("modified", "index.html"),
        Change("deleted", "materials/hw01.pdf"),
    ]
    assert _branch_commits(remote, "gh-pages") == 1
    assert _git("show", "gh-pages:index.html", cwd=remote) == "<h1>Home</h1>"


@pytest.mark.integration
def test_a_dry_run_with_nothing_to_change_reports_no_changes(git_project):
    project, build_dir, remote = git_project
    gh_pages_publish(build_dir, {}, project)

    assert gh_pages_publish(build_dir, {}, project, dry_run=True) == []


@pytest.mark.integration
def test_a_dry_run_reports_paths_with_spaces_and_unicode_as_they_are(git_project):
    project, build_dir, remote = git_project
    (build_dir / "notes on café.html").write_text("x")

    changes = gh_pages_publish(build_dir, {}, project, dry_run=True)

    assert Change("added", "notes on café.html") in changes


@pytest.mark.integration
def test_a_git_dry_run_reports_changes_too(git_project, tmp_path):
    project, build_dir, remote = git_project

    changes = git_publish(build_dir, {"branch": "site"}, project, dry_run=True)

    assert [c.path for c in changes] == ["index.html", "materials/hw01.pdf"]
    assert _git("branch", "--list", cwd=remote) == ""


@pytest.mark.integration
def test_a_dry_run_needs_no_git_identity(git_project, tmp_path, monkeypatch):
    # e.g. on CI, checking a pull request: nothing is committed
    project, build_dir, remote = git_project
    _git("config", "--unset", "user.name", cwd=project)
    _git("config", "--unset", "user.email", cwd=project)
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ["NAME", "EMAIL"]:
        monkeypatch.delenv(f"GIT_AUTHOR_{var}", raising=False)
        monkeypatch.delenv(f"GIT_COMMITTER_{var}", raising=False)

    changes = gh_pages_publish(build_dir, {}, project, dry_run=True)

    assert len(changes) == 2


@pytest.mark.integration
def test_a_publish_reports_what_it_changed(git_project):
    project, build_dir, remote = git_project
    gh_pages_publish(build_dir, {}, project)
    (build_dir / "index.html").write_text("<h1>Updated</h1>")

    changes = gh_pages_publish(build_dir, {}, project)

    assert changes == [Change("modified", "index.html")]
    assert _branch_commits(remote, "gh-pages") == 2


@pytest.mark.integration
def test_a_publish_that_changes_nothing_reports_no_changes(git_project):
    project, build_dir, remote = git_project
    gh_pages_publish(build_dir, {}, project)

    assert gh_pages_publish(build_dir, {}, project) == []
    assert _branch_commits(remote, "gh-pages") == 1


def test_a_publish_result_as_a_dict():
    result = PublishResult(
        target="github",
        strategy="gh-pages",
        dry_run=True,
        changes=[Change("added", "CNAME")],
    )

    assert result.to_dict() == {
        "strategy": "gh-pages",
        "dry_run": True,
        "changes": [{"status": "added", "path": "CNAME"}],
    }
    assert PublishResult("s", "rsync", False, None).to_dict()["changes"] is None


def test_a_change_as_a_dict():
    assert Change("deleted", "old.html").to_dict() == {
        "status": "deleted",
        "path": "old.html",
    }


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
            "--progress",
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


def test_rsync_uses_options_that_macos_rsync_accepts(tmp_path):
    # macOS's rsync (openrsync) rejects --info=progress2
    run = _Recorder()

    rsync_publish(
        tmp_path, {"host": "example.com", "remote_path": "/var/www"}, tmp_path, run=run
    )

    (cmd,) = run.commands
    assert "--progress" in cmd
    assert not any(arg.startswith("--info") for arg in cmd)


class _Itemizer:
    """A fake command runner for an rsync dry run, which prints *output*."""

    def __init__(self, output):
        self.output = output
        self.commands = []
        self.kwargs = []

    def __call__(self, cmd, **kwargs):
        self.commands.append(cmd)
        self.kwargs.append(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout=self.output, stderr="")


# as printed by rsync 3 (11 flags) and macOS's openrsync (9 flags)
_ITEMIZED = """\
*deleting   old.html
*deleting   retired/
<f+++++++++ materials/hw02.pdf
<f.st...... index.html
.f..t...... unchanged.html
cd+++++++++ materials/
<f+++++++ notes on café.html
>f.s..... styles.css
"""


def test_an_rsync_dry_run_reports_its_itemized_changes(tmp_path):
    run = _Itemizer(_ITEMIZED)

    changes = rsync_publish(
        tmp_path,
        {"host": "example.com", "remote_path": "/var/www"},
        tmp_path,
        run=run,
        dry_run=True,
    )

    # (directories, and files whose contents don't change, are left out)
    assert changes == [
        Change("modified", "index.html"),
        Change("added", "materials/hw02.pdf"),
        Change("added", "notes on café.html"),
        Change("deleted", "old.html"),
        Change("modified", "styles.css"),
    ]
    (cmd,) = run.commands
    assert cmd[:4] == ["rsync", "-az", "--dry-run", "--itemize-changes"]
    assert "--delete" in cmd
    assert "--progress" not in cmd
    assert run.kwargs[0]["capture_output"] is True


def test_an_rsync_publish_does_not_report_its_changes(tmp_path):
    result = rsync_publish(
        tmp_path,
        {"host": "example.com", "remote_path": "/var/www"},
        tmp_path,
        run=_Recorder(),
    )

    assert result is None


def test_an_rsync_dry_run_with_nothing_to_change_reports_no_changes(tmp_path):
    changes = rsync_publish(
        tmp_path,
        {"host": "example.com", "remote_path": "/var/www"},
        tmp_path,
        run=_Itemizer(""),
        dry_run=True,
    )

    assert changes == []


def test_a_failing_rsync_is_a_clear_error(tmp_path):
    def failing(cmd, **kwargs):
        raise subprocess.CalledProcessError(12, cmd)

    with pytest.raises(Error) as excinfo:
        rsync_publish(
            tmp_path,
            {"host": "example.com", "remote_path": "/var/www"},
            tmp_path,
            run=failing,
        )

    assert str(excinfo.value) == (
        "rsync to example.com:/var/www failed with exit status 12 (its output is "
        "above)."
    )


# unknown options ======================================================================


def test_gh_pages_rejects_an_unknown_option(tmp_path):
    with pytest.raises(Error) as excinfo:
        gh_pages_publish(tmp_path, {"brach": "site"}, tmp_path)

    assert str(excinfo.value) == (
        'The gh-pages publish strategy has no option "brach". Its options are '
        "branch, message, repository, user_email, user_name."
    )


def test_git_rejects_an_unknown_option(tmp_path):
    with pytest.raises(Error) as excinfo:
        git_publish(tmp_path, {"branch": "site", "remot": "origin"}, tmp_path)

    assert str(excinfo.value) == (
        'The git publish strategy has no option "remot". Its options are '
        "branch, message, remote, url, user_email, user_name."
    )


def test_rsync_rejects_an_unknown_option(tmp_path):
    run = _Recorder()

    with pytest.raises(Error) as excinfo:
        rsync_publish(
            tmp_path,
            {"host": "example.com", "remote_path": "/srv", "dleete": False},
            tmp_path,
            run=run,
        )

    assert str(excinfo.value) == (
        'The rsync publish strategy has no option "dleete". Its options are '
        "delete, host, remote_path, user."
    )
    assert run.commands == []
