from ._common import is_something_missing, basic_element

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


def _listing_vars(context, element_config):
    collections = context.materials.collections
    collection = collections[element_config["collection"]]
    publications_and_keys = sorted(collection.publications.items())
    publications = [v for (j, v) in publications_and_keys]

    return {"is_something_missing": is_something_missing, "publications": publications}


listing = basic_element("listing.html", SCHEMA, _listing_vars)
