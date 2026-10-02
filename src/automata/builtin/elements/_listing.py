"""Listing element for displaying collections in a table."""

from dataclasses import dataclass
from typing import Any, cast

import jinja2
import smartconfig

from automata.extensions import Extension
from automata.materials import Publication
from automata.util.resolution import string_or_template_string, unwrap_templates
from automata.website import TemplateElement
from automata.website.exceptions import WebsiteError

from ._common import get_collection

REQUIREMENTS_CONFIG_SCHEMA = {
    "type": "dict",
    "optional_keys": {
        "artifacts": {
            "type": "list",
            "element_schema": {"type": "string"},
            "default": [],
        },
        "metadata": {
            "type": "list",
            "element_schema": {"type": "string"},
            "default": [],
        },
        "non_null_metadata": {
            "type": "list",
            "element_schema": {"type": "string"},
            "default": [],
        },
        "cell_content_if_missing": {
            "type": "string",
            "nullable": True,
            "default": None,
        },
    },
}

COLUMN_CONFIG_SCHEMA = {
    "type": "dict",
    "required_keys": {
        "heading": {"type": "string"},
        "cell_content": string_or_template_string(),
    },
    "optional_keys": {
        "requires": {
            **REQUIREMENTS_CONFIG_SCHEMA,
            "nullable": True,
            "default": None,
        },
    },
}


class Listing(TemplateElement):
    """Element that displays publications from a collection in a table."""

    template = "elements/listing.html"
    schema = {
        "type": "dict",
        "required_keys": {
            "collection": {"type": "string"},
            "columns": {"type": "list", "element_schema": COLUMN_CONFIG_SCHEMA},
        },
        "optional_keys": {
            "numbered": {"type": "boolean", "default": False},
        },
    }

    def extra_resolution(
        self,
        config: smartconfig.types.Configuration,
    ) -> smartconfig.types.Configuration:
        return unwrap_templates(config)

    def template_vars(
        self,
        config: smartconfig.types.Configuration,
    ) -> dict[str, Any]:
        """Build the table: its headings, and one row per publication.

        Each cell's content is chosen and resolved here, so the template only
        lays out the table.
        """
        tvars = super().template_vars(config)
        resolve = tvars["resolve"]

        config_dict = cast(dict[str, Any], config)
        collection_name = cast(str, config_dict["collection"])
        collection = get_collection(self.context, collection_name, "listing")
        columns = config_dict["columns"]

        rows = []
        for number, (key, publication) in enumerate(
            sorted(collection.publications.items()), start=1
        ):
            cells = []
            for column in columns:
                content = _cell_content(publication, column)
                try:
                    cells.append(resolve(content, {"publication": publication}))
                except (WebsiteError, jinja2.TemplateError) as e:
                    raise WebsiteError(
                        f'Listing of "{collection_name}", column '
                        f'"{column["heading"]}", publication "{key}": {e}'
                    ) from e
            rows.append(ListingRow(number=number, cells=cells))

        tvars.update(
            {
                "headings": [column["heading"] for column in columns],
                "rows": rows,
                "numbered": config_dict["numbered"],
            }
        )
        return tvars


@dataclass
class ListingRow:
    """One row of a listing: its 1-based number and its cells' content."""

    number: int
    cells: list[str]


def _cell_content(publication: Publication, column: dict[str, Any]) -> str:
    """The (unresolved) content for a column's cell in a publication's row.

    If the column requires something the publication lacks and the column
    gives ``cell_content_if_missing``, that is used; otherwise ``cell_content``.
    """
    requires = column.get("requires")
    if requires is not None and requires["cell_content_if_missing"] is not None:
        if _is_something_missing(publication, requires):
            return str(requires["cell_content_if_missing"])
    return str(column["cell_content"])


def _is_something_missing(publication: Publication, requirements) -> bool:
    """Check if a publication is missing required artifacts or metadata."""
    if requirements is None:
        return False

    for artifact in requirements.get("artifacts", []):
        if artifact not in publication.artifacts:
            return True

    for metadata_key in requirements.get("metadata", []):
        if metadata_key not in publication.metadata:
            return True

    for metadata_key in requirements.get("non_null_metadata", []):
        if (
            metadata_key not in publication.metadata
            or publication.metadata[metadata_key] is None
        ):
            return True

    return False


def _collect(inputs):
    inputs.elements["listing"] = Listing
    return inputs


extension = Extension(
    name="builtin-listing",
    hooks={"on_render_collect": _collect},
)
