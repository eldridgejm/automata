from ..exceptions import Error


class CoreException(Error):
    """An exception raised by the core functionality."""


class DiscoveryError(CoreException):
    """An error raised during discovery."""
