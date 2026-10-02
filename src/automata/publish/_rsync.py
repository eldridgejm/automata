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


def publish(
    build_directory: Path,
    config: dict[str, Any],
    project_directory: Path,
    *,
    run: Callable[..., Any] = subprocess.run,
) -> None:
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

    Raises
    ------
    automata.exceptions.Error
        If ``host`` or ``remote_path`` is missing, or rsync is not installed.

    """
    host = config.get("host")
    remote_path = config.get("remote_path")
    for key, value in [("host", host), ("remote_path", remote_path)]:
        if not value:
            raise Error(f"The rsync publish strategy requires '{key}' in its config.")

    user = config.get("user")
    destination = f"{user}@{host}:{remote_path}" if user else f"{host}:{remote_path}"

    # a trailing / makes rsync copy the directory's contents, not the directory
    source = str(build_directory).rstrip("/") + "/"

    cmd = ["rsync", "-az", "--info=progress2"]
    if config.get("delete", True):
        cmd.append("--delete")
    cmd += [source, destination]

    try:
        run(cmd, check=True)
    except FileNotFoundError:
        raise Error(
            "The rsync publish strategy needs rsync, which was not found on PATH."
        ) from None
