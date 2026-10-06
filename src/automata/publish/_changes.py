"""What a publish would change: the result of a dry run."""

import dataclasses
import inspect
from typing import Any, Literal

Status = Literal["added", "modified", "deleted"]


@dataclasses.dataclass(frozen=True)
class Change:
    """A file a publish would add, modify, or delete.

    Attributes
    ----------
    status : str
        ``"added"``, ``"modified"``, or ``"deleted"``.
    path : str
        The file's path, relative to the site's root, with ``/`` separators.

    """

    status: Status
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "path": self.path}


def supports_dry_run(publisher: Any) -> bool:
    """Whether the strategy *publisher* can do a dry run: whether it takes a
    ``dry_run`` keyword argument (and, given ``dry_run=True``, returns the
    :class:`Change` list rather than publishing)."""
    try:
        parameters = inspect.signature(publisher).parameters
    except (TypeError, ValueError):
        return False
    return "dry_run" in parameters
