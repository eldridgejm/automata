"""Generate a static website from course materials."""

from .._extension import extension_from_directory, extension_from_entry_point
from . import exceptions
from ._elements import BasicElement, Element, TemplateElement
from ._frontmatter import Frontmatter
from ._generate import RenderContext, generate
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "Frontmatter",
    "PageError",
    "Element",
    "BasicElement",
    "TemplateElement",
    "generate",
    "extension_from_directory",
    "extension_from_entry_point",
    "exceptions",
]
