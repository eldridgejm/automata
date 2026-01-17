"""Generate a static website from course materials."""

from .._plugin import Plugin, merge_plugins
from . import exceptions
from ._config import WebsiteConfig
from ._elements import BasicElement, Element, TemplateElement
from ._frontmatter import Frontmatter
from ._generate import RenderContext, generate
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "WebsiteConfig",
    "Plugin",
    "merge_plugins",
    "Frontmatter",
    "PageError",
    "Element",
    "BasicElement",
    "TemplateElement",
    "generate",
    "exceptions",
]
