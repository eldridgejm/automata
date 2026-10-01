"""Extensions: collections of hooks that customize automata's behavior.

This is the public API for writing and loading extensions. A theme is an
extension that provides page templates; see the extensions documentation.
"""

from ._apply import apply_extension, apply_extensions
from ._directory import extension_from_directory
from ._entry_point import extension_from_entry_point
from ._types import EXTENSIONS_GROUP, THEMES_GROUP, Extension

__all__ = [
    "EXTENSIONS_GROUP",
    "THEMES_GROUP",
    "Extension",
    "apply_extension",
    "apply_extensions",
    "extension_from_directory",
    "extension_from_entry_point",
]
