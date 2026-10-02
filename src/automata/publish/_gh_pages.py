"""GitHub Pages publish strategy.

Pushes the contents of the build directory to a branch (default
``gh-pages``) on a Git remote (default ``origin``).
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


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
    project_directory : Path
        The project root, whose git repository defines the remote.

    """
    branch = config.get("branch", "gh-pages")
    remote = config.get("remote", "origin")
    message = config.get("message", "Deploy to GitHub Pages")

    def _run(*args, **kw):
        return subprocess.run(args, check=True, capture_output=True, text=True, **kw)

    # Work in a temporary directory so we don't disturb the working tree
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Initialize a fresh repo and fetch just the target branch (if it exists)
        _run("git", "init", cwd=tmp)
        remote_url = _get_remote_url(remote, project_directory)
        _run("git", "remote", "add", "origin", remote_url, cwd=tmp)

        # Try to fetch the existing branch; it's fine if it doesn't exist yet
        try:
            _run("git", "fetch", "origin", branch, cwd=tmp)
            _run("git", "checkout", branch, cwd=tmp)
            # Clean out old content
            _run("git", "rm", "-rf", ".", cwd=tmp)
        except subprocess.CalledProcessError:
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

        _run("git", "commit", "-m", message, cwd=tmp)
        _run("git", "push", "origin", branch, "--force", cwd=tmp)


def _get_remote_url(remote: str, project_directory: Path) -> str:
    """Get the URL of a git remote configured in the project's repository."""
    result = subprocess.run(
        ["git", "remote", "get-url", remote],
        cwd=project_directory,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
