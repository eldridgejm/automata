"""Helpers shared by the built-in elements."""

from typing import Any

from automata.website import RenderContext
from automata.website.exceptions import WebsiteError


def get_collection(context: RenderContext, name: str, element: str) -> Any:
    """The named collection, or a WebsiteError listing the available ones."""
    collections = context.materials.collections
    if name not in collections:
        available = ", ".join(sorted(collections)) or "none"
        raise WebsiteError(
            f'The {element} refers to unknown collection "{name}". '
            f"Available collections: {available}."
        )
    return collections[name]
