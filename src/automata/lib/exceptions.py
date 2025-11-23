"""Exceptions used in :mod:`automata.lib`."""


class Error(Exception):
    """Generic error, and base class for all exceptions in this module."""


class DiscoveryError(Error):
    """A configuration file is not valid.

    The string representation of this exception will contain the error message
    and the path to the file that caused the error.

    Attributes
    ----------
    msg : str
        The error message.
    path : Path
        The path to the file that caused the error.

    """

    def __init__(self, msg, path):
        self.path = path
        self.msg = msg

    def __str__(self):
        return f"Error reading {self.path}: {self.msg}"


class BuildError(Error):
    """Problem while building the artifact."""
