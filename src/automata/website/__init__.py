"""Static site generator for course webpages."""

from . import themes
from ._generate import generate
from ._initialize import initialize
from .exceptions import ElementError, Error, PageError

__all__ = ["generate", "initialize", "Error", "PageError", "ElementError", "themes"]
