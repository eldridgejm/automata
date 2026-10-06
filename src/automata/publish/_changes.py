"""What a publish changed, or (for a dry run) would change."""

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
    list of :class:`Change` it would make rather than publishing)."""
    try:
        parameters = inspect.signature(publisher).parameters
    except (TypeError, ValueError):
        return False
    return "dry_run" in parameters


@dataclasses.dataclass(frozen=True)
class PublishResult:
    """What publishing to a target did, or, for a dry run, would do.

    Attributes
    ----------
    target : str
        The publish target's name.
    strategy : str
        Its strategy, e.g. ``"gh-pages"``.
    dry_run : bool
        Whether this was a dry run (nothing was published).
    changes : list[Change] | None
        The files added, modified, or deleted, in order of path (empty if
        nothing changed), or None if the strategy doesn't report them (an
        extension's may not; rsync doesn't, except in a dry run).

    """

    target: str
    strategy: str
    dry_run: bool
    changes: list[Change] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "dry_run": self.dry_run,
            "changes": (
                None
                if self.changes is None
                else [change.to_dict() for change in self.changes]
            ),
        }
