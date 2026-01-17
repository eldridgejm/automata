"""Generate a static website from course materials."""

from .._config import ExtensionConfig, WebsiteConfig
from ..extension import Extension, merge_extensions
from . import exceptions
from ._elements import BasicElement, Element, TemplateElement
from ._frontmatter import Frontmatter
from ._generate import RenderContext, generate
from .exceptions import PageError

__all__ = [
    "RenderContext",
    "ExtensionConfig",
    "WebsiteConfig",
    "Extension",
    "merge_extensions",
    "Frontmatter",
    "PageError",
    "Element",
    "BasicElement",
    "TemplateElement",
    "generate",
    "exceptions",
]
