"""Static site generator for course webpages."""

from ._build import build
from ._initialize import initialize
from .exceptions import ElementError, Error, PageError

__all__ = ["build", "initialize", "Error", "PageError", "ElementError"]
