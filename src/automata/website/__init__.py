"""Generate a static website from course materials."""

from . import exceptions
from ._config import Config
from ._frontmatter import Frontmatter
from ._generate import generate
from ._render import RenderContext, render_page_from_html, render_page_from_markdown
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "Config",
    "Frontmatter",
    "PageError",
    "render_page_from_markdown",
    "render_page_from_html",
    "generate",
    "exceptions",
]
