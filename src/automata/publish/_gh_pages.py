"""GitHub Pages publish strategy.

Pushes the contents of the build directory to a branch (default
``gh-pages``) of a GitHub repository, given as ``org/name`` and pushed to
over SSH, or else of the project's ``origin``. To publish to any other git
repository (over HTTPS, say), use the git strategy.
"""

import re
from pathlib import Path
from typing import Any

from ..exceptions import Error
from ._changes import Change
from ._git import push, remote_url
from ._options import check_options

# where GitHub repositories are pushed to, over SSH
GITHUB = "git@github.com:"


def repository_url(repository: str, github: str = GITHUB) -> str:
    """The URL pushed to for the GitHub *repository* (``org/name``)."""
    return f"{github}{repository}.git"


def publish(
    build_directory: Path,
    config: dict[str, Any],
    project_directory: Path,
    github: str = GITHUB,
    *,
    dry_run: bool = False,
) -> list[Change]:
    """Deploy the built site to GitHub Pages.

    The site replaces the contents of the target branch, in a single commit (no
    commit is made if nothing changed).

    Parameters
    ----------
    build_directory : Path
        Path to the directory containing the built site.
    config : dict
        Strategy-specific configuration:

        - ``repository`` (str): The GitHub repository, as ``org/name`` (e.g.
          ``"dsc-courses/dsc40b-2026-fa"``), pushed to over SSH. By default,
          the project's ``origin`` remote.
        - ``branch`` (str): Target branch name. Default ``"gh-pages"``.
        - ``message`` (str): Commit message. Default ``"Deploy to GitHub Pages"``.
        - ``user_name``, ``user_email`` (str): The commit's author (see
          :func:`automata.publish._git.push`).
    project_directory : Path
        The project root, whose git repository has the ``origin`` remote and
        the default identity.
    github : str
        What a repository's ``org/name`` is appended to (with ``.git``) to make
        the URL pushed to.
    dry_run : bool
        Instead of publishing, return what publishing would change (see
        :func:`automata.publish._git.push`).

    Returns
    -------
    list[Change]
        The changes made (or, for a dry run, that would be), in order of path.

    Raises
    ------
    automata.exceptions.Error
        If ``repository`` isn't like ``org/name``, no commit identity can be
        found, or publishing fails.

    """
    check_options(
        "gh-pages",
        config,
        ("branch", "message", "repository", "user_email", "user_name"),
    )
    if "repository" in config:
        repository = config["repository"]
        if not (
            isinstance(repository, str) and re.fullmatch(r"[\w.-]+/[\w.-]+", repository)
        ):
            raise Error(
                'The gh-pages publish strategy\'s "repository" is a GitHub '
                f'repository, written like "org/name", not "{repository}". To '
                'publish to another repository, use the "git" strategy, with '
                'its "url".'
            )
        url = repository_url(repository.removesuffix(".git"), github)
        source = f'GitHub repository "{repository}" ({url})'
    else:
        url = remote_url("origin", project_directory, "gh-pages")
        source = f'remote "origin" ({url})'
    return push(
        build_directory,
        project_directory,
        url=url,
        source=source,
        branch=config.get("branch", "gh-pages"),
        message=config.get("message", "Deploy to GitHub Pages"),
        config=config,
        strategy="gh-pages",
        dry_run=dry_run,
    )
