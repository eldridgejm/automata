"""Generate a static website from course materials."""

from .._config import PluginConfig, WebsiteConfig
from ..plugin import Plugin, merge_plugins
from . import exceptions
from ._elements import BasicElement, Element, TemplateElement
from ._frontmatter import Frontmatter
from ._generate import RenderContext, generate
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "PluginConfig",
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
