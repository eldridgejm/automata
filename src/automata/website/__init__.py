"""Generate a static website from course materials."""

from . import exceptions
from ._config import ThemeConfig, WebsiteConfig
from ._elements import BasicElement, Element, TemplateElement
from ._frontmatter import Frontmatter
from ._generate import generate
from ._render import RenderContext
from ._theme import Theme
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "WebsiteConfig",
    "ThemeConfig",
    "Theme",
    "Frontmatter",
    "PageError",
    "Element",
    "BasicElement",
    "TemplateElement",
    "generate",
    "exceptions",
]
