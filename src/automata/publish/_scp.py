"""SCP/rsync publish strategy.

Deploys the built site to a remote host using ``rsync`` (preferred) or
``scp`` as a fallback.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any


def publish(build_directory: Path, config: dict[str, Any]) -> None:
    """Deploy the built site to a remote host via rsync or scp.

    Parameters
    ----------
    build_directory : Path
        Path to the directory containing the built site.
    config : dict
        Strategy-specific configuration:

        - ``host`` (str): Remote hostname. **Required.**
        - ``remote_path`` (str): Destination path on the remote. **Required.**
        - ``user`` (str): SSH username. Optional; defaults to current user.
        - ``delete`` (bool): Whether to delete remote files not in source.
          Default ``True``. Only applies when using rsync.

    Raises
    ------
    ValueError
        If required config keys are missing.
    RuntimeError
        If neither rsync nor scp is available.

    """
    host = config.get("host")
    remote_path = config.get("remote_path")
    if not host or not remote_path:
        raise ValueError(
            "scp publish strategy requires 'host' and 'remote_path' in config"
        )

    user = config.get("user")
    delete = config.get("delete", True)

    destination = f"{user}@{host}:{remote_path}" if user else f"{host}:{remote_path}"

    # Ensure the source path ends with / so rsync copies contents, not the dir
    source = str(build_directory).rstrip("/") + "/"

    if shutil.which("rsync"):
        cmd = ["rsync", "-az", "--info=progress2"]
        if delete:
            cmd.append("--delete")
        cmd += [source, destination]
    elif shutil.which("scp"):
        cmd = ["scp", "-r", source, destination]
    else:
        raise RuntimeError(
            "Neither rsync nor scp found on PATH. "
            "Install one of them to use the scp publish strategy."
        )

    subprocess.run(cmd, check=True)
