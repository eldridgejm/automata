"""Generate a static website from course materials."""

from . import exceptions
from ._config import WebsiteConfig
from ._content import WebsiteContent
from ._elements import BasicElement, Element, TemplateElement
from ._frontmatter import Frontmatter
from ._generate import RenderContext, generate
from ._theme import Theme, ThemeHooks
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "WebsiteConfig",
    "WebsiteContent",
    "Theme",
    "ThemeHooks",
    "Frontmatter",
    "PageError",
    "Element",
    "BasicElement",
    "TemplateElement",
    "generate",
    "exceptions",
]
