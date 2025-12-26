"""Listing element for displaying collections in a table."""

from typing import Any, cast

import smartconfig

from automata.website import RenderContext, TemplateElement


class RequirementsConfig(smartconfig.Prototype):
    """Configuration for conditional content requirements."""

    artifacts: list[str] = []
    metadata: list[str] = []
    non_null_metadata: list[str] = []
    cell_content_if_missing: str | None = None


class ColumnConfig(smartconfig.Prototype):
    """Configuration for a single column in the listing."""

    heading: str
    cell_content: str
    requires: RequirementsConfig | None = None


class Listing(TemplateElement):
    """Element that displays publications from a collection in a table."""

    template = "elements/listing.html"
    schema = {
        "type": "dict",
        "required_keys": {
            "collection": {"type": "string"},
            "columns": {"type": "list", "element_schema": ColumnConfig._schema()},
        },
        "optional_keys": {
            "numbered": {"type": "boolean", "default": False},
        },
    }

    def template_vars(
        self,
        context: RenderContext,
        config: smartconfig.types.Configuration,
    ) -> dict[str, Any]:
        """Provide additional template variables."""
        tvars = super().template_vars(context, config)

        # Get the collection
        config_dict = cast(dict[str, Any], config)
        collection_name = cast(str, config_dict["collection"])
        collection = context.materials.collections[collection_name]

        # Get publications sorted by key
        publications_and_keys = sorted(collection.publications.items())
        publications = [v for (k, v) in publications_and_keys]

        tvars.update(
            {
                "publications": publications,
            }
        )

        return tvars
