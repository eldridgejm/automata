"""Listing element for displaying collections in a table."""

from typing import Any, cast

import smartconfig

from automata.util.resolution import string_or_template_string, unwrap_templates
from automata.website import TemplateElement

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
        """Provide additional template variables."""
        tvars = super().template_vars(config)

        # Get the collection
        config_dict = cast(dict[str, Any], config)
        collection_name = cast(str, config_dict["collection"])
        collection = self.context.materials.collections[collection_name]

        # Get publications sorted by key
        publications_and_keys = sorted(collection.publications.items())
        publications = [v for (k, v) in publications_and_keys]

        tvars.update(
            {
                "publications": publications,
            }
        )

        return tvars
