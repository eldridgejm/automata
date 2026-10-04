"""Initializing a new project (automata init)."""

import importlib.resources
from importlib.resources.abc import Traversable
from pathlib import Path

from .config import find_config
from .exceptions import Error

# the project template: its files are copied into the new project as they are
_TEMPLATE = importlib.resources.files(__package__) / "init_templates" / "default"


def _template_files(
    node: Traversable, parts: tuple[str, ...] = ()
) -> dict[tuple[str, ...], Traversable]:
    """The files under *node*, keyed by their path's parts (relative to it)."""
    files = {}
    for entry in node.iterdir():
        if entry.name.startswith(".") or entry.name == "__pycache__":
            continue
        entry_parts = parts + (entry.name,)
        if entry.is_dir():
            files.update(_template_files(entry, entry_parts))
        else:
            files[entry_parts] = entry
    return files


def create_project(path: Path) -> list[Path]:
    """Create a new project in the directory *path* (see :meth:`Automata.init`),
    returning the files created."""
    files = _template_files(_TEMPLATE)

    for name in sorted({parts[0] for parts in files}):
        if (path / name).exists():
            raise Error(
                f'"{path / name}" already exists. automata init only creates a '
                f"new project, and doesn't change existing files."
            )

    enclosing = find_config(path)
    if enclosing is not None:
        raise Error(
            f'"{path}" is inside the project configured by "{enclosing}". '
            f"automata init doesn't create a project inside another."
        )

    created = []
    for parts, source in sorted(files.items()):
        destination = path.joinpath(*parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        created.append(destination)
    return created
