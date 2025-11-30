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

from smartconfig import Prototype

from .._types import RenderContext
from ._common import basic_element, is_something_missing


class Requires(Prototype):
    artifacts: list[str] = []
    metadata: list[str] = []
    non_null_metadata: list[str] = []
    cell_content_if_missing: str | None = None


class Column(Prototype):
    heading: str
    cell_content: str
    requires: Requires | None = None


class Config(Prototype):
    collection: str
    columns: list[Column]
    numbered: bool = False


def _listing_vars(
    context: RenderContext, element_config: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Compute render-time variables for the listing element.

    Extracts the specified collection from the materials universe and prepares
    the publications for rendering. Publications are sorted by their keys
    (typically publication identifiers like "01", "02", etc.) to ensure
    consistent ordering in the table.

    Parameters
    ----------
    context : RenderContext
        The rendering context containing the materials universe.
    element_config : Mapping[str, Any]
        The resolved element configuration containing the ``collection`` key.

    Returns
    -------
    Mapping[str, Any]
        A dict with:
        - ``publications``: List of Publication objects, sorted by key.
        - ``is_something_missing``: Helper function for conditional rendering.
    """
    assert context.materials is not None
    collections = context.materials.collections
    collection = collections[element_config["collection"]]
    publications_and_keys = sorted(collection.publications.items())
    publications = [v for (j, v) in publications_and_keys]

    return {"is_something_missing": is_something_missing, "publications": publications}


element = basic_element("elements/listing.html", Config._schema(), _listing_vars)
