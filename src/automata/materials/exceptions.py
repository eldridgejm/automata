"""Exceptions used in :mod:`automata.materials`."""

import pathlib

from ..exceptions import Error as _Error


class MaterialsError(_Error):
    """Generic error, and base class for all exceptions in this module."""


class DiscoveryError(MaterialsError):
    """A configuration file is not valid.

    The string representation of this exception will contain the error message
    and the path to the file that caused the error.

    Attributes
    ----------
    msg : str
        The error message.
    path : Path
        The path to the file that caused the error.
    reason : str | None
        For an invalid value, the problem, without its location.
    keypath : tuple | None
        For an invalid value, its keypath within the file, as the user wrote it.
    line : int | None
        The line of the file with the problem, if known.

    """

    def __init__(
        self,
        msg: str,
        path: pathlib.Path,
        *,
        reason: str | None = None,
        keypath: tuple | None = None,
        line: int | None = None,
    ):
        self.path = path
        self.msg = msg
        self.reason = reason
        self.keypath = keypath
        self.line = line

    @classmethod
    def at(
        cls, reason: str, keypath: tuple, path: pathlib.Path, line: int | None = None
    ) -> "DiscoveryError":
        """An error about the value at *keypath* (on *line*) in the file at *path*."""
        from ..util.resolution import describe_config_error

        return cls(
            describe_config_error(reason, keypath),
            path,
            reason=reason,
            keypath=keypath,
            line=line,
        )

    def __str__(self):
        location = self.path if self.line is None else f"{self.path}:{self.line}"
        return f"{location}: {self.msg}"


class BuildError(MaterialsError):
    """Problem while building an artifact.

    The message names the artifact by its key path (e.g.
    ``homeworks/01-intro/homework.pdf``) once :func:`automata.materials.build`
    has recorded it in :attr:`key_path`, and by *fallback_name* otherwise.

    Parameters
    ----------
    summary : str
        A one-line summary containing ``{name}`` where the artifact's name
        goes (other braces doubled, as for :meth:`str.format`).
    fallback_name : str
        The name to use when the key path is not known.
    details : str
        Further lines (the recipe, its directory, its output).

    """

    def __init__(self, summary: str, *, fallback_name: str, details: str = ""):
        self.summary = summary
        self.fallback_name = fallback_name
        self.details = details
        self.key_path: list[str] = []
        super().__init__(summary)

    @property
    def name(self) -> str:
        return "/".join(self.key_path) or self.fallback_name

    def __str__(self) -> str:
        return self.summary.format(name=self.name) + self.details
