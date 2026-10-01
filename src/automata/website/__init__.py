"""Generate a static website from course materials."""

from . import exceptions
from ._elements import BasicElement, Element, TemplateElement
from ._frontmatter import Frontmatter
from ._render import RenderContext, render
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "Frontmatter",
    "PageError",
    "Element",
    "BasicElement",
    "TemplateElement",
    "render",
    "exceptions",
]
