"""Git publish strategy.

Pushes the contents of the build directory to a branch of any git
repository: a remote of the project's repository (default ``origin``), or a
repository given by its URL. The gh-pages strategy is this, for a GitHub
repository's ``gh-pages`` branch.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..exceptions import Error
from ._options import check_options


def publish(
    build_directory: Path, config: dict[str, Any], project_directory: Path
) -> None:
    """Replace the contents of a branch of a git repository with the built site.

    The site replaces the contents of the branch, in a single commit (no commit
    is made if nothing changed).

    Parameters
    ----------
    build_directory : Path
        Path to the directory containing the built site.
    config : dict
        Strategy-specific configuration:

        - ``branch`` (str): The branch to publish to. Required.
        - ``url`` (str): The URL of the repository to push to, which needn't
          be a remote of the project's repository (or the project needn't be
          in one), e.g. ``"https://github.com/org/site.git"``. A relative local
          path is relative to the project.
        - ``remote`` (str): In place of ``url``, the name of a remote of the
          project's repository. Default ``"origin"``.
        - ``message``, ``user_name``, ``user_email``: see :func:`push`.
    project_directory : Path
        The project root, whose git repository defines the remotes and the
        default identity.

    Raises
    ------
    automata.exceptions.Error
        If there is no ``branch``, both ``remote`` and ``url`` are given, or
        publishing fails.

    """
    check_options(
        "git",
        config,
        ("branch", "message", "remote", "url", "user_email", "user_name"),
    )
    if "remote" in config and "url" in config:
        raise Error(
            'The git publish strategy takes "remote" (a remote of the project\'s git '
            'repository) or "url" (any repository), not both.'
        )
    if "branch" not in config:
        raise Error(
            'The git publish strategy needs a "branch" to publish to (whose '
            "contents it replaces)."
        )
    if "url" in config:
        url = relative_to(project_directory, config["url"])
        source = url
    else:
        remote = config.get("remote", "origin")
        url = remote_url(remote, project_directory, "git")
        source = f'remote "{remote}" ({url})'
    push(
        build_directory,
        project_directory,
        url=url,
        source=source,
        branch=config["branch"],
        message=config.get("message", "Publish the site"),
        config=config,
        strategy="git",
    )


def push(
    build_directory: Path,
    project_directory: Path,
    url: str,
    source: str,
    branch: str,
    message: str,
    config: dict[str, Any],
    strategy: str,
) -> None:
    """Replace the contents of *branch* of the repository at *url* with the
    build directory, in a single commit (none if nothing changed).

    *source* describes the repository in errors (e.g. ``remote "origin"
    (<url>)``), and *strategy* names the strategy publishing. The commit's
    message is *message*, and its author is ``user_name`` and ``user_email``
    from *config*, or else the project's git identity (``git config user.name``
    and ``user.email``, local or global), or else the ``GIT_COMMITTER_NAME``
    and ``GIT_COMMITTER_EMAIL`` environment variables.

    Raises
    ------
    automata.exceptions.Error
        If no commit identity can be found, the branch can't be read, or a git
        command fails.

    """
    user_name, user_email = _identity(config, project_directory, strategy)

    def _run(*args, **kw):
        result = subprocess.run(args, capture_output=True, text=True, **kw)
        if result.returncode != 0:
            raise Error(
                f"{strategy} publishing failed: `{' '.join(args)}` exited with "
                f"status {result.returncode}: {result.stderr.strip()}"
            )
        return result

    # Work in a temporary directory so we don't disturb the working tree
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Initialize a fresh repo and fetch just the target branch (if it exists)
        _run("git", "init", cwd=tmp)
        _run("git", "remote", "add", "origin", url, cwd=tmp)

        # Check whether the branch exists. Only a branch that doesn't exist may
        # start over as an orphan: if the remote can't be read, the force-push
        # below would replace the branch's history.
        listed = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        if listed.returncode != 0:
            raise Error(
                f'{strategy} publishing could not read branch "{branch}" from '
                f"{source}: {listed.stderr.strip()}"
            )
        if listed.stdout.strip():
            _run("git", "fetch", "origin", branch, cwd=tmp)
            _run("git", "checkout", branch, cwd=tmp)
            # Clean out old content
            _run("git", "rm", "-rf", ".", cwd=tmp)
        else:
            # Branch doesn't exist yet — start with an orphan
            _run("git", "checkout", "--orphan", branch, cwd=tmp)

        # Copy build contents into the temp repo. A .git in the build directory
        # (e.g. if it is a checkout) would replace the temp repo's.
        shutil.copytree(
            build_directory,
            tmp,
            dirs_exist_ok=True,
            ignore=lambda directory, names: (
                [".git"] if Path(directory) == Path(build_directory) else []
            ),
        )

        # Commit and push
        _run("git", "add", "-A", cwd=tmp)

        # Check if there's anything to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=tmp,
            capture_output=True,
        )
        if result.returncode == 0:
            return  # nothing changed

        _run(
            "git",
            "-c",
            f"user.name={user_name}",
            "-c",
            f"user.email={user_email}",
            "commit",
            "-m",
            message,
            cwd=tmp,
        )
        _run("git", "push", "origin", branch, "--force", cwd=tmp)


def _identity(
    config: dict[str, Any], project_directory: Path, strategy: str
) -> tuple[str, str]:
    """The name and email to commit with (see :func:`push`)."""
    identity = []
    for key, git_key, env_var in [
        ("user_name", "user.name", "GIT_COMMITTER_NAME"),
        ("user_email", "user.email", "GIT_COMMITTER_EMAIL"),
    ]:
        value = (
            config.get(key)
            or _git_config(git_key, project_directory)
            or os.environ.get(env_var)
        )
        if not value:
            raise Error(
                f"The {strategy} publish strategy needs a git identity to commit "
                "with, but none is set. Set user_name and user_email in the "
                "strategy's config in automata.yaml, or set git's user.name and "
                "user.email (git config user.name ...)."
            )
        identity.append(value)
    return identity[0], identity[1]


def _git_config(key: str, project_directory: Path) -> str | None:
    """A git config value as seen from the project's repository, or None."""
    result = subprocess.run(
        ["git", "config", "--get", key],
        cwd=project_directory,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def remote_url(remote: str, project_directory: Path, strategy: str) -> str:
    """The URL of a git remote configured in the project's repository."""
    result = subprocess.run(
        ["git", "remote", "get-url", remote],
        cwd=project_directory,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Error(
            f'The {strategy} publish strategy could not find git remote "{remote}" '
            f"in {project_directory}: {result.stderr.strip()}"
        )
    return relative_to(project_directory, result.stdout.strip())


def relative_to(project_directory: Path, url: str) -> str:
    """*url*, or, if it is a relative local path, the path it names relative to
    *project_directory* (the push runs in a temporary directory)."""
    if "://" not in url and ":" not in url and not Path(url).is_absolute():
        return str((project_directory / url).resolve())
    return url
