"""rsync publish strategy.

Mirrors the built site to a directory on a remote host over SSH with
``rsync``, deleting remote files that are no longer in the build (so that
withdrawn materials and deleted pages do not linger on the server).
"""

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..exceptions import Error
from ._changes import Change
from ._options import check_options


def publish(
    build_directory: Path,
    config: dict[str, Any],
    project_directory: Path,
    *,
    run: Callable[..., Any] = subprocess.run,
    dry_run: bool = False,
) -> list[Change] | None:
    """Deploy the built site to a remote host with rsync.

    Parameters
    ----------
    build_directory : Path
        Path to the directory containing the built site.
    config : dict
        Strategy-specific configuration:

        - ``host`` (str): Remote hostname. **Required.**
        - ``remote_path`` (str): Destination path on the remote. **Required.**
        - ``user`` (str): SSH username. Optional; defaults to the SSH default.
        - ``delete`` (bool): Whether to delete remote files not in the build.
          Default ``True``.
    project_directory : Path
        The project root (unused; part of the publisher signature).
    run : Callable
        Runs the command (default :func:`subprocess.run`). Tests pass a fake.
    dry_run : bool
        Instead of publishing, return what publishing would change, from
        ``rsync --dry-run --itemize-changes`` (which changes nothing on the
        host).

    Returns
    -------
    list[Change] | None
        For a dry run, the files that would be added, modified, or deleted, in
        order of path; otherwise None.

    Raises
    ------
    automata.exceptions.Error
        If ``host`` or ``remote_path`` is missing, or rsync is not installed.

    """
    check_options("rsync", config, ("delete", "host", "remote_path", "user"))
    host = config.get("host")
    remote_path = config.get("remote_path")
    for key, value in [("host", host), ("remote_path", remote_path)]:
        if not value:
            raise Error(f"The rsync publish strategy requires '{key}' in its config.")

    user = config.get("user")
    destination = f"{user}@{host}:{remote_path}" if user else f"{host}:{remote_path}"

    # a trailing / makes rsync copy the directory's contents, not the directory
    source = str(build_directory).rstrip("/") + "/"

    # --progress, not --info=progress2, which macOS's rsync (openrsync) rejects
    cmd = ["rsync", "-az"]
    cmd += ["--dry-run", "--itemize-changes"] if dry_run else ["--progress"]
    if config.get("delete", True):
        cmd.append("--delete")
    cmd += [source, destination]

    try:
        if dry_run:
            result = run(cmd, check=True, capture_output=True, text=True)
            return _itemized_changes(result.stdout)
        run(cmd, check=True)
    except FileNotFoundError:
        raise Error(
            "The rsync publish strategy needs rsync, which was not found on PATH."
        ) from None
    except subprocess.CalledProcessError as e:
        raise Error(
            f"rsync to {destination} failed with exit status {e.returncode} (its "
            f"output is above)."
        ) from None
    return None


def _itemized_changes(itemized: str) -> list[Change]:
    """The files changed in *itemized*, the output of ``rsync
    --itemize-changes``: each line a code (e.g. ``<f.st......``, sent with
    a new size and time) and a path, or ``*deleting`` and a path. Directories,
    and files whose contents aren't sent, are left out."""
    changes = []
    for line in itemized.splitlines():
        code, _, path = line.partition(" ")
        path = path.lstrip(" ")
        if not path or path.endswith("/"):
            continue
        if code == "*deleting":
            changes.append(Change("deleted", path))
        # sent (<), received (>), or changed locally (c): a file's contents
        elif len(code) > 2 and code[0] in "<>c" and code[1] == "f":
            new = set(code[2:]) == {"+"}
            changes.append(Change("added" if new else "modified", path))
    return sorted(changes, key=lambda change: change.path)
