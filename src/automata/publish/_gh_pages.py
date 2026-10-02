"""GitHub Pages publish strategy.

Pushes the contents of the build directory to a branch (default
``gh-pages``) on a Git remote (default ``origin``).
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..exceptions import Error


def publish(
    build_directory: Path, config: dict[str, Any], project_directory: Path
) -> None:
    """Deploy the built site to GitHub Pages.

    The site replaces the contents of the target branch, in a single commit (no
    commit is made if nothing changed). The remote is looked up in the
    project's git repository.

    Parameters
    ----------
    build_directory : Path
        Path to the directory containing the built site.
    config : dict
        Strategy-specific configuration:

        - ``branch`` (str): Target branch name. Default ``"gh-pages"``.
        - ``remote`` (str): Git remote name, as configured in the project's
          repository. Default ``"origin"``.
        - ``message`` (str): Commit message. Default ``"Deploy to GitHub Pages"``.
        - ``user_name``, ``user_email`` (str): The commit's author. By default,
          the project's git identity (``git config user.name`` and
          ``user.email``, local or global), or else the
          ``GIT_COMMITTER_NAME`` and ``GIT_COMMITTER_EMAIL`` environment
          variables.
    project_directory : Path
        The project root, whose git repository defines the remote and the
        default identity.

    Raises
    ------
    automata.exceptions.Error
        If no commit identity can be found.

    """
    branch = config.get("branch", "gh-pages")
    remote = config.get("remote", "origin")
    message = config.get("message", "Deploy to GitHub Pages")
    user_name, user_email = _identity(config, project_directory)

    def _run(*args, **kw):
        result = subprocess.run(args, capture_output=True, text=True, **kw)
        if result.returncode != 0:
            raise Error(
                f"gh-pages publishing failed: `{' '.join(args)}` exited with status "
                f"{result.returncode}: {result.stderr.strip()}"
            )
        return result

    # Work in a temporary directory so we don't disturb the working tree
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Initialize a fresh repo and fetch just the target branch (if it exists)
        _run("git", "init", cwd=tmp)
        remote_url = _get_remote_url(remote, project_directory)
        _run("git", "remote", "add", "origin", remote_url, cwd=tmp)

        # Fetch the existing branch; it's fine if it doesn't exist yet
        fetched = subprocess.run(
            ["git", "fetch", "origin", branch], cwd=tmp, capture_output=True
        )
        if fetched.returncode == 0:
            _run("git", "checkout", branch, cwd=tmp)
            # Clean out old content
            _run("git", "rm", "-rf", ".", cwd=tmp)
        else:
            # Branch doesn't exist yet — start with an orphan
            _run("git", "checkout", "--orphan", branch, cwd=tmp)

        # Copy build contents into the temp repo
        shutil.copytree(build_directory, tmp, dirs_exist_ok=True)

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


def _identity(config: dict[str, Any], project_directory: Path) -> tuple[str, str]:
    """The name and email to commit with (see :func:`publish`)."""
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
                "The gh-pages publish strategy needs a git identity to commit with, "
                "but none is set. Set user_name and user_email in the strategy's "
                "config in automata.yaml, or set git's user.name and user.email "
                "(git config user.name ...)."
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


def _get_remote_url(remote: str, project_directory: Path) -> str:
    """Get the URL of a git remote configured in the project's repository."""
    result = subprocess.run(
        ["git", "remote", "get-url", remote],
        cwd=project_directory,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Error(
            f'The gh-pages publish strategy could not find git remote "{remote}" '
            f"in {project_directory}: {result.stderr.strip()}"
        )
    return result.stdout.strip()
