"""Content dataclass for website generation."""

from dataclasses import dataclass, field
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING

from ..materials import ExportedMaterials

if TYPE_CHECKING:
    from ._elements import Element


@dataclass
class WebsiteContent:
    """Content resources for website generation.

    Groups the data needed for website generation: templates, pages, static
    files, elements, and materials.  Hooks and configuration are separate
    concerns and are not included here.
    """

    templates: dict[str, str] = field(default_factory=dict)
    pages: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    elements: dict[str, type["Element"]] = field(default_factory=dict)
    materials: ExportedMaterials | None = None
