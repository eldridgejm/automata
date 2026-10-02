import pathlib

from ..exceptions import Error as _Error


class WebsiteError(_Error):
    """Base class for exceptions in this module."""


class PageError(WebsiteError):
    """Exception raised for errors during page processing.

    This includes errors during frontmatter parsing, rendering, or other
    page-related operations.

    Parameters
    ----------
    message : str
        Description of the error
    path : pathlib.Path
        Path to the file that caused the error
    line : int | None
        The line of the file with the error, if known

    """

    def __init__(self, message: str, path: pathlib.Path, line: int | None = None):
        self.message = message
        self.path = path
        self.line = line
        location = str(path) if line is None else f"{path}:{line}"
        super().__init__(f"{location}: {message}")
