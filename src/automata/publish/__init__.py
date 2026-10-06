"""Publish strategies for deploying built sites."""

from . import _registry as registry
from ._changes import Change, supports_dry_run
from ._gh_pages import publish as _gh_pages_publish
from ._git import publish as _git_publish
from ._rsync import publish as _rsync_publish

# Register builtin strategies
registry.register("gh-pages", _gh_pages_publish)
registry.register("git", _git_publish)
registry.register("rsync", _rsync_publish)

__all__ = ["Change", "registry", "supports_dry_run"]
