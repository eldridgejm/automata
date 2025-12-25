"""Generate a static website from course materials."""

from . import exceptions
from ._config import Config, ThemeConfig
from ._elements import element, template_element
from ._frontmatter import Frontmatter
from ._generate import generate
from ._render import RenderContext
from ._theme import Theme
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "Config",
    "ThemeConfig",
    "Theme",
    "Frontmatter",
    "PageError",
    "element",
    "template_element",
    "generate",
    "exceptions",
]
