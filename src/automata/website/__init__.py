"""Generate a static website from course materials."""

from . import exceptions
from ._config import Config, ThemeConfig
from ._frontmatter import Frontmatter
from ._generate import generate
from ._render import RenderContext
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "Config",
    "ThemeConfig",
    "Frontmatter",
    "PageError",
    "generate",
    "exceptions",
]
