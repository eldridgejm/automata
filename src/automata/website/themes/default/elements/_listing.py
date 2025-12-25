"""Listing element for displaying collections in a table."""

from typing import Any, cast

import jinja2
import smartconfig

from automata.website import TemplateElement
from automata.website._render import RenderContext


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
        # Get the collection
        config_dict = cast(dict[str, Any], config)
        collection_name = cast(str, config_dict["collection"])
        collection = context.materials.collections[collection_name]

        # Get publications sorted by key
        publications_and_keys = sorted(collection.publications.items())
        publications = [v for (k, v) in publications_and_keys]

        # Helper function to check if something is missing
        def is_something_missing(publication, requirements):
            """Check if a publication is missing required artifacts or metadata."""
            if requirements is None:
                return False

            # Check for missing artifacts
            for artifact in requirements.get("artifacts", []):
                if artifact not in publication.artifacts:
                    return True

            # Check for missing metadata
            for metadata_key in requirements.get("metadata", []):
                if metadata_key not in publication.metadata:
                    return True

            # Check for null metadata
            for metadata_key in requirements.get("non_null_metadata", []):
                if (
                    metadata_key not in publication.metadata
                    or publication.metadata[metadata_key] is None
                ):
                    return True

            return False

        # Helper function to evaluate template strings
        def evaluate(template_str, publication):
            """Evaluate a Jinja2 template string with publication context."""
            try:
                template = jinja2.Template(
                    template_str,
                    undefined=jinja2.StrictUndefined,
                )
                return template.render(publication=publication, context=context)
            except jinja2.UndefinedError as exc:
                raise Exception(f"Error evaluating template: {exc}")

        return {
            "publications": publications,
            "is_something_missing": is_something_missing,
            "evaluate": evaluate,
        }
