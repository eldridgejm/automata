"""Publish strategies for deploying built sites."""

from . import _registry as registry
from ._gh_pages import publish as _gh_pages_publish
from ._scp import publish as _scp_publish

# Register builtin strategies
registry.register("gh-pages", _gh_pages_publish)
registry.register("scp", _scp_publish)

__all__ = ["registry"]
