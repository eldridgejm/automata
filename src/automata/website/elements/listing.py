"""Listing element for displaying course materials in a table.

A listing element renders a table displaying publications from a collection,
such as homework assignments, lectures, or labs. Each row represents a
publication, and columns are configurable to show metadata, links to artifacts,
or custom content.

Features
--------
- Displays publications from a specified collection in tabular format
- Configurable columns with custom headings and cell content templates
- Conditional rendering based on artifact availability or metadata presence
- Optional row numbering
- Cell content supports Jinja2 templating with access to publication data

Schema
------
collection (str): The name of the collection to display (e.g., "homework").
columns (list): List of column definitions, each containing:
    - heading (str): The column header text.
    - cell_content (str): Jinja2 template for the cell content. Has access
      to ``publication`` (the current publication) and ``artifacts``/``metadata``.
    - requires (dict, optional): Conditions that must be met for the cell
      to render. If not met, the cell shows ``cell_content_if_missing`` or
      is left empty. Contains:
        - artifacts (list[str]): Artifact names that must exist.
        - metadata (list[str]): Metadata keys that must be present.
        - non_null_metadata (list[str]): Metadata keys that must be non-null.
        - cell_content_if_missing (str | None): Fallback content if
          requirements are not met.
numbered (bool, optional): If True, adds a leading column with row numbers.
    Defaults to False.

Example YAML configuration
--------------------------
::

    listing:
      collection: homework
      numbered: true
      columns:
        - heading: Name
          cell_content: "{{ publication.metadata.name }}"
        - heading: Due Date
          cell_content: "{{ publication.metadata.due.strftime('%b %d') }}"
        - heading: Assignment
          cell_content: "[PDF]({{ artifacts['homework.pdf'].path }})"
          requires:
            artifacts: [homework.pdf]
            cell_content_if_missing: "Not yet released"
        - heading: Solutions
          cell_content: "[PDF]({{ artifacts['solution.pdf'].path }})"
          requires:
            artifacts: [solution.pdf]
"""

from typing import Any, Mapping

from .._types import RenderContext
from ._common import basic_element, is_something_missing

COLUMN_SCHEMA = {
    "type": "dict",
    "required_keys": {
        "cell_content": {"type": "string"},
        "heading": {"type": "string"},
    },
    "optional_keys": {
        "requires": {
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
            "default": None,
            "nullable": True,
        },
    },
}

SCHEMA = {
    "type": "dict",
    "required_keys": {
        "collection": {"type": "string"},
        "columns": {"type": "list", "element_schema": COLUMN_SCHEMA},
    },
    "optional_keys": {"numbered": {"type": "boolean", "default": False}},
}


def _listing_vars(
    context: RenderContext, element_config: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Compute render-time variables for the listing element."""
    assert context.materials is not None
    collections = context.materials.collections
    collection = collections[element_config["collection"]]
    publications_and_keys = sorted(collection.publications.items())
    publications = [v for (j, v) in publications_and_keys]

    return {"is_something_missing": is_something_missing, "publications": publications}


listing = basic_element("listing.html", SCHEMA, _listing_vars)
