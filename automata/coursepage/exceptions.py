class Error(Exception):
    """A general error."""


class PageError(Error):
    """A problem in one of the user-defined pages."""


class ElementError(Error):
    """A problem while evaluating an element."""
